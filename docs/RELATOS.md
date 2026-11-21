# Relatos da comunidade: ativação pendente

O redesenho não cria conta, não conecta banco e não publica relatos falsos. Sem `VITE_REPORTS_API_URL`, o envio fica indisponível com explicação visível. Nenhuma chave secreta pode entrar em variável `VITE_`.

## Contrato da API

O frontend já lê `GET /reports` e envia `POST /reports` sob a URL HTTPS da variável `VITE_REPORTS_API_URL`. Esse servidor ainda precisa ser implementado e configurado antes de habilitar a variável. Uma URL configurada, sozinha, não ativa persistência.

GET retorna `{ "reports": [...] }`, somente aprovados e não vencidos. Campos: `id`, `street`, `neighborhood`, `kind` (`alagamento`, `interdicao`, `deslizamento`), `description`, `lat`, `lng`, `observed_at`, `expires_at`, `status` (`approved`), `source` (`citizen` ou `official`). Datas ISO com fuso. Resposta não inclui IP, identificador privado, contato ou dados de moderação.

POST aceita apenas `street`, `neighborhood`, `kind`, `description`, `lat`, `lng`, `observed_at` e o campo antispam `website` (que deve estar vazio). O servidor atribui `id`, data de recebimento, origem `citizen`, status `pending` e vencimento. Nunca aceitar `status`, `source`, `expires_at` ou poder de moderador do navegador. Retornar HTTP 202 e identificador apenas depois de gravação durável. POST não publica automaticamente.

## Banco de referência (não executado)

Esquema PostgreSQL sugerido, para ser revisado ao escolher/configurar o serviço. Não executar automaticamente em produção. Não há migração aplicada.

```sql
create table public.community_reports (
  id uuid primary key default gen_random_uuid(),
  street text not null check (char_length(street) between 3 and 120),
  neighborhood text not null check (char_length(neighborhood) between 2 and 80),
  kind text not null check (kind in ('alagamento','interdicao','deslizamento')),
  description text not null check (char_length(description) between 10 and 600),
  lat double precision not null check (lat between -22.1 and -21.3),
  lng double precision not null check (lng between -43.9 and -42.9),
  observed_at timestamptz not null,
  received_at timestamptz not null default now(),
  expires_at timestamptz not null,
  status text not null default 'pending' check (status in ('pending','approved','rejected','resolved')),
  source text not null default 'citizen' check (source in ('citizen','official')),
  reviewed_at timestamptz,
  reviewer_id uuid,
  check (expires_at > observed_at)
);
create index community_reports_active on public.community_reports(status, expires_at);
alter table public.community_reports enable row level security;
-- Se usado com Supabase, executar apenas após revisão das funções e papéis:
revoke all on public.community_reports from anon, authenticated;
-- Não há política de escrita pública. Todas as operações passam por API
-- com credencial de servidor, validação e autenticação de moderador.
-- Credencial service_role fica SOMENTE no servidor.
```

## O que falta antes de liberar

1. Confirmar responsável e substituto pela moderação. Não há promessa de atendimento 24 horas. Primeiro modo recomendado: todo relato aguarda revisão. Não oferecer chave de autoaprovação ao cliente. UI administrativa protegida e registro de quem aprovou, rejeitou, encerrou ou corrigiu cada item ainda precisam ser implementados.
2. Implementar a API acima com validação no servidor. Validar CEP/localidade por limites municipais quando houver geometria oficial, tamanho dos textos, coordenadas finitas, horário observado nas últimas 2 horas e nunca no futuro. A caixa geográfica do frontend é apenas filtro amplo, não prova de pertencer a JF.
3. Política inicial sugerida: expirar 2h após a observação, nunca 2h após uma aprovação tardia. Não aprovar um relato já vencido. Renovação requer nova observação e revisão. Expiração é decisão editorial, não limiar de segurança de órgão oficial. Aplicar filtro de vencimento no banco/API e no frontend. Relato encerrado não prova que uma rua ficou segura.
4. Proteger POST com limite por origem/sessão, limite global, deduplicação, CAPTCHA validado no servidor quando aplicável e proteção contra abuso. Honeypot sozinho não basta. Rejeitar campos extras e HTML; renderizar sempre como texto. Não expor contatos/IP nem localização do aparelho quando diferente do local que o usuário confirmou.
5. Autenticação forte para moderadores, autorização de servidor e trilha privada de auditoria. Fonte oficial somente por ingestão verificada ou curadoria com URL de origem. Aprovação humana não equivale a confirmação oficial. Definir canal de correção/denúncia e política de retenção. Até existir canal, não ativar envio público.
6. Configurar CORS para a origem do site, HTTPS, timeouts, monitoramento de indisponibilidade, retenção e backups exportáveis. Testar consultas de dois dispositivos e atualização da página, envio negado, falha de rede, aprovação, expiração e tentativas de alterar terceiros antes de liberar.
7. Supabase Free pode hospedar o banco no início, dentro de cotas. Pausa por inatividade e ausência de garantias impedem tratá-lo como sistema de emergência. Não ativar plano pago nem criar contas sem aprovação.

## Decisões do redesenho

- Sem pontos demonstrativos na camada de ocorrências reais.
- Indicador automático de risco/sirene e classificação experimental de transbordamento não aparecem na página. Os arquivos antigos continuam no repositório, mas não são montados.
- Previsão Open-Meteo é horária para a cidade, com data de consulta e estado indisponível. Não fornece previsão precisa por rua nem minuto.
- Radar exibe apenas passado recente, não previsão. Falhas e atraso são visíveis; cobertura local pode ser incompleta. A lista é alternativa ao mapa.
- Previsão gratuita requer uso não comercial e atribuição. Propaganda, assinatura ou finalidade promocional mudam o enquadramento. Não é garantia de disponibilidade.

Fontes de referência: https://open-meteo.com/en/terms , https://open-meteo.com/en/docs , https://www.rainviewer.com/api/transition-faq.html , https://supabase.com/pricing , https://supabase.com/docs/guides/database/postgres/row-level-security . Verificadas em 21/11/2026, revisar ao ativar.
