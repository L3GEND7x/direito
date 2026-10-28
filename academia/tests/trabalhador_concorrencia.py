"""Processo independente usado pelos testes de concorrência (executado com `python este_arquivo.py ...`).

modo "mesma_versao": espera o instante combinado e grava sobre a versão 1.
modo "incrementar": lê, acrescenta uma pesagem e grava N vezes, relendo e repetindo quando houver Conflito.
Imprime uma linha JSON com o resultado.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from foco_leve import armazenamento as A  # noqa: E402
from foco_leve import regras as R  # noqa: E402

modo, db, uid, nome, inicio = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
loja, u = A.LojaSQLite(db), {"id": uid}
while time.time() < inicio:  # todos os processos começam no mesmo instante
    time.sleep(0.0005)
if modo == "mesma_versao":
    S = R.padrao()
    S["profile"]["nome"] = nome
    try:
        loja.salvar(u, S, versao_esperada=1)
        print(json.dumps({"resultado": "ok", "nome": nome}))
    except A.Conflito:
        print(json.dumps({"resultado": "conflito", "nome": nome}))
else:
    vezes, conflitos = int(sys.argv[6]), 0
    for i in range(vezes):
        while True:
            S, v = loja.carregar_com_versao(u)
            S["weights"].append({"id": f"{nome}-{i}", "date": "2026-10-01", "peso": 100.0})
            try:
                loja.salvar(u, S, v)
                break
            except A.Conflito:
                conflitos += 1
    print(json.dumps({"resultado": "ok", "nome": nome, "conflitos": conflitos}))
