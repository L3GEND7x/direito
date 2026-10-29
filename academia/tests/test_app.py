"""Interface Streamlit (executa o app sem navegador): conta, primeiro acesso, abas, treino, retomada e isolamento."""
import json
import os
import sqlite3
import tempfile
import time

import streamlit as st
from streamlit.testing.v1 import AppTest

os.environ["FOCO_LEVE_DB"] = os.path.join(tempfile.mkdtemp(), "teste.db")
os.environ["FOCO_LEVE_MODO_LOCAL"] = "1"
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_ANON_KEY", None)
APP = os.path.join(os.path.dirname(__file__), "..", "app.py")
ABAS = ["Início", "Treino", "Evolução", "Meu plano", "Perfil"]

from foco_leve import armazenamento as A  # noqa: E402 (depois de definir o banco de teste)
from foco_leve import regras as R  # noqa: E402


def abrir():
    """Uma aba nova do navegador (ou a mesma recarregada): sessão do Streamlit vazia."""
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    return at


def botao(at, rotulo):
    return [b for b in at.button if b.label == rotulo][0]


def campo(at, rotulo, chave=None):
    return [x for x in at.text_input if x.label == rotulo and (chave is None or x.key == chave)][0]


def criar_conta(at, email, senha="senha-segura-1"):
    campo(at, "E-mail", "novo_email").input(email)
    campo(at, "Senha (mínimo 8 caracteres)").input(senha)
    campo(at, "Repita a senha").input(senha)
    botao(at, "Criar conta").click().run()
    assert not at.exception and at.session_state["usuario"]["email"] == email
    return at


def entrar(at, email, senha="senha-segura-1"):
    campo(at, "E-mail", "login_email").input(email)
    campo(at, "Senha").input(senha)
    botao(at, "Entrar").click().run()
    return at


def primeiro_acesso(at, peso="112,5"):
    for rot, v in {"Peso atual (kg)": peso, "Peso desejado (kg)": "90", "Altura (cm)": "178", "Idade (anos)": "30"}.items():
        campo(at, rot).input(v)
    botao(at, "Continuar").click().run()
    for k, v in {"as_dor": "nao", "as_inchaco": "nao", "as_caminhar": "nao", "as_diag": "nao", "as_liberacao": "sim",
                 "as_lesao": "nao"}.items():
        at.radio(key=k).set_value(v)
    botao(at, "Salvar avaliação").click().run()
    assert not at.exception
    return at


def test_nada_aparece_sem_entrar():
    at = abrir()
    assert "usuario" not in at.session_state and "S" not in at.session_state
    assert not at.radio  # sem barra de abas e sem nenhum dado antes do login
    entrar(at, "ninguem@exemplo.com", "senha-errada-1")
    assert any("incorretos" in e.value for e in at.error) and "usuario" not in at.session_state


