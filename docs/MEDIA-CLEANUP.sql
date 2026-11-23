-- Review and approve before running. No Storage objects are deleted by this migration.
begin;
create table if not exists ajf_private.media_cleanup (
 path text primary key, expires_at timestamptz not null,
 deleted_at timestamptz, check (path ~ '^r/[a-zA-Z0-9][a-zA-Z0-9._-]{0,199}$' and path not like '%..%')
);
alter table ajf_private.media_cleanup enable row level security;
revoke all on ajf_private.media_cleanup from public, anon, authenticated;

-- Keep references before the existing 7-day report-row purge discards them.
create or replace function ajf_private.queue_report_media() returns trigger
language plpgsql security definer set search_path=pg_catalog,ajf_private as $$
begin
 insert into ajf_private.media_cleanup(path,expires_at)
 select e->>'path',old.expires_at from jsonb_array_elements(old.media) e
 where e->>'path' ~ '^r/[a-zA-Z0-9][a-zA-Z0-9._-]{0,199}$' and e->>'path' not like '%..%'
 on conflict on constraint media_cleanup_pkey do update set expires_at=greatest(media_cleanup.expires_at,excluded.expires_at);
 return old;
end $$;
revoke all on function ajf_private.queue_report_media() from public,anon,authenticated;
drop trigger if exists queue_media_before_report_delete on ajf_private.reports;
create trigger queue_media_before_report_delete before delete on ajf_private.reports
for each row execute function ajf_private.queue_report_media();

create or replace function public.ajf_media_cleanup_eligible(object_path text) returns boolean
language sql stable security definer set search_path=pg_catalog,ajf_private as $$
 select exists(select 1 from ajf_private.media_cleanup q where q.path=object_path
   and q.expires_at<=now() and q.deleted_at is null)
 and not exists(select 1 from ajf_private.reports r, jsonb_array_elements(r.media) e
   where e->>'path'=object_path and r.expires_at>now());
$$;
create or replace function public.ajf_media_cleanup_candidates() returns table(path text)
language plpgsql security definer set search_path=pg_catalog,ajf_private as $$
begin
 insert into ajf_private.media_cleanup(path,expires_at)
 select e->>'path',max(r.expires_at) from ajf_private.reports r, jsonb_array_elements(r.media) e
 where r.expires_at<=now() and e->>'path' ~ '^r/[a-zA-Z0-9][a-zA-Z0-9._-]{0,199}$'
 and e->>'path' not like '%..%' group by e->>'path'
 on conflict on constraint media_cleanup_pkey do update set expires_at=greatest(media_cleanup.expires_at,excluded.expires_at);
 return query select q.path from ajf_private.media_cleanup q
 where public.ajf_media_cleanup_eligible(q.path) order by q.expires_at limit 100;
end $$;
create or replace function public.ajf_media_cleanup_ack(object_path text) returns void
language sql security definer set search_path=pg_catalog,ajf_private as $$
 update ajf_private.media_cleanup q set deleted_at=now() where q.path=object_path
 and public.ajf_media_cleanup_eligible(object_path);
$$;
revoke all on function public.ajf_media_cleanup_candidates(),public.ajf_media_cleanup_eligible(text),public.ajf_media_cleanup_ack(text) from public,anon,authenticated;
grant execute on function public.ajf_media_cleanup_candidates(),public.ajf_media_cleanup_eligible(text),public.ajf_media_cleanup_ack(text) to service_role;
commit;
