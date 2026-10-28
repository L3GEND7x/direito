"""Armazenamento: concorrência real entre processos, contas, isolamento, migração, backup e cliente Supabase."""
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from foco_leve import armazenamento as A
from foco_leve import regras as R

@pytest.fixture
def loja(tmp_path):
    return A.LojaSQLite(tmp_path / "t.db")


# ---------------------------------------------------------------- concorrência (processos separados)
TRABALHADOR = Path(__file__).with_name("trabalhador_concorrencia.py")


def _processos(args_por_processo):
    """Inicia processos Python independentes que gravam no mesmo banco no mesmo instante e devolve o que cada um imprimiu."""
    inicio = time.time() + 1.5
    ps = [subprocess.Popen([sys.executable, str(TRABALHADOR), *a[:4], str(inicio), *a[4:]], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True) for a in args_por_processo]
    saidas = []
    for p in ps:
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0, err
        saidas.append(json.loads(out.strip().splitlines()[-1]))
    return saidas


def test_gravacoes_simultaneas_so_uma_vence(tmp_path):
    for rodada in range(8):
        db = tmp_path / f"c{rodada}.db"
        u = {"id": "u1"}
        A.LojaSQLite(db).salvar(u, R.padrao(), 0)
        res = _processos([("mesma_versao", str(db), "u1", f"aba{i}") for i in range(4)])
        vencedores = [r["nome"] for r in res if r["resultado"] == "ok"]
        assert len(vencedores) == 1, res  # nunca duas gravações aceitas sobre a mesma versão
        S, v = A.LojaSQLite(db).carregar_com_versao(u)
        assert v == 2 and S["profile"]["nome"] == vencedores[0]


def test_ler_alterar_gravar_concorrente_sem_perda(tmp_path):
    db = tmp_path / "inc.db"
    A.LojaSQLite(db).salvar({"id": "u1"}, R.padrao(), 0)
    res = _processos([("incrementar", str(db), "u1", f"p{k}", "15") for k in range(3)])
    assert sorted(r["nome"] for r in res) == ["p0", "p1", "p2"]
    S, v = A.LojaSQLite(db).carregar_com_versao({"id": "u1"})
    assert len(S["weights"]) == 45 and v == 46  # nenhuma das 45 gravações se perdeu


def test_conflito_desfaz_a_transacao(loja):
    u = {"id": "u1"}
    loja.salvar(u, R.padrao(), 0)
    with pytest.raises(A.Conflito):
        loja.salvar(u, R.padrao(), 0)  # inserir de novo
    with pytest.raises(A.Conflito):
        loja.salvar(u, R.padrao(), 7)  # versão errada
    assert loja.versao(u) == 1


# ---------------------------------------------------------------- contas e isolamento
def test_contas_e_isolamento(loja):
    ana = loja.criar_conta("Ana@Exemplo.com ", "senha-segura-1")
    beto = loja.criar_conta("beto@exemplo.com", "outra-senha-2")
    assert ana["id"] != beto["id"] and ana["email"] == "ana@exemplo.com"
    with pytest.raises(A.ErroAutenticacao):
        loja.criar_conta("ana@exemplo.com", "qualquer-coisa")
    with pytest.raises(A.ErroAutenticacao):
        loja.entrar("ana@exemplo.com", "errada!!!")
    with pytest.raises(A.ErroAutenticacao):
        loja.entrar("ninguem@exemplo.com", "senha-segura-1")
    with pytest.raises(A.ErroAutenticacao):
        loja.criar_conta("sem-arroba", "senha-segura-1")
    with pytest.raises(A.ErroAutenticacao):
        loja.criar_conta("c@exemplo.com", "curta")
    assert loja.entrar("ANA@exemplo.com", "senha-segura-1")["id"] == ana["id"]
    S = R.padrao()
    S["weights"].append({"id": "w", "date": "2026-10-01", "peso": 99.0})
    loja.salvar(ana, S, 0)
    assert loja.carregar_com_versao(beto) == (R.mesclar(None), 0)  # Beto não vê nada da Ana
    with pytest.raises(A.Conflito):
        loja.salvar(beto, S, 1)  # nem consegue gravar na versão da Ana
    assert loja.carregar_com_versao(ana)[0]["weights"][0]["peso"] == 99.0
    con = sqlite3.connect(loja.caminho)
    senhas = con.execute("SELECT hash FROM usuarios").fetchall()
    assert all(b"senha" not in h[0] for h in senhas)  # a senha não fica gravada em texto


