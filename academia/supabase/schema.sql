-- Foco Leve: dados pessoais por usuário no Supabase (Postgres) com Row Level Security.
-- Rode uma vez no SQL Editor do projeto (Supabase → SQL Editor → New query → cole tudo → Run).
-- Pode ser rodado de novo sem perder dados. Não contém dados nem credenciais.
--
-- Modelo: uma linha por usuário. A coluna "dados" (jsonb) guarda todo o estado pessoal da conta — perfil e dados
-- físicos, pesagens, plano e treinos personalizados, sessão em andamento e treinos concluídos, metas, preferências,
-- agenda, hábitos e check-ins diários —, no mesmo formato da cópia de segurança (.json) do app. Como tudo está na
-- linha do dono, as políticas abaixo cobrem todos esses registros. O app não guarda fotos nem arquivos de usuário
-- (as fotos dos exercícios são públicas), por isso não há bucket de Storage.

create table if not exists public.foco_leve_estado (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  dados      jsonb       not null,
  versao     integer     not null default 1 check (versao >= 1),
  atualizado timestamptz not null default now()
);

-- Quem não entrou (papel anon) não tem nenhum acesso; usuários autenticados passam pelo RLS.
revoke all on table public.foco_leve_estado from anon;
revoke all on table public.foco_leve_estado from authenticated;
grant select, insert, update, delete on table public.foco_leve_estado to authenticated;

-- Isolamento: auth.uid() é o "sub" do token assinado pelo Supabase, não um valor enviado pelo navegador.
alter table public.foco_leve_estado enable row level security;
alter table public.foco_leve_estado force row level security;

drop policy if exists "dono le" on public.foco_leve_estado;
create policy "dono le" on public.foco_leve_estado
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "dono cria" on public.foco_leve_estado;
create policy "dono cria" on public.foco_leve_estado
  for insert to authenticated with check ((select auth.uid()) = user_id and versao = 1);

drop policy if exists "dono atualiza" on public.foco_leve_estado;
create policy "dono atualiza" on public.foco_leve_estado
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

drop policy if exists "dono apaga" on public.foco_leve_estado;
create policy "dono apaga" on public.foco_leve_estado
  for delete to authenticated using ((select auth.uid()) = user_id);

-- Integridade da versão: toda atualização sobe exatamente 1, o dono não muda e a data é a do servidor.
-- Junto com o filtro "versao = esperada" que o app envia, duas abas nunca gravam uma por cima da outra.
create or replace function public.foco_leve_versao() returns trigger
language plpgsql set search_path = '' as $$
begin
  if new.user_id <> old.user_id then
    raise exception 'user_id não pode mudar';
  end if;
  if new.versao <> old.versao + 1 then
    raise exception 'versão fora de ordem: esperada %, recebida %', old.versao + 1, new.versao;
  end if;
  new.atualizado := now();
  return new;
end $$;

drop trigger if exists foco_leve_versao on public.foco_leve_estado;
create trigger foco_leve_versao before update on public.foco_leve_estado
  for each row execute function public.foco_leve_versao();
