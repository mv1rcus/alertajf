import { useEffect, useState } from "react";

/** Código IBGE de Juiz de Fora (MG). */
export const GEOCODE_JF = "3136702";
export const URL_AVISOS = "https://apiprevmet3.inmet.gov.br/avisos/ativos";

export type Aviso = {
  id: string;
  descricao: string;
  severidade: string;
  cor: string;
  inicio: string;
  fim: string;
  fimTs: number | null;
  riscos: string;
  instrucoes: string[];
};

type Bruto = Record<string, unknown>;

/** A API manda listas como texto, ex.: "['a', 'b']". Isso separa os itens. */
function itens(v: unknown): string[] {
  if (Array.isArray(v)) return v.map(String);
  const s = String(v ?? "").trim();
  if (!s) return [];
  const out: string[] = [];
  for (const m of s.matchAll(/'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"/g)) out.push((m[1] ?? m[2] ?? "").trim());
  return out.length ? out : [s];
}

function dataBr(s: unknown): string {
  const m = String(s ?? "").match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  return m ? `${m[3]}/${m[2]} ${m[4]}:${m[5]}` : String(s ?? "");
}

/** Timestamp do fim do aviso (horário de Brasília). null se a data vier fora do formato. */
function fimTs(s: unknown): number | null {
  const m = String(s ?? "").match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  if (!m) return null;
  const t = Date.parse(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:00-03:00`);
  return Number.isFinite(t) ? t : null;
}

/** Avisos oficiais do INMET (hoje e próximos dias) que valem para Juiz de Fora. */
export async function buscarAvisos(): Promise<Aviso[]> {
  const r = await fetch(URL_AVISOS, { signal: AbortSignal.timeout(15000) });
  if (!r.ok) throw new Error(`INMET ${r.status}`);
  const d = (await r.json()) as { hoje?: Bruto[]; futuro?: Bruto[] };
  if (!Array.isArray(d.hoje) || !Array.isArray(d.futuro)) throw new Error("Resposta INMET inválida");
  const vistos = new Set<string>();
  const lista: Aviso[] = [];
  for (const a of [...(d.hoje ?? []), ...(d.futuro ?? [])]) {
    const geocodes = String(a["geocodes"] ?? "").split(",").map((x) => x.trim());
    if (!geocodes.includes(GEOCODE_JF)) continue;
    if (String(a["encerrado"]).toLowerCase() === "true") continue;
    const id = String(a["id_aviso"] ?? a["id"]);
    if (vistos.has(id)) continue;
    vistos.add(id);
    lista.push({
      id,
      descricao: String(a["descricao"] ?? "Aviso"),
      severidade: String(a["severidade"] ?? ""),
      cor: String(a["aviso_cor"] ?? "#FFFE00"),
      inicio: dataBr(a["inicio"]),
      fim: dataBr(a["fim"]),
      fimTs: fimTs(a["fim"]),
      riscos: itens(a["riscos"]).join(" "),
      instrucoes: itens(a["instrucoes"]),
    });
  }
  return lista;
}

export type StatusAvisos = "carregando" | "ok" | "erro";

/** Busca ao abrir e depois a cada 10 minutos. */
export function useAvisos() {
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const [status, setStatus] = useState<StatusAvisos>("carregando");
  const [atualizado, setAtualizado] = useState("");
  useEffect(() => {
    let vivo = true;
    const go = () =>
      buscarAvisos()
        .then((l) => { if (!vivo) return; setAvisos(l); setStatus("ok"); setAtualizado(new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })); })
        .catch(() => { if (vivo) { setStatus("erro"); setAvisos([]); } });
    go();
    const t = setInterval(go, 10 * 60 * 1000);
    return () => { vivo = false; clearInterval(t); };
  }, []);
  return { avisos, status, atualizado };
}
