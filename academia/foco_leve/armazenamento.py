"""Armazenamento local em SQLite (um registro JSON por usuário, com número de versão)."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .regras import mesclar

CAMINHO_PADRAO = Path(os.environ.get("FOCO_LEVE_DB", Path.home() / ".foco_leve" / "foco_leve.db"))


class Conflito(Exception):
    """Os dados foram salvos por outra aba ou aparelho depois que esta sessão os carregou."""


def _conectar(caminho: Path) -> sqlite3.Connection:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE IF NOT EXISTS estado (usuario TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado TEXT DEFAULT CURRENT_TIMESTAMP)")
    colunas = {r[1] for r in con.execute("PRAGMA table_info(estado)")}
    if "versao" not in colunas:  # bancos criados antes da versão
        con.execute("ALTER TABLE estado ADD COLUMN versao INTEGER NOT NULL DEFAULT 0")
    return con


def versao(usuario: str = "padrao", caminho: Path = CAMINHO_PADRAO) -> int:
    with _conectar(caminho) as con:
        row = con.execute("SELECT versao FROM estado WHERE usuario=?", (usuario,)).fetchone()
    return int(row[0]) if row else 0


def carregar_com_versao(usuario: str = "padrao", caminho: Path = CAMINHO_PADRAO) -> tuple[dict, int]:
    with _conectar(caminho) as con:
        row = con.execute("SELECT dados, versao FROM estado WHERE usuario=?", (usuario,)).fetchone()
    if not row:
        return mesclar(None), 0
    try:
        return mesclar(json.loads(row[0])), int(row[1])
    except (ValueError, TypeError):
        return mesclar(None), int(row[1])


def carregar(usuario: str = "padrao", caminho: Path = CAMINHO_PADRAO) -> dict:
    return carregar_com_versao(usuario, caminho)[0]


def salvar(S: dict, usuario: str = "padrao", caminho: Path = CAMINHO_PADRAO, versao_esperada: int | None = None) -> int:
    """Grava e devolve a nova versão. Com versao_esperada, recusa (Conflito) se outra aba salvou antes."""
    dados = json.dumps({k: v for k, v in S.items() if not k.startswith("_")}, ensure_ascii=False)
    with _conectar(caminho) as con:
        row = con.execute("SELECT versao FROM estado WHERE usuario=?", (usuario,)).fetchone()
        atual = int(row[0]) if row else 0
        if versao_esperada is not None and atual != versao_esperada:
            raise Conflito(f"versão no banco {atual}, esperada {versao_esperada}")
        nova = atual + 1
        if row:
            con.execute("UPDATE estado SET dados=?, versao=?, atualizado=CURRENT_TIMESTAMP WHERE usuario=?", (dados, nova, usuario))
        else:
            con.execute("INSERT INTO estado(usuario,dados,versao) VALUES(?,?,?)", (usuario, dados, nova))
    return nova


def importar_json(texto: str) -> dict:
    """Aceita uma cópia de segurança do app Python ou da versão web; registros malformados são descartados."""
    try:
        o = json.loads(texto)
    except ValueError as e:
        raise ValueError("O arquivo não é um JSON válido.") from e
    if not isinstance(o, dict) or "profile" not in o or not isinstance(o.get("sessions"), list) or not isinstance(o.get("weights"), list):
        raise ValueError("O texto não é uma cópia válida do Foco Leve.")
    S = mesclar(o)
    S["_descartados"] = (len(o["sessions"]) - len(S["sessions"])) + (len(o["weights"]) - len(S["weights"]))
    return S