def _banco_antigo(loja, antigo):
    con = sqlite3.connect(loja.caminho)
    con.execute("CREATE TABLE estado (usuario TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado TEXT)")
    con.execute("INSERT INTO estado(usuario, dados) VALUES(?, ?)", (A.LEGADO, json.dumps(antigo)))
    con.commit()
    con.close()


ANTIGO = {"profile": {"nome": "Ana"}, "assess": {"done": True}, "sessions": [], "weights": [{"id": "w", "date": "2026-09-01", "peso": 115}]}


def test_registro_sem_dono_fica_pendente_e_nunca_e_apagado(loja):
    _banco_antigo(loja, ANTIGO)
    assert loja.tem_legado() and loja.carregar_legado()["profile"]["nome"] == "Ana"
    u = loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    assert loja.carregar_com_versao(u) == (R.mesclar(None), 0)  # conta nova não recebe nada automaticamente
    with pytest.raises(ValueError):
        loja.atribuir_legado("ninguem@exemplo.com")  # conta inexistente
    cheio = loja.criar_conta("cheio@exemplo.com", "senha-segura-1")
    loja.salvar(cheio, R.padrao(), 0)
    with pytest.raises(ValueError):
        loja.atribuir_legado("cheio@exemplo.com")  # nunca sobrescreve uma conta com dados
    backup = loja.atribuir_legado("ana@exemplo.com")
    assert json.loads(backup.read_text())["weights"][0]["peso"] == 115  # backup gravado antes
    assert loja.carregar_com_versao(u)[0]["weights"][0]["peso"] == 115
    assert loja.tem_legado()  # o original continua no banco
    beto = loja.criar_conta("beto@exemplo.com", "senha-segura-1")
    with pytest.raises(ValueError):
        loja.atribuir_legado("beto@exemplo.com")  # só pode ser atribuído uma vez
    assert loja.carregar_com_versao(beto)[1] == 0


def test_script_de_migracao(tmp_path, capsys):
    import migrar_legado
    loja = A.LojaSQLite(tmp_path / "t.db")
    _banco_antigo(loja, ANTIGO)
    banco = ["--banco", str(loja.caminho)]
    assert migrar_legado.main(["listar", *banco]) == 0 and "1 pesagem" in capsys.readouterr().out
    saida = tmp_path / "copia.json"
    assert migrar_legado.main(["exportar", "--saida", str(saida), *banco]) == 0
    assert A.importar_json(saida.read_text())["weights"][0]["peso"] == 115
    assert migrar_legado.main(["exportar", "--saida", str(saida), *banco]) == 1  # não sobrescreve
    loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    with pytest.raises(SystemExit):
        migrar_legado.main(["atribuir", "--email", "ana@exemplo.com", *banco])  # sem --confirmar
    assert migrar_legado.main(["atribuir", "--email", "ana@exemplo.com", "--confirmar", *banco]) == 0
    assert loja.tem_legado()


def test_apagar_e_validar_so_a_propria_conta(loja):
    ana = loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    beto = loja.criar_conta("beto@exemplo.com", "senha-segura-1")
    loja.salvar(ana, R.padrao(), 0)
    loja.salvar(beto, R.padrao(), 0)
    loja.apagar(beto)
    assert loja.versao(beto) == 0 and loja.versao(ana) == 1
    loja.validar(ana)
    with pytest.raises(A.ErroAutenticacao):
        loja.validar({"id": ana["id"], "email": "beto@exemplo.com"})  # identidade montada à mão
    with pytest.raises(A.ErroAutenticacao):
        loja.enviar_recuperacao("ana@exemplo.com")  # sem e-mail no modo local


# ---------------------------------------------------------------- backup e restauração
def test_backup_e_restauracao_preservam_os_registros(loja):
    u = loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    S = R.padrao()
    S["profile"].update({"nome": "Ana", "confirmado": True})
    S["weights"] = [{"id": "a", "date": "2026-10-01", "peso": 110.2, "cintura": 101.0, "cond": "x", "obs": ""}]
    R.iniciar_sessao(S, "A")
    R.marcar_serie(S, 0, 0, True)
    R.finalizar_sessao(S, "bem", 80, rpe_sessao=6, fadiga=3, recuperacao="boa")
    S["habits"]["2026-10-01"] = {"agua": 8}
    v = loja.salvar(u, S, 0)
    copia = A.serializar(loja.carregar_com_versao(u)[0])  # o que o botão "Baixar cópia" entrega
    outra = loja.criar_conta("outra@exemplo.com", "senha-segura-2")
    restaurado = A.importar_json(copia)
    assert restaurado.pop("_descartados") == 0
    loja.salvar(outra, restaurado, 0)
    a, b = loja.carregar_com_versao(u)[0], loja.carregar_com_versao(outra)[0]
    assert json.loads(A.serializar(a)) == json.loads(A.serializar(b)) and v == 1
    # a cópia não leva identidade nem token, e restaurar numa conta não mexe na outra
    assert u["id"] not in copia and "token" not in copia and "ana@exemplo.com" not in copia
    b["weights"].append({"id": "b", "date": "2026-10-02", "peso": 70.0, "cintura": None, "cond": "", "obs": ""})
    loja.salvar(outra, b, 1)
    assert [w["peso"] for w in loja.carregar_com_versao(u)[0]["weights"]] == [110.2]


