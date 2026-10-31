"""Administração de usuários, configurações, retenção e auditoria."""

from __future__ import annotations

import csv
import io
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select

from . import audit
from .models import PERFIL_ROTULO, Perfil, RegistroAuditoria, Usuario, agora
from .security import gerar_senha_temporaria, hash_senha
from .services import consultas as svc
from .validators import ValorInvalido, normalizar_cnpj, normalizar_cpf
from .web import Proibido, conferir_csrf, ctx_de, encerrar_sessoes, exigir, ip_de, render

router = APIRouter()

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.get("/admin/usuarios")
def usuarios(request: Request, dep=Depends(exigir(Perfil.ADMIN))):
    _, sessao, db = dep
    lista = list(db.execute(select(Usuario).order_by(Usuario.ativo.desc(), Usuario.nome)).scalars())
    return render(request, "admin/usuarios.html", {"usuarios": lista, "erro": None, "senha_temp": None, "v": {}},
                  sessao=sessao)


@router.post("/admin/usuarios")
async def usuario_criar(request: Request, dep=Depends(exigir(Perfil.ADMIN))):
    admin, sessao, db = dep
    form = await conferir_csrf(request, sessao.csrf)
    v = {k: form[k] for k in ("nome", "email", "oab", "perfil")}
    v["email"] = v["email"].lower()
    erro = None
    if len(v["nome"]) < 3:
        erro = "Informe o nome completo."
    elif not EMAIL.match(v["email"]):
        erro = "E-mail inválido."
    elif v["perfil"] not in {p.value for p in Perfil}:
        erro = "Selecione o perfil."
    elif db.scalar(select(Usuario.id).where(Usuario.email == v["email"])):
        erro = "Já existe usuário com este e-mail."
    elif v["perfil"] == Perfil.ADVOGADO.value and not v["oab"]:
        erro = "Informe a inscrição na OAB do advogado."
    lista = lambda: list(db.execute(select(Usuario).order_by(Usuario.ativo.desc(), Usuario.nome)).scalars())  # noqa: E731
    if erro:
        return render(request, "admin/usuarios.html", {"usuarios": lista(), "erro": erro, "senha_temp": None, "v": v},
                      status_code=400, sessao=sessao)
    senha = gerar_senha_temporaria()
    novo = Usuario(nome=v["nome"], email=v["email"], oab=v["oab"] or None, perfil=Perfil(v["perfil"]),
                   senha_hash=hash_senha(senha), trocar_senha=True)
    db.add(novo)
    db.flush()
    audit.registrar(db, "usuario_criado", admin, "usuario", novo.id, {"perfil": novo.perfil.value}, ip_de(request))
    db.commit()
    return render(request, "admin/usuarios.html",
                  {"usuarios": lista(), "erro": None, "senha_temp": (novo.email, senha), "v": {}}, sessao=sessao)


@router.post("/admin/usuarios/{uid}/{acao}")
async def usuario_acao(uid: int, acao: str, request: Request, dep=Depends(exigir(Perfil.ADMIN))):
    admin, sessao, db = dep
    form = await conferir_csrf(request, sessao.csrf)
    alvo = db.get(Usuario, uid)
    if alvo is None:
        raise Proibido()
    if alvo.id == admin.id and acao in {"desativar", "perfil"}:
        raise Proibido()  # evita que o administrador se tranque fora do sistema
    ip = ip_de(request)
    senha_temp = None
    if acao == "desativar":
        alvo.ativo = False
        alvo.desativado_em = agora()
        encerrar_sessoes(db, alvo.id)
        audit.registrar(db, "usuario_desativado", admin, "usuario", alvo.id, {}, ip)
    elif acao == "reativar":
        alvo.ativo = True
        alvo.desativado_em = None
        alvo.bloqueado_ate = None
        audit.registrar(db, "usuario_reativado", admin, "usuario", alvo.id, {}, ip)
    elif acao == "redefinir-mfa":
        alvo.mfa_ativo = False
        alvo.mfa_segredo_cifrado = None
        alvo.mfa_ultimo_passo = None
        encerrar_sessoes(db, alvo.id)
        audit.registrar(db, "mfa_redefinido", admin, "usuario", alvo.id, {}, ip)
    elif acao == "redefinir-senha":
        senha_temp = gerar_senha_temporaria()
        alvo.senha_hash = hash_senha(senha_temp)
        alvo.trocar_senha = True
        alvo.tentativas_falhas = 0
        alvo.bloqueado_ate = None
        encerrar_sessoes(db, alvo.id)
        audit.registrar(db, "senha_redefinida", admin, "usuario", alvo.id, {}, ip)
    elif acao == "perfil":
        novo = form["perfil"]
        if novo not in {p.value for p in Perfil}:
            raise Proibido()
        anterior = alvo.perfil.value
        alvo.perfil = Perfil(novo)
        encerrar_sessoes(db, alvo.id)
        audit.registrar(db, "usuario_alterado", admin, "usuario", alvo.id, {"perfil_de": anterior, "perfil_para": novo}, ip)
    else:
        raise Proibido()
    db.commit()
    if senha_temp:
        lista = list(db.execute(select(Usuario).order_by(Usuario.ativo.desc(), Usuario.nome)).scalars())
        return render(request, "admin/usuarios.html",
                      {"usuarios": lista, "erro": None, "senha_temp": (alvo.email, senha_temp), "v": {}}, sessao=sessao)
    return RedirectResponse("/admin/usuarios?msg=usuario_ok", status_code=303)


