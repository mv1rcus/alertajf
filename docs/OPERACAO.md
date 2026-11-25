# Guia de operação do AlertaJF

Documento de referência para manutenção humana. Descreve a arquitetura e práticas observadas no projeto; detalhes operacionais podem mudar e devem ser confirmados nas configurações e serviços atuais antes de uma manutenção. Este arquivo não substitui revisão, aprovação ou autorização para alterações.

## 1. Projeto

O AlertaJF é um site independente de alertas de chuva, alagamentos e deslizamentos em Juiz de Fora: https://alertajf.vercel.app. O repositório público é `mv1rcus/alertajf`; o projeto usa Vercel, Supabase e workflows do GitHub Actions.

## 2. Comportamento do mapa

- Os relatos publicados devem corresponder a uma ocorrência de chuva em Juiz de Fora com local identificável. Imagens genéricas de céu e imagens de alertas não são evidência de uma ocorrência local.
- Pins exibem a fonte e a indicação “Não verificado”. A duração configurada é de 2 horas.
- Testes não devem criar relatos públicos.
- A mídia de relatos é preparada como MP4 (H.264/AAC) ou JPEG, conforme o tipo de arquivo.
- O portão de chuva usa dados do Open-Meteo. A configuração atual fica no código do projeto; confira-a antes de interpretar por que uma execução prosseguiu ou parou.

## 3. Componentes

- `robos/robo1_instagram.py`: leitura de posts públicos incorporados e leitura de stories por provedor configurado.
- `robos/robo2_noticias.py`: busca em Google News e feeds RSS locais.
- `robos/robo3_baixar.py`: obtenção e conversão da mídia selecionada.
- `robos/robo4_publicar.py`: processamento da fila de ocorrências.
- `robos/portao.py`: avaliação das condições de chuva.
- `robos/fontes.json`: fontes, limites e intervalos dos leitores.
- `robos/common.py`: funções compartilhadas, estado e integração de IA.
- `scripts/defesa_civil.py` e o workflow `defesa-civil.yml`: atualização dos alertas da Defesa Civil.

## 4. Agenda e frequência

A configuração registrada em 24/11/2026 indicava execução de varredura e atualização da Defesa Civil a cada 10 minutos pelo cron-job.org, com workflows do GitHub Actions como destino. O arquivo de workflow `varredura.yml` também contém um agendamento de reserva.

Na configuração então registrada, o leitor de serviços processava 9 perfis por varredura, com intervalo de 15 minutos; 12 perfis eram revisitados em aproximadamente 27 minutos durante chuva. A leitura de stories era programada para 12 perfis a cada 60 minutos. Esses valores são um retrato, não garantia do estado atual. Confirme as configurações em `robos/fontes.json`, nos workflows e no agendador antes de diagnosticar atrasos.

`diag-embed.yml` é um workflow manual de diagnóstico do leitor de embeds. Seu objetivo é apenas verificar a resposta pública do embed.

## 5. Leitores e limites de provedores

O leitor principal de posts usa embeds públicos do Instagram. Provedores externos estão configurados como alternativas quando a fonte principal falha. Stories dependem de um provedor externo e podem consumir cota; disponibilidade, limites e custos mudam conforme o plano do serviço.

Antes de alterar fontes, intervalos ou provedores, confira `robos/fontes.json` e os termos, preços e limites atuais do serviço. O projeto deve continuar dentro dos planos aprovados e sem custos inesperados. Se houver cobrança, exigência de cartão ou mudança de plano, interrompa essa alteração e obtenha aprovação explícita antes de prosseguir.

O estado e os contadores dos leitores são mantidos no banco do projeto. Use os painéis e consultas já aprovados para manutenção; não inclua dados de acesso, respostas de autenticação ou conteúdo privado em documentação, issues, commits ou logs.

## 6. Segurança e privacidade

- O repositório é público. Não registre nele senhas, tokens, chaves, códigos de verificação, cookies, sessões autenticadas ou dados privados.
- A configuração do workflow não deve persistir cookies ou estado de sessão de navegador em cache.
- Os leitores públicos devem preferir fontes acessíveis sem autenticação. Qualquer necessidade nova de autenticação, conta ou acesso deve passar pelo processo de aprovação apropriado e pelo armazenamento seguro já adotado para o projeto.
- Não automatize login, troca de senha, interação social ou publicação em contas pessoais como parte do leitor de fontes.
- Para um segredo exposto ou suspeita de acesso indevido, preserve o registro do incidente e encaminhe a um mantenedor autorizado para resposta pelo canal seguro. Não copie o segredo para relatórios.

## 7. Diagnóstico

Para investigar uma execução:

1. Confira no GitHub Actions o horário, o workflow, o resultado e o resumo da execução.
2. Compare o horário com a agenda atual do cron-job.org e com as configurações atuais dos leitores.
3. Diferencie falha de fonte, limite de provedor, portão de chuva fechado e ausência de candidato válido.
4. Confirme no painel do projeto o estado da fila e os registros de execução, usando apenas o acesso autorizado já disponível.
5. Antes de concluir que uma ocorrência foi publicada, confira o mapa público e a fonte exibida no pin.

Em períodos sem chuva, uma execução sem publicação pode ser normal. Um resultado sem pin, por si só, não comprova falha.

## 8. Alterações no projeto

Para uma mudança de código ou documentação, trabalhe em uma branch separada, faça a revisão e os testes pertinentes e abra um pull request para `main`. Descreva o escopo e os resultados dos testes. Não faça merge até a revisão e aprovação exigidas para aquela mudança. Alterações em `src/` podem iniciar um deploy; mudanças em `robos/`, `scripts/` e `docs/` normalmente não alteram a interface, mas confirme o comportamento atual dos workflows e da hospedagem.

Use os fluxos seguros e aprovados de GitHub, Vercel e Supabase. Não coloque credenciais em comandos copiados para documentação, no histórico do shell ou em registros de execução. Para mudanças de configuração que possam gerar custo ou afetar dados públicos, apresente o impacto e obtenha aprovação antes de aplicá-las.

## 9. Verificação após manutenção

Depois de uma alteração, confirme o resultado no serviço correspondente: execução do workflow, estado do leitor, fila de ocorrências e visualização pública do site. Registre um resumo curto em português, separando execuções, candidatos e pins, e indique claramente qualquer falha ou incerteza.