def test_todas_as_abas_e_um_treino_com_retomada():
    at = criar_conta(abrir(), "ana@exemplo.com")
    # passo 1: dados reais (sem eles não dá para continuar)
    botao(at, "Continuar").click().run()
    assert any("Preencha seus dados" in e.value for e in at.error)
    primeiro_acesso(at)
    S = at.session_state["S"]
    assert S["profile"]["confirmado"] and S["profile"]["pesoInicial"] == 112.5 and [w["peso"] for w in S["weights"]] == [112.5]
    assert any("Avaliação registrada" in s.value for s in at.success)
    for aba in ["Treino", "Evolução", "Meu plano", "Perfil", "Início"]:
        at.radio(key="aba").set_value(aba).run()
        assert not at.exception, aba
    # treino de hoje garantido (hoje pode ser dia de descanso na agenda)
    at.radio(key="aba").set_value("Treino").run()
    [s for s in at.selectbox if s.label == "Trocar o treino de hoje"][0].set_value("A").run()
    botao(at, "Iniciar este treino").click().run()
    assert not at.exception and at.session_state["S"]["active"]["workout"] == "A"
    campo(at, "Carga da série 1 (kg)").input("40")
    botao(at, "Concluir série 1").click().run()
    assert not at.exception
    ex0 = at.session_state["S"]["active"]["ex"][0]
    assert ex0["sets"][0] == {**ex0["sets"][0], "done": True, "load": "40", "reps": "15"}
    # cronômetro de descanso: termina no descanso prescrito a partir de agora
    desc = at.session_state["S"]["active"]["ex"][0]["presc"]["descanso"]
    fim = at.session_state["descanso_ate"] / 1000
    assert abs(fim - (time.time() + desc)) < 15 and at.session_state["descanso_total"] == desc
    # recarregar a página: precisa entrar de novo e a sessão continua de onde parou
    at = entrar(abrir(), "ana@exemplo.com")
    at.radio(key="aba").set_value("Treino").run()
    assert not at.exception and at.session_state["S"]["active"]["ex"][0]["sets"][0]["done"]
    assert any(b.label == "Concluir série 2" for b in at.button)
    botao(at, "Finalizar treino").click().run()
    [r for r in at.radio if r.label == "Sensação geral"][0].set_value("bem")
    botao(at, "Salvar treino").click().run()
    assert not at.exception
    S = at.session_state["S"]
    assert S["active"] is None and S["sessions"][-1]["status"] == "concluida" and S["sessions"][-1]["volume"] == 600
    assert any("Treino concluído" in m.value for m in at.markdown)  # tela de resumo


def test_isolamento_entre_contas():
    a = criar_conta(abrir(), "carla@exemplo.com")
    primeiro_acesso(a, peso="101,1")
    b = criar_conta(abrir(), "duda@exemplo.com")
    assert b.session_state["S"]["weights"] == [] and not b.session_state["S"]["profile"]["confirmado"]
    primeiro_acesso(b, peso="77,7")
    a2 = entrar(abrir(), "carla@exemplo.com")
    assert [w["peso"] for w in a2.session_state["S"]["weights"]] == [101.1]
    b2 = entrar(abrir(), "duda@exemplo.com")
    assert [w["peso"] for w in b2.session_state["S"]["weights"]] == [77.7]
    con = sqlite3.connect(os.environ["FOCO_LEVE_DB"])
    donos = [r[0] for r in con.execute("SELECT usuario FROM estado")]
    assert "padrao" not in donos and len(set(donos)) == len(donos)  # nenhum identificador fixo compartilhado
    # cada conta tem a própria rotação de exercícios, estável entre acessos
    sa, sb = a2.session_state["S"]["semente"], b2.session_state["S"]["semente"]
    assert sa and sb and sa != sb and entrar(abrir(), "carla@exemplo.com").session_state["S"]["semente"] == sa
    a2.radio(key="aba").set_value("Meu plano").run()
    assert not a2.exception and any("Como o seu treino é montado" in e.label for e in a2.expander)
    a2.radio(key="aba").set_value("Perfil").run()
    assert any("Peso atual: 101,1 kg" in c.value for c in a2.caption)


def textos(no) -> str:
    """Tudo o que a tela mostra: textos, rótulos, valores de campos, tabelas e HTML."""
    partes = []
    for filho in getattr(no, "children", {}).values():
        partes.append(textos(filho))
    try:
        v = no.value
        partes.append(v.to_string() if hasattr(v, "to_string") else str(v))
    except Exception:  # noqa: BLE001 - elementos sem valor
        pass
    partes.append(str(getattr(no, "proto", "")))
    return "\n".join(partes)


def todas_as_telas(at) -> str:
    out = []
    for aba in ABAS:
        at.radio(key="aba").set_value(aba).run()
        assert not at.exception, aba
        out.append(textos(at.main))
    return "\n".join(out)


MARCAS = ["Zuleica", "123,4", "81,7", "joelho-zuleica", "nota-habito-zuleica"]


