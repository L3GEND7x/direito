"""Regras do plano personalizado de 20 semanas."""
import pytest

from foco_leve import dados as D
from foco_leve import plano as P
from foco_leve import regras as R

TREINOS_FORCA = ["A", "B", "LA", "LB", "FULL"]


@pytest.fixture
def S():
    s = R.padrao()
    s["assess"].update({"done": True, "date": R.hoje(), "dor": "nao", "inchaco": "nao", "caminhar": "nao",
                        "diag": "nao", "liberacao": "sim", "lesao": "nao"})
    return s


def ws():
    return R.inicio_semana(R.hoje())


def ids(pl):
    return [it["id"] for it in pl["itens"]]


def cardio(pl):
    return next(it for it in pl["itens"] if D.EXERCICIOS[it["id"]].get("cardio"))


def test_cinco_fases_cobrem_20_semanas():
    semanas = [n for f in D.FASES_20 for n in range(f["semanas"][0], f["semanas"][1] + 1)]
    assert semanas == list(range(1, 21))
    assert [P.fase_da_semana(n)[0] for n in (1, 4, 5, 9, 13, 17, 20)] == [0, 0, 1, 2, 3, 4, 4]


def test_todo_treino_tem_cardio_de_30_min_e_90_min_planejados(S):
    for semana in range(1, 21):
        for wk in TREINOS_FORCA + ["CARDIO"]:
            pl = P.plano_do_dia(S, ws(), semana, wk=wk)
            assert cardio(pl)["duracao"] >= 30, (semana, wk)
            if wk != "CARDIO" or semana > 4:
                assert pl["total"] >= 85, (semana, wk, pl["total"])
            assert pl["total"] <= 90


def test_treinos_variam_todas_as_semanas(S):
    for perfil in ({}, {"pesoInicial": 80, "pesoMeta": 75}):
        S["profile"].update(perfil)
        for wk in TREINOS_FORCA + ["CARDIO"]:
            combos = [tuple(ids(P.plano_do_dia(S, ws(), n, wk=wk))) for n in range(1, 21)]
            assert len(set(combos)) == 20, wk


def test_prescricao_da_fase(S):
    pl1 = P.plano_do_dia(S, ws(), 1, wk="A")
    forca = [it for it in pl1["itens"] if "duracao" not in it]
    assert all(it["series"] == 2 for it in forca)  # iniciante nas semanas 1 e 2
    pl3 = P.plano_do_dia(S, ws(), 3, wk="A")
    assert all(it["series"] == 3 and str(it["reps"]).startswith(("15", "12")) for it in pl3["itens"] if "duracao" not in it)
    assert len(P.plano_do_dia(S, ws(), 5, wk="A")["itens"]) >= len(pl1["itens"])  # fase 2 acrescenta exercícios


def test_meta_muda_o_cardio(S):
    S["profile"]["tempoMax"] = 150  # tempo de sobra: só a meta decide
    longe = cardio(P.plano_do_dia(S, ws(), 13, wk="A"))["duracao"]
    S["profile"].update({"pesoInicial": 90, "pesoMeta": 89})
    perto = cardio(P.plano_do_dia(S, ws(), 13, wk="A"))["duracao"]
    assert P.cardio_semanal_alvo(S) == 150 and longe > perto >= 30


def test_treino_cabe_no_tempo(S):
    S["profile"]["tempoMax"] = 60
    pl = P.plano_do_dia(S, ws(), 9, wk="A")
    assert pl["total"] <= 60 and cardio(pl)["duracao"] >= 30
    forca = [x for x in ids(pl) if not D.EXERCICIOS[x].get("cardio")]
    assert len(forca) >= P.MIN_EXERCICIOS_FORCA
    assert any("Para caber" in a for a in pl["avisos"]) and any("abaixo da meta de 90" in a for a in pl["avisos"])


def test_peso_alto_comeca_com_baixo_impacto(S):
    assert P.baixo_impacto(S, 1)  # 115 kg, 1,75 m: IMC 37,6
    for semana in range(1, 9):
        for wk in TREINOS_FORCA + ["CARDIO"]:
            pl = P.plano_do_dia(S, ws(), semana, wk=wk)
            assert cardio(pl)["id"] in D.CARDIO_BAIXO_IMPACTO
            assert not set(ids(pl)) & D.EXIGE_CHAO_OU_EQUILIBRIO
    assert not P.baixo_impacto(S, 9)
    S["profile"].update({"pesoInicial": 75})
    assert not P.baixo_impacto(S, 1)


def test_limitacao_bloqueia_exercicios(S):
    S["profile"]["limitacao"] = "Dor no joelho direito ao agachar"
    for semana in range(1, 21):
        for wk in ("LA", "LB", "FULL"):
            pl = P.plano_do_dia(S, ws(), semana, wk=wk)
            assert not set(ids(pl)) & set(D.ARTICULACOES["joelho"]), (semana, wk)
    pl = P.plano_do_dia(S, ws(), 1, wk="LA")
    assert any("joelho" in m for _, m in pl["bloqueados"])


