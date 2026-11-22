import { createServerFn } from "@tanstack/react-start";

type RiverPoint = { time: string; cm: number };
export type EnvironmentData = {
  checkedAt: string;
  river: { status: "ok" | "error"; station: string; code: string; source: string; readings: RiverPoint[] };
  alerts: { status: "ok" | "error"; source: string; updated: string; items: { id: string; event: string; level: string; time: string }[] };
  radar: { status: "ok" | "error"; source: string; frames: { time: string; url: string; bbox: number[] }[] };
};
let cache: { at: number; data: EnvironmentData } | undefined;
const ANA = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos";
const CEMADEN = "https://painelalertas.cemaden.gov.br/wsAlertas2";
const RADAR = "https://data.inpe.br/bdc/stac/v1/search";
const get = (url: string) => fetch(url, { signal: AbortSignal.timeout(12000), headers: { Accept: "application/json,application/xml,text/xml" } }).then(r => { if (!r.ok) throw Error("Fonte indisponível"); return r; });
const dayBr = (date: Date) => date.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
const tag = (xml: string, name: string) => xml.match(new RegExp(`<${name}>([^<]+)</${name}>`))?.[1]?.trim() || "";
export const getEnvironment = createServerFn({ method: "GET" }).handler(async (): Promise<EnvironmentData> => {
  if (cache && Date.now() - cache.at < 10 * 60000) return cache.data;
  const now = new Date();
  const start = new Date(now.getTime() - 7 * 24 * 3600000);
  const anaUrl = `${ANA}?${new URLSearchParams({ codEstacao: "58480501", dataInicio: dayBr(start), dataFim: dayBr(now) })}`;
  const radarUrl = `${RADAR}?${new URLSearchParams({ collections: "br-weather-radar-cappi-1", bbox: "-43.7,-22,-43,-21.4", datetime: `${new Date(now.getTime() - 3 * 3600000).toISOString()}/${now.toISOString()}`, limit: "100" })}`;
  const data: EnvironmentData = {
    checkedAt: now.toISOString(),
    river: { status: "error", station: "PCH Marmelos Montante 1", code: "58480501", source: anaUrl, readings: [] },
    alerts: { status: "error", source: "https://painelalertas.cemaden.gov.br/", updated: "", items: [] },
    radar: { status: "error", source: "https://data.inpe.br/dados/radares-meteorologicos/", frames: [] },
  };
  await Promise.allSettled([
    (async () => {
      const xml = await (await get(anaUrl)).text();
      const readings: RiverPoint[] = [];
      for (const match of xml.matchAll(/<DadosHidrometereologicos(?:\s[^>]*)?>([\s\S]*?)<\/DadosHidrometereologicos>/g)) {
        const row = match[1] || ""; const raw = tag(row, "Nivel");
        if (tag(row, "CodEstacao") !== "58480501" || !raw) continue;
        const time = tag(row, "DataHora").replace(" ", "T") + "-03:00"; const cm = Number(raw);
        if (Number.isFinite(Date.parse(time)) && Date.parse(time) <= Date.now() + 60000 && Number.isFinite(cm) && cm > -10000 && cm < 100000) readings.push({ time, cm });
      }
      readings.sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
      readings.splice(0, Math.max(0, readings.length - 96));
      if (!readings.length) throw Error("Sem leitura");
      data.river.status = "ok"; data.river.readings = readings;
    })(),
    (async () => {
      const json = await (await get(CEMADEN)).json();
      if (!Array.isArray(json.alertas)) throw Error("Formato não reconhecido");
      data.alerts.updated = String(json.atualizado || "");
      const stamp = data.alerts.updated.match(/^(\d{2})-(\d{2})-(\d{4}) (\d{2}:\d{2}:\d{2}) UTC$/);
      const sourceAt = stamp ? Date.parse(`${stamp[3]}-${stamp[2]}-${stamp[1]}T${stamp[4]}Z`) : NaN;
      if (!Number.isFinite(sourceAt) || Date.now() - sourceAt > 60 * 60000 || sourceAt > Date.now() + 60000) throw Error("Painel desatualizado");
      const semAcento = (s: string) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
      const soJF = (x: Record<string, unknown>) => (String(x["codibge"] ?? "").trim() === "3136702" || semAcento(String(x["municipio"] ?? "")) === "juiz de fora") && String(x["uf"]) === "MG" && x["status"] === 1;
      data.alerts.items = json.alertas.filter(soJF).map((x: Record<string, unknown>) => ({ id: String(x['cod_alerta']), event: String(x['evento']), level: String(x['nivel']), time: String(x['ult_atualizacao']) }));
      data.alerts.status = "ok";
    })(),
    (async () => {
      const json = await (await get(radarUrl)).json();
      if (!Array.isArray(json.features)) throw Error("Catálogo indisponível");
      const frames = json.features.filter((f: { id?: string }) => f.id?.startsWith("decea_picocouto_")).map((f: { properties?: { datetime?: string }; assets?: { thumbnail?: { href?: string } }; bbox?: number[] }) => ({ time: f.properties?.datetime || "", url: f.assets?.thumbnail?.href || "", bbox: f.bbox || [] })).filter((f: { time: string; url: string; bbox: number[] }) => /^https:\/\/data\.inpe\.br\/bdc\/data\/br-weather-radar-cappi\//.test(f.url) && f.bbox.length === 4 && f.bbox.every(Number.isFinite) && Number.isFinite(Date.parse(f.time)) && Date.parse(f.time) <= Date.now() + 60000 && Date.now() - Date.parse(f.time) < 90 * 60000).sort((a: { time: string }, b: { time: string }) => Date.parse(a.time) - Date.parse(b.time)).slice(-6);
      if (!frames.length) throw Error("Sem radar recente");
      data.radar.status = "ok"; data.radar.frames = frames;
    })(),
  ]);
  cache = { at: Date.now(), data };
  return data;
});
