"""Decisão sobre o registro da versão sem contas (migração pendente).

As versões antigas do Foco Leve guardavam um único registro, chamado "padrao", compartilhado por todos que abriam o
link. Não há como saber de quem ele é, por isso o app não o mostra a ninguém. Quem administra o servidor decide:

  python migrar_legado.py listar   [--banco CAMINHO]
  python migrar_legado.py exportar --saida arquivo.json [--banco CAMINHO]
  python migrar_legado.py atribuir --email pessoa@exemplo.com --confirmar [--banco CAMINHO]   (só modo local)

- listar: mostra quantos registros existem, sem alterar nada.
- exportar: grava uma cópia .json. Com Supabase, entregue o arquivo à pessoa certa: ela entra na própria conta e usa
  Perfil → Cópia de segurança → Restaurar. Assim nenhuma chave administrativa é necessária.
- atribuir: no banco SQLite local, copia o registro para a conta indicada (que precisa existir e estar vazia),
  depois de gravar um backup ao lado do banco.

Nada é apagado: o registro original continua no banco.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from foco_leve import armazenamento as A


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["listar", "exportar", "atribuir"])
    ap.add_argument("--banco", default=str(A.CAMINHO_PADRAO), help="arquivo SQLite da versão anterior")
    ap.add_argument("--saida", help="arquivo .json de destino (exportar)")
    ap.add_argument("--email", help="conta que recebe o registro (atribuir)")
    ap.add_argument("--confirmar", action="store_true", help="confirma a atribuição (atribuir)")
    a = ap.parse_args(argv)
    if not Path(a.banco).exists():
        print(f"Banco não encontrado: {a.banco}")
        return 1
    loja = A.LojaSQLite(a.banco)
    if not loja.tem_legado():
        print("Não há registro da versão sem contas neste banco.")
        return 0
    antigo = loja.carregar_legado()
    if a.acao == "listar":
        print(f"Registro sem dono: {len(antigo['sessions'])} treino(s), {len(antigo['weights'])} pesagem(ns), "
              f"{len(antigo['habits'])} dia(s) de hábitos. Nome no perfil: {antigo['profile'].get('nome') or '(vazio)'}")
        return 0
    if a.acao == "exportar":
        if not a.saida:
            ap.error("informe --saida")
        destino = Path(a.saida)
        if destino.exists():
            print(f"{destino} já existe; escolha outro nome para não sobrescrever.")
            return 1
        destino.write_text(A.serializar(antigo), encoding="utf-8")
        print(f"Cópia gravada em {destino}.")
        return 0
    if not a.email or not a.confirmar:
        ap.error("atribuir exige --email e --confirmar")
    try:
        backup = loja.atribuir_legado(a.email)
    except ValueError as e:
        print(f"Nada foi alterado: {e}")
        return 1
    print(f"Registro copiado para {a.email}. Backup em {backup}. O registro original foi mantido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
