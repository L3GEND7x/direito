"""Peso semanal (evolução × regressão), pontos, níveis e figurinhas."""
import pytest

from foco_leve import evolucao as E
from foco_leve import recompensas as RC
from foco_leve import regras as R


@pytest.fixture
def S():
    s = R.padrao()
    s["assess"].update({"done": True, "date": R.hoje(), "dor": "nao", "inchaco": "nao", "caminhar": "nao",
                        "diag": "nao", "liberacao": "sim", "lesao": "nao"})
    s["profile"].update({"confirmado": True, "pesoInicial": 100, "pesoMeta": 90, "dias": 3})
    s["schedule"] = {str(d): ("A" if d in (1, 3, 5) else "OFF") for d in range(7)}
    return s


def sessao(data, carga=40, n=0, hora_ms=None):
    return {"id": f"s{data}{n}", "date": data, "workout": "A", "status": "concluida", "startedAt": hora_ms or n,
            "ex": [{"id": "supino_maquina", "sets": [{"done": True, "load": str(carga), "reps": "15"}], "painLevel": "nenhum"}]}


def peso(data, kg):
    return {"id": data, "date": data, "peso": kg, "cond": E.PESAGEM_SEMANAL}


# ---------------------------------------------------------------- peso semanal
def test_evolucao_e_regressao_em_relacao_a_meta(S):
    ws = R.inicio_semana(R.hoje())
    S["weights"] = [peso(R.add_dias(ws, -21), 100), peso(R.add_dias(ws, -14), 99.2), peso(R.add_dias(ws, -7), 99.6),
                    peso(ws, 99.65)]
    sem = E.pesos_semanais(S)
    assert [x["direcao"] for x in sem] == ["inicio", "evolucao", "regressao", "estavel"]
    assert sem[1]["variacao"] == pytest.approx(-0.8)
    # quem quer ganhar peso: subir é evolução
    S["profile"].update({"pesoInicial": 60, "pesoMeta": 70})
    S["weights"] = [peso(R.add_dias(ws, -7), 60), peso(ws, 60.5)]
    assert E.pesos_semanais(S)[-1]["direcao"] == "evolucao"


def test_pesagem_desta_semana(S):
    assert E.pesagem_desta_semana(S) is None
    S["weights"] = [peso(R.add_dias(R.inicio_semana(R.hoje()), -1), 98), peso(R.hoje(), 97.5)]
    assert E.pesagem_desta_semana(S)["peso"] == 97.5


# ---------------------------------------------------------------- pontos
def test_pontos_vem_dos_registros(S):
    assert RC.pontos(S)["total"] == 0 and RC.pontos(S)["nivel"] == 1
    ws = R.inicio_semana(R.hoje())
    anterior = R.add_dias(ws, -7)
    # semana anterior completa (seg, qua, sex) com um recorde na sexta; pesagem nas duas semanas
    S["sessions"] = [sessao(R.add_dias(anterior, d), carga, n=d) for d, carga in ((0, 40), (2, 40), (4, 45))]
    S["weights"] = [peso(anterior, 99), peso(R.hoje(), 98.5)]
    pt = RC.pontos(S)
    itens = {x["motivo"]: x["qtd"] for x in pt["itens"]}
    assert itens["Treinos concluídos"] == 3 and itens["Semanas com todos os treinos feitos"] == 1
    assert itens["Semanas com pesagem registrada"] == 2 and itens["Recordes de carga"] == 1
    assert pt["total"] == 3 * 10 + 100 + 2 * 20 + 30
    # excluir um treino tira os pontos dele (e a semana deixa de ser completa)
    S["sessions"].pop()
    assert RC.pontos(S)["total"] == 2 * 10 + 2 * 20


def test_dois_treinos_no_mesmo_dia_contam_uma_vez(S):
    S["sessions"] = [sessao(R.hoje(), n=1), sessao(R.hoje(), n=2)]
    assert {x["motivo"]: x["qtd"] for x in RC.pontos(S)["itens"]}["Treinos concluídos"] == 1


def test_niveis(S):
    S["checkins"] = {R.add_dias(R.hoje(), -k): {"sono": 7} for k in range(260)}  # 520 pontos
    pt = RC.pontos(S)
    assert pt["nivel"] == 2 and pt["nome_nivel"] == RC.NIVEIS[1] and pt["falta"] == 480


# ---------------------------------------------------------------- figurinhas
def test_figurinhas_e_novas_so_uma_vez(S):
    assert not any(f["ganha"] for f in RC.figurinhas(S))
    ws = R.inicio_semana(R.hoje())
    anterior = R.add_dias(ws, -7)
    S["sessions"] = [sessao(R.add_dias(anterior, d), 40 + d, n=d) for d in (0, 2, 4)]
    S["weights"] = [peso(anterior, 99), peso(R.hoje(), 98.8)]
    ganhas = {f["id"] for f in RC.figurinhas(S) if f["ganha"]}
    assert {"primeiro", "semana", "recorde", "kg1"} <= ganhas and "t10" not in ganhas
    assert {f["id"] for f in RC.novas(S)} == ganhas
    RC.marcar_vistas(S)
    assert RC.novas(S) == []
    S["metasCarga"] = {"supino_maquina": 44}
    assert [f["id"] for f in RC.novas(S)] == ["metacarga"]


def test_meta_de_peso_atingida(S):
    S["weights"] = [peso(R.hoje(), 89.8)]
    ids = {f["id"] for f in RC.figurinhas(S) if f["ganha"]}
    assert {"kg1", "kg5", "metapeso"} <= ids


def test_recompensas_nao_alteram_o_estado(S):
    S["sessions"] = [sessao(R.hoje())]
    antes = R.copia(S)
    RC.pontos(S), RC.figurinhas(S), RC.novas(S)
    assert R.copia(S) == antes
