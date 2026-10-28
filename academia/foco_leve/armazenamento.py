"""Armazenamento local em SQLite (um registro JSON por usuário)."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .regras import mesclar

CAMINHO_PADRAO = Path(os.environ.get("FOCO_LEVE_DB", Path.home() / ".foco_leve" / "foco_leve.db"))


def _conectar(caminho: Path) -> sqlite3.Connection:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE IF NOT EXISTS estado (usuario TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado TEXT DEFAULT CURRENT_TIMESTAMP)")
    return con


def carregar(usuario: str = "padrao", caminho: Path = CAMINHO_PADRAO) -> dict:
    with _conectar(caminho) as con:
        row = con.execute("SELECT dados FROM estado WHERE usuario=?", (usuario,)).fetchone()
    if not row:
        return mesclar(None)
    try:
        return mesclar(json.loads(row[0]))
    except (ValueError, TypeError):
        return mesclar(None)


def salvar(S: dict, usuario: str = "padrao", caminho: Path = CAMINHO_PADRAO) -> None:
    dados = json.dumps({k: v for k, v in S.items() if not k.startswith("_")}, ensure_ascii=False)
    with _conectar(caminho) as con:
        con.execute("INSERT INTO estado(usuario,dados,atualizado) VALUES(?,?,CURRENT_TIMESTAMP) "
                    "ON CONFLICT(usuario) DO UPDATE SET dados=excluded.dados, atualizado=CURRENT_TIMESTAMP", (usuario, dados))


def importar_json(texto: str) -> dict:
    """Aceita uma cópia de segurança do app Python ou da versão web."""
    o = json.loads(texto)
    if not isinstance(o, dict) or "profile" not in o or not isinstance(o.get("sessions"), list) or not isinstance(o.get("weights"), list):
        raise ValueError("O texto não é uma cópia válida do Foco Leve.")
    return mesclar(o)
