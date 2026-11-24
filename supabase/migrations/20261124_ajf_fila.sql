-- Fila de varredura dos robôs. Só a service role acessa (RLS ligada, sem políticas).
create table if not exists public.ajf_fila (
  id uuid primary key default gen_random_uuid(),
  origem text not null check (origem in ('instagram','noticias')),
  post_id text not null,
  url text not null,
  autor text not null default '',
  legenda text not null default '',
  publicado_em timestamptz,
  midia_url text,
  eh_video boolean not null default false,
  estado text not null default 'novo' check (estado in ('novo','analisado','baixado','publicado','descartado','erro')),
  analise jsonb,
  midia_path text,
  request_id uuid not null default gen_random_uuid(),
  motivo text,
  tentativas int not null default 0,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  unique (origem, post_id)
);
alter table public.ajf_fila enable row level security;
revoke all on public.ajf_fila from anon, authenticated;
create index if not exists ajf_fila_estado_idx on public.ajf_fila (estado, criado_em);

create table if not exists public.ajf_robos_log (
  id bigint generated always as identity primary key,
  robo text not null,
  ok boolean not null,
  resumo text not null default '',
  criado_em timestamptz not null default now()
);
alter table public.ajf_robos_log enable row level security;
revoke all on public.ajf_robos_log from anon, authenticated;

-- Tabelas criadas via SQL ficam sem privilégio pro service_role neste projeto; liberar explicitamente.
grant usage on schema public to service_role;
grant select, insert, update, delete on public.ajf_fila, public.ajf_robos_log to service_role;
