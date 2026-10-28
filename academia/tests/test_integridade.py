"""Integridade dos dados: versões, conflitos entre abas, cópias malformadas, fuso e registros."""
import json
from datetime import datetime, timezone

import pytest

from foco_leve import armazenamento as A
from foco_leve import regras as R


@pytest.fixture
def db(tmp_path):
    return tmp_path / "t.db"


def test_versao_e_conflito_entre_abas(db):
    S = R.padrao()
    v1 = A.salvar(S, caminho=db)
    aba1, va = A.carregar_com_versao(caminho=db)
    aba2, vb = A.carregar_com_versao(caminho=db)
    assert va == vb == v1
    aba1["weights"].append({"id": "a", "date": "2026-10-01", "peso": 110.0})
    v2 = A.salvar(aba1, caminho=db, versao_esperada=va)
    assert v2 == v1 + 1
    aba2["habits"]["2026-10-01"] = {"agua": 5}
    with pytest.raises(A.Conflito):  # a segunda aba não apaga a pesagem da primeira
        A.salvar(aba2, caminho=db, versao_esperada=vb)
    assert A.carregar(caminho=db)["weights"][0]["peso"] == 110.0


def test_banco_antigo_sem_coluna_de_versao(db):
    import sqlite3
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE estado (usuario TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado TEXT)")
    con.execute("INSERT INTO estado(usuario, dados) VALUES('padrao', ?)", (json.dumps({"profile": {"nome": "Ana"}, "sessions": [], "weights": []}),))
    con.commit(); con.close()
    S, v = A.carregar_com_versao(caminho=db)
    assert S["profile"]["nome"] == "Ana" and v == 0
    assert A.salvar(S, caminho=db, versao_esperada=0) == 1


def test_copia_malformada_e_descartada_sem_derrubar():
    texto = json.dumps({"profile": {}, "sessions": [{"date": "x"}, {"date": "2026-10-01", "ex": [{"id": "removido_do_catalogo", "sets": []}]}],
                        "weights": [{"date": "2026-10-01"}, "lixo", {"date": "2026-10-02", "peso": "113,4"}],
                        "checkins": {"ontem": {}, "2026-10-01": "x"}, "habits": [], "active": {"date": "2026-10-01", "ex": [{"id": "zzz"}]}})
    S = A.importar_json(texto)
    assert [w["peso"] for w in S["weights"]] == ["113,4"] and len(S["sessions"]) == 1
    assert S["checkins"] == {} and S["habits"] == {} and S["active"] is None and S["_descartados"] == 3
    R.pesos_ordenados(S)
    with pytest.raises(ValueError):
        A.importar_json("não é json")


def test_dados_de_exemplo_marcados():
    assert R.padrao()["profile"]["confirmado"] is False
    antigo = {"profile": {"pesoInicial": 100}, "assess": {"done": True}, "sessions": [], "weights": []}
    assert R.mesclar(antigo)["profile"]["confirmado"] is True  # quem já usava o app não volta ao passo 1
    assert R.mesclar({"profile": {}, "sessions": [], "weights": []})["profile"]["confirmado"] is False


def test_fuso_define_o_dia(monkeypatch):
    class Relogio(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 29, 2, 30, tzinfo=timezone.utc).astimezone(tz)  # 02:30 UTC

    monkeypatch.setattr(R, "datetime", Relogio)
    R.definir_fuso("America/Manaus")
    assert R.hoje() == "2026-10-28"  # 22:30 em Manaus, ainda dia 28
    R.definir_fuso("nao_existe")
    assert R.hoje() == "2026-10-28" and R.agora().hour == 23  # cai para Brasília
    R.definir_fuso(None)


def test_kcal_registradas_nao_mudam_com_o_peso():
    S = R.padrao()
    S["sessions"].append({"id": "x", "date": R.hoje(), "workout": "A", "status": "concluida", "minutes": 60, "kcal": 400, "ex": []})
    antes = R.energia_semana(S, R.inicio_semana(R.hoje()))["kcal"]
    S["profile"]["pesoInicial"] = 80
    assert R.energia_semana(S, R.inicio_semana(R.hoje()))["kcal"] == antes == 400


def test_remover_exercicio_da_sessao():
    S = R.padrao()
    R.iniciar_sessao(S, "A")
    ids = [e["id"] for e in S["active"]["ex"]]
    uids = [e["uid"] for e in S["active"]["ex"]]
    assert len(set(uids)) == len(uids)
    removido = R.remover_exercicio_sessao(S, 1)
    assert removido["id"] == ids[1] and [e["id"] for e in S["active"]["ex"]] == ids[:1] + ids[2:]
    for e in S["active"]["ex"]:
        e.pop("uid")
    assert R.garantir_uids(S["active"]) and all(e.get("uid") for e in S["active"]["ex"])
