"""Tela “Personal IA” do Foco Leve: conversa com o Foco Leve AI — Personal Trainer.

Tudo é da conta autenticada: conversas, mensagens e fotos ficam no armazém por usuário (foco_leve/ia_storage.py), o
contexto sai do estado dessa conta e o estado temporário da tela vive em st.session_state com prefixo “ia_” (apagado
ao sair da conta). Nada pessoal fica em cache compartilhado.
"""
from __future__ import annotations

import html
import logging

import streamlit as st

from foco_leve import ia_context as C
from foco_leve import ia_safety as SEG
from foco_leve import ia_service as SV
from foco_leve import ia_storage as ST
from foco_leve import ia_vision as V
from foco_leve import plano as P
from foco_leve.armazenamento import ErroArmazenamento

log = logging.getLogger("foco_leve.ia")

SUGESTOES = ["Monte meu treino de hoje.", "Analise minha evolução esta semana.", "Como posso melhorar minha execução?",
             "Adapte meu treino às limitações que informei.", "Tenho pouco tempo hoje. Como posso treinar?",
             "Explique meus resultados e proponha os próximos passos."]
AVISO_LESAO = ("> **Aviso do Foco Leve:** você descreveu um possível sinal de lesão. Interrompa o que causa dor e "
               "procure avaliação de um profissional de saúde antes de retomar os exercícios dessa região.\n\n")
AVATAR = {"user": None, "assistant": None}  # avatares padrão: o tema.css diferencia pessoa e IA por eles


def configuracao() -> SV.ConfigIA | None:
    """Lida a cada execução (sem cache): uma chave salva em Secrets vale na próxima recarga."""
    try:
        sec = dict(st.secrets["ia"]) if st.secrets.load_if_toml_exists() and "ia" in st.secrets else {}
    except Exception:  # noqa: BLE001 - Secrets malformado: o aviso de configuração aparece na tela
        sec = {}
    return SV.ler_config(sec)


def _cabecalho(cfg, uso) -> None:
    if not cfg:
        status, cor = "Não configurado", "var(--text-3)"
    elif uso and uso["mensagens"] >= cfg.limite_mensagens_dia:
        status, cor = "Limite de hoje atingido", "var(--warning)"
    else:
        status, cor = "Online", "var(--success)"
    st.markdown(
        "<div class='fl-ia-cab'><div class='fl-ia-avatar' aria-hidden='true'>AI</div><div>"
        "<div class='marca'>Foco Leve AI</div><h1>Personal Trainer</h1>"
        f"<div class='fl-ia-status'><span style='background:{cor}'></span>{html.escape(status)}</div>"
        "</div></div>", unsafe_allow_html=True)


def _foto_da_mensagem(arm, u, aid):
    cache = st.session_state.setdefault("ia_fotos", {})  # só nesta sessão do navegador; some ao sair da conta
    if aid not in cache:
        cache[aid] = arm.anexo(u, aid)
    return cache[aid]


def _cartao_proposta(arm, u, m, S, salvar, hoje) -> None:
    prop, estado = m["proposta"], m.get("proposta_estado") or "pendente"
    with st.container(border=True):
        st.markdown(f"**Proposta para revisar:** {html.escape(prop.get('resumo', ''))}")
        st.markdown("\n".join(f"- {html.escape(x.lstrip('• '))}" for x in SEG.descrever(prop)))
        if estado == "aplicada":
            st.success("Aplicada ao seu plano.")
            return
        if estado == "descartada":
            st.caption("Descartada. Nada foi alterado.")
            return
        st.caption("Nada muda no seu plano até você confirmar.")
        c1, c2 = st.columns(2)
        if c1.button("Aplicar ao meu plano", key=f"ia_apl_{m['id']}", type="primary", use_container_width=True):
            try:
                semana = P.semana_do_programa(S)["semana"]
                avisos = SEG.aplicar_proposta(prop, S, semana, hoje)
            except ValueError as e:
                st.error(f"Não foi possível aplicar: {e}")
                return
            salvar()
            arm.marcar_proposta(u, m["id"], "aplicada")
            st.session_state.aviso = ("ok", "Plano atualizado", "A proposta do Personal IA foi aplicada."
                                      + (" " + " ".join(avisos) if avisos else ""))
            st.rerun()
        if c2.button("Descartar", key=f"ia_desc_{m['id']}", use_container_width=True):
            arm.marcar_proposta(u, m["id"], "descartada")
            st.rerun()


