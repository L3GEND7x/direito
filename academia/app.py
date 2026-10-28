"""FOCO LEVE — Treino e Emagrecimento (versão Python / Streamlit).

Executar:  streamlit run app.py
No celular: streamlit run app.py --server.address 0.0.0.0  e abra http://IP-DO-COMPUTADOR:8501
"""
from __future__ import annotations

import hashlib
import html
import importlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# No Streamlit Cloud, uma atualização do repositório nem sempre reinicia o processo: este arquivo roda na versão
# nova, mas os módulos do app importados antes continuam na versão antiga (e falta o que foi acrescentado neles).
# Antes de importá-los, recarrega os que mudaram no disco — na ordem das dependências.
MODULOS_DO_APP = ("foco_leve.dados", "foco_leve.regras", "foco_leve.plano", "foco_leve.evolucao",
                  "foco_leve.armazenamento", "foco_leve.ia_vision", "foco_leve.ia_safety", "foco_leve.ia_context",
                  "foco_leve.ia_storage", "foco_leve.ia_service", "ui", "personal_ai")
_cascata = False  # depois de recarregar um módulo, recarrega também os seguintes (podem depender dele)
for _nome in MODULOS_DO_APP:
    _mod = sys.modules.get(_nome)
    if _mod is None:
        continue  # ainda não importado: o import abaixo já lê a versão do disco
    try:
        _mtime = Path(_mod.__file__).stat().st_mtime
    except (OSError, TypeError):
        continue
    if _cascata or getattr(_mod, "_fl_mtime", None) != _mtime:  # mudou, ou veio de uma versão anterior deste arquivo
        _mod = importlib.reload(_mod)
        _mod._fl_mtime = _mtime
        _cascata = True

import personal_ai
import ui
from foco_leve import armazenamento as A
from foco_leve import dados as D
from foco_leve import evolucao as E
from foco_leve import plano as P
from foco_leve import regras as R
from foco_leve.regras import br, brx, fmt_d, fmt_dy, num, ok

for _mod in (sys.modules[n] for n in MODULOS_DO_APP if n in sys.modules):  # carregados agora: marca a versão do disco
    if not hasattr(_mod, "_fl_mtime"):
        _mod._fl_mtime = Path(_mod.__file__).stat().st_mtime

st.set_page_config(page_title="Foco Leve", page_icon="💪", layout="centered")

PASTA_FOTOS = A.CAMINHO_PADRAO.parent / "fotos"

st.markdown(ui.tema_css(), unsafe_allow_html=True)
components.html(ui.AJUSTES_PAGINA, height=0)


# ------------------------------------------------------------------ conta e estado
def abrir_loja():
    """Supabase se houver credenciais em Secrets ou variáveis de ambiente; SQLite só no modo local de desenvolvimento.

    Lido a cada execução, sem cache: Secrets salvos com o app já no ar valem na próxima recarga da página, sem
    reiniciar. O cliente só guarda a URL e a chave pública; o token de cada pessoa fica em st.session_state.
    Devolve (loja ou None, motivo para mostrar quando não houver banco). O motivo nunca repete valores dos Secrets."""
    segredos, motivo = {}, ""
    try:
        # load_if_toml_exists não exibe o aviso "No secrets found" quando não há arquivo (uso local)
        if st.secrets.load_if_toml_exists():
            if "supabase" in st.secrets:
                segredos = {"supabase": dict(st.secrets["supabase"])}
                faltam = [k for k in ("url", "anon_key") if not segredos["supabase"].get(k)]
                if faltam:
                    motivo = "Nos Secrets, a seção [supabase] está sem: " + ", ".join(faltam) + "."
            else:
                motivo = "Os Secrets foram encontrados, mas sem a seção [supabase] (com url e anon_key)."
    except Exception as e:  # noqa: BLE001 - arquivo de Secrets malformado
        linha = re.search(r"line (\d+)", str(e))
        motivo = ("Os Secrets do app têm um erro de formato" + (f" na linha {linha.group(1)}" if linha else "")
                  + ". Confira as aspas retas (\") e os nomes [supabase], url e anon_key.")
    try:
        loja = A.configurar(segredos)
    except ValueError as e:  # chave secreta configurada no lugar da pública
        return None, str(e)
    return loja, ("" if loja else motivo)


def endereco_do_app() -> str | None:
    """Para onde o link de recuperação deve voltar: site_url dos Secrets, FOCO_LEVE_SITE_URL ou esta visita."""
    try:
        if st.secrets.load_if_toml_exists() and st.secrets.get("supabase", {}).get("site_url"):
            return str(st.secrets["supabase"]["site_url"])
    except Exception:  # noqa: BLE001
        pass
    if os.environ.get("FOCO_LEVE_SITE_URL"):
        return os.environ["FOCO_LEVE_SITE_URL"]
    host = (st.context.headers.get("Host") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9.-]+(:\d+)?", host):
        return None  # sem endereço confiável: o Supabase usa a Site URL configurada
    return ("http://" if host.startswith(("localhost", "127.0.0.1")) else "https://") + host


LOJA, ERRO_CONFIG = abrir_loja()
VALIDAR_A_CADA = 300  # segundos entre confirmações da sessão no servidor de autenticação


def html_topo(titulo: str, sobre: str) -> None:
    st.markdown(ui.cabecalho(titulo, sobre), unsafe_allow_html=True)


def nota_banco() -> str:
    if LOJA.tipo == "supabase":
        return "Seus dados ficam na sua conta, em um banco de dados persistente (Supabase)."
    return ("Modo local de desenvolvimento: os dados ficam neste computador, separados por conta. "
            "Baixe a cópia de segurança com frequência.")


def tela_configuracao_pendente() -> None:
    """Sem banco configurado o app não abre dados pessoais (nada de SQLite compartilhado no servidor público)."""
    html_topo("Foco Leve", "Treino e emagrecimento")
    st.error(ERRO_CONFIG or "O banco de dados ainda não foi configurado, por isso o acesso às contas está desativado.")
    st.markdown("Quem administra o app precisa informar a URL e a chave pública do Supabase em **Settings → Secrets** "
                "do Streamlit Community Cloud (veja `academia/.streamlit/secrets.toml.example` e o README). "
                "Para testar no computador, rode com `FOCO_LEVE_MODO_LOCAL=1`.")


def tela_entrada() -> None:
    """Login e cadastro. Nenhum dado pessoal é lido ou gravado antes de saber de quem é."""
    html_topo("Entrar", "Treino e emagrecimento")
    st.caption(nota_banco())
    falhas = st.session_state.get("falhas_login", [])
    falhas = [x for x in falhas if time.time() - x < 60]
    st.session_state.falhas_login = falhas
    bloqueado = len(falhas) >= 5
    if bloqueado:
        st.error("Muitas tentativas seguidas. Aguarde 1 minuto e tente de novo.")
    abas = st.tabs(["Entrar", "Criar conta"] + (["Esqueci a senha"] if LOJA.recuperacao else []))
    aba_entrar, aba_criar = abas[:2]
    with aba_entrar, st.form("entrar"):
        email = st.text_input("E-mail", key="login_email", autocomplete="email")
        senha = st.text_input("Senha", type="password", key="login_senha", autocomplete="current-password")
        if st.form_submit_button("Entrar", type="primary", use_container_width=True, disabled=bloqueado):
            with st.spinner("Entrando…"):
                try:
                    st.session_state.usuario = LOJA.entrar(email, senha)
                except (A.ErroAutenticacao, A.ErroArmazenamento) as e:
                    st.session_state.falhas_login = falhas + [time.time()]
                    st.error(str(e))
                    return
            st.session_state.validado_em = time.time()
            st.rerun()
    with aba_criar, st.form("criar"):
        email = st.text_input("E-mail", key="novo_email", autocomplete="email")
        senha = st.text_input(f"Senha (mínimo {A.SENHA_MIN} caracteres)", type="password", key="novo_senha",
                              autocomplete="new-password")
        senha2 = st.text_input("Repita a senha", type="password", key="novo_senha2", autocomplete="new-password")
        if st.form_submit_button("Criar conta", type="primary", use_container_width=True, disabled=bloqueado):
            if senha != senha2:
                st.error("As senhas não conferem.")
                return
            with st.spinner("Criando a conta…"):
                try:
                    st.session_state.usuario = LOJA.criar_conta(email, senha)
                except (A.ErroAutenticacao, A.ErroArmazenamento) as e:
                    st.error(str(e))
                    return
            st.session_state.validado_em = time.time()
            st.rerun()
    if LOJA.recuperacao:
        with abas[2]:
            tela_recuperacao(bloqueado)
    if LOJA.tipo == "supabase":
        st.caption("Sua senha é guardada e conferida pelo serviço de autenticação do Supabase; o app não a armazena.")
    else:
        st.caption("Modo local: a senha não é guardada em texto, só um resumo criptográfico (PBKDF2).")


def tela_recuperacao(bloqueado: bool) -> None:
    """Pedido do e-mail de recuperação. O link do e-mail traz a pessoa de volta para escolher a nova senha."""
    with st.form("recuperar"):
        st.caption("Enviaremos um link para o seu e-mail. Abra o link e escolha a nova senha. "
                   "Se o e-mail tiver conta, a mensagem chega em alguns minutos (confira também o spam).")
        email = st.text_input("E-mail da conta", key="rec_email", autocomplete="email")
        if st.form_submit_button("Enviar link", type="primary", use_container_width=True, disabled=bloqueado):
            try:
                LOJA.enviar_recuperacao(email, endereco_do_app())
            except (A.ErroAutenticacao, A.ErroArmazenamento) as e:
                st.error(str(e))
            else:
                st.success("Pedido enviado. Abra o link do e-mail em até 1 hora.")
    with st.expander("Recebi um código numérico no e-mail"):
        with st.form("redefinir"):
            email = st.text_input("E-mail da conta", key="red_email", autocomplete="email")
            codigo = st.text_input("Código recebido", key="red_codigo", autocomplete="one-time-code")
            nova = st.text_input(f"Nova senha (mínimo {A.SENHA_MIN} caracteres)", type="password", key="red_senha",
                                 autocomplete="new-password")
            if st.form_submit_button("Trocar a senha e entrar", use_container_width=True, disabled=bloqueado):
                with st.spinner("Conferindo o código…"):
                    try:
                        st.session_state.usuario = LOJA.redefinir_senha(email, codigo, nova)
                    except (A.ErroAutenticacao, A.ErroArmazenamento) as e:
                        st.session_state.falhas_login = st.session_state.get("falhas_login", []) + [time.time()]
                        st.error(str(e))
                        return
                st.session_state.validado_em = time.time()
                st.rerun()


def retorno_do_link() -> None:
    """Chegada pelo link do e-mail (?rec=…&code=…): troca o código por uma sessão no servidor e limpa a URL."""
    q = st.query_params
    if not {"rec", "code", "error_description"} & set(q.keys()):
        return
    chave, codigo, erro = q.get("rec", ""), q.get("code", ""), q.get("error_description", "")
    st.query_params.clear()  # o código não fica na barra de endereço nem no histórico
    if erro or not codigo or not chave:
        st.session_state.aviso_login = "Este link de recuperação venceu ou já foi usado. Peça um novo e-mail."
        return
    try:
        st.session_state.recuperando = LOJA.abrir_link_recuperacao(chave, codigo)
    except (A.ErroAutenticacao, A.ErroArmazenamento) as e:
        st.session_state.aviso_login = str(e)


