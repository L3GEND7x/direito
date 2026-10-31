"""Primitivas de segurança: senhas, criptografia de dados, HMAC, MFA e mascaramento."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

_ph = PasswordHasher()

SENHA_MIN = 12


def hash_senha(senha: str) -> str:
    return _ph.hash(senha)


def conferir_senha(senha_hash: str, senha: str) -> bool:
    try:
        return _ph.verify(senha_hash, senha)
    except (VerificationError, InvalidHashError):
        return False


# Hash fixo para gastar o mesmo tempo quando o e-mail não existe (evita enumeração por tempo).
HASH_FICTICIO = _ph.hash("senha-ficticia-para-tempo-constante")


def politica_senha(senha: str) -> list[str]:
    problemas = []
    if len(senha) < SENHA_MIN:
        problemas.append(f"ter pelo menos {SENHA_MIN} caracteres")
    if not re.search(r"[a-z]", senha) or not re.search(r"[A-Z]", senha):
        problemas.append("misturar letras maiúsculas e minúsculas")
    if not re.search(r"\d", senha):
        problemas.append("conter ao menos um número")
    if not re.search(r"[^A-Za-z0-9]", senha):
        problemas.append("conter ao menos um símbolo")
    return problemas


def gerar_senha_temporaria() -> str:
    # 4 grupos legíveis + símbolo e dígito garantidos para satisfazer a política.
    base = secrets.token_urlsafe(12).replace("-", "x").replace("_", "y")
    return f"{base[:6]}-{base[6:12]}#A{secrets.randbelow(10)}a"


def novo_token() -> str:
    return secrets.token_urlsafe(32)


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


class Cofre:
    """Criptografia simétrica (Fernet: AES-128-CBC + HMAC-SHA256) e HMAC de documentos."""

    def __init__(self, data_key: str, secret_key: str):
        try:
            self._fernet = Fernet(data_key.encode())
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "JURISDATA_DATA_KEY inválida. Gere com: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            ) from exc
        self._hmac_key = hashlib.sha256(("hmac-documento:" + secret_key).encode()).digest()

    def cifrar(self, texto: str | None) -> str | None:
        if texto is None:
            return None
        return self._fernet.encrypt(texto.encode()).decode()

    def decifrar(self, token: str | None) -> str | None:
        if token is None:
            return None
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Não foi possível decifrar o dado (chave incorreta ou dado corrompido).") from exc

    def cifrar_json(self, dados: dict) -> str:
        return self.cifrar(json.dumps(dados, ensure_ascii=False, default=str))  # type: ignore[return-value]

    def decifrar_json(self, token: str | None) -> dict | None:
        texto = self.decifrar(token)
        return None if texto is None else json.loads(texto)

    def hash_documento(self, digitos: str) -> str:
        return hmac.new(self._hmac_key, digitos.encode(), hashlib.sha256).hexdigest()


# --- MFA (TOTP, RFC 6238) ----------------------------------------------------------------------

def novo_segredo_mfa() -> str:
    return pyotp.random_base32()


def uri_mfa(segredo: str, email: str, emissor: str) -> str:
    return pyotp.TOTP(segredo).provisioning_uri(name=email, issuer_name=emissor)


def conferir_totp(segredo: str, codigo: str, ultimo_passo: int | None) -> int | None:
    """Confere o código (tolerância de ±1 janela) e impede reutilização do mesmo código.

    Retorna o passo de tempo aceito, ou ``None`` se o código for inválido ou já usado.
    """
    codigo = re.sub(r"\D", "", codigo or "")
    if len(codigo) != 6:
        return None
    totp = pyotp.TOTP(segredo)
    passo_atual = int(time.time()) // totp.interval
    for passo in (passo_atual - 1, passo_atual, passo_atual + 1):
        if ultimo_passo is not None and passo <= ultimo_passo:
            continue
        if hmac.compare_digest(totp.at(passo * totp.interval), codigo):
            return passo
    return None


# --- Mascaramento ------------------------------------------------------------------------------

def mascarar_cpf(digitos: str) -> str:
    d = re.sub(r"\D", "", digitos)
    if len(d) != 11:
        return "***"
    return f"***.{d[3:6]}.{d[6:9]}-**"


def mascarar_cnpj(valor: str) -> str:
    # CNPJ identifica a empresa (em regra não é dado pessoal); exibido formatado, sem máscara.
    d = re.sub(r"[^0-9A-Za-z]", "", valor).upper()
    if len(d) != 14:
        return "***"
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def mascarar_documento(valor: str) -> str:
    d = re.sub(r"[^0-9A-Za-z]", "", valor)
    return mascarar_cpf(d) if len(d) == 11 else mascarar_cnpj(d)


_CPF_EM_TEXTO = re.compile(r"(?<!\d)(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?!\d)")


def mascarar_cpfs_em_texto(valor: str) -> str:
    """Mascara qualquer sequência com formato de CPF dentro de um texto (ex.: QSA)."""
    return _CPF_EM_TEXTO.sub(lambda m: f"***.{m.group(2)}.{m.group(3)}-**", valor)
