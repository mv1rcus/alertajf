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
export const URL_DEFESA_CIVIL = "/defesa-civil.json";

export async function buscarAlertaDC(): Promise<AlertaDC | null> {
  const r = await fetch(`${URL_DEFESA_CIVIL}?t=${Math.floor(Date.now() / 60000)}`, { signal: AbortSignal.timeout(15000), cache: "no-store" });
  if (!r.ok) throw new Error(`Defesa Civil ${r.status}`);
  const d = (await r.json()) as { alertas?: AlertaDC[] };
  if (!Array.isArray(d.alertas)) throw new Error("Resposta inválida");
  const a = d.alertas[0];
  return a && a.texto && !Number.isNaN(Date.parse(a.emitido)) ? a : null;
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
  const [status, setStatus] = useState<"carregando" | "ok" | "erro">("carregando");
  useEffect(() => {
    let vivo = true;
    const go = () =>
      buscarAlertaDC()
        .then((a) => { if (vivo) { setAlerta(a); setStatus("ok"); } })
        .catch(() => { if (vivo) setStatus("erro"); });
    go();
    const t = setInterval(go, 5 * 60 * 1000);
    return () => { vivo = false; clearInterval(t); };
  }, []);
  return { alerta, status };
}