def tela_nova_senha() -> None:
    u = st.session_state.recuperando
    html_topo("Nova senha", u.get("email", ""))
    with st.form("nova_senha"):
        nova = st.text_input(f"Nova senha (mínimo {A.SENHA_MIN} caracteres)", type="password", key="ns_senha",
                             autocomplete="new-password")
        nova2 = st.text_input("Repita a nova senha", type="password", key="ns_senha2", autocomplete="new-password")
        if st.form_submit_button("Salvar a nova senha e entrar", type="primary", use_container_width=True):
            if nova != nova2:
                st.error("As senhas não conferem.")
                return
            try:
                LOJA.definir_senha(u, nova)
            except (A.ErroAutenticacao, A.ErroArmazenamento) as e:
                st.error(str(e))
                return
            st.session_state.usuario = st.session_state.pop("recuperando")
            st.session_state.validado_em = time.time()
            st.rerun()
    if st.button("Cancelar", use_container_width=True):
        del st.session_state["recuperando"]
        st.rerun()


def sair() -> None:
    u = st.session_state.get("usuario")
    if u:
        LOJA.sair(u)
    for k in list(st.session_state.keys()):
        if k not in ("falhas_login",):
            del st.session_state[k]


def falha_banco(e: Exception) -> None:
    html_topo("Sem conexão", "Não foi possível falar com o banco de dados")
    st.error(str(e))
    c1, c2 = st.columns(2)
    if c1.button("Tentar de novo", type="primary", use_container_width=True):
        st.rerun()
    if c2.button("Sair da conta", use_container_width=True):
        sair()
        st.rerun()
    st.stop()


def estado() -> dict:
    """Estado da conta. Se outra aba ou aparelho salvou depois, recarrega do banco antes de desenhar a tela:
    como cada ação salva na hora, esta sessão não tem nada pendente nesse momento."""
    u = st.session_state.usuario
    try:
        if time.time() - st.session_state.get("validado_em", 0) > VALIDAR_A_CADA:
            LOJA.validar(u)  # a identidade vem do servidor de autenticação, nunca da URL ou do navegador
            st.session_state.validado_em = time.time()
        v = LOJA.versao(u)
        if "S" not in st.session_state or (st.session_state.get("versao") != v and not st.session_state.get("pendente")):
            st.session_state.S, st.session_state.versao = LOJA.carregar_com_versao(u)
            if P.sincronizar_pesagem_inicial(st.session_state.S):
                try:  # corrige e grava já; se outra aba salvou no meio, a correção roda de novo na próxima carga
                    st.session_state.versao = LOJA.salvar(u, st.session_state.S, st.session_state.versao)
                except A.Conflito:
                    st.session_state.pop("S", None)
                    st.rerun()
            if not st.session_state.S.get("semente"):
                # rotação própria da conta na escolha dos exercícios (estável: vem do identificador da conta)
                st.session_state.S["semente"] = int(hashlib.sha256(str(u["id"]).encode()).hexdigest()[:8], 16) % 9973
    except A.ErroAutenticacao as e:
        sair()
        st.session_state.aviso_login = str(e)
        st.rerun()
    except A.ErroArmazenamento as e:
        if "S" not in st.session_state:
            falha_banco(e)
        st.warning("Sem conexão com o banco: mostrando os últimos dados carregados. O que você alterar agora "
                   "será enviado quando a conexão voltar.")
    return st.session_state.S


def salvar() -> None:
    """Grava só se ninguém salvou no meio; senão descarta esta ação e recarrega (nunca apaga o que a outra aba gravou)."""
    u = st.session_state.usuario
    try:
        st.session_state.versao = LOJA.salvar(u, st.session_state.S, st.session_state.get("versao", 0))
        st.session_state.pendente = False
    except A.Conflito:
        st.session_state.S, st.session_state.versao = LOJA.carregar_com_versao(u)
        st.session_state.pendente = False
        st.session_state.aviso = ("alerta", "Dados atualizados em outra aba",
                                  "O app foi aberto em outra aba ou aparelho e salvou antes. Os dados foram recarregados: "
                                  "repita a última ação, se ela não aparecer.")
        st.rerun()
    except A.ErroAutenticacao as e:
        sair()
        st.session_state.aviso_login = str(e)
        st.rerun()
    except A.ErroArmazenamento as e:
        # mantém a alteração nesta tela e tenta de novo na próxima ação (a versão esperada continua a mesma)
        st.session_state.pendente = True
        st.session_state.aviso = ("erro", "Alteração ainda não salva", str(e))


if LOJA is None:
    with st.container():
        tela_configuracao_pendente()
    st.stop()

if not st.session_state.get("usuario"):
    retorno_do_link()
    if st.session_state.get("recuperando"):
        with st.container():
            tela_nova_senha()
        st.stop()
    if st.session_state.get("aviso_login"):
        st.warning(st.session_state.pop("aviso_login"))
    with st.container():  # bloco próprio: o formulário de login não é reaproveitado pela tela seguinte
        tela_entrada()
    st.stop()

if st.session_state.get("pendente"):
    st.warning("Há uma alteração ainda não salva por falta de conexão.")
    if st.button("Tentar salvar agora", type="primary"):
        salvar()
        st.rerun()

S = estado()
R.definir_fuso(S["profile"].get("fuso"))
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
    """Início e fim do movimento lado a lado (também no celular, onde colunas do Streamlit empilhariam)."""
    pasta = D.FOTOS.get(ex_id)
    if not pasta:
        st.caption("Sem foto para este exercício.")
        return
    if (PASTA_FOTOS / f"{pasta}_0.jpg").exists():  # fotos baixadas para uso sem internet
        c1, c2 = st.columns(2)
        c1.image(foto(ex_id, 0), caption="Início", use_container_width=True)
        c2.image(foto(ex_id, 1), caption="Fim", use_container_width=True)
        return
    nome = html.escape(R.nome_ex(ex_id))
    html_md("<div class='fl-fotos'>" + "".join(
        f"<figure><img src='{D.FOTO_URL_BASE}{pasta}/{i}.jpg' alt='{nome}: {r.lower()} do movimento' loading='lazy'>"
        f"<figcaption>{r}</figcaption></figure>" for i, r in ((0, "Início"), (1, "Fim"))) + "</div>")


def capa(ex_ids, chip: str, titulo: str, texto: str = "", ficha=()) -> None:
    """Capa com foto de fundo, no estilo do modelo (foto do primeiro exercício que tiver imagem)."""
    pasta = next((D.FOTOS[i] for i in ex_ids if D.FOTOS.get(i)), None)
    fundo = "linear-gradient(180deg,rgba(0,0,0,.05) 0%,rgba(0,0,0,.55) 48%,rgba(0,0,0,.94) 100%)"
    if pasta:
        fundo += f",url('{D.FOTO_URL_BASE}{pasta}/0.jpg')"
    linhas = "".join(f"<div><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>" for k, v in ficha)
    st.markdown(f"<div class='fl-hero' style=\"background-image:{fundo}\"><span class='fl-chip'>{html.escape(chip)}</span>"
                f"<div class='fl-hero-tit'>{html.escape(titulo)}</div>" + (f"<div class='fl-texto'>{html.escape(texto)}</div>" if texto else "")
                + (f"<div class='fl-ficha'>{linhas}</div>" if linhas else "") + "</div>", unsafe_allow_html=True)


def cartoes(itens) -> None:
    """Grade de indicadores: (rótulo, valor, nota opcional, destaque)."""
    html_md(ui.grade(itens))


def html_md(conteudo: str) -> None:
    st.markdown(conteudo, unsafe_allow_html=True)


def cabecalho(titulo: str, sobre: str = "") -> None:
    html_md(ui.cabecalho(titulo, sobre))


def data_extensa(d: str) -> str:
    x = R.pd(d)
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
             "novembro", "dezembro"]
    return f"{D.DIAS_SEMANA[R.dia_js(d)]}, {x.day} de {meses[x.month - 1]}"


def prescricao(e: dict) -> str:
    if e["tipo"] == "tempo":
        return f"{e['duracao']} min"
    return f"{e['series']} × {e['reps']}" + (" (sem carga)" if e.get("semCarga") else "") + f" · descanso {e['descanso']} s"


def prescricao_html(e: dict) -> str:
    if e["tipo"] == "tempo":
        return f"<span class='fl-presc'>{e['duracao']} min <span>· {html.escape(e['grupo'])}</span></span>"
    extra = " (sem carga)" if e.get("semCarga") else ""
    return (f"<span class='fl-presc'>{e['series']} × {html.escape(str(e['reps']))}{extra} "
            f"<span>· descanso {e['descanso']} s · {html.escape(e['grupo'])}</span></span>")


def como_executar(e: dict, ex_id: str) -> None:
    """Fotos, passos e alertas: recolhidos para não poluir a tela durante o treino."""
    with st.expander("Como executar"):
        mostrar_fotos(ex_id)
        st.caption("Músculos: " + e["musculos"])
        for n, passo in enumerate(e["instrucoes"], 1):
            st.markdown(f"{n}. {passo}")
        for a in e["alertas"]:
            st.caption(":material/warning: " + a)


def cartao_exercicio(ex_id: str, com_rec: bool, presc: dict | None = None) -> None:
    e = {**R.get_ex(S, ex_id), **(presc or {})}
    livre, msg = R.status_ex(S, ex_id)
    with st.container(border=True):
        st.markdown(f"#### {e['nome']}")
        html_md(prescricao_html(e))
        if not livre:
            st.error(msg)
        elif com_rec:
            html_md(f"<div class='fl-rec'>{html.escape(R.recomendacao(S, ex_id))}</div>")
        como_executar(e, ex_id)


def cronometro(fim_ms: int, total_s: int = 0, proximo: str = "") -> None:
    """Descanso entre séries: contagem regressiva com barra, vibra no fim (quando o aparelho permite)."""
    components.html(f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',Roboto,system-ui,sans-serif;background:#1c1c1f;border:1px solid rgba(240,54,74,.45);color:#f5f5f7;border-radius:18px;padding:12px 18px 14px">
<div style="display:flex;justify-content:space-between;align-items:baseline">
<span style="font-size:13px;color:#a1a1a6;font-weight:600;letter-spacing:.04em;text-transform:uppercase">Descanso</span>
<b id="t" style="font-size:30px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums">0:00</b></div>
<div style="height:6px;background:#2a2a2e;border-radius:99px;margin-top:8px;overflow:hidden"><div id="b" style="height:100%;width:100%;background:#f0364a;border-radius:99px;transition:width .25s linear"></div></div>
<div style="font-size:12px;color:#a1a1a6;margin-top:8px">{html.escape(proximo)}</div></div>
<script>
const fim={fim_ms}, tot={max(1, total_s)};
function f(){{const s=Math.ceil((fim-Date.now())/1000);const el=document.getElementById('t');
document.getElementById('b').style.width=Math.max(0,Math.min(100,s/tot*100))+'%';
if(s<=0){{el.textContent='Pronto';el.style.color='#30d158';try{{navigator.vibrate&&navigator.vibrate(200)}}catch(e){{}}return;}}
el.textContent=Math.floor(s/60)+':'+String(s%60).padStart(2,'0');setTimeout(f,250);}}f();
</script>""", height=104)


def cronometro_sessao(inicio_ms: int, plano_min: int | None) -> None:
    """Relógio da sessão que anda sozinho no navegador, sem recarregar o app."""
    components.html(f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',Roboto,system-ui,sans-serif;display:flex;justify-content:space-between;align-items:center;color:#f5f5f7;padding:2px 2px">
<span style="font-size:13px;color:#a1a1a6">Tempo de treino{f" · plano ≈ {plano_min} min" if plano_min else ""}</span>
<b id="t" style="font-size:28px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums">0:00</b></div>
<script>
const ini={inicio_ms};
function f(){{const s=Math.max(0,Math.floor((Date.now()-ini)/1000));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;
document.getElementById('t').textContent=(h?h+':'+String(m).padStart(2,'0'):m)+':'+String(x).padStart(2,'0');setTimeout(f,500);}}f();
</script>""", height=44)


