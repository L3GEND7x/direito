"""Objetivos, equipamentos, grupos prioritários, biblioteca e acompanhamento automático."""
import itertools
import re

import pytest

from foco_leve import armazenamento as A
from foco_leve import biblioteca as B
from foco_leve import dados as D
from foco_leve import monitoramento as M
from foco_leve import objetivos as O
from foco_leve import plano as P
from foco_leve import regras as R

TREINOS_FORCA = ["A", "B", "LA", "LB", "FULL"]


@pytest.fixture
def S():
    s = R.padrao()
    s["assess"].update({"done": True, "date": R.hoje(), "dor": "nao", "inchaco": "nao", "caminhar": "nao",
                        "diag": "nao", "liberacao": "sim", "lesao": "nao"})
    s["profile"].update({"confirmado": True, "pesoInicial": 90, "pesoMeta": 80, "altura": 175})
    s["weights"] = [{"id": "w0", "date": R.hoje(), "peso": 90, "cond": P.PESAGEM_INICIAL}]
    return s


def ws():
    return R.inicio_semana(R.hoje())


def ids(pl):
    return [it["id"] for it in pl["itens"]]


def forca(pl):
    return [it for it in pl["itens"] if "duracao" not in it]


def cardio_min(pl):
    return sum(it["duracao"] for it in pl["itens"] if D.EXERCICIOS[it["id"]].get("cardio"))


# ---------------------------------------------------------------- compatibilidade
def test_conta_antiga_sem_campos_novos_recebe_o_mesmo_plano(S):
    """Sem objetivos/equipamentos/prioridades salvos, o plano é o de antes (emagrecimento, todos os equipamentos)."""
    explicito = R.mesclar(R.copia(S))
    explicito["profile"].update({"objetivos": ["emagrecimento"], "equipamentos": list(B.EQUIPAMENTOS), "prioridades": []})
    for semana, wk in itertools.product((1, 5, 12, 20), TREINOS_FORCA + ["CARDIO"]):
        a, b = P.plano_do_dia(S, ws(), semana, wk=wk), P.plano_do_dia(explicito, ws(), semana, wk=wk)
        assert a["itens"] == b["itens"] and a["total"] == b["total"], (semana, wk)
    assert O.objetivos(S) == ["emagrecimento"] and O.tem_todos_os_equipamentos(S) and O.prioridades(S) == []


# ---------------------------------------------------------------- todos os objetivos e combinações
COMBINACOES = [[o] for o in O.OBJETIVOS] + [["emagrecimento", "gluteos"], ["hipertrofia", "peitoral"],
                                             ["emagrecimento", "hipertrofia", "condicionamento"], ["gluteos", "peitoral"],
                                             list(O.OBJETIVOS)]


@pytest.mark.parametrize("objs", COMBINACOES, ids=lambda o: "+".join(o))
@pytest.mark.parametrize("nivel", ["Iniciante", "Intermediário", "Avançado"])
def test_cada_objetivo_gera_plano_valido(S, objs, nivel):
    S["profile"].update({"objetivos": objs, "nivel": nivel})
    for dias in (2, 3, 4, 5):
        S["profile"]["dias"] = dias
        S["schedule"] = P.agenda_para(dias, objs)
        for semana in (1, 6, 14):
            for pl in P.plano_da_semana(S, semana, ws()):
                if pl["wk"] in ("OFF", "REC"):
                    continue
                assert len(ids(pl)) == len(set(ids(pl))), pl["wk"]  # sem exercício repetido
                assert all(not P.motivo_bloqueio(S, x, semana) for x in ids(pl))
                assert pl["total"] <= S["profile"]["tempoMax"] + 1
                if pl["wk"] != "CARDIO":
                    assert len(forca(pl)) >= 3, (objs, nivel, dias, pl["wk"])
                if nivel == "Iniciante":
                    assert all(B.meta(x)["dificuldade"] != "avancado" for x in ids(pl))


