"""Painel, clientes, processos, consultas e diligências patrimoniais."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit, lgpd
from .connectors.base import TIPOS_CONSULTA, tipo_e_cpf
from .models import (
    AndamentoDiligencia,
    Cliente,
    Consulta,
    Diligencia,
    Perfil,
    Processo,
    StatusConsulta,
    Usuario,
    agora,
)
from .security import mascarar_documento
from .services import consultas as svc
from .services.relatorios import data_hora, gerar_pdf
from .validators import ValorInvalido, ler_data_opcional, normalizar_cnj, normalizar_cnpj, normalizar_cpf
from .web import Proibido, conferir_csrf, ctx_de, exigir, ip_de, render

router = APIRouter()

ADV, ASS, AUD, ADM = Perfil.ADVOGADO, Perfil.ASSISTENTE, Perfil.AUDITOR, Perfil.ADMIN

AREAS = {
    "criminal": "Criminal",
    "execucao": "Execução / cumprimento de sentença",
    "civel": "Cível",
    "consumidor": "Consumidor",
    "trabalhista": "Trabalhista",
    "familia": "Família e sucessões",
    "tributario": "Tributário",
    "outra": "Outra",
}

SISTEMAS = {
    "sisbajud": "SISBAJUD — ativos financeiros",
    "renajud": "RENAJUD — veículos",
    "infojud": "INFOJUD — informações fiscais",
    "sniper": "SNIPER — investigação patrimonial integrada",
    "cnib": "CNIB — indisponibilidade de bens",
    "registro_imoveis": "Registro de imóveis (ofício/ONR)",
    "junta_comercial": "Junta Comercial",
    "outro": "Outra diligência",
}

STATUS_DILIGENCIA = {
    "a_requerer": "A requerer",
    "requerida": "Requerida ao juízo",
    "deferida": "Deferida",
    "indeferida": "Indeferida",
    "em_cumprimento": "Em cumprimento",
    "resultado_juntado": "Resultado juntado aos autos",
    "sem_resultado": "Sem resultado útil",
    "encerrada": "Encerrada",
}

CHECKLIST_PEDIDO = [
    "Decisão ou fase processual que autoriza a medida (título executivo, cumprimento de sentença, medida assecuratória etc.)",
    "Qualificação do pesquisado (nome e CPF/CNPJ conferidos)",
    "Demonstração das tentativas anteriores e do resultado (quando exigido pelo juízo)",
    "Indicação do sistema e do alcance pretendido (valor, período, tipo de bem)",
    "Fundamento legal conferido na redação vigente [NECESSÁRIO CONFERIR]",
    "Prazo para manifestação sobre o resultado",
]


def _processos_ativos(db: Session) -> list[Processo]:
    return list(db.execute(select(Processo).where(Processo.ativo.is_(True)).order_by(Processo.id.desc())).scalars())


# --- Painel -------------------------------------------------------------------------------------

@router.get("/")
def painel(request: Request, dep=Depends(exigir())):
    usuario, sessao, db = dep
    ctx = ctx_de(request)
    dados: dict = {}
    if usuario.perfil in (ADV, ASS):
        dados["consultas_24h"] = svc.consultas_nas_ultimas_24h(db, usuario)
        dados["limite"] = ctx.cfg.limite_diario_consultas
        filtro = [] if usuario.perfil == ADV else [Consulta.solicitante_id == usuario.id]
        dados["recentes"] = list(db.execute(
            select(Consulta).where(*filtro).order_by(Consulta.id.desc()).limit(8)).scalars())
        dados["pendentes"] = db.scalar(select(func.count(Consulta.id)).where(Consulta.status == StatusConsulta.PENDENTE, *filtro))
        limite = date.today() + timedelta(days=7)
        dados["prazos"] = list(db.execute(
            select(Diligencia).where(Diligencia.prazo.is_not(None), Diligencia.prazo <= limite,
                                     Diligencia.status.not_in(["encerrada", "resultado_juntado", "sem_resultado"]))
            .order_by(Diligencia.prazo)).scalars())
        dados["processos_ativos"] = db.scalar(select(func.count(Processo.id)).where(Processo.ativo.is_(True)))
    if usuario.perfil in (ADM, AUD):
        integra, falha_id, total = audit.verificar_cadeia(db)
        dados["cadeia"] = {"integra": integra, "falha_id": falha_id, "total": total}
        dados["usuarios_ativos"] = db.scalar(select(func.count(Usuario.id)).where(Usuario.ativo.is_(True)))
    return render(request, "painel.html", dados, sessao=sessao)


# --- Clientes -----------------------------------------------------------------------------------

@router.get("/clientes")
def clientes(request: Request, dep=Depends(exigir(ADV, ASS))):
    _, sessao, db = dep
    lista = list(db.execute(select(Cliente).order_by(Cliente.nome)).scalars())
    return render(request, "clientes/lista.html", {"clientes": lista}, sessao=sessao)


@router.get("/clientes/novo")
def cliente_form(request: Request, dep=Depends(exigir(ADV, ASS))):
    _, sessao, _ = dep
    return render(request, "clientes/novo.html", {"erro": None, "v": {}}, sessao=sessao)


@router.post("/clientes/novo")
async def cliente_criar(request: Request, dep=Depends(exigir(ADV, ASS))):
    usuario, sessao, db = dep
    ctx = ctx_de(request)
    form = await conferir_csrf(request, sessao.csrf)
    v = {k: form[k] for k in ("nome", "tipo", "documento", "contato", "observacoes")}
    try:
        if len(v["nome"]) < 3:
            raise ValorInvalido("Informe o nome do cliente.")
        if v["tipo"] not in ("PF", "PJ"):
            raise ValorInvalido("Selecione pessoa física ou jurídica.")
        doc = None
        if v["documento"]:
            doc = normalizar_cpf(v["documento"]) if v["tipo"] == "PF" else normalizar_cnpj(v["documento"])
    except ValorInvalido as exc:
        return render(request, "clientes/novo.html", {"erro": str(exc), "v": v}, status_code=400, sessao=sessao)
    cliente = Cliente(
        nome=v["nome"], tipo=v["tipo"],
        documento_cifrado=ctx.cofre.cifrar(doc), documento_mascarado=mascarar_documento(doc) if doc else None,
        documento_hash=ctx.cofre.hash_documento(doc) if doc else None,
        contato_cifrado=ctx.cofre.cifrar(v["contato"]) if v["contato"] else None,
        observacoes=v["observacoes"] or None, criado_por_id=usuario.id,
    )
    db.add(cliente)
    db.flush()
    audit.registrar(db, "cliente_criado", usuario, "cliente", cliente.id, {}, ip_de(request))
    db.commit()
    return RedirectResponse("/clientes?msg=cliente_ok", status_code=303)


# --- Processos ----------------------------------------------------------------------------------

@router.get("/processos")
def processos(request: Request, dep=Depends(exigir(ADV, ASS))):
    _, sessao, db = dep
    lista = list(db.execute(select(Processo).order_by(Processo.ativo.desc(), Processo.id.desc())).scalars())
    return render(request, "processos/lista.html", {"processos": lista, "AREAS": AREAS}, sessao=sessao)


def _form_processo_ctx(db: Session) -> dict:
    return {
        "clientes": list(db.execute(select(Cliente).order_by(Cliente.nome)).scalars()),
        "advogados": list(db.execute(select(Usuario).where(Usuario.perfil == ADV, Usuario.ativo.is_(True))
                                     .order_by(Usuario.nome)).scalars()),
        "AREAS": AREAS,
    }


@router.get("/processos/novo")
def processo_form(request: Request, dep=Depends(exigir(ADV))):
    usuario, sessao, db = dep
    return render(request, "processos/novo.html", {"erro": None, "v": {"responsavel_id": str(usuario.id)},
                                                   **_form_processo_ctx(db)}, sessao=sessao)


@router.post("/processos/novo")
async def processo_criar(request: Request, dep=Depends(exigir(ADV))):
    usuario, sessao, db = dep
    form = await conferir_csrf(request, sessao.csrf)
    campos = ("numero_cnj", "identificacao_demanda", "cliente_id", "parte_contraria", "orgao", "classe", "area",
              "polo_cliente", "responsavel_id")
    v = {k: form[k] for k in campos}
    try:
        numero = normalizar_cnj(v["numero_cnj"]) if v["numero_cnj"] else None
        if not numero and len(v["identificacao_demanda"]) < 10:
            raise ValorInvalido("Informe o número CNJ ou descreva a demanda pré-processual (mínimo 10 caracteres).")
        if numero and db.scalar(select(Processo.id).where(Processo.numero_cnj == numero)):
            raise ValorInvalido("Este número de processo já está cadastrado.")
        cliente = db.get(Cliente, form.inteiro("cliente_id") or 0)
        if cliente is None:
            raise ValorInvalido("Selecione o cliente.")
        responsavel = db.get(Usuario, form.inteiro("responsavel_id") or 0)
        if responsavel is None or responsavel.perfil != ADV or not responsavel.ativo:
            raise ValorInvalido("Selecione o advogado responsável.")
        if v["area"] not in AREAS:
            raise ValorInvalido("Selecione a área.")
    except ValorInvalido as exc:
        return render(request, "processos/novo.html", {"erro": str(exc), "v": v, **_form_processo_ctx(db)},
                      status_code=400, sessao=sessao)
    processo = Processo(
        numero_cnj=numero, identificacao_demanda=v["identificacao_demanda"] or None, cliente_id=cliente.id,
        parte_contraria=v["parte_contraria"] or None, orgao=v["orgao"] or None, classe=v["classe"] or None,
        area=v["area"], polo_cliente=v["polo_cliente"] or None, responsavel_id=responsavel.id,
    )
    db.add(processo)
    db.flush()
    audit.registrar(db, "processo_criado", usuario, "processo", processo.id, {"numero_cnj": numero}, ip_de(request))
    db.commit()
    return RedirectResponse(f"/processos/{processo.id}?msg=processo_ok", status_code=303)


@router.get("/processos/{pid}")
def processo_detalhe(pid: int, request: Request, dep=Depends(exigir(ADV, ASS))):
    usuario, sessao, db = dep
    processo = db.get(Processo, pid)
    if processo is None:
        raise Proibido()
    filtro = [] if usuario.perfil == ADV else [Consulta.solicitante_id == usuario.id]
    lista_consultas = list(db.execute(select(Consulta).where(Consulta.processo_id == pid, *filtro)
                                      .order_by(Consulta.id.desc())).scalars())
    diligencias = list(db.execute(select(Diligencia).where(Diligencia.processo_id == pid)
                                  .order_by(Diligencia.id.desc())).scalars())
    return render(request, "processos/detalhe.html", {
        "p": processo, "consultas": lista_consultas, "diligencias": diligencias, "AREAS": AREAS,
        "SISTEMAS": SISTEMAS, "STATUS_DILIGENCIA": STATUS_DILIGENCIA, "TIPOS": TIPOS_CONSULTA,
    }, sessao=sessao)


@router.post("/processos/{pid}/encerrar")
async def processo_encerrar(pid: int, request: Request, dep=Depends(exigir(ADV))):
    usuario, sessao, db = dep
    await conferir_csrf(request, sessao.csrf)
    processo = db.get(Processo, pid)
    if processo is None:
        raise Proibido()
    processo.ativo = False
    processo.encerrado_em = agora()
    audit.registrar(db, "processo_encerrado", usuario, "processo", pid, {}, ip_de(request))
    db.commit()
    return RedirectResponse(f"/processos/{pid}?msg=processo_encerrado", status_code=303)


# --- Consultas ----------------------------------------------------------------------------------

@router.get("/consultas")
def consultas_lista(request: Request, dep=Depends(exigir(ADV, ASS, AUD))):
    usuario, sessao, db = dep
    filtro = [Consulta.solicitante_id == usuario.id] if usuario.perfil == ASS else []
    status = request.query_params.get("status")
    if status in {s.value for s in StatusConsulta}:
        filtro.append(Consulta.status == StatusConsulta(status))
    lista = list(db.execute(select(Consulta).where(*filtro).order_by(Consulta.id.desc()).limit(200)).scalars())
    return render(request, "consultas/lista.html", {"consultas": lista, "TIPOS": TIPOS_CONSULTA,
                                                    "status_filtro": status, "StatusConsulta": StatusConsulta},
                  sessao=sessao)


def _form_consulta_ctx(request: Request, db: Session, usuario: Usuario) -> dict:
    ctx = ctx_de(request)
    return {
        "opcoes": ctx.registro.opcoes(),
        "processos": _processos_ativos(db),
        "BASES": lgpd.BASES_LEGAIS,
        "FINALIDADES": lgpd.FINALIDADES,
        "DECLARACAO": lgpd.DECLARACAO,
        "JUST_MIN": lgpd.JUSTIFICATIVA_MIN,
        "exige_aprovacao": usuario.perfil == ASS and ctx.cfg.assistente_exige_aprovacao,
        "usadas": svc.consultas_nas_ultimas_24h(db, usuario),
    }


@router.get("/consultas/nova")
def consulta_form(request: Request, dep=Depends(exigir(ADV, ASS))):
    usuario, sessao, db = dep
    v = {"base_legal": lgpd.BASE_LEGAL_PADRAO, "processo_id": request.query_params.get("processo", "")}
    return render(request, "consultas/nova.html", {"erro": None, "v": v, **_form_consulta_ctx(request, db, usuario)},
                  sessao=sessao)


@router.post("/consultas/nova")
async def consulta_criar(request: Request, dep=Depends(exigir(ADV, ASS))):
    usuario, sessao, db = dep
    form = await conferir_csrf(request, sessao.csrf)
    opcao = form["opcao"]
    tipo, _, fonte = opcao.partition("|")
    v = {k: form[k] for k in ("opcao", "nascimento", "processo_id", "finalidade_tipo", "justificativa", "base_legal")}
    try:
        consulta = svc.solicitar(
            db, ctx_de(request), usuario, tipo=tipo, fonte=fonte, documento=form["documento"],
            nascimento=form["nascimento"] if tipo_e_cpf(tipo) else None, processo_id=form.inteiro("processo_id"),
            finalidade_tipo=form["finalidade_tipo"], justificativa=form["justificativa"],
            base_legal=form["base_legal"], declaracao=form.marcado("declaracao"), ip=ip_de(request),
        )
    except svc.ErroRegra as exc:
        db.rollback()
        # O documento não é devolvido ao formulário (não fica em cache do navegador).
        return render(request, "consultas/nova.html", {"erro": str(exc), "v": v,
                                                       **_form_consulta_ctx(request, db, usuario)},
                      status_code=400, sessao=sessao)
    msg = {StatusConsulta.PENDENTE: "consulta_pendente", StatusConsulta.CONCLUIDA: "consulta_ok"}.get(
        consulta.status, "consulta_falha")
    return RedirectResponse(f"/consultas/{consulta.id}?msg={msg}", status_code=303)


def _carregar_consulta(db: Session, cid: int, usuario: Usuario) -> Consulta:
    consulta = db.get(Consulta, cid)
    if consulta is None or not svc.pode_ver_metadados(usuario, consulta):
        raise Proibido()
    return consulta


@router.get("/consultas/{cid}")
def consulta_detalhe(cid: int, request: Request, dep=Depends(exigir(ADV, ASS, AUD))):
    usuario, sessao, db = dep
    ctx = ctx_de(request)
    consulta = _carregar_consulta(db, cid, usuario)
    resultado = None
    if svc.pode_ver_resultado(usuario, consulta):
        resultado = svc.abrir_resultado(db, ctx, consulta, usuario, ip_de(request))
        if resultado is not None:
            audit.registrar(db, "consulta_visualizada", usuario, "consulta", cid, {}, ip_de(request))
            db.commit()
    return render(request, "consultas/detalhe.html", {
        "c": consulta, "resultado": resultado, "linhas": svc.achatar(resultado["dados"]) if resultado else [],
        "TIPOS": TIPOS_CONSULTA, "BASES": lgpd.BASES_LEGAIS, "data_hora": data_hora,
        "pode_aprovar": usuario.perfil == ADV and consulta.status == StatusConsulta.PENDENTE
        and consulta.solicitante_id != usuario.id,
    }, sessao=sessao)


@router.post("/consultas/{cid}/aprovar")
async def consulta_aprovar(cid: int, request: Request, dep=Depends(exigir(ADV))):
    usuario, sessao, db = dep
    await conferir_csrf(request, sessao.csrf)
    consulta = _carregar_consulta(db, cid, usuario)
    try:
        svc.aprovar(db, ctx_de(request), consulta, usuario, ip_de(request))
    except svc.ErroRegra:
        db.rollback()
        raise Proibido()
    msg = "consulta_ok" if consulta.status == StatusConsulta.CONCLUIDA else "consulta_falha"
    return RedirectResponse(f"/consultas/{cid}?msg={msg}", status_code=303)


@router.post("/consultas/{cid}/recusar")
async def consulta_recusar(cid: int, request: Request, dep=Depends(exigir(ADV))):
    usuario, sessao, db = dep
    form = await conferir_csrf(request, sessao.csrf)
    consulta = _carregar_consulta(db, cid, usuario)
    try:
        svc.recusar(db, consulta, usuario, form["motivo"], ip_de(request))
    except svc.ErroRegra:
        db.rollback()
        raise Proibido()
    return RedirectResponse(f"/consultas/{cid}?msg=consulta_recusada", status_code=303)


@router.get("/consultas/{cid}/relatorio.pdf")
def consulta_pdf(cid: int, request: Request, dep=Depends(exigir(ADV, ASS))):
    usuario, sessao, db = dep
    ctx = ctx_de(request)
    consulta = _carregar_consulta(db, cid, usuario)
    integral = request.query_params.get("integral") == "1"
    try:
        resultado = svc.abrir_resultado(db, ctx, consulta, usuario, ip_de(request), integral=integral)
    except svc.ErroRegra:
        raise Proibido()
    if resultado is None:
        raise Proibido()
    acao = "relatorio_integral_exportado" if integral else "relatorio_exportado"
    reg = audit.registrar(db, acao, usuario, "consulta", cid, {"documento_hash": consulta.documento_hash}, ip_de(request))
    db.commit()
    pdf = gerar_pdf(consulta, resultado, svc.documento_exibicao(ctx, consulta, integral), usuario, agora(), reg.id,
                    ctx.cfg.nome_sistema, integral)
    nome = f"jurisdata-consulta-{cid}{'-integral' if integral else ''}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{nome}"'})


# --- Diligências patrimoniais -------------------------------------------------------------------

@router.get("/diligencias")
def diligencias(request: Request, dep=Depends(exigir(ADV, ASS))):
    _, sessao, db = dep
    lista = list(db.execute(select(Diligencia).order_by(Diligencia.atualizado_em.desc())).scalars())
    return render(request, "diligencias/lista.html", {"diligencias": lista, "SISTEMAS": SISTEMAS,
                                                      "STATUS": STATUS_DILIGENCIA}, sessao=sessao)


def _form_dil_ctx(db: Session) -> dict:
    return {"processos": _processos_ativos(db), "SISTEMAS": SISTEMAS, "STATUS": STATUS_DILIGENCIA,
            "CHECKLIST": CHECKLIST_PEDIDO}


@router.get("/diligencias/nova")
def diligencia_form(request: Request, dep=Depends(exigir(ADV, ASS))):
    _, sessao, db = dep
    v = {"processo_id": request.query_params.get("processo", ""), "status": "a_requerer"}
    return render(request, "diligencias/nova.html", {"erro": None, "v": v, **_form_dil_ctx(db)}, sessao=sessao)


@router.post("/diligencias/nova")
async def diligencia_criar(request: Request, dep=Depends(exigir(ADV, ASS))):
    usuario, sessao, db = dep
    ctx = ctx_de(request)
    form = await conferir_csrf(request, sessao.csrf)
    campos = ("processo_id", "sistema", "pesquisado_nome", "pesquisado_doc", "objetivo", "status", "data_pedido",
              "data_decisao", "referencia_decisao", "prazo")
    v = {k: form[k] for k in campos}
    try:
        processo = db.get(Processo, form.inteiro("processo_id") or 0)
        if processo is None or not processo.ativo:
            raise ValorInvalido("Selecione um processo ativo.")
        if v["sistema"] not in SISTEMAS or v["status"] not in STATUS_DILIGENCIA:
            raise ValorInvalido("Selecione o sistema e a situação.")
        if len(v["pesquisado_nome"]) < 3 or len(v["objetivo"]) < 10:
            raise ValorInvalido("Informe o pesquisado e o objetivo da diligência.")
        doc = None
        if v["pesquisado_doc"]:
            bruto = "".join(ch for ch in v["pesquisado_doc"] if ch.isalnum())
            doc = normalizar_cpf(bruto) if len(bruto) == 11 else normalizar_cnpj(bruto)
        datas = {k: ler_data_opcional(v[k], k.replace("_", " ").capitalize()) for k in ("data_pedido", "data_decisao", "prazo")}
    except ValorInvalido as exc:
        return render(request, "diligencias/nova.html", {"erro": str(exc), "v": v, **_form_dil_ctx(db)},
                      status_code=400, sessao=sessao)
    dil = Diligencia(
        processo_id=processo.id, sistema=v["sistema"], pesquisado_nome=v["pesquisado_nome"],
        pesquisado_doc_cifrado=ctx.cofre.cifrar(doc), pesquisado_doc_mascarado=mascarar_documento(doc) if doc else None,
        objetivo=v["objetivo"], status=v["status"], referencia_decisao=v["referencia_decisao"] or None,
        criado_por_id=usuario.id, **datas,
    )
    db.add(dil)
    db.flush()
    db.add(AndamentoDiligencia(diligencia_id=dil.id, status=dil.status, descricao="Diligência registrada.",
                               usuario_id=usuario.id))
    audit.registrar(db, "diligencia_criada", usuario, "diligencia", dil.id,
                    {"processo_id": processo.id, "sistema": dil.sistema}, ip_de(request))
    db.commit()
    return RedirectResponse(f"/diligencias/{dil.id}?msg=diligencia_ok", status_code=303)


@router.get("/diligencias/{did}")
def diligencia_detalhe(did: int, request: Request, dep=Depends(exigir(ADV, ASS))):
    _, sessao, db = dep
    dil = db.get(Diligencia, did)
    if dil is None:
        raise Proibido()
    return render(request, "diligencias/detalhe.html", {"d": dil, "SISTEMAS": SISTEMAS, "STATUS": STATUS_DILIGENCIA,
                                                        "erro": None, "data_hora": data_hora}, sessao=sessao)


@router.post("/diligencias/{did}/andamento")
async def diligencia_andamento(did: int, request: Request, dep=Depends(exigir(ADV, ASS))):
    usuario, sessao, db = dep
    form = await conferir_csrf(request, sessao.csrf)
    dil = db.get(Diligencia, did)
    if dil is None:
        raise Proibido()
    try:
        if form["status"] not in STATUS_DILIGENCIA:
            raise ValorInvalido("Selecione a situação.")
        if len(form["descricao"]) < 5:
            raise ValorInvalido("Descreva o andamento.")
        data_decisao = ler_data_opcional(form["data_decisao"], "Data da decisão")
        prazo = ler_data_opcional(form["prazo"], "Prazo")
    except ValorInvalido as exc:
        return render(request, "diligencias/detalhe.html", {"d": dil, "SISTEMAS": SISTEMAS, "STATUS": STATUS_DILIGENCIA,
                                                            "erro": str(exc), "data_hora": data_hora},
                      status_code=400, sessao=sessao)
    dil.status = form["status"]
    if data_decisao:
        dil.data_decisao = data_decisao
    if form["referencia_decisao"]:
        dil.referencia_decisao = form["referencia_decisao"]
    if form["resultado"]:
        dil.resultado = form["resultado"]
    dil.prazo = prazo
    dil.atualizado_em = agora()
    db.add(AndamentoDiligencia(diligencia_id=did, status=dil.status, descricao=form["descricao"], usuario_id=usuario.id))
    audit.registrar(db, "diligencia_andamento", usuario, "diligencia", did, {"status": dil.status}, ip_de(request))
    db.commit()
    return RedirectResponse(f"/diligencias/{did}?msg=andamento_ok", status_code=303)
