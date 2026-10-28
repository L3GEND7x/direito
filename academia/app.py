"""FOCO LEVE — Treino e Emagrecimento (versão Python / Streamlit).

Executar:  streamlit run app.py
No celular: streamlit run app.py --server.address 0.0.0.0  e abra http://IP-DO-COMPUTADOR:8501
"""
from __future__ import annotations

import html
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from foco_leve import armazenamento as A
from foco_leve import dados as D
from foco_leve import regras as R
from foco_leve.regras import br, brx, fmt_d, fmt_dy, num, ok

st.set_page_config(page_title="Foco Leve", page_icon="💪", layout="centered")

PASTA_FOTOS = A.CAMINHO_PADRAO.parent / "fotos"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Teko:wght@500;600;700&display=swap');
:root{--vermelho:#ef233c;--vermelho-claro:#ff5266;--vermelho-escuro:#b5122a;--preto:#09090b;--painel:#151519;--cinza:#a1a1aa;--borda:#303036;
--grad:linear-gradient(100deg,#ff5266 0%,#ef233c 45%,#b5122a 100%);--titulo:'Teko','Poppins',sans-serif}
.stApp{background:radial-gradient(ellipse at 50% -10%,rgba(239,35,60,.16),transparent 45%),linear-gradient(180deg,#151519 0%,#09090b 38%);color:#f4f4f5;font-family:'Poppins',sans-serif}
.block-container{padding-top:2.6rem;padding-bottom:3rem;max-width:860px}
header[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#111114;border-right:1px solid #303036}
.stApp [data-testid="stMarkdownContainer"],.stApp p,.stApp li,.stApp label,.stApp input,.stApp textarea,.stApp button,.stApp [data-baseweb="select"] div,.stApp small{font-family:'Poppins',sans-serif!important}
h1,h2,h3,h4{font-family:var(--titulo)!important;font-weight:600!important;letter-spacing:.01em;line-height:1.05!important}
h2{font-size:2.3rem!important}h3{font-size:2rem!important}h4{font-size:1.55rem!important}
/* marca */
.fl-marca{font-family:var(--titulo)!important;font-weight:700;letter-spacing:.06em;color:#f4f4f5;font-size:2.7rem!important;margin:0;line-height:1!important;text-transform:uppercase}
.fl-marca:before{content:' ';display:inline-block;width:7px;height:.72em;background:var(--grad);border-radius:4px;margin-right:12px;vertical-align:.02em}
.fl-sub{color:#a1a1aa;margin:2px 0 1.1rem 19px;font-size:.9rem;font-style:italic;letter-spacing:.02em}
/* navegação: abas sublinhadas */
.st-key-aba [role="radiogroup"]{gap:2px 22px;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;border-bottom:1px solid #26262b;padding-bottom:2px}
.st-key-aba [role="radiogroup"] label{background:transparent!important;border:0!important;border-radius:0!important;padding:6px 2px 9px!important;margin:0;position:relative;flex:0 0 auto}
.st-key-aba [role="radiogroup"] label>div:first-child{display:none}
.st-key-aba [role="radiogroup"] label p{font-style:italic;color:#a1a1aa;font-size:.98rem}
.st-key-aba [role="radiogroup"] label:has(input:checked) p{color:#fff;font-weight:600}
.st-key-aba [role="radiogroup"] label:has(input:checked):after{content:'';position:absolute;left:0;right:0;bottom:-3px;height:3px;border-radius:3px;background:var(--grad)}
/* opções em formulários */
.stRadio [role="radiogroup"]{gap:8px}
.stRadio [role="radiogroup"] label{background:#151519;border:1px solid #303036;border-radius:999px;padding:7px 14px}
.stRadio [role="radiogroup"] label:has(input:checked){border-color:#ef233c;background:rgba(239,35,60,.12)}
/* botões em pílula com gradiente */
.stButton>button,.stFormSubmitButton>button,.stDownloadButton>button{border-radius:999px;font-weight:600;min-height:2.7rem;padding:0 1.4rem;transition:all .18s ease}
button[kind="primary"],button[kind="primaryFormSubmit"]{background:var(--grad)!important;border:0!important;color:#fff!important;font-family:var(--titulo);font-size:1.3rem!important;letter-spacing:.03em;box-shadow:0 8px 22px -10px rgba(239,35,60,.75)}
.stApp button[kind="primary"] p,.stApp button[kind="primaryFormSubmit"] p{font-size:1.3rem!important;font-family:var(--titulo)!important;font-weight:600;line-height:1}
button[kind="primary"]:hover,button[kind="primaryFormSubmit"]:hover{filter:brightness(1.08);transform:translateY(-1px)}
button[kind="secondary"],button[kind="secondaryFormSubmit"],.stDownloadButton>button{background:transparent!important;border:1px solid #3b3b44!important;color:#f4f4f5!important}
button[kind="secondary"]:hover,button[kind="secondaryFormSubmit"]:hover,.stDownloadButton>button:hover{border-color:#ef233c!important;color:#ff5266!important}
button:focus-visible{box-shadow:0 0 0 .2rem rgba(239,35,60,.35)!important}
/* cartões */
/* só os contêineres com borda (os sem borda usam a classe vazia st-emotion-cache-0 no Streamlit 1.41) */
[data-testid="stVerticalBlockBorderWrapper"]:not(.st-emotion-cache-0),[data-testid="stForm"]{border-color:#26262b!important;border-radius:24px!important;background:linear-gradient(160deg,#1a1a1f 0%,#0e0e11 100%)}
[data-testid="stMetric"]{background:linear-gradient(160deg,#1c1c22,#101013);border:1px solid #26262b;border-radius:20px;padding:14px 18px}
div[data-testid="stMetricValue"],div[data-testid="stMetricValue"] *{font-family:var(--titulo)!important;font-variant-numeric:tabular-nums;color:#fff;font-weight:600;font-size:2.2rem;line-height:1.1}
div[data-testid="stMetricLabel"] p{color:#a1a1aa;font-style:italic}
[data-testid="stImage"] img{border-radius:18px}
[data-testid="stExpander"] details{border-color:#26262b;border-radius:16px;overflow:hidden}
/* campos sublinhados, como no login do modelo */
[data-baseweb="input"],[data-baseweb="textarea"]{background:transparent!important;border:0!important;border-bottom:1.5px solid #4a4a52!important;border-radius:0!important}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within{border-bottom-color:#ef233c!important}
[data-baseweb="input"] input,[data-baseweb="base-input"],textarea{background:transparent!important;color:#f4f4f5!important}
[data-baseweb="select"]>div{background-color:#151519!important;color:#f4f4f5!important;border-color:#3b3b44!important;border-radius:14px!important}
[data-testid="stWidgetLabel"] p{font-style:italic;color:#c4c4cc}
[data-testid="stAlertContainer"]{border-radius:16px}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]){background:rgba(239,35,60,.08);border-left:4px solid #ef233c}
[data-testid="stAlertContentInfo"]{color:#f4f4f5}
[data-testid="stProgress"] div[role="progressbar"]>div>div>div{background:var(--grad)!important}
hr{border-color:#26262b}
small,.stCaption{color:#a1a1aa}
/* elementos próprios */
.fl-presc{color:#ff5266;font-weight:600;font-size:1.02rem}
.fl-rec{background:var(--grad);border-radius:22px 22px 22px 6px;padding:14px 18px;font-size:.88rem;color:#fff;line-height:1.5;margin:4px 0 10px}
.fl-hero{position:relative;border-radius:28px;overflow:hidden;min-height:330px;padding:26px 24px 22px;display:flex;flex-direction:column;justify-content:flex-end;
background-color:#151519;background-size:cover;background-position:center 30%;border:1px solid #26262b;margin-bottom:14px}
.fl-chip{align-self:flex-start;font-size:.72rem;letter-spacing:.12em;font-weight:600;color:#fff;background:rgba(239,35,60,.9);border-radius:999px;padding:4px 11px;margin-bottom:10px}
.fl-hero-tit{font-family:var(--titulo)!important;font-weight:700;font-size:2.9rem!important;line-height:.95;text-transform:uppercase;color:#fff;margin:0 0 6px}
.fl-hero .fl-texto{color:#e4e4e7;margin:0 0 12px;font-size:.92rem}
.fl-ficha{display:grid;grid-template-columns:auto 1fr;gap:4px 26px;font-size:.9rem}
.fl-ficha span{color:#a1a1aa;font-style:italic}.fl-ficha b{color:#fff;font-style:italic;font-weight:600}
.fl-grade{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:6px 0 14px}
.fl-tile{background:linear-gradient(160deg,#1c1c22,#101013);border:1px solid #26262b;border-radius:22px;padding:14px 16px;min-height:104px;display:flex;flex-direction:column;gap:2px}
.fl-tile.destaque{background:var(--grad);border:0;box-shadow:0 12px 28px -14px rgba(239,35,60,.8)}
.fl-tile small{color:#a1a1aa;font-style:italic;font-size:.8rem}.fl-tile.destaque small,.fl-tile.destaque em{color:rgba(255,255,255,.85)}
.fl-tile b{font-family:var(--titulo);font-size:2.1rem;font-weight:600;line-height:1;color:#fff;margin-top:6px}
.fl-tile em{font-size:.78rem;color:#a1a1aa;font-style:normal;margin-top:2px}
@media(max-width:600px){.block-container{padding-left:1rem;padding-right:1rem;padding-top:2.4rem}.fl-marca{font-size:2.3rem!important}
.fl-grade{grid-template-columns:repeat(2,1fr)}.fl-hero{min-height:300px}.fl-hero-tit{font-size:2.5rem!important}}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ estado
def estado() -> dict:
    if "S" not in st.session_state:
        st.session_state.S = A.carregar()
    return st.session_state.S


def salvar() -> None:
    A.salvar(st.session_state.S)


S = estado()
t = R.hoje()


def aviso(tipo: str, titulo: str, texto: str) -> None:
    fn = {"erro": st.error, "alerta": st.warning, "ok": st.success, "info": st.info}[tipo]
    fn(f"**{titulo}**  \n{texto}")


def aviso_urgente() -> None:
    aviso("erro", "PARE — procure atendimento médico urgente",
          "Foi registrado inchaço súbito ou importante, febre, vermelhidão intensa ou incapacidade de apoiar a perna. "
          "Os treinos ficam bloqueados. Depois do atendimento, atualize a avaliação no Perfil e o check-in de hoje.")


def foto(ex_id: str, i: int) -> str:
    pasta = D.FOTOS.get(ex_id)
    if not pasta:
        return ""
    local = PASTA_FOTOS / f"{pasta}_{i}.jpg"
    return str(local) if local.exists() else f"{D.FOTO_URL_BASE}{pasta}/{i}.jpg"


def mostrar_fotos(ex_id: str) -> None:
    if not D.FOTOS.get(ex_id):
        st.caption("Sem foto para este exercício.")
        return
    c1, c2 = st.columns(2)
    c1.image(foto(ex_id, 0), caption="Início", use_container_width=True)
    c2.image(foto(ex_id, 1), caption="Fim", use_container_width=True)


def capa(ex_ids, chip: str, titulo: str, texto: str = "", ficha=()) -> None:
    """Capa com foto de fundo, no estilo do modelo (foto do primeiro exercício que tiver imagem)."""
    pasta = next((D.FOTOS[i] for i in ex_ids if D.FOTOS.get(i)), None)
    fundo = "linear-gradient(180deg,rgba(9,9,11,.10) 0%,rgba(9,9,11,.55) 45%,#09090b 92%)"
    if pasta:
        fundo += f",url('{D.FOTO_URL_BASE}{pasta}/0.jpg')"
    linhas = "".join(f"<span>{html.escape(k)}</span><b>{html.escape(v)}</b>" for k, v in ficha)
    st.markdown(f"<div class='fl-hero' style=\"background-image:{fundo}\"><span class='fl-chip'>{html.escape(chip)}</span>"
                f"<div class='fl-hero-tit'>{html.escape(titulo)}</div>" + (f"<div class='fl-texto'>{html.escape(texto)}</div>" if texto else "")
                + (f"<div class='fl-ficha'>{linhas}</div>" if linhas else "") + "</div>", unsafe_allow_html=True)


def cartoes(itens) -> None:
    """Grade de indicadores: (rótulo, valor, nota opcional, destaque)."""
    blocos = "".join(f"<div class='fl-tile{' destaque' if dest else ''}'><small>{html.escape(r)}</small><b>{html.escape(v)}</b>"
                     + (f"<em>{html.escape(n)}</em>" if n else "") + "</div>" for r, v, n, dest in itens)
    st.markdown(f"<div class='fl-grade'>{blocos}</div>", unsafe_allow_html=True)


def prescricao(e: dict) -> str:
    if e["tipo"] == "tempo":
        return f"{e['duracao']} min"
    return f"{e['series']} × {e['reps']}" + (" (sem carga)" if e.get("semCarga") else "") + f" · descanso {e['descanso']} s"


def cartao_exercicio(ex_id: str, com_rec: bool) -> None:
    e = R.get_ex(S, ex_id)
    livre, msg = R.status_ex(S, ex_id)
    with st.container(border=True):
        mostrar_fotos(ex_id)
        st.markdown(f"#### {e['nome']}")
        st.markdown(f"<span class='fl-presc'>{prescricao(e)}</span> · {e['grupo']}", unsafe_allow_html=True)
        st.caption("Músculos: " + e["musculos"])
        if not livre:
            st.error(msg)
        elif com_rec:
            st.markdown(f"<div class='fl-rec'>{R.recomendacao(S, ex_id)}</div>", unsafe_allow_html=True)
        with st.expander("Como executar"):
            for n, passo in enumerate(e["instrucoes"], 1):
                st.markdown(f"{n}. {passo}")
        for a in e["alertas"]:
            st.caption("⚠️ " + a)


def cronometro(fim_ms: int) -> None:
    components.html(f"""
<div id="r" style="font-family:Poppins,system-ui,sans-serif;background:linear-gradient(100deg,#ff5266 0%,#ef233c 45%,#b5122a 100%);color:#fff;border-radius:999px;padding:8px 22px;display:flex;justify-content:space-between;align-items:center">
<span style="font-style:italic">Descanso</span><b id="t" style="font-size:1.6rem;font-variant-numeric:tabular-nums">0:00</b></div>
<script>
const fim={fim_ms};
function f(){{const s=Math.ceil((fim-Date.now())/1000);const el=document.getElementById('t');
if(s<=0){{el.textContent='Pronto!';try{{navigator.vibrate&&navigator.vibrate(200)}}catch(e){{}}return;}}
el.textContent=Math.floor(s/60)+':'+String(s%60).padStart(2,'0');setTimeout(f,250);}}f();
</script>""", height=70)


# ------------------------------------------------------------------ cabeçalho e navegação
st.markdown("<div class='fl-marca'>FOCO LEVE</div><div class='fl-sub'>Treino e Emagrecimento</div>", unsafe_allow_html=True)
ABAS = ["Início", "Treinos", "Evolução", "Hábitos", "Perfil"]
if "aba" not in st.session_state:
    st.session_state.aba = "Início"
if st.session_state.get("_ir"):
    st.session_state.aba = st.session_state.pop("_ir")
aba = st.radio("Seção", ABAS, horizontal=True, key="aba", label_visibility="collapsed")
if st.session_state.get("aviso"):
    tipo, tit, txt = st.session_state.pop("aviso")
    aviso(tipo, tit, txt)


def ir(nova: str) -> None:
    st.session_state.aba = nova


# ------------------------------------------------------------------ formulário de avaliação
def form_avaliacao() -> None:
    a = S["assess"]
    SN = ["sim", "nao"]
    SNX = ["sim", "nao", "nao_sei"]
    rot = {"sim": "Sim", "nao": "Não", "nao_sei": "Não sei"}

    def radio(lbl, k, opts):
        idx = opts.index(a[k]) if a.get(k) in opts else None
        return st.radio(lbl, opts, index=idx, format_func=rot.get, horizontal=True, key="as_" + k)

    with st.form("avaliacao"):
        st.markdown("##### Saúde e segurança")
        v = {
            "dor": radio("Existe dor no joelho ou em outra articulação?", "dor", SN),
            "inchaco": radio("Existe inchaço em alguma articulação?", "inchaco", SN),
            "caminhar": radio("Existe dificuldade para caminhar?", "caminhar", SN),
            "diag": radio("Existe diagnóstico médico?", "diag", SN),
        }
        diag_txt = st.text_input("Diagnóstico informado (se houver)", a.get("diagTxt", ""))
        v["liberacao"] = radio("Há liberação profissional para musculação?", "liberacao", SNX)
        v["lesao"] = radio("Existe alguma lesão muscular em recuperação?", "lesao", SNX)
        obs = st.text_area("Outra limitação física ou observação (opcional)", a.get("joelho", ""))
        proib = st.text_area("Exercícios proibidos pelo médico ou fisioterapeuta (se houver)", a.get("proibidos", ""))
        recom = st.text_area("Exercícios recomendados pelo profissional (se houver)", a.get("recomendados", ""))
        st.markdown("**Sinais de alerta agora**")
        red = {k: st.checkbox(lbl, a["red"].get(k, False), key="asr_" + k) for k, lbl in
               [("subito", "Inchaço súbito ou importante"), ("febre", "Febre"),
                ("vermelhidao", "Vermelhidão intensa"), ("apoio", "Incapacidade de apoiar a perna")]}
        if st.form_submit_button("Salvar avaliação", type="primary"):
            faltam = [k for k, x in v.items() if x is None]
            if faltam:
                st.error("Responda todas as perguntas de Sim/Não antes de salvar.")
                return
            a.update(v)
            a.update({"diagTxt": diag_txt.strip(), "joelho": obs.strip(), "proibidos": proib.strip(),
                      "recomendados": recom.strip(), "red": red, "done": True, "date": t})
            if not S.get("startDate"):
                S["startDate"] = t
            st.session_state.editar_aval = False
            salvar()
            st.session_state.aviso = resultado_avaliacao()
            st.rerun()


def resultado_avaliacao():
    n = R.seguranca(S)
    if n == "urgent":
        return ("erro", "PARE — procure atendimento médico urgente", "Sinal de alerta registrado. Os treinos ficam bloqueados.")
    if n == "caution":
        return ("alerta", "Avaliação profissional recomendada", "Há dor, inchaço ou dificuldade para caminhar registrados. Os exercícios de pernas ficam bloqueados enquanto isso.")
    if n == "noclear":
        return ("alerta", "Liberação pendente", "Sem liberação profissional registrada para musculação. Recomenda-se obtê-la antes de começar.")
    return ("ok", "Avaliação registrada", "Plano completo disponível: membros superiores, membros inferiores e cardio.")


# ------------------------------------------------------------------ check-in
def checkin() -> None:
    ci = S["checkins"].get(t)
    if ci and not st.session_state.get("editar_ci"):
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.markdown("**Check-in de hoje**")
            if c2.button("Editar", key="ed_ci"):
                st.session_state.editar_ci = True
                st.rerun()
            sono = ci.get("sono")
            st.caption(f"Dor {ci['dor']}/10 · {'com' if ci.get('inchaco') else 'sem'} inchaço · fadiga {ci['fadiga']}/5" + (f" · sono {brx(sono)} h" if ok(sono) else ""))
            if ci.get("inchaco") or ci["dor"] >= 3:
                st.warning("Com dor ou inchaço, faça apenas o que não causa dor e procure avaliação se não passar.")
        return
    c = ci or {"dor": 0, "inchaco": False, "fadiga": 2, "sono": None, "redItems": []}
    with st.form("checkin"):
        st.markdown("**Como você está hoje?**")
        dor = st.slider("Dor em articulações (joelho, quadril, tornozelo)", 0, 10, int(c["dor"]))
        inch = st.radio("Inchaço em alguma articulação?", ["Não", "Sim"], index=1 if c.get("inchaco") else 0, horizontal=True)
        fad = st.select_slider("Fadiga (1 = descansado, 5 = exausto)", [1, 2, 3, 4, 5], value=int(c.get("fadiga", 2)))
        sono_txt = st.text_input("Horas de sono na última noite", brx(c["sono"]) if ok(c.get("sono")) else "", placeholder="Ex.: 7,5")
        st.markdown("Algum destes sinais hoje?")
        itens = {k: st.checkbox(lbl, k in (c.get("redItems") or []), key="ci_" + k) for k, lbl in
                 [("subito", "Inchaço súbito ou importante"), ("febre", "Febre"),
                  ("vermelhidao", "Vermelhidão intensa em uma articulação ou na perna"), ("apoio", "Não consigo apoiar a perna")]}
        if st.form_submit_button("Salvar check-in", type="primary"):
            sono = num(sono_txt)
            if sono_txt.strip() and (not ok(sono) or not 0 <= sono <= 24):
                st.error("Horas de sono devem estar entre 0 e 24.")
                return
            red = [k for k, v in itens.items() if v]
            S["checkins"][t] = {"dor": dor, "inchaco": inch == "Sim", "fadiga": fad,
                                "sono": sono if sono_txt.strip() else None, "red": bool(red), "redItems": red}
            st.session_state.editar_ci = False
            salvar()
            st.rerun()


# ------------------------------------------------------------------ INÍCIO
def tela_primeiro_acesso() -> None:
    p = S["profile"]
    capa(["agachamento_goblet"], "PRIMEIRO PASSO", "Olá, vamos definir a meta",
         "Antes do primeiro treino, responda a algumas perguntas rápidas de segurança. "
         "Elas não substituem avaliação médica nem a orientação do profissional de educação física.")
    cartoes([("Peso inicial", f"{br(p['pesoInicial'])} kg", None, True), ("Meta", f"{br(p['pesoMeta'])} kg", "sem prazo", True),
             ("Idade", f"{p['idade']} anos", None, False), ("Altura", f"{br(p['altura'], 0)} cm", None, False)])
    st.subheader("Avaliação de segurança")
    st.caption(f"IMC inicial estimado: {br(R.imc(S, p['pesoInicial']))} kg/m² (triagem, não é diagnóstico). "
               f"Diferença até a meta: {br(p['pesoInicial'] - p['pesoMeta'])} kg, sem data obrigatória.")
    form_avaliacao()


def tela_inicio() -> None:
    if not S["assess"]["done"]:
        # bloco próprio: evita que o formulário seja reaproveitado pelo do check-in após salvar
        with st.container():
            tela_primeiro_acesso()
        return
    if R.seguranca(S) == "urgent":
        aviso_urgente()
    lem = R.lembretes(S, datetime.now().strftime("%H:%M"))
    if lem:
        with st.container(border=True):
            st.caption("LEMBRETES")
            for x in lem:
                st.write(x)
    wk = R.treino_do_dia(S, t)
    W = D.TREINOS[wk]
    ficha = ()
    if wk != "OFF":
        n = sum(1 for i in W["ex"] if R.status_ex(S, i)[0])
        ficha = (("Duração", f"cerca de {R.minutos_estimados(S, wk)} min"), ("Exercícios", str(n)),
                 ("Programa", f"semana {min(R.semana_programa(S), 4)} de 4"))
    capa(W["ex"] or ["esteira_caminhada"], f"{D.DIAS_SEMANA[R.dia_js(t)].upper()}, {fmt_dy(t)}", W["nome"], W["obj"], ficha)
    if wk != "OFF":
        if S["active"]:
            st.button("Continuar treino", type="primary", on_click=ir, args=("Treinos",), use_container_width=True)
        elif R.feito_em(S, t):
            st.success("Treino de hoje concluído.")
        elif st.button("Iniciar treino", type="primary", use_container_width=True):
            tentar_iniciar(wk)
    checkin()
    p = S["profile"]
    cw, ini, meta = R.peso_atual(S), p["pesoInicial"], p["pesoMeta"]
    ws = R.inicio_semana(t)
    ses = [s for s in S["sessions"] if s["date"] in R.dias_da_semana(ws)]
    st.markdown("### Painel")
    i = R.imc(S, cw)
    en = R.energia_semana(S, ws)
    cartoes([("Peso atual" if S["weights"] else "Peso inicial", f"{br(cw)} kg",
              f"{'+' if cw > ini else ''}{br(cw - ini)} kg desde o início" if S["weights"] else None, True),
             ("Meta (sem prazo)", f"{br(meta)} kg", f"faltam {br(max(0, cw - meta))} kg", True),
             ("IMC (triagem)", br(i), R.imc_categoria(i), False),
             ("Treinos na semana", f"{sum(1 for s in ses if s.get('status') == 'concluida')} de {R.planejados_semana(S)}", None, False),
             ("Minutos na semana", br(sum(float(s.get('minutes') or 0) for s in ses), 0), None, False),
             ("kcal na semana", "≈ " + br(en["kcal"], 0), "estimativa", False)])
    cm = en["cardioMin"]
    st.markdown(f"**Cardio na semana: {br(cm, 0)} min** — meta da OMS: 150 a 300 min")
    st.progress(min(1.0, cm / 300))
    st.caption(("Dentro da faixa recomendada pela OMS." if 150 <= cm < 300 else "Faixa máxima da OMS atingida." if cm >= 300
                else f"Faltam {br(150 - cm, 0)} min para o mínimo da OMS.") +
               " Calorias calculadas pelo Compêndio de Atividades Físicas 2024 (MET × peso × tempo): valores aproximados.")
    grafico_peso("diario", 180)
    rv = R.recuperacao(S)
    st.markdown(f"**Recuperação:** {rv['txt']} — {rv['detalhe']}")
    historico_cargas()


def historico_cargas() -> None:
    linhas = []
    for ex_id in D.EXERCICIOS:
        h = [x for x in R.historico_ex(S, ex_id) if x["max"] is not None]
        if h:
            linhas.append({"Exercício": R.nome_ex(ex_id), "Última (kg)": brx(h[-1]["max"]), "Data": fmt_d(h[-1]["date"]),
                           "Anterior (kg)": brx(h[-2]["max"]) if len(h) > 1 else "—"})
    st.markdown("### Histórico de cargas")
    if linhas:
        st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)
    else:
        st.caption("As cargas aparecem aqui depois do primeiro treino registrado.")


def tentar_iniciar(wk: str) -> None:
    if R.feito_em(S, t):
        st.session_state.aviso = ("info", "Treino de hoje já registrado", "O próximo treino fica para amanhã. Não é preciso compensar.")
    elif R.seguranca(S) == "urgent":
        st.session_state.aviso = ("erro", "Treinos bloqueados", "Há sinal de alerta registrado. Procure atendimento médico.")
    elif R.seguranca(S) == "pending":
        st.session_state.aviso = ("alerta", "Avaliação pendente", "Conclua a avaliação de segurança antes do primeiro treino.")
    elif R.seguranca(S) in ("caution", "noclear") and wk != "REC" and not st.session_state.get("ciente"):
        st.session_state.pre_inicio = wk
        st.session_state._ir = "Treinos"
        st.rerun()
    else:
        R.iniciar_sessao(S, wk)
        st.session_state.pre_inicio = None
        st.session_state.ciente = False
        salvar()
        st.session_state._ir = "Treinos"
    st.rerun()


# ------------------------------------------------------------------ TREINOS
def tela_treinos() -> None:
    if R.alerta_vermelho(S):
        aviso_urgente()
    if S["active"]:
        tela_sessao()
        return
    ws = R.inicio_semana(t)
    if "dia_sel" not in st.session_state:
        st.session_state.dia_sel = t
    st.markdown(f"### Agenda da semana  \n<small>{fmt_d(ws)} a {fmt_d(R.add_dias(ws, 6))}</small>", unsafe_allow_html=True)
    cols = st.columns(7)
    for col, d in zip(cols, R.dias_da_semana(ws)):
        k = R.treino_do_dia(S, d)
        marca = " ✓" if R.feito_em(S, d) else ""
        if col.button(f"{D.DIAS_CURTOS[R.dia_js(d)]}\n{R.pd(d).day}\n{D.TREINOS[k]['curto']}{marca}", key="d_" + d,
                      type="primary" if d == st.session_state.dia_sel else "secondary", use_container_width=True):
            st.session_state.dia_sel = d
            st.rerun()
    pw = R.semana_programa(S)
    fase = D.FASES[min(pw, 4) - 1]
    with st.expander(f"Semana {pw}{' (ciclo de 4 concluído)' if pw > 4 else ' de 4'} · {fase['n']}"):
        for item in fase["itens"]:
            st.markdown("- " + item)
    d = st.session_state.dia_sel
    wk = R.treino_do_dia(S, d)
    W = D.TREINOS[wk]
    ficha = (("Duração", f"cerca de {R.minutos_estimados(S, wk)} min"), ("Exercícios", str(len(W["ex"])))) if wk != "OFF" else ()
    capa(W["ex"] or ["esteira_caminhada"], f"{D.DIAS_SEMANA[R.dia_js(d)].upper()} · {fmt_d(d)}" + (" · HOJE" if d == t else ""),
         W["nome"], W["obj"], ficha)
    with st.container():
        if d == t:
            if st.session_state.get("pre_inicio"):
                aviso("alerta", "Antes de começar", "Há dor, inchaço ou liberação pendente registrados. Faça só o que não causa dor e interrompa ao primeiro sintoma.")
                ciente = st.checkbox("Entendi e vou interromper ao primeiro sintoma.")
                c1, c2 = st.columns(2)
                if c1.button("Iniciar assim mesmo", disabled=not ciente, type="primary"):
                    st.session_state.ciente = True
                    tentar_iniciar(st.session_state.pre_inicio)
                if c2.button("Voltar"):
                    st.session_state.pre_inicio = None
                    st.rerun()
            elif R.feito_em(S, t):
                st.success("Treino de hoje concluído. Para recuperar bem, não acumule outro treino hoje.")
            else:
                if wk != "OFF" and st.button("Iniciar este treino", type="primary"):
                    tentar_iniciar(wk)
                opcoes = [""] + list(D.TREINOS)
                atual = S["dayOverride"].get(t, "")
                novo = st.selectbox("Trocar o treino de hoje", opcoes, index=opcoes.index(atual) if atual in opcoes else 0,
                                    format_func=lambda k: "Manter a agenda" if not k else D.TREINOS[k]["nome"])
                if novo != atual:
                    if novo:
                        S["dayOverride"][t] = novo
                    else:
                        S["dayOverride"].pop(t, None)
                    salvar()
                    st.rerun()
        elif d < t:
            ss = [s for s in S["sessions"] if s["date"] == d]
            for s in ss:
                st.caption(f"{'Concluído' if s.get('status') == 'concluida' else 'Interrompido'}: {R.nome_treino(s['workout'])} · {br(s.get('pct', 0), 0)}% · {br(s.get('minutes', 0), 0)} min")
            if not ss:
                st.caption("Nenhum treino registrado neste dia.")
    for ex_id in W["ex"]:
        cartao_exercicio(ex_id, d == t)


def tela_sessao() -> None:
    a = S["active"]
    W = D.TREINOS[a["workout"]]
    feitos = sum(1 for e in a["ex"] if e.get("done"))
    with st.container(border=True):
        st.caption(f"SESSÃO EM ANDAMENTO · {fmt_d(a['date'])}")
        st.subheader(W["nome"])
        st.progress(feitos / len(a["ex"]) if a["ex"] else 0.0, text=f"{feitos}/{len(a['ex'])} exercícios")
        c = st.columns(2)
        dec = int((time.time() * 1000 - a["startedAt"]) / 1000)
        c[0].metric("Tempo de treino", f"{dec // 60}:{dec % 60:02d}")
        c[1].metric("Volume", f"{br(R.volume(a), 0)} kg")
        st.caption("Marque a série ao terminar: repetições e a última carga usada são preenchidas sozinhas e o descanso começa. Esforço recomendado: 6 a 8 de 10, sem chegar à falha.")
    if st.session_state.get("descanso_ate", 0) > time.time() * 1000:
        cronometro(st.session_state.descanso_ate)
    if a["workout"] in ("A", "B", "C", "LA", "LB"):
        st.info("**Aquecimento (5 a 10 min):** 5 minutos de esteira ou bicicleta em ritmo leve e 1 série leve de 10 a 12 repetições do primeiro exercício. "
                "Ordem do treino: músculos grandes antes dos pequenos e exercícios multiarticulares antes dos isolados.")
    for i, se in enumerate(a["ex"]):
        exercicio_sessao(i, se)
    st.divider()
    if st.session_state.get("finalizar"):
        with st.form("fim"):
            st.markdown("**Como você se sentiu ao terminar?**")
            sens = st.radio("Sensação geral", ["bem", "cansado", "exausto", "dor"], index=None, horizontal=True,
                            format_func={"bem": "Bem", "cansado": "Cansado, mas bem", "exausto": "Muito cansado", "dor": "Com dor"}.get)
            mins = st.number_input("Duração (minutos)", 1, 240, max(1, min(180, round((time.time() * 1000 - a["startedAt"]) / 60000))))
            obs = st.text_area("Observações")
            c1, c2 = st.columns(2)
            if c1.form_submit_button("Salvar sessão", type="primary"):
                if not sens:
                    st.error("Escolha como você se sentiu.")
                    return
                rec = R.finalizar_sessao(S, sens, mins, obs)
                st.session_state.finalizar = False
                st.session_state.descanso_ate = 0
                salvar()
                pr = rec.pop("_recordes")
                if sens == "dor":
                    st.session_state.aviso = ("alerta", "Sessão salva com registro de dor", "Procure avaliação antes do próximo treino que possa agravar a dor.")
                else:
                    st.session_state.aviso = ("ok", "Sessão salva",
                        f"{sum(1 for e in rec['ex'] if e.get('done'))} de {len(rec['ex'])} exercícios ({br(rec['pct'], 0)}%) · {rec['minutes']} min · volume de {br(rec['volume'], 0)} kg · ≈ {br(rec['kcal'], 0)} kcal (estimativa)."
                        + (" Novo recorde de carga: " + "; ".join(pr) + "." if pr else ""))
                st.rerun()
            if c2.form_submit_button("Voltar"):
                st.session_state.finalizar = False
                st.rerun()
    elif st.session_state.get("sintoma"):
        with st.form("sint"):
            st.markdown("**Qual sintoma?**")
            marc = [k for k, lbl in [("joelho", "Dor em articulação que piora com o exercício"), ("inchaco", "Inchaço em articulação"),
                                     ("apoio", "Dificuldade para apoiar a perna"), ("peito", "Dor ou aperto no peito"),
                                     ("ar", "Falta de ar desproporcional ao esforço"), ("tontura", "Tontura ou mal-estar"),
                                     ("outro", "Outra dor ou desconforto")] if st.checkbox(lbl, key="s_" + k)]
            c1, c2 = st.columns(2)
            if c1.form_submit_button("Interromper sessão", type="primary"):
                if not marc:
                    st.error("Marque pelo menos um sintoma.")
                    return
                urg = R.interromper_sessao(S, marc)
                st.session_state.sintoma = False
                salvar()
                st.session_state.aviso = (("erro", "PARE — procure atendimento médico",
                                           "Dor ou aperto no peito, falta de ar desproporcional ou incapacidade de apoiar a perna exigem avaliação médica.")
                                          if urg else ("alerta", "Sessão interrompida", "Descanse e não retome hoje. O registro foi salvo no histórico."))
                st.rerun()
            if c2.form_submit_button("Voltar"):
                st.session_state.sintoma = False
                st.rerun()
    else:
        c1, c2, c3 = st.columns(3)
        if c1.button("Finalizar sessão", type="primary", use_container_width=True):
            st.session_state.finalizar = True
            st.rerun()
        if c2.button("Senti um sintoma", use_container_width=True):
            st.session_state.sintoma = True
            st.rerun()
        if st.session_state.get("conf_desc"):
            if c3.button("Confirmar descarte", use_container_width=True):
                S["active"] = None
                st.session_state.conf_desc = False
                salvar()
                st.session_state.aviso = ("info", "Sessão descartada", "Nada foi registrado.")
                st.rerun()
        elif c3.button("Descartar", use_container_width=True):
            st.session_state.conf_desc = True
            st.rerun()


def exercicio_sessao(i: int, se: dict) -> None:
    e = R.get_ex(S, se["id"])
    sid = S["active"]["id"]
    with st.container(border=True):
        mostrar_fotos(se["id"])
        st.markdown(f"#### {e['nome']} {'✅' if se.get('done') else ''}")
        st.markdown(f"<span class='fl-presc'>{prescricao(e)}</span>", unsafe_allow_html=True)
        st.markdown(f"<div class='fl-rec'>{R.recomendacao(S, se['id'])}</div>", unsafe_allow_html=True)
        for j, sset in enumerate(se["sets"]):
            k = f"{sid}_{i}_{j}"
            if e["tipo"] == "tempo":
                c1, c2 = st.columns([1, 2])
                feito = c1.checkbox("Feito", sset["done"], key="c" + k)
                mn = c2.text_input("Minutos", sset.get("min", ""), key="m" + k, placeholder=f"meta {e['duracao']}", label_visibility="collapsed")
                if mn != sset.get("min", ""):
                    v = num(mn)
                    if mn.strip() and (not ok(v) or not 0 <= v <= 240):
                        st.error("Minutos inválidos.")
                    else:
                        sset["min"] = mn.strip()
                        salvar()
            else:
                c1, c2, c3 = st.columns([1.2, 1, 1])
                feito = c1.checkbox(f"Série {j + 1}", sset["done"], key="c" + k)
                if not e.get("semCarga"):
                    ult = R.ultima_carga(S, se["id"])
                    ld = c2.text_input("kg", sset.get("load", ""), key="l" + k, placeholder="kg" + (f" (últ. {ult})" if ult else ""), label_visibility="collapsed")
                    if ld != sset.get("load", ""):
                        v = num(ld)
                        if ld.strip() and (not ok(v) or not 0 <= v <= 500):
                            st.error("Carga inválida: use apenas números.")
                        else:
                            sset["load"] = ld.strip()
                            salvar()
                else:
                    c2.caption("sem carga")
                rp = c3.text_input("reps", sset.get("reps", ""), key="r" + k, placeholder="reps", label_visibility="collapsed")
                if rp != sset.get("reps", ""):
                    v = num(rp)
                    if rp.strip() and (not ok(v) or not 0 <= v <= 200):
                        st.error("Repetições inválidas.")
                    else:
                        sset["reps"] = rp.strip()
                        salvar()
            if feito != sset["done"]:
                desc = R.marcar_serie(S, i, j, feito)
                for pre in ("l", "r", "m"):
                    st.session_state.pop(pre + k, None)
                st.session_state.descanso_ate = time.time() * 1000 + desc * 1000 if desc else 0
                salvar()
                st.rerun()
        if e.get("cardio"):
            ops = D.INTENSIDADES[e["cardio"]]
            vals = [o[0] for o in ops]
            esc = st.selectbox("Intensidade (usada na estimativa de calorias)", vals, index=vals.index(se.get("met")) if se.get("met") in vals else 0,
                               format_func=dict(ops).get, key=f"met{sid}_{i}")
            if esc != se.get("met"):
                se["met"] = esc
                salvar()
        alts = [x for x in D.ALTERNATIVAS.get(se["id"], []) if x in D.EXERCICIOS and R.status_ex(S, x)[0]]
        if alts and not any(x["done"] for x in se["sets"]):
            tr = st.selectbox("Aparelho ocupado? Trocar por", [""] + alts, format_func=lambda x: "Manter este exercício" if not x else R.nome_ex(x), key=f"sw{sid}_{i}")
            if tr:
                S["active"]["ex"][i] = R.nova_entrada(S, tr)
                st.session_state.pop(f"sw{sid}_{i}", None)
                salvar()
                st.rerun()
        c1, c2 = st.columns(2)
        rpe_ops = [""] + [str(n) for n in range(1, 11)]
        rpe = c1.selectbox("Esforço percebido (1–10)", rpe_ops, index=rpe_ops.index(str(se.get("rpe") or "")), key=f"rpe{sid}_{i}")
        dor_ops = ["nenhum", "leve", "moderado", "forte"]
        dor = c2.selectbox("Dor ou desconforto", dor_ops, index=dor_ops.index(se.get("painLevel") or "nenhum"), format_func=str.capitalize, key=f"pl{sid}_{i}")
        if rpe != (se.get("rpe") or "") or dor != se.get("painLevel"):
            se["rpe"], se["painLevel"] = rpe, dor
            salvar()
        if dor in ("moderado", "forte"):
            st.error("**Pare este exercício.** Com dor moderada ou forte, interrompa. Se a dor for em uma articulação, no peito ou vier com inchaço, use “Senti um sintoma”.")
        txt = st.text_input("Onde e como foi o desconforto (opcional)", se.get("pain", ""), key=f"pt{sid}_{i}")
        if txt != se.get("pain", ""):
            se["pain"] = txt
            salvar()
        conc = st.checkbox("Exercício concluído", se.get("done", False), key=f"exd{sid}_{i}")
        if conc != se.get("done"):
            se["done"] = conc
            salvar()
            st.rerun()
        with st.expander("Como executar"):
            for n, passo in enumerate(e["instrucoes"], 1):
                st.markdown(f"{n}. {passo}")
        for al in e["alertas"]:
            st.caption("⚠️ " + al)


# ------------------------------------------------------------------ EVOLUÇÃO
def grafico_peso(modo: str, altura: int = 240) -> None:
    dados = R.serie_peso(S, modo)
    if len(dados) < 2:
        st.caption("Registre pelo menos duas pesagens para ver o gráfico de evolução do peso.")
        return
    df = pd.DataFrame([{"ordem": n, "Data": l, "Peso (kg)": round(v, 1)} for n, (l, v) in enumerate(dados)])
    lo, hi = float(df["Peso (kg)"].min()), float(df["Peso (kg)"].max())
    # especificação Vega-Lite direta: não depende do pacote altair, que não importa no Python 3.14
    spec = {
        "height": altura,
        "mark": {"type": "line", "color": "#EF233C", "strokeWidth": 3, "point": {"color": "#FF5266", "size": 70}},
        "encoding": {
            "x": {"field": "Data", "type": "nominal", "sort": list(df["Data"]), "title": None},
            "y": {"field": "Peso (kg)", "type": "quantitative", "scale": {"domain": [lo - 1.5, hi + 1.5]}},
            "tooltip": [{"field": "Data", "type": "nominal"}, {"field": "Peso (kg)", "type": "quantitative"}],
        },
    }
    st.vega_lite_chart(df, spec, use_container_width=True)


def tela_evolucao() -> None:
    p = S["profile"]
    cw, ini, meta = R.peso_atual(S), p["pesoInicial"], p["pesoMeta"]
    st.markdown("### Peso")
    c = st.columns(4)
    c[0].metric("Atual" if S["weights"] else "Inicial", f"{br(cw)} kg")
    c[1].metric("Desde o início", f"{'+' if cw - ini > 0 else ''}{br(cw - ini)} kg" if S["weights"] else "—",
                f"{'+' if cw > ini else ''}{br((cw - ini) / ini * 100)}%" if S["weights"] else None, delta_color="inverse")
    c[2].metric("Até a meta", f"{br(max(0, cw - meta))} kg")
    ms = R.media_semana(S, R.inicio_semana(t))
    c[3].metric("Média da semana", f"{br(ms)} kg" if ms is not None else "—")
    st.caption("Oscilações de um dia para o outro refletem água, alimentação e intestino, não ganho ou perda comprovada de gordura. Compare médias semanais.")
    with st.form("pesagem", clear_on_submit=True):
        st.markdown("**Registrar pesagem**")
        c1, c2 = st.columns(2)
        dt = c1.date_input("Data", value=R.pd(t), max_value=R.pd(t), format="DD/MM/YYYY")
        peso = c2.text_input("Peso (kg)", placeholder="Ex.: 114,2")
        c1, c2 = st.columns(2)
        cint = c1.text_input("Circunferência abdominal (cm)", placeholder="opcional")
        cond = c2.selectbox("Condições da pesagem", ["Em jejum, após ir ao banheiro", "Pela manhã, após café", "À tarde ou à noite", "Outra condição"])
        obs = st.text_input("Observações", placeholder="opcional")
        if st.form_submit_button("Salvar pesagem", type="primary"):
            pv, cv = num(peso), num(cint)
            erros = []
            if not ok(pv) or not 30 <= pv <= 300:
                erros.append("Informe o peso entre 30 e 300 kg.")
            if cint.strip() and (not ok(cv) or not 40 <= cv <= 250):
                erros.append("A circunferência deve ficar entre 40 e 250 cm.")
            if erros:
                st.error(" ".join(erros))
            else:
                d = dt.isoformat()
                S["weights"] = [x for x in S["weights"] if x["date"] != d]
                S["weights"].append({"id": R.novo_id(), "date": d, "peso": round(pv, 1), "cintura": round(cv, 1) if cint.strip() else None,
                                     "cond": cond, "obs": obs.strip()})
                salvar()
                st.success("Pesagem salva.")
                st.rerun()
    modo = st.radio("Gráfico", ["diario", "semanal", "mensal"], horizontal=True, format_func={"diario": "Diário", "semanal": "Semanal", "mensal": "Mensal"}.get)
    grafico_peso(modo)
    st.markdown("### Pesagens")
    w = list(reversed(R.pesos_ordenados(S)))
    if not w:
        st.caption("Nenhuma pesagem registrada.")
    for x in w:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{br(x['peso'])} kg** · {fmt_dy(x['date'])}" + (f" · cintura {brx(x['cintura'])} cm" if ok(x.get("cintura")) else "") + f"  \n<small>{x.get('cond', '')}{' · ' + x['obs'] if x.get('obs') else ''}</small>", unsafe_allow_html=True)
        if c2.button("Excluir", key="dw" + x["id"]):
            S["weights"] = [y for y in S["weights"] if y["id"] != x["id"]]
            salvar()
            st.rerun()
    st.markdown("### Relatório semanal")
    if "sem_rel" not in st.session_state:
        st.session_state.sem_rel = R.inicio_semana(t)
    c1, c2, c3 = st.columns([1, 3, 1])
    if c1.button("‹ Anterior"):
        st.session_state.sem_rel = R.add_dias(st.session_state.sem_rel, -7)
        st.rerun()
    if c3.button("Próxima ›", disabled=st.session_state.sem_rel >= R.inicio_semana(t)):
        st.session_state.sem_rel = R.add_dias(st.session_state.sem_rel, 7)
        st.rerun()
    texto = R.relatorio_semanal(S, st.session_state.sem_rel)
    st.code(texto, language=None)
    st.download_button("Baixar relatório (.txt)", texto.encode("utf-8"), file_name=f"foco-leve-relatorio-{st.session_state.sem_rel}.txt")
    st.markdown("### Histórico de treinos")
    ss = sorted(S["sessions"], key=lambda s: -s.get("startedAt", 0))[:30]
    if not ss:
        st.caption("Nenhum treino registrado.")
    for s in ss:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{R.nome_treino(s['workout'])}** · {fmt_dy(s['date'])}  \n<small>{'Concluída' if s.get('status') == 'concluida' else 'Interrompida'} · {br(s.get('pct', 0), 0)}% · {br(s.get('minutes', 0), 0)} min"
                 + (f" · {br(s['volume'], 0)} kg de volume" if s.get("volume") else "") + (f" · ≈ {br(s['kcal'], 0)} kcal" if s.get("kcal") else "") + "</small>", unsafe_allow_html=True)
        if c2.button("Excluir", key="ds" + s["id"]):
            S["sessions"] = [y for y in S["sessions"] if y["id"] != s["id"]]
            salvar()
            st.rerun()


# ------------------------------------------------------------------ HÁBITOS
def tela_habitos() -> None:
    st.markdown("### Hábitos  \n<small>Opcional · salva automaticamente</small>", unsafe_allow_html=True)
    dsel = st.date_input("Dia", value=R.pd(t), max_value=R.pd(t), format="DD/MM/YYYY").isoformat()
    x = S["habits"].setdefault(dsel, {})
    c1, c2 = st.columns(2)
    agua = c1.number_input("Água (copos de 250 ml)", 0, 30, int(x.get("agua") or 0), key="h_agua_" + dsel)
    sono_txt = c2.text_input("Horas de sono", brx(x["sono"]) if ok(x.get("sono")) else "", key="h_sono_" + dsel, placeholder="Ex.: 7")
    ref = st.text_area("Refeições do dia", x.get("refeicoes", ""), key="h_ref_" + dsel, placeholder="O que comeu e em que horário (livre)")
    esc = {}
    for k, lbl in [("fome", "Fome ao longo do dia"), ("saciedade", "Saciedade após as refeições"), ("energia", "Nível de energia")]:
        esc[k] = st.select_slider(lbl + " (1 a 5)", [0, 1, 2, 3, 4, 5], value=int(x.get(k) or 0), format_func=lambda n: "—" if n == 0 else str(n), key=f"h_{k}_{dsel}")
    obs = st.text_area("Observações sobre a rotina", x.get("obs", ""), key="h_obs_" + dsel)
    sono = num(sono_txt)
    if sono_txt.strip() and (not ok(sono) or not 0 <= sono <= 24):
        st.error("Horas de sono devem ficar entre 0 e 24.")
    novo = {"agua": agua, "sono": sono if sono_txt.strip() and ok(sono) and 0 <= sono <= 24 else (x.get("sono") if sono_txt.strip() else None),
            "refeicoes": ref, "obs": obs, **{k: (v or None) for k, v in esc.items()}}
    if novo != {k: x.get(k) for k in novo}:
        x.update(novo)
        salvar()
    st.caption(f"{br(agua * 250, 0)} ml de água registrados.")
    linhas = []
    for n in range(7):
        d = R.add_dias(t, -n)
        y = S["habits"].get(d, {})
        linhas.append({"Dia": fmt_d(d), "Água": f"{br((y.get('agua') or 0) * 250, 0)} ml" if y.get("agua") else "—",
                       "Sono": f"{brx(y['sono'])} h" if ok(y.get("sono")) else "—", "Energia": f"{y['energia']}/5" if y.get("energia") else "—"})
    st.markdown("#### Últimos 7 dias")
    st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)
    st.markdown("#### Orientações gerais")
    for item in ["Monte o prato com verduras e legumes, uma fonte de proteína e uma porção de carboidrato, de preferência integral.",
                 "Prefira alimentos in natura ou minimamente processados e reduza ultraprocessados e bebidas açucaradas.",
                 "Beba água ao longo do dia, sem exageros.", "Mantenha horários regulares de refeição e de sono.",
                 "Para um plano alimentar individual, procure nutricionista. Este app não prescreve dietas, restrições ou medicamentos para emagrecer."]:
        st.markdown("- " + item)


# ------------------------------------------------------------------ PERFIL
def tela_perfil() -> None:
    p = S["profile"]
    st.markdown("### Perfil")
    with st.form("perfil"):
        nome = st.text_input("Nome (opcional)", p.get("nome", ""))
        c1, c2 = st.columns(2)
        campos = {"idade": ("Idade (anos)", 10, 100), "altura": ("Altura (cm)", 120, 230), "pesoInicial": ("Peso inicial (kg)", 30, 300),
                  "pesoMeta": ("Peso desejado (kg)", 30, 300), "dias": ("Dias por semana", 1, 7), "tempoMax": ("Tempo máximo por sessão (min)", 10, 180)}
        vals = {}
        for n, (k, (lbl, lo, hi)) in enumerate(campos.items()):
            vals[k] = (c1 if n % 2 == 0 else c2).text_input(lbl, brx(p[k]))
        c1, c2 = st.columns(2)
        local = c1.text_input("Local de treino", p.get("local", ""))
        nivel = c2.text_input("Nível", p.get("nivel", ""))
        obj = st.text_input("Objetivo", p.get("objetivo", ""))
        lim = st.text_area("Limitações e contraindicações", p.get("limitacao", ""))
        if st.form_submit_button("Salvar perfil", type="primary"):
            erros, novos = [], {}
            for k, (lbl, lo, hi) in campos.items():
                v = num(vals[k])
                if not ok(v) or not lo <= v <= hi:
                    erros.append(f"{lbl} deve ficar entre {lo} e {hi}.")
                else:
                    novos[k] = round(v, 1)
            if erros:
                st.error(" ".join(erros))
            else:
                novos["idade"], novos["dias"] = int(novos["idade"]), int(novos["dias"])
                p.update(novos)
                p.update({"nome": nome.strip(), "local": local.strip(), "nivel": nivel.strip(), "objetivo": obj.strip(), "limitacao": lim.strip()})
                salvar()
                st.success("Perfil salvo.")
                st.rerun()
    i0, i1 = R.imc(S, p["pesoInicial"]), R.imc(S, R.peso_atual(S))
    st.caption(f"IMC inicial: {br(i0)} kg/m² · IMC atual: {br(i1)} kg/m² ({R.imc_categoria(i1)}). Indicador de triagem, não é diagnóstico.")

    st.markdown("### Avaliação de segurança")
    if S["assess"]["done"] and not st.session_state.get("editar_aval"):
        tipo, tit, txt = resultado_avaliacao()
        aviso(tipo, tit, txt)
        a = S["assess"]
        yn = {"sim": "Sim", "nao": "Não", "nao_sei": "Não sei"}
        st.dataframe(pd.DataFrame([
            ("Dor articular", yn.get(a["dor"], "—")), ("Inchaço", yn.get(a["inchaco"], "—")), ("Dificuldade para caminhar", yn.get(a["caminhar"], "—")),
            ("Diagnóstico médico", yn.get(a["diag"], "—") + (": " + a["diagTxt"] if a.get("diagTxt") else "")),
            ("Liberação para musculação", yn.get(a["liberacao"], "—")), ("Lesão muscular em recuperação", yn.get(a["lesao"], "—")),
            ("Observações", a.get("joelho") or "—")], columns=["Item", "Resposta"]), hide_index=True, use_container_width=True)
        st.caption(f"Atualizada em {fmt_dy(a['date'])}" if a.get("date") else "")
        if st.button("Atualizar avaliação"):
            st.session_state.editar_aval = True
            st.rerun()
    else:
        form_avaliacao()

    st.markdown("### Plano de exercícios")
    st.caption("Séries, repetições, descanso e duração são editáveis.")
    usados = []
    for W in D.TREINOS.values():
        for x in W["ex"]:
            if x not in usados:
                usados.append(x)
    linhas = []
    for x in usados:
        e = R.get_ex(S, x)
        linhas.append({"id": x, "Ativo": e["ativo"], "Exercício": e["nome"], "Séries": int(e.get("series") or 1),
                       "Repetições": str(e.get("reps") or ""), "Descanso (s)": int(e.get("descanso") or 0),
                       "Duração (min)": int(e.get("duracao") or 0) if e["tipo"] == "tempo" else None})
    df = pd.DataFrame(linhas)
    ed = st.data_editor(df, hide_index=True, use_container_width=True, disabled=["id", "Exercício"], column_config={
        "id": None,
        "Séries": st.column_config.NumberColumn(min_value=1, max_value=10, step=1),
        "Descanso (s)": st.column_config.NumberColumn(min_value=0, max_value=600, step=5),
        "Duração (min)": st.column_config.NumberColumn(min_value=1, max_value=120, step=1)}, key="plano_ed")
    c1, c2 = st.columns(2)
    if c1.button("Salvar plano", type="primary"):
        for _, r in ed.iterrows():
            o = S["plan"].setdefault(r["id"], {})
            o["ativo"] = bool(r["Ativo"])
            base = D.EXERCICIOS[r["id"]]
            if base["tipo"] == "tempo":
                if pd.notna(r["Duração (min)"]):
                    o["duracao"] = int(r["Duração (min)"])
            else:
                o["series"], o["descanso"] = int(r["Séries"]), int(r["Descanso (s)"])
                o["reps"] = str(r["Repetições"]).strip()[:12] or base["reps"]
        salvar()
        st.success("Plano atualizado.")
    if c2.button("Restaurar valores iniciais"):
        S["plan"] = {}
        st.session_state.pop("plano_ed", None)
        salvar()
        st.rerun()

    st.markdown("### Agenda semanal")
    cols = st.columns(2)
    for n, d in enumerate([1, 2, 3, 4, 5, 6, 0]):
        ks = list(D.TREINOS)
        atual = S["schedule"].get(str(d), "OFF")
        v = cols[n % 2].selectbox(D.DIAS_SEMANA[d], ks, index=ks.index(atual) if atual in ks else ks.index("OFF"),
                                  format_func=lambda k: D.TREINOS[k]["nome"], key=f"ag{d}")
        if v != atual:
            S["schedule"][str(d)] = v
            salvar()

    st.markdown("### Lembretes")
    st.info("Os lembretes aparecem no Início quando o app é aberto. Para notificações no celular é preciso a versão nativa.")
    Rm = S["reminders"]
    hora = st.time_input("Horário do lembrete de treino", datetime.strptime(Rm["hora"], "%H:%M").time())
    dias = st.multiselect("Dias da semana", [1, 2, 3, 4, 5, 6, 0], default=Rm["dias"], format_func=lambda d: D.DIAS_CURTOS[d])
    flags = {k: st.checkbox(lbl, Rm[k], key="rm_" + k) for k, lbl in [("treino", "Lembrete para iniciar o treino"), ("sessao", "Lembrete para registrar a sessão"),
                                                                         ("peso", "Lembrete para atualizar o peso"), ("resumo", "Resumo semanal"), ("recuperacao", "Avisos de recuperação")]}
    novo = {"hora": hora.strftime("%H:%M"), "dias": sorted(dias), **flags}
    if novo != {k: Rm[k] for k in novo}:
        Rm.update(novo)
        salvar()

    st.markdown("### Fotos offline")
    st.caption(f"As fotos vêm do Free Exercise DB pela internet. Para usar sem internet, baixe uma vez (cerca de 3 MB) para {PASTA_FOTOS}.")
    if st.button("Baixar fotos"):
        PASTA_FOTOS.mkdir(parents=True, exist_ok=True)
        falhas = 0
        barra = st.progress(0.0)
        pastas = sorted(set(D.FOTOS.values()))
        for n, pasta in enumerate(pastas):
            for i in (0, 1):
                destino = PASTA_FOTOS / f"{pasta}_{i}.jpg"
                if destino.exists():
                    continue
                try:
                    urllib.request.urlretrieve(f"{D.FOTO_URL_BASE}{pasta}/{i}.jpg", destino)
                except OSError:
                    falhas += 1
            barra.progress((n + 1) / len(pastas))
        st.success("Fotos baixadas." if not falhas else f"Concluído com {falhas} falha(s). Verifique a internet e tente de novo.")

    st.markdown("### Cópia de segurança")
    dados_json = json.dumps(S, ensure_ascii=False, indent=1)
    st.download_button("Baixar cópia (.json)", dados_json.encode("utf-8"), file_name=f"foco-leve-{t}.json", mime="application/json")
    up = st.file_uploader("Restaurar a partir de uma cópia (.json do app Python ou da versão web)", type=["json", "txt"])
    if up is not None and st.button("Restaurar dados"):
        try:
            st.session_state.S = A.importar_json(up.getvalue().decode("utf-8"))
            salvar()
            st.success("Dados restaurados.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    if st.session_state.get("conf_reset"):
        st.warning("Isso apaga todos os registros deste computador.")
        c1, c2 = st.columns(2)
        if c1.button("Apagar tudo"):
            st.session_state.S = R.padrao()
            st.session_state.conf_reset = False
            salvar()
            st.rerun()
        if c2.button("Cancelar"):
            st.session_state.conf_reset = False
            st.rerun()
    elif st.button("Apagar todos os dados"):
        st.session_state.conf_reset = True
        st.rerun()

    st.markdown("### Base científica e fontes")
    for txt, url in D.FONTES:
        st.markdown(f"- {txt} [link]({url})")


# ------------------------------------------------------------------ roteamento
{"Início": tela_inicio, "Treinos": tela_treinos, "Evolução": tela_evolucao, "Hábitos": tela_habitos, "Perfil": tela_perfil}[aba]()