def test_gluteos_entram_pelo_menos_2_vezes_por_semana(S):
    S["profile"]["objetivos"] = ["gluteos"]
    assert O.prioridades(S) == ["Glúteos"]
    opcoes = set(O.PRIORIDADES["Glúteos"][1])
    for dias in (3, 4, 5):
        S["schedule"] = P.agenda_para(dias, ["gluteos"])
        dias_com_gluteo = [pl for pl in P.plano_da_semana(S, 6, ws()) if set(ids(pl)) & opcoes]
        assert len(dias_com_gluteo) >= 2, dias
    # a vaga prioritária vem logo depois do primeiro composto
    pl = P.plano_do_dia(S, ws(), 6, wk="LB")
    assert ids(pl)[1] in opcoes


def test_peitoral_entra_em_dois_treinos_de_superiores(S):
    S["profile"]["objetivos"] = ["peitoral"]
    peito = {x for x in D.EXERCICIOS if B.grupo(x) == "Peitoral"}
    assert set(ids(P.plano_do_dia(S, ws(), 6, wk="A"))) & peito
    assert set(ids(P.plano_do_dia(S, ws(), 6, wk="B"))) & peito  # B (costas) ganha um exercício de peito


def test_hipertrofia_mais_series_e_cardio_no_minimo(S):
    S["profile"].update({"objetivos": ["hipertrofia"], "nivel": "Intermediário"})
    assert P.cardio_semanal_alvo(S) == 150
    pl = P.plano_do_dia(S, ws(), 6, wk="LA")
    assert cardio_min(pl) <= 30
    compostos = [it for it in forca(pl) if it["id"] not in D.ISOLADOS]
    assert compostos and all(it["series"] == 4 for it in compostos)
    S["profile"]["objetivos"] = ["emagrecimento"]
    assert all(it["series"] == 3 for it in forca(P.plano_do_dia(S, ws(), 6, wk="LA")) if it["id"] not in D.ISOLADOS)
    assert cardio_min(P.plano_do_dia(S, ws(), 6, wk="LA")) >= 30


def test_condicionamento_e_emagrecimento_sobem_o_cardio(S):
    S["profile"]["objetivos"] = ["condicionamento"]
    assert P.cardio_semanal_alvo(S) >= 200
    S["profile"].update({"objetivos": ["emagrecimento"], "pesoMeta": 70})  # 20 kg da meta
    assert P.cardio_semanal_alvo(S) == 250


def test_completo_com_3_dias_e_corpo_inteiro(S):
    assert set(P.agenda_para(3, ["completo"]).values()) == {"FULL", "OFF"}
    assert "A" in P.agenda_para(3, ["emagrecimento"]).values()  # padrão anterior preservado


def test_mudar_objetivo_refaz_so_a_agenda_sugerida(S):
    S["profile"]["dias"] = 3
    S["schedule"] = P.agenda_para(3, ["emagrecimento"])
    P.atualizar_perfil(S, {"objetivos": ["hipertrofia"]})
    assert list(S["schedule"].values()).count("FULL") == 3
    S["schedule"]["2"] = "CARDIO"  # agenda montada à mão
    feita_a_mao = dict(S["schedule"])
    P.atualizar_perfil(S, {"objetivos": ["emagrecimento"]})
    assert S["schedule"] == feita_a_mao


# ---------------------------------------------------------------- equipamentos
@pytest.mark.parametrize("equip", [["halteres", "corpo"], ["corpo"], ["barra", "corpo"], ["maquinas"]])
def test_plano_so_usa_o_equipamento_disponivel(S, equip):
    S["profile"].update({"equipamentos": equip, "objetivos": ["emagrecimento", "gluteos"]})
    for wk in TREINOS_FORCA:
        pl = P.plano_do_dia(S, ws(), 6, wk=wk)
        for x in ids(pl):
            assert set(B.meta(x)["equipamentos"]) & set(equip), (equip, wk, x)
        assert forca(pl), (equip, wk)
        # falta de aparelho não aparece como bloqueio de segurança, só como vaga sem opção
        assert not [m for _, m in pl["bloqueados"] if "Precisa de" in m], (equip, wk)
    if "cardio" not in equip:
        assert "caminhada_livre" in ids(P.plano_do_dia(S, ws(), 6, wk="A"))


def test_iniciante_nao_recebe_exercicio_de_tecnica_avancada(S):
    S["profile"].update({"equipamentos": ["barra"], "nivel": "Iniciante"})
    assert "intermediário" in P.motivo_bloqueio(S, "agachamento_livre", 6)
    S["profile"]["nivel"] = "Intermediário"
    assert P.motivo_bloqueio(S, "agachamento_livre", 6) == ""


