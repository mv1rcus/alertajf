export type LeituraChuva = { time: string; mm: number };
export type ResumoChuva = {
  ultimaHora: number; acumulado24h: number; leituraEm: string; fresca: boolean;
  inicioEm: string; horasValidas: number; horasEsperadas: number; completa: boolean;
};
const HORA = 3600000;

/** Uma leitura por horário. Duplicatas não somam; em conflito usa o maior valor,
 * de forma determinística e conservadora, independentemente da ordem de chegada. */
export function normalizarChuva(leituras: LeituraChuva[], agora: number): LeituraChuva[] {
  const fimCompleto = Math.floor(agora / HORA) * HORA;
  const unicas = new Map<number, number>();
  for (const l of leituras) {
    const t = Date.parse(l.time);
    if (!Number.isFinite(t) || t > fimCompleto || t % HORA !== 0 || !Number.isFinite(l.mm) || l.mm < 0 || l.mm >= 1000) continue;
    unicas.set(t, Math.max(unicas.get(t) ?? 0, l.mm));
  }
  return [...unicas].sort((a, b) => a[0] - b[0]).map(([t, mm]) => ({ time: new Date(t).toISOString(), mm }));
}

/** Janela de 24 horas encerrada na última leitura horária disponível, nunca no
 * relógio da página. Uma hora ausente torna a soma parcial, não zero medido. */
export function resumirChuva(leituras: LeituraChuva[], agora: number): ResumoChuva | null {
  const validas = normalizarChuva(leituras, agora);
  const ultima = validas.at(-1);
  if (!ultima) return null;
  const fim = Date.parse(ultima.time);
  const inicio = fim - 24 * HORA;
  const janela = validas.filter((l) => Date.parse(l.time) > inicio && Date.parse(l.time) <= fim);
  return {
    ultimaHora: ultima.mm,
    acumulado24h: Math.round(janela.reduce((s, l) => s + l.mm, 0) * 10) / 10,
    leituraEm: ultima.time, inicioEm: new Date(inicio).toISOString(),
    fresca: agora - fim <= 2.5 * HORA,
    horasValidas: janela.length, horasEsperadas: 24, completa: janela.length === 24,
  };
}

/** Ordem explícita de referência, não maior chuva nem corrida entre respostas.
 * A primeira estação com leitura válida permanece; demais são só fallback. */
export function escolherEstacaoChuva<T extends { ordem: number; leituras: LeituraChuva[] }>(candidatas: T[], agora: number): T | undefined {
  return [...candidatas].sort((a, b) => a.ordem - b.ordem).find((c) => normalizarChuva(c.leituras, agora).length > 0);
}
