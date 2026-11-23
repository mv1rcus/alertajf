-- AlertaJF: liga a mídia enviada pelo Marcus (Instagram @jfdepressao/@jfdepressao02) aos pinos de 22/11.
-- Rodar DEPOIS de RELATOS-MIDIA.sql e depois do upload dos arquivos ao bucket relatos-midia.
begin;
update ajf_private.reports set media='[{"path":"r/padre-cafe.mp4","kind":"video","credit":"@jfdepressao (Instagram)"}]'::jsonb where id='0b364246-16bf-4e8d-a157-0cf0916ea6cb';
update ajf_private.reports set media='[{"path":"r/av-juiz-de-fora-mg353.mp4","kind":"video","credit":"@jfdepressao02 (Instagram)"}]'::jsonb where id='54460ab4-b832-43c9-871c-24262c028930';
update ajf_private.reports set media='[{"path":"r/av-jk-top-fitness.mp4","kind":"video","credit":"@jfdepressao (Instagram)"}]'::jsonb where id='aa24d6c8-d1e3-4b63-9e4c-341c896e681e';
update ajf_private.reports set media='[{"path":"r/geraldo-scaldine.mp4","kind":"video","credit":"@jfdepressao (Instagram)"}]'::jsonb where id='c2780661-d917-4a1a-85e5-55bbdf51e870';
update ajf_private.reports set media='[{"path":"r/santa-luzia-ribeirao.mp4","kind":"video","credit":"@jfdepressao (Instagram)"}]'::jsonb where id='e8bf1fd8-1ec3-4ccf-8742-50a221c9f541';
update ajf_private.reports set media='[{"path":"r/odorico-filgueiras-pinto.mp4","kind":"video","credit":"@jfdepressao (Instagram)"}]'::jsonb where id='5524dbe3-ea73-41de-8b38-832a19a43898';
update ajf_private.reports set media='[{"path":"r/airton-ribeiro-foto.jpg","kind":"image","credit":"@jfdepressao (Instagram)"},{"path":"r/airton-ribeiro-video.mp4","kind":"video","credit":"@jfdepressao (Instagram)"}]'::jsonb where id='1a2a2a2a-869a-4538-a586-993f9ef5e66b';
commit;