# ---------------------------------------------------------------- segurança continua valendo
def test_limitacoes_e_sintomas_valem_com_prioridades(S):
    S["profile"].update({"objetivos": ["gluteos"], "prioridades": ["Quadríceps"], "limitacao": "dor no joelho e no quadril"})
    for wk in ("LA", "LB", "FULL"):
        pl = P.plano_do_dia(S, ws(), 6, wk=wk)
        proibidos = set(D.ARTICULACOES["joelho"]) | set(D.ARTICULACOES["quadril"])
        assert not set(ids(pl)) & proibidos, wk
    S["checkins"][R.hoje()] = {"dor": 6, "inchaco": True, "fadiga": 2, "sono": 7, "red": False}
    pl = P.plano_do_dia(S, ws(), 6, wk="LB")
    assert not [x for x in ids(pl) if D.EXERCICIOS[x].get("requer") == "pernas"]


def test_proibido_por_nome_bloqueia_exercicios_novos(S):
    S["assess"]["proibidos"] = "hip thrust, flexão"
    assert P.motivo_bloqueio(S, "hip_thrust", 6)
    assert P.motivo_bloqueio(S, "flexao_bracos", 6) and P.motivo_bloqueio(S, "flexao_inclinada", 6)
    assert not P.motivo_bloqueio(S, "supino_maquina", 6)


def test_prioridades_no_maximo_duas(S):
    S["profile"].update({"objetivos": ["gluteos", "peitoral"], "prioridades": ["Costas", "Ombros"]})
    assert O.prioridades(S) == ["Glúteos", "Peitoral"]


# ---------------------------------------------------------------- biblioteca
def test_biblioteca_cobre_o_catalogo_e_as_fontes_existem():
    assert set(B._M) == set(D.EXERCICIOS)
    for x in D.EXERCICIOS:
        m = B.meta(x)
        assert m["grupo"] in B.GRUPOS and all(g in B.GRUPOS for g in m["secundarios"])
        assert m["equipamentos"] and all(q in B.EQUIPAMENTOS for q in m["equipamentos"])
        assert m["dificuldade"] in B.DIFICULDADES
        assert all(f in B.REFERENCIAS for f in m["fontes"])
    for texto, url in B.REFERENCIAS.values():
        assert texto and re.match(r"^https://[a-z0-9.-]+\.[a-z]{2,}/\S+$", url), url
    assert all(B.por_grupo(g) for g in B.GRUPOS)
    for g, (_, opcoes, treinos) in O.PRIORIDADES.items():
        assert all(x in D.EXERCICIOS for x in opcoes) and all(w in D.MODELOS for w in treinos), g
    for opcoes in O.EXTRAS_POR_VAGA.values():
        assert all(x in D.EXERCICIOS for x in opcoes)


def test_fotos_dos_exercicios_novos_tem_nome_de_pasta_valido():
    for x in ("hip_thrust", "flexao_bracos", "agachamento_livre", "remada_halter"):
        assert re.match(r"^[A-Za-z0-9_-]+$", D.FOTOS[x])
    # sem foto conferida, sem foto: nada de imagem que mostra outro movimento
    assert "ponte_gluteo" not in D.FOTOS and "caminhada_livre" not in D.FOTOS


def test_peso_do_corpo_sem_carga_sugere_variacao(S):
    S["sessions"] = [{"id": "s1", "date": R.add_dias(R.hoje(), -2), "workout": "A", "status": "concluida", "startedAt": 1,
                      "ex": [{"id": "flexao_inclinada", "sets": [{"done": True, "load": "", "reps": "15"}], "painLevel": "nenhum"}]}]
    assert "variação mais difícil" in R.recomendacao(S, "flexao_inclinada")


# ---------------------------------------------------------------- acompanhamento automático
def sessao(data, ex, status="concluida", n=0):
    return {"id": f"s{data}{n}", "date": data, "workout": "A", "status": status, "startedAt": n,
            "ex": [{"id": i, "sets": [{"done": True, "load": str(c), "reps": "15"} for _ in range(3)], "painLevel": dor}
                   for i, c, dor in ex]}