def texto_etapas(pl: dict) -> str:
    cardio = next((it for it in pl["itens"] if "duracao" in it and D.EXERCICIOS[it["id"]].get("cardio")), None)
    partes = []
    for nome, mins in pl["etapas"].items():
        if not mins:
            continue
        extra = f" ({R.nome_ex(cardio['id'])})" if nome == "Cardio" and cardio else ""
        partes.append(f"{nome} {mins} min{extra}")
    return " · ".join(partes)


CAMPOS_PERFIL = {"idade": ("Idade (anos)", 10, 100), "altura": ("Altura (cm)", 120, 230),
                 "pesoInicial": ("Peso inicial (kg)", 30, 300), "pesoMeta": ("Peso desejado (kg)", 30, 300),
                 "dias": ("Dias por semana", 1, 7), "tempoMax": ("Tempo máximo por sessão (min)", 30, 180)}
NIVEIS = ["Iniciante", "Intermediário", "Avançado"]
TEMPOS = [45, 60, 75, 90, 105, 120, 150]


def validar_perfil(textos: dict) -> tuple[dict, list[str]]:
    """Converte e confere os campos numéricos do perfil; devolve (valores, erros)."""
    erros, novos = [], {}
    for k, txt in textos.items():
        lbl, lo, hi = CAMPOS_PERFIL[k]
        v = num(txt)
        if not ok(v) or not lo <= v <= hi:
            erros.append(f"{lbl} deve ficar entre {lo} e {hi}.")
        else:
            novos[k] = int(round(v)) if k in ("idade", "dias", "tempoMax") else round(v, 1)
    return novos, erros


def editar_dados() -> None:
    """Edição rápida no Início: muda o perfil e recalcula o plano futuro, sem tocar no histórico."""
    p = S["profile"]
    with st.expander(":material/edit: Editar meus dados e recalcular o plano"):
        with st.form("dados_inicio"):
            # uma linha de colunas por par de campos: no celular a ordem continua lógica
            c1, c2 = st.columns(2)
            peso_hoje = c1.text_input("Peso de hoje (kg, opcional)", placeholder="Ex.: 113,4")
            meta = c2.text_input("Peso desejado (kg)", brx(p["pesoMeta"]))
            c1, c2 = st.columns(2)
            ini = c1.text_input("Peso inicial (kg)", brx(p["pesoInicial"]))
            alt = c2.text_input("Altura (cm)", brx(p["altura"]))
            c1, c2 = st.columns(2)
            idade = c1.text_input("Idade (anos)", brx(p["idade"]))
            nivel_atual = next((n for n in NIVEIS if n.lower()[:5] == str(p.get("nivel") or "").lower()[:5]), "Iniciante")
            nivel = c2.selectbox("Nível de experiência", NIVEIS, index=NIVEIS.index(nivel_atual))
            c1, c2 = st.columns(2)
            dias = c1.selectbox("Dias de treino por semana", list(range(1, 8)), index=max(0, min(6, int(p["dias"]) - 1)))
            tempos = sorted(set(TEMPOS) | {int(p.get("tempoMax") or 90)})
            tempo = c2.selectbox("Tempo máximo por treino (min)", tempos, index=tempos.index(int(p.get("tempoMax") or 90)))
            lim = st.text_area("Limitações, dores e restrições", p.get("limitacao", ""),
                               placeholder="Ex.: dor no joelho direito ao agachar; hérnia lombar")
            st.caption("O plano usa estes dados para escolher exercícios, séries, cardio e duração. Os treinos já registrados não mudam.")
            if st.form_submit_button("Salvar e recalcular", type="primary"):
                novos, erros = validar_perfil({"pesoMeta": meta, "pesoInicial": ini, "altura": alt, "idade": idade})
                pv = num(peso_hoje)
                if peso_hoje.strip() and (not ok(pv) or not 30 <= pv <= 300):
                    erros.append("O peso de hoje deve ficar entre 30 e 300 kg.")
                if erros:
                    st.error(" ".join(erros))
                    return
                novos.update({"dias": int(dias), "tempoMax": int(tempo), "nivel": nivel, "limitacao": lim.strip(), "confirmado": True})
                agenda_antes = dict(S["schedule"])
                P.atualizar_perfil(S, novos)
                if peso_hoje.strip():
                    S["weights"] = [x for x in S["weights"] if x["date"] != t]
                    S["weights"].append({"id": R.novo_id(), "date": t, "peso": round(pv, 1), "cintura": None,
                                         "cond": "Registrado no Início", "obs": ""})
                salvar()
                pl = P.plano_do_dia(S, t)
                msg = f"Hoje: {pl['nome']}" + (f", ≈ {pl['total']} min ({texto_etapas(pl)})." if pl["wk"] != "OFF" else ".")
                if S["schedule"] != agenda_antes:
                    msg += f" Agenda refeita para {dias} dia(s) por semana."
                st.session_state.aviso = ("ok", "Plano recalculado", msg + " O histórico foi mantido.")
                st.rerun()


# ------------------------------------------------------------------ cabeçalho e navegação
ABAS = ["Início", "Treinos", "Personal IA", "Evolução", "Hábitos", "Perfil"]
ICONES = {"Início": ":material/home:", "Treinos": ":material/fitness_center:", "Personal IA": ":material/smart_toy:",
          "Evolução": ":material/monitoring:", "Hábitos": ":material/water_drop:", "Perfil": ":material/person:"}
if "aba" not in st.session_state:
    st.session_state.aba = "Início"
if st.session_state.get("_ir"):
    st.session_state.aba = st.session_state.pop("_ir")
# barra de abas fixa no rodapé (posicionada pelo tema.css)
aba = st.radio("Seção", ABAS, horizontal=True, key="aba", label_visibility="collapsed",
               format_func=lambda k: f"{ICONES[k]} {k}")
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
        partes = []
        if R.sintomas(S):
            partes.append("Há dor, inchaço ou dificuldade para caminhar registrados: os exercícios de pernas ficam bloqueados enquanto isso.")
        if R.lesao_em_recuperacao(S):
            partes.append("Há lesão muscular em recuperação (ou não se sabe): as cargas não progridem e cada treino pede confirmação.")
        return ("alerta", "Avaliação profissional recomendada", " ".join(partes))
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
def form_dados_iniciais() -> None:
    """Passo 1 do primeiro acesso: os valores aparecem como exemplo até a pessoa confirmar os dela."""
    p = S["profile"]
    with st.form("dados_iniciais"):
        st.markdown("#### Passo 1 de 2 · Seus dados")
        st.caption("Os campos vêm com valores de exemplo. Troque pelos seus: o plano de 20 semanas é calculado a partir deles.")
        nome = st.text_input("Nome (opcional)", p.get("nome", ""))
        c1, c2 = st.columns(2)
        peso = c1.text_input("Peso atual (kg)", placeholder=f"exemplo: {brx(p['pesoInicial'])}")
        meta = c2.text_input("Peso desejado (kg)", placeholder=f"exemplo: {brx(p['pesoMeta'])}")
        c1, c2 = st.columns(2)
        alt = c1.text_input("Altura (cm)", placeholder=f"exemplo: {brx(p['altura'])}")
        idade = c2.text_input("Idade (anos)", placeholder=f"exemplo: {brx(p['idade'])}")
        c1, c2 = st.columns(2)
        dias = c1.selectbox("Dias de treino por semana", list(range(1, 8)), index=4)
        tempo = c2.selectbox("Tempo máximo por treino (min)", TEMPOS, index=TEMPOS.index(90))
        c1, c2 = st.columns(2)
        nivel = c1.selectbox("Nível de experiência", NIVEIS)
        fuso = c2.selectbox("Fuso horário", list(R.FUSOS), index=list(R.FUSOS).index(p.get("fuso") or R.FUSO_PADRAO),
                            format_func=lambda k: R.FUSOS[k][0])
        lim = st.text_area("Limitações, dores e restrições (se houver)", p.get("limitacao", ""),
                           placeholder="Ex.: dor no joelho direito ao agachar")
        if st.form_submit_button("Continuar", type="primary", use_container_width=True):
            novos, erros = validar_perfil({"pesoInicial": peso, "pesoMeta": meta, "altura": alt, "idade": idade})
            if erros:
                st.error("Preencha seus dados: " + " ".join(erros))
                return
            novos.update({"nome": nome.strip(), "dias": int(dias), "tempoMax": int(tempo), "nivel": nivel, "fuso": fuso,
                          "limitacao": lim.strip(), "confirmado": True})
            P.atualizar_perfil(S, novos)
            S["schedule"] = P.agenda_para(int(dias))
            if not any(w["date"] == t for w in S["weights"]):
                S["weights"].append({"id": R.novo_id(), "date": t, "peso": novos["pesoInicial"], "cintura": None,
                                     "cond": P.PESAGEM_INICIAL, "obs": ""})
            salvar()
            st.rerun()


def tela_primeiro_acesso() -> None:
    p = S["profile"]
    capa(["agachamento_goblet"], "PRIMEIRO PASSO", "Olá, vamos montar o seu plano",
         "Dois passos rápidos: seus dados e algumas perguntas de segurança. "
         "Elas não substituem avaliação médica nem a orientação do profissional de educação física.")
    if not p.get("confirmado"):
        form_dados_iniciais()
        return
    cartoes([("Peso inicial", f"{br(p['pesoInicial'])} kg", None, True), ("Meta", f"{br(p['pesoMeta'])} kg", "sem prazo", True),
             ("Idade", f"{p['idade']} anos", None, False), ("Altura", f"{br(p['altura'], 0)} cm", None, False)])
    st.subheader("Passo 2 de 2 · Avaliação de segurança")
    st.caption(f"IMC inicial estimado: {br(R.imc(S, p['pesoInicial']))} kg/m² (triagem, não é diagnóstico). "
               f"Diferença até a meta: {br(p['pesoInicial'] - p['pesoMeta'])} kg, sem data obrigatória.")
    form_avaliacao()


def saudacao() -> str:
    h = R.agora().hour
    return "Bom dia" if 5 <= h < 12 else ("Boa tarde" if 12 <= h < 18 else "Boa noite")


def grupos_do_treino(pl: dict) -> str:
    grupos = []
    for it in pl["itens"]:
        g = D.EXERCICIOS[it["id"]]["grupo"]
        if g not in grupos and g not in ("Cardio", "Recuperação"):
            grupos.append(g)
    return " · ".join(grupos)


