CREATE OR REPLACE FUNCTION public.ajf_submit(payload jsonb)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'ajf_private', 'storage'
AS $function$
declare u uuid:=auth.uid(); t timestamptz; rid uuid; s text; n text; d text; k text; la float8; lo float8; m jsonb;
begin
 if u is null then raise exception 'Sessão necessária'; end if;
 if payload is null or jsonb_typeof(payload)<>'object' or exists(select 1 from jsonb_object_keys(payload) key where key not in ('street','neighborhood','kind','description','lat','lng','observed_at','website','request_id','media')) then raise exception 'Campos inválidos'; end if;
 if coalesce(payload->>'website','')<>'' then raise exception 'Envio recusado'; end if;
 s:=btrim(payload->>'street'); n:=btrim(payload->>'neighborhood'); d:=btrim(payload->>'description'); k:=payload->>'kind';
 if s is null or n is null or d is null or k is null or (s||n||d) ~ '[<>]' then raise exception 'Texto inválido'; end if;
 t:=(payload->>'observed_at')::timestamptz; la:=(payload->>'lat')::float8; lo:=(payload->>'lng')::float8;
 if t is null or t>now() or t<=now()-interval '2 hours' or la is null or lo is null then raise exception 'Observação deve ser das últimas 2 horas, sem horário futuro'; end if;
 m:=coalesce(payload->'media','[]'::jsonb);
 if jsonb_typeof(m)<>'array' or jsonb_array_length(m)>2
 or exists(select 1 from jsonb_array_elements(m) e
   where jsonb_typeof(e)<>'object'
   or exists(select 1 from jsonb_object_keys(e) k2 where k2 not in ('path','kind','credit'))
   or coalesce(e->>'kind','') not in ('image','video')
   or coalesce(e->>'path','') !~ ('^r/'||(payload->>'request_id')||'-[a-z0-9]+\.(jpg|jpeg|png|webp|heic|mp4|mov|webm)$')
   or coalesce(e->>'credit','') ~ '[<>]' or char_length(coalesce(e->>'credit',''))>120) then raise exception 'Mídia inválida'; end if;
 perform pg_advisory_xact_lock(214728,1);
 select id into rid from ajf_private.reports where author=u and request_id=(payload->>'request_id')::uuid;
 if found then return rid; end if;
 delete from ajf_private.reports where received_at<now()-interval '7 days';
 if (select count(*) from ajf_private.reports where author=u and received_at>now()-interval '1 hour')>=30
 or exists(select 1 from ajf_private.reports where author=u and received_at>now()-interval '1 minute') then raise exception 'Limite de envios: aguarde antes de tentar novamente'; end if;
 if (select count(*) from ajf_private.reports where received_at>now()-interval '1 hour')>=300 then raise exception 'Limite temporário do serviço. Tente mais tarde'; end if;
 if exists(select 1 from ajf_private.reports where author=u and not withdrawn and expires_at>now() and lower(street)=lower(s) and lower(neighborhood)=lower(n) and kind=k) then raise exception 'Você já enviou um relato recente para esse local'; end if;
 insert into ajf_private.reports(author,request_id,street,neighborhood,kind,description,lat,lng,observed_at,expires_at,media)
 values(u,(payload->>'request_id')::uuid,s,n,k,d,la,lo,t,t+interval '2 hours',m) returning id into rid;
 return rid;
end; $function$
;

update ajf_private.reports set expires_at = least(expires_at, observed_at + interval '2 hours') where expires_at > observed_at + interval '2 hours';
