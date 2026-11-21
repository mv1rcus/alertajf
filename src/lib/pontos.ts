export type Ponto = { id: string; nome: string; tipo: "alagamento" | "interdicao" | "deslizamento" | "sem_luz" | "relato"; descricao: string; lat: number; lng: number };
export const pontosCriticos: Ponto[] = [
  { id: "1", nome: "Rio Paraibuna", tipo: "alagamento", descricao: "Nível do rio em observação – risco de transbordamento", lat: -21.7600, lng: -43.3440 },
  { id: "2", nome: "Av. Brasil", tipo: "alagamento", descricao: "Pontos de alagamento ao longo da avenida", lat: -21.7560, lng: -43.3470 },
  { id: "3", nome: "Santa Luzia", tipo: "deslizamento", descricao: "Encostas com risco de deslizamento", lat: -21.7880, lng: -43.3600 },
  { id: "4", nome: "Benfica", tipo: "alagamento", descricao: "Ruas sujeitas a alagamento", lat: -21.6950, lng: -43.4300 },
  { id: "5", nome: "Poço Rico", tipo: "interdicao", descricao: "Via com interdição em caso de chuva forte", lat: -21.7660, lng: -43.3380 },
];
