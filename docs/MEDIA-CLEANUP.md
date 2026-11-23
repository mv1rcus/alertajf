# Exclusão das mídias após 5h

## Situação deste PR
Código preparado, **ainda não instalado em produção**. O texto do site corrige a promessa anterior: o pino some após 5h, mas até a ativação da rotina o arquivo pode continuar acessível pelo link direto.

## Proposta para aprovar
1. Aplicar `MEDIA-CLEANUP.sql`: fila privada, preservação dos caminhos antes da limpeza de linhas antigas e três RPCs exclusivas de service_role. Não altera ajf_submit nem a validade de 5h; não apaga arquivos.
2. Publicar `supabase/functions/cleanup-report-media` no projeto dedicado. A função usa a chave de serviço já fornecida pelo ambiente da Edge Function. Não aceita destinos/caminhos enviados pelo cliente. Exige POST e Authorization igual à chave de serviço, e sempre usa apenas o bucket relatos-midia.
3. Guardar o JWT service_role existente no Supabase Vault com nome `ajf_cleanup_service_role` pelo painel seguro. Nunca colocar esse valor no repo, frontend ou chat. Nenhum token novo é necessário.
4. Aplicar `MEDIA-CLEANUP-SCHEDULE.sql`: cron a cada minuto por pg_net, invocando a Edge Function. Gratuito dentro das cotas do Supabase Free, sem upgrade. São cerca de 43.200 chamadas/mês. Confirmar as cotas atuais no painel antes de ativar; se indisponível, parar sem contratar plano.
5. Testar com imagem PNG sintética sem pessoas, num prefixo `r/cleanup-test-<uuid>.png`, vinculada somente a fixture privada com expiração já vencida, nunca no feed público. Confirmar URL acessível antes, executar a rotina, confirmar Storage sem objeto e URL sem arquivo depois. Criar também fixture privada futura para confirmar que o arquivo ativo permanece; remover a fixture/arquivo sintético apenas no escopo do teste aprovado. Verificar grants (anon/authenticated não executam as RPCs). Não executar teste usando mídia real de morador.
6. Conferir job e execução efetiva. Só depois trocar a mensagem provisória do site por: "O pino e a mídia saem do mapa 5h após o horário observado. Os arquivos são excluídos pela limpeza automática após esse prazo, normalmente em até alguns minutos. Falhas temporárias podem atrasar a exclusão; cópias feitas por terceiros não são controladas pelo site."

## Limites e segurança
- Somente arquivos referenciados por relatos expirados. Nunca varre o bucket nem apaga anexos ativos, retirados antes da validade ou órfãos sem vínculo conhecido.
- Nova checagem imediatamente antes de cada exclusão protege referências ativas compartilhadas. Não existe edição pública para reativar relatos. Operações administrativas concorrentes que estendam expiração devem pausar o cron primeiro.
- Até 100 objetos por execução; exclusão pela API Storage, nunca `delete from storage.objects`. A confirmação da fila só ocorre depois da resposta de sucesso. Falhas tentam de novo na execução seguinte.
- Nenhuma chave nem URL de mídia pessoal é registrada nos logs. A fila guarda apenas path, prazo e confirmação, protegida por RLS e sem grants públicos.
- A retirada/denúncia oculta do mapa, mas esta proposta só exclui fisicamente depois do prazo original, conforme o pedido de 5h. Uploads abandonados sem relato são outro problema e não entram na exclusão desta proposta.
- Reversão: desativar o cron. Exclusão física não é reversível; não há backup prometido.
- A migração protege referências de futuras exclusões de linhas, mas não recupera referências que já tenham sido apagadas antes da instalação.

## Testes locais
`node --test supabase/functions/cleanup-report-media/cleanup.test.mjs` cobre filtro de paths, ordem de chamadas, referência ativa, falha de Storage, ausência de ack em falha e falha fechada na seleção. Teste real depende da aprovação da instalação.

## Fontes
- https://supabase.com/docs/guides/storage/management/delete-objects
- https://supabase.com/docs/guides/functions/schedule-functions
- https://supabase.com/docs/guides/storage/security/access-control
