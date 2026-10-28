"""Conversas, mensagens e fotos do Personal IA, sempre por usuário (sem interface).

Mesma interface em duas implementações, escolhida pela loja de dados já configurada no app:
- ArmazemIASupabase: tabelas de supabase/personal_ia.sql, com o token da pessoa. O Postgres aplica o RLS em toda
  leitura e escrita; o filtro user_id=eq.<id> nas consultas é só uma segunda barreira.
- ArmazemIASQLite: mesmo arquivo do modo local; toda consulta inclui "usuario = ?".
O identificador do usuário vem sempre da sessão autenticada no servidor (st.session_state), nunca do navegador.
"""
from __future__ import annotations

import base64
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from .armazenamento import ErroArmazenamento

TITULO_PADRAO = "Nova conversa"


class AcessoNegado(Exception):
    """Conversa, mensagem ou foto que não existe ou não pertence a quem pediu."""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _desde_24h() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds")


def titulo_de(texto: str) -> str:
    t = " ".join((texto or "").split())
    return (t[:57] + "…") if len(t) > 58 else (t or TITULO_PADRAO)


def para(loja):
    """O armazém de conversas que combina com a loja de dados do app (ou None se não houver)."""
    if loja is None:
        return None
    if loja.tipo == "supabase":
        return ArmazemIASupabase(loja)
    return ArmazemIASQLite(loja.caminho)


