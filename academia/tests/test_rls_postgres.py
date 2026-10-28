"""Políticas de Row Level Security de supabase/schema.sql testadas num PostgreSQL de verdade.

Sobe um Postgres temporário, recria o que o Supabase oferece (papéis anon e authenticated, tabela auth.users,
função auth.uid() lendo o "sub" do token e os privilégios padrão que o Supabase concede no schema public), aplica
o schema.sql do repositório sem alterações e tenta acessos cruzados como usuário autenticado.
Pulado se os binários do PostgreSQL não estiverem instalados.
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

SCHEMA = Path(__file__).resolve().parents[1] / "supabase" / "schema.sql"
SCHEMA_IA = Path(__file__).resolve().parents[1] / "supabase" / "personal_ia.sql"
BIN = next(iter(sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)), None) or (
    os.path.dirname(shutil.which("pg_ctl")) if shutil.which("pg_ctl") else None)
pytestmark = pytest.mark.skipif(not BIN or not os.path.exists(os.path.join(BIN, "initdb")), reason="PostgreSQL ausente")

# o mínimo do Supabase de que o schema.sql depende (como no projeto hospedado)
SUPABASE_BASE = """
create role anon nologin noinherit;
create role authenticated nologin noinherit;
create schema auth;
create table auth.users (id uuid primary key, email text);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(coalesce(current_setting('request.jwt.claim.sub', true),
                         current_setting('request.jwt.claims', true)::jsonb ->> 'sub'), '')::uuid $$;
