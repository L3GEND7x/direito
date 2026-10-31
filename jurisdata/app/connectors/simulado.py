"""Conector SIMULADO — dados 100% fictícios, para desenvolvimento e treinamento.

Bloqueado em produção (``Config.validar``). Todo resultado sai marcado como fictício na tela
e no PDF. Datas de nascimento especiais permitem treinar o tratamento de falhas:

* 01/01/1901 → "dados não conferem" (simula CPF + nascimento divergentes);
* 02/02/1902 → fonte indisponível (simula queda da fonte).
"""

from __future__ import annotations

import hashlib
from datetime import date

from ..config import Config
from .base import FonteIndisponivel, NaoConfigurado, NaoEncontrado, RequisicaoRecusada, ResultadoConsulta

AVISO = "DADOS FICTÍCIOS — conector simulado de treinamento. Não utilizar em processo."


class SimuladoConector:
    id = "simulado"
    rotulo = "Simulado (dados fictícios de treinamento)"

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @property
    def tipos(self) -> tuple[str, ...]:
        return ("cpf", "cnpj_basica", "cnpj_qsa", "cnpj_empresa") if self.cfg.modo_simulado else ()

    def consultar(self, tipo: str, documento: str, nascimento: date | None = None) -> ResultadoConsulta:
        if not self.cfg.modo_simulado:
            raise NaoConfigurado("Conector simulado desativado.")
        n = int(hashlib.sha256(documento.encode()).hexdigest()[:6], 16) % 1000
        if tipo == "cpf":
            if nascimento is None:
                raise RequisicaoRecusada("Informe a data de nascimento.")
            if nascimento == date(1901, 1, 1):
                raise NaoEncontrado("Documento não localizado na fonte ou dados informados não conferem.")
            if nascimento == date(1902, 2, 2):
                raise FonteIndisponivel("A fonte está indisponível (simulação). A consulta não foi concluída.")
            dados = {
                "nome": f"PESSOA FICTÍCIA DE TESTE {n:03d}",
                "situacao": {"codigo": "0", "descricao": "Regular"},
                "inscricao": "01/01/2000",
            }
        elif tipo in ("cnpj_basica", "cnpj_qsa", "cnpj_empresa"):
            dados = {
                "razao_social": f"EMPRESA FICTÍCIA DE TESTE {n:03d} LTDA",
                "nome_fantasia": "FICTÍCIA",
                "situacao_cadastral": {"codigo": "2", "descricao": "Ativa"},
                "natureza_juridica": "Sociedade Empresária Limitada (fictício)",
                "municipio": "Cidade Fictícia",
                "uf": "XX",
            }
            if tipo != "cnpj_basica":
                socios = [
                    {"nome": f"SÓCIO FICTÍCIO A {n:03d}", "qualificacao": "Sócio-Administrador"},
                    {"nome": f"SÓCIO FICTÍCIO B {n:03d}", "qualificacao": "Sócio"},
                ]
                if tipo == "cnpj_empresa":
                    socios[0]["cpf"] = "000.000.001-91"
                    socios[1]["cpf"] = "000.000.002-72"
                dados["socios"] = socios
        else:
            raise RequisicaoRecusada("Tipo não atendido pelo conector simulado.")
        return ResultadoConsulta(fonte=self.id, fonte_rotulo=self.rotulo, ambiente="simulado", dados=dados, aviso=AVISO)
