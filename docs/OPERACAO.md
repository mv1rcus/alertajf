# Operação do AlertaJF (a bíblia para quem assumir)

Escrito em 24/11/2026. Contém só nomes de itens do cofre, nunca valores. Sempre confira o estado ao vivo antes de agir.

## 1. O que é
Site de alerta de chuva de Juiz de Fora: https://alertajf.vercel.app. Repo público github.com/mvthebest/alertajf (sincronizado com o Lovable), Vercel Hobby (grátis), Supabase grátis (projeto fnpssjnsljhwdoikfwcu). Quatro robôs publicam ocorrências no mapa.

## 2. Regras duras do Marcus
- Só ferramentas grátis. Avisar qualquer coisa que possa custar. Cadastro que pedir cartão ou endereço de cobrança: parar, preencher nada, avisar o agente principal (Main).
- Publicar só ocorrência real de chuva AGORA em JF, com local identificado. Descartar foto genérica de céu e imagem de alerta.
- Mídia: vídeo H.264/AAC mp4; foto JPEG (bucket relatos-midia).
- Crédito da fonte sempre visível, marcado "Não verificado". Cada pin dura 2 h. Nunca forçar pin público para teste.
- Os robôs acordam com chuva confirmada (>= 0,3 mm na última hora, Open-Meteo) ou previsão chegando.
- Autoria de commit: só mvthebest, sem co-autor.
- O robô NUNCA loga no Instagram, não segue, não curte, não posta. Nada de trocar senha do Instagram.
- Qualquer conta nova, segredo ou código de verificação por telefone/email: confirmar com Main ANTES, agrupar os pedidos de código, avisar Main antes de pedir ao Marcus.
- Marcus quer relatório curto em português, separando jobs, candidatos e pins. Reconhecer erro próprio.

## 3. Os 4 robôs (pasta robos/)
- Robô 1, robo1_instagram.py: Instagram. Posts: leitor próprio por embed público (principal) e serviços de terceiros como reserva. Stories: Apify. A IA lê só texto.
- Robô 2, robo2_noticias.py: Google News e RSS locais.
- Robô 3, robo3_baixar.py: baixa e converte a mídia.
- Robô 4, robo4_publicar.py: publica (fila ajf_fila para pins).
- portao.py: portão de chuva (só Open-Meteo). Previsão sozinha abre o portão.
- Configuração: robos/fontes.json (perfis, tetos, intervalos, ordem das reservas). common.py: utilidades, estado, IA (Gemini).
- scripts/defesa_civil.py: alertas da Defesa Civil (workflow defesa-civil.yml).

## 4. Gatilhos e agenda
- varredura.yml (workflow_dispatch + cron reserva). O gatilho real é o cron-job.org, job 8935035, a cada 10 min (o comentário no workflow ainda diz 15). Defesa Civil: cron-job.org a cada 10 min.
- Robô 1 serviços: perfis_por_varredura 9, intervalo_min 15 (cada um dos 12 perfis relido em ~27 min com chuva). Stories: 12 perfis, a cada 60 min.
- diag-embed.yml: workflow manual só de leitura para testar o embed do IP do GitHub.

## 5. Instagram, estado dos leitores
12 perfis em fontes.json servicos.perfis: transitojuizdefora, jfdepressao, noticiasjf1, luismar.tv, jfdepressao02, jfnoticias.com.br, eucurtojf, matheusbrumjornalista, acessa.com_, mgbron_line_, folhajf, tribunademinas.
- embed (principal, grátis, sem cota): instagram.com/<perfil>/embed/ traz os 6 posts mais recentes (contextJSON). O mp4 vem de instagram.com/p/<código>/embed/captioned/ (video_url). Usar User-Agent simples ("Mozilla/5.0"); com UA de navegador completo vem outra página sem video_url. Se falhar em todos os perfis (401/403/429), o embed pausa 1 h e os terceiros assumem sozinhos. Testado do IP da AWS e de um runner do GitHub (HTTP 200).
- Reservas (planos grátis, tetos em fontes.json servicos.teto): Scrappa (450/mês, 25/dia), maviapi (1500/mês, 60/dia, vale até 2026-12-01), herascrape (2400, 25/dia), SocialTap (100 únicos), CreatorCrawl (50 únicos). api.sh: conta criada e chave testada (1.000 créditos/mês, `fresh` custa 1 crédito igual), NÃO ligado no robô.
- Stories: Apify (ator lance_api/instagram-stories-scraper-api), cobra por perfil lido, teto 60/dia e 800/mês (o crédito grátis real pode ser ~700 leituras). Sem login, não existe leitura grátis ilimitada de story (testado: página de stories pede login; espelhos usam contas por trás).
- Estado e uso: ajf_estado, chave robo1_uso.
- Removido a pedido do Marcus: Bright Data (o segredo BRIGHTDATA_KEY ainda existe no GitHub, inofensivo; apagar com o Marcus com o app GitHub aberto por causa do sudo).

