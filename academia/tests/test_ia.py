"""Personal IA: fotos, segurança, contexto, armazenamento isolado por usuário e serviço de IA.

O serviço é testado com o SDK oficial `anthropic` apontado para tests/ia_falso.py, um servidor local que SIMULA a
API (sem chave real, sem custo). A integração com a API real depende de uma chave em Secrets e não foi executada.
"""
import io
import json
import os

import pytest
from PIL import Image

from foco_leve import armazenamento as A
from foco_leve import ia_context as C
from foco_leve import ia_safety as SEG
from foco_leve import ia_service as SV
from foco_leve import ia_storage as ST
from foco_leve import ia_vision as V
from foco_leve import plano as P
from foco_leve import regras as R
from ia_falso import Falso
from test_armazenamento import Resposta, SupabaseFalso


def _foto(fmt="JPEG", tam=(800, 600), modo="RGB", exif=False) -> bytes:
    img = Image.new(modo, tam, (200, 30, 40) if modo == "RGB" else (200, 30, 40, 128))
    b = io.BytesIO()
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "Fabricante-Secreto"  # Make
        img.save(b, format=fmt, exif=ex.tobytes())
    else:
        img.save(b, format=fmt)
    return b.getvalue()


def _estado(**perfil):
    S = R.padrao()
    S["profile"].update({"nome": "Fulana Privada", "pesoInicial": 100, "pesoMeta": 80, "altura": 170, "idade": 35,
                         "dias": 4, "tempoMax": 90, "nivel": "Iniciante", "confirmado": True, **perfil})
    S["assess"].update({"done": True, "dor": "nao", "inchaco": "nao", "caminhar": "nao", "diag": "nao",
                        "liberacao": "sim", "lesao": "nao"})
    S["weights"] = [{"id": "w1", "date": R.add_dias(R.hoje(), -10), "peso": 100.0, "cond": P.PESAGEM_INICIAL},
                    {"id": "w2", "date": R.hoje(), "peso": 98.4, "cond": ""}]
    return S


# ---------------------------------------------------------------- fotos
def test_fotos_validas_sao_regravadas_sem_metadados():
    for fmt, modo in (("JPEG", "RGB"), ("PNG", "RGBA"), ("WEBP", "RGB")):
        r = V.preparar(_foto(fmt, (3000, 2000), modo, exif=fmt == "JPEG"), 8 * 1024 * 1024)
        assert r["mime"] == "image/jpeg" and max(r["largura"], r["altura"]) == V.LADO_MAXIMO
        img = Image.open(io.BytesIO(r["bytes"]))
        assert img.format == "JPEG" and not img.getexif()
        assert b"Fabricante-Secreto" not in r["bytes"]


def test_fotos_invalidas_e_grandes_sao_recusadas():
    with pytest.raises(V.ImagemInvalida, match="vazio"):
        V.preparar(b"", 1000)
    with pytest.raises(V.ImagemInvalida, match="não é uma foto"):
        V.preparar(b"isto nao e imagem" * 50, 10_000)
    with pytest.raises(V.ImagemInvalida, match="limite"):
        V.preparar(_foto(tam=(2000, 2000)), 1000)
    b = io.BytesIO()
    Image.new("RGB", (10, 10)).save(b, format="GIF")
    with pytest.raises(V.ImagemInvalida, match="Formato"):
        V.preparar(b.getvalue(), 10_000)
    with pytest.raises(V.ImagemInvalida):
        V.preparar(_foto()[:200], 10_000_000)  # arquivo truncado


# ---------------------------------------------------------------- segurança
def test_sinais_de_alerta():
    assert SEG.classificar("Senti uma dor no peito e falta de ar na esteira").nivel == "urgente"
    assert SEG.classificar("Meu joelho inchou e tem uma dor forte").nivel == "lesao"
    assert SEG.classificar("Meu joelho está incomodando").nivel == "desconforto"
    assert SEG.classificar("Hoje estou cansado e só tenho 40 minutos").nivel is None
    S = _estado()
    txt = SEG.instrucao_de_seguranca(SEG.classificar("torci o tornozelo e está inchado"), S)
    assert "avaliação por profissional de saúde" in txt and "Não diagnostique" in txt
    S["checkins"][R.hoje()] = {"dor": 2, "inchaco": False, "fadiga": 2, "red": True}
    assert "não treinar" in SEG.instrucao_de_seguranca(SEG.Alerta(), S)
    assert "192" in SEG.RESPOSTA_URGENTE