def minutos_cardio(pl: dict) -> int:
    return int(pl["etapas"].get("Cardio") or 0)


def tela_inicio() -> None:
    if not S["assess"]["done"]:
        cabecalho("Bem-vindo", data_extensa(t))
        # bloco próprio: evita que o formulário seja reaproveitado pelo do check-in após salvar
        with st.container():
            tela_primeiro_acesso()
        return
    p = S["profile"]
    nome = (p.get("nome") or "").split()
    cabecalho(f"{saudacao()}{', ' + nome[0] if nome else ''}", data_extensa(t))
    if R.seguranca(S) == "urgent":
        aviso_urgente()
    lem = R.lembretes(S, R.agora().strftime("%H:%M"))
    if lem:
        st.info("  \n".join(lem))

    # treino de hoje: a ação principal da tela
    wk = R.treino_do_dia(S, t)
    pl = P.plano_do_dia(S, t)
    if wk == "OFF":
        capa(["esteira_caminhada"], f"SEMANA {pl['semana']} DE {D.SEMANAS_PLANO}", "Descanso",
             "Hoje é dia de recuperação. Não é preciso compensar treinos.")
    else:
        ficha = (("Duração", f"≈ {pl['total']} min"), ("Cardio", f"{minutos_cardio(pl)} min"),
                 ("Exercícios", str(len(pl["itens"]))))
        capa([it["id"] for it in pl["itens"]] or ["esteira_caminhada"],
             f"HOJE · SEMANA {pl['semana']} DE {D.SEMANAS_PLANO}", pl["nome"], grupos_do_treino(pl) or pl["obj"], ficha)
        if S["active"]:
            st.button("Continuar treino", type="primary", on_click=ir, args=("Treinos",), use_container_width=True,
                      key="acao_principal", icon=":material/play_arrow:")
        elif R.feito_em(S, t):
            st.success("Treino de hoje concluído. Bom trabalho: agora é recuperar bem.")
        elif st.button("Iniciar treino", type="primary", use_container_width=True, key="acao_principal",
                       icon=":material/play_arrow:"):
            tentar_iniciar(wk)
        st.caption(texto_etapas(pl))

    # progresso: semana do plano, consistência e cardio
    ws = R.inicio_semana(t)
    dias = E.estado_dos_dias(S, ws)
    feitos = sum(1 for d in dias if d["estado"] == "feito")
    planejados = sum(1 for d in dias if d["estado"] != "descanso")
    cm = R.energia_semana(S, ws)["cardioMin"]
    cons = E.consistencia(S)
    fi, fase = P.fase_da_semana(pl["semana"])
    with st.container(border=True):
        html_md(f"<p class='fl-rotulo'>Semana {pl['semana']} de {D.SEMANAS_PLANO} · Fase {fi + 1} — {html.escape(fase['n'])}</p>")
        html_md(ui.aneis([
            ("Treinos na semana", f"{feitos}/{planejados}", "feitos", feitos / planejados if planejados else 0, "var(--accent)"),
            ("Cardio na semana", br(cm, 0), "de 150 min", cm / 150, "#f5f5f7"),
            ("Plano de 20 semanas", str(cons["aprovadas"]), "semanas concluídas", cons["aprovadas"] / D.SEMANAS_PLANO, "#8e8e93"),
        ]) + ui.semana(dias))

    # peso
    cw, meta = R.peso_atual(S), float(p["pesoMeta"])
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Peso atual" if S["weights"] else "Peso inicial", f"{br(cw)} kg")
        c2.metric("Meta", f"{br(meta)} kg")
        c3.metric("Faltam", f"{br(max(0, cw - meta))} kg")
        if len(S["weights"]) >= 2:
            grafico_peso("diario", 150)
        else:
            html_md(ui.vazio("Gráfico de peso", "Registre pelo menos duas pesagens (em Evolução ou em “Editar meus dados”) "
                                                "para ver a curva aqui."))
        i = R.imc(S, cw)
        st.caption(f"IMC {br(i)} kg/m² ({R.imc_categoria(i)}): indicador de triagem, não é diagnóstico.")

    # última sessão
    u = E.ultima_sessao(S)
    html_md("<div class='fl-secao'>Última sessão</div>")
    if u:
        html_md(ui.grade([
            (f"{fmt_d(u['data'])} · {'concluída' if u['status'] == 'concluida' else 'interrompida'}", u["nome"].split(" — ")[0], None, False),
            ("Duração", f"{br(u['minutos'] or 0, 0)} min", f"{u['feitos']} de {u['total']} exercícios", False),
            ("Cardio", f"{u['cardio']} min", f"volume {br(u['volume'] or 0, 0)} kg", False)]))
    else:
        html_md(ui.vazio("Nenhuma sessão ainda", "Quando você concluir o primeiro treino, o resumo aparece aqui."))

    # bem-estar e dados
    html_md("<div class='fl-secao'>Hoje</div>")
    checkin()
    rv = R.recuperacao(S)
    st.caption(f"Recuperação: {rv['txt']} — {rv['detalhe']}")
    editar_dados()


def historico_cargas() -> None:
    linhas = [{"Exercício": c["nome"], "Primeira (kg)": brx(c["primeira"]), "Última (kg)": brx(c["ultima"]),
               "Variação": ("+" if c["variacao"] > 0 else "") + brx(c["variacao"]) + " kg", "Desde": fmt_d(c["data_primeira"]),
               "Registros": c["registros"]} for c in E.comparacao_cargas(S)]
    if linhas:
        st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)
    else:
        html_md(ui.vazio("Sem cargas registradas", "As cargas aparecem aqui depois do primeiro treino com carga anotada."))


def tentar_iniciar(wk: str) -> None:
    if R.feito_em(S, t):
        st.session_state.aviso = ("info", "Treino de hoje já registrado", "O próximo treino fica para amanhã. Não é preciso compensar.")
    elif R.seguranca(S) == "urgent":
        st.session_state.aviso = ("erro", "Treinos bloqueados", "Há sinal de alerta registrado. Procure atendimento médico.")
    elif R.seguranca(S) == "pending":
        st.session_state.aviso = ("alerta", "Avaliação pendente", "Conclua a avaliação de segurança antes do primeiro treino.")
    elif R.seguranca(S) in ("caution", "noclear") and wk != "REC" and not st.session_state.get("ciente"):
        st.session_state.dia_sel = t  # a confirmação aparece no cartão de hoje
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
    if st.session_state.get("resumo"):
        tela_resumo(st.session_state.resumo)
        return
    if R.alerta_vermelho(S):
        aviso_urgente()
    if S["active"]:
        tela_sessao()
        return
    ws = R.inicio_semana(t)
    if "dia_sel" not in st.session_state:
        st.session_state.dia_sel = t
    cabecalho("Treinos", f"Semana de {fmt_d(ws)} a {fmt_d(R.add_dias(ws, 6))}")
    # faixa de dias rolável; a chave inclui o dia escolhido para o app poder mudar a seleção sozinho
    dias = R.dias_da_semana(ws)

    def rotulo_dia(d):
        k = R.treino_do_dia(S, d)
        return f"{D.DIAS_CURTOS[R.dia_js(d)]} {R.pd(d).day}\n{D.TREINOS[k]['curto']}{' ✓' if R.feito_em(S, d) else ''}"
    sel = st.radio("Dia da semana", dias, index=dias.index(st.session_state.dia_sel) if st.session_state.dia_sel in dias else 0,
                   format_func=rotulo_dia, horizontal=True, key="dia_" + st.session_state.dia_sel, label_visibility="collapsed")
    if sel != st.session_state.dia_sel:
        st.session_state.dia_sel = sel
        st.rerun()
    sp = P.semana_do_programa(S)
    pw = sp["semana"]
    fi, fase = P.fase_da_semana(pw)
    d = st.session_state.dia_sel
    wk = R.treino_do_dia(S, d)
    pl = P.plano_do_dia(S, d, pw)
    ficha = (("Duração", f"≈ {pl['total']} min"), ("Cardio", f"{minutos_cardio(pl)} min"),
             ("Exercícios", str(len(pl["itens"])))) if wk != "OFF" else ()
    capa([it["id"] for it in pl["itens"]] or ["esteira_caminhada"],
         f"{D.DIAS_SEMANA[R.dia_js(d)].upper()} · {fmt_d(d)}" + (" · HOJE" if d == t else ""), pl["nome"],
         grupos_do_treino(pl) or pl["obj"], ficha)
    if wk != "OFF" and pl["etapas"]:
        st.caption(texto_etapas(pl))
    for x in pl["avisos"]:
        st.caption(":material/info: " + x)
    if pl["bloqueados"]:
        st.warning("**Fora do plano por segurança:**  \n" + "  \n".join(f"{R.nome_ex(x)}: {m}" for x, m in pl["bloqueados"]))
    with st.expander(":material/tune: Como este treino foi montado para você"):
        st.markdown("\n".join(f"- {x}" for x in P.resumo_personalizacao(S, pw)))
        st.caption("A escolha dos exercícios também segue uma ordem própria da sua conta, que muda a cada semana. "
                   "Mudou peso, nível, dias, tempo ou limitações? Atualize no Perfil ou em “Editar meus dados” no Início.")
    with st.container():
        if d == t:
            if st.session_state.get("pre_inicio"):
                aviso("alerta", "Antes de começar", "Há dor, inchaço, lesão em recuperação ou liberação pendente registrados. Faça só o que não causa dor e interrompa ao primeiro sintoma.")
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
                if wk != "OFF" and st.button("Iniciar este treino", type="primary", use_container_width=True,
                                             key="acao_principal", icon=":material/play_arrow:"):
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
    if wk not in ("OFF", "REC") and d >= t:
        editar_treino(pl)
    for it in pl["itens"]:
        cartao_exercicio(it["id"], d == t, it)
    html_md("<div class='fl-secao'>Plano de 20 semanas</div>")
    with st.container(border=True):
        html_md(f"<p class='fl-rotulo'>Semana {pw} de {D.SEMANAS_PLANO} · Fase {fi + 1} — {html.escape(fase['n'])}</p>")
        st.caption(f"Objetivo da semana: {P.objetivo_da_semana(pw)} · Esforço: {fase['rpe']}")
        if sp["concluido"]:
            st.success("Plano de 20 semanas concluído. Gere o relatório em Evolução e combine a próxima etapa com o profissional.")
        elif sp["historico"]:
            ult = sp["historico"][-1]
            (st.caption if ult["aprovada"] else st.warning)(f"Semana anterior (semana {ult['semana']}): {ult['motivo']}")
        with st.expander("Como a semana do plano avança"):
            st.markdown("A semana só avança quando a anterior foi bem executada e bem recuperada:\n"
                        "- pelo menos 60% dos treinos planejados concluídos;\n"
                        "- nenhuma sessão interrompida por sintoma nem dor moderada ou forte;\n"
                        "- nenhum sinal de alerta, inchaço ou dor forte no check-in;\n"
                        "- nenhuma sessão com recuperação ruim.\n\n"
                        "Se algo disso falhar, a mesma semana se repete. Terminar o calendário não basta.")
        with st.expander("Ver o plano das 20 semanas"):
            ver_plano(pw, ws)


