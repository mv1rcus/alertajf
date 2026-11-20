export type Clima = { chuvaMm: number; rajadaKmh: number; codigo: number };
export type Nivel = "normal" | "atencao" | "critico";

/** Regras de alerta: crítico = chuva >= 10 mm/h, rajadas >= 60 km/h ou trovoada. */
export function avaliarRisco(c: Clima): { nivel: Nivel; motivos: string[] } {
  const crit: string[] = [];
  const at: string[] = [];
  if (c.chuvaMm >= 10) crit.push(`Chuva forte (${c.chuvaMm.toFixed(1)} mm/h)`);
  else if (c.chuvaMm >= 5) at.push(`Chuva moderada (${c.chuvaMm.toFixed(1)} mm/h)`);
  if (c.rajadaKmh >= 60) crit.push(`Rajadas de vento de ${Math.round(c.rajadaKmh)} km/h`);
  else if (c.rajadaKmh >= 45) at.push(`Ventos de ${Math.round(c.rajadaKmh)} km/h`);
  if (c.codigo >= 95) crit.push("Tempestade com raios");
  if (crit.length) return { nivel: "critico", motivos: crit };
  if (at.length) return { nivel: "atencao", motivos: at };
  return { nivel: "normal", motivos: [] };
}

/** Pior condição entre agora e as próximas 3 horas em Juiz de Fora. */
export async function buscarClima(): Promise<Clima> {
  const url = "https://api.open-meteo.com/v1/forecast?latitude=-21.7642&longitude=-43.3503&current=precipitation,wind_gusts_10m,weather_code&hourly=precipitation,wind_gusts_10m,weather_code&forecast_hours=3&timezone=America%2FSao_Paulo";
  const r = await fetch(url);
  const d = await r.json();
  const h = d.hourly ?? {};
  const max = (a: number[] | undefined, v: number) => Math.max(v ?? 0, ...(a ?? []).map((x) => x ?? 0));
  return {
    chuvaMm: max(h.precipitation, d.current?.precipitation),
    rajadaKmh: max(h.wind_gusts_10m, d.current?.wind_gusts_10m),
    codigo: max(h.weather_code, d.current?.weather_code),
  };
}