@router.get("/admin/configuracoes")
def configuracoes(request: Request, dep=Depends(exigir(Perfil.ADMIN))):
    _, sessao, _ = dep
    ctx = ctx_de(request)
    return render(request, "admin/configuracoes.html", {"fontes": ctx.registro.situacao(), "c": ctx.cfg}, sessao=sessao)


@router.post("/admin/retencao")
async def retencao(request: Request, dep=Depends(exigir(Perfil.ADMIN))):
    admin, sessao, db = dep
    await conferir_csrf(request, sessao.csrf)
    svc.expurgar_vencidas(db, admin, ip_de(request))
    return RedirectResponse("/admin/configuracoes?msg=retencao_ok", status_code=303)


# --- Auditoria ----------------------------------------------------------------------------------

def _filtrar(request: Request, db):
    ctx = ctx_de(request)
    q = request.query_params
    filtro = []
    if q.get("acao") in audit.ACOES:
        filtro.append(RegistroAuditoria.acao == q["acao"])
    if q.get("usuario", "").isdigit():
        filtro.append(RegistroAuditoria.usuario_id == int(q["usuario"]))
    erro = None
    if q.get("documento"):
        bruto = "".join(ch for ch in q["documento"] if ch.isalnum())
        try:
            doc = normalizar_cpf(bruto) if len(bruto) == 11 else normalizar_cnpj(bruto)
            alvo = ctx.cofre.hash_documento(doc)
            filtro.append(RegistroAuditoria.detalhes["documento_hash"].as_string() == alvo)
        except ValorInvalido as exc:
            erro = str(exc)
    return filtro, erro


@router.get("/auditoria")
def auditoria(request: Request, dep=Depends(exigir(Perfil.ADMIN, Perfil.AUDITOR))):
    _, sessao, db = dep
    filtro, erro = _filtrar(request, db)
    registros = list(db.execute(select(RegistroAuditoria).where(*filtro).order_by(RegistroAuditoria.id.desc())
                                .limit(300)).scalars())
    integra, falha_id, total = audit.verificar_cadeia(db)
    usuarios = list(db.execute(select(Usuario).order_by(Usuario.nome)).scalars())
    return render(request, "auditoria/lista.html", {
        "registros": registros, "ACOES": audit.ACOES, "cadeia": {"integra": integra, "falha_id": falha_id, "total": total},
        "usuarios": usuarios, "q": request.query_params, "q_str": str(request.query_params), "erro": erro,
    }, sessao=sessao)


@router.get("/auditoria/exportar.csv")
def auditoria_csv(request: Request, dep=Depends(exigir(Perfil.ADMIN, Perfil.AUDITOR))):
    usuario, _, db = dep
    filtro, _ = _filtrar(request, db)
    reg_export = audit.registrar(db, "auditoria_exportada", usuario, None, None,
                                 {"filtros": {k: v for k, v in request.query_params.items() if k != "documento"}},
                                 ip_de(request))
    db.commit()
    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";")
    w.writerow(["id", "momento_utc", "usuario_id", "usuario_email", "acao", "objeto_tipo", "objeto_id", "detalhes",
                "ip", "hash_anterior", "hash"])
    for r in db.execute(select(RegistroAuditoria).where(*filtro).order_by(RegistroAuditoria.id)).scalars():
        w.writerow([r.id, r.momento.isoformat(), r.usuario_id, r.usuario_email, r.acao, r.objeto_tipo, r.objeto_id,
                    r.detalhes, r.ip, r.hash_anterior, r.hash])
    return Response("﻿" + saida.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="auditoria-{reg_export.id}.csv"'})


__all__ = ["router", "PERFIL_ROTULO"]
