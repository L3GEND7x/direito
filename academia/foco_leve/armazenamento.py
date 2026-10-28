"""Armazenamento do Foco Leve, com contas e um registro JSON versionado por usuário.

Duas implementações com a mesma interface:
- LojaSupabase: banco Postgres persistente do Supabase, via REST. É o armazenamento do app publicado: a autenticação
  é a do Supabase (a senha nunca passa pelo nosso banco) e o isolamento é garantido no próprio Postgres pelas
  políticas de Row Level Security de supabase/schema.sql, não por filtros do Python.
- LojaSQLite: arquivo local, só para desenvolvimento e testes no computador (precisa de FOCO_LEVE_MODO_LOCAL=1).
  Contas com resumo PBKDF2 da senha (nunca a senha), registros isolados por usuário.

Toda gravação é condicional à versão lida ("compare-and-swap"): se outra aba ou aparelho gravou antes, a gravação
é recusada com Conflito em vez de sobrescrever.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from .regras import mesclar

CAMINHO_PADRAO = Path(os.environ.get("FOCO_LEVE_DB", Path.home() / ".foco_leve" / "foco_leve.db"))
LEGADO = "padrao"  # registro único das versões sem contas; só é lido para a migração, nunca gravado
SENHA_MIN = 8
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# Recuperação de senha por link (PKCE): o verificador fica só na memória do servidor, sob uma chave aleatória
# que volta na URL do link. Sem ele o código do link não vale nada. Some ao reiniciar o app (basta pedir de novo).
VALIDADE_LINK = 3600
_LINKS: dict[str, tuple[str, float]] = {}
_TRAVA_LINKS = threading.Lock()


class Conflito(Exception):
    """Os dados foram salvos por outra aba ou aparelho depois que esta sessão os carregou."""


class ErroAutenticacao(Exception):
    """E-mail ou senha inválidos, conta inexistente ou já cadastrada (mensagem pronta para mostrar)."""


class ErroArmazenamento(Exception):
    """Falha de rede ou do banco (mensagem pronta para mostrar)."""


def serializar(S: dict) -> str:
    return json.dumps({k: v for k, v in S.items() if not k.startswith("_")}, ensure_ascii=False)


def validar_credenciais(email: str, senha: str) -> str:
    email = (email or "").strip().lower()
    if not _EMAIL.match(email):
        raise ErroAutenticacao("Informe um e-mail válido.")
    if len(senha or "") < SENHA_MIN:
        raise ErroAutenticacao(f"A senha precisa ter pelo menos {SENHA_MIN} caracteres.")
    return email


# ================================================================ SQLite local
class LojaSQLite:
    tipo = "local"
    recuperacao = False  # sem envio de e-mail no modo local

    def __init__(self, caminho: Path | str = CAMINHO_PADRAO):
        self.caminho = Path(caminho)

    def _con(self) -> sqlite3.Connection:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        # autocommit: as transações são abertas explicitamente com BEGIN IMMEDIATE
        con = sqlite3.connect(self.caminho, timeout=15, isolation_level=None)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE IF NOT EXISTS estado (usuario TEXT PRIMARY KEY, dados TEXT NOT NULL, "
                    "atualizado TEXT DEFAULT CURRENT_TIMESTAMP)")
        if "versao" not in {r[1] for r in con.execute("PRAGMA table_info(estado)")}:  # bancos de antes da versão
            con.execute("ALTER TABLE estado ADD COLUMN versao INTEGER NOT NULL DEFAULT 0")
        con.execute("CREATE TABLE IF NOT EXISTS usuarios (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, "
                    "sal BLOB NOT NULL, hash BLOB NOT NULL, criado TEXT DEFAULT CURRENT_TIMESTAMP)")
        return con

    # ---------------------------------------------------------- contas
    @staticmethod
    def _hash(senha: str, sal: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, 310_000)

    def criar_conta(self, email: str, senha: str) -> dict:
        email = validar_credenciais(email, senha)
        sal = secrets.token_bytes(16)
        uid = uuid.uuid4().hex
        con = self._con()
        try:
            con.execute("INSERT INTO usuarios(id, email, sal, hash) VALUES(?,?,?,?)", (uid, email, sal, self._hash(senha, sal)))
        except sqlite3.IntegrityError as e:
            raise ErroAutenticacao("Já existe uma conta com este e-mail. Use “Entrar”.") from e
        finally:
            con.close()
        return {"id": uid, "email": email}

    def entrar(self, email: str, senha: str) -> dict:
        email = (email or "").strip().lower()
        con = self._con()
        try:
            row = con.execute("SELECT id, sal, hash FROM usuarios WHERE email=?", (email,)).fetchone()
        finally:
            con.close()
        # calcula o hash mesmo sem conta, para não revelar pelo tempo de resposta quais e-mails existem
        sal = row[1] if row else b"\0" * 16
        ok = hmac.compare_digest(self._hash(senha or "", sal), row[2] if row else b"")
        if not (row and ok):
            raise ErroAutenticacao("E-mail ou senha incorretos.")
        return {"id": row[0], "email": email}

    def sair(self, usuario: dict) -> None:
        return None

    def validar(self, usuario: dict) -> None:
        """Confere no banco que a conta da sessão ainda existe."""
        con = self._con()
        try:
            row = con.execute("SELECT 1 FROM usuarios WHERE id=? AND email=?", (usuario["id"], usuario["email"])).fetchone()
        finally:
            con.close()
        if not row:
            raise ErroAutenticacao("Sua sessão não é mais válida. Entre de novo.")

    def enviar_recuperacao(self, email: str, voltar_para: str | None = None) -> None:
        raise ErroAutenticacao("A recuperação de senha por e-mail só existe com o banco Supabase.")

    def abrir_link_recuperacao(self, chave: str, codigo: str) -> dict:
        raise ErroAutenticacao("A recuperação de senha por e-mail só existe com o banco Supabase.")

    def redefinir_senha(self, email: str, codigo: str, nova: str) -> dict:
        raise ErroAutenticacao("A recuperação de senha por e-mail só existe com o banco Supabase.")

    # ---------------------------------------------------------- dados
    def apagar(self, usuario: dict) -> None:
        """Apaga os dados da própria conta (a conta continua existindo)."""
        con = self._con()
        try:
            con.execute("DELETE FROM estado WHERE usuario=?", (usuario["id"],))
        finally:
            con.close()

    def versao(self, usuario: dict) -> int:
        con = self._con()
        try:
            row = con.execute("SELECT versao FROM estado WHERE usuario=?", (usuario["id"],)).fetchone()
        finally:
            con.close()
        return int(row[0]) if row else 0

    def carregar_com_versao(self, usuario: dict) -> tuple[dict, int]:
        return self._ler(usuario["id"])

    def _ler(self, chave: str) -> tuple[dict, int]:
        con = self._con()
        try:
            row = con.execute("SELECT dados, versao FROM estado WHERE usuario=?", (chave,)).fetchone()
        finally:
            con.close()
        if not row:
            return mesclar(None), 0
        try:
            return mesclar(json.loads(row[0])), int(row[1])
        except (ValueError, TypeError):
            return mesclar(None), int(row[1])

    def salvar(self, usuario: dict, S: dict, versao_esperada: int) -> int:
        """Grava se a versão no banco ainda for a esperada; devolve a nova versão ou levanta Conflito.

        A verificação e a escrita acontecem no mesmo comando (UPDATE ... WHERE versao = ?), dentro de uma
        transação BEGIN IMMEDIATE: duas gravações simultâneas sobre a mesma versão nunca são ambas aceitas."""
        dados = serializar(S)
        con = self._con()
        try:
            con.execute("BEGIN IMMEDIATE")
            # bancos de antes da numeração têm linhas com versão 0: também são atualizadas pelo filtro de versão
            cur = con.execute("UPDATE estado SET dados=?, versao=versao+1, atualizado=CURRENT_TIMESTAMP "
                              "WHERE usuario=? AND versao=?", (dados, usuario["id"], versao_esperada))
            if cur.rowcount != 1:
                if versao_esperada != 0:
                    raise Conflito(f"a versão no banco não é mais {versao_esperada}")
                try:
                    con.execute("INSERT INTO estado(usuario, dados, versao) VALUES(?,?,1)", (usuario["id"], dados))
                except sqlite3.IntegrityError as e:
                    raise Conflito("já existe registro para este usuário") from e
            con.execute("COMMIT")
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return versao_esperada + 1

    # ---------------------------------------------------------- registro da versão sem contas (migração pendente)
    # O app não mostra esse registro a ninguém: o dono não pode ser identificado com segurança. Quem administra
    # o servidor decide com migrar_legado.py, que faz backup antes e nunca apaga o registro original.
    def tem_legado(self) -> bool:
        con = self._con()
        try:
            return con.execute("SELECT 1 FROM estado WHERE usuario=?", (LEGADO,)).fetchone() is not None
        finally:
            con.close()

    def carregar_legado(self) -> dict:
        return self._ler(LEGADO)[0]

    def guardar_backup_legado(self, pasta: Path | None = None) -> Path:
        """Cópia em arquivo do registro antigo, exatamente como está no banco."""
        con = self._con()
        try:
            row = con.execute("SELECT dados FROM estado WHERE usuario=?", (LEGADO,)).fetchone()
        finally:
            con.close()
        destino = Path(pasta or self.caminho.parent) / f"backup-legado-{datetime.now():%Y%m%d-%H%M%S-%f}.json"
        destino.write_text(row[0] if row else "{}", encoding="utf-8")
        return destino

    def atribuir_legado(self, email: str) -> Path:
        """Copia o registro antigo para a conta indicada, depois de gravar um backup. Recusa se a conta já tiver dados
        ou se o registro já tiver sido atribuído a alguém. O registro original fica intacto."""
        con = self._con()
        try:
            con.execute("CREATE TABLE IF NOT EXISTS legado_atribuido (usuario TEXT NOT NULL, backup TEXT NOT NULL, "
                        "quando TEXT DEFAULT CURRENT_TIMESTAMP)")
            row = con.execute("SELECT id, email FROM usuarios WHERE email=?", ((email or "").strip().lower(),)).fetchone()
            ja = con.execute("SELECT usuario FROM legado_atribuido").fetchone()
        finally:
            con.close()
        if not self.tem_legado():
            raise ValueError("Não há registro da versão sem contas neste banco.")
        if not row:
            raise ValueError("Não existe conta com este e-mail. A pessoa precisa criar a conta no app antes.")
        if ja:
            raise ValueError("Este registro já foi atribuído a uma conta.")
        usuario = {"id": row[0], "email": row[1]}
        if self.versao(usuario):
            raise ValueError("A conta já tem dados; para não sobrescrever nada, a atribuição foi cancelada.")
        backup = self.guardar_backup_legado()
        self.salvar(usuario, self.carregar_legado(), 0)
        con = self._con()
        try:
            con.execute("INSERT INTO legado_atribuido(usuario, backup) VALUES(?,?)", (usuario["id"], str(backup)))
        finally:
            con.close()
        return backup


# ================================================================ Supabase
class LojaSupabase:
    """Cliente mínimo das APIs de autenticação (GoTrue) e de dados (PostgREST) do Supabase.

    Usa a chave pública (anon) do projeto e o token de acesso de cada usuário: o servidor só devolve e
    só aceita gravar a linha do próprio usuário (Row Level Security)."""
    tipo = "supabase"
    recuperacao = True
    TABELA = "foco_leve_estado"

    def __init__(self, url: str, chave_anon: str, sessao=None, tempo_limite: float = 15):
        import requests  # dependência do próprio Streamlit
        self.url = url.rstrip("/")
        self.chave = chave_anon
        # sem Session compartilhada: a mesma loja atende todos os usuários do servidor e não deve guardar cookies
        self.http = sessao or requests
        self.tempo_limite = tempo_limite

    # ---------------------------------------------------------- HTTP
    def _req(self, metodo: str, caminho: str, usuario: dict | None = None, headers: dict | None = None,
             renovado: bool = False, **kw):
        cab = {"apikey": self.chave, "Content-Type": "application/json", **(headers or {})}
        if usuario:
            cab["Authorization"] = f"Bearer {usuario['token']}"
        try:
            r = self.http.request(metodo, f"{self.url}{caminho}", headers=cab, timeout=self.tempo_limite, **kw)
        except Exception as e:  # noqa: BLE001 - qualquer falha de rede vira mensagem para a tela
            raise ErroArmazenamento("Sem conexão com o banco de dados. Verifique a internet e tente de novo.") from e
        if r.status_code == 401 and usuario and usuario.get("refresh") and not renovado:
            self._renovar(usuario)  # token de acesso expirou (dura 1 h): renova uma vez e repete
            return self._req(metodo, caminho, usuario, headers=headers, renovado=True, **kw)
        if r.status_code == 429:
            raise ErroAutenticacao(self._limite(caminho))
        return r

    @staticmethod
    def _limite(caminho: str) -> str:
        """Mensagem para o limite de pedidos do Supabase (HTTP 429), conforme o que foi pedido."""
        if caminho.startswith(("/auth/v1/signup", "/auth/v1/recover")):
            return ("O limite de e-mails do servidor foi atingido (cadastros e recuperações de senha enviam e-mail). "
                    "Aguarde alguns minutos — se continuar, até 1 hora — e tente de novo.")
        if caminho.startswith("/auth/v1/token"):
            return "Muitas tentativas de entrada em pouco tempo. Aguarde alguns minutos e tente de novo."
        return "Muitos pedidos em pouco tempo. Aguarde alguns minutos e tente de novo."

    def _renovar(self, usuario: dict) -> None:
        r = self._req("POST", "/auth/v1/token?grant_type=refresh_token", json={"refresh_token": usuario["refresh"]})
        if r.status_code != 200:
            raise ErroAutenticacao("Sua sessão expirou. Entre de novo.")
        d = r.json()
        usuario.update({"token": d["access_token"], "refresh": d.get("refresh_token", usuario["refresh"]),
                        "expira": time.time() + int(d.get("expires_in", 3600))})

    @staticmethod
    def _usuario(d: dict) -> dict:
        return {"id": d["user"]["id"], "email": d["user"].get("email", ""), "token": d["access_token"],
                "refresh": d.get("refresh_token"), "expira": time.time() + int(d.get("expires_in", 3600))}

    # ---------------------------------------------------------- contas
    def criar_conta(self, email: str, senha: str) -> dict:
        email = validar_credenciais(email, senha)
        r = self._req("POST", "/auth/v1/signup", json={"email": email, "password": senha})
        if r.status_code in (400, 422):
            raise ErroAutenticacao("Não foi possível criar a conta com estes dados (e-mail já cadastrado ou senha fraca).")
        if r.status_code >= 300:
            raise ErroArmazenamento(f"O servidor recusou o cadastro (código {r.status_code}).")
        d = r.json()
        if not d.get("access_token"):  # projeto exige confirmação por e-mail
            raise ErroAutenticacao("Conta criada. Confirme pelo link enviado ao seu e-mail e depois use “Entrar”.")
        return self._usuario(d)

    def entrar(self, email: str, senha: str) -> dict:
        r = self._req("POST", "/auth/v1/token?grant_type=password",
                      json={"email": (email or "").strip().lower(), "password": senha or ""})
        if r.status_code in (400, 401):
            raise ErroAutenticacao("E-mail ou senha incorretos, ou e-mail ainda não confirmado.")
        if r.status_code >= 300:
            raise ErroArmazenamento(f"O servidor recusou a entrada (código {r.status_code}).")
        return self._usuario(r.json())

    def sair(self, usuario: dict) -> None:
        try:
            self._req("POST", "/auth/v1/logout", usuario)
        except (ErroArmazenamento, ErroAutenticacao):
            pass

    def validar(self, usuario: dict) -> None:
        """Pergunta ao servidor de autenticação de quem é o token desta sessão (renovando-o se expirou)."""
        r = self._req("GET", "/auth/v1/user", usuario)
        if r.status_code != 200 or (r.json() or {}).get("id") != usuario["id"]:
            raise ErroAutenticacao("Sua sessão não é mais válida. Entre de novo.")

    def enviar_recuperacao(self, email: str, voltar_para: str | None = None) -> None:
        """Pede ao Supabase o e-mail de recuperação. A resposta não revela se o e-mail tem conta.

        O link do e-mail volta para `voltar_para` com ?rec=<chave>&code=<código>; o código só é trocado por uma
        sessão junto com o verificador PKCE guardado aqui no servidor (abrir_link_recuperacao)."""
        email = (email or "").strip().lower()
        if not _EMAIL.match(email):
            raise ErroAutenticacao("Informe um e-mail válido.")
        verificador = secrets.token_urlsafe(48)
        desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
        chave = secrets.token_urlsafe(16)
        agora = time.time()
        with _TRAVA_LINKS:
            for k in [k for k, (_, ate) in _LINKS.items() if ate < agora]:
                del _LINKS[k]
            _LINKS[chave] = (verificador, agora + VALIDADE_LINK)
        caminho = "/auth/v1/recover"
        if voltar_para:
            caminho += "?redirect_to=" + quote(f"{voltar_para.rstrip('/')}/?rec={chave}", safe="")
        r = self._req("POST", caminho, json={"email": email, "code_challenge": desafio, "code_challenge_method": "s256"})
        if r.status_code >= 500:
            raise ErroArmazenamento(f"O servidor não enviou o e-mail (código {r.status_code}). Tente mais tarde.")

    def abrir_link_recuperacao(self, chave: str, codigo: str) -> dict:
        """Troca o código do link do e-mail (uso único) por uma sessão, com o verificador guardado no servidor."""
        with _TRAVA_LINKS:
            item = _LINKS.pop(chave or "", None)
        if not item or item[1] < time.time() or not codigo:
            raise ErroAutenticacao("Este link de recuperação venceu ou já foi usado. Peça um novo e-mail.")
        r = self._req("POST", "/auth/v1/token?grant_type=pkce", json={"auth_code": codigo, "code_verifier": item[0]})
        if r.status_code != 200 or not r.json().get("access_token"):
            raise ErroAutenticacao("Este link de recuperação venceu ou já foi usado. Peça um novo e-mail.")
        return self._usuario(r.json())

    def definir_senha(self, usuario: dict, nova: str) -> None:
        if len(nova or "") < SENHA_MIN:
            raise ErroAutenticacao(f"A senha precisa ter pelo menos {SENHA_MIN} caracteres.")
        r = self._req("PUT", "/auth/v1/user", usuario, json={"password": nova})
        if r.status_code != 200:
            raise ErroAutenticacao("O servidor recusou a nova senha (fraca ou igual à anterior). Escolha outra.")

    def redefinir_senha(self, email: str, codigo: str, nova: str) -> dict:
        """Confere o código numérico do e-mail (modelo com {{ .Token }}) e grava a nova senha."""
        email = validar_credenciais(email, nova)
        codigo = re.sub(r"\s", "", codigo or "")
        if not codigo.isdigit():
            raise ErroAutenticacao("Digite o código numérico que chegou no e-mail.")
        r = self._req("POST", "/auth/v1/verify", json={"type": "recovery", "email": email, "token": codigo})
        if r.status_code != 200 or not r.json().get("access_token"):
            raise ErroAutenticacao("Código inválido ou vencido. Peça um novo e-mail de recuperação.")
        usuario = self._usuario(r.json())
        self.definir_senha(usuario, nova)
        return usuario

    # ---------------------------------------------------------- dados
    def _linha(self, usuario: dict, campos: str):
        r = self._req("GET", f"/rest/v1/{self.TABELA}?select={campos}&user_id=eq.{usuario['id']}", usuario)
        if r.status_code != 200:
            raise ErroArmazenamento(f"Não foi possível ler seus dados (código {r.status_code}).")
        linhas = r.json()
        return linhas[0] if linhas else None

    def versao(self, usuario: dict) -> int:
        row = self._linha(usuario, "versao")
        return int(row["versao"]) if row else 0

    def carregar_com_versao(self, usuario: dict) -> tuple[dict, int]:
        row = self._linha(usuario, "dados,versao")
        if not row:
            return mesclar(None), 0
        return mesclar(row["dados"]), int(row["versao"])

    def salvar(self, usuario: dict, S: dict, versao_esperada: int) -> int:
        dados = json.loads(serializar(S))
        pref = {"Prefer": "return=representation"}
        if versao_esperada == 0:
            r = self._req("POST", f"/rest/v1/{self.TABELA}", usuario, headers=pref,
                          json={"user_id": usuario["id"], "dados": dados, "versao": 1})
            if r.status_code == 409:
                raise Conflito("já existe registro para este usuário")
        else:
            # atualização condicional: o filtro versao=eq.N e a escrita são um único UPDATE no Postgres
            r = self._req("PATCH", f"/rest/v1/{self.TABELA}?user_id=eq.{usuario['id']}&versao=eq.{versao_esperada}",
                          usuario, headers=pref, json={"dados": dados, "versao": versao_esperada + 1})
            if r.status_code == 200 and r.json() == []:
                raise Conflito(f"a versão no banco não é mais {versao_esperada}")
        if r.status_code not in (200, 201):
            raise ErroArmazenamento(f"Não foi possível salvar (código {r.status_code}). Seus dados desta tela não foram gravados.")
        return versao_esperada + 1

    def apagar(self, usuario: dict) -> None:
        r = self._req("DELETE", f"/rest/v1/{self.TABELA}?user_id=eq.{usuario['id']}", usuario)
        if r.status_code not in (200, 204):
            raise ErroArmazenamento(f"Não foi possível apagar os dados (código {r.status_code}).")

    def tem_legado(self) -> bool:
        return False


# ================================================================ configuração
def configurar(secrets_: dict | None = None):
    """Supabase quando houver URL e chave em st.secrets["supabase"] ou nas variáveis de ambiente.

    Sem Supabase, o SQLite local só é usado se FOCO_LEVE_MODO_LOCAL=1 (desenvolvimento no computador). Caso
    contrário devolve None e o app não abre dados pessoais: um arquivo SQLite no servidor público seria
    compartilhado pelo processo e apagado a cada reinício."""
    sb = dict((secrets_ or {}).get("supabase") or {})
    url = sb.get("url") or os.environ.get("SUPABASE_URL")
    chave = sb.get("anon_key") or os.environ.get("SUPABASE_ANON_KEY")
    if url and chave:
        if chave.startswith("sb_secret_") or _papel_jwt(chave) == "service_role":
            raise ValueError("A chave configurada é secreta (service_role/secret), que ignora o RLS. "
                             "Use a chave pública: anon ou publishable.")
        return LojaSupabase(url, chave)
    if os.environ.get("FOCO_LEVE_MODO_LOCAL") == "1":
        return LojaSQLite(os.environ.get("FOCO_LEVE_DB") or CAMINHO_PADRAO)
    return None


def _papel_jwt(chave: str) -> str | None:
    """Papel ("anon" ou "service_role") declarado numa chave JWT do Supabase, sem validar a assinatura."""
    try:
        meio = chave.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(meio + "=" * (-len(meio) % 4))).get("role")
    except (IndexError, ValueError, AttributeError):
        return None


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
