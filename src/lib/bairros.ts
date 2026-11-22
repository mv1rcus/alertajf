export type Bairro = { nome: string; lat: number; lon: number };

/** Bairros urbanos de Juiz de Fora com coordenada aproximada do centro (OpenStreetMap/Nominatim). */
export const BAIRROS: Bairro[] = [
  { nome: "Alto dos Passos", lat: -21.7763, lon: -43.3475 },
  { nome: "Bandeirantes", lat: -21.7216, lon: -43.3542 },
  { nome: "Bom Pastor", lat: -21.7768, lon: -43.3433 },
  { nome: "Borboleta", lat: -21.756, lon: -43.3796 },
  { nome: "Cascatinha", lat: -21.7839, lon: -43.3631 },
  { nome: "Centro", lat: -21.7601, lon: -43.3463 },
  { nome: "Cidade Nova", lat: -21.8038, lon: -43.3587 },
  { nome: "Costa Carvalho", lat: -21.7635, lon: -43.332 },
  { nome: "Dom Bosco", lat: -21.7783, lon: -43.3626 },
  { nome: "Esplanada", lat: -21.741, lon: -43.3796 },
  { nome: "Estrela Sul", lat: -21.7854, lon: -43.3546 },
  { nome: "Fábrica", lat: -21.7444, lon: -43.371 },
  { nome: "Granbery", lat: -21.7675, lon: -43.3438 },
  { nome: "Imaculada Conceição", lat: -21.7729, lon: -43.2975 },
  { nome: "Ipiranga", lat: -21.7911, lon: -43.3505 },
  { nome: "Jardim Glória", lat: -21.7531, lon: -43.358 },
  { nome: "Jardim Natal", lat: -21.7321, lon: -43.3995 },
  { nome: "João Paulo II", lat: -21.7618, lon: -43.3912 },
  { nome: "Linhares", lat: -21.7352, lon: -43.3258 },
  { nome: "Lourdes", lat: -21.7705, lon: -43.3271 },
  { nome: "Manoel Honório", lat: -21.7435, lon: -43.3537 },
  { nome: "Mariano Procópio", lat: -21.7462, lon: -43.3557 },
  { nome: "Monte Castelo", lat: -21.7478, lon: -43.3826 },
  { nome: "Morro da Glória", lat: -21.7492, lon: -43.3548 },
  { nome: "Mundo Novo", lat: -21.7783, lon: -43.3512 },
  { nome: "Niterói", lat: -21.7852, lon: -43.3077 },
  { nome: "Novo Horizonte", lat: -21.7967, lon: -43.392 },
  { nome: "Olavo Costa", lat: -21.7753, lon: -43.3366 },
  { nome: "Parque Guarani", lat: -21.716, lon: -43.3554 },
  { nome: "Poço Rico", lat: -21.7637, lon: -43.3392 },
  { nome: "Progresso", lat: -21.7309, lon: -43.3464 },
  { nome: "Salvaterra", lat: -21.806, lon: -43.3742 },
  { nome: "Santa Cecília", lat: -21.7813, lon: -43.3528 },
  { nome: "Santa Efigênia", lat: -21.8005, lon: -43.3581 },
  { nome: "Santa Luzia", lat: -21.7869, lon: -43.3447 },
  { nome: "Santa Rita", lat: -21.7357, lon: -43.3416 },
  { nome: "Santa Rita de Cássia", lat: -21.7357, lon: -43.3416 },
  { nome: "Santa Terezinha", lat: -21.7417, lon: -43.3605 },
  { nome: "Santo Antônio", lat: -21.7732, lon: -43.3127 },
  { nome: "São Dimas", lat: -21.7377, lon: -43.3766 },
  { nome: "São Mateus", lat: -21.7736, lon: -43.3547 },
  { nome: "São Pedro", lat: -21.7708, lon: -43.3879 },
  { nome: "São Sebastião", lat: -21.758, lon: -43.3533 },
  { nome: "Teixeiras", lat: -21.7909, lon: -43.3623 },
  { nome: "Universitário", lat: -21.7496, lon: -43.3583 },
  { nome: "Vale do Ipê", lat: -21.7533, lon: -43.3649 },
  { nome: "Vila Ideal", lat: -21.7795, lon: -43.3297 },
];

const semAcento = (s: string) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

/** Filtra bairros pelo texto digitado, ignorando acentos. */
export function buscarBairros(texto: string): Bairro[] {
  const q = semAcento(texto.trim());
  if (!q) return BAIRROS;
  return BAIRROS.filter((b) => semAcento(b.nome).includes(q));
}

/** Bairro da lista mais próximo de uma coordenada (GPS). */
export function bairroMaisProximo(lat: number, lon: number): Bairro | null {
  let best: Bairro | null = null; let bd = Infinity;
  for (const b of BAIRROS) {
    const d = Math.hypot((b.lat - lat) * 111, (b.lon - lon) * 95);
    if (d < bd) { bd = d; best = b; }
  }
  return best;
}
