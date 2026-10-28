import math

import pytest

from foco_leve import dados as D
from foco_leve import regras as R


@pytest.fixture
def S():
    s = R.padrao()
    s["assess"].update({"done": True, "date": R.hoje(), "dor": "nao", "inchaco": "nao", "caminhar": "nao",
                        "diag": "nao", "liberacao": "sim", "lesao": "nao"})
    return s


def test_catalogo_consistente():
    for k, w in D.TREINOS.items():
        for ex in w["ex"]:
            assert ex in D.EXERCICIOS, (k, ex)
    for k, alts in D.ALTERNATIVAS.items():
        assert k in D.EXERCICIOS and all(a in D.EXERCICIOS for a in alts)
    for k in D.FOTOS:
        assert k in D.EXERCICIOS
    forca = [e for e in D.EXERCICIOS.values() if e["tipo"] == "carga" and not e.get("semCarga")
             and e["grupo"] not in ("Recuperação", "Abdômen")]
    assert all(e["series"] == 3 and str(e["reps"]).startswith("15") for e in forca)
    assert D.EXERCICIOS["esteira_caminhada"]["duracao"] == 30
    assert D.EXERCICIOS["cardio_longo"]["duracao"] == 40


def test_imc_e_formatacao(S):
    assert round(R.imc(S, 115), 1) == 37.6
    assert R.imc_categoria(37.6) == "obesidade grau II"
    assert R.br(1234.5) == "1.234,5"
    assert R.num("114,2") == 114.2 and math.isnan(R.num("abc"))


def test_seguranca(S):
    assert R.seguranca(S) == "ok"
    S["checkins"][R.hoje()] = {"dor": 4, "inchaco": False, "fadiga": 2, "sono": 7, "red": False}
    assert R.seguranca(S) == "caution"
    assert R.status_ex(S, "leg_press")[0] is False
    assert R.status_ex(S, "supino_maquina")[0] is True
    S["assess"]["red"]["febre"] = True
    assert R.seguranca(S) == "urgent"


def test_sessao_autopreenchimento_e_energia(S):
    S["profile"]["nivel"] = "Intermediário"  # 3 séries desde a semana 1
    R.iniciar_sessao(S, "A")
    a = S["active"]
    assert len(a["ex"]) == 6 and a["semana"] == 1
    a["ex"][0]["sets"][0]["load"] = "40"
    descanso = R.marcar_serie(S, 0, 0, True)
    assert descanso == 75  # descanso da fase 1
    assert a["ex"][0]["sets"][0]["reps"] == "15"
    R.marcar_serie(S, 0, 1, True)
    assert a["ex"][0]["sets"][1]["load"] == "40"
    R.marcar_serie(S, 0, 2, True)
    assert a["ex"][0]["done"] is True
    assert R.volume(a) == 40 * 15 * 3
    cardio = len(a["ex"]) - 1
    a["ex"][cardio]["sets"][0]["min"] = "30"
    a["ex"][cardio]["met"] = "4.8"
    R.marcar_serie(S, cardio, 0, True)
    rec = R.finalizar_sessao(S, "bem", 75, rpe_sessao=6, fadiga=3, recuperacao="boa")
    # 30 min a 4,8 MET + 45 min a 3,5 MET, 115 kg  -> 276 + 301,9 = 578
    assert rec["kcal"] == 578 and rec["recuperacao"] == "boa" and rec["rpeSessao"] == 6
    assert R.energia_semana(S, R.inicio_semana(R.hoje()))["cardioMin"] == 30


def test_progressao_acsm(S):
    S["profile"]["nivel"] = "Intermediário"
    for dia, reps in (("2026-10-01", "16"), ("2026-10-03", "16")):
        R.iniciar_sessao(S, "A")
        S["active"]["date"] = dia
        for j in range(3):
            S["active"]["ex"][0]["sets"][j]["load"] = "40"
            R.marcar_serie(S, 0, j, True)
        S["active"]["ex"][0]["sets"][2]["reps"] = reps
        R.finalizar_sessao(S, "bem", 60)
    txt = R.recomendacao(S, "supino_maquina")
    assert "Critério de progressão atingido" in txt and "42 kg" in txt


def test_recorde(S):
    for carga in ("30", "35"):
        R.iniciar_sessao(S, "A")
        S["active"]["ex"][0]["sets"][0]["load"] = carga
        R.marcar_serie(S, 0, 0, True)
        rec = R.finalizar_sessao(S, "bem", 60)
    assert rec["_recordes"] == ["Supino na máquina: 35 kg"]


def test_relatorio_sem_dados_inventados(S):
    txt = R.relatorio_semanal(S, R.inicio_semana(R.hoje()))
    assert "Nenhuma pesagem registrada" in txt and "nan" not in txt.lower()


def test_migracao_da_versao_web():
    antigo = {"v": 2, "profile": {"tempoMax": 60}, "schedule": {"0": "OFF", "1": "A", "2": "LA", "3": "CARDIO", "4": "B", "5": "LB", "6": "OFF"},
              "sessions": [], "weights": []}
    m = R.mesclar(antigo)
    assert m["schedule"] == D.AGENDA_PADRAO and m["profile"]["tempoMax"] == 90 and m["v"] == R.VERSAO