# ================================================================ SQLite (modo local)
class ArmazemIASQLite:
    def __init__(self, caminho):
        self.caminho = caminho

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho, timeout=15, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS ia_conversas (id TEXT PRIMARY KEY, usuario TEXT NOT NULL, titulo TEXT NOT NULL,
                resumo TEXT NOT NULL DEFAULT '', resumo_ate INTEGER NOT NULL DEFAULT 0, criada TEXT NOT NULL,
                atualizada TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ia_conversas_dono ON ia_conversas(usuario, atualizada);
            CREATE TABLE IF NOT EXISTS ia_mensagens (id TEXT PRIMARY KEY,
                conversa_id TEXT NOT NULL REFERENCES ia_conversas(id) ON DELETE CASCADE, usuario TEXT NOT NULL,
                papel TEXT NOT NULL CHECK (papel IN ('user','assistant')), texto TEXT NOT NULL, proposta TEXT,
                proposta_estado TEXT, tokens_entrada INTEGER, tokens_saida INTEGER, criada TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ia_mensagens_conversa ON ia_mensagens(conversa_id, criada);
            CREATE TABLE IF NOT EXISTS ia_anexos (id TEXT PRIMARY KEY,
                mensagem_id TEXT NOT NULL REFERENCES ia_mensagens(id) ON DELETE CASCADE, usuario TEXT NOT NULL,
                mime TEXT NOT NULL, largura INTEGER, altura INTEGER, dados BLOB NOT NULL, criada TEXT NOT NULL);
        """)
        return con

    def conversas(self, u: dict) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT id, titulo, atualizada FROM ia_conversas WHERE usuario=? "
                               "ORDER BY atualizada DESC LIMIT 100", (u["id"],)).fetchall()
        finally:
            con.close()
        return [dict(r) for r in rows]

    def criar_conversa(self, u: dict, titulo: str = TITULO_PADRAO) -> dict:
        c = {"id": str(uuid.uuid4()), "titulo": titulo_de(titulo), "resumo": "", "resumo_ate": 0, "atualizada": _agora()}
        con = self._con()
        try:
            con.execute("INSERT INTO ia_conversas(id, usuario, titulo, criada, atualizada) VALUES(?,?,?,?,?)",
                        (c["id"], u["id"], c["titulo"], c["atualizada"], c["atualizada"]))
        finally:
            con.close()
        return c

    def conversa(self, u: dict, cid: str) -> dict | None:
        con = self._con()
        try:
            r = con.execute("SELECT id, titulo, resumo, resumo_ate, atualizada FROM ia_conversas WHERE id=? AND usuario=?",
                            (cid, u["id"])).fetchone()
        finally:
            con.close()
        return dict(r) if r else None

    def renomear(self, u: dict, cid: str, titulo: str) -> None:
        con = self._con()
        try:
            con.execute("UPDATE ia_conversas SET titulo=? WHERE id=? AND usuario=?", (titulo_de(titulo), cid, u["id"]))
        finally:
            con.close()

    def excluir_conversa(self, u: dict, cid: str) -> bool:
        con = self._con()
        try:
            return con.execute("DELETE FROM ia_conversas WHERE id=? AND usuario=?", (cid, u["id"])).rowcount == 1
        finally:
            con.close()

    def mensagens(self, u: dict, cid: str) -> list[dict]:
        con = self._con()
        try:
            rows = con.execute("SELECT id, papel, texto, proposta, proposta_estado, criada FROM ia_mensagens "
                               "WHERE conversa_id=? AND usuario=? ORDER BY criada, rowid", (cid, u["id"])).fetchall()
            fotos = con.execute("SELECT a.id, a.mensagem_id FROM ia_anexos a JOIN ia_mensagens m ON m.id = a.mensagem_id "
                                "WHERE m.conversa_id=? AND a.usuario=? ORDER BY a.criada, a.rowid", (cid, u["id"])).fetchall()
        finally:
            con.close()
        por_msg: dict[str, list[str]] = {}
        for f in fotos:
            por_msg.setdefault(f["mensagem_id"], []).append(f["id"])
        out = []
        for r in rows:
            d = dict(r)
            d["proposta"] = json.loads(d["proposta"]) if d["proposta"] else None
            d["anexos"] = por_msg.get(d["id"], [])
            out.append(d)
        return out

    def adicionar_mensagem(self, u: dict, cid: str, papel: str, texto: str, proposta: dict | None = None,
                           tokens: tuple[int | None, int | None] = (None, None)) -> str:
        mid, agora = str(uuid.uuid4()), _agora()
        con = self._con()
        try:
            con.execute("BEGIN IMMEDIATE")
            if not con.execute("SELECT 1 FROM ia_conversas WHERE id=? AND usuario=?", (cid, u["id"])).fetchone():
                con.execute("ROLLBACK")
                raise AcessoNegado("Conversa não encontrada.")
            con.execute("INSERT INTO ia_mensagens(id, conversa_id, usuario, papel, texto, proposta, proposta_estado, "
                        "tokens_entrada, tokens_saida, criada) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (mid, cid, u["id"], papel, texto, json.dumps(proposta, ensure_ascii=False) if proposta else None,
                         "pendente" if proposta else None, tokens[0], tokens[1], agora))
            con.execute("UPDATE ia_conversas SET atualizada=? WHERE id=?", (agora, cid))
            con.execute("COMMIT")
        finally:
            con.close()
        return mid

    def adicionar_anexo(self, u: dict, mid: str, foto: dict) -> str:
        aid = str(uuid.uuid4())
        con = self._con()
        try:
            if not con.execute("SELECT 1 FROM ia_mensagens WHERE id=? AND usuario=?", (mid, u["id"])).fetchone():
                raise AcessoNegado("Mensagem não encontrada.")
            con.execute("INSERT INTO ia_anexos(id, mensagem_id, usuario, mime, largura, altura, dados, criada) "
                        "VALUES(?,?,?,?,?,?,?,?)", (aid, mid, u["id"], foto["mime"], foto["largura"], foto["altura"],
                                                    foto["bytes"], _agora()))
        finally:
            con.close()
        return aid

    def anexo(self, u: dict, aid: str) -> bytes | None:
        con = self._con()
        try:
            r = con.execute("SELECT dados FROM ia_anexos WHERE id=? AND usuario=?", (aid, u["id"])).fetchone()
        finally:
            con.close()
        return bytes(r["dados"]) if r else None

    def marcar_proposta(self, u: dict, mid: str, estado: str) -> bool:
        con = self._con()
        try:
            return con.execute("UPDATE ia_mensagens SET proposta_estado=? WHERE id=? AND usuario=? "
                               "AND proposta_estado='pendente'", (estado, mid, u["id"])).rowcount == 1
        finally:
            con.close()

    def salvar_resumo(self, u: dict, cid: str, resumo: str, ate: int) -> None:
        con = self._con()
        try:
            con.execute("UPDATE ia_conversas SET resumo=?, resumo_ate=? WHERE id=? AND usuario=?", (resumo, ate, cid, u["id"]))
        finally:
            con.close()

    def uso_24h(self, u: dict) -> dict:
        desde = _desde_24h()
        con = self._con()
        try:
            msgs = con.execute("SELECT count(*) FROM ia_mensagens WHERE usuario=? AND papel='user' AND criada>=?",
                               (u["id"], desde)).fetchone()[0]
            fotos = con.execute("SELECT count(*) FROM ia_anexos WHERE usuario=? AND criada>=?", (u["id"], desde)).fetchone()[0]
        finally:
            con.close()
        return {"mensagens": msgs, "fotos": fotos}


# ================================================================ Supabase (RLS)
class ArmazemIASupabase:
    CONV, MSG, ANX = "foco_leve_ia_conversas", "foco_leve_ia_mensagens", "foco_leve_ia_anexos"
    REP = {"Prefer": "return=representation"}

    def __init__(self, loja):
        self.loja = loja  # LojaSupabase: mesma URL, chave pública e renovação de token

    def _ok(self, r, acao: str):
        if r.status_code in (401, 403) or (r.status_code == 400 and "row-level security" in r.text):
            raise AcessoNegado(f"Sem permissão para {acao}.")
        if r.status_code >= 300:
            raise ErroArmazenamento(f"Não foi possível {acao} (código {r.status_code}).")
        return r.json() if r.text else None

    def _get(self, u, tabela, consulta, acao):
        return self._ok(self.loja._req("GET", f"/rest/v1/{tabela}?{consulta}&user_id=eq.{u['id']}", u), acao)

    def conversas(self, u: dict) -> list[dict]:
        return self._get(u, self.CONV, "select=id,titulo,atualizada&order=atualizada.desc&limit=100", "listar as conversas")

    def criar_conversa(self, u: dict, titulo: str = TITULO_PADRAO) -> dict:
        r = self.loja._req("POST", f"/rest/v1/{self.CONV}", u, headers=self.REP,
                           json={"user_id": u["id"], "titulo": titulo_de(titulo)})
        return self._ok(r, "criar a conversa")[0]

    def conversa(self, u: dict, cid: str) -> dict | None:
        rows = self._get(u, self.CONV, f"select=id,titulo,resumo,resumo_ate,atualizada&id=eq.{cid}", "abrir a conversa")
        return rows[0] if rows else None

    def renomear(self, u: dict, cid: str, titulo: str) -> None:
        self._ok(self.loja._req("PATCH", f"/rest/v1/{self.CONV}?id=eq.{cid}&user_id=eq.{u['id']}", u,
                                json={"titulo": titulo_de(titulo)}), "renomear a conversa")

    def excluir_conversa(self, u: dict, cid: str) -> bool:
        r = self.loja._req("DELETE", f"/rest/v1/{self.CONV}?id=eq.{cid}&user_id=eq.{u['id']}", u, headers=self.REP)
        return bool(self._ok(r, "excluir a conversa"))

    def mensagens(self, u: dict, cid: str) -> list[dict]:
        rows = self._get(u, self.MSG, f"select=id,papel,texto,proposta,proposta_estado,criada&conversa_id=eq.{cid}"
                                      "&order=criada.asc,id.asc", "carregar as mensagens")
        ids = [r["id"] for r in rows]
        por_msg: dict[str, list[str]] = {}
        if ids:
            fotos = self._get(u, self.ANX, f"select=id,mensagem_id&mensagem_id=in.({','.join(ids)})&order=criada.asc",
                              "carregar as fotos")
            for f in fotos:
                por_msg.setdefault(f["mensagem_id"], []).append(f["id"])
        for r in rows:
            r["anexos"] = por_msg.get(r["id"], [])
        return rows

    def adicionar_mensagem(self, u: dict, cid: str, papel: str, texto: str, proposta: dict | None = None,
                           tokens: tuple[int | None, int | None] = (None, None)) -> str:
        corpo = {"conversa_id": cid, "user_id": u["id"], "papel": papel, "texto": texto, "proposta": proposta,
                 "proposta_estado": "pendente" if proposta else None, "tokens_entrada": tokens[0], "tokens_saida": tokens[1]}
        r = self.loja._req("POST", f"/rest/v1/{self.MSG}", u, headers=self.REP, json=corpo)
        return self._ok(r, "salvar a mensagem")[0]["id"]

    def adicionar_anexo(self, u: dict, mid: str, foto: dict) -> str:
        corpo = {"mensagem_id": mid, "user_id": u["id"], "mime": foto["mime"], "largura": foto["largura"],
                 "altura": foto["altura"], "dados": base64.b64encode(foto["bytes"]).decode("ascii")}
        r = self.loja._req("POST", f"/rest/v1/{self.ANX}", u, headers=self.REP, json=corpo)
        return self._ok(r, "salvar a foto")[0]["id"]

    def anexo(self, u: dict, aid: str) -> bytes | None:
        rows = self._get(u, self.ANX, f"select=dados&id=eq.{aid}", "abrir a foto")
        return base64.b64decode(rows[0]["dados"]) if rows else None

    def marcar_proposta(self, u: dict, mid: str, estado: str) -> bool:
        r = self.loja._req("PATCH", f"/rest/v1/{self.MSG}?id=eq.{mid}&user_id=eq.{u['id']}&proposta_estado=eq.pendente",
                           u, headers=self.REP, json={"proposta_estado": estado})
        return bool(self._ok(r, "registrar a decisão"))

    def salvar_resumo(self, u: dict, cid: str, resumo: str, ate: int) -> None:
        self._ok(self.loja._req("PATCH", f"/rest/v1/{self.CONV}?id=eq.{cid}&user_id=eq.{u['id']}", u,
                                json={"resumo": resumo[:12000], "resumo_ate": ate}), "salvar o resumo")

    def uso_24h(self, u: dict) -> dict:
        desde = quote(_desde_24h(), safe="")  # o "+" do fuso viraria espaço na URL
        msgs = self._get(u, self.MSG, f"select=id&papel=eq.user&criada=gte.{desde}&limit=1000", "contar o uso")
        fotos = self._get(u, self.ANX, f"select=id&criada=gte.{desde}&limit=1000", "contar o uso")
        return {"mensagens": len(msgs), "fotos": len(fotos)}