def ver_plano(pw: int, ws: str) -> None:
    sem = st.selectbox("Semana", list(range(1, D.SEMANAS_PLANO + 1)), index=pw - 1, key="ver_sem",
                       format_func=lambda n: f"Semana {n} · Fase {P.fase_da_semana(n)[0] + 1} — {P.fase_da_semana(n)[1]['n']}"
                       + (" (atual)" if n == pw else ""))
    fase = P.fase_da_semana(sem)[1]
    st.caption(f"{fase['texto']} Objetivo: {P.objetivo_da_semana(sem)}")
    if sem > pw:
        st.caption("Prévia com os dados de hoje: o plano é recalculado se peso, dias, tempo ou limitações mudarem.")
    for pl in P.plano_da_semana(S, sem, ws):
        dia = D.DIAS_SEMANA[R.dia_js(pl["data"])]
        if pl["wk"] == "OFF":
            st.markdown(f"**{dia}** — Descanso")
            continue
        st.markdown(f"**{dia}** — {pl['nome']} · ≈ {pl['total']} min  \n<small>{texto_etapas(pl)}</small>",
                    unsafe_allow_html=True)
        linhas = [{"Exercício": R.nome_ex(it["id"]),
                   "Prescrição": f"{it['duracao']} min" if "duracao" in it else f"{it['series']} × {it['reps']}",
                   "Descanso": f"{it['descanso']} s" if it.get("descanso") else "—"} for it in pl["itens"]]
        st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)


def editar_treino(pl: dict) -> None:
    """Troca, inclui ou remove exercícios só deste treino e desta semana; o cardio continua obrigatório."""
    chave = f"{pl['semana']}|{pl['wk']}"
    forca = [it for it in pl["itens"] if "duracao" not in it]
    cardio = next((it["id"] for it in pl["itens"] if "duracao" in it and D.EXERCICIOS[it["id"]].get("cardio")), None)
    with st.expander(":material/edit: Editar exercícios deste treino" + (" (personalizado)" if pl["personalizado"] else "")):
        atuais = [it["id"] for it in forca]
        opcoes = [x for x, e in D.EXERCICIOS.items() if e["tipo"] == "carga" and e["grupo"] != "Recuperação"
                  and (x in atuais or not P.motivo_bloqueio(S, x, pl["semana"]))]
        with st.form("ed_" + chave):
            sel = st.multiselect("Exercícios de musculação, na ordem do treino", opcoes, default=[it["id"] for it in forca],
                                 format_func=R.nome_ex)
            mod = None
            if cardio:
                cardios = [c for c in D.CARDIO_TODOS if not P.motivo_bloqueio(S, c, pl["semana"])] or [cardio]
                mod = st.selectbox("Modalidade de cardio (mínimo de 30 min)", cardios,
                                   index=cardios.index(cardio) if cardio in cardios else 0, format_func=R.nome_ex)
            st.caption("Séries, repetições e descanso dos exercícios atuais (exercícios novos entram com a prescrição da fase):")
            df = pd.DataFrame([{"id": it["id"], "Exercício": R.nome_ex(it["id"]), "Séries": int(it["series"]),
                                "Repetições": str(it["reps"]), "Descanso (s)": int(it["descanso"])} for it in forca])
            ed = st.data_editor(df, hide_index=True, use_container_width=True, disabled=["id", "Exercício"],
                                column_config={"id": None,
                                               "Séries": st.column_config.NumberColumn(min_value=1, max_value=10, step=1),
                                               "Descanso (s)": st.column_config.NumberColumn(min_value=0, max_value=600, step=5)},
                                key="ed_tab_" + chave) if len(df) else None
            c1, c2 = st.columns(2)
            salvar_ed = c1.form_submit_button("Salvar este treino", type="primary")
            restaurar = c2.form_submit_button("Voltar ao plano original")
        if salvar_ed:
            if not sel:
                st.error("Escolha pelo menos um exercício de musculação.")
                return
            presc = {}
            if ed is not None:
                for _, r in ed.iterrows():
                    reps = str(r["Repetições"]).strip()[:12]
                    if pd.isna(r["Séries"]) or pd.isna(r["Descanso (s)"]) or not reps:
                        st.error(f"Preencha séries, repetições e descanso de {r['Exercício']}.")
                        return
                    if r["id"] in sel:  # guarda só o que continua no treino
                        presc[r["id"]] = {"series": int(r["Séries"]), "reps": reps, "descanso": int(r["Descanso (s)"])}
            S.setdefault("ajustes", {})[chave] = {"ex": sel, "cardio": mod, "presc": presc}
            salvar()
            st.session_state.aviso = ("ok", "Treino atualizado", f"Vale para {pl['nome']} na semana {pl['semana']}. O resto do plano não muda.")
            st.rerun()
        if restaurar:
            S.get("ajustes", {}).pop(chave, None)
            salvar()
            st.rerun()


def cardio_feito(a: dict) -> float:
    return sum(num(x.get("min")) for e in a["ex"] if D.EXERCICIOS.get(e["id"], {}).get("cardio")
               for x in e["sets"] if x.get("done") and ok(num(x.get("min"))))


def tela_sessao() -> None:
    a = S["active"]
    if R.garantir_uids(a):  # sessões começadas antes desta versão
        salvar()
    W = D.TREINOS[a["workout"]]
    n = len(a["ex"])
    feitos = sum(1 for e in a["ex"] if e.get("done"))
    atual = next((i for i, e in enumerate(a["ex"]) if not e.get("done")), None)
    semana = a.get("semana") or P.semana_do_programa(S)["semana"]
    fi, fase = P.fase_da_semana(semana)
    cabecalho(W["nome"].split(" — ")[0], f"Em andamento · semana {semana} de {D.SEMANAS_PLANO} · fase {fi + 1}")
    with st.container(border=True):
        cronometro_sessao(a["startedAt"], int(a.get("planoMin") or 0) or None)
        st.progress(feitos / n if n else 0.0, text=f"{feitos} de {n} exercícios")
        plano_cardio = (a.get("etapas") or {}).get("Cardio")
        html_md(ui.grade([("Volume", f"{br(R.volume(a), 0)} kg", "carga × repetições", False),
                          ("Cardio", f"{br(cardio_feito(a), 0)} min", f"de {plano_cardio} min" if plano_cardio else None, False),
                          ("Esforço-alvo", fase["rpe"].replace(" de 10", ""), "de 10, sem falha", False)]))
    if st.session_state.get("descanso_ate", 0) > time.time() * 1000:
        cronometro(st.session_state.descanso_ate, st.session_state.get("descanso_total", 0),
                   st.session_state.get("descanso_proximo", ""))
    if a["workout"] not in ("REC", "OFF"):
        etapas = a.get("etapas") or {}
        with st.expander(f"Aquecimento ({etapas.get('Aquecimento', 10)} min) e volta à calma ({etapas.get('Volta à calma', 5)} min)"):
            st.markdown("**Aquecimento:** 5 minutos de esteira ou bicicleta em ritmo leve e 1 série leve de 10 a 12 repetições "
                        "do primeiro exercício.  \n**Ordem:** músculos grandes antes dos pequenos, multiarticulares antes dos isolados.  \n"
                        "**Volta à calma:** cardio bem leve e respiração no final.")
    for i, se in enumerate(a["ex"]):
        exercicio_sessao(i, se, i == atual)
    html_md("<div style='height:8px'></div>")
    if st.session_state.get("finalizar"):
        form_finalizar(a)
    elif st.session_state.get("sintoma"):
        form_sintoma()
    else:
        if st.button("Finalizar treino", type="primary", use_container_width=True, key="acao_principal",
                     icon=":material/flag:"):
            st.session_state.finalizar = True
            st.rerun()
        c1, c2 = st.columns(2)
        if c1.button("Senti um sintoma", use_container_width=True, icon=":material/healing:"):
            st.session_state.sintoma = True
            st.rerun()
        if st.session_state.get("conf_desc"):
            if c2.button("Confirmar descarte", use_container_width=True):
                S["active"] = None
                st.session_state.conf_desc = False
                salvar()
                st.session_state.aviso = ("info", "Sessão descartada", "Nada foi registrado.")
                st.rerun()
        elif c2.button("Descartar", use_container_width=True, icon=":material/delete:"):
            st.session_state.conf_desc = True
            st.rerun()


def form_finalizar(a: dict) -> None:
    with st.form("fim"):
        st.markdown("#### Como foi o treino?")
        sens = st.radio("Sensação geral", ["bem", "cansado", "exausto", "dor"], index=None, horizontal=True,
                        format_func={"bem": "Bem", "cansado": "Cansado, mas bem", "exausto": "Muito cansado", "dor": "Com dor"}.get)
        mins = st.number_input("Duração (minutos)", 1, 240, max(1, min(180, round((time.time() * 1000 - a["startedAt"]) / 60000))))
        rpe_s = st.slider("Esforço da sessão inteira (0 = repouso, 10 = máximo)", 0, 10, 6)
        fad = st.select_slider("Fadiga ao terminar (1 = descansado, 5 = exausto)", [1, 2, 3, 4, 5], value=3)
        recup = st.radio("Como está a recuperação dos últimos treinos?", ["boa", "regular", "ruim"], horizontal=True,
                         format_func=str.capitalize)
        obs = st.text_area("Observações (opcional)")
        salvar_bt = st.form_submit_button("Salvar treino", type="primary", use_container_width=True)
        voltar = st.form_submit_button("Voltar ao treino", use_container_width=True)
    if salvar_bt:
        if not sens:
            st.error("Escolha como você se sentiu para salvar.")
            return
        cardio = cardio_feito(a)
        rec = R.finalizar_sessao(S, sens, mins, obs, rpe_sessao=rpe_s, fadiga=fad, recuperacao=recup)
        st.session_state.finalizar = False
        st.session_state.descanso_ate = 0
        salvar()
        pr = rec.pop("_recordes")
        st.session_state.resumo = {"nome": D.TREINOS[rec["workout"]]["nome"], "feitos": sum(1 for e in rec["ex"] if e.get("done")),
                                   "total": len(rec["ex"]), "pct": rec["pct"], "minutos": rec["minutes"], "volume": rec["volume"],
                                   "kcal": rec["kcal"], "cardio": cardio, "recordes": pr, "dor": sens == "dor"}
        st.rerun()
    if voltar:
        st.session_state.finalizar = False
        st.rerun()


def form_sintoma() -> None:
    with st.form("sint"):
        st.markdown("#### Qual sintoma?")
        marc = [k for k, lbl in [("joelho", "Dor em articulação que piora com o exercício"), ("inchaco", "Inchaço em articulação"),
                                 ("apoio", "Dificuldade para apoiar a perna"), ("peito", "Dor ou aperto no peito"),
                                 ("ar", "Falta de ar desproporcional ao esforço"), ("tontura", "Tontura ou mal-estar"),
                                 ("outro", "Outra dor ou desconforto")] if st.checkbox(lbl, key="s_" + k)]
        parar = st.form_submit_button("Interromper sessão", type="primary", use_container_width=True)
        voltar = st.form_submit_button("Voltar ao treino", use_container_width=True)
    if parar:
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
    if voltar:
        st.session_state.sintoma = False
        st.rerun()


