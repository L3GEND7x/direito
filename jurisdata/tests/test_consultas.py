from datetime import timedelta

from sqlalchemy import select

from app.models import Consulta, RegistroAuditoria, StatusConsulta
from app.services.consultas import expurgar_vencidas

from .conftest import com, csrf_pagina, entrar

CPF = "529.982.247-25"


def _dados(pid, **kw):
    base = {
        "opcao": "cpf|simulado", "documento": CPF, "nascimento": "10/05/1980", "processo_id": str(pid),
        "finalidade_tipo": "pesquisa_patrimonial", "base_legal": "art7_vi", "declaracao": "1",
        "justificativa": "Localizar bens do executado após tentativa frustrada de penhora.",
    }
    base.update(kw)
    return base


def _acoes(ctx):
    with ctx.fabrica() as s:
        return [r.acao for r in s.execute(select(RegistroAuditoria).order_by(RegistroAuditoria.id)).scalars()]


def test_advogado_consulta_cpf_e_exporta_pdf(app, ctx, equipe):
    adv, segredo = equipe["adv"]
    c = entrar(app, adv.email, segredo)
    token = csrf_pagina(c, "/consultas/nova")
    r = c.post("/consultas/nova", data={"csrf": token, **_dados(equipe["processo_id"])})
    assert r.status_code == 303 and "msg=consulta_ok" in r.headers["location"]
    pagina = c.get(r.headers["location"])
    assert "PESSOA FICTÍCIA DE TESTE" in pagina.text
    assert "DADOS FICTÍCIOS" in pagina.text
    assert "52998224725" not in pagina.text and "529.982.247-25" not in pagina.text
    with ctx.fabrica() as s:
        consulta = s.execute(select(Consulta)).scalar_one()
        assert consulta.status == StatusConsulta.CONCLUIDA
        assert "52998224725" not in (consulta.documento_cifrado or "")
        assert "FICTÍCIA" not in consulta.resultado_cifrado  # resultado gravado criptografado
        cid = consulta.id
    pdf = c.get(f"/consultas/{cid}/relatorio.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    integral = c.get(f"/consultas/{cid}/relatorio.pdf?integral=1")
    assert integral.status_code == 200
    acoes = _acoes(ctx)
    for esperado in ("consulta_solicitada", "consulta_executada", "consulta_visualizada", "relatorio_exportado",
                     "relatorio_integral_exportado"):
        assert esperado in acoes
    with ctx.fabrica() as s:
        detalhes = [str(r.detalhes) for r in s.execute(select(RegistroAuditoria)).scalars()]
    assert not any("52998224725" in d or "529.982.247-25" in d for d in detalhes)


def test_validacoes_da_consulta(app, ctx, equipe):
    adv, segredo = equipe["adv"]
    c = entrar(app, adv.email, segredo)
    token = csrf_pagina(c, "/consultas/nova")
    pid = equipe["processo_id"]
    casos = [
        (_dados(pid, documento="111.111.111-11"), "CPF inválido"),
        (_dados(pid, nascimento=""), "Data de nascimento"),
        (_dados(pid, processo_id=""), "Vincule a consulta"),
        (_dados(pid, justificativa="curta"), "justificativa"),
        (_dados(pid, declaracao=""), "declaração"),
        (_dados(pid, base_legal="inventada"), "base legal"),
        (_dados(pid, opcao="cpf|serpro"), "indisponível"),
    ]
    for dados, trecho in casos:
        r = c.post("/consultas/nova", data={"csrf": token, **dados})
        assert r.status_code == 400 and trecho.lower() in r.text.lower(), trecho
    with ctx.fabrica() as s:
        assert s.execute(select(Consulta)).first() is None


def test_assistente_depende_de_aprovacao(app, ctx, equipe):
    ass, s_ass = equipe["ass"]
    adv, s_adv = equipe["adv"]
    ca = entrar(app, ass.email, s_ass)
    r = ca.post("/consultas/nova", data={"csrf": csrf_pagina(ca, "/consultas/nova"), **_dados(equipe["processo_id"])})
    assert "msg=consulta_pendente" in r.headers["location"]
    cid = int(r.headers["location"].split("/")[2].split("?")[0])
    assert "PESSOA FICTÍCIA" not in ca.get(f"/consultas/{cid}").text
    # Assistente não aprova.
    assert ca.post(f"/consultas/{cid}/aprovar", data={"csrf": csrf_pagina(ca)}).status_code == 403
    cv = entrar(app, adv.email, s_adv)
    assert "Aprovar e executar" in cv.get(f"/consultas/{cid}").text
    r = cv.post(f"/consultas/{cid}/aprovar", data={"csrf": csrf_pagina(cv)})
    assert "msg=consulta_ok" in r.headers["location"]
    with ctx.fabrica() as s:
        consulta = s.get(Consulta, cid)
        assert consulta.status == StatusConsulta.CONCLUIDA and consulta.aprovador_id == adv.id
    # Agora a assistente vê o resultado da própria consulta.
    assert "PESSOA FICTÍCIA" in ca.get(f"/consultas/{cid}").text


def test_recusa_apaga_documento(app, ctx, equipe):
    ass, s_ass = equipe["ass"]
    adv, s_adv = equipe["adv"]
    ca = entrar(app, ass.email, s_ass)
    r = ca.post("/consultas/nova", data={"csrf": csrf_pagina(ca, "/consultas/nova"), **_dados(equipe["processo_id"])})
    cid = int(r.headers["location"].split("/")[2].split("?")[0])
    cv = entrar(app, adv.email, s_adv)
    token = csrf_pagina(cv)
    assert cv.post(f"/consultas/{cid}/recusar", data={"csrf": token, "motivo": "x"}).status_code == 403
    r = cv.post(f"/consultas/{cid}/recusar", data={"csrf": token, "motivo": "Finalidade não demonstrada."})
    assert r.status_code == 303
    with ctx.fabrica() as s:
        consulta = s.get(Consulta, cid)
        assert consulta.status == StatusConsulta.RECUSADA and consulta.documento_cifrado is None


def test_auditor_ve_metadados_mas_nao_conteudo(app, equipe):
    adv, s_adv = equipe["adv"]
    aud, s_aud = equipe["aud"]
    cv = entrar(app, adv.email, s_adv)
    r = cv.post("/consultas/nova", data={"csrf": csrf_pagina(cv, "/consultas/nova"), **_dados(equipe["processo_id"])})
    cid = int(r.headers["location"].split("/")[2].split("?")[0])
    cu = entrar(app, aud.email, s_aud)
    pagina = cu.get(f"/consultas/{cid}")
    assert pagina.status_code == 200
    assert "***.982.247-**" in pagina.text and "PESSOA FICTÍCIA" not in pagina.text
    assert cu.get(f"/consultas/{cid}/relatorio.pdf").status_code == 403


def test_assistente_nao_ve_consulta_de_outro(app, equipe):
    adv, s_adv = equipe["adv"]
    ass, s_ass = equipe["ass"]
    cv = entrar(app, adv.email, s_adv)
    r = cv.post("/consultas/nova", data={"csrf": csrf_pagina(cv, "/consultas/nova"), **_dados(equipe["processo_id"])})
    cid = int(r.headers["location"].split("/")[2].split("?")[0])
    ca = entrar(app, ass.email, s_ass)
    assert ca.get(f"/consultas/{cid}").status_code == 403
    assert ca.get(f"/consultas/{cid}/relatorio.pdf").status_code == 403


def test_falha_da_fonte_nao_exibe_dados(app, ctx, equipe):
    adv, segredo = equipe["adv"]
    c = entrar(app, adv.email, segredo)
    r = c.post("/consultas/nova", data={"csrf": csrf_pagina(c, "/consultas/nova"),
                                        **_dados(equipe["processo_id"], nascimento="02/02/1902")})
    assert "msg=consulta_falha" in r.headers["location"]
    pagina = c.get(r.headers["location"])
    assert "não foi concluída" in pagina.text and "PESSOA FICTÍCIA" not in pagina.text
    cid = int(r.headers["location"].split("/")[2].split("?")[0])
    assert c.get(f"/consultas/{cid}/relatorio.pdf").status_code == 403
    assert "consulta_falhou" in _acoes(ctx)


def test_limite_diario(app, ctx, equipe):
    app.state.ctx.cfg = com(ctx.cfg, limite_diario_consultas=2)
    adv, segredo = equipe["adv"]
    c = entrar(app, adv.email, segredo)
    token = csrf_pagina(c, "/consultas/nova")
    for _ in range(2):
        assert c.post("/consultas/nova", data={"csrf": token, **_dados(equipe["processo_id"])}).status_code == 303
    r = c.post("/consultas/nova", data={"csrf": token, **_dados(equipe["processo_id"])})
    assert r.status_code == 400 and "Limite" in r.text
    assert "consulta_bloqueada" in _acoes(ctx)


def test_processo_encerrado_bloqueia_consulta(app, ctx, equipe):
    adv, segredo = equipe["adv"]
    c = entrar(app, adv.email, segredo)
    pid = equipe["processo_id"]
    assert c.post(f"/processos/{pid}/encerrar", data={"csrf": csrf_pagina(c)}).status_code == 303
    r = c.post("/consultas/nova", data={"csrf": csrf_pagina(c), **_dados(pid)})
    assert r.status_code == 400 and "encerrado" in r.text


def test_retencao_expurga_dados(app, ctx, equipe):
    adv, segredo = equipe["adv"]
    c = entrar(app, adv.email, segredo)
    r = c.post("/consultas/nova", data={"csrf": csrf_pagina(c, "/consultas/nova"), **_dados(equipe["processo_id"])})
    cid = int(r.headers["location"].split("/")[2].split("?")[0])
    with ctx.fabrica() as s:
        consulta = s.get(Consulta, cid)
        consulta.expurgar_em = consulta.solicitada_em - timedelta(days=1)
        s.commit()
        assert expurgar_vencidas(s) == 1
        consulta = s.get(Consulta, cid)
        assert consulta.status == StatusConsulta.EXPURGADA
        assert consulta.resultado_cifrado is None and consulta.documento_cifrado is None
        assert consulta.documento_mascarado == "***.982.247-**"
        assert expurgar_vencidas(s) == 0  # idempotente


def test_cadastro_de_cliente_processo_e_diligencia(app, ctx, equipe):
    adv, segredo = equipe["adv"]
    c = entrar(app, adv.email, segredo)
    r = c.post("/clientes/novo", data={"csrf": csrf_pagina(c, "/clientes/novo"), "nome": "Maria Cliente", "tipo": "PF",
                                       "documento": CPF, "contato": "", "observacoes": ""})
    assert r.status_code == 303
    lista = c.get("/clientes").text
    assert "***.982.247-**" in lista and CPF not in lista
    numero = "0001234-{:02d}.2024.8.26.0100".format(98 - int("0001234" + "2024" + "8" + "26" + "0100" + "00") % 97)
    token = csrf_pagina(c, "/processos/novo")
    from app.models import Cliente
    with ctx.fabrica() as s:
        cli_id = s.execute(select(Cliente.id).where(Cliente.nome == "Maria Cliente")).scalar_one()
    dados = {"csrf": token, "numero_cnj": numero, "identificacao_demanda": "", "cliente_id": str(cli_id),
             "parte_contraria": "Devedor", "orgao": "1ª Vara", "classe": "Cumprimento de sentença", "area": "execucao",
             "polo_cliente": "Autor/Exequente", "responsavel_id": str(adv.id)}
    r = c.post("/processos/novo", data=dados)
    assert r.status_code == 303
    pid = int(r.headers["location"].split("/")[2].split("?")[0])
    assert c.post("/processos/novo", data=dados).status_code == 400  # número duplicado
    assert c.post("/processos/novo", data={**dados, "numero_cnj": "0001234-00.2024.8.26.0100"}).status_code == 400
    r = c.post("/diligencias/nova", data={
        "csrf": csrf_pagina(c, "/diligencias/nova"), "processo_id": str(pid), "sistema": "sisbajud",
        "pesquisado_nome": "Devedor", "pesquisado_doc": "", "objetivo": "Pesquisa de ativos financeiros do executado.",
        "status": "requerida", "data_pedido": "01/10/2026", "data_decisao": "", "referencia_decisao": "", "prazo": "",
    })
    assert r.status_code == 303
    did = int(r.headers["location"].split("/")[2].split("?")[0])
    r = c.post(f"/diligencias/{did}/andamento", data={
        "csrf": csrf_pagina(c), "status": "deferida", "descricao": "Pedido deferido pelo juízo.",
        "data_decisao": "15/10/2026", "referencia_decisao": "Evento 42", "prazo": "30/10/2026", "resultado": "",
    })
    assert r.status_code == 303
    pagina = c.get(f"/diligencias/{did}").text
    assert "Pedido deferido pelo juízo." in pagina and "Evento 42" in pagina


def test_auditoria_busca_por_documento_e_csv(app, ctx, equipe):
    adv, s_adv = equipe["adv"]
    aud, s_aud = equipe["aud"]
    cv = entrar(app, adv.email, s_adv)
    cv.post("/consultas/nova", data={"csrf": csrf_pagina(cv, "/consultas/nova"), **_dados(equipe["processo_id"])})
    cu = entrar(app, aud.email, s_aud)
    r = cu.get("/auditoria", params={"documento": CPF})
    assert r.status_code == 200 and "Consulta solicitada" in r.text and "Cadeia íntegra" in r.text
    csv = cu.get("/auditoria/exportar.csv")
    assert csv.status_code == 200 and "consulta_solicitada" in csv.text
    assert "52998224725" not in csv.text
