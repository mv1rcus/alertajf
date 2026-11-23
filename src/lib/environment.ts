import { createServerFn } from "@tanstack/react-start";
import { escolherEstacaoChuva, normalizarChuva } from "./chuva";

type RiverPoint = { time: string; cm: number };
type RainPoint = { time: string; mm: number };
export type FonteLeitura = { station: string; code: string; onde: string; leituraEm: string };
export type EnvironmentData = {
  checkedAt: string;
  river: { status: "ok" | "error"; station: string; code: string; onde: string; source: string; readings: RiverPoint[]; fontes: FonteLeitura[] };
  rain: { status: "ok" | "error"; station: string; code: string; onde: string; source: string; readings: RainPoint[]; fontes: FonteLeitura[] };
  outrosRios: { rio: string; station: string; code: string; onde: string; leituraEm: string; cm: number | null; tendencia: "subindo" | "descendo" | "estavel" }[];
  alerts: { status: "ok" | "error"; source: string; updated: string; items: { id: string; event: string; level: string; time: string }[] };
  radar: { status: "ok" | "error"; source: string; frames: { time: string; url: string; bbox: number[] }[] };
};
let cache: { at: number; data: EnvironmentData } | undefined;
const ANA = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos";
const CEMADEN = "https://painelalertas.cemaden.gov.br/wsAlertas2";
const RADAR = "https://data.inpe.br/bdc/stac/v1/search";

/** Estações telemétricas da ANA dentro de Juiz de Fora com pluviômetro e nível.
 *  Chuva: referência fixa em Marmelos Montante 1, demais só se não houver leitura válida. */
const ESTACOES_ANA = [
  { code: "58480501", station: "PCH Marmelos Montante 1", onde: "a ~3 km do centro" },
  { code: "58487000", station: "PCH Marmelos Barramento", onde: "a ~4 km do centro" },
  { code: "58489000", station: "PCH Joasal Barramento", onde: "a ~7 km do centro, na saída sul" },
];

/** Outros rios dentro de JF com telemetria ANA ativa (além do Paraibuna). */
const RIOS_EXTRAS = [
  { code: "58512040", station: "UHE Picada Montante 1", rio: "Rio do Peixe", onde: "zona oeste de JF" },
  { code: "58520200", station: "CGH Monte Verde Jusante", rio: "Rio Monte Verde", onde: "zona sul, área rural de JF" },
];

const get = (url: string) => fetch(url, { signal: AbortSignal.timeout(12000), headers: { Accept: "application/json,application/xml,text/xml" } }).then(r => { if (!r.ok) throw Error("Fonte indisponível"); return r; });
const dayBr = (date: Date) => date.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
const tag = (xml: string, name: string) => xml.match(new RegExp(`<${name}>([^<]+)</${name}>`))?.[1]?.trim() || "";
const anaUrl = (code: string, start: Date, now: Date) => `${ANA}?${new URLSearchParams({ codEstacao: code, dataInicio: dayBr(start), dataFim: dayBr(now) })}`;

