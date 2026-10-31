from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Protocol

TIPOS_CONSULTA: dict[str, str] = {
    "cpf": "Pessoa física — CPF",
    "cnpj_basica": "Pessoa jurídica — CNPJ (cadastro básico)",
    "cnpj_qsa": "Pessoa jurídica — CNPJ + quadro societário",
    "cnpj_empresa": "Pessoa jurídica — CNPJ + QSA + documento dos sócios",
    "cnpj_publico": "Pessoa jurídica — CNPJ em dados públicos",
}


def tipo_e_cpf(tipo: str) -> bool:
    return tipo == "cpf"


class ErroConector(Exception):
    """Falha na consulta. A mensagem é exibida ao usuário e registrada (sem dados pessoais)."""

    codigo = "erro"


class NaoConfigurado(ErroConector):
    codigo = "nao_configurado"


class NaoEncontrado(ErroConector):
    codigo = "nao_encontrado"


class RequisicaoRecusada(ErroConector):
    codigo = "requisicao_recusada"


class CredencialRecusada(ErroConector):
    codigo = "credencial_recusada"


class LimiteExcedido(ErroConector):
    codigo = "limite_excedido"


class FonteIndisponivel(ErroConector):
    codigo = "fonte_indisponivel"


@dataclass
class ResultadoConsulta:
    fonte: str
    fonte_rotulo: str
    ambiente: str  # "producao" (API oficial contratada) | "publica" | "simulado"
    dados: dict
    consultado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    aviso: str | None = None

    def como_dict(self) -> dict:
        return {
            "fonte": self.fonte,
            "fonte_rotulo": self.fonte_rotulo,
            "ambiente": self.ambiente,
            "dados": self.dados,
            "consultado_em": self.consultado_em,
            "aviso": self.aviso,
        }


class Conector(Protocol):
    id: str
    rotulo: str
    tipos: tuple[str, ...]

    def consultar(self, tipo: str, documento: str, nascimento: date | None = None) -> ResultadoConsulta: ...
