# Relatos da comunidade

Implementado no PR #4, aguardando revisão e aprovação antes de entrar em produção.

## O que aparece

Relatos são publicados imediatamente como **relato da comunidade, não verificado**. Não há aprovação oficial nem classificação de segurança. “Também vi” mostra um número de apoios de sessões diferentes. O próprio autor não pode apoiar, e cada sessão só pode apoiar uma vez. Apoios não transformam o relato em confirmado.

Os relatos somem da consulta e do mapa 2 horas após a observação. Isso não significa que a rua ficou segura. O autor pode retirar seu relato no mesmo navegador. Três denúncias de sessões diferentes ocultam um relato. Essas regras são simples e podem sofrer abuso; não há atendimento ou revisão humana garantidos.

## Implementação e acesso

- Projeto dedicado: https://supabase.com/dashboard/project/fnpssjnsljhwdoikfwcu
- Supabase Free, região São Paulo. Nenhum cartão ou plano pago.
- `src/lib/reports-config.ts` contém somente URL do projeto e chave **publishable**, feitas para o navegador. Não colocar senha, `service_role`, chave secreta ou token administrativo em `VITE_*` ou no repositório.
- Não precisa de variável de ambiente secreta na Vercel. A publicação desse PR habilita o cliente para o projeto dedicado.
- Tabelas em `ajf_private`, fora do schema público e sem grants para `anon`/`authenticated`, com RLS habilitada e sem políticas diretas. As únicas operações expostas são as funções abaixo, com `search_path` fixo e grants mínimos.
- `ajf_reports`: leitura pública apenas de campos necessários, últimos 100 ativos, não retirados e não ocultados. Nunca retorna autor, IP, contato ou tokens.
- `ajf_submit`: sessão anônima autenticada, validação de texto, campos extras recusados, tipos, coordenadas regionais, observação das últimas 2h sem futuro, honeypot, expiração calculada no banco, origem fixa da comunidade e ID de tentativa para reenvio idempotente.
- `ajf_react`: sem autoapoio/autodenúncia, sem repetição, apenas ativo, limite por sessão e global.
- `ajf_withdraw`: autor da mesma sessão pode retirar, ninguém pode alterar relatos alheios.
- SQL de instalação revisado e aplicado no banco dedicado, disponível em `docs/COMMUNITY.sql`. Não executar novamente sem migração: o script inicial cria objetos e não é idempotente.

## Limites e privacidade

- 5 relatos/hora/sessão, intervalo mínimo de 1 minuto.
- 100 relatos/hora para o projeto, com serialização no banco contra concorrência.
- 30 ações/hora/sessão e 500 ações/hora/projeto.
- Autenticação Supabase limita por padrão a criação de sessões anônimas a 30/hora por IP; não alterado.
- Sessão não equivale a pessoa. Apagar armazenamento, trocar navegador ou IP pode contornar parte dos limites. Não anunciar identidade verificada nem proteção absoluta contra spam. CAPTCHA não está configurado; avaliar se houver abuso.
- A caixa regional é ampla, não um teste de pertença ao município. O formulário diz JF e entorno. Não geocodificar para alegar localização exata de endereço.
- Campos de localização e texto são públicos. GPS só é pedido pelo botão e o usuário confirma o ponto. O frontend renderiza texto sem HTML.
- Registros vencidos ficam fora da consulta pública; registros com mais de 7 dias são apagados na próxima publicação. Sem publicação posterior, os registros antigos podem permanecer privados. Sessões anônimas e logs do serviço seguem a retenção do provedor e não são apagados pelo script de relatos.
- A senha do banco fica no cofre e não é usada pelo frontend. Tokens de sessão ficam no armazenamento local do visitante. Não há e-mail, telefone ou cadastro obrigatório.
- Falhas não são traduzidas em ausência de perigo. Um envio de resultado incerto pede atualizar a lista; o ID da tentativa impede duplicação no mesmo formulário.

## Verificação antes da entrega

- Build completo, TypeScript e 9 testes existentes passaram.
- Consulta HTTP real retornou lista vazia e autenticação anônima respondeu corretamente.
- Teste SQL em uma transação com rollback passou: permissões, inserção, idempotência, limite, autoapoio, apoio duplicado, falsificação de origem oficial, contagem de apoio, ocultação com 3 denúncias e expiração. Banco ficou vazio após rollback. Nenhum relato fictício foi mantido.
- Verificar retirada, rede indisponível, UI desktop/celular e carregamento do deploy de prévia antes de pedir aprovação.
- Não publicar teste fictício no feed. Testes de escrita devem usar transação e rollback ou ambiente isolado não público.

## Limitações operacionais

Supabase Free pode pausar por inatividade e tem cotas. Não há garantia de disponibilidade nem backup gerenciado nesta configuração. Não é um canal de emergência. Em perigo, buscar local seguro e ligar 199 ou 193.
