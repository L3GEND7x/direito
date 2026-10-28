-- Foco Leve — Personal IA: conversas, mensagens e fotos de cada usuário, com Row Level Security.
-- Rode DEPOIS de schema.sql, uma vez, no SQL Editor do Supabase (New query → cole tudo → Run).
-- Pode ser rodado de novo sem perder dados. Não contém dados nem credenciais.
--
-- As fotos ficam na tabela foco_leve_ia_anexos (JPEG reprocessado pelo app, sem metadados), protegidas pelas
-- mesmas regras de dono das mensagens. Assim não há bucket de Storage a configurar.

create table if not exists public.foco_leve_ia_conversas (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  titulo      text not null default 'Nova conversa' check (char_length(titulo) between 1 and 120),
  resumo      text not null default '' check (char_length(resumo) <= 12000),
  resumo_ate  integer not null default 0 check (resumo_ate >= 0),
  criada      timestamptz not null default now(),
  atualizada  timestamptz not null default now()
);
create index if not exists foco_leve_ia_conversas_dono on public.foco_leve_ia_conversas (user_id, atualizada desc);

create table if not exists public.foco_leve_ia_mensagens (
  id              uuid primary key default gen_random_uuid(),
  conversa_id     uuid not null references public.foco_leve_ia_conversas (id) on delete cascade,
  user_id         uuid not null default auth.uid() references auth.users (id) on delete cascade,
  papel           text not null check (papel in ('user', 'assistant')),
  texto           text not null check (char_length(texto) <= 40000),
  proposta        jsonb,
  proposta_estado text check (proposta_estado in ('pendente', 'aplicada', 'descartada')),
  tokens_entrada  integer,
  tokens_saida    integer,
  criada          timestamptz not null default now()
);
create index if not exists foco_leve_ia_mensagens_conversa on public.foco_leve_ia_mensagens (conversa_id, criada);
create index if not exists foco_leve_ia_mensagens_dono on public.foco_leve_ia_mensagens (user_id, criada);

create table if not exists public.foco_leve_ia_anexos (
  id           uuid primary key default gen_random_uuid(),
  mensagem_id  uuid not null references public.foco_leve_ia_mensagens (id) on delete cascade,
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  mime         text not null check (mime = 'image/jpeg'),
  largura      integer check (largura between 1 and 4096),
  altura       integer check (altura between 1 and 4096),
  dados        text not null check (char_length(dados) <= 3000000),  -- base64 de no máximo ~2,2 MB
  criada       timestamptz not null default now()
);
create index if not exists foco_leve_ia_anexos_mensagem on public.foco_leve_ia_anexos (mensagem_id);

-- Quem não entrou (anon) não tem acesso nenhum; usuários autenticados passam pelo RLS.
revoke all on table public.foco_leve_ia_conversas, public.foco_leve_ia_mensagens, public.foco_leve_ia_anexos from anon;
revoke all on table public.foco_leve_ia_conversas, public.foco_leve_ia_mensagens, public.foco_leve_ia_anexos from authenticated;
grant select, insert, update, delete on table public.foco_leve_ia_conversas to authenticated;
grant select, insert, update, delete on table public.foco_leve_ia_mensagens to authenticated;
grant select, insert, delete on table public.foco_leve_ia_anexos to authenticated;

alter table public.foco_leve_ia_conversas enable row level security;
alter table public.foco_leve_ia_conversas force row level security;
alter table public.foco_leve_ia_mensagens enable row level security;
alter table public.foco_leve_ia_mensagens force row level security;
alter table public.foco_leve_ia_anexos enable row level security;
alter table public.foco_leve_ia_anexos force row level security;

-- Conversas: só as do próprio usuário.
drop policy if exists "dono le" on public.foco_leve_ia_conversas;
create policy "dono le" on public.foco_leve_ia_conversas
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "dono cria" on public.foco_leve_ia_conversas;
create policy "dono cria" on public.foco_leve_ia_conversas
  for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists "dono atualiza" on public.foco_leve_ia_conversas;