def test_sintomas_bloqueiam_pernas(S):
    S["checkins"][R.hoje()] = {"dor": 4, "inchaco": False, "fadiga": 2, "sono": 7, "red": False}
    pl = P.plano_do_dia(S, ws(), 1, wk="LA")
    assert ids(pl) == ["ergometro_bracos"]
    assert any("superiores" in a for a in pl["avisos"])
    assert not [x for x in ids(P.plano_do_dia(S, ws(), 1, wk="A")) if D.EXERCICIOS[x].get("requer") == "pernas"]


def test_agenda_pelos_dias_sem_grupo_repetido_em_dias_seguidos():
    grupo = {"A": "sup", "B": "sup", "LA": "inf", "LB": "inf", "FULL": "todo"}
    for dias in range(1, 8):
        ag = P.agenda_para(dias)
        treinos = [d for d in ag.values() if d not in ("OFF", "REC")]
        assert len(treinos) == min(dias, 6) and all(d in D.TREINOS for d in ag.values())
        ordem = [ag[str(d)] for d in (1, 2, 3, 4, 5, 6, 0)]
        for a, b in zip(ordem, ordem[1:]):
            assert not (grupo.get(a) and grupo.get(a) == grupo.get(b)), (dias, a, b)


def test_mudar_perfil_recalcula_sem_apagar_historico(S):
    R.iniciar_sessao(S, "A")
    R.finalizar_sessao(S, "bem", 80)
    antes = [dict(x) for x in S["sessions"]]
    mudou = P.atualizar_perfil(S, {"dias": 3, "pesoInicial": 100.0, "tempoMax": 75})
    assert set(mudou) == {"dias", "pesoInicial", "tempoMax"}
    assert S["schedule"] == P.agenda_para(3)
    assert S["sessions"] == antes
    assert P.plano_do_dia(S, ws(), 3, wk="A")["total"] <= 75


def test_semana_so_avanca_com_execucao_e_recuperacao(S, monkeypatch):
    S["startDate"] = "2026-10-05"  # segunda-feira
    monkeypatch.setattr(R, "hoje", lambda: "2026-10-28")  # 4ª semana do calendário

    def treinar(dias, **extra):
        for d in dias:
            S["sessions"].append({"id": d, "date": d, "workout": "A", "status": "concluida", "ex": [], **extra})

    treinar(["2026-10-05", "2026-10-06", "2026-10-07"])  # semana 1: 3 de 5 → avança
    treinar(["2026-10-12"])  # semana 2: 1 de 5 → repete
    sp = P.semana_do_programa(S)
    assert sp["semana"] == 2 and not sp["historico"][-1]["aprovada"]
    treinar(["2026-10-19", "2026-10-20", "2026-10-21"], recuperacao="ruim")  # 3 de 5, mas recuperação ruim → repete
    sp = P.semana_do_programa(S)
    assert sp["semana"] == 2 and "recuperação ruim" in sp["historico"][-1]["motivo"]
    for s in S["sessions"]:
        s.pop("recuperacao", None)
    assert P.semana_do_programa(S)["semana"] == 3


def test_ajuste_do_usuario_vale_so_para_aquele_treino(S):
    chave = "3|A"
    S["ajustes"][chave] = {"ex": ["supino_maquina", "rosca_maquina"], "cardio": "eliptico",
                           "presc": {"supino_maquina": {"series": 4, "reps": "12", "descanso": 90}}}
    pl = P.plano_do_dia(S, ws(), 3, wk="A")
    assert ids(pl)[:2] == ["supino_maquina", "rosca_maquina"] and cardio(pl)["id"] == "eliptico"
    assert pl["itens"][0]["series"] == 4 and pl["personalizado"]
    assert ids(P.plano_do_dia(S, ws(), 4, wk="A"))[:2] != ["supino_maquina", "rosca_maquina"]


def test_sessao_grava_a_prescricao_do_plano(S):
    R.iniciar_sessao(S, "LA")
    a = S["active"]
    assert all("presc" in e for e in a["ex"]) and a["etapas"]["Aquecimento"] == 10
    assert R.ex_sessao(S, a["ex"][-1])["duracao"] >= 30


def test_exercicios_proibidos_por_nome_saem_do_plano(S):
    S["assess"]["proibidos"] = "Não fazer leg press nem agachamento; rosca martelo também não."
    for semana in range(1, 21):
        for wk in ("A", "B", "LA", "LB", "FULL"):
            pl = P.plano_do_dia(S, ws(), semana, wk=wk)
            assert not set(ids(pl)) & {"leg_press", "agachamento_goblet", "hack_maquina", "rosca_martelo"}, (semana, wk)
    assert "rosca_sentado" in {x for x in D.EXERCICIOS if not P.proibido_por_nome(S, x)}  # só a rosca citada sai
    m = P.motivo_bloqueio(S, "leg_press", 1)
    assert "proibido" in m and "leg press" in m