def conta_cheia(email) -> dict:
    """Conta com registros de todas as categorias: perfil, avaliação, metas, pesos, plano, sessões, hábitos."""
    loja = A.LojaSQLite(os.environ["FOCO_LEVE_DB"])
    u = loja.criar_conta(email, "senha-segura-1")
    S = R.padrao()
    S["profile"].update({"nome": "Zuleica", "pesoInicial": 123.4, "pesoMeta": 81.7, "limitacao": "joelho-zuleica",
                         "confirmado": True, "dias": 4})
    S["assess"].update({"done": True, "dor": "nao", "inchaco": "nao", "caminhar": "nao", "diag": "nao",
                        "liberacao": "sim", "lesao": "nao", "date": R.hoje()})
    S["weights"] = [{"id": "z", "date": R.hoje(), "peso": 123.4, "cintura": None, "cond": "", "obs": "pesagem-zuleica"}]
    R.iniciar_sessao(S, "A")
    R.marcar_serie(S, 0, 0, True)
    R.finalizar_sessao(S, "bem", 70, rpe_sessao=6, fadiga=3, recuperacao="boa")
    R.iniciar_sessao(S, "B")  # sessão em andamento
    S["habits"][R.hoje()] = {"agua": 7, "obs": "nota-habito-zuleica"}
    S["checkins"][R.hoje()] = {"dor": 2, "inchaco": False, "fadiga": 2, "sono": 6, "obs": "checkin-zuleica"}
    loja.salvar(u, S, 0)
    return u


def test_sair_e_entrar_em_outra_conta_nao_deixa_nada_visivel():
    dona = conta_cheia("zuleica@exemplo.com")
    at = entrar(abrir(), "zuleica@exemplo.com")
    tela_a = todas_as_telas(at)
    assert all(m in tela_a for m in MARCAS), "controle: as marcas aparecem para a dona"
    assert at.session_state["S"]["active"] is not None
    at.radio(key="aba").set_value("Perfil").run()
    botao(at, "Sair da conta").click().run()
    assert "usuario" not in at.session_state and "S" not in at.session_state and not at.radio
    # outra pessoa entra no mesmo navegador, sem recarregar a página
    criar_conta(at, "yara@exemplo.com")
    primeiro_acesso(at, peso="70,2")
    S = at.session_state["S"]
    assert S["active"] is None and S["sessions"] == [] and S["habits"] == {} and S["checkins"] == {}
    assert S["profile"]["nome"] == "" and [w["peso"] for w in S["weights"]] == [70.2]
    assert at.session_state["usuario"]["id"] != dona["id"]
    tela_b = todas_as_telas(at)
    vazou = [m for m in MARCAS + ["pesagem-zuleica", "checkin-zuleica", "zuleica@exemplo.com"] if m in tela_b]
    assert not vazou, vazou


def test_ids_na_url_nao_mudam_a_identidade():
    dona = conta_cheia("xenia@exemplo.com")
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in {"usuario": dona["id"], "user_id": dona["id"], "id": dona["id"], "email": "xenia@exemplo.com"}.items():
        at.query_params[k] = v
    at.run()
    assert "usuario" not in at.session_state and not at.radio  # a URL não faz ninguém entrar
    criar_conta(at, "wanda@exemplo.com")
    assert at.session_state["usuario"]["id"] != dona["id"]
    assert at.session_state["S"]["weights"] == [] and at.session_state["S"]["profile"]["nome"] == ""
    assert not [m for m in MARCAS if m in todas_as_telas(at)]


def test_reiniciar_o_streamlit_mantem_os_dados_de_cada_conta():
    conta_cheia("vera@exemplo.com")
    st.cache_resource.clear()  # o que um reinício do servidor apaga: o cliente do banco em cache e todas as sessões
    at = entrar(abrir(), "vera@exemplo.com")
    assert not at.exception and at.session_state["S"]["profile"]["nome"] == "Zuleica"
    assert at.session_state["S"]["active"]["workout"] == "B"  # a sessão em andamento continua


