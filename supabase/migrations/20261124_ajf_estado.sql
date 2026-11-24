-- Estado dos robôs (contadores de cota e intervalos): fica no banco, não no cache do Actions (o cache zera quando o job falha).
create table if not exists public.ajf_estado (
  chave text primary key,
  valor jsonb not null default '{}'::jsonb,
  atualizado_em timestamptz not null default now()
);
alter table public.ajf_estado enable row level security;
-- sem políticas: só a service role (robôs) lê e escreve; anon/authenticated não enxergam nada.
