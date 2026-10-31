"""Configuração lida exclusivamente de variáveis de ambiente.

Segredos (chaves, credenciais de API) nunca ficam no banco nem no código.
Em produção, use o cofre de segredos do provedor de nuvem para injetar estas variáveis.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(nome: str, padrao: bool = False) -> bool:
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _int(nome: str, padrao: int) -> int:
    valor = os.environ.get(nome)
    return int(valor) if valor not in (None, "") else padrao


def _str(nome: str, padrao: str = "") -> str:
    return os.environ.get(nome, padrao).strip()


class ConfiguracaoInvalida(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    nome_sistema: str = "JurisData"
    ambiente: str = "desenvolvimento"  # desenvolvimento | producao
    database_url: str = "sqlite:///./jurisdata.db"

    # Chave para HMAC (busca por documento sem guardar o número em claro nos logs) e tokens.
    secret_key: str = ""
    # Chave Fernet (base64, 32 bytes) para criptografar dados pessoais e resultados no banco.
    data_key: str = ""

    cookie_secure: bool = True
    sessao_inatividade_min: int = 30
    sessao_maxima_horas: int = 12
    tentativas_login_max: int = 5
    bloqueio_login_min: int = 15

    retencao_dias: int = 365
    limite_diario_consultas: int = 30
    assistente_exige_aprovacao: bool = True

    # Conector simulado: dados FICTÍCIOS, só para desenvolvimento e treinamento.
    modo_simulado: bool = False

    # SERPRO (credenciais do contrato; endpoints devem ser conferidos no API Center).
    serpro_consumer_key: str = ""
    serpro_consumer_secret: str = ""
    serpro_token_url: str = ""
    serpro_cnpj_url: str = ""
    serpro_cpf_url_template: str = ""
    serpro_timeout_s: int = 20

    # BrasilAPI: dados públicos (dados abertos da Receita), não é a API oficial em tempo real.
    brasilapi_habilitada: bool = False
    brasilapi_cnpj_url: str = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

    extras: dict = field(default_factory=dict)

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"

    def validar(self) -> None:
        faltando = [n for n, v in (("JURISDATA_SECRET_KEY", self.secret_key), ("JURISDATA_DATA_KEY", self.data_key)) if not v]
        if faltando:
            raise ConfiguracaoInvalida(
                "Variáveis obrigatórias ausentes: " + ", ".join(faltando) + ". Veja jurisdata/.env.example."
            )
        if len(self.secret_key) < 32:
            raise ConfiguracaoInvalida("JURISDATA_SECRET_KEY deve ter pelo menos 32 caracteres.")
        if self.producao:
            if self.modo_simulado:
                raise ConfiguracaoInvalida("O conector simulado não pode ser ativado em produção.")
            if not self.cookie_secure:
                raise ConfiguracaoInvalida("Em produção o cookie de sessão deve ser Secure (HTTPS).")
            if self.database_url.startswith("sqlite"):
                raise ConfiguracaoInvalida("Em produção use PostgreSQL (JURISDATA_DATABASE_URL).")


def carregar() -> Config:
    return Config(
        ambiente=_str("JURISDATA_AMBIENTE", "desenvolvimento"),
        database_url=_str("JURISDATA_DATABASE_URL", "sqlite:///./jurisdata.db"),
        secret_key=_str("JURISDATA_SECRET_KEY"),
        data_key=_str("JURISDATA_DATA_KEY"),
        cookie_secure=_bool("JURISDATA_COOKIE_SECURE", True),
        sessao_inatividade_min=_int("JURISDATA_SESSAO_INATIVIDADE_MIN", 30),
        sessao_maxima_horas=_int("JURISDATA_SESSAO_MAXIMA_HORAS", 12),
        tentativas_login_max=_int("JURISDATA_TENTATIVAS_LOGIN_MAX", 5),
        bloqueio_login_min=_int("JURISDATA_BLOQUEIO_LOGIN_MIN", 15),
        retencao_dias=_int("JURISDATA_RETENCAO_DIAS", 365),
        limite_diario_consultas=_int("JURISDATA_LIMITE_DIARIO_CONSULTAS", 30),
        assistente_exige_aprovacao=_bool("JURISDATA_ASSISTENTE_EXIGE_APROVACAO", True),
        modo_simulado=_bool("JURISDATA_MODO_SIMULADO", False),
        serpro_consumer_key=_str("JURISDATA_SERPRO_CONSUMER_KEY"),
        serpro_consumer_secret=_str("JURISDATA_SERPRO_CONSUMER_SECRET"),
        serpro_token_url=_str("JURISDATA_SERPRO_TOKEN_URL"),
        serpro_cnpj_url=_str("JURISDATA_SERPRO_CNPJ_URL"),
        serpro_cpf_url_template=_str("JURISDATA_SERPRO_CPF_URL_TEMPLATE"),
        serpro_timeout_s=_int("JURISDATA_SERPRO_TIMEOUT_S", 20),
        brasilapi_habilitada=_bool("JURISDATA_BRASILAPI_HABILITADA", False),
        brasilapi_cnpj_url=_str("JURISDATA_BRASILAPI_CNPJ_URL", "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"),
    )
