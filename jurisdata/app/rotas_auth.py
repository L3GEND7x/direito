"""Login, MFA, troca de senha, termo de responsabilidade e saída."""

from __future__ import annotations

import hmac
from datetime import timedelta

import segno
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .models import Sessao, Usuario, agora, como_utc
from .security import (
    HASH_FICTICIO,
    conferir_senha,
    conferir_totp,
    hash_senha,
    novo_segredo_mfa,
    novo_token,
    politica_senha,
    sha256,
    uri_mfa,
)
from .web import (
    COOKIE_PRE,
    COOKIE_SESSAO,
    Formulario,
    Proibido,
    Redirecionar,
    conferir_csrf,
    criar_sessao,
    ctx_de,
    exigir,
    get_db,
    ip_de,
    render,
    sessao_atual,
)

router = APIRouter()

FALHA_LOGIN = "E-mail ou senha inválidos, ou conta temporariamente bloqueada."

TERMO = [
    "Uso as consultas exclusivamente para a finalidade declarada e vinculada a processo ou demanda do escritório.",
    "Não compartilho meu login, senha ou dispositivo de autenticação com ninguém.",
    "Não copio, exporto ou repasso dados pessoais além do estritamente necessário à atuação profissional.",
    "Sei que todas as consultas, visualizações e exportações ficam registradas em trilha de auditoria.",
    "Comunico imediatamente ao administrador qualquer suspeita de acesso indevido ou incidente de segurança.",
    "O descumprimento destas regras pode gerar responsabilização disciplinar, civil e penal.",
]


def _definir_cookie(resposta, nome: str, valor: str, request: Request) -> None:
    cfg = ctx_de(request).cfg
    resposta.set_cookie(nome, valor, httponly=True, secure=cfg.cookie_secure, samesite="strict", path="/")


def _registrar_falha(db: Session, request: Request, usuario: Usuario, acao: str) -> None:
    cfg = ctx_de(request).cfg
    usuario.tentativas_falhas += 1
    if usuario.tentativas_falhas >= cfg.tentativas_login_max:
        usuario.bloqueado_ate = agora() + timedelta(minutes=cfg.bloqueio_login_min)
        usuario.tentativas_falhas = 0
        audit.registrar(db, "login_bloqueado", usuario, "usuario", usuario.id, {"minutos": cfg.bloqueio_login_min}, ip_de(request))
    audit.registrar(db, acao, usuario, "usuario", usuario.id, {}, ip_de(request))
    db.commit()


def _bloqueado(usuario: Usuario) -> bool:
    return usuario.bloqueado_ate is not None and como_utc(usuario.bloqueado_ate) > agora()


@router.get("/login")
def login_form(request: Request):
    pre = novo_token()
    resposta = render(request, "login.html", {"pre": pre, "erro": None})
    _definir_cookie(resposta, COOKIE_PRE, pre, request)
    return resposta


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    form = await conferir_csrf(request, request.cookies.get(COOKIE_PRE, ""))
    email = form["email"].lower()
    usuario = db.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()

    def falha():
        pre = novo_token()
        resposta = render(request, "login.html", {"pre": pre, "erro": FALHA_LOGIN, "email": email}, status_code=401)
        _definir_cookie(resposta, COOKIE_PRE, pre, request)
        return resposta

    if usuario is None:
        conferir_senha(HASH_FICTICIO, form["senha"])
        audit.registrar(db, "login_falha", None, None, None, {"motivo": "email_desconhecido"}, ip_de(request), email=email[:254])
        db.commit()
        return falha()
    if not usuario.ativo or _bloqueado(usuario):
        conferir_senha(HASH_FICTICIO, form["senha"])
        audit.registrar(db, "login_falha", usuario, "usuario", usuario.id,
                        {"motivo": "inativo" if not usuario.ativo else "bloqueado"}, ip_de(request))
        db.commit()
        return falha()
    if not conferir_senha(usuario.senha_hash, form["senha"]):
        _registrar_falha(db, request, usuario, "login_falha")
        return falha()

    token = criar_sessao(db, usuario, ip_de(request))
    db.commit()
    resposta = RedirectResponse("/login/mfa", status_code=303)
    _definir_cookie(resposta, COOKIE_SESSAO, token, request)
    resposta.delete_cookie(COOKIE_PRE, path="/")
    return resposta


def _sessao_pendente(request: Request, db: Session) -> Sessao:
    sessao = sessao_atual(request, db)
    if sessao is None:
        raise Redirecionar("/login")
    if sessao.etapa == "completa":
        raise Redirecionar("/")
    return sessao


def _qr_svg(uri: str) -> str:
    return segno.make(uri, error="m").svg_data_uri(scale=5, dark="#000000", light="#ffffff", border=2)


@router.get("/login/mfa")
def mfa_form(request: Request, db: Session = Depends(get_db)):
    sessao = _sessao_pendente(request, db)
    return _tela_mfa(request, db, sessao, None)


def _tela_mfa(request: Request, db: Session, sessao: Sessao, erro: str | None, status_code: int = 200):
    ctx = ctx_de(request)
    usuario = sessao.usuario
    contexto: dict = {"erro": erro, "cadastro": not usuario.mfa_ativo, "tela_acesso": True}
    if not usuario.mfa_ativo:
        if not usuario.mfa_segredo_cifrado:
            usuario.mfa_segredo_cifrado = ctx.cofre.cifrar(novo_segredo_mfa())
            db.commit()
        segredo = ctx.cofre.decifrar(usuario.mfa_segredo_cifrado)
        contexto["qr"] = _qr_svg(uri_mfa(segredo, usuario.email, ctx.cfg.nome_sistema))
        contexto["segredo"] = " ".join(segredo[i:i + 4] for i in range(0, len(segredo), 4))
    return render(request, "mfa.html", contexto, status_code=status_code, sessao=sessao)


