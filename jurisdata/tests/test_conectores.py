from dataclasses import replace
from datetime import date

import httpx
import pytest

from app.connectors import Registro
from app.connectors import serpro as serpro_mod
from app.connectors.base import CredencialRecusada, FonteIndisponivel, NaoConfigurado, NaoEncontrado
from app.connectors.serpro import SerproConector

CFG_SERPRO = dict(
    serpro_consumer_key="chave", serpro_consumer_secret="segredo",
    serpro_token_url="https://serpro.test/token",
    serpro_cnpj_url="https://serpro.test/consulta-cnpj/v2",
    serpro_cpf_url_template="https://serpro.test/cpf/v3/{cpf}?nascimento={nascimento_ddmmaaaa}",
)


@pytest.fixture(autouse=True)
def limpar_token():
    serpro_mod._token_cache.clear()
    yield
    serpro_mod._token_cache.clear()


def _cliente(manipulador):
    return httpx.Client(transport=httpx.MockTransport(manipulador))


def test_sem_configuracao_nada_e_oferecido(cfg):
    reg = Registro(replace(cfg, modo_simulado=False))
    assert reg.opcoes() == []
    with pytest.raises(NaoConfigurado):
        SerproConector(cfg).consultar("cpf", "52998224725", date(1980, 5, 10))


def test_template_cpf_sem_nascimento_nao_e_aceito(cfg):
    c = SerproConector(replace(cfg, **{**CFG_SERPRO, "serpro_cpf_url_template": "https://serpro.test/cpf/{cpf}"}))
    assert not c.cpf_configurado and "cpf" not in c.tipos


def test_cpf_monta_url_e_usa_token(cfg):
    chamadas = []

    def manipulador(req: httpx.Request):
        chamadas.append(req)
        if req.url.path == "/token":
            assert req.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert req.headers["authorization"] == "Bearer tok"
        assert str(req.url) == "https://serpro.test/cpf/v3/52998224725?nascimento=10051980"
        return httpx.Response(200, json={"nome": "FULANO", "situacao": {"descricao": "Regular"}})

    c = SerproConector(replace(cfg, **CFG_SERPRO), _cliente(manipulador))
    r = c.consultar("cpf", "52998224725", date(1980, 5, 10))
    assert r.dados["nome"] == "FULANO" and r.ambiente == "producao"
    c.consultar("cpf", "52998224725", date(1980, 5, 10))
    assert sum(1 for ch in chamadas if ch.url.path == "/token") == 1  # token reaproveitado


def test_cnpj_modalidades(cfg):
    caminhos = []

    def manipulador(req):
        if req.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        caminhos.append(req.url.path)
        return httpx.Response(200, json={"ni": "11222333000181"})

    c = SerproConector(replace(cfg, **CFG_SERPRO), _cliente(manipulador))
    for tipo in ("cnpj_basica", "cnpj_qsa", "cnpj_empresa"):
        c.consultar(tipo, "11222333000181")
    assert caminhos == ["/consulta-cnpj/v2/basica/11222333000181", "/consulta-cnpj/v2/qsa/11222333000181",
                        "/consulta-cnpj/v2/empresa/11222333000181"]


def test_token_expirado_e_renovado_uma_vez(cfg):
    tokens = iter(["velho", "novo"])

    def manipulador(req):
        if req.url.path == "/token":
            return httpx.Response(200, json={"access_token": next(tokens), "expires_in": 3600})
        if req.headers["authorization"] == "Bearer velho":
            return httpx.Response(401)
        return httpx.Response(200, json={"ok": True})

    c = SerproConector(replace(cfg, **CFG_SERPRO), _cliente(manipulador))
    assert c.consultar("cnpj_basica", "11222333000181").dados == {"ok": True}


@pytest.mark.parametrize("status,erro", [(404, NaoEncontrado), (403, CredencialRecusada), (503, FonteIndisponivel)])
def test_erros_http(cfg, status, erro):
    def manipulador(req):
        if req.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(status)

    c = SerproConector(replace(cfg, **CFG_SERPRO), _cliente(manipulador))
    with pytest.raises(erro):
        c.consultar("cnpj_basica", "11222333000181")


def test_timeout_vira_fonte_indisponivel(cfg):
    def manipulador(req):
        if req.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        raise httpx.ReadTimeout("lento", request=req)

    c = SerproConector(replace(cfg, **CFG_SERPRO), _cliente(manipulador))
    with pytest.raises(FonteIndisponivel):
        c.consultar("cnpj_basica", "11222333000181")


def test_producao_recusa_configuracao_insegura(cfg):
    from app.config import ConfiguracaoInvalida

    for ajuste in ({"modo_simulado": True}, {"modo_simulado": False, "cookie_secure": False},
                   {"modo_simulado": False}):
        with pytest.raises(ConfiguracaoInvalida):
            replace(cfg, ambiente="producao", **ajuste).validar()