## 6. Cofre (nomes dos itens, valores nunca)
GitHub PAT alertajf (instinct) · GitHub mvthebest · Supabase access token alertajf · Supabase alertajf database · Gemini API key alertajf-varredura · Apify API token (AlertaJF) · Scrappa API key (AlertaJF) · herascrape API key AlertaJF · maviapi API key AlertaJF · SocialTap API key AlertaJF · CreatorCrawl API key AlertaJF · api.sh API key (AlertaJF) e api.sh (AlertaJF, Agent Mail) · cron-job.org (AlertaJF, Agent Mail) · GitHub PAT alertajf-defesa-civil-cron (cron-job.org) · Vercel via GitHub mvthebest · Lovable · Instagram (chuvas JF) e Instagram (robô JF, conta nova) (o robô NÃO usa).
Receita: `tools vault write-file --key password --name '<item>' --return-channel none --json` devolve um caminho; ler com $(cat caminho) no mesmo comando, nunca imprimir, apagar a pasta do cofre depois. Itens criados por agente começam sem acesso do sandbox: pedir o link de aprovação via Main. O email do agente (xitik2@mail.instinct.com) recebe os códigos de cadastro.

## 7. Como publicar mudanças
- Código do robô (robos/, scripts/, docs/): commit como mvthebest (`git -c user.name=mvthebest -c user.email=68456420+mvthebest@users.noreply.github.com commit`), push da branch com o PAT (cabeçalho Authorization Basic de x-access-token:TOKEN), abrir o PR pelo navegador na nuvem (config-h, github.com: https://github.com/mvthebest/alertajf/compare/main...BRANCH?expand=1, "Create pull request"), mergear pela API (PUT /pulls/N/merge, squash). O PAT não cria PR, não edita workflow, segredo nem issue: isso vai pelo navegador, e mexer em segredo dispara confirmação no GitHub Mobile do Marcus (avisar Main antes, os dígitos valem ~1 min).
- Visual/front-end (src/): só com ok do Marcus por PR, repassado por Main. A cota de deploy da Vercel Hobby acaba até ~11h de 25/11; mudanças só de robos/ e scripts/ não gastam deploy.
- Depois de cada lease de navegador: `tools cloud_browser report --outcome` por site.

## 8. Prova de saúde
- Runs: https://api.github.com/repos/mvthebest/alertajf/actions/workflows/varredura.yml/runs?per_page=8 (público; logs exigem o PAT).
- Supabase (API de gestão, POST /v1/projects/fnpssjnsljhwdoikfwcu/database/query): tabelas public.ajf_robos_log, public.ajf_fila, public.ajf_estado, ajf_private.reports (pins), ajf_private.reactions.
- Sem chuva o robô só registra "poupando a cota grátis": isso é normal.

## 9. Pendências em aberto (24/11 noite)
1. Validar o campo has_public_story do embed contra o Apify (o robô já grava a linha "Validação has_public_story" no ajf_robos_log na primeira chuva). Se o campo discriminar story ativo, ligar stories.filtrar_por_flag em fontes.json (PR de 1 linha). Se não, não adianta.
2. Primeira varredura com chuva real: ler o log do embed e confirmar que saem pins.
3. Depois do deploy da Vercel (~11h de 25/11): conferir a legenda do radar a 390 px.
4. Apagar o secret BRIGHTDATA_KEY (com o Marcus). Corrigir o comentário "15 min" do varredura.yml (só pelo navegador).
5. Retestar de vez em quando os espelhos de stories (storiesfly, insnoop, insmask, imginn, picuki, greatfon, storiesig, anonyig e novos). Aprovar só se aguentar leitura automatizada sem login, sem chave e sem anúncio por 2 dias seguidos. Em 24/11: imginn, picuki, greatfon dão 403 do Cloudflare; storiesig.info e anonyig bloqueiam nosso IP; os outros só funcionam pelo navegador.
6. Possível: subir perfis por varredura ou stories se o Marcus pedir; sempre conferir tetos e custo (tudo precisa continuar grátis).

## Segurança da sessão do Instagram (25/11/2026)
- Sessão do @mv1thebest caiu (regra do Marcus, 25/11): o robô religa sozinho com as credenciais salvas, sem ficar parado. Login falhou: pausa de 1h e nova tentativa. Challenge/checkpoint: pausa de 2h, com calma, sem martelar. 429: 6h. Avisar o Marcus se pedir ação dele (ex.: aprovar dispositivo no celular).
- O workflow NÃO guarda mais cache de sessão (repo público: cache de sessão logada é risco). O robô1 só escreve sessão numa pasta temporária da rodada. A sessão do leitor logado (@mv1thebest) vive só na tabela privada ajf_segredos. Estado da descoberta de perfis: ajf_estado, chave ig_descoberta. Nunca reintroduzir actions/cache para sessão, cookie ou storage state.
- Pendente com o Marcus: apagar os secrets órfãos IG_USERNAME, IG_PASSWORD, IG_TOTP_SECRET do GitHub (app aberto, por causa do sudo).