create policy "dono atualiza" on public.foco_leve_ia_conversas
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
drop policy if exists "dono apaga" on public.foco_leve_ia_conversas;
create policy "dono apaga" on public.foco_leve_ia_conversas
  for delete to authenticated using ((select auth.uid()) = user_id);

-- Mensagens: do próprio usuário E numa conversa dele (não dá para escrever na conversa de outra pessoa).
drop policy if exists "dono le" on public.foco_leve_ia_mensagens;
create policy "dono le" on public.foco_leve_ia_mensagens
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "dono cria" on public.foco_leve_ia_mensagens;
create policy "dono cria" on public.foco_leve_ia_mensagens
  for insert to authenticated with check (
    (select auth.uid()) = user_id
    and exists (select 1 from public.foco_leve_ia_conversas c
                where c.id = conversa_id and c.user_id = (select auth.uid())));
drop policy if exists "dono atualiza" on public.foco_leve_ia_mensagens;
create policy "dono atualiza" on public.foco_leve_ia_mensagens
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
drop policy if exists "dono apaga" on public.foco_leve_ia_mensagens;
create policy "dono apaga" on public.foco_leve_ia_mensagens
  for delete to authenticated using ((select auth.uid()) = user_id);

-- Fotos: do próprio usuário E presas a uma mensagem dele. Não há atualização: uma foto só é criada ou apagada.
drop policy if exists "dono le" on public.foco_leve_ia_anexos;
create policy "dono le" on public.foco_leve_ia_anexos
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "dono cria" on public.foco_leve_ia_anexos;
create policy "dono cria" on public.foco_leve_ia_anexos
  for insert to authenticated with check (
    (select auth.uid()) = user_id
    and exists (select 1 from public.foco_leve_ia_mensagens m
                where m.id = mensagem_id and m.user_id = (select auth.uid())));
drop policy if exists "dono apaga" on public.foco_leve_ia_anexos;
create policy "dono apaga" on public.foco_leve_ia_anexos
  for delete to authenticated using ((select auth.uid()) = user_id);

-- Integridade: dono e conversa de um registro não mudam; o texto de uma mensagem também não
-- (só o estado da proposta pode mudar, de "pendente" para "aplicada" ou "descartada").
create or replace function public.foco_leve_ia_imutavel() returns trigger
language plpgsql set search_path = '' as $$
begin
  if new.user_id <> old.user_id then
    raise exception 'user_id não pode mudar';
  end if;
  if tg_table_name = 'foco_leve_ia_mensagens' then
    if new.conversa_id <> old.conversa_id or new.papel <> old.papel or new.texto <> old.texto
       or new.proposta is distinct from old.proposta then
      raise exception 'mensagem não pode ser alterada, só o estado da proposta';
    end if;
  end if;
  if tg_table_name = 'foco_leve_ia_conversas' then
    new.atualizada := now();
  end if;
  return new;
end $$;

drop trigger if exists foco_leve_ia_conversas_imutavel on public.foco_leve_ia_conversas;
create trigger foco_leve_ia_conversas_imutavel before update on public.foco_leve_ia_conversas
  for each row execute function public.foco_leve_ia_imutavel();
drop trigger if exists foco_leve_ia_mensagens_imutavel on public.foco_leve_ia_mensagens;
create trigger foco_leve_ia_mensagens_imutavel before update on public.foco_leve_ia_mensagens
  for each row execute function public.foco_leve_ia_imutavel();

-- Nova mensagem: a conversa sobe para o topo da lista (roda com as permissões de quem escreveu, sob o RLS).
create or replace function public.foco_leve_ia_tocar_conversa() returns trigger
language plpgsql set search_path = '' as $$
begin
  update public.foco_leve_ia_conversas set atualizada = now() where id = new.conversa_id;
  return new;
end $$;

drop trigger if exists foco_leve_ia_mensagens_tocar on public.foco_leve_ia_mensagens;
create trigger foco_leve_ia_mensagens_tocar after insert on public.foco_leve_ia_mensagens
  for each row execute function public.foco_leve_ia_tocar_conversa();