def test_mensagem_vazia_ou_longa():
    with pytest.raises(SEG.MensagemInvalida):
        SEG.validar_texto("   ")
    assert SEG.validar_texto("", tem_foto=True) == ""
    with pytest.raises(SEG.MensagemInvalida):
        SEG.validar_texto("x" * (SEG.TEXTO_MAXIMO + 1))


def test_proposta_validada_e_so_aplicada_por_confirmacao():
    S = _estado(limitacao="dor no joelho")
    sem = P.semana_do_programa(S)["semana"]
    prop, avisos = SEG.validar_proposta({"tipo": "treino_da_semana", "resumo": "x", "treino": "LA",
                                         "exercicios": ["leg_press", "inventado", "supino_maquina", "cadeira_flexora"]},
                                        S, sem)
    assert "leg_press" not in prop["exercicios"]  # joelho: bloqueado pelas mesmas regras do plano
    assert "inventado" not in prop["exercicios"] and any("inventado" in a for a in avisos)
    antes = json.dumps(S, sort_keys=True)
    assert SEG.descrever(prop)  # o cartão mostra a proposta...
    assert json.dumps(S, sort_keys=True) == antes  # ...e nada muda sem confirmação
    SEG.aplicar_proposta(prop, S, sem, R.hoje())
    assert S["ajustes"][f"{sem}|LA"]["ex"] == prop["exercicios"]
    perfil, _ = SEG.validar_proposta({"tipo": "perfil", "resumo": "y", "tempo_max": 40, "dias": 9,
                                      "limitacao": "dor no ombro"}, S, sem)
    assert perfil["mudancas"] == {"tempoMax": 40, "limitacao_nova": "dor no ombro"}  # dias=9 ignorado
    SEG.aplicar_proposta(perfil, S, sem, R.hoje())
    assert S["profile"]["tempoMax"] == 40 and S["profile"]["limitacao"] == "dor no joelho; dor no ombro"
    assert SEG.validar_proposta({"tipo": "apagar_tudo", "resumo": "z"}, S, sem)[0] is None
    hoje, _ = SEG.validar_proposta({"tipo": "hoje", "resumo": "descansar", "hoje": "descanso"}, S, sem)
    SEG.aplicar_proposta(hoje, S, sem, R.hoje())
    assert S["dayOverride"][R.hoje()] == "OFF"


# ---------------------------------------------------------------- contexto
def test_contexto_sem_dados_pessoais_desnecessarios_e_com_origem():
    S = _estado()
    ctx = C.montar(S, "Analise minha evolução esta semana", R.hoje())
    assert "Fulana" not in ctx and "@" not in ctx
    assert "[declarado]" in ctx and "[calculado]" in ctx and "98" in ctx
    assert "## Peso" in ctx  # intenção de evolução traz as pesagens
    curto = C.montar(S, "Como posso melhorar minha execução no supino?", R.hoje())
    assert "## Peso" not in curto  # só o necessário
    novo = R.padrao()
    assert "AINDA NÃO INFORMADO" in C.montar(novo, "oi", R.hoje())


