/** Selo de frescor dos dados: mostra há quanto tempo a fonte foi lida.
 *  Verde até 20 min; âmbar ("stale") depois disso. Não renderiza sem timestamp válido. */
export function idadeTexto(ts?: string | null): string | null {
  if (!ts) return null;
  const ms = Date.now() - Date.parse(ts);
  if (!Number.isFinite(ms) || ms < 0) return null;
  const min = Math.round(ms / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  if (min < 1440) return `há ${Math.floor(min / 60)} h`;
  return `há ${Math.floor(min / 1440)} d`;
}

export function Fresco({ ts }: { ts?: string | null }) {
  const t = idadeTexto(ts);
  if (!t) return null;
  const velho = Date.now() - Date.parse(ts!) > 20 * 60000;
  return <span className={`fresh${velho ? " stale" : ""}`}>{t}</span>;
}
