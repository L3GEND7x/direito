"""Validação de CPF, CNPJ (numérico e alfanumérico), datas e numeração única CNJ."""

from __future__ import annotations

import re
from datetime import date, datetime


class ValorInvalido(ValueError):
    pass


def normalizar_cpf(valor: str) -> str:
    d = re.sub(r"\D", "", valor or "")
    if len(d) != 11 or d == d[0] * 11:
        raise ValorInvalido("CPF inválido: informe 11 dígitos.")
    for tamanho in (9, 10):
        soma = sum(int(d[i]) * (tamanho + 1 - i) for i in range(tamanho))
        dv = (soma * 10) % 11 % 10
        if dv != int(d[tamanho]):
            raise ValorInvalido("CPF inválido: dígito verificador não confere.")
    return d


def _valor_cnpj(c: str) -> int:
    # Regra do CNPJ alfanumérico (IN RFB 2.229/2024): valor = código ASCII − 48.
    return ord(c) - 48


def normalizar_cnpj(valor: str) -> str:
    v = re.sub(r"[^0-9A-Za-z]", "", valor or "").upper()
    if len(v) != 14 or not re.fullmatch(r"[0-9A-Z]{12}\d{2}", v) or v == v[0] * 14:
        raise ValorInvalido("CNPJ inválido: informe 14 caracteres (12 alfanuméricos + 2 dígitos).")
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(_valor_cnpj(v[i]) * p for i, p in enumerate(pesos))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(v[pos]):
            raise ValorInvalido("CNPJ inválido: dígito verificador não confere.")
    return v


def formatar_cpf(d: str) -> str:
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def formatar_cnpj(v: str) -> str:
    return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"


def ler_data(valor: str, campo: str = "Data") -> date:
    valor = (valor or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d%m%Y"):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            continue
    raise ValorInvalido(f"{campo} inválida: use DD/MM/AAAA.")


def ler_data_opcional(valor: str | None, campo: str = "Data") -> date | None:
    return ler_data(valor, campo) if valor and valor.strip() else None


def validar_nascimento(valor: str) -> date:
    d = ler_data(valor, "Data de nascimento")
    if d > date.today() or d.year < 1900:
        raise ValorInvalido("Data de nascimento fora do intervalo aceito.")
    return d


_CNJ = re.compile(r"^(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})$")


def normalizar_cnj(valor: str) -> str:
    """Valida a numeração única (Resolução CNJ nº 65/2008) e devolve no formato padrão."""
    m = _CNJ.match(re.sub(r"\s", "", valor or ""))
    if not m:
        raise ValorInvalido("Número do processo fora do padrão CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO).")
    n, dd, aaaa, j, tr, oooo = m.groups()
    if int(n + aaaa + j + tr + oooo + dd) % 97 != 1:
        raise ValorInvalido("Número do processo inválido: dígito verificador não confere.")
    return f"{n}-{dd}.{aaaa}.{j}.{tr}.{oooo}"