# ---------------------------------------------------------------- cliente Supabase (servidor simulado)
class Resposta:
    def __init__(self, status, corpo=None):
        self.status_code, self._corpo = status, corpo
        self.text = json.dumps(corpo) if corpo is not None else ""

    def json(self):
        return self._corpo


class SupabaseFalso:
    """Imita GoTrue + PostgREST com Row Level Security: cada token só alcança a linha do próprio usuário."""

    def __init__(self):
        self.usuarios, self.tokens, self.linhas, self.chamadas = {}, {}, {}, []
        self.expirar_proximo = False
        self.fora_do_ar = False
        self.emitidos = 0
        self.limite = False  # simula o HTTP 429 (limite de pedidos/e-mails do Supabase)
        self.codigos = {}
        self.links = {}  # e-mail -> endereço do link de recuperação (o que a pessoa abriria)
        self.pkce = {}  # código do link -> (uid, desafio)

    def _sessao(self, uid):
        self.emitidos += 1
        tok = f"tok-{uid}-{self.emitidos}"
        self.tokens[tok] = uid
        return {"access_token": tok, "refresh_token": f"ref-{uid}", "expires_in": 3600, "user": {"id": uid, "email": self.usuarios[uid][0]}}

    def request(self, metodo, url, headers=None, json=None, timeout=None):
        assert headers["apikey"] == "anon-teste"
        self.chamadas.append((metodo, url))
        if self.fora_do_ar:
            raise ConnectionError("sem rede")
        if self.limite:
            return Resposta(429, {"msg": "email rate limit exceeded"})
        caminho = url.split("supabase.test", 1)[1]
        if caminho == "/auth/v1/signup":
            if any(e == json["email"] for e, _ in self.usuarios.values()):
                return Resposta(422, {"msg": "User already registered"})
            uid = f"uid-{len(self.usuarios) + 1}"
            self.usuarios[uid] = (json["email"], json["password"])
            return Resposta(200, self._sessao(uid))
        if caminho == "/auth/v1/token?grant_type=password":
            for uid, (e, s) in self.usuarios.items():
                if e == json["email"] and s == json["password"]:
                    return Resposta(200, self._sessao(uid))
            return Resposta(400, {"error": "invalid_grant"})
        if caminho == "/auth/v1/token?grant_type=refresh_token":
            uid = json["refresh_token"].removeprefix("ref-")
            return Resposta(200, self._sessao(uid))
        if caminho == "/auth/v1/logout":
            return Resposta(204)
        if caminho.startswith("/auth/v1/recover"):
            self.codigos[json["email"]] = "123456"  # o e-mail com o código; a resposta é igual com ou sem conta
            uid = next((u for u, (e, _) in self.usuarios.items() if e == json["email"]), None)
            if uid and json.get("code_challenge"):
                from urllib.parse import parse_qs, urlsplit
                volta = parse_qs(urlsplit(caminho).query).get("redirect_to", ["https://site-url.test/"])[0]
                codigo = f"pkce-{len(self.pkce) + 1}"
                self.pkce[codigo] = (uid, json["code_challenge"])
                self.links[json["email"]] = volta + ("&" if "?" in volta else "?") + "code=" + codigo
            return Resposta(200, {})
        if caminho == "/auth/v1/token?grant_type=pkce":
            import base64
            import hashlib
            uid, desafio = self.pkce.pop(json["auth_code"], (None, None))
            calc = base64.urlsafe_b64encode(hashlib.sha256(json["code_verifier"].encode()).digest()).rstrip(b"=").decode()
            if not uid or calc != desafio:
                return Resposta(400, {"msg": "invalid flow state"})
            return Resposta(200, self._sessao(uid))
            return Resposta(200, {})
        if caminho == "/auth/v1/verify":
            uid = next((u for u, (e, _) in self.usuarios.items() if e == json["email"]), None)
            if json["type"] != "recovery" or not uid or self.codigos.pop(json["email"], None) != json["token"]:
                return Resposta(403, {"msg": "Token has expired or is invalid"})
            return Resposta(200, self._sessao(uid))
        tok = (headers.get("Authorization") or "").removeprefix("Bearer ")
        if self.expirar_proximo:
            self.expirar_proximo = False
            self.tokens.pop(tok, None)
        if tok not in self.tokens:
            return Resposta(401, {"message": "JWT expired"})
        dono = self.tokens[tok]
        if caminho == "/auth/v1/user":
            if metodo == "PUT":
                self.usuarios[dono] = (self.usuarios[dono][0], json["password"])
            return Resposta(200, {"id": dono, "email": self.usuarios[dono][0]})
        tabela, _, consulta = caminho.removeprefix("/rest/v1/").partition("?")
        assert tabela == "foco_leve_estado"
        filtros = dict(p.split("=", 1) for p in consulta.split("&") if "=" in p and not p.startswith("select"))
        alvo = filtros.get("user_id", "").removeprefix("eq.")
        if metodo == "GET":
            linha = self.linhas.get(alvo) if alvo == dono else None  # RLS: só a própria linha
            return Resposta(200, [linha] if linha else [])
        if metodo == "POST":
            if json["user_id"] != dono:
                return Resposta(403, {"message": "new row violates row-level security policy"})
            if dono in self.linhas:
                return Resposta(409, {"message": "duplicate key"})
            self.linhas[dono] = {"dados": json["dados"], "versao": json["versao"]}
            return Resposta(201, [self.linhas[dono]])
        if metodo == "PATCH":
            linha = self.linhas.get(alvo) if alvo == dono else None
            if not linha or str(linha["versao"]) != filtros.get("versao", "").removeprefix("eq."):
                return Resposta(200, [])  # nenhuma linha atendeu o filtro
            linha.update(json)
            return Resposta(200, [linha])
        if metodo == "DELETE":
            if alvo == dono:
                self.linhas.pop(dono, None)
            return Resposta(204)
        return Resposta(405)