# ---------------------------------------------------------------- armazenamento: SQLite
def _isolamento(arm, ana, beto):
    c = arm.criar_conversa(ana, "Meu treino de pernas está pesado demais para mim")
    assert c["titulo"].startswith("Meu treino") and len(c["titulo"]) <= 58
    m = arm.adicionar_mensagem(ana, c["id"], "user", "joelho incomoda")
    foto = V.preparar(_foto(), 8_000_000)
    aid = arm.adicionar_anexo(ana, m, foto)
    arm.adicionar_mensagem(ana, c["id"], "assistant", "Vamos adaptar.", proposta={"tipo": "hoje", "resumo": "descansar"})
    assert [x["id"] for x in arm.conversas(ana)] == [c["id"]]
    msgs = arm.mensagens(ana, c["id"])
    assert [x["papel"] for x in msgs] == ["user", "assistant"] and msgs[0]["anexos"] == [aid]
    assert msgs[1]["proposta_estado"] == "pendente"
    assert arm.anexo(ana, aid) == foto["bytes"]
    # Beto não vê nem mexe em nada da Ana, mesmo sabendo os ids
    assert arm.conversas(beto) == [] and arm.conversa(beto, c["id"]) is None
    assert arm.mensagens(beto, c["id"]) == [] and arm.anexo(beto, aid) is None
    with pytest.raises(ST.AcessoNegado):
        arm.adicionar_mensagem(beto, c["id"], "user", "invasão")
    with pytest.raises(ST.AcessoNegado):
        arm.adicionar_anexo(beto, m, foto)
    assert arm.excluir_conversa(beto, c["id"]) is False
    assert arm.marcar_proposta(beto, msgs[1]["id"], "aplicada") is False
    arm.renomear(beto, c["id"], "hackeado")
    assert arm.conversa(ana, c["id"])["titulo"].startswith("Meu treino")
    assert arm.uso_24h(ana) == {"mensagens": 1, "fotos": 1} and arm.uso_24h(beto) == {"mensagens": 0, "fotos": 0}
    # decisões e resumo
    assert arm.marcar_proposta(ana, msgs[1]["id"], "aplicada") is True
    assert arm.marcar_proposta(ana, msgs[1]["id"], "descartada") is False  # só sai de "pendente" uma vez
    arm.salvar_resumo(ana, c["id"], "- objetivo: emagrecer", 2)
    assert arm.conversa(ana, c["id"])["resumo_ate"] == 2
    # nova conversa não mistura histórico; excluir leva mensagens e fotos junto
    c2 = arm.criar_conversa(ana)
    assert arm.mensagens(ana, c2["id"]) == []
    assert arm.excluir_conversa(ana, c["id"]) is True
    assert arm.mensagens(ana, c["id"]) == [] and arm.anexo(ana, aid) is None
    assert [x["id"] for x in arm.conversas(ana)] == [c2["id"]]


def test_armazem_sqlite_isola_usuarios_e_persiste(tmp_path):
    loja = A.LojaSQLite(tmp_path / "t.db")
    ana, beto = loja.criar_conta("ana@x.com", "senha-segura-1"), loja.criar_conta("beto@x.com", "senha-segura-1")
    _isolamento(ST.para(loja), ana, beto)
    c = ST.para(loja).criar_conversa(ana, "persistente")
    assert c["id"] in [x["id"] for x in ST.para(A.LojaSQLite(tmp_path / "t.db")).conversas(ana)]  # "reinício"