def _historico(arm, u) -> None:
    conversas = arm.conversas(u)
    atual = st.session_state.get("ia_conversa")
    c1, c2 = st.columns([3, 2])
    opcoes = [None] + [c["id"] for c in conversas]
    titulos = {c["id"]: c["titulo"] for c in conversas}
    sel = c1.selectbox("Conversa", opcoes, index=opcoes.index(atual) if atual in opcoes else 0,
                       format_func=lambda i: "Nova conversa" if i is None else titulos.get(i, "Conversa"),
                       key="ia_sel_" + str(atual), label_visibility="collapsed")
    if sel != atual:
        st.session_state.ia_conversa = sel
        st.rerun()
    if c2.button("Nova conversa", icon=":material/add_comment:", use_container_width=True, disabled=atual is None):
        st.session_state.ia_conversa = None
        st.rerun()
    if not conversas:
        return
    with st.expander(f":material/history: Minhas conversas ({len(conversas)})"):
        apagar = st.session_state.get("ia_excluir")
        for c in conversas:
            a, b = st.columns([4, 1])
            a.markdown(f"**{html.escape(c['titulo'])}**  \n<small>{html.escape(str(c['atualizada'])[:10])}</small>",
                       unsafe_allow_html=True)
            if b.button("Excluir", key=f"ia_x_{c['id']}", use_container_width=True):
                st.session_state.ia_excluir = c["id"]
                st.rerun()
            if apagar == c["id"]:
                st.warning("Excluir esta conversa, as mensagens e as fotos dela? Não dá para desfazer.")
                s1, s2 = st.columns(2)
                if s1.button("Excluir definitivamente", key="ia_x_ok", type="primary", use_container_width=True):
                    arm.excluir_conversa(u, c["id"])
                    st.session_state.pop("ia_excluir", None)
                    if st.session_state.get("ia_conversa") == c["id"]:
                        st.session_state.ia_conversa = None
                    st.rerun()
                if s2.button("Cancelar", key="ia_x_nao", use_container_width=True):
                    st.session_state.pop("ia_excluir", None)
                    st.rerun()


def _boas_vindas(S, hoje) -> str:
    falta = C.perfil_incompleto(S)
    pl = P.plano_do_dia(S, hoje)
    hoje_txt = "hoje é dia de descanso na sua agenda" if pl["wk"] == "OFF" else f"hoje o seu plano tem **{pl['nome']}**"
    txt = (f"Olá! Sou o seu Personal IA. Conheço o seu plano do Foco Leve — {hoje_txt}. Posso montar ou adaptar o "
           "treino, analisar sua evolução, comentar fotos de exercícios e explicar o porquê de cada ajuste.")
    if falta:
        txt += "\n\nPara personalizar melhor, ainda faltam: " + "; ".join(falta) + ". Podemos completar aos poucos."
    return txt + "\n\n_Não substituo avaliação médica nem o acompanhamento presencial de um profissional._"