@pytest.fixture
def supa():
    falso = SupabaseFalso()
    return A.LojaSupabase("https://x.supabase.test/", "anon-teste", sessao=falso), falso


def test_supabase_contas_isolamento_e_conflito(supa):
    loja, falso = supa
    ana = loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    beto = loja.criar_conta("beto@exemplo.com", "senha-segura-2")
    with pytest.raises(A.ErroAutenticacao):
        loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    with pytest.raises(A.ErroAutenticacao):
        loja.entrar("ana@exemplo.com", "errada!!!")
    ana = loja.entrar("ana@exemplo.com", "senha-segura-1")
    S = R.padrao()
    S["profile"]["nome"] = "Ana"
    assert loja.salvar(ana, S, 0) == 1
    assert loja.carregar_com_versao(beto) == (R.mesclar(None), 0)  # isolamento
    falso_beto = dict(beto, id=ana["id"])  # Beto tentando se passar pela Ana com o próprio token
    assert loja.carregar_com_versao(falso_beto) == (R.mesclar(None), 0)
    with pytest.raises(A.ErroArmazenamento):
        loja.salvar(falso_beto, S, 0)  # inserir na linha de outro: 403 da RLS
    with pytest.raises(A.Conflito):
        loja.salvar(falso_beto, S, 1)  # atualizar a linha de outro: o filtro não alcança nada
    with pytest.raises(A.Conflito):
        loja.salvar(ana, S, 0)
    assert loja.salvar(ana, S, 1) == 2
    with pytest.raises(A.Conflito):
        loja.salvar(ana, S, 1)  # outra aba que ainda achava que era a versão 1
    assert loja.carregar_com_versao(ana)[0]["profile"]["nome"] == "Ana" and loja.versao(ana) == 2


def test_supabase_renova_token_e_trata_queda_de_rede(supa):
    loja, falso = supa
    u = loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    token_antigo = u["token"]
    falso.expirar_proximo = True
    assert loja.versao(u) == 0 and u["token"] != token_antigo  # renovou e repetiu a chamada
    falso.fora_do_ar = True
    with pytest.raises(A.ErroArmazenamento):
        loja.versao(u)


def test_supabase_recuperacao_de_senha(supa):
    loja, falso = supa
    loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    loja.enviar_recuperacao("ninguem@exemplo.com")  # não revela que o e-mail não tem conta
    loja.enviar_recuperacao("ana@exemplo.com")
    with pytest.raises(A.ErroAutenticacao):
        loja.redefinir_senha("ana@exemplo.com", "000000", "nova-senha-123")
    loja.enviar_recuperacao("ana@exemplo.com")
    u = loja.redefinir_senha("ana@exemplo.com", " 123 456 ", "nova-senha-123")
    assert u["email"] == "ana@exemplo.com"
    with pytest.raises(A.ErroAutenticacao):
        loja.entrar("ana@exemplo.com", "senha-segura-1")
    assert loja.entrar("ana@exemplo.com", "nova-senha-123")["id"] == u["id"]