def test_registro_da_versao_sem_contas_fica_pendente():
    con = sqlite3.connect(os.environ["FOCO_LEVE_DB"])
    con.execute("CREATE TABLE IF NOT EXISTS estado (usuario TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado TEXT, "
                "versao INTEGER NOT NULL DEFAULT 0)")
    antigo = {"profile": {"nome": "Eva-antiga", "confirmado": True}, "assess": {"done": True}, "sessions": [],
              "weights": [{"id": "w", "date": "2026-09-01", "peso": 99.9}]}
    con.execute("INSERT OR REPLACE INTO estado(usuario, dados, versao) VALUES('padrao', ?, 3)", (json.dumps(antigo),))
    con.commit()
    at = criar_conta(abrir(), "eva@exemplo.com")
    assert at.session_state["S"]["weights"] == []  # nada é atribuído automaticamente
    primeiro_acesso(at)
    assert "Eva-antiga" not in todas_as_telas(at)  # ninguém vê o registro sem dono
    assert con.execute("SELECT count(*) FROM estado WHERE usuario='padrao'").fetchone()[0] == 1  # nem é apagado


def test_sem_banco_configurado_nao_abre_dados_pessoais(monkeypatch):
    monkeypatch.delenv("FOCO_LEVE_MODO_LOCAL")
    st.cache_resource.clear()
    try:
        at = abrir()
        assert any("não foi configurado" in e.value for e in at.error)
        assert not at.text_input and not at.radio  # nem login, nem abas
    finally:
        monkeypatch.setenv("FOCO_LEVE_MODO_LOCAL", "1")
        st.cache_resource.clear()


def test_modo_supabase_duas_contas_e_recuperacao_de_senha(monkeypatch):
    """O app inteiro com o cliente Supabase, contra o servidor simulado (com RLS) dos testes de armazenamento."""
    import requests
    from test_armazenamento import SupabaseFalso
    falso = SupabaseFalso()
    monkeypatch.setattr(requests, "request", falso.request)
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-teste")
    monkeypatch.setenv("FOCO_LEVE_SITE_URL", "https://foco-leve.test")
    st.cache_resource.clear()
    try:
        a = criar_conta(abrir(), "sa@exemplo.com")
        primeiro_acesso(a, peso="88,8")
        b = criar_conta(abrir(), "sb@exemplo.com")
        assert b.session_state["S"]["weights"] == []
        primeiro_acesso(b, peso="66,6")
        assert [w["peso"] for w in entrar(abrir(), "sa@exemplo.com").session_state["S"]["weights"]] == [88.8]
        assert set(falso.linhas) == {a.session_state["usuario"]["id"], b.session_state["usuario"]["id"]}
        assert "66,6" not in todas_as_telas(entrar(abrir(), "sa@exemplo.com"))
        # recuperação de senha pelo código numérico (modelo de e-mail com {{ .Token }})
        r = abrir()
        campo(r, "E-mail da conta", "rec_email").input("sa@exemplo.com")
        botao(r, "Enviar link").click().run()
        assert any("Pedido enviado" in x.value for x in r.success)
        campo(r, "E-mail da conta", "red_email").input("sa@exemplo.com")
        campo(r, "Código recebido").input(falso.codigos["sa@exemplo.com"])
        campo(r, "Nova senha (mínimo 8 caracteres)").input("senha-nova-77")
        botao(r, "Trocar a senha e entrar").click().run()
        assert not r.exception and r.session_state["usuario"]["email"] == "sa@exemplo.com"
        assert [w["peso"] for w in r.session_state["S"]["weights"]] == [88.8]
        assert "usuario" not in entrar(abrir(), "sa@exemplo.com").session_state  # a senha antiga não vale mais
        assert entrar(abrir(), "sa@exemplo.com", "senha-nova-77").session_state["usuario"]["email"] == "sa@exemplo.com"
        # recuperação pelo link do e-mail padrão: volta ao app com ?rec=…&code=…
        from urllib.parse import parse_qs, urlsplit
        r = abrir()
        campo(r, "E-mail da conta", "rec_email").input("sa@exemplo.com")
        botao(r, "Enviar link").click().run()
        assert falso.links["sa@exemplo.com"].startswith("https://foco-leve.test/?rec=")
        q = parse_qs(urlsplit(falso.links["sa@exemplo.com"]).query)
        link = AppTest.from_file(APP, default_timeout=60)
        link.query_params["rec"], link.query_params["code"] = q["rec"][0], q["code"][0]
        link.run()
        assert not link.exception and "usuario" not in link.session_state  # ainda não entrou
        assert dict(link.query_params) == {}  # o código saiu da URL
        campo(link, "Nova senha (mínimo 8 caracteres)").input("senha-do-link-9")
        campo(link, "Repita a nova senha").input("senha-do-link-9")
        botao(link, "Salvar a nova senha e entrar").click().run()
        assert not link.exception and link.session_state["usuario"]["email"] == "sa@exemplo.com"
        assert [w["peso"] for w in link.session_state["S"]["weights"]] == [88.8]
        assert entrar(abrir(), "sa@exemplo.com", "senha-do-link-9").session_state["usuario"]["email"] == "sa@exemplo.com"
        # o mesmo link de novo (ou um link inventado) não abre nada
        de_novo = AppTest.from_file(APP, default_timeout=60)
        de_novo.query_params["rec"], de_novo.query_params["code"] = q["rec"][0], q["code"][0]
        de_novo.run()
        assert "usuario" not in de_novo.session_state and "recuperando" not in de_novo.session_state
        assert any("venceu ou já foi usado" in w.value for w in de_novo.warning)
        sem_chave = AppTest.from_file(APP, default_timeout=60)
        sem_chave.query_params["code"] = "pkce-qualquer"  # link que voltou sem a chave do servidor
        sem_chave.run()
        assert "usuario" not in sem_chave.session_state and dict(sem_chave.query_params) == {}
        assert any("venceu ou já foi usado" in w.value for w in sem_chave.warning)
    finally:
        st.cache_resource.clear()


