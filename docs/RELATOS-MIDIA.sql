-- AlertaJF: foto/vídeo opcional nos relatos da comunidade.
-- Aplicar uma vez no projeto dedicado alertajf (SQL Editor do Supabase). Pode rodar de novo sem efeito colateral.
begin;

-- 1) Coluna de mídia nos relatos: lista JSON de {path, kind, credit?}, vazia por padrão.
alter table ajf_private.reports add column if not exists media jsonb not null default '[]'::jsonb;

-- 2) Bucket público para a mídia dos relatos: 25 MB por arquivo, só imagem/vídeo comuns.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('relatos-midia', 'relatos-midia', true, 26214400,
        array['image/jpeg','image/png','image/webp','image/heic','image/heif','video/mp4','video/quicktime','video/webm'])
on conflict (id) do nothing;

-- 3) Upload só com sessão (a mesma sessão anônima dos relatos) e só dentro da pasta r/.
--    Sem update/delete: ninguém sobrescreve nem apaga mídia de outro relato.
drop policy if exists "ajf_media_upload" on storage.objects;
create policy "ajf_media_upload" on storage.objects for insert to authenticated
with check (bucket_id = 'relatos-midia' and (storage.foldername(name))[1] = 'r');

-- 4) Leitura pública passa a incluir a mídia do relato (só path/tipo/crédito, nunca autor).
create or replace function public.ajf_reports() returns jsonb language sql stable security definer
set search_path = pg_catalog, ajf_private as $$
 select coalesce(jsonb_agg(to_jsonb(x) order by x.observed_at desc),'[]'::jsonb) from (
 select r.id,r.street,r.neighborhood,r.kind,r.description,r.lat,r.lng,r.observed_at,r.expires_at,r.media,
 'community'::text as status,'citizen'::text as source,
 (select count(*) from ajf_private.reactions v where v.report_id=r.id and v.action='seen') as seen_count
 from ajf_private.reports r where not r.withdrawn and r.expires_at>now()
 and (select count(*) from ajf_private.reactions v where v.report_id=r.id and v.action='flag')<3
 order by r.observed_at desc limit 100
 ) x;
$$;

-- 5) Envio passa a aceitar "media" opcional: até 2 itens {path, kind}, e o path precisa
--    começar com o request_id do próprio envio (ninguém anexa arquivo de outra pessoa).
create or replace function public.ajf_submit(payload jsonb) returns uuid language plpgsql security definer
set search_path = pg_catalog, ajf_private as $$
declare u uuid:=auth.uid(); t timestamptz; rid uuid; s text; n text; d text; k text; la float8; lo float8; m jsonb;
begin
 if u is null then raise exception 'Sessão necessária'; end if;
 if payload is null or jsonb_typeof(payload)<>'object' or exists(select 1 from jsonb_object_keys(payload) key where key not in ('street','neighborhood','kind','description','lat','lng','observed_at','website','request_id','media')) then raise exception 'Campos inválidos'; end if;
 if coalesce(payload->>'website','')<>'' then raise exception 'Envio recusado'; end if;
 s:=btrim(payload->>'street'); n:=btrim(payload->>'neighborhood'); d:=btrim(payload->>'description'); k:=payload->>'kind';
 if s is null or n is null or d is null or k is null or (s||n||d) ~ '[<>]' then raise exception 'Texto inválido'; end if;
 t:=(payload->>'observed_at')::timestamptz; la:=(payload->>'lat')::float8; lo:=(payload->>'lng')::float8;
 if t is null or t>now() or t<=now()-interval '5 hours' or la is null or lo is null then raise exception 'Observação deve ser das últimas 5 horas, sem horário futuro'; end if;
 m:=coalesce(payload->'media','[]'::jsonb);
 if jsonb_typeof(m)<>'array' or jsonb_array_length(m)>2
 or exists(select 1 from jsonb_array_elements(m) e
   where jsonb_typeof(e)<>'object'
   or exists(select 1 from jsonb_object_keys(e) k2 where k2 not in ('path','kind'))
   or coalesce(e->>'kind','') not in ('image','video')
   or coalesce(e->>'path','') !~ ('^r/'||(payload->>'request_id')||'-[a-z0-9]+\.(jpg|jpeg|png|webp|heic|mp4|mov|webm)$')) then raise exception 'Mídia inválida'; end if;
 perform pg_advisory_xact_lock(214728,1);
 select id into rid from ajf_private.reports where author=u and request_id=(payload->>'request_id')::uuid;
 if found then return rid; end if;
 delete from ajf_private.reports where received_at<now()-interval '7 days';
 if (select count(*) from ajf_private.reports where author=u and received_at>now()-interval '1 hour')>=30
 or exists(select 1 from ajf_private.reports where author=u and received_at>now()-interval '1 minute') then raise exception 'Limite de envios: aguarde antes de tentar novamente'; end if;
 if (select count(*) from ajf_private.reports where received_at>now()-interval '1 hour')>=300 then raise exception 'Limite temporário do serviço. Tente mais tarde'; end if;
 if exists(select 1 from ajf_private.reports where author=u and not withdrawn and expires_at>now() and lower(street)=lower(s) and lower(neighborhood)=lower(n) and kind=k) then raise exception 'Você já enviou um relato recente para esse local'; end if;
 insert into ajf_private.reports(author,request_id,street,neighborhood,kind,description,lat,lng,observed_at,expires_at,media)
 values(u,(payload->>'request_id')::uuid,s,n,k,d,la,lo,t,t+interval '5 hours',m) returning id into rid;
 return rid;
end;
$$;

commit;
