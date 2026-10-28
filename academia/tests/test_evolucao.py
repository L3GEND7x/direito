"""Números da evolução: só dados registrados."""
import pytest

from foco_leve import evolucao as E
from foco_leve import regras as R


@pytest.fixture
def S(monkeypatch):
    monkeypatch.setattr(R, "hoje", lambda: "2026-10-28")  # quarta-feira
    s = R.padrao()
    s["assess"].update({"done": True, "date": "2026-10-12", "dor": "nao", "inchaco": "nao", "caminhar": "nao",
                        "diag": "nao", "liberacao": "sim", "lesao": "nao"})
    s["startDate"] = "2026-10-12"
    return s


def sessao(S, data, carga=None, minutos=60, **extra):
    ex = []
    if carga:
        ex.append({"id": "supino_maquina", "sets": [{"done": True, "load": str(carga), "reps": "15"}], "done": True})
    ex.append({"id": "bicicleta", "sets": [{"done": True, "min": "30"}], "done": True, "met": "5.0"})
    S["sessions"].append({"id": data, "date": data, "workout": "A", "status": "concluida", "startedAt": len(S["sessions"]),
                          "minutes": minutos, "ex": ex, **extra})


def test_sem_dados_nao_inventa_numeros(S):
    assert E.ultima_sessao(S) is None and E.comparacao_cargas(S) == [] and E.comparacao_peso(S) is None
    assert all(x["feitos"] == 0 and x["cardio"] == 0 for x in E.semanas_recentes(S))
    assert E.consistencia(S)["aprovadas"] == 0  # semanas passadas sem treino contam como não aprovadas
    S["startDate"] = ""
    assert E.consistencia(S)["taxa"] is None


def test_dias_da_semana(S):
    sessao(S, "2026-10-26")
    estados = {d["data"]: d["estado"] for d in E.estado_dos_dias(S, "2026-10-26")}
    assert estados["2026-10-26"] == "feito" and estados["2026-10-27"] == "perdido"
    assert estados["2026-10-28"] == "planejado" and estados["2026-11-01"] == "descanso"


def test_semanas_e_linha_do_tempo(S):
    for d in ("2026-10-12", "2026-10-13", "2026-10-14"):  # semana 1 aprovada
        sessao(S, d, carga=40)
    sessao(S, "2026-10-19", carga=45)  # semana 2: 1 treino → repete
    sem = E.semanas_recentes(S, 3)
    assert [x["feitos"] for x in sem] == [3, 1, 0] and sem[0]["cardio"] == 90
    estados, atual = E.estados_20(S)
    assert atual == 2 and estados[0] == "ok" and estados[1] == "atual" and estados[2] == ""
    c = E.consistencia(S)
    assert c["avaliadas"] == 2 and c["aprovadas"] == 1 and c["sequencia"] == 0


def test_comparacoes(S):
    sessao(S, "2026-10-12", carga=40)
    sessao(S, "2026-10-26", carga=47.5)
    cmp = E.comparacao_cargas(S)[0]
    assert cmp["primeira"] == 40 and cmp["ultima"] == 47.5 and cmp["variacao"] == 7.5
    S["weights"] += [{"id": "a", "date": "2026-10-12", "peso": 115.0}, {"id": "b", "date": "2026-10-26", "peso": 112.4}]
    pw = E.comparacao_peso(S)
    assert round(pw["variacao"], 1) == -2.6 and round(pw["falta"], 1) == 23.4
    u = E.ultima_sessao(S)
    assert u["data"] == "2026-10-26" and u["cardio"] == 30 and u["feitos"] == 2


def test_criterios_da_semana_atual(S):
    sessao(S, "2026-10-26")
    S["checkins"]["2026-10-27"] = {"dor": 1, "inchaco": True, "red": False}
    itens = E.criterios_semana_atual(S)
    assert itens[0][0] is None  # 1 de 3: semana em andamento, ainda em aberto
    assert itens[3][0] is False