def _gerar(arm, u, cfg, S, conv, msgs, hoje, alerta) -> None:
    """Pede a resposta da IA para a última mensagem da pessoa e grava o resultado."""
    servico = SV.ServicoIA(cfg)
    ultima = msgs[-1]
    anteriores = msgs[:-1][-cfg.janela_mensagens:]
    fotos = [b for b in (_foto_da_mensagem(arm, u, a) for a in ultima.get("anexos", [])) if b]
    contexto = C.montar(S, ultima["texto"], hoje)
    seg = SEG.instrucao_de_seguranca(alerta, S)
    with st.chat_message("assistant", avatar=AVATAR["assistant"]):
        if alerta.nivel == "lesao":
            st.markdown(AVISO_LESAO)
        with st.spinner("Analisando seus dados…"):
            st.write_stream(servico.responder(anteriores, conv.get("resumo") or "", contexto, ultima["texto"], fotos, seg))
    r = servico.ultimo
    semana = P.semana_do_programa(S)["semana"]
    proposta, avisos = None, []
    for bruta in r.propostas:
        proposta, avisos = SEG.validar_proposta(bruta, S, semana)
        if proposta:
            break
    texto = (AVISO_LESAO if alerta.nivel == "lesao" else "") + r.texto
    if r.truncado:
        texto += "\n\n_A resposta foi interrompida por ser longa demais. Peça a continuação, se precisar._"
    if avisos:
        texto += "\n\n_Observação do app: " + " ".join(avisos) + "_"
    arm.adicionar_mensagem(u, conv["id"], "assistant", texto, proposta=proposta, tokens=(r.tokens_entrada, r.tokens_saida))
    # resumo: quando 6 mensagens novas saem da janela, elas entram no resumo (as últimas seguem em texto integral)
    total = len(msgs) + 1
    fim = total - cfg.janela_mensagens
    if fim - int(conv.get("resumo_ate") or 0) >= 6:
        try:
            todas = arm.mensagens(u, conv["id"])
            novo = servico.resumir(conv.get("resumo") or "", todas[int(conv.get("resumo_ate") or 0):fim])
            arm.salvar_resumo(u, conv["id"], novo, fim)
        except (SV.IAIndisponivel, SV.ErroIA, ErroArmazenamento) as e:
            log.warning("Resumo não atualizado: %s", e)


def _enviar(arm, u, cfg, S, texto, arquivos, hoje) -> None:
    """Valida, grava a mensagem da pessoa e pede a resposta. Erros aparecem na tela, sem resposta inventada."""
    try:
        texto = SEG.validar_texto(texto, tem_foto=bool(arquivos))
    except SEG.MensagemInvalida as e:
        st.session_state.ia_erro = str(e)
        return
    if len(arquivos) > cfg.max_fotos_por_mensagem:
        st.session_state.ia_erro = f"Envie no máximo {cfg.max_fotos_por_mensagem} foto(s) por mensagem."
        return
    uso = arm.uso_24h(u)
    if uso["mensagens"] >= cfg.limite_mensagens_dia:
        st.session_state.ia_erro = (f"Você chegou ao limite de {cfg.limite_mensagens_dia} mensagens nas últimas 24 horas. "
                                    "O limite controla o custo do serviço; tente de novo mais tarde.")
        return
    if arquivos and uso["fotos"] + len(arquivos) > cfg.limite_fotos_dia:
        st.session_state.ia_erro = f"Limite de {cfg.limite_fotos_dia} fotos nas últimas 24 horas atingido."
        return
    fotos = []
    for f in arquivos:
        try:
            fotos.append(V.preparar(f.getvalue(), int(cfg.max_foto_mb * 1024 * 1024)))
        except V.ImagemInvalida as e:
            st.session_state.ia_erro = f"{f.name}: {e}"
            return
    alerta = SEG.classificar(texto)
    cid = st.session_state.get("ia_conversa")
    if not cid or not arm.conversa(u, cid):
        cid = arm.criar_conversa(u, texto or "Análise de foto")["id"]
        st.session_state.ia_conversa = cid
    mid = arm.adicionar_mensagem(u, cid, "user", texto)
    for f in fotos:
        aid = arm.adicionar_anexo(u, mid, f)
        st.session_state.setdefault("ia_fotos", {})[aid] = f["bytes"]
    if alerta.nivel == "urgente":  # resposta fixa do app: não depende da IA nem espera por ela
        arm.adicionar_mensagem(u, cid, "assistant", SEG.RESPOSTA_URGENTE)
        return
    st.session_state.ia_responder = alerta.nivel or ""


def _ao_enviar(arm, u, cfg, S, hoje, sugestao: str | None = None) -> None:
    """Callback do botão Enviar (ou de uma sugestão): roda antes da próxima execução da tela."""
    texto = sugestao if sugestao is not None else st.session_state.get("ia_texto", "")
    arquivos = [] if sugestao is not None else list(st.session_state.get("ia_fotos_up") or [])
    try:
        _enviar(arm, u, cfg, S, texto, arquivos, hoje)
    except (ErroArmazenamento, ST.AcessoNegado) as e:
        st.session_state.ia_erro = f"A mensagem não pôde ser salva: {e}"


