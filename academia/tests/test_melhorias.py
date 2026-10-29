"""Registro rápido de séries, medidas corporais, sugestões com confirmação e relatório em PDF."""
import pytest

from foco_leve import evolucao as E
from foco_leve import monitoramento as M
from foco_leve import plano as P
from foco_leve import regras as R
from foco_leve import relatorio_pdf as RP


@pytest.fixture
def S():
    s = R.padrao()
    s["assess"].update({"done": True, "date": R.hoje(), "dor": "nao", "inchaco": "nao", "caminhar": "nao",
                        "diag": "nao", "liberacao": "sim", "lesao": "nao"})
    s["profile"].update({"confirmado": True, "nome": "Zé Conceição", "nivel": "Intermediário", "dias": 5})
    s["schedule"] = P.agenda_para(5)
    return s


def sessao(data, ex, n=0, status="concluida"):
    return {"id": f"s{data}{n}", "date": data, "workout": "A", "status": status, "startedAt": n,
            "ex": [{"id": i, "sets": [{"done": True, "load": str(c), "reps": "15"} for _ in range(3)], "painLevel": dor}
                   for i, c, dor in ex]}


# ---------------------------------------------------------------- séries
def test_concluir_series_restantes_de_uma_vez(S):
    R.iniciar_sessao(S, "A")
    se = S["active"]["ex"][0]
    se["sets"][0].update({"load": "40", "reps": "15"})
    R.marcar_serie(S, 0, 0, True)
    n = R.concluir_restantes(S, 0, "42,5", "12")
    assert n == len(se["sets"]) - 1 and se["done"]
    assert [x["load"] for x in se["sets"][1:]] == ["42,5"] * n and all(x["reps"] == "12" for x in se["sets"][1:])
    assert se["sets"][0]["load"] == "40"  # a série já feita não muda
    assert R.concluir_restantes(S, 0, "50", "10") == 0


# ---------------------------------------------------------------- medidas
def test_medidas_comparadas_so_com_dois_registros(S):
    S["weights"] = [{"id": "a", "date": R.add_dias(R.hoje(), -20), "peso": 100, "cintura": 110, "quadril": 120, "cond": ""},
                    {"id": "b", "date": R.add_dias(R.hoje(), -1), "peso": 98, "cintura": 106.5, "braco": 35, "cond": ""}]
    med = {m["chave"]: m for m in E.comparacao_medidas(S)}
    assert set(med) == {"cintura"} and med["cintura"]["variacao"] == -3.5
    S["sessions"] = [sessao(R.add_dias(R.hoje(), -1), [("supino_maquina", 40, "nenhum")])]
    assert any("cintura -3,5 cm" in o["texto"] for o in M.observacoes(S))


# ---------------------------------------------------------------- sugestões
def _tres_semanas_abaixo(S, feitos=2):
    ws = R.inicio_semana(R.hoje())
    S["sessions"] = [sessao(R.add_dias(ws, -7 * k + d), [("supino_maquina", 40, "nenhum")], n=k * 10 + d)
                     for k in (1, 2, 3) for d in range(feitos)]


def test_sugere_menos_dias_e_so_aplica_com_confirmacao(S):
    _tres_semanas_abaixo(S, 2)
    sug = [x for x in M.sugestoes(S) if x["acao"][0] == "dias"]
    assert sug and sug[0]["acao"] == ("dias", 2)
    assert S["profile"]["dias"] == 5  # sugerir não muda nada
    msg = M.aplicar(S, sug[0])
    assert S["profile"]["dias"] == 2 and "2 dia" in msg
    assert not [x for x in M.sugestoes(S) if x["acao"][0] == "dias"]


def test_dor_repetida_sugere_tirar_o_exercicio(S):
    hoje = R.hoje()
    S["sessions"] = [sessao(R.add_dias(hoje, -k), [("leg_press", 100, "moderado")], n=k) for k in (2, 6)]
    sug = [x for x in M.sugestoes(S) if x["acao"] == ("desativar", "leg_press")]
    assert sug and "profissional de saúde" in sug[0]["texto"]
    M.aplicar(S, sug[0])
    assert R.status_ex(S, "leg_press")[0] is False
    assert "leg_press" not in [it["id"] for it in P.plano_do_dia(S, hoje, 6, wk="LA")["itens"]]


def test_agora_nao_esconde_por_duas_semanas(S, monkeypatch):
    _tres_semanas_abaixo(S, 1)
    sug = M.sugestoes(S)[0]
    M.dispensar(S, sug)
    assert not M.sugestoes(S)
    depois = R.add_dias(R.hoje(), M.DISPENSA_DIAS)
    monkeypatch.setattr(R, "hoje", lambda: depois)
    assert sug["id"] not in {k for k, d in S["dispensadas"].items() if R.dias_entre(d, depois) < M.DISPENSA_DIAS}


# ---------------------------------------------------------------- PDF
def test_pdf_com_dados_e_vazio(S):
    vazio = RP.gerar(S)
    assert vazio[:5] == b"%PDF-" and len(vazio) > 1000
    hoje = R.hoje()
    S["profile"]["limitacao"] = "dor no joelho — “leve” ≥ 2×"
    S["weights"] = [{"id": f"w{k}", "date": R.add_dias(hoje, -k), "peso": 100 - k * 0.1, "cintura": 110 - k * 0.1,
                     "cond": ""} for k in range(0, 40, 4)]
    S["sessions"] = [sessao(R.add_dias(hoje, -k), [("supino_maquina", 40 + k, "nenhum"), ("leg_press", 100, "forte")], n=k)
                     for k in (1, 3, 8)]
    cheio = RP.gerar(S)
    assert cheio[:5] == b"%PDF-" and len(cheio) > len(vazio)


def test_pdf_nao_altera_o_estado(S):
    antes = R.copia(S)
    RP.gerar(S)
    assert R.copia(S) == antes