def textos(S, tela="evolucao"):
    return " | ".join(o["texto"] for o in M.para_tela(S, tela, 20))


def test_sem_registros_nao_inventa_observacoes(S):
    obs = M.observacoes(S)
    assert len(obs) == 1 and "Ainda não há treinos" in obs[0]["texto"]


def test_aumento_de_carga_e_series_por_grupo(S):
    hoje = R.hoje()
    S["sessions"] = [sessao(R.add_dias(hoje, -3), [("supino_maquina", 40, "nenhum"), ("leg_press", 100, "nenhum")], n=1),
                     sessao(R.add_dias(hoje, -1), [("supino_maquina", 45, "nenhum"), ("leg_press", 100, "nenhum")], n=2)]
    t = textos(S)
    assert "aumentou a carga em 1 exercício" in t and "Supino na máquina" in t
    assert "6 de 6 séries" in t
    sg = M.series_por_grupo(S, R.add_dias(hoje, -6), hoje)
    assert sg == {"Peitoral": 6, "Quadríceps": 6}


def test_dor_registrada_vira_alerta_sem_diagnostico(S):
    S["sessions"] = [sessao(R.add_dias(R.hoje(), -1), [("leg_press", 100, "forte")])]
    o = M.observacoes(S)[0]
    assert o["tipo"] == "alerta" and "Leg press" in o["texto"] and "profissional de saúde" in o["texto"]
    assert not re.search(r"lesão|tendinite|diagnóstico", o["texto"], re.I)


def test_queda_de_frequencia_e_dias_sem_treinar(S):
    S["schedule"] = {str(d): ("A" if d in (1, 2, 3, 4, 5) else "OFF") for d in range(7)}
    inicio = ws()
    antigas = [sessao(R.add_dias(inicio, -7 * k + d), [("supino_maquina", 40, "nenhum")], n=k * 10 + d)
               for k in (3, 4) for d in range(5)]
    S["sessions"] = antigas
    t = textos(S, "inicio")
    assert "frequência caiu" in t and "Perfil" in t and "só muda se você confirmar" in t
    assert "dias sem concluir um treino" in t


def test_peso_so_com_pesagens_suficientes(S):
    S["sessions"] = [sessao(R.add_dias(R.hoje(), -1), [("supino_maquina", 40, "nenhum")])]
    assert "Média de peso" not in textos(S)
    S["weights"] = [{"id": f"w{k}", "date": R.add_dias(R.hoje(), -k), "peso": 90 - k * 0.05, "cond": ""} for k in range(0, 28, 3)]
    assert "Média de peso" in textos(S)


def test_observacoes_nao_alteram_o_plano(S):
    S["sessions"] = [sessao(R.add_dias(R.hoje(), -1), [("leg_press", 100, "forte")])]
    antes = R.copia(S)
    M.observacoes(S)
    assert R.copia(S) == antes


# ---------------------------------------------------------------- persistência e isolamento por conta
def test_objetivos_persistem_por_conta_e_nao_vazam(tmp_path, S):
    db = tmp_path / "contas.db"
    ana, bia = {"id": "ana"}, {"id": "bia"}
    sa = R.mesclar(R.copia(S))
    sa["profile"].update({"objetivos": ["gluteos", "emagrecimento"], "equipamentos": ["halteres", "corpo"],
                          "prioridades": ["Glúteos"]})
    sb = R.mesclar(R.copia(S))
    sb["profile"].update({"objetivos": ["peitoral"], "prioridades": []})
    A.LojaSQLite(db).salvar(ana, sa, 0)
    A.LojaSQLite(db).salvar(bia, sb, 0)
    # outro processo / reinício: nova conexão ao mesmo arquivo
    la, lb = A.LojaSQLite(db).carregar_com_versao(ana)[0], A.LojaSQLite(db).carregar_com_versao(bia)[0]
    assert O.objetivos(la) == ["gluteos", "emagrecimento"] and O.equipamentos(la) == {"halteres", "corpo"}
    assert O.objetivos(lb) == ["peitoral"] and O.tem_todos_os_equipamentos(lb)
    pa, pb = P.plano_do_dia(la, ws(), 6, wk="LB"), P.plano_do_dia(lb, ws(), 6, wk="LB")
    assert ids(pa) != ids(pb)
