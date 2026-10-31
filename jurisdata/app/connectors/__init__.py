"""Registro de conectores. Cada fonte é independente: trocar de fornecedor = trocar o conector."""

from __future__ import annotations

from ..config import Config
from .base import TIPOS_CONSULTA, ErroConector, NaoConfigurado, ResultadoConsulta
from .brasilapi import BrasilApiConector
from .serpro import SerproConector
from .simulado import SimuladoConector

__all__ = ["TIPOS_CONSULTA", "ErroConector", "ResultadoConsulta", "Registro"]


class Registro:
    def __init__(self, cfg: Config, conectores: list | None = None):
        self.cfg = cfg
        self.conectores = conectores if conectores is not None else [
            SerproConector(cfg),
            BrasilApiConector(cfg),
            SimuladoConector(cfg),
        ]

    def por_id(self, fonte: str):
        for c in self.conectores:
            if c.id == fonte:
                return c
        raise NaoConfigurado(f"Fonte desconhecida: {fonte}")

    def opcoes(self) -> list[tuple[str, str, str]]:
        """Combinações disponíveis (tipo, fonte, rótulo) para o formulário."""
        saida = []
        for tipo, rotulo_tipo in TIPOS_CONSULTA.items():
            for c in self.conectores:
                if tipo in c.tipos:
                    saida.append((tipo, c.id, f"{rotulo_tipo} · {c.rotulo}"))
        return saida

    def disponivel(self, tipo: str, fonte: str) -> bool:
        return any(t == tipo and f == fonte for t, f, _ in self.opcoes())

    def situacao(self) -> list[dict]:
        """Resumo para a tela de configurações (sem expor segredos)."""
        serpro = self.por_id("serpro") if any(c.id == "serpro" for c in self.conectores) else None
        linhas = []
        if serpro is not None:
            linhas.append({"fonte": "SERPRO — credenciais", "ok": serpro.credenciais_ok})
            linhas.append({"fonte": "SERPRO — Consulta CPF", "ok": serpro.cpf_configurado})
            linhas.append({"fonte": "SERPRO — Consulta CNPJ", "ok": serpro.cnpj_configurado})
        linhas.append({"fonte": "BrasilAPI — CNPJ público", "ok": self.cfg.brasilapi_habilitada})
        linhas.append({"fonte": "Simulado (fictício)", "ok": self.cfg.modo_simulado})
        linhas.append({"fonte": "SENATRAN — veículos", "ok": False, "nota": "Depende de aprovação (TAAD)."})
        return linhas
