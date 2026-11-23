-- SECOND APPROVAL: run only after deploying cleanup-report-media and setting up
-- the existing service-role JWT in Supabase Vault, named ajf_cleanup_service_role.
-- Never put the key in this file, GitHub, VITE variables or conversation.
create extension if not exists pg_cron;
create extension if not exists pg_net;
do $$ begin
 if not exists(select 1 from vault.secrets where name='ajf_cleanup_service_role') then
 raise exception 'Missing private Vault secret'; end if;
 if exists(select 1 from cron.job where jobname='ajf-cleanup-report-media') then
 perform cron.unschedule('ajf-cleanup-report-media'); end if;
end $$;
select cron.schedule('ajf-cleanup-report-media','* * * * *',$job$
select net.http_post(
 url:='https://fnpssjnsljhwdoikfwcu.supabase.co/functions/v1/cleanup-report-media',
 headers:=jsonb_build_object('Content-Type','application/json','Authorization',
 'Bearer '||(select decrypted_secret from vault.decrypted_secrets where name='ajf_cleanup_service_role')),
 body:='{}'::jsonb,timeout_milliseconds:=10000);
$job$);
