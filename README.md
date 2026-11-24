# AlertaJF

**Juiz de Fora de olho no tempo.** Mapa ao vivo de chuva, alagamentos e emergências em Juiz de Fora (MG).

**Site no ar:** https://alertajf.vercel.app/
**TikTok:** [@alertajf](https://www.tiktok.com/@alertajf)

## O que o site mostra

- **Radar de chuva ao vivo** sobre o mapa de JF, com animação dos últimos quadros e previsão de curto prazo (RainViewer; radar do INPE como alternativa).
- **Relatos da comunidade no mapa**: alagamentos, vias interditadas e deslizamentos reportados por quem está na rua, com **foto e vídeo** do local. Cada pino fica no mapa por 5 horas e sai automaticamente.
- **Nível do Rio Paraibuna e de outros rios de JF**, com leituras das estações de telemetria da ANA e indicação de atenção quando a vazão passa do normal.
- **Previsão para JF**: chuva e rajadas de vento agora e nas próximas horas (Open-Meteo), com selo de risco quando há temporal.
- **Descargas elétricas** quase em tempo real na região (rede de detecção do INPE/CPTEC).
- **Alertas oficiais**: avisos do INMET e o último alerta da Defesa Civil de Juiz de Fora, sempre com horário e fonte.
- **Emergência em um toque**: botões diretos para a **Defesa Civil (199)** e os **Bombeiros (193)**, e instruções para receber os alertas oficiais por SMS (envie seu CEP para **40199**).

Tudo com dados focados em Juiz de Fora, gratuito e sem cadastro. Dá para instalar como app na tela inicial do celular.

## Importante

O AlertaJF é um **projeto independente**, sem vínculo com Prefeitura, Defesa Civil, INMET ou ANA. Os relatos da comunidade são publicados sem revisão prévia e não são verificados. Previsões e medições podem falhar ou atrasar. **Em perigo, busque um local seguro e use os canais oficiais (199 / 193).**

## Tecnologia

Site estático em React + TypeScript (Vite), mapa com Leaflet/OpenStreetMap, relatos e mídia no Supabase, deploy na Vercel.

## Desenvolvimento

```sh
git clone https://github.com/mvthebest/alertajf.git
cd alertajf
npm i
npm run dev
```
