export type Ponto = { id: string; nome: string; tipo: "alagamento" | "interdicao" | "deslizamento" | "relato"; descricao: string; lat: number; lng: number };
export const pontosCriticos: Ponto[] = [
  { id: "1", nome: "Rio Paraibuna", tipo: "alagamento", descricao: "Nível do rio em observação – risco de transbordamento", lat: -21.7600, lng: -43.3440 },
  { id: "2", nome: "Av. Brasil", tipo: "alagamento", descricao: "Pontos de alagamento ao longo da avenida", lat: -21.7560, lng: -43.3470 },
  { id: "3", nome: "Santa Luzia", tipo: "deslizamento", descricao: "Encostas com risco de deslizamento", lat: -21.7880, lng: -43.3600 },
  { id: "4", nome: "Benfica", tipo: "alagamento", descricao: "Ruas sujeitas a alagamento", lat: -21.6950, lng: -43.4300 },
  { id: "5", nome: "Poço Rico", tipo: "interdicao", descricao: "Via com interdição em caso de chuva forte", lat: -21.7660, lng: -43.3380 },
];
export const alertas = [
  { quando: "há 1h", texto: "Alerta de tempestade com vendaval e chuva moderada a forte. Evite áreas de risco, árvores e estruturas que possam cair. Proteja-se!" },
  { quando: "19/11 18:10", texto: "Alerta de pancadas isoladas de chuva em Juiz de Fora. Em caso de emergência ligue 199. Fonte: PJF" },
  { quando: "18/11 14:44", texto: "Alerta de Tempestade Severa com chuva moderada a forte. Proteja-se!" },
  { quando: "18/11 13:50", texto: "Alerta de tempestade acompanhada de raios e rajadas de vento em Juiz de Fora. Em caso de emergência ligue 199. Fonte: PJF" },
];
