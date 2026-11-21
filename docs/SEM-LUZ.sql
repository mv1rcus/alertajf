-- Habilita o tipo "sem_luz" nos relatos da comunidade.
-- Aplicar no Supabase (SQL Editor) somente depois da aprovação do Marcus.
-- Desfazer: voltar a restrição para ('alagamento','interdicao','deslizamento')
-- depois de apagar ou retirar os relatos sem_luz.
alter table ajf_private.reports drop constraint if exists reports_kind_check;
alter table ajf_private.reports add constraint reports_kind_check
  check (kind in ('alagamento','interdicao','deslizamento','sem_luz'));