export const getEnvironment = createServerFn({ method: "GET" }).handler(async (): Promise<EnvironmentData> => {
  if (cache && Date.now() - cache.at < 10 * 60000) return cache.data;
  const now = new Date();
  const start = new Date(now.getTime() - 7 * 24 * 3600000);
  const radarUrl = `${RADAR}?${new URLSearchParams({ collections: "br-weather-radar-cappi-1", bbox: "-43.7,-22,-43,-21.4", datetime: `${new Date(now.getTime() - 3 * 3600000).toISOString()}/${now.toISOString()}`, limit: "100" })}`;
  const vazia = ESTACOES_ANA[0]!;
  const data: EnvironmentData = {
    checkedAt: now.toISOString(),
    river: { status: "error", station: vazia.station, code: vazia.code, onde: vazia.onde, source: anaUrl(vazia.code, start, now), readings: [], fontes: [] },
    rain: { status: "error", station: vazia.station, code: vazia.code, onde: vazia.onde, source: anaUrl(vazia.code, start, now), readings: [], fontes: [] },
    outrosRios: [],
    alerts: { status: "error", source: "https://painelalertas.cemaden.gov.br/", updated: "", items: [] },
    radar: { status: "error", source: "https://data.inpe.br/dados/radares-meteorologicos/", frames: [] },
  };
  const candidatosRio: { ordem: number; station: string; code: string; onde: string; url: string; niveis: RiverPoint[] }[] = [];
  const candidatosChuva: { ordem: number; station: string; code: string; onde: string; url: string; leituras: RainPoint[] }[] = [];
  await Promise.allSettled([
    // Uma consulta por estação da ANA; de cada uma saem nível (rio) e chuva (mm).
    ...ESTACOES_ANA.map(async (est, ordem) => {
      const url = anaUrl(est.code, start, now);
      const xml = await (await get(url)).text();
      const niveis: RiverPoint[] = [];
      const chuvas: RainPoint[] = [];
      for (const match of xml.matchAll(/<DadosHidrometereologicos(?:\s[^>]*)?>([\s\S]*?)<\/DadosHidrometereologicos>/g)) {
        const row = match[1] || "";
        if (tag(row, "CodEstacao") !== est.code) continue;
        const time = tag(row, "DataHora").replace(" ", "T") + "-03:00";
        const timeOk = Number.isFinite(Date.parse(time)) && Date.parse(time) <= Date.now() + 60000;
        const raw = tag(row, "Nivel"); const cm = Number(raw);
        if (timeOk && raw && Number.isFinite(cm) && cm > -10000 && cm < 100000) niveis.push({ time, cm });
        const rawRain = tag(row, "Chuva"); const mm = Number(rawRain);
        if (timeOk && rawRain && Number.isFinite(mm) && mm >= 0 && mm < 1000) chuvas.push({ time, mm });
      }
      niveis.sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
      niveis.splice(0, Math.max(0, niveis.length - 96));
      chuvas.sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
      // Deduplica antes do corte para que repetições não expulsem horas válidas.
      const unicas = normalizarChuva(chuvas, now.getTime());
      chuvas.splice(0, chuvas.length, ...unicas.slice(-48));
      // Nível do rio: cada estação tem régua com referência própria (escalas não comparáveis),
      // então não dá para trocar de estação pela leitura mais recente. Candidata entra na lista
      // e a escolha acontece depois, sempre preferindo a estação principal (ordem de ESTACOES_ANA).
      if (niveis.length) {
        const ultima = niveis[niveis.length - 1]!;
        data.river.fontes.push({ station: est.station, code: est.code, onde: est.onde, leituraEm: ultima.time });
        candidatosRio.push({ ordem, station: est.station, code: est.code, onde: est.onde, url, niveis });
      }
      if (chuvas.length) {
        const ultima = chuvas[chuvas.length - 1]!;
        data.rain.fontes.push({ station: est.station, code: est.code, onde: est.onde, leituraEm: ultima.time });
        candidatosChuva.push({ ordem, ...est, url, leituras: chuvas });
      }
    }),
    // Outros rios de JF: última leitura de nível de cada estação extra.
    ...RIOS_EXTRAS.map(async (est) => {
      try {
        const xml = await (await get(anaUrl(est.code, start, now))).text();
      const niveis: RiverPoint[] = [];
      for (const match of xml.matchAll(/<DadosHidrometereologicos(?:\s[^>]*)?>([\s\S]*?)<\/DadosHidrometereologicos>/g)) {
        const row = match[1] || "";
        if (tag(row, "CodEstacao") !== est.code) continue;
        const time = tag(row, "DataHora").replace(" ", "T") + "-03:00";
        const timeOk = Number.isFinite(Date.parse(time)) && Date.parse(time) <= Date.now() + 60000;
        const raw = tag(row, "Nivel"); const cm = Number(raw);
        if (timeOk && raw && Number.isFinite(cm) && cm > -10000 && cm < 100000) niveis.push({ time, cm });
      }
      niveis.sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
      const ultima = niveis.at(-1); const anterior = niveis.at(-2);
        if (!ultima) throw Error("Sem leitura");
        data.outrosRios.push({ rio: est.rio, station: est.station, code: est.code, onde: est.onde, leituraEm: ultima.time, cm: ultima.cm, tendencia: !anterior ? "estavel" : ultima.cm > anterior.cm ? "subindo" : ultima.cm < anterior.cm ? "descendo" : "estavel" });
      } catch {
        data.outrosRios.push({ rio: est.rio, station: est.station, code: est.code, onde: est.onde, leituraEm: "", cm: null, tendencia: "estavel" });
      }
    }),
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
  // Estação principal (mais próxima do centro, régua de referência do site) tem prioridade;
  // Nunca substituir a régua principal: barramentos podem ter outro datum de cota.
  // Sem resposta da referência, o rio permanece explicitamente sem leitura.
  const escolhido = candidatosRio.find(c => c.code === "58480501");
  if (escolhido) {
    data.river.status = "ok"; data.river.station = escolhido.station; data.river.code = escolhido.code; data.river.onde = escolhido.onde; data.river.source = escolhido.url; data.river.readings = escolhido.niveis;
  }
  const chuvaEscolhida = escolherEstacaoChuva(candidatosChuva, now.getTime());
  if (chuvaEscolhida) {
    data.rain.status = "ok"; data.rain.station = chuvaEscolhida.station; data.rain.code = chuvaEscolhida.code;
    data.rain.onde = chuvaEscolhida.onde; data.rain.source = chuvaEscolhida.url; data.rain.readings = chuvaEscolhida.leituras;
  }
  data.river.fontes.sort((a, b) => Date.parse(b.leituraEm) - Date.parse(a.leituraEm));
  data.rain.fontes.sort((a, b) => Date.parse(b.leituraEm) - Date.parse(a.leituraEm));
  cache = { at: Date.now(), data };
  return data;
});
