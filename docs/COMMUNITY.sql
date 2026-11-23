-- AlertaJF: community reports, no official verification claims.
-- Apply only to the dedicated alertajf project. All tables are private to RPCs.
begin;
create schema if not exists ajf_private;
revoke all on schema ajf_private from public, anon, authenticated;
create table ajf_private.reports (
 id uuid primary key default gen_random_uuid(), author uuid not null, request_id uuid not null, unique(author,request_id),
 street text not null check(char_length(street) between 3 and 120),
 neighborhood text not null check(char_length(neighborhood) between 2 and 80),
 kind text not null check(kind in ('alagamento','interdicao','deslizamento')),
 description text not null check(char_length(description) between 10 and 600),
 lat double precision not null check(lat between -22.1 and -21.3),
 lng double precision not null check(lng between -43.9 and -42.9),
 observed_at timestamptz not null, received_at timestamptz not null default now(),
 expires_at timestamptz not null, withdrawn boolean not null default false
);
create table ajf_private.reactions (
 report_id uuid not null references ajf_private.reports(id) on delete cascade,
 author uuid not null, action text not null check(action in ('seen','flag')),
 created_at timestamptz not null default now(), primary key(report_id,author,action)
);
alter table ajf_private.reports enable row level security;
alter table ajf_private.reactions enable row level security;
revoke all on all tables in schema ajf_private from public, anon, authenticated;
create index on ajf_private.reports(expires_at);
create index on ajf_private.reports(author,received_at);
create index on ajf_private.reactions(author,created_at);

create function public.ajf_reports() returns jsonb language sql stable security definer
set search_path = pg_catalog, ajf_private as $$
 select coalesce(jsonb_agg(to_jsonb(x) order by x.observed_at desc),'[]'::jsonb) from (
 select r.id,r.street,r.neighborhood,r.kind,r.description,r.lat,r.lng,r.observed_at,r.expires_at,
 'community'::text as status,'citizen'::text as source,
 (select count(*) from ajf_private.reactions v where v.report_id=r.id and v.action='seen') as seen_count
 from ajf_private.reports r where not r.withdrawn and r.expires_at>now()
 and (select count(*) from ajf_private.reactions v where v.report_id=r.id and v.action='flag')<3
 order by r.observed_at desc limit 100
 ) x;
$$;

create function public.ajf_submit(payload jsonb) returns uuid language plpgsql security definer
set search_path = pg_catalog, ajf_private as $$
declare u uuid:=auth.uid(); t timestamptz; rid uuid; s text; n text; d text; k text; la float8; lo float8;
begin
 if u is null then raise exception 'Sessão necessária'; end if;
 if payload is null or jsonb_typeof(payload)<>'object' or exists(select 1 from jsonb_object_keys(payload) key where key not in ('street','neighborhood','kind','description','lat','lng','observed_at','website','request_id')) then raise exception 'Campos inválidos'; end if;
 if coalesce(payload->>'website','')<>'' then raise exception 'Envio recusado'; end if;
 s:=btrim(payload->>'street'); n:=btrim(payload->>'neighborhood'); d:=btrim(payload->>'description'); k:=payload->>'kind';
 if s is null or n is null or d is null or k is null or (s||n||d) ~ '[<>]' then raise exception 'Texto inválido'; end if;
 t:=(payload->>'observed_at')::timestamptz; la:=(payload->>'lat')::float8; lo:=(payload->>'lng')::float8;
 if t is null or t>now() or t<=now()-interval '2 hours' or la is null or lo is null then raise exception 'Observação deve ser das últimas 2 horas, sem horário futuro'; end if;
 perform pg_advisory_xact_lock(214728,1);
 select id into rid from ajf_private.reports where author=u and request_id=(payload->>'request_id')::uuid;
 if found then return rid; end if;
 delete from ajf_private.reports where received_at<now()-interval '7 days';
 if (select count(*) from ajf_private.reports where author=u and received_at>now()-interval '1 hour')>=30
 or exists(select 1 from ajf_private.reports where author=u and received_at>now()-interval '1 minute') then raise exception 'Limite de envios: aguarde antes de tentar novamente'; end if;
 if (select count(*) from ajf_private.reports where received_at>now()-interval '1 hour')>=300 then raise exception 'Limite temporário do serviço. Tente mais tarde'; end if;
 if exists(select 1 from ajf_private.reports where author=u and not withdrawn and expires_at>now() and lower(street)=lower(s) and lower(neighborhood)=lower(n) and kind=k) then raise exception 'Você já enviou um relato recente para esse local'; end if;
 insert into ajf_private.reports(author,request_id,street,neighborhood,kind,description,lat,lng,observed_at,expires_at)
 values(u,(payload->>'request_id')::uuid,s,n,k,d,la,lo,t,t+interval '5 hours') returning id into rid;
 return rid;
end;
$$;

create function public.ajf_react(report_id uuid, reaction text) returns void language plpgsql security definer
set search_path = pg_catalog, ajf_private as $$
declare u uuid:=auth.uid(); r ajf_private.reports;
begin
 if u is null or reaction is null or reaction not in ('seen','flag') then raise exception 'Ação inválida'; end if;
 perform pg_advisory_xact_lock(214728,1);
 select * into r from ajf_private.reports where id=report_id;
 if not found or r.withdrawn or r.expires_at<=now() then raise exception 'Relato indisponível ou vencido'; end if;
 if r.author=u then raise exception 'Não é possível reforçar ou denunciar seu próprio relato'; end if;
 if exists(select 1 from ajf_private.reactions v where v.report_id=ajf_react.report_id and v.author=u and v.action=reaction) then raise exception 'Você já sinalizou este relato'; end if;
 if (select count(*) from ajf_private.reactions where author=u and created_at>now()-interval '1 hour')>=30 then raise exception 'Limite de ações: tente mais tarde'; end if;
 if (select count(*) from ajf_private.reactions where created_at>now()-interval '1 hour')>=500 then raise exception 'Limite temporário do serviço'; end if;
 insert into ajf_private.reactions(report_id,author,action) values(ajf_react.report_id,u,reaction);
end;
$$;
revoke all on function public.ajf_reports() from public;
revoke all on function public.ajf_submit(jsonb) from public;
revoke all on function public.ajf_react(uuid,text) from public;
grant execute on function public.ajf_reports() to anon,authenticated;
grant execute on function public.ajf_submit(jsonb) to authenticated;
grant execute on function public.ajf_react(uuid,text) to authenticated;
create function public.ajf_withdraw(report_id uuid) returns void language plpgsql security definer set search_path=pg_catalog,ajf_private as $$ begin if auth.uid() is null then raise exception 'Sessão necessária'; end if; update ajf_private.reports set withdrawn=true where id=report_id and author=auth.uid(); if not found then raise exception 'Não é possível retirar: use o mesmo navegador em que publicou'; end if; end; $$;
revoke all on function public.ajf_withdraw(uuid) from public;
grant execute on function public.ajf_withdraw(uuid) to authenticated;
commit;
