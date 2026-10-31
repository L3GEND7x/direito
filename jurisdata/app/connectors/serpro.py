"""Conector SERPRO (Consulta CPF e Consulta CNPJ).

ATENÇÃO — endpoints e formato de requisição NÃO estão fixados no código: devem ser copiados
da documentação do contrato no API Center (https://apicenter.estaleiro.serpro.gov.br) e
informados por variável de ambiente. Motivos:

* CPF v3: o aviso oficial do SERPRO sobre a v3 (vigente desde 29/05/2026) indica o endpoint
  ``https://apicpf.estaleiro.serpro.gov.br/api/v3/cpf/`` — diferente do endereço citado no
  projeto (``gateway.apiserpro.serpro.gov.br/consulta-cpf-df/v3``). A forma de envio da data de
  nascimento [NECESSÁRIO CONFERIR NA DOCUMENTAÇÃO]. Por isso a URL é um modelo configurável com
  os marcadores ``{cpf}``, ``{nascimento_ddmmaaaa}`` e ``{nascimento_iso}``.
  O mesmo aviso informa que não há ambiente de testes da v3: toda chamada é cobrada.
* CNPJ: informe a URL base da versão contratada; o conector acrescenta ``/{modalidade}/{cnpj}``
  (modalidades ``basica``, ``qsa`` e ``empresa``) [CONFERIR NA DOCUMENTAÇÃO DO CONTRATO].

O retorno é guardado como veio da fonte (sem renomear campos), para não presumir um esquema.
"""

from __future__ import annotations

import base64
import threading
import time
from datetime import date

import httpx

from ..config import Config
from .base import (
    CredencialRecusada,
    FonteIndisponivel,
    LimiteExcedido,
    NaoConfigurado,
    NaoEncontrado,
    RequisicaoRecusada,
    ResultadoConsulta,
)

_MODALIDADE = {"cnpj_basica": "basica", "cnpj_qsa": "qsa", "cnpj_empresa": "empresa"}

_token_lock = threading.Lock()
_token_cache: dict[str, tuple[str, float]] = {}


class SerproConector:
    id = "serpro"
    rotulo = "SERPRO / Receita Federal (API oficial contratada)"

    def __init__(self, cfg: Config, cliente: httpx.Client | None = None):
        self.cfg = cfg
        self._cliente = cliente

    # -- disponibilidade ---------------------------------------------------------------------
    @property
    def credenciais_ok(self) -> bool:
        return bool(self.cfg.serpro_consumer_key and self.cfg.serpro_consumer_secret and self.cfg.serpro_token_url)

    @property
    def cpf_configurado(self) -> bool:
        t = self.cfg.serpro_cpf_url_template
        return self.credenciais_ok and "{cpf}" in t and ("{nascimento_ddmmaaaa}" in t or "{nascimento_iso}" in t)

    @property
    def cnpj_configurado(self) -> bool:
        return self.credenciais_ok and bool(self.cfg.serpro_cnpj_url)

    @property
    def tipos(self) -> tuple[str, ...]:
        tipos: list[str] = []
        if self.cpf_configurado:
            tipos.append("cpf")
        if self.cnpj_configurado:
            tipos += list(_MODALIDADE)
        return tuple(tipos)

    # -- HTTP --------------------------------------------------------------------------------
    def _http(self) -> httpx.Client:
        if self._cliente is None:
            self._cliente = httpx.Client(timeout=self.cfg.serpro_timeout_s)
        return self._cliente

    def _token(self, renovar: bool = False) -> str:
        chave = self.cfg.serpro_consumer_key
        with _token_lock:
            em_cache = _token_cache.get(chave)
            if em_cache and not renovar and em_cache[1] > time.time() + 30:
                return em_cache[0]
            basic = base64.b64encode(f"{chave}:{self.cfg.serpro_consumer_secret}".encode()).decode()
            try:
                resp = self._http().post(
                    self.cfg.serpro_token_url,
                    headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
                    data={"grant_type": "client_credentials"},
                )
            except httpx.HTTPError as exc:
                raise FonteIndisponivel("Não foi possível obter o token do SERPRO (falha de comunicação).") from exc
            if resp.status_code in (400, 401, 403):
                raise CredencialRecusada("O SERPRO recusou as credenciais do contrato. Verifique consumer key/secret.")
            if resp.status_code != 200:
                raise FonteIndisponivel(f"Token do SERPRO indisponível (HTTP {resp.status_code}).")
            corpo = resp.json()
            token = corpo.get("access_token")
            if not token:
                raise FonteIndisponivel("Resposta de token do SERPRO sem access_token.")
            _token_cache[chave] = (token, time.time() + float(corpo.get("expires_in", 300)))
            return token

    def _get(self, url: str) -> dict:
        for tentativa in (1, 2):
            token = self._token(renovar=tentativa == 2)
            try:
                resp = self._http().get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            except httpx.TimeoutException as exc:
                raise FonteIndisponivel("A fonte não respondeu no tempo limite. A consulta não foi concluída.") from exc
            except httpx.HTTPError as exc:
                raise FonteIndisponivel("Falha de comunicação com a fonte. A consulta não foi concluída.") from exc
            if resp.status_code == 401 and tentativa == 1:
                continue  # token expirado: renova uma vez
            return self._tratar(resp)
        raise CredencialRecusada("O SERPRO recusou o token de acesso.")

    @staticmethod
    def _tratar(resp: httpx.Response) -> dict:
        s = resp.status_code
        if s == 200:
            try:
                return resp.json()
            except ValueError as exc:
                raise FonteIndisponivel("A fonte devolveu uma resposta que não é JSON.") from exc
        if s == 404:
            raise NaoEncontrado("Documento não localizado na fonte ou dados informados não conferem.")
        if s in (400, 422):
            raise RequisicaoRecusada(f"A fonte recusou a requisição (HTTP {s}). Confira os dados informados.")
        if s in (401, 403):
            raise CredencialRecusada(f"Acesso negado pela fonte (HTTP {s}). Verifique o contrato e as credenciais.")
        if s == 429:
            raise LimiteExcedido("Limite de requisições da fonte atingido. Tente mais tarde.")
        raise FonteIndisponivel(f"A fonte está indisponível (HTTP {s}). A consulta não foi concluída.")

    # -- consulta ----------------------------------------------------------------------------
    def consultar(self, tipo: str, documento: str, nascimento: date | None = None) -> ResultadoConsulta:
        if tipo == "cpf":
            if not self.cpf_configurado:
                raise NaoConfigurado("Consulta CPF do SERPRO não configurada neste ambiente.")
            if nascimento is None:
                raise RequisicaoRecusada("A Consulta CPF v3 exige a data de nascimento.")
            url = (
                self.cfg.serpro_cpf_url_template.replace("{cpf}", documento)
                .replace("{nascimento_ddmmaaaa}", nascimento.strftime("%d%m%Y"))
                .replace("{nascimento_iso}", nascimento.isoformat())
            )
        elif tipo in _MODALIDADE:
            if not self.cnpj_configurado:
                raise NaoConfigurado("Consulta CNPJ do SERPRO não configurada neste ambiente.")
            url = f"{self.cfg.serpro_cnpj_url.rstrip('/')}/{_MODALIDADE[tipo]}/{documento}"
        else:
            raise RequisicaoRecusada("Tipo de consulta não atendido pelo SERPRO.")
        return ResultadoConsulta(fonte=self.id, fonte_rotulo=self.rotulo, ambiente="producao", dados=self._get(url))
