import { useEffect, useState } from "react";

export type AlertaDC = {
  id: string;
  evento: string;
  texto: string;
  emitido: string;
  expira: string;
  severidade: string;
  origem: string;
};

/** Arquivo atualizado a cada ~10 min pelo workflow "Alertas da Defesa Civil (JF)" (feed IDAP/MIDR). */
/** Dados ficam na branch "dados" (fora de main) para não gastar deploys da Vercel; cai pro arquivo local se o GitHub falhar. */
export const URL_DEFESA_CIVIL = "https://raw.githubusercontent.com/mvthebest/alertajf/dados/defesa-civil.json";
export const URL_DEFESA_CIVIL_RESERVA = "/defesa-civil.json";

export type RespostaDC = { alerta: AlertaDC | null; fonteAtualizada: string | null };

export async function buscarAlertaDC(): Promise<RespostaDC> {
  const pedir = (u: string) => fetch(`${u}?t=${Math.floor(Date.now() / 60000)}`, { signal: AbortSignal.timeout(15000), cache: "no-store" });
  let r = await pedir(URL_DEFESA_CIVIL).catch(() => null);
  let daReserva = false;
  if (!r || !r.ok) { r = await pedir(URL_DEFESA_CIVIL_RESERVA); daReserva = true; }
  if (!r.ok) throw new Error(`Defesa Civil ${r.status}`);
  const d = (await r.json()) as { alertas?: AlertaDC[]; fonte_atualizada_em?: string };
  if (!Array.isArray(d.alertas)) throw new Error("Resposta inválida");
  // alerta vencido nunca aparece como atual: pega o primeiro que ainda não expirou
  const vigente = (x: AlertaDC) => !x.expira || Number.isNaN(Date.parse(x.expira)) || Date.parse(x.expira) > Date.now();
  // o arquivo reserva do deploy envelhece (o workflow grava na branch "dados"): só vale se a fonte foi atualizada há menos de 6 h
  if (daReserva) {
    const f = typeof d.fonte_atualizada_em === "string" ? Date.parse(d.fonte_atualizada_em) : NaN;
    if (Number.isNaN(f) || Date.now() - f > 6 * 3600 * 1000) throw new Error("Defesa Civil: arquivo reserva desatualizado");
  }
  const a = d.alertas.find(vigente);
  const alerta = a && a.texto && !Number.isNaN(Date.parse(a.emitido)) ? a : null;
  const fonteAtualizada = typeof d.fonte_atualizada_em === "string" && !Number.isNaN(Date.parse(d.fonte_atualizada_em)) ? d.fonte_atualizada_em : null;
  return { alerta, fonteAtualizada };
}

/** Texto curto para a faixa: "19:49" (hoje) ou "20/11 19:49". */
export function horaAlertaDC(iso: string, agora = new Date()): string {
  const d = new Date(iso);
  const hm = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" });
  const dia = (x: Date) => x.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
  return dia(d) === dia(agora) ? hm : `${dia(d).slice(0, 5)} ${hm}`;
}

export function useAlertaDC() {
  const [alerta, setAlerta] = useState<AlertaDC | null>(null);
  const [fonteAtualizada, setFonteAtualizada] = useState<string | null>(null);
  const [status, setStatus] = useState<"carregando" | "ok" | "erro">("carregando");
  useEffect(() => {
    let vivo = true;
    const go = () =>
      buscarAlertaDC()
        .then((r) => { if (vivo) { setAlerta(r.alerta); setFonteAtualizada(r.fonteAtualizada); setStatus("ok"); } })
        .catch(() => { if (vivo) setStatus("erro"); });
    go();
    const t = setInterval(go, 5 * 60 * 1000);
    return () => { vivo = false; clearInterval(t); };
  }, []);
  return { alerta, status, fonteAtualizada };
}
