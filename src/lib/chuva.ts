export type LeituraChuva = { time: string; mm: number };
export type ResumoChuva = { ultimaHora: number; acumulado24h: number; leituraEm: string; fresca: boolean };

/** Resume as leituras horárias de uma estação pluviométrica: mm da última hora
 *  medida e acumulado das últimas 24h. Ignora leituras futuras ou inválidas e
 *  marca como "fresca" apenas quando a última leitura tem até 2h30 de atraso. */
export function resumirChuva(leituras: LeituraChuva[], agora: number): ResumoChuva | null {
  const validas = leituras.filter((l) => Number.isFinite(Date.parse(l.time)) && Date.parse(l.time) <= agora + 60000 && Number.isFinite(l.mm) && l.mm >= 0 && l.mm < 1000);
  if (!validas.length) return null;
  const ultima = validas[validas.length - 1]!;
  const desde = agora - 24 * 3600000;
  const acumulado = validas.filter((l) => Date.parse(l.time) > desde).reduce((s, l) => s + l.mm, 0);
  return { ultimaHora: ultima.mm, acumulado24h: Math.round(acumulado * 10) / 10, leituraEm: ultima.time, fresca: agora - Date.parse(ultima.time) <= 2.5 * 3600000 };
}