def test_lesao_em_recuperacao_pede_confirmacao_e_nao_progride(S):
    S["assess"]["lesao"] = "sim"
    assert R.seguranca(S) == "caution"
    assert "não aumente a carga" in R.recomendacao(S, "supino_maquina")
    S["assess"]["lesao"] = "nao_sei"
    assert R.seguranca(S) == "caution"
    S["assess"]["lesao"] = "nao"
    assert R.seguranca(S) == "ok"


def test_troca_de_aparelho_respeita_limitacoes(S):
    S["profile"]["limitacao"] = "dor no joelho"
    alternativas = [x for x in D.ALTERNATIVAS["leg_press"] if not P.motivo_bloqueio(S, x, 3)]
    assert alternativas == []  # agachamento e avanço também forçam o joelho


# ---------------------------------------------------------------- personalização por pessoa
def _perfil(nivel="Iniciante", semente=0):
    S = R.padrao()
    S["profile"].update({"pesoInicial": 100, "pesoMeta": 80, "altura": 175, "idade": 30, "dias": 5, "tempoMax": 120,
                         "nivel": nivel, "confirmado": True})
    S["assess"].update({"done": True, "dor": "nao", "inchaco": "nao", "caminhar": "nao", "diag": "nao",
                        "liberacao": "sim", "lesao": "nao"})
    S["weights"] = [{"id": "w0", "date": "2026-10-01", "peso": 100, "cond": P.PESAGEM_INICIAL}]
    if semente:
        S["semente"] = semente
    return S


def _exercicios(S, semana, wk):
    return [it["id"] for it in P.plano_do_dia(S, "2026-10-05", semana, wk)["itens"]]


def test_contas_diferentes_recebem_treinos_diferentes():
    iguais = sum(_exercicios(_perfil(semente=1), sem, wk) == _exercicios(_perfil(semente=2), sem, wk)
                 for sem in range(1, 21) for wk in ("A", "B", "LA", "LB", "FULL"))
    assert iguais < 100 * 0.5  # mesmo perfil, contas diferentes: a maioria dos treinos difere
    # e a mesma conta continua com o mesmo plano (estável entre acessos)
    assert _exercicios(_perfil(semente=7), 3, "A") == _exercicios(_perfil(semente=7), 3, "A")


def test_nivel_muda_volume_e_exercicios():
    ini, inter, av = _perfil("Iniciante"), _perfil("Intermediário"), _perfil("Avançado")
    assert len(_exercicios(inter, 1, "A")) > len(_exercicios(ini, 1, "A"))  # complementares desde a 1ª semana
    series = {n: [it["series"] for it in P.plano_do_dia(S, "2026-10-05", 10, "A")["itens"] if "duracao" not in it]
              for n, S in (("ini", ini), ("av", av))}
    assert max(series["av"]) == 4 and max(series["ini"]) == 3
    assert any("Avançado" in x for x in P.resumo_personalizacao(av, 10))


def test_peso_inicial_corrige_a_pesagem_do_primeiro_acesso():
    S = _perfil()
    S["profile"]["pesoInicial"] = 90
    S["weights"][0]["peso"] = 90  # digitou 90 no primeiro acesso
    S["profile"]["pesoMeta"] = 90
    assert R.peso_atual(S) == 90 and P.cardio_semanal_alvo(S) == 150
    P.atualizar_perfil(S, {"pesoInicial": 115.0})
    assert R.peso_atual(S) == 115 and P.cardio_semanal_alvo(S) == 250  # Início e plano passam a usar 115
    S["weights"].append({"id": "w1", "date": "2026-10-10", "peso": 112.0, "cond": "", "obs": ""})
    P.atualizar_perfil(S, {"pesoInicial": 116.0})
    assert [w["peso"] for w in R.pesos_ordenados(S)] == [116.0, 112.0]  # pesagens posteriores não mudam


def test_conta_antiga_com_pesagem_inicial_diferente_do_perfil_e_corrigida():
    S = _perfil()
    S["weights"][0]["peso"] = 90  # gravado no primeiro acesso; depois o perfil foi para 100 sem corrigir a pesagem
    S["weights"].append({"id": "w9", "date": "2026-10-20", "peso": 99.0, "cond": "", "obs": ""})
    assert P.sincronizar_pesagem_inicial(S) is True
    assert [w["peso"] for w in R.pesos_ordenados(S)] == [100.0, 99.0]  # pesagens posteriores intactas
    assert P.sincronizar_pesagem_inicial(S) is False  # nada mais a corrigir
    novo = R.padrao()
    novo["weights"] = [{"id": "x", "date": "2026-10-01", "peso": 70, "cond": P.PESAGEM_INICIAL}]
    assert P.sincronizar_pesagem_inicial(novo) is False  # perfil ainda não confirmado: não mexe
