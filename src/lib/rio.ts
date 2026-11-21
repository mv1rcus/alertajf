export type NivelRio = "normal" | "atencao" | "critico";
export type Rio = { hoje: number; normal: number; dias: { data: string; vazao: number; previsao: boolean }[] };

/** Regras: atenção quando a água passa de 1,6x o normal; crítico a partir de 2,5x. */
export function avaliarRio(hoje: number, normal: number): NivelRio {
  if (normal <= 0) return "normal";
  const r = hoje / normal;
  if (r >= 2.5) return "critico";
  if (r >= 1.6) return "atencao";
  return "normal";
}

/** Vazão diária do Rio Paraibuna (últimos 60 dias + 5 de previsão). Normal = mediana dos 60 dias. */
export async function buscarRio(): Promise<Rio> {
  const r = await fetch("https://flood-api.open-meteo.com/v1/flood?latitude=-21.76&longitude=-43.344&daily=river_discharge&past_days=60&forecast_days=6");
  const d = await r.json();
  const t: string[] = d.daily?.time ?? [];
  const v: number[] = (d.daily?.river_discharge ?? []).map((x: number | null) => x ?? 0);
  const iHoje = Math.max(0, t.length - 6);
  const passado = [...v.slice(0, iHoje)].sort((a, b) => a - b);
  const normal = passado[Math.floor(passado.length / 2)] ?? v[iHoje] ?? 0;
  const dias = t.slice(iHoje - 7, iHoje + 6).map((data, k) => ({ data, vazao: v[iHoje - 7 + k], previsao: iHoje - 7 + k > iHoje }));
  return { hoje: v[iHoje] ?? 0, normal, dias };
}