grant usage on schema public, auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
alter default privileges in schema public grant all on tables to anon, authenticated;
"""
A_ID, B_ID, C_ID = (str(uuid.uuid4()) for _ in range(3))


@pytest.fixture(scope="module")
def pg():
    raiz = tempfile.mkdtemp(prefix="pg-foco-")
    dados, sock = os.path.join(raiz, "dados"), os.path.join(raiz, "sock")
    os.makedirs(sock)
    como = []
    if os.geteuid() == 0:  # o Postgres não roda como root
        shutil.chown(raiz, "postgres")
        shutil.chown(sock, "postgres")
        como = ["runuser", "-u", "postgres", "--"]
    subprocess.run(como + [f"{BIN}/initdb", "-D", dados, "-U", "postgres", "-A", "trust"], check=True, capture_output=True)
    porta = str(54000 + os.getpid() % 1000)
    subprocess.run(como + [f"{BIN}/pg_ctl", "-D", dados, "-w", "-l", os.path.join(raiz, "log"), "-o",
                           f"-k {sock} -p {porta} -c listen_addresses=''", "start"], check=True, capture_output=True)

    def sql(texto, usuario=None, papel=None):
        """Executa como superusuário, ou com o papel e o token (sub) de um usuário, como faz o PostgREST."""
        prefixo = ""
        if papel:
            claims = json.dumps({"sub": usuario, "role": papel}) if usuario else json.dumps({"role": papel})
            prefixo = f"set role {papel}; select set_config('request.jwt.claims', '{claims}', false);\n"
        r = subprocess.run(como + [f"{BIN}/psql", "-h", sock, "-p", porta, "-U", "postgres", "-d", "postgres", "-X",
                                   "-q", "-At", "-v", "ON_ERROR_STOP=1"], input=prefixo + texto, text=True, capture_output=True)
        return r.returncode, (r.stdout.strip().splitlines()[1:] if papel else r.stdout.strip().splitlines()), r.stderr

    rc, _, err = sql(SUPABASE_BASE + SCHEMA.read_text(encoding="utf-8") + SCHEMA_IA.read_text(encoding="utf-8"))
    assert rc == 0, err
    rc, _, err = sql(SCHEMA.read_text(encoding="utf-8") + SCHEMA_IA.read_text(encoding="utf-8"))  # rodar de novo não pode falhar
    assert rc == 0, err
    sql(f"insert into auth.users values ('{A_ID}', 'a@x.com'), ('{B_ID}', 'b@x.com'), ('{C_ID}', 'c@x.com');")
    yield sql
    subprocess.run(como + [f"{BIN}/pg_ctl", "-D", dados, "-m", "immediate", "stop"], capture_output=True)
    shutil.rmtree(raiz, ignore_errors=True)


def como_a(sql, texto):
    return sql(texto, A_ID, "authenticated")


def como_b(sql, texto):
    return sql(texto, B_ID, "authenticated")


ESTADO_A = {"profile": {"nome": "Ana", "peso": 101.1, "meta": 80}, "weights": [{"date": "2026-10-01", "peso": 101.1}],
            "plan": {"A": ["leg_press"]}, "sessions": [{"workout": "A"}], "active": {"workout": "A"},
            "habits": {"2026-10-01": {"agua": 8}}, "checkins": {"2026-10-01": {"sono": 7}}}


def test_rls_isolamento_completo(pg):
    sql = pg
    # 1. A cria o próprio registro (treino, peso, hábitos, metas, sessões) e consegue lê-lo
    rc, _, err = como_a(sql, f"insert into public.foco_leve_estado(user_id, dados, versao) values "
                             f"('{A_ID}', '{json.dumps(ESTADO_A)}', 1);")
    assert rc == 0, err
    _, linhas, _ = como_a(sql, "select dados->'plan'->>'A', dados->'profile'->>'peso' from public.foco_leve_estado;")
    assert linhas == ['["leg_press"]|101.1']

    # 2. B não vê nada de A, nem pedindo o id de A diretamente
    _, linhas, _ = como_b(sql, "select count(*) from public.foco_leve_estado;")
    assert linhas == ["0"]
    _, linhas, _ = como_b(sql, f"select count(*) from public.foco_leve_estado where user_id = '{A_ID}';")
    assert linhas == ["0"]

    # 3. B não altera nem apaga a linha de A (o filtro não encontra nada; nenhuma linha muda)
    _, linhas, _ = como_b(sql, f"update public.foco_leve_estado set dados = '{{}}', versao = 2 where user_id = '{A_ID}' returning 1;")
    assert linhas == []
    _, linhas, _ = como_b(sql, f"delete from public.foco_leve_estado where user_id = '{A_ID}' returning 1;")
    assert linhas == []

    # 4. B não cria registro em nome de outra pessoa (manipular o user_id do corpo da requisição)
    rc, _, err = como_b(sql, f"insert into public.foco_leve_estado(user_id, dados, versao) values ('{C_ID}', '{{}}', 1);")
    assert rc != 0 and "row-level security" in err
    rc, _, err = como_b(sql, f"insert into public.foco_leve_estado(user_id, dados, versao) values ('{A_ID}', '{{}}', 1) "
                             f"on conflict (user_id) do update set dados = excluded.dados;")
    assert rc != 0

    # B cria a própria linha e não consegue "transferi-la" para A
    rc, _, err = como_b(sql, f"insert into public.foco_leve_estado(user_id, dados, versao) values ('{B_ID}', '{{\"profile\": {{\"peso\": 77.7}}}}', 1);")
    assert rc == 0, err
    rc, _, err = como_b(sql, f"update public.foco_leve_estado set user_id = '{A_ID}', versao = 2 where user_id = '{B_ID}';")
    assert rc != 0

    # o superusuário confere que A continua intacto
    _, linhas, _ = sql(f"select dados->'profile'->>'peso', versao from public.foco_leve_estado where user_id = '{A_ID}';")
    assert linhas == ["101.1|1"]
    _, linhas, _ = sql("select count(*) from public.foco_leve_estado;")
    assert linhas == ["2"]


def test_rls_sem_login_nao_le_nem_grava(pg):
    sql = pg
    rc, _, err = sql("select count(*) from public.foco_leve_estado;", papel="anon")
    assert rc != 0 and "permission denied" in err
    rc, _, err = sql(f"insert into public.foco_leve_estado(user_id, dados) values ('{C_ID}', '{{}}');", papel="anon")
    assert rc != 0 and "permission denied" in err
    # autenticado sem "sub" (token adulterado ou sem usuário) não enxerga ninguém
    _, linhas, _ = sql("select count(*) from public.foco_leve_estado;", papel="authenticated")
    assert linhas == ["0"]


def test_rls_versao_e_apagar_os_proprios_dados(pg):
    sql = pg
    rc, _, err = sql(f"insert into public.foco_leve_estado(user_id, dados, versao) values ('{C_ID}', '{{}}', 1);", C_ID, "authenticated")
    assert rc == 0, err
    # gravação condicional: a primeira com versao = 1 vence, a segunda (mesma versão lida) não altera nada
    _, l1, _ = sql(f"update public.foco_leve_estado set dados = '{{\"x\": 1}}', versao = 2 where user_id = '{C_ID}' and versao = 1 returning versao;", C_ID, "authenticated")
    _, l2, _ = sql(f"update public.foco_leve_estado set dados = '{{\"x\": 2}}', versao = 2 where user_id = '{C_ID}' and versao = 1 returning versao;", C_ID, "authenticated")
    assert l1 == ["2"] and l2 == []
    rc, _, err = sql(f"update public.foco_leve_estado set versao = 9 where user_id = '{C_ID}';", C_ID, "authenticated")
    assert rc != 0 and "fora de ordem" in err
    # o dono pode apagar os próprios dados; os de A e B continuam
    _, linhas, _ = sql(f"delete from public.foco_leve_estado where user_id = '{C_ID}' returning 1;", C_ID, "authenticated")
    assert linhas == ["1"]
    _, linhas, _ = sql("select count(*) from public.foco_leve_estado;")
    assert linhas == ["2"]


def test_rls_ligado_em_todas_as_tabelas_publicas(pg):
    """Nenhuma tabela do schema public com dados pessoais fica sem RLS."""
    _, linhas, _ = pg("select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                      "where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity;")
    assert linhas == []


# ---------------------------------------------------------------- Personal IA: conversas, mensagens e fotos
def _um(linhas):
    assert len(linhas) == 1, linhas
    return linhas[0]


def test_rls_personal_ia_isolamento(pg):
    sql = pg
    # A cria conversa, mensagem e foto; vê as três
    rc, l, err = como_a(sql, "insert into public.foco_leve_ia_conversas(titulo) values ('Treino de pernas') returning id;")
    assert rc == 0, err
    conv_a = _um(l)
    rc, l, err = como_a(sql, f"insert into public.foco_leve_ia_mensagens(conversa_id, papel, texto) "
                             f"values ('{conv_a}', 'user', 'meu joelho incomoda') returning id;")
    assert rc == 0, err
    msg_a = _um(l)
    rc, l, err = como_a(sql, f"insert into public.foco_leve_ia_anexos(mensagem_id, mime, largura, altura, dados) "
                             f"values ('{msg_a}', 'image/jpeg', 10, 10, 'QUJD') returning id;")
    assert rc == 0, err
    foto_a = _um(l)
    _, l, _ = como_a(sql, "select (select count(*) from public.foco_leve_ia_conversas), "
                          "(select count(*) from public.foco_leve_ia_mensagens), (select count(*) from public.foco_leve_ia_anexos);")
    assert l == ["1|1|1"]

    # B não vê nada de A, nem pedindo pelos ids
    _, l, _ = como_b(sql, f"select (select count(*) from public.foco_leve_ia_conversas where id = '{conv_a}'), "
                          f"(select count(*) from public.foco_leve_ia_mensagens where id = '{msg_a}'), "
                          f"(select count(*) from public.foco_leve_ia_anexos where id = '{foto_a}');")
    assert l == ["0|0|0"]
    # B não altera nem apaga
    _, l, _ = como_b(sql, f"update public.foco_leve_ia_conversas set titulo = 'x' where id = '{conv_a}' returning 1;")
    assert l == []
    _, l, _ = como_b(sql, f"update public.foco_leve_ia_mensagens set proposta_estado = 'aplicada' where id = '{msg_a}' returning 1;")
    assert l == []
    for tabela, i in (("foco_leve_ia_anexos", foto_a), ("foco_leve_ia_mensagens", msg_a), ("foco_leve_ia_conversas", conv_a)):
        _, l, _ = como_b(sql, f"delete from public.{tabela} where id = '{i}' returning 1;")
        assert l == [], tabela
    # B não escreve na conversa de A, nem com o próprio user_id, nem anexa foto à mensagem de A
    rc, _, err = como_b(sql, f"insert into public.foco_leve_ia_mensagens(conversa_id, papel, texto) values ('{conv_a}', 'user', 'oi');")
    assert rc != 0 and "row-level security" in err
    rc, _, err = como_b(sql, f"insert into public.foco_leve_ia_mensagens(conversa_id, user_id, papel, texto) "
                             f"values ('{conv_a}', '{A_ID}', 'user', 'oi');")
    assert rc != 0 and "row-level security" in err
    rc, _, err = como_b(sql, f"insert into public.foco_leve_ia_anexos(mensagem_id, mime, dados) values ('{msg_a}', 'image/jpeg', 'QUJD');")
    assert rc != 0 and "row-level security" in err
    rc, _, err = como_b(sql, f"insert into public.foco_leve_ia_conversas(user_id, titulo) values ('{A_ID}', 'falsa');")
    assert rc != 0 and "row-level security" in err

    # sem login: nada
    rc, _, err = sql("select count(*) from public.foco_leve_ia_mensagens;", papel="anon")
    assert rc != 0 and "permission denied" in err

    # integridade: a mensagem não muda de texto nem de conversa; só o estado da proposta
    rc, _, err = como_a(sql, f"update public.foco_leve_ia_mensagens set texto = 'outro' where id = '{msg_a}';")
    assert rc != 0 and "não pode ser alterada" in err
    rc, _, err = como_a(sql, f"update public.foco_leve_ia_mensagens set proposta_estado = 'descartada' where id = '{msg_a}';")
    assert rc == 0, err
    rc, _, err = como_a(sql, f"update public.foco_leve_ia_conversas set user_id = '{B_ID}' where id = '{conv_a}';")
    assert rc != 0

    # o superusuário confere que nada de A sumiu
    _, l, _ = sql(f"select (select count(*) from public.foco_leve_ia_conversas where user_id = '{A_ID}'), "
                  f"(select count(*) from public.foco_leve_ia_mensagens where user_id = '{A_ID}'), "
                  f"(select count(*) from public.foco_leve_ia_anexos where user_id = '{A_ID}');")
    assert l == ["1|1|1"]

    # A apaga a conversa: mensagens e fotos vão junto
    _, l, _ = como_a(sql, f"delete from public.foco_leve_ia_conversas where id = '{conv_a}' returning 1;")
    assert l == ["1"]
    _, l, _ = sql(f"select (select count(*) from public.foco_leve_ia_mensagens where user_id = '{A_ID}'), "
                  f"(select count(*) from public.foco_leve_ia_anexos where user_id = '{A_ID}');")
    assert l == ["0|0"]
