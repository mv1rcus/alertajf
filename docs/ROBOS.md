# Robôs de varredura do AlertaJF

Quatro robôs (GitHub Actions + Supabase + Gemini grátis) alimentam o mapa de relatos sozinhos, sem depender de ninguém ligado.

## Como funciona

```
portão (chuva?) -> Robô 1 (Instagram) ┐
                -> Robô 2 (Notícias)  ┴-> Robô 3 (baixa/converte) -> Robô 4 (publica)
```

Os robôs conversam por uma fila no Supabase (`public.ajf_fila`). Cada etapa tem estados (`novo`, `analisado`, `baixado`, `publicado`, `descartado`, `erro`) e log em `public.ajf_robos_log`. Se um robô falha, os outros seguem.

1. **Robô 1**: lê os perfis de Instagram de `robos/fontes.json` (posts e stories) e manda cada texto para a IA.
2. **Robô 2**: lê o Google Notícias (RSS) e manda cada notícia para a IA.
3. **Robô 3**: baixa o vídeo na hora e converte para **H.264 + AAC, mp4, faststart, até 720p e 7 MB** (toca em iPhone, Android e desktop; VP9/webm quebram no Safari do iPhone). Confere o codec com `ffprobe`.
4. **Robô 4**: publica pela função pública `ajf_submit` (mesmas regras e limites do formulário do site) e depois baixa o arquivo servido para conferir o codec.

## Ciclo dormir/acordar

O portão (`robos/portao.py`) usa o Open-Meteo (grátis) para JF. Os robôs **acordam** se choveu na última hora **ou** se há chuva prevista na próxima hora (chuva chegando). Quando a chuva acaba, o portão fecha em até ~1 hora e os robôs **voltam a dormir**: sem chuva nem previsão, só o job do portão roda (segundos de uso).
O radar RainViewer que o site usa só mostra o que já passou (sem previsão), então a antecipação vem do Open-Meteo.

## Regras de publicação (aplicadas na IA e de novo em código)

- Só **ocorrência real da chuva ATUAL em Juiz de Fora**: alagamento, enxurrada, deslizamento/queda de barranco, via interditada, queda de energia por chuva.
- Só com **local identificado** (rua ou bairro de JF no texto). Sem local, descarta.
- **Só da chuva de hoje**: a IA extrai o horário do fato; só publica se estiver dentro das últimas 5 h (a mesma janela de expiração do site). Post antigo de temporal passado é descartado mesmo que o perfil tenha postado agora.
- **Descarta** foto/vídeo genérico de céu ou chuva caindo, imagem de alerta (Defesa Civil, previsão, gráfico) e notícia de outra cidade.
- Todo relato leva **crédito da fonte** e o aviso **"Não verificado."**; expira em 5 h como os demais.

## Custo zero (e o que pode virar custo)

| Peça | Plano | Observação |
|---|---|---|
| GitHub Actions | repo público = grátis | se o repo virar privado, passa a ter limite de minutos |
| Gemini (AI Studio) | free tier, sem faturamento | não ative faturamento no projeto |
| Supabase | free | limite de 5 GB de banda/mês: se o site viralizar com muitos vídeos, pode estourar |
| Open-Meteo, Nominatim, Google Notícias | grátis | Nominatim: 1 consulta por segundo |

## Secrets do repositório (Settings > Secrets and variables > Actions)

`GEMINI_API_KEY`, `SUPABASE_SERVICE_ROLE`, `IG_USERNAME`, `IG_PASSWORD`. Nunca coloque chaves no código.

## Quando algo quebra (e como arrumar)

- **Instagram caiu** (issue "Robô do Instagram: login caiu"): entre na conta pelo app, aceite a verificação "foi você", depois rode o workflow "Varredura" com "forçar". Se a conta foi banida, o Google Notícias segue alimentando o site; troque `IG_USERNAME`/`IG_PASSWORD` por outra conta.
- **Instagram mudou o formato**: ajuste `robos/robo1_instagram.py` (usa a biblioteca `instaloader`; atualizar a versão costuma resolver).
- **IA com erro 429**: o robô espera e tenta de novo; passando do limite grátis, o item fica para a próxima rodada.
- **Ver o que está acontecendo**: tabelas `ajf_robos_log` e `ajf_fila` no Supabase; a aba Actions mostra cada rodada.

## Gatilho

O cron do GitHub atrasa (às vezes horas). O gatilho confiável é um job no cron-job.org chamando `workflow_dispatch` da "Varredura" a cada 15 minutos (grátis). O `schedule` no workflow é só o reserva.