def tela_resumo(r: dict) -> None:
    """Tela de conclusão com o resumo do que foi registrado."""
    cabecalho("Resumo", data_extensa(t))
    with st.container(border=True):
        html_md(ui.fim_de_sessao("Treino concluído", f"{r['nome']} · sessão salva no histórico"))
        html_md(ui.grade([("Duração", f"{r['minutos']} min", None, False),
                          ("Exercícios", f"{r['feitos']}/{r['total']}", f"{br(r['pct'], 0)}% concluído", False),
                          ("Cardio", f"{br(r['cardio'], 0)} min", None, False),
                          ("Volume", f"{br(r['volume'], 0)} kg", "carga × repetições", False),
                          ("Gasto", f"≈ {br(r['kcal'], 0)}", "kcal (estimativa)", False),
                          ("Recordes", str(len(r["recordes"])), "de carga", bool(r["recordes"]))]))
        if r["recordes"]:
            st.success("Novo recorde de carga: " + "; ".join(r["recordes"]) + ".")
        if r["dor"]:
            st.warning("Sessão salva com registro de dor: procure avaliação antes do próximo treino que possa agravar a dor.")
        st.caption("A semana do plano avança quando ela termina com pelo menos 60% dos treinos e sem sinais de alerta.")
        if st.button("Concluir", type="primary", use_container_width=True, key="acao_principal"):
            st.session_state.pop("resumo", None)
            st.session_state._ir = "Início"
            st.rerun()


def concluir_serie(i: int, j: int, k: str, e: dict, se: dict) -> None:
    desc = R.marcar_serie(S, i, j, True)
    st.session_state.descanso_ate = time.time() * 1000 + desc * 1000 if desc else 0
    st.session_state.descanso_total = desc
    restantes = [x for x in se["sets"] if not x["done"]]
    st.session_state.descanso_proximo = (f"Próximo: série {j + 2} de {e['nome']}" if restantes else "")
    salvar()
    if se.get("done"):
        st.toast(f"{e['nome']} concluído", icon=":material/check_circle:")
    else:
        st.toast(f"Série {j + 1} concluída · descanso de {desc} s", icon=":material/timer:")
    st.rerun()


def exercicio_sessao(i: int, se: dict, aberto: bool) -> None:
    e = R.ex_sessao(S, se)
    sid = se["uid"]
    feitas = sum(1 for x in se["sets"] if x["done"])
    resumo = f"{e['duracao']} min" if e["tipo"] == "tempo" else f"{feitas}/{len(se['sets'])} séries"
    if se.get("done"):
        rotulo = f":material/check_circle: {e['nome']} · concluído"
    elif aberto:
        rotulo = f":material/play_circle: Agora: {e['nome']} · {resumo}"
    else:
        rotulo = f"{e['nome']} · {resumo}"
    with st.expander(rotulo, expanded=aberto):
        if not se.get("done"):
            mostrar_fotos(se["id"])  # demonstração do movimento logo no topo
        html_md(prescricao_html(e))
        if not se.get("done"):
            html_md(f"<div class='fl-rec'>{html.escape(R.recomendacao(S, se['id']))}</div>")
        if e["tipo"] == "tempo":
            bloco_cardio(i, se, e, sid)
        else:
            bloco_series(i, se, e, sid)
        detalhes_exercicio(i, se, e, sid)


def bloco_series(i: int, se: dict, e: dict, sid: str) -> None:
    proxima = next((j for j, x in enumerate(se["sets"]) if not x["done"]), None)
    ult = R.ultima_carga(S, se["id"])
    for j, sset in enumerate(se["sets"]):
        k = f"{sid}_{j}"
        if sset["done"]:
            carga = f"{sset.get('load')} kg × " if sset.get("load") and not e.get("semCarga") else ""
            html_md(f"<div class='fl-serie-ok'><i>✓</i>Série {j + 1}<span>{html.escape(carga + str(sset.get('reps') or ''))}"
                    f"{' reps' if sset.get('reps') else ''}</span></div>")
            html_md("<div style='height:6px'></div>")
        elif j == proxima:
            anterior = se["sets"][j - 1].get("load") if j > 0 else ""
            c1, c2 = st.columns(2)
            ld = ""
            if not e.get("semCarga"):
                ld = c1.text_input(f"Carga da série {j + 1} (kg)", sset.get("load") or anterior or "", key="l" + k,
                                   placeholder=f"última: {ult}" if ult else "kg")
            else:
                c1.caption("Sem carga")
            rp = c2.text_input(f"Repetições da série {j + 1}", sset.get("reps") or R.reps_alvo(e), key="r" + k)
            if st.button(f"Concluir série {j + 1}", type="primary", use_container_width=True, key=f"serie_ok_{k}",
                         icon=":material/check:"):
                vl, vr = num(ld), num(rp)
                if ld.strip() and (not ok(vl) or not 0 <= vl <= 500):
                    st.error("Carga inválida: use apenas números (ex.: 42,5).")
                    return
                if rp.strip() and (not ok(vr) or not 0 <= vr <= 200):
                    st.error("Repetições inválidas.")
                    return
                sset["load"], sset["reps"] = ld.strip(), rp.strip()
                concluir_serie(i, j, k, e, se)
        else:
            st.caption(f"Série {j + 1} · {e['reps']} repetições")
    if feitas := [j for j, x in enumerate(se["sets"]) if x["done"]]:
        if st.button("Desfazer última série", key=f"desfazer_{sid}", icon=":material/undo:"):
            R.marcar_serie(S, i, feitas[-1], False)
            st.session_state.descanso_ate = 0
            salvar()
            st.rerun()


def bloco_cardio(i: int, se: dict, e: dict, sid: str) -> None:
    sset = se["sets"][0]
    k = f"{sid}_0"
    if sset["done"]:
        html_md(f"<div class='fl-serie-ok'><i>✓</i>{html.escape(e['nome'])}<span>{html.escape(str(sset.get('min') or e['duracao']))} min</span></div>")
        if st.button("Desfazer", key=f"desfazer_{sid}", icon=":material/undo:"):
            R.marcar_serie(S, i, 0, False)
            salvar()
            st.rerun()
        return
    if e.get("cardio"):
        semana = S["active"].get("semana") or 1
        mods = [c for c in D.CARDIO_TODOS if c == se["id"] or not P.motivo_bloqueio(S, c, semana)]
        if se["id"] in mods and len(mods) > 1:
            nova = st.selectbox("Modalidade de cardio", mods, index=mods.index(se["id"]), format_func=R.nome_ex, key=f"mod{sid}")
            if nova != se["id"]:
                entrada = R.nova_entrada(S, nova, se.get("presc"))
                entrada["sets"][0]["min"] = sset.get("min", "")
                S["active"]["ex"][i] = entrada
                st.session_state.pop(f"mod{sid}", None)
                salvar()
                st.rerun()
        ops = D.INTENSIDADES[e["cardio"]]
        vals = [o[0] for o in ops]
        esc = st.selectbox("Intensidade (usada na estimativa de calorias)", vals,
                           index=vals.index(se.get("met")) if se.get("met") in vals else 0, format_func=dict(ops).get, key=f"met{sid}")
        if esc != se.get("met"):
            se["met"] = esc
            salvar()
    mn = st.text_input("Minutos feitos", sset.get("min") or str(e["duracao"]), key="m" + k)
    if st.button(f"Concluir {'cardio' if e.get('cardio') else 'exercício'}", type="primary", use_container_width=True,
                 key=f"serie_ok_{k}", icon=":material/check:"):
        v = num(mn)
        if mn.strip() and (not ok(v) or not 0 <= v <= 240):
            st.error("Minutos inválidos: use um número entre 0 e 240.")
            return
        sset["min"] = mn.strip()
        concluir_serie(i, 0, k, e, se)


def detalhes_exercicio(i: int, se: dict, e: dict, sid: str) -> None:
    semana = S["active"].get("semana") or 1
    # a troca só oferece o que o plano também aceitaria: limitações, proibidos e sintomas de hoje valem aqui também
    alts = [x for x in D.ALTERNATIVAS.get(se["id"], []) if x in D.EXERCICIOS and not P.motivo_bloqueio(S, x, semana)]
    if alts and not any(x["done"] for x in se["sets"]) and not e.get("cardio"):
        tr = st.selectbox("Aparelho ocupado? Trocar por", [""] + alts,
                          format_func=lambda x: "Manter este exercício" if not x else R.nome_ex(x), key=f"sw{sid}")
        if tr:
            S["active"]["ex"][i] = R.nova_entrada(S, tr, se.get("presc"))
            st.session_state.pop(f"sw{sid}", None)
            salvar()
            st.rerun()
    c1, c2 = st.columns(2)
    rpe_ops = [""] + [str(n) for n in range(1, 11)]
    rpe = c1.selectbox("Esforço percebido (1–10)", rpe_ops, index=rpe_ops.index(str(se.get("rpe") or "")), key=f"rpe{sid}",
                       format_func=lambda x: x or "—")
    dor_ops = ["nenhum", "leve", "moderado", "forte"]
    dor = c2.selectbox("Dor ou desconforto", dor_ops, index=dor_ops.index(se.get("painLevel") or "nenhum"),
                       format_func=str.capitalize, key=f"pl{sid}")
    if rpe != (se.get("rpe") or "") or dor != se.get("painLevel"):
        se["rpe"], se["painLevel"] = rpe, dor
        salvar()
    if dor in ("moderado", "forte"):
        st.error("**Pare este exercício.** Com dor moderada ou forte, interrompa. Se a dor for em uma articulação, no peito "
                 "ou vier com inchaço, use “Senti um sintoma”.")
    if dor != "nenhum" or se.get("pain"):
        txt = st.text_input("Onde e como foi o desconforto (opcional)", se.get("pain", ""), key=f"pt{sid}")
        if txt != se.get("pain", ""):
            se["pain"] = txt
            salvar()
    c1, c2 = st.columns(2)
    with c1.popover("Como executar", icon=":material/info:", use_container_width=True):
        if se.get("done"):
            mostrar_fotos(se["id"])
        st.caption("Músculos: " + e["musculos"])
        for n_, passo in enumerate(e["instrucoes"], 1):
            st.markdown(f"{n_}. {passo}")
        for al in e["alertas"]:
            st.caption(":material/warning: " + al)
    if not se.get("done") and c2.button("Marcar como concluído", key=f"exd{sid}", use_container_width=True,
                                        help="Para quando você fez o exercício sem registrar todas as séries"):
        se["done"] = True
        salvar()
        st.toast(f"{e['nome']} concluído", icon=":material/check_circle:")
        st.rerun()
    remover_exercicio(i, se, e, sid)


def remover_exercicio(i: int, se: dict, e: dict, sid: str) -> None:
    """Tira o exercício só desta sessão, com confirmação; o plano e o histórico não mudam."""
    chave = f"rm{sid}"
    if not st.session_state.get(chave):
        if st.button("Remover deste treino", key=f"rmb{sid}", icon=":material/delete:", use_container_width=True):
            st.session_state[chave] = True
            st.rerun()
        return
    feitas = sum(1 for x in se["sets"] if x["done"])
    st.warning(f"Remover **{e['nome']}** desta sessão?" + (f" As {feitas} série(s) já registradas dele serão descartadas." if feitas else "")
               + " O plano e os outros treinos não mudam.")
    c1, c2 = st.columns(2)
    if c1.button("Remover", key=f"rmok{sid}", type="primary", use_container_width=True):
        R.remover_exercicio_sessao(S, i)
        st.session_state.pop(chave, None)
        st.session_state.descanso_ate = 0
        salvar()
        st.toast(f"{e['nome']} removido do treino", icon=":material/delete:")
        st.rerun()
    if c2.button("Cancelar", key=f"rmno{sid}", use_container_width=True):
        st.session_state.pop(chave, None)
        st.rerun()