# ---------------------------------------------------------------- armazenamento: Supabase (PostgREST simulado)
class PostgRESTFalso(SupabaseFalso):
    """Imita as três tabelas do Personal IA com as regras de dono de supabase/personal_ia.sql."""

    def __init__(self):
        super().__init__()
        self.t = {"foco_leve_ia_conversas": {}, "foco_leve_ia_mensagens": {}, "foco_leve_ia_anexos": {}}
        self.n = 0

    def request(self, metodo, url, headers=None, json=None, timeout=None):
        caminho = url.split("supabase.test", 1)[1]
        tabela, _, consulta = caminho.removeprefix("/rest/v1/").partition("?")
        if tabela not in self.t:
            return super().request(metodo, url, headers=headers, json=json, timeout=timeout)
        dono = self.tokens.get((headers.get("Authorization") or "").removeprefix("Bearer "))
        if not dono:
            return Resposta(401, {"message": "JWT"})
        filtros = [p.split("=", 1) for p in consulta.split("&") if "=" in p]
        linhas = [r for r in self.t[tabela].values() if r["user_id"] == dono]  # RLS

        def passa(r):
            for k, v in filtros:
                if k in ("select", "order", "limit"):
                    continue
                if v.startswith("eq.") and str(r.get(k)) != v[3:]:
                    return False
                if v.startswith("in.(") and str(r.get(k)) not in v[4:-1].split(","):
                    return False
                if v.startswith("gte.") and str(r.get(k)) < v[4:].replace("%3A", ":").replace("%2B", "+"):
                    return False
            return True

        alvo = [r for r in linhas if passa(r)]
        if metodo == "GET":
            return Resposta(200, sorted(alvo, key=lambda r: r["criada"]))
        if metodo == "POST":
            ok = json["user_id"] == dono
            if tabela == "foco_leve_ia_mensagens":
                c = self.t["foco_leve_ia_conversas"].get(json["conversa_id"])
                ok = ok and c is not None and c["user_id"] == dono
            if tabela == "foco_leve_ia_anexos":
                m = self.t["foco_leve_ia_mensagens"].get(json["mensagem_id"])
                ok = ok and m is not None and m["user_id"] == dono
            if not ok:
                return Resposta(403, {"message": "new row violates row-level security policy"})
            self.n += 1
            r = {"id": f"id{self.n}", "criada": f"2099-01-01T00:00:{self.n:02d}", "atualizada": f"{self.n}",
                 "resumo": "", "resumo_ate": 0, **json}
            self.t[tabela][r["id"]] = r
            return Resposta(201, [r])
        if metodo == "PATCH":
            for r in alvo:
                r.update(json)
            return Resposta(200, alvo)
        if metodo == "DELETE":
            for r in alvo:
                self.t[tabela].pop(r["id"])
                if tabela == "foco_leve_ia_conversas":
                    for m in [m for m in self.t["foco_leve_ia_mensagens"].values() if m["conversa_id"] == r["id"]]:
                        self.t["foco_leve_ia_mensagens"].pop(m["id"])
                        for a in [a for a in self.t["foco_leve_ia_anexos"].values() if a["mensagem_id"] == m["id"]]:
                            self.t["foco_leve_ia_anexos"].pop(a["id"])
            return Resposta(200, alvo)
        return Resposta(405)


def test_armazem_supabase_isola_usuarios():
    falso = PostgRESTFalso()
    loja = A.LojaSupabase("https://x.supabase.test/", "anon-teste", sessao=falso)
    ana, beto = loja.criar_conta("ana@x.com", "senha-segura-1"), loja.criar_conta("beto@x.com", "senha-segura-1")
    _isolamento(ST.para(loja), ana, beto)
    # Beto trocando o próprio id pelo da Ana: o servidor (token) decide quem ele é
    falso_beto = dict(beto, id=ana["id"])
    assert ST.para(loja).conversas(falso_beto) == []


# ---------------------------------------------------------------- serviço de IA (SDK real → servidor simulado)
@pytest.fixture
def api():
    f = Falso()
    yield f
    f.fechar()


def _servico(api, **cfg):
    import anthropic
    c = SV.ConfigIA(api_key="chave-de-teste", **cfg)
    return SV.ServicoIA(c, cliente=anthropic.Anthropic(api_key="chave-de-teste", base_url=api.url, max_retries=0))