def test_secrets_salvos_com_o_app_no_ar_valem_sem_reiniciar(monkeypatch):
    """No Streamlit Cloud, salvar os Secrets não reinicia o servidor: a próxima visita já deve ver o banco."""
    monkeypatch.delenv("FOCO_LEVE_MODO_LOCAL")
    assert any("não foi configurado" in e.value for e in abrir().error)
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-teste")
    at = abrir()  # mesmo processo, sem limpar cache
    assert not at.error and any(x.key == "login_email" for x in at.text_input)


def test_atualizacao_sem_reiniciar_recarrega_os_modulos(monkeypatch):
    """Streamlit Cloud: app.py novo com o módulo ui antigo na memória (sem AJUSTES_PAGINA) não pode quebrar."""
    import ui
    abrir()
    monkeypatch.delattr(ui, "AJUSTES_PAGINA")  # o "ui" antigo, de antes da atualização
    monkeypatch.delattr(ui, "_fl_mtime")       # importado por uma versão anterior do app.py
    at = abrir()
    assert not at.exception and hasattr(ui, "AJUSTES_PAGINA")
    monkeypatch.delattr(ui, "AJUSTES_PAGINA")
    ui._fl_mtime = 0                            # arquivo mudou no disco depois da carga
    at = abrir()
    assert not at.exception and hasattr(ui, "AJUSTES_PAGINA")


def test_conta_com_pesagem_inicial_antiga_e_corrigida_ao_entrar():
    """Caso real: primeiro acesso com 90 kg, depois o Perfil foi para 115 kg antes da correção do PR #10."""
    from foco_leve import plano as P
    loja = A.LojaSQLite(os.environ["FOCO_LEVE_DB"])
    u = loja.criar_conta("pesoantigo@exemplo.com", "senha-segura-1")
    S = R.padrao()
    S["profile"].update({"pesoInicial": 115, "pesoMeta": 90, "confirmado": True})
    S["assess"]["done"] = True
    S["weights"] = [{"id": "w", "date": R.hoje(), "peso": 90.0, "cond": P.PESAGEM_INICIAL, "obs": ""}]
    loja.salvar(u, S, 0)
    at = entrar(abrir(), "pesoantigo@exemplo.com")
    assert not at.exception and [w["peso"] for w in at.session_state["S"]["weights"]] == [115.0]
    tela = textos(at.main)  # cartões de peso do Início: atual e quanto falta
    assert "<b>115,0 kg</b>" in tela and "<b>25,0 kg</b>" in tela
    assert loja.carregar_com_versao(u)[0]["weights"][0]["peso"] == 115.0  # já gravado no banco


