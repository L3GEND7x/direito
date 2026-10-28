"""Teste de fumaça da interface Streamlit (executa o app sem navegador)."""
import os
import tempfile

from streamlit.testing.v1 import AppTest

os.environ["FOCO_LEVE_DB"] = os.path.join(tempfile.mkdtemp(), "teste.db")
APP = os.path.join(os.path.dirname(__file__), "..", "app.py")


def test_todas_as_abas_e_um_treino():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    # passo 1: dados reais (sem eles não dá para continuar)
    [b for b in at.button if b.label == "Continuar"][0].click().run()
    assert any("Preencha seus dados" in e.value for e in at.error)
    campos = {"Peso atual (kg)": "112,5", "Peso desejado (kg)": "90", "Altura (cm)": "178", "Idade (anos)": "30"}
    for rot, v in campos.items():
        [x for x in at.text_input if x.label == rot][0].input(v)
    [b for b in at.button if b.label == "Continuar"][0].click().run()
    assert not at.exception
    p = at.session_state["S"]["profile"]
    assert p["confirmado"] and p["pesoInicial"] == 112.5 and p["altura"] == 178
    assert [w["peso"] for w in at.session_state["S"]["weights"]] == [112.5]
    # passo 2: avaliação de segurança
    resp = {"as_dor": "nao", "as_inchaco": "nao", "as_caminhar": "nao", "as_diag": "nao", "as_liberacao": "sim", "as_lesao": "nao"}
    for k, v in resp.items():
        at.radio(key=k).set_value(v)
    [b for b in at.button if b.label == "Salvar avaliação"][0].click()
    at.run()
    assert not at.exception
    assert any("Avaliação registrada" in s.value for s in at.success)
    for aba in ["Treinos", "Evolução", "Hábitos", "Perfil", "Início"]:
        at.radio(key="aba").set_value(aba).run()
        assert not at.exception, aba
    # iniciar o treino do dia, se houver
    at.radio(key="aba").set_value("Treinos").run()
    botoes = [b for b in at.button if b.label == "Iniciar este treino"]
    if botoes:
        botoes[0].click().run()
        assert not at.exception
        concluir = [b for b in at.button if b.label in ("Concluir série 1", "Concluir cardio", "Concluir exercício")]
        concluir[0].click().run()
        assert not at.exception
        assert any(e["sets"][0]["done"] for e in at.session_state["S"]["active"]["ex"])
        # reabrir o app: a sessão em andamento e a série concluída vêm do banco
        at = AppTest.from_file(APP, default_timeout=60).run()
        at.radio(key="aba").set_value("Treinos").run()
        assert not at.exception and any(e["sets"][0]["done"] for e in at.session_state["S"]["active"]["ex"])
        [b for b in at.button if b.label == "Finalizar treino"][0].click().run()
        [r for r in at.radio if r.label == "Sensação geral"][0].set_value("bem")
        [b for b in at.button if b.label == "Salvar treino"][0].click().run()
        assert not at.exception
        assert at.session_state["S"]["active"] is None and at.session_state["S"]["sessions"][-1]["status"] == "concluida"
        assert any("Treino concluído" in m.value for m in at.markdown)  # tela de resumo