def tela(S: dict, usuario: dict, loja, salvar, hoje: str) -> None:
    arm = ST.para(loja)
    cfg = configuracao()
    u = usuario
    try:
        uso = arm.uso_24h(u) if cfg else None
    except (ErroArmazenamento, ST.AcessoNegado):
        uso = None
    _cabecalho(cfg, uso)
    if not cfg:
        st.info("**O Personal IA ainda não está configurado.** Quem administra o app precisa informar a chave da API "
                "da Anthropic em Settings → Secrets (seção [ia], veja o README). Suas conversas anteriores continuam "
                "disponíveis abaixo, mas não é possível enviar mensagens agora.")
    try:
        _historico(arm, u)
        cid = st.session_state.get("ia_conversa")
        conv = arm.conversa(u, cid) if cid else None
        if cid and not conv:  # excluída em outra aba
            st.session_state.ia_conversa = conv = None
        msgs = arm.mensagens(u, conv["id"]) if conv else []
    except (ErroArmazenamento, ST.AcessoNegado) as e:
        st.error(f"Não foi possível carregar suas conversas: {e}")
        return

    if not msgs:
        with st.chat_message("assistant", avatar=AVATAR["assistant"]):
            st.markdown(_boas_vindas(S, hoje))
    for m in msgs:
        with st.chat_message(m["papel"], avatar=AVATAR[m["papel"]]):
            for aid in m.get("anexos", []):
                b = _foto_da_mensagem(arm, u, aid)
                if b:
                    st.image(b, width=240)
            st.markdown(m["texto"])
        if m["papel"] == "assistant" and m.get("proposta"):
            _cartao_proposta(arm, u, m, S, salvar, hoje)

    # resposta pendente (mensagem recém-gravada) ou nova tentativa depois de uma falha
    pendente = st.session_state.pop("ia_responder", None)
    if cfg and conv and msgs and msgs[-1]["papel"] == "user" and pendente is not None:
        try:
            _gerar(arm, u, cfg, S, conv, msgs, hoje, SEG.classificar(msgs[-1]["texto"]))
        except (SV.IAIndisponivel, SV.ErroIA) as e:
            st.session_state.ia_erro = str(e)
        except (ErroArmazenamento, ST.AcessoNegado) as e:
            st.session_state.ia_erro = f"A resposta não pôde ser salva: {e}"
        st.rerun()

    if st.session_state.get("ia_erro"):
        st.error(st.session_state.pop("ia_erro"))
    if cfg and msgs and msgs[-1]["papel"] == "user":
        st.caption("A última mensagem ainda não tem resposta.")
        if st.button("Tentar responder de novo", icon=":material/refresh:", key="ia_retry"):
            st.session_state.ia_responder = ""
            st.rerun()

    bloqueado = not cfg or (uso is not None and uso["mensagens"] >= cfg.limite_mensagens_dia)
    if not msgs and cfg:
        st.caption("Sugestões")
        cols = st.columns(2)
        for i, sug in enumerate(SUGESTOES):
            cols[i % 2].button(sug, key=f"ia_sug_{i}", use_container_width=True, disabled=bloqueado,
                               on_click=_ao_enviar, args=(arm, u, cfg, S, hoje, sug))

    with st.form("ia_form", clear_on_submit=True):
        st.text_area("Mensagem para o Personal IA", key="ia_texto", height=90, disabled=bloqueado,
                     placeholder="Ex.: Hoje estou cansado e só tenho 40 minutos.", label_visibility="collapsed")
        max_fotos = cfg.max_fotos_por_mensagem if cfg else 0
        st.file_uploader(f"Anexar fotos (JPEG, PNG ou WebP, até {max_fotos} por mensagem)",
                         type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True,
                         key="ia_fotos_up", disabled=bloqueado or not max_fotos)
        st.form_submit_button("Enviar", type="primary", use_container_width=True, disabled=bloqueado,
                              icon=":material/send:", on_click=_ao_enviar if cfg else None,
                              args=(arm, u, cfg, S, hoje) if cfg else None)
    if cfg and uso is not None:
        st.caption(f"{uso['mensagens']} de {cfg.limite_mensagens_dia} mensagens nas últimas 24 h. As respostas são "
                   "geradas por IA e podem conter erros: confira com um profissional antes de mudanças importantes.")