# ------------------------------------------------------------------ EVOLUÇÃO
# configuração comum dos gráficos: fundo transparente, eixos discretos e fonte do sistema
VEGA_CONFIG = {
    "background": None, "view": {"stroke": None},
    "font": "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, system-ui, sans-serif",
    "axis": {"labelColor": "#a1a1a6", "titleColor": "#a1a1a6", "gridColor": "rgba(255,255,255,0.07)",
             "domainColor": "rgba(255,255,255,0.12)", "tickColor": "rgba(255,255,255,0.12)", "labelFontSize": 11,
             "titleFontSize": 11, "titleFontWeight": 500},
    "legend": {"labelColor": "#a1a1a6", "titleColor": "#a1a1a6", "orient": "top", "labelFontSize": 11},
}


def grafico(df: pd.DataFrame, spec: dict) -> None:
    # especificação Vega-Lite direta: não depende do pacote altair, que não importa no Python 3.14
    st.vega_lite_chart(df, {**spec, "config": VEGA_CONFIG}, use_container_width=True, theme=None)


def grafico_peso(modo: str, altura: int = 240) -> None:
    dados = R.serie_peso(S, modo)
    if len(dados) < 2:
        html_md(ui.vazio("Gráfico de peso", "Registre pelo menos duas pesagens para ver a evolução."))
        return
    df = pd.DataFrame([{"ordem": n, "Data": l, "Peso (kg)": round(v, 1)} for n, (l, v) in enumerate(dados)])
    lo, hi = float(df["Peso (kg)"].min()), float(df["Peso (kg)"].max())
    meta = float(S["profile"]["pesoMeta"])
    mostra_meta = lo - meta <= 6  # a linha da meta só entra quando não achata a curva
    dominio = [min(lo, meta) - 1 if mostra_meta else lo - 1.5, hi + 1.5]
    camadas = [
        {"mark": {"type": "area", "color": {"x1": 1, "y1": 1, "x2": 1, "y2": 0, "gradient": "linear",
                                            "stops": [{"offset": 0, "color": "rgba(240,54,74,0)"},
                                                      {"offset": 1, "color": "rgba(240,54,74,0.22)"}]},
                  "interpolate": "monotone"},
         "encoding": {"y": {"field": "Peso (kg)", "type": "quantitative", "scale": {"domain": dominio}, "title": None}}},
        {"mark": {"type": "line", "color": "#f0364a", "strokeWidth": 2.5, "interpolate": "monotone",
                  "point": {"color": "#f0364a", "size": 36, "filled": True}},
         "encoding": {"y": {"field": "Peso (kg)", "type": "quantitative", "scale": {"domain": dominio}, "title": None},
                      "tooltip": [{"field": "Data", "type": "nominal"}, {"field": "Peso (kg)", "type": "quantitative"}]}},
    ]
    if mostra_meta:
        camadas.append({"mark": {"type": "rule", "color": "#a1a1a6", "strokeDash": [4, 4]}, "encoding": {"y": {"datum": meta}}})
    grafico(df, {"height": altura, "encoding": {"x": {"field": "Data", "type": "nominal", "sort": list(df["Data"]), "title": None,
                                                      "axis": {"labelAngle": 0, "labelOverlap": True}}},
                 "layer": camadas})
    if not mostra_meta:
        st.caption(f"Meta: {br(meta)} kg (fora da escala do gráfico para não achatar a curva).")


def grafico_barras(linhas: list[dict], y: str, titulo_y: str, ref: float | None = None, y2: str | None = None,
                   altura: int = 200) -> None:
    """Barras por semana; y2 desenha o planejado como barra de fundo; ref desenha uma linha de referência."""
    df = pd.DataFrame(linhas)
    camadas = []
    if y2:
        camadas.append({"mark": {"type": "bar", "color": "#2a2a2e", "cornerRadiusTopLeft": 5, "cornerRadiusTopRight": 5},
                        "encoding": {"y": {"field": y2, "type": "quantitative", "title": titulo_y}}})
    camadas.append({"mark": {"type": "bar", "color": "#f0364a", "cornerRadiusTopLeft": 5, "cornerRadiusTopRight": 5,
                             "width": {"band": 0.55}},
                    "encoding": {"y": {"field": y, "type": "quantitative", "title": titulo_y},
                                 "tooltip": [{"field": "Semana", "type": "nominal"}, {"field": y, "type": "quantitative"}]
                                 + ([{"field": y2, "type": "quantitative"}] if y2 else [])}})
    if ref:
        camadas.append({"mark": {"type": "rule", "color": "#a1a1a6", "strokeDash": [4, 4]}, "encoding": {"y": {"datum": ref}}})
    grafico(df, {"height": altura, "encoding": {"x": {"field": "Semana", "type": "nominal", "sort": list(df["Semana"]),
                                                      "title": None, "axis": {"labelAngle": 0}}},
                 "layer": camadas})


def tela_evolucao() -> None:
    cabecalho("Evolução", "Seus registros, sem estimativas inventadas")
    aba_plano, aba_peso, aba_treinos, aba_rel = st.tabs(["Plano", "Peso", "Treinos", "Relatório"])
    with aba_plano:
        evolucao_plano()
    with aba_peso:
        evolucao_peso()
    with aba_treinos:
        evolucao_treinos()
    with aba_rel:
        evolucao_relatorio()


def evolucao_plano() -> None:
    estados, atual = E.estados_20(S)
    fi, fase = P.fase_da_semana(atual)
    cons = E.consistencia(S)
    with st.container(border=True):
        html_md(f"<p class='fl-rotulo'>Linha do tempo · semana {atual} de {D.SEMANAS_PLANO}</p>")
        html_md(ui.linha_do_tempo(estados, [(f["n"], *f["semanas"]) for f in D.FASES_20], fi))
    html_md(ui.grade([
        ("Semanas concluídas", f"{cons['aprovadas']}/{D.SEMANAS_PLANO}", None, True),
        ("Sequência atual", str(cons["sequencia"]), "semanas seguidas", False),
        ("Aproveitamento", f"{br(cons['taxa'] * 100, 0)}%" if cons["taxa"] is not None else "—",
         f"de {cons['avaliadas']} semanas avaliadas" if cons["avaliadas"] else "nenhuma semana encerrada", False)]))
    html_md("<div class='fl-secao'>Meta desta semana</div>")
    with st.container(border=True):
        html_md(f"<p class='fl-rotulo'>Fase {fi + 1} — {html.escape(fase['n'])} · esforço {html.escape(fase['rpe'])}</p>"
                f"<p style='margin:0 0 8px'>{html.escape(P.objetivo_da_semana(atual))}</p>")
        html_md(ui.criterios(E.criterios_semana_atual(S)))
        st.caption("Com todos os itens em dia ao fim da semana, o plano avança para a semana seguinte.")


def evolucao_peso() -> None:
    p = S["profile"]
    cw, ini, meta = R.peso_atual(S), float(p["pesoInicial"]), float(p["pesoMeta"])
    ms = R.media_semana(S, R.inicio_semana(t))
    html_md(ui.grade([
        ("Atual" if S["weights"] else "Inicial", f"{br(cw)} kg", None, False),
        ("Desde o início", f"{'+' if cw - ini > 0 else ''}{br(cw - ini)} kg" if S["weights"] else "—",
         f"{'+' if cw > ini else ''}{br((cw - ini) / ini * 100)}%" if S["weights"] else None, False),
        ("Até a meta", f"{br(max(0, cw - meta))} kg", f"meta {br(meta)} kg", False),
        ("Média da semana", f"{br(ms)} kg" if ms is not None else "—", "2 ou mais pesagens", False)]))
    with st.container(border=True):
        modo = st.radio("Período do gráfico", ["diario", "semanal", "mensal"], horizontal=True,
                        format_func={"diario": "Diário", "semanal": "Semanal", "mensal": "Mensal"}.get)
        grafico_peso(modo)
        st.caption("Oscilações de um dia para o outro refletem água, alimentação e intestino, não ganho ou perda comprovada "
                   "de gordura. Compare médias semanais.")
    cmp = E.comparacao_peso(S)
    if cmp and cmp["registros"] >= 2:
        st.caption(f"Primeira pesagem: {br(cmp['primeira'])} kg em {fmt_dy(cmp['data_primeira'])} · última: {br(cmp['ultima'])} kg "
                   f"em {fmt_dy(cmp['data_ultima'])} · variação de {'+' if cmp['variacao'] > 0 else ''}{br(cmp['variacao'])} kg "
                   f"em {cmp['registros']} registros.")
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
    html_md("<div class='fl-secao'>Pesagens</div>")
    w = list(reversed(R.pesos_ordenados(S)))
    if not w:
        html_md(ui.vazio("Nenhuma pesagem registrada", "Use o formulário acima para registrar a primeira."))
    for x in w:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{br(x['peso'])} kg** · {fmt_dy(x['date'])}" + (f" · cintura {brx(x['cintura'])} cm" if ok(x.get("cintura")) else "") + f"  \n<small>{x.get('cond', '')}{' · ' + x['obs'] if x.get('obs') else ''}</small>", unsafe_allow_html=True)
        if c2.button("Excluir", key="dw" + x["id"]):
            S["weights"] = [y for y in S["weights"] if y["id"] != x["id"]]
            salvar()
            st.rerun()


def evolucao_treinos() -> None:
    sem = E.semanas_recentes(S, 8)
    linhas = [{"Semana": x["rotulo"], "Concluídos": x["feitos"], "Planejados": x["planejados"], "Cardio (min)": x["cardio"]}
              for x in sem]
    with st.container(border=True):
        html_md("<p class='fl-rotulo'>Frequência · últimas 8 semanas</p>")
        if any(x["feitos"] for x in sem):
            grafico_barras(linhas, "Concluídos", "Treinos", y2="Planejados")
            st.caption("Barra vermelha: treinos concluídos. Fundo cinza: treinos planejados na agenda.")
        else:
            html_md(ui.vazio("Sem treinos concluídos", "A frequência aparece aqui depois do primeiro treino salvo."))
    with st.container(border=True):
        html_md("<p class='fl-rotulo'>Cardio por semana · minutos</p>")
        if any(x["cardio"] for x in sem):
            grafico_barras(linhas, "Cardio (min)", "Minutos", ref=150)
            st.caption("Linha tracejada: 150 min, o mínimo semanal recomendado pela OMS.")
        else:
            html_md(ui.vazio("Sem cardio registrado", "Os minutos de cardio concluídos nos treinos aparecem aqui."))
    html_md("<div class='fl-secao'>Cargas: primeiro registro × último</div>")
    historico_cargas()
    html_md("<div class='fl-secao'>Histórico de treinos</div>")
    ss = sorted(S["sessions"], key=lambda s: -s.get("startedAt", 0))[:30]
    if not ss:
        html_md(ui.vazio("Nenhum treino registrado", "Os treinos salvos aparecem aqui, do mais recente para o mais antigo."))
    for s in ss:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{R.nome_treino(s['workout'])}** · {fmt_dy(s['date'])}  \n<small>{'Concluída' if s.get('status') == 'concluida' else 'Interrompida'} · {br(s.get('pct', 0), 0)}% · {br(s.get('minutes', 0), 0)} min"
                 + (f" · {br(s['volume'], 0)} kg de volume" if s.get("volume") else "") + (f" · ≈ {br(s['kcal'], 0)} kcal" if s.get("kcal") else "") + "</small>", unsafe_allow_html=True)
        if c2.button("Excluir", key="ds" + s["id"]):
            S["sessions"] = [y for y in S["sessions"] if y["id"] != s["id"]]
            salvar()
            st.rerun()