def test_perfil_tem_botao_de_compartilhar_so_com_o_link(monkeypatch):
    monkeypatch.setenv("FOCO_LEVE_SITE_URL", "https://foco-leve.test")
    at = primeiro_acesso(criar_conta(abrir(), "share@exemplo.com"))
    at.radio(key="aba").set_value("Perfil").run()
    assert not at.exception
    assert any("Convide alguém" in m.value for m in at.markdown)
    assert [c.value for c in at.code] == ["https://foco-leve.test"]
    whats = [x.proto.url for x in at.get("link_button")]
    assert len(whats) == 1 and whats[0].startswith("https://wa.me/?text=") and "foco-leve.test" in whats[0]
    assert "share" not in whats[0].split("foco-leve.test")[0].lower()  # só convite + link, sem e-mail da conta
    import ui
    h = ui.botao_compartilhar("https://foco-leve.test", "convite </script><b>")
    assert "navigator.share" in h and "clipboard" in h and "</script><b>" not in h


def test_objetivos_em_cartoes_biblioteca_e_acompanhamento():
    at = criar_conta(abrir(), "obj@exemplo.com")
    # primeiro acesso: objetivo combinado, sem máquinas, glúteos como prioridade
    at.button_group(key="pri_obj").set_value(["emagrecimento", "gluteos"])
    at.button_group(key="pri_eq").set_value(["halteres", "corpo"])
    primeiro_acesso(at)
    p = at.session_state["S"]["profile"]
    assert p["objetivos"] == ["emagrecimento", "gluteos"] and p["equipamentos"] == ["halteres", "corpo"]
    # Meu plano: nenhum objetivo é recusado; a explicação do plano e a biblioteca ficam aqui
    at.radio(key="aba").set_value("Meu plano").run()
    assert not at.exception
    tudo = textos(at.main)
    assert "Objetivo: Emagrecimento + Glúteos" in tudo and "Biblioteca de exercícios" in tudo
    at.button_group(key="plano_obj").set_value([])
    botao(at, "Salvar e recalcular").click().run()
    assert any("pelo menos um objetivo" in e.value for e in at.error)
    at.button_group(key="plano_obj").set_value(["emagrecimento", "gluteos"])
    at.selectbox(key="bib_grupo").set_value("Peitoral").run()
    assert "Supino na máquina · fora do seu plano" in [e.label for e in at.expander]
    assert "Flexão de braços inclinada (mãos no banco)" in [e.label for e in at.expander]
    # Evolução: acompanhamento sem dados não inventa números
    at.radio(key="aba").set_value("Evolução").run()
    assert not at.exception and "Ainda não há treinos concluídos" in textos(at.main)


def test_meu_plano_recalcula_e_sessao_antiga_com_aba_antiga():
    at = criar_conta(abrir(), "plano@exemplo.com")
    primeiro_acesso(at)
    at.radio(key="aba").set_value("Meu plano").run()
    at.button_group(key="plano_obj").set_value(["hipertrofia"])
    [s for s in at.selectbox if s.label == "Dias de treino por semana"][0].set_value(3)
    botao(at, "Salvar e recalcular").click().run()
    assert not at.exception
    p = at.session_state["S"]["profile"]
    assert p["objetivos"] == ["hipertrofia"] and p["dias"] == 3
    assert list(at.session_state["S"]["schedule"].values()).count("FULL") == 3  # 3 dias + foco muscular = corpo inteiro
    assert any("Plano recalculado" in str(x.value) for x in at.success)
    # Perfil não repete os campos do plano
    at.radio(key="aba").set_value("Perfil").run()
    assert not [s for s in at.selectbox if s.label == "Dias de treino por semana"]


