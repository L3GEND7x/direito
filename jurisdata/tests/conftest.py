from __future__ import annotations

import os
import re
import sys
from dataclasses import replace
from pathlib import Path

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config  # noqa: E402
from app.contexto import montar  # noqa: E402
from app.main import criar_app  # noqa: E402
from app.models import Cliente, Perfil, Processo, Usuario, agora  # noqa: E402
from app.security import hash_senha  # noqa: E402

SENHA = "Senha-Forte-123!"


# Para rodar contra PostgreSQL: JURISDATA_TEST_DATABASE_URL=postgresql+psycopg://... pytest
URL_TESTE = os.environ.get("JURISDATA_TEST_DATABASE_URL")


@pytest.fixture
def cfg(tmp_path):
    return Config(
        database_url=URL_TESTE or f"sqlite:///{tmp_path / 'teste.db'}",
        secret_key="s" * 48,
        data_key=Fernet.generate_key().decode(),
        cookie_secure=False,
        modo_simulado=True,
    )


@pytest.fixture
def ctx(cfg):
    if URL_TESTE:
        from app.db import Base, criar_engine

        engine = criar_engine(URL_TESTE)
        Base.metadata.drop_all(engine)
        engine.dispose()
    contexto = montar(cfg)
    yield contexto
    contexto.engine.dispose()


@pytest.fixture
def app(ctx):
    return criar_app(ctx=ctx)


@pytest.fixture
def db(ctx):
    with ctx.fabrica() as sessao:
        yield sessao


def criar_usuario(ctx, perfil: Perfil, email: str, nome: str | None = None, pronto: bool = True) -> tuple[Usuario, str]:
    segredo = pyotp.random_base32()
    with ctx.fabrica() as s:
        u = Usuario(
            nome=nome or email.split("@")[0].title(), email=email, perfil=perfil, senha_hash=hash_senha(SENHA),
            oab="SP 000000" if perfil == Perfil.ADVOGADO else None,
            trocar_senha=not pronto, mfa_ativo=pronto, mfa_segredo_cifrado=ctx.cofre.cifrar(segredo) if pronto else None,
            termo_aceito_em=agora() if pronto else None,
        )
        s.add(u)
        s.commit()
        s.refresh(u)
        return u, segredo


CSRF = re.compile(r'name="csrf" value="([^"]+)"')


def csrf_de(html: str) -> str:
    m = CSRF.search(html)
    assert m, "csrf não encontrado"
    return m.group(1)


def entrar(app, email: str, segredo: str, senha: str = SENHA) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    r = c.get("/login")
    r = c.post("/login", data={"csrf": csrf_de(r.text), "email": email, "senha": senha})
    assert r.status_code == 303, r.text
    r = c.get("/login/mfa")
    r = c.post("/login/mfa", data={"csrf": csrf_de(r.text), "codigo": pyotp.TOTP(segredo).now()})
    assert r.status_code == 303 and r.headers["location"] == "/", r.text
    return c


def csrf_pagina(c: TestClient, url: str = "/") -> str:
    r = c.get(url)
    assert r.status_code == 200, (url, r.status_code, r.text[:500])
    return csrf_de(r.text)


@pytest.fixture
def equipe(ctx):
    adv, s_adv = criar_usuario(ctx, Perfil.ADVOGADO, "adv@escritorio.test", "Ana Advogada")
    adv2, s_adv2 = criar_usuario(ctx, Perfil.ADVOGADO, "adv2@escritorio.test", "Bruno Advogado")
    ass, s_ass = criar_usuario(ctx, Perfil.ASSISTENTE, "ass@escritorio.test", "Carla Assistente")
    aud, s_aud = criar_usuario(ctx, Perfil.AUDITOR, "aud@escritorio.test", "Davi Auditor")
    adm, s_adm = criar_usuario(ctx, Perfil.ADMIN, "adm@escritorio.test", "Eva Admin")
    with ctx.fabrica() as s:
        cli = Cliente(nome="Cliente Teste", tipo="PF", criado_por_id=adv.id)
        s.add(cli)
        s.flush()
        proc = Processo(numero_cnj=None, identificacao_demanda="Execução de título — teste", cliente_id=cli.id,
                        area="execucao", responsavel_id=adv.id)
        s.add(proc)
        s.commit()
        pid = proc.id
    return {
        "adv": (adv, s_adv), "adv2": (adv2, s_adv2), "ass": (ass, s_ass), "aud": (aud, s_aud), "adm": (adm, s_adm),
        "processo_id": pid,
    }


def com(cfg: Config, **kw) -> Config:
    return replace(cfg, **kw)