def evolucao_relatorio() -> None:
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


# ------------------------------------------------------------------ HÁBITOS
def tela_habitos() -> None:
    cabecalho("Hábitos", "Opcional · salva automaticamente")
    dsel = st.date_input("Dia", value=R.pd(t), max_value=R.pd(t), format="DD/MM/YYYY").isoformat()
    x = S["habits"].get(dsel, {})  # o dia só é gravado quando algo for preenchido
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
    vazio = {"agua": 0, "sono": None, "refeicoes": "", "obs": "", "fome": None, "saciedade": None, "energia": None}
    antes = {k: x.get(k, vazio[k]) for k in novo}
    if novo != antes:
        if novo == vazio:
            S["habits"].pop(dsel, None)
        else:
            S["habits"][dsel] = {**x, **novo}
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
TEXTO_CONVITE = "Estou usando o Foco Leve para organizar meus treinos e acompanhar minha evolução. Experimente:"


def compartilhar() -> None:
    """Convite para o app: só o link público, nunca dados da conta."""
    url = endereco_do_app()
    with st.container(border=True):
        html_md("<p class='fl-rotulo'>Convide alguém</p>")
        if not url:
            st.caption("O link do app ainda não está configurado (site_url em Secrets).")
            return
        components.html(ui.botao_compartilhar(url, TEXTO_CONVITE), height=82)
        st.link_button("Enviar pelo WhatsApp", "https://wa.me/?text=" + urllib.parse.quote(f"{TEXTO_CONVITE} {url}"),
                       icon=":material/chat:", use_container_width=True)
        st.caption("Ou copie o link:")
        st.code(url, language=None)
        st.caption("Só o link do app é compartilhado. Seus dados continuam visíveis apenas para você.")


def tela_perfil() -> None:
    p = S["profile"]
    cabecalho("Perfil", "Seus dados, segurança e preferências")
    with st.container(border=True):
        u = st.session_state.usuario
        html_md(f"<p class='fl-rotulo'>Conta</p><p style='margin:0'>{html.escape(u['email'])}</p>")
        st.caption(nota_banco())
        if st.button("Sair da conta", icon=":material/logout:", use_container_width=True):
            sair()
            st.rerun()
    compartilhar()
    with st.form("perfil"):
        nome = st.text_input("Nome (opcional)", p.get("nome", ""))
        c1, c2 = st.columns(2)
        vals = {}
        for n, (k, (lbl, lo, hi)) in enumerate(CAMPOS_PERFIL.items()):
            vals[k] = (c1 if n % 2 == 0 else c2).text_input(lbl, brx(p[k]))
        c1, c2 = st.columns(2)
        local = c1.text_input("Local de treino", p.get("local", ""))
        nivel_atual = next((n for n in NIVEIS if n.lower()[:5] == str(p.get("nivel") or "").lower()[:5]), "Iniciante")
        nivel = c2.selectbox("Nível de experiência", NIVEIS, index=NIVEIS.index(nivel_atual))
        obj = st.text_input("Objetivo", p.get("objetivo", ""))
        fuso = st.selectbox("Fuso horário (define o que é “hoje” no app)", list(R.FUSOS),
                            index=list(R.FUSOS).index(p.get("fuso") or R.FUSO_PADRAO), format_func=lambda k: R.FUSOS[k][0])
        lim = st.text_area("Limitações e contraindicações", p.get("limitacao", ""))
        if st.form_submit_button("Salvar perfil", type="primary"):
            novos, erros = validar_perfil(vals)
            if erros:
                st.error(" ".join(erros))
            else:
                novos.update({"nome": nome.strip(), "local": local.strip(), "nivel": nivel, "objetivo": obj.strip(), "fuso": fuso,
                              "confirmado": True,
                              "limitacao": lim.strip()})
                P.atualizar_perfil(S, novos)
                salvar()
                st.session_state.aviso = ("ok", "Perfil salvo", "O plano foi recalculado com os dados novos. O histórico foi mantido.")
                st.rerun()
    if S["weights"]:
        ult = R.pesos_ordenados(S)[-1]
        st.caption(f"Peso atual: {br(ult['peso'])} kg (última pesagem, em {fmt_dy(ult['date'])}). "
                   "Para registrar um peso novo, use Evolução ou “Editar meus dados” no Início; "
                   "mudar o peso inicial aqui corrige também a pesagem do primeiro acesso.")
    i0, i1 = R.imc(S, p["pesoInicial"]), R.imc(S, R.peso_atual(S))
    st.caption(f"IMC inicial: {br(i0)} kg/m² · IMC atual: {br(i1)} kg/m² ({R.imc_categoria(i1)}). Indicador de triagem, não é diagnóstico.")

    html_md("<div class='fl-secao'>Avaliação de segurança</div>")
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

    html_md("<div class='fl-secao'>Plano de exercícios</div>")
    st.caption("Desative um exercício para tirá-lo de todas as semanas, ou mude séries, repetições e descanso. "
               "Só o que você alterar substitui a prescrição da fase. O cardio é calculado pelo plano (mínimo de 30 min).")
    usados = []
    for vagas in D.MODELOS.values():
        for _, ops, _ in vagas:
            usados += [x for x in ops if x not in usados]
    for W in D.TREINOS.values():
        usados += [x for x in W["ex"] if x not in usados]
    usados = [x for x in usados if not D.EXERCICIOS[x].get("cardio")]
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
            base = D.EXERCICIOS[r["id"]]
            o = {}
            # grava só o que difere do padrão: o resto continua seguindo a fase do plano
            if not bool(r["Ativo"]):
                o["ativo"] = False
            if base["tipo"] == "tempo":
                if pd.notna(r["Duração (min)"]) and int(r["Duração (min)"]) != int(base.get("duracao") or 0):
                    o["duracao"] = int(r["Duração (min)"])
            else:
                if pd.notna(r["Séries"]) and int(r["Séries"]) != int(base["series"]):
                    o["series"] = int(r["Séries"])
                if pd.notna(r["Descanso (s)"]) and int(r["Descanso (s)"]) != int(base.get("descanso") or 0):
                    o["descanso"] = int(r["Descanso (s)"])
                reps = str(r["Repetições"]).strip()[:12]
                if reps and reps != str(base.get("reps")):
                    o["reps"] = reps
            if o:
                S["plan"][r["id"]] = o
            else:
                S["plan"].pop(r["id"], None)
        salvar()
        st.success("Plano atualizado.")
    if c2.button("Restaurar valores iniciais"):
        S["plan"] = {}
        st.session_state.pop("plano_ed", None)
        salvar()
        st.rerun()

    html_md("<div class='fl-secao'>Agenda semanal</div>")
    cols = st.columns(2)
    for n, d in enumerate([1, 2, 3, 4, 5, 6, 0]):
        ks = list(D.TREINOS)
        atual = S["schedule"].get(str(d), "OFF")
        v = cols[n % 2].selectbox(D.DIAS_SEMANA[d], ks, index=ks.index(atual) if atual in ks else ks.index("OFF"),
                                  format_func=lambda k: D.TREINOS[k]["nome"], key=f"ag{d}")
        if v != atual:
            S["schedule"][str(d)] = v
            salvar()

    html_md("<div class='fl-secao'>Lembretes</div>")
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

    html_md("<div class='fl-secao'>Fotos offline</div>")
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
                parcial = destino.with_suffix(".parcial")
                try:
                    # baixa para um arquivo temporário: uma queda no meio não deixa foto quebrada para sempre
                    urllib.request.urlretrieve(f"{D.FOTO_URL_BASE}{pasta}/{i}.jpg", parcial)
                    parcial.replace(destino)
                except OSError:
                    parcial.unlink(missing_ok=True)
                    falhas += 1
            barra.progress((n + 1) / len(pastas))
        st.success("Fotos baixadas." if not falhas else f"Concluído com {falhas} falha(s). Verifique a internet e tente de novo.")

    html_md("<div class='fl-secao'>Cópia de segurança</div>")
    dados_json = json.dumps({k: v for k, v in S.items() if not k.startswith("_")}, ensure_ascii=False, indent=1)
    st.download_button("Baixar cópia (.json)", dados_json.encode("utf-8"), file_name=f"foco-leve-{t}.json", mime="application/json")
    up = st.file_uploader("Restaurar a partir de uma cópia (.json do app Python ou da versão web)", type=["json", "txt"])
    if up is not None:
        st.warning("Restaurar **substitui todos os registros atuais** pelos da cópia. Baixe a cópia atual acima antes, se quiser guardá-la.")
        ciente = st.checkbox("Entendi que os registros atuais serão substituídos", key="ciente_restaurar")
        if st.button("Restaurar dados", disabled=not ciente):
            try:
                novo = A.importar_json(up.getvalue().decode("utf-8", errors="replace"))
            except ValueError as e:
                st.error(f"Não foi possível restaurar: {e}")
            else:
                descartados = novo.pop("_descartados", 0)
                st.session_state.S = novo
                salvar()
                st.session_state.aviso = ("ok", "Dados restaurados",
                                          f"{len(novo['sessions'])} treinos e {len(novo['weights'])} pesagens recuperados."
                                          + (f" {descartados} registro(s) malformado(s) foram ignorados." if descartados else ""))
                st.rerun()
    if st.session_state.get("conf_reset"):
        st.warning("Isso apaga todos os registros **desta conta**: treinos, pesagens, hábitos e perfil. "
                   "Baixe a cópia de segurança acima antes, se quiser guardá-los.")
        ciente = st.checkbox("Entendi que não dá para desfazer", key="ciente_apagar")
        c1, c2 = st.columns(2)
        if c1.button("Apagar tudo", type="primary", disabled=not ciente):
            try:
                LOJA.apagar(st.session_state.usuario)  # só a linha desta conta (garantido também pelo RLS)
            except A.ErroArmazenamento as e:
                st.error(str(e))
            else:
                st.session_state.S, st.session_state.versao = R.padrao(), 0
                st.session_state.conf_reset = False
                st.rerun()
        if c2.button("Cancelar"):
            st.session_state.conf_reset = False
            st.rerun()
    elif st.button("Apagar todos os dados"):
        st.session_state.conf_reset = True
        st.rerun()

    html_md("<div class='fl-secao'>Base científica e fontes</div>")
    for txt, url in D.FONTES:
        st.markdown(f"- {txt} [link]({url})")


# ------------------------------------------------------------------ roteamento
{"Início": tela_inicio, "Treinos": tela_treinos, "Evolução": tela_evolucao, "Hábitos": tela_habitos, "Perfil": tela_perfil,
 "Personal IA": lambda: personal_ai.tela(S, st.session_state.usuario, LOJA, salvar, t)}[aba]()
