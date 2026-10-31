"""Conector BrasilAPI (projeto open source) — CNPJ a partir de dados públicos.

Não é a API oficial em tempo real: reflete dados abertos publicados pela Receita Federal,
que podem estar defasados. O relatório informa isso expressamente.
"""

from __future__ import annotations

from datetime import date

import httpx

from ..config import Config
from .base import FonteIndisponivel, LimiteExcedido, NaoConfigurado, NaoEncontrado, RequisicaoRecusada, ResultadoConsulta

AVISO = (
    "Fonte pública não oficial (BrasilAPI, baseada em dados abertos da Receita Federal). "
    "Pode não refletir a situação cadastral atual; confirme na fonte oficial antes de juntar aos autos."
)


class BrasilApiConector:
    id = "brasilapi"
    rotulo = "BrasilAPI — dados públicos de CNPJ"

    def __init__(self, cfg: Config, cliente: httpx.Client | None = None):
        self.cfg = cfg
        self._cliente = cliente

    @property
    def tipos(self) -> tuple[str, ...]:
        return ("cnpj_publico",) if self.cfg.brasilapi_habilitada else ()

    def consultar(self, tipo: str, documento: str, nascimento: date | None = None) -> ResultadoConsulta:
        if not self.cfg.brasilapi_habilitada:
            raise NaoConfigurado("Fonte BrasilAPI desabilitada neste ambiente.")
        if tipo != "cnpj_publico":
            raise RequisicaoRecusada("A BrasilAPI só atende consulta pública de CNPJ.")
        if not documento.isdigit():
            raise RequisicaoRecusada("A fonte pública pode não aceitar CNPJ alfanumérico; use a fonte oficial.")
        cliente = self._cliente or httpx.Client(timeout=15)
        try:
            resp = cliente.get(self.cfg.brasilapi_cnpj_url.replace("{cnpj}", documento))
        except httpx.HTTPError as exc:
            raise FonteIndisponivel("Falha de comunicação com a BrasilAPI. A consulta não foi concluída.") from exc
        if resp.status_code == 404:
            raise NaoEncontrado("CNPJ não localizado na base pública.")
        if resp.status_code == 429:
            raise LimiteExcedido("Limite de requisições da BrasilAPI atingido.")
        if resp.status_code != 200:
            raise FonteIndisponivel(f"BrasilAPI indisponível (HTTP {resp.status_code}).")
        return ResultadoConsulta(fonte=self.id, fonte_rotulo=self.rotulo, ambiente="publica", dados=resp.json(), aviso=AVISO)