def test_config_sem_chave_nao_cria_servico(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert SV.ler_config({}) is None
    cfg = SV.ler_config({"anthropic_api_key": "k", "esforco": "absurdo", "max_tokens": "999999", "limite_mensagens_dia": "x"})
    assert cfg.modelo == "claude-opus-5-5" and cfg.esforco == "medium" and cfg.max_tokens == 64000
    assert cfg.limite_mensagens_dia == 40


def test_resposta_em_streaming_com_contexto_e_foto(api):
    sv = _servico(api)
    S = _estado()
    hist = [{"papel": "user", "texto": "oi", "anexos": ["a1"]}, {"papel": "assistant", "texto": "olá"}]
    foto = V.preparar(_foto(), 8_000_000)["bytes"]
    pedacos = list(sv.responder(hist, "- resumo antigo", C.montar(S, "monte meu treino", R.hoje()), "monte meu treino",
                                [foto], seguranca="instrução X"))
    assert "".join(pedacos) == api.texto and sv.ultimo.texto == api.texto
    assert sv.ultimo.tokens_entrada == 1200 and sv.ultimo.tokens_saida == 42
    corpo = api.pedidos[-1]["corpo"]
    assert corpo["model"] == "claude-opus-5-5" and corpo["stream"] is True
    assert corpo["thinking"] == {"type": "adaptive"} and corpo["output_config"] == {"effort": "medium"}
    assert corpo["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in api.pedidos[-1]["headers"]["anthropic-beta"]
    assert corpo["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert corpo["tools"][0]["name"] == "propor_alteracao"
    atual = corpo["messages"][-1]["content"]
    assert atual[0]["type"] == "image" and atual[0]["source"]["media_type"] == "image/jpeg"
    assert "<contexto_foco_leve>" in atual[1]["text"] and "instrução X" in atual[1]["text"]
    assert "resumo antigo" in corpo["messages"][0]["content"]
    assert "1 foto(s)" in corpo["messages"][1]["content"]  # fotos antigas não são reenviadas
    tudo = json.dumps(corpo, ensure_ascii=False)
    assert "Fulana" not in tudo and "chave-de-teste" not in tudo


def test_proposta_da_ia_vem_separada_do_texto(api):
    sv = _servico(api)
    api.modo = "ferramenta"
    list(sv.responder([], "", "ctx", "pode encurtar meu treino?", []))
    assert sv.ultimo.propostas == [api.proposta]


def test_recusa_e_falhas_do_provedor_nao_viram_resposta_simulada(api):
    sv = _servico(api)
    api.modo = "recusa"
    list(sv.responder([], "", "ctx", "pergunta", []))
    assert sv.ultimo.recusa and "Não posso ajudar" in sv.ultimo.texto
    esperado = {"401": (SV.IAIndisponivel, "chave"), "404": (SV.IAIndisponivel, "modelo"),
                "429": (SV.IAIndisponivel, "muitas solicitações"), "529": (SV.IAIndisponivel, "indisponível"),
                "400": (SV.ErroIA, "não conseguiu processar")}
    for modo, (classe, trecho) in esperado.items():
        api.modo = modo
        with pytest.raises(classe, match=trecho) as e:
            list(sv.responder([], "", "ctx", "pergunta", []))
        assert "chave-de-teste" not in str(e.value)
    api.fechar()
    with pytest.raises(SV.IAIndisponivel, match="conexão"):
        list(sv.responder([], "", "ctx", "pergunta", []))


def test_resumo_da_conversa(api):
    sv = _servico(api)
    assert sv.resumir("", [{"papel": "user", "texto": "quero emagrecer"}]) == "- resumo de teste"
    corpo = api.pedidos[-1]["corpo"]
    assert corpo["output_config"] == {"effort": "low"} and "quero emagrecer" in corpo["messages"][0]["content"]
    assert os.environ.get("ANTHROPIC_API_KEY") in (None, "")  # nenhum teste usou chave real


def test_supabase_sem_a_migracao_do_personal_ia_explica_o_que_falta():
    falso = PostgRESTFalso()
    del falso.t["foco_leve_ia_conversas"]  # personal_ia.sql não rodado: a tabela não existe
    orig = falso.request

    def req(metodo, url, **kw):
        if "foco_leve_ia_conversas" in url:
            return Resposta(404, {"code": "PGRST205", "message": "Could not find the table"})
        return orig(metodo, url, **kw)
    falso.request = req
    loja = A.LojaSupabase("https://x.supabase.test/", "anon-teste", sessao=falso)
    ana = loja.criar_conta("ana@x.com", "senha-segura-1")
    with pytest.raises(A.ErroArmazenamento, match="personal_ia.sql"):
        ST.para(loja).conversas(ana)