def test_series_iguais_medidas_pdf_e_instalar():
    at = criar_conta(abrir(), "rapida@exemplo.com")
    primeiro_acesso(at)
    at.radio(key="aba").set_value("Treino").run()
    [s for s in at.selectbox if s.label == "Trocar o treino de hoje"][0].set_value("A").run()
    botao(at, "Iniciar este treino").click().run()
    campo(at, "Carga da série 1 (kg)").input("30")
    todas = [b for b in at.button if b.label.startswith("Concluir as ") and b.label.endswith(" séries iguais")][0]
    todas.click().run()
    assert not at.exception
    ex0 = at.session_state["S"]["active"]["ex"][0]
    assert ex0["done"] and all(x["done"] and x["load"] == "30" and x["reps"] == "15" for x in ex0["sets"])
    # medidas corporais junto com a pesagem
    at.radio(key="aba").set_value("Evolução").run()
    campo(at, "Peso (kg)").input("110")
    campo(at, "Quadril (cm)").input("118,5")
    botao(at, "Salvar pesagem").click().run()
    assert not at.exception
    w = [x for x in at.session_state["S"]["weights"] if x["peso"] == 110][0]
    assert w["quadril"] == 118.5 and w["braco"] is None
    # relatório em PDF
    botao(at, "Preparar PDF").click().run()
    assert not at.exception and at.session_state["pdf_rel"][:5] == b"%PDF-"
    # instalar na tela inicial
    at.radio(key="aba").set_value("Perfil").run()
    assert any("Instalar na tela inicial" in e.label for e in at.expander)
    # sair apaga o PDF da sessão (não fica para a próxima conta)
    botao(at, "Sair da conta").click().run()
    assert "pdf_rel" not in at.session_state


def test_ficha_no_treino_meta_de_carga_e_lembrete_de_copia():
    at = criar_conta(abrir(), "metas@exemplo.com")
    primeiro_acesso(at)
    at.radio(key="aba").set_value("Treino").run()
    [s for s in at.selectbox if s.label == "Trocar o treino de hoje"][0].set_value("A").run()
    botao(at, "Iniciar este treino").click().run()
    assert any(s.label == "Aparelho ocupado ou desconfortável? Trocar por" for s in at.selectbox)
    campo(at, "Carga da série 1 (kg)").input("30")
    [b for b in at.button if b.label.startswith("Concluir as ")][0].click().run()
    botao(at, "Finalizar treino").click().run()
    [r for r in at.radio if r.label == "Sensação geral"][0].set_value("bem")
    botao(at, "Salvar treino").click().run()
    assert not at.exception and at.session_state["S"]["sessions"]
    # Evolução (em outra aba do navegador): gráfico do exercício e meta de carga
    at = entrar(abrir(), "metas@exemplo.com")
    at.radio(key="aba").set_value("Evolução").run()
    ex = at.selectbox(key="ev_ex").value
    [x for x in at.text_input if x.label == "Meta de carga (kg)"][0].input("45")
    botao(at, "Salvar meta").click().run()
    assert not at.exception and at.session_state["S"]["metasCarga"] == {ex: 45.0}
    assert "Recordes pessoais" in textos(at.main) and "Esta semana × anterior" in textos(at.main)
    # Início: lembrete de cópia de segurança (há treino e nenhuma cópia baixada)
    at.radio(key="aba").set_value("Início").run()
    assert "ainda não baixou uma cópia de segurança" in textos(at.main)


def test_peso_semanal_pontos_e_album():
    at = criar_conta(abrir(), "pontos@exemplo.com")
    primeiro_acesso(at, peso="100")
    # Início: peso da semana
    [x for x in at.text_input if x.label == "Peso desta semana (kg)"][0].input("99,4")
    botao(at, "Atualizar").click().run()
    assert not at.exception
    S = at.session_state["S"]
    hoje = [w for w in S["weights"] if w["date"] == R.hoje()]
    assert len(hoje) == 1 and hoje[0]["peso"] == 99.4  # substitui a pesagem do primeiro acesso do mesmo dia
    tudo = textos(at.main)
    assert "pontos" in tudo and "Nível 1" in tudo
    # Evolução → Conquistas: álbum com figurinhas bloqueadas e a tabela de pontos
    at.radio(key="aba").set_value("Evolução").run()
    tudo = textos(at.main)
    assert not at.exception and "Álbum de figurinhas" in tudo and "Primeiro passo" in tudo and "De onde vêm os pontos" in tudo
