"""Sessões, autenticação, autorização, CSRF e renderização."""

from __future__ import annotations

import hmac
from datetime import timedelta
from pathlib import Path
from typing import Iterator

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .contexto import Contexto
from .models import PERFIL_ROTULO, Perfil, Sessao, Usuario, agora, como_utc
from .security import novo_token, sha256
from .services.relatorios import FUSO

COOKIE_SESSAO = "jd_sessao"
COOKIE_PRE = "jd_pre"  # CSRF das telas antes do login (double submit)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _data(valor) -> str:
    return valor.strftime("%d/%m/%Y") if valor else "—"


def _data_hora_curta(valor) -> str:
    if not valor:
        return "—"
    return como_utc(valor).astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


templates.env.filters["data"] = _data
templates.env.filters["dh"] = _data_hora_curta

MENSAGENS = {
    "senha_ok": "Senha alterada.",
    "mfa_ok": "Autenticação em dois fatores ativada.",
    "saiu": "Você saiu do sistema.",
    "expirou": "Sua sessão expirou. Entre novamente.",
    "cliente_ok": "Cliente cadastrado.",
    "processo_ok": "Processo/demanda cadastrado.",
    "processo_encerrado": "Processo/demanda encerrado.",
    "consulta_pendente": "Consulta enviada para aprovação de um advogado.",
    "consulta_ok": "Consulta concluída.",
    "consulta_falha": "A consulta não foi concluída. Veja o motivo abaixo.",
    "consulta_recusada": "Consulta recusada.",
    "diligencia_ok": "Diligência registrada.",
    "andamento_ok": "Andamento registrado.",
    "usuario_ok": "Usuário atualizado.",
    "retencao_ok": "Expurgo por retenção executado.",
}


class Redirecionar(Exception):
    def __init__(self, url: str):
        self.url = url


class Proibido(Exception):
    pass


def ctx_de(request: Request) -> Contexto:
    return request.app.state.ctx


def get_db(request: Request) -> Iterator[Session]:
    db = ctx_de(request).fabrica()
    try:
        yield db
    finally:
        db.close()


def ip_de(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- Sessões ------------------------------------------------------------------------------------

def criar_sessao(db: Session, usuario: Usuario, ip: str | None) -> str:
    token = novo_token()
    db.add(Sessao(token_hash=sha256(token), usuario_id=usuario.id, etapa="senha", csrf=novo_token(), ip=ip))
    return token


def sessao_atual(request: Request, db: Session) -> Sessao | None:
    token = request.cookies.get(COOKIE_SESSAO)
    if not token:
        return None
    sessao = db.execute(select(Sessao).where(Sessao.token_hash == sha256(token))).scalar_one_or_none()
    if sessao is None:
        return None
    cfg = ctx_de(request).cfg
    momento = agora()
    vencida = (
        como_utc(sessao.ultimo_uso) + timedelta(minutes=cfg.sessao_inatividade_min) < momento
        or como_utc(sessao.criada_em) + timedelta(hours=cfg.sessao_maxima_horas) < momento
        or not sessao.usuario.ativo
    )
    if vencida:
        db.delete(sessao)
        db.commit()
        raise Redirecionar("/login?msg=expirou")
    sessao.ultimo_uso = momento
    db.commit()
    return sessao


def encerrar_sessoes(db: Session, usuario_id: int) -> None:
    for s in db.execute(select(Sessao).where(Sessao.usuario_id == usuario_id)).scalars():
        db.delete(s)


def exigir(*perfis: Perfil, liberar_pendencias: bool = False):
    """Dependência: sessão completa + perfil permitido + pendências obrigatórias resolvidas."""

    def dependencia(request: Request, db: Session = Depends(get_db)) -> tuple[Usuario, Sessao, Session]:
        sessao = sessao_atual(request, db)
        if sessao is None:
            raise Redirecionar("/login")
        if sessao.etapa != "completa":
            raise Redirecionar("/login/mfa")
        usuario = sessao.usuario
        if not liberar_pendencias:
            if usuario.trocar_senha:
                raise Redirecionar("/conta/senha")
            if usuario.termo_aceito_em is None:
                raise Redirecionar("/conta/termo")
        if perfis and usuario.perfil not in perfis:
            raise Proibido()
        return usuario, sessao, db

    return dependencia


class Formulario:
    """Acesso simples aos campos de texto do formulário (sempre str, sem espaços nas pontas)."""

    def __init__(self, form):
        self._form = form

    def __getitem__(self, chave: str) -> str:
        valor = self._form.get(chave)
        return valor.strip() if isinstance(valor, str) else ""

    def marcado(self, chave: str) -> bool:
        return self[chave] in {"1", "on", "sim", "true"}

    def inteiro(self, chave: str) -> int | None:
        valor = self[chave]
        return int(valor) if valor.isdigit() else None


async def conferir_csrf(request: Request, esperado: str) -> Formulario:
    form = await request.form()
    recebido = form.get("csrf")
    if not esperado or not isinstance(recebido, str) or not hmac.compare_digest(recebido, esperado):
        raise Proibido()
    return Formulario(form)


def render(request: Request, nome: str, contexto: dict | None = None, status_code: int = 200, sessao: Sessao | None = None):
    ctx = ctx_de(request)
    dados = {
        "cfg": ctx.cfg,
        "nome_sistema": ctx.cfg.nome_sistema,
        "usuario": sessao.usuario if sessao else None,
        "csrf": sessao.csrf if sessao else "",
        "msg": MENSAGENS.get(request.query_params.get("msg", "")),
        "Perfil": Perfil,
        "PERFIL_ROTULO": PERFIL_ROTULO,
        "caminho": request.url.path,
    }
    dados.update(contexto or {})
    return templates.TemplateResponse(request, nome, dados, status_code=status_code)
