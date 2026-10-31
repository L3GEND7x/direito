import pyotp
import pytest

from app import audit
from app.models import RegistroAuditoria
from app.security import (
    Cofre,
    conferir_totp,
    mascarar_cpf,
    mascarar_cpfs_em_texto,
    politica_senha,
)
from app.validators import ValorInvalido, normalizar_cnj, normalizar_cnpj, normalizar_cpf


def test_cpf():
    assert normalizar_cpf("529.982.247-25") == "52998224725"
    for invalido in ("529.982.247-26", "111.111.111-11", "123"):
        with pytest.raises(ValorInvalido):
            normalizar_cpf(invalido)


def test_cnpj_numerico_e_alfanumerico():
    assert normalizar_cnpj("11.222.333/0001-81") == "11222333000181"
    with pytest.raises(ValorInvalido):
        normalizar_cnpj("11.222.333/0001-82")
    # Exemplo de CNPJ alfanumérico divulgado pela Receita Federal.
    assert normalizar_cnpj("12.ABC.345/01DE-35") == "12ABC34501DE35"
    with pytest.raises(ValorInvalido):
        normalizar_cnpj("12.ABC.345/01DE-36")


def _cnj_valido(n="0001234", aaaa="2024", j="8", tr="26", oooo="0100"):
    dv = 98 - int(n + aaaa + j + tr + oooo + "00") % 97
    return f"{n}-{dv:02d}.{aaaa}.{j}.{tr}.{oooo}"


def test_numero_cnj():
    numero = _cnj_valido()
    assert normalizar_cnj(numero.replace("-", "").replace(".", "")) == numero
    errado = numero[:8] + ("00" if numero[8:10] != "00" else "01") + numero[10:]
    with pytest.raises(ValorInvalido):
        normalizar_cnj(errado)


def test_mascaras():
    assert mascarar_cpf("52998224725") == "***.982.247-**"
    assert mascarar_cpfs_em_texto("sócio 529.982.247-25 e 52998224725") == "sócio ***.982.247-** e ***.982.247-**"
    # CNPJ não é confundido com CPF
    assert mascarar_cpfs_em_texto("11222333000181") == "11222333000181"


def test_politica_senha():
    assert politica_senha("curta")
    assert politica_senha("Senha-Forte-123!") == []


def test_totp_sem_reuso():
    segredo = pyotp.random_base32()
    codigo = pyotp.TOTP(segredo).now()
    passo = conferir_totp(segredo, codigo, None)
    assert passo is not None
    assert conferir_totp(segredo, codigo, passo) is None  # mesmo código não vale duas vezes
    assert conferir_totp(segredo, "000000" if codigo != "000000" else "111111", None) is None


def test_cofre(cfg):
    cofre = Cofre(cfg.data_key, cfg.secret_key)
    token = cofre.cifrar("52998224725")
    assert "52998224725" not in token
    assert cofre.decifrar(token) == "52998224725"
    assert cofre.hash_documento("52998224725") == cofre.hash_documento("52998224725")


def test_cadeia_de_auditoria_detecta_adulteracao(db):
    for i in range(3):
        audit.registrar(db, "login_ok", None, detalhes={"i": i}, email="x@y.z")
    db.commit()
    assert audit.verificar_cadeia(db) == (True, None, 3)
    reg = db.get(RegistroAuditoria, 2)
    reg.detalhes = {"i": 99}
    db.commit()
    integra, falha, _ = audit.verificar_cadeia(db)
    assert not integra and falha == 2


def test_cadeia_detecta_exclusao(db):
    for i in range(3):
        audit.registrar(db, "login_ok", None, detalhes={"i": i}, email="x@y.z")
    db.commit()
    db.delete(db.get(RegistroAuditoria, 2))
    db.commit()
    assert audit.verificar_cadeia(db)[0] is False