@router.post("/login/mfa")
async def mfa(request: Request, db: Session = Depends(get_db)):
    ctx = ctx_de(request)
    sessao = _sessao_pendente(request, db)
    form = await conferir_csrf(request, sessao.csrf)
    usuario = sessao.usuario
    if _bloqueado(usuario):
        db.delete(sessao)
        db.commit()
        raise Redirecionar("/login")
    segredo = ctx.cofre.decifrar(usuario.mfa_segredo_cifrado) if usuario.mfa_segredo_cifrado else None
    passo = conferir_totp(segredo, form["codigo"], usuario.mfa_ultimo_passo) if segredo else None
    if passo is None:
        _registrar_falha(db, request, usuario, "mfa_falha")
        if _bloqueado(usuario):
            db.delete(sessao)
            db.commit()
            raise Redirecionar("/login")
        return _tela_mfa(request, db, sessao, "Código inválido ou já utilizado.", status_code=401)

    usuario.mfa_ultimo_passo = passo
    usuario.tentativas_falhas = 0
    if not usuario.mfa_ativo:
        usuario.mfa_ativo = True
        audit.registrar(db, "mfa_ativado", usuario, "usuario", usuario.id, {}, ip_de(request))
    # Nova sessão após autenticação completa (evita fixação de sessão).
    db.delete(sessao)
    token = novo_token()
    db.add(Sessao(token_hash=sha256(token), usuario_id=usuario.id, etapa="completa", csrf=novo_token(), ip=ip_de(request)))
    audit.registrar(db, "login_ok", usuario, "usuario", usuario.id, {}, ip_de(request))
    db.commit()
    resposta = RedirectResponse("/", status_code=303)
    _definir_cookie(resposta, COOKIE_SESSAO, token, request)
    return resposta


@router.post("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    try:
        sessao = sessao_atual(request, db)
    except Redirecionar:
        sessao = None
    if sessao is not None:
        await conferir_csrf(request, sessao.csrf)
        audit.registrar(db, "logout", sessao.usuario, "usuario", sessao.usuario_id, {}, ip_de(request))
        db.delete(sessao)
        db.commit()
    resposta = RedirectResponse("/login?msg=saiu", status_code=303)
    resposta.delete_cookie(COOKIE_SESSAO, path="/")
    return resposta


@router.get("/conta/senha")
def senha_form(request: Request, dep=Depends(exigir(liberar_pendencias=True))):
    usuario, sessao, _ = dep
    return render(request, "conta/senha.html", {"erros": [], "obrigatoria": usuario.trocar_senha}, sessao=sessao)


@router.post("/conta/senha")
async def senha(request: Request, dep=Depends(exigir(liberar_pendencias=True))):
    usuario, sessao, db = dep
    form: Formulario = await conferir_csrf(request, sessao.csrf)
    erros = []
    if not conferir_senha(usuario.senha_hash, form["atual"]):
        erros.append("A senha atual não confere.")
    nova = form["nova"]
    if nova != form["confirmacao"]:
        erros.append("A confirmação não corresponde à nova senha.")
    problemas = politica_senha(nova)
    if problemas:
        erros.append("A nova senha deve " + ", ".join(problemas) + ".")
    if nova and hmac.compare_digest(nova, form["atual"]):
        erros.append("A nova senha deve ser diferente da atual.")
    if erros:
        return render(request, "conta/senha.html", {"erros": erros, "obrigatoria": usuario.trocar_senha},
                      status_code=400, sessao=sessao)
    usuario.senha_hash = hash_senha(nova)
    usuario.trocar_senha = False
    # Encerra as demais sessões do usuário.
    for s in db.execute(select(Sessao).where(Sessao.usuario_id == usuario.id, Sessao.id != sessao.id)).scalars():
        db.delete(s)
    audit.registrar(db, "senha_alterada", usuario, "usuario", usuario.id, {}, ip_de(request))
    db.commit()
    return RedirectResponse("/?msg=senha_ok", status_code=303)


@router.get("/conta/termo")
def termo_form(request: Request, dep=Depends(exigir(liberar_pendencias=True))):
    usuario, sessao, _ = dep
    if usuario.trocar_senha:
        raise Redirecionar("/conta/senha")
    return render(request, "conta/termo.html", {"termo": TERMO, "erro": None}, sessao=sessao)


@router.post("/conta/termo")
async def termo(request: Request, dep=Depends(exigir(liberar_pendencias=True))):
    usuario, sessao, db = dep
    form = await conferir_csrf(request, sessao.csrf)
    if not form.marcado("aceito"):
        return render(request, "conta/termo.html", {"termo": TERMO, "erro": "Marque a confirmação para continuar."},
                      status_code=400, sessao=sessao)
    usuario.termo_aceito_em = agora()
    audit.registrar(db, "termo_aceito", usuario, "usuario", usuario.id, {"versao": 1}, ip_de(request))
    db.commit()
    return RedirectResponse("/", status_code=303)


__all__ = ["router", "Proibido"]
