import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Perfil, RegistroAuditoria, Sessao, Usuario

from .conftest import SENHA, criar_usuario, csrf_de, csrf_pagina, entrar


def test_paginas_exigem_login(app):
    c = TestClient(app, follow_redirects=False)
    for url in ("/", "/consultas", "/consultas/nova", "/auditoria", "/admin/usuarios"):
        r = c.get(url)
        assert r.status_code == 303 and r.headers["location"] == "/login"


def test_cabecalhos_de_seguranca(app):
    r = TestClient(app).get("/login")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_primeiro_acesso_completo(app, ctx):
    u, _ = criar_usuario(ctx, Perfil.ADVOGADO, "novo@escritorio.test", pronto=False)
    c = TestClient(app, follow_redirects=False)
    r = c.post("/login", data={"csrf": csrf_de(c.get("/login").text), "email": "NOVO@escritorio.test", "senha": SENHA})
    assert r.headers["location"] == "/login/mfa"
    # Sem MFA concluído, nada além da tela de MFA.
    assert c.get("/").headers["location"] == "/login/mfa"
    r = c.get("/login/mfa")
    assert "Ative a verificação em dois fatores" in r.text and "data:image/svg+xml" in r.text
    with ctx.fabrica() as s:
        segredo = ctx.cofre.decifrar(s.get(Usuario, u.id).mfa_segredo_cifrado)
    r = c.post("/login/mfa", data={"csrf": csrf_de(r.text), "codigo": "000000"})
    assert r.status_code == 401
    r = c.post("/login/mfa", data={"csrf": csrf_de(r.text), "codigo": pyotp.TOTP(segredo).now()})
    assert r.headers["location"] == "/"
    # Troca de senha obrigatória e depois termo.
    assert c.get("/").headers["location"] == "/conta/senha"
    token = csrf_pagina(c, "/conta/senha")
    r = c.post("/conta/senha", data={"csrf": token, "atual": SENHA, "nova": "fraca", "confirmacao": "fraca"})
    assert r.status_code == 400
    nova = "Outra-Senha-Forte-456?"
    r = c.post("/conta/senha", data={"csrf": token, "atual": SENHA, "nova": nova, "confirmacao": nova})
    assert r.status_code == 303
    assert c.get("/").headers["location"] == "/conta/termo"
    token = csrf_pagina(c, "/conta/termo")
    assert c.post("/conta/termo", data={"csrf": token}).status_code == 400
    assert c.post("/conta/termo", data={"csrf": token, "aceito": "1"}).status_code == 303
    assert c.get("/").status_code == 200
    with ctx.fabrica() as s:
        acoes = [r.acao for r in s.execute(select(RegistroAuditoria)).scalars()]
    assert {"mfa_falha", "mfa_ativado", "login_ok", "senha_alterada", "termo_aceito"} <= set(acoes)


def test_bloqueio_apos_tentativas(app, ctx):
    criar_usuario(ctx, Perfil.ADVOGADO, "alvo@escritorio.test")
    c = TestClient(app, follow_redirects=False)
    for _ in range(ctx.cfg.tentativas_login_max):
        r = c.post("/login", data={"csrf": csrf_de(c.get("/login").text), "email": "alvo@escritorio.test", "senha": "errada"})
        assert r.status_code == 401
    # Mesmo com a senha certa, permanece bloqueado.
    r = c.post("/login", data={"csrf": csrf_de(c.get("/login").text), "email": "alvo@escritorio.test", "senha": SENHA})
    assert r.status_code == 401
    with ctx.fabrica() as s:
        assert s.scalar(select(Usuario.bloqueado_ate).where(Usuario.email == "alvo@escritorio.test")) is not None


def test_mensagem_de_falha_nao_revela_email(app):
    c = TestClient(app, follow_redirects=False)
    r = c.post("/login", data={"csrf": csrf_de(c.get("/login").text), "email": "nao@existe.test", "senha": "x"})
    assert r.status_code == 401 and "E-mail ou senha inválidos" in r.text


def test_csrf_obrigatorio(app, equipe):
    adv, segredo = equipe["adv"]
    c = entrar(app, adv.email, segredo)
    r = c.post("/clientes/novo", data={"nome": "Sem token", "tipo": "PF"})
    assert r.status_code == 403
    r = c.post("/clientes/novo", data={"csrf": "falso", "nome": "Token falso", "tipo": "PF"})
    assert r.status_code == 403


def test_login_csrf_obrigatorio(app):
    c = TestClient(app, follow_redirects=False)
    c.get("/login")
    assert c.post("/login", data={"csrf": "outro", "email": "a@b.c", "senha": "x"}).status_code == 403


def test_permissoes_por_perfil(app, equipe):
    adm, s_adm = equipe["adm"]
    aud, s_aud = equipe["aud"]
    ca = entrar(app, adm.email, s_adm)
    assert ca.get("/consultas/nova").status_code == 403  # administrador não consulta
    assert ca.get("/admin/usuarios").status_code == 200
    cu = entrar(app, aud.email, s_aud)
    assert cu.get("/auditoria").status_code == 200
    assert cu.get("/admin/usuarios").status_code == 403
    assert cu.get("/consultas/nova").status_code == 403
    assert cu.get("/processos").status_code == 403


def test_desativacao_revoga_sessao(app, ctx, equipe):
    adm, s_adm = equipe["adm"]
    ass, s_ass = equipe["ass"]
    c_ass = entrar(app, ass.email, s_ass)
    assert c_ass.get("/").status_code == 200
    c_adm = entrar(app, adm.email, s_adm)
    token = csrf_pagina(c_adm, "/admin/usuarios")
    assert c_adm.post(f"/admin/usuarios/{ass.id}/desativar", data={"csrf": token}).status_code == 303
    assert c_ass.get("/").headers["location"] == "/login"
    with ctx.fabrica() as s:
        assert s.scalar(select(Sessao.id).where(Sessao.usuario_id == ass.id)) is None


def test_admin_cria_usuario_com_senha_temporaria(app, ctx, equipe):
    adm, s_adm = equipe["adm"]
    c = entrar(app, adm.email, s_adm)
    token = csrf_pagina(c, "/admin/usuarios")
    r = c.post("/admin/usuarios", data={"csrf": token, "nome": "Fabio Advogado", "email": "fabio@escritorio.test",
                                         "perfil": "advogado", "oab": ""})
    assert r.status_code == 400 and "OAB" in r.text
    r = c.post("/admin/usuarios", data={"csrf": token, "nome": "Fabio Advogado", "email": "fabio@escritorio.test",
                                         "perfil": "advogado", "oab": "AM 1234"})
    assert r.status_code == 200 and "Senha temporária" in r.text
    with ctx.fabrica() as s:
        u = s.execute(select(Usuario).where(Usuario.email == "fabio@escritorio.test")).scalar_one()
        assert u.trocar_senha and not u.mfa_ativo