def test_supabase_recuperacao_por_link_pkce(supa):
    from urllib.parse import parse_qs, urlsplit
    loja, falso = supa
    loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    loja.enviar_recuperacao("ana@exemplo.com", "https://app.test")
    q = parse_qs(urlsplit(falso.links["ana@exemplo.com"]).query)
    assert falso.links["ana@exemplo.com"].startswith("https://app.test/?rec=")
    with pytest.raises(A.ErroAutenticacao):
        loja.abrir_link_recuperacao("chave-inventada", q["code"][0])  # sem o verificador do servidor não abre
    loja.enviar_recuperacao("ana@exemplo.com", "https://app.test")
    q = parse_qs(urlsplit(falso.links["ana@exemplo.com"]).query)
    u = loja.abrir_link_recuperacao(q["rec"][0], q["code"][0])
    assert u["email"] == "ana@exemplo.com"
    with pytest.raises(A.ErroAutenticacao):
        loja.abrir_link_recuperacao(q["rec"][0], q["code"][0])  # uso único
    with pytest.raises(A.ErroAutenticacao):
        loja.definir_senha(u, "curta")
    loja.definir_senha(u, "nova-senha-456")
    assert loja.entrar("ana@exemplo.com", "nova-senha-456")["id"] == u["id"]
    loja.enviar_recuperacao("ninguem@exemplo.com", "https://app.test")  # sem conta: mesma resposta, sem link


def test_supabase_limite_de_pedidos_tem_mensagem_clara(supa):
    loja, falso = supa
    loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    falso.limite = True
    for acao, trecho in [(lambda: loja.criar_conta("beto@exemplo.com", "senha-segura-1"), "limite de e-mails"),
                         (lambda: loja.enviar_recuperacao("ana@exemplo.com", "https://app.test"), "limite de e-mails"),
                         (lambda: loja.entrar("ana@exemplo.com", "senha-segura-1"), "tentativas de entrada")]:
        with pytest.raises(A.ErroAutenticacao) as e:
            acao()
        assert trecho in str(e.value) and "429" not in str(e.value)
    falso.limite = False
    assert loja.entrar("ana@exemplo.com", "senha-segura-1")["email"] == "ana@exemplo.com"


def test_supabase_ids_manipulados_validacao_e_exclusao(supa):
    loja, falso = supa
    ana = loja.criar_conta("ana@exemplo.com", "senha-segura-1")
    beto = loja.criar_conta("beto@exemplo.com", "senha-segura-2")
    loja.salvar(ana, R.padrao(), 0)
    loja.validar(ana)
    with pytest.raises(A.ErroAutenticacao):
        loja.validar(dict(beto, id=ana["id"]))  # o servidor diz de quem é o token: não é da Ana
    loja.apagar(dict(beto, id=ana["id"]))  # Beto tentando apagar a linha da Ana
    assert loja.versao(ana) == 1
    loja.apagar(ana)
    assert loja.versao(ana) == 0
    # a loja é compartilhada entre as sessões do servidor: não pode guardar token nem dados de ninguém
    assert set(vars(loja)) == {"url", "chave", "http", "tempo_limite"}


def test_configuracao_escolhe_o_banco(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("FOCO_LEVE_MODO_LOCAL", raising=False)
    assert A.configurar({}) is None  # sem banco e sem modo local: nenhum SQLite compartilhado no servidor
    monkeypatch.setenv("FOCO_LEVE_MODO_LOCAL", "1")
    assert isinstance(A.configurar({}), A.LojaSQLite)
    with pytest.raises(ValueError):
        A.configurar({"supabase": {"url": "https://p.supabase.co", "anon_key": "sb_secret_abc"}})
    import base64
    jwt = "x." + base64.urlsafe_b64encode(json.dumps({"role": "service_role"}).encode()).decode().rstrip("=") + ".y"
    with pytest.raises(ValueError):
        A.configurar({"supabase": {"url": "https://p.supabase.co", "anon_key": jwt}})
    assert isinstance(A.configurar({"supabase": {"url": "https://p.supabase.co", "anon_key": "k"}}), A.LojaSupabase)
    monkeypatch.setenv("SUPABASE_URL", "https://p.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "k")
    assert isinstance(A.configurar(None), A.LojaSupabase)
