import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense, useEffect, useState } from "react";
import { pontosCriticos, alertas, type Ponto } from "@/lib/pontos";

import AutoAlert from "@/components/AutoAlert";
import RiverLevel from "@/components/RiverLevel";

const RainMap = lazy(() => import("@/components/RainMap"));

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Alerta JF – Chuvas e emergências em Juiz de Fora" },
      { name: "description", content: "Mapa em tempo real de alagamentos, vias interditadas e áreas de risco em Juiz de Fora (MG), com alertas da Defesa Civil." },
      { property: "og:title", content: "Alerta JF – Chuvas e emergências em Juiz de Fora" },
      { property: "og:description", content: "Mapa de chuvas, alagamentos e alertas da Defesa Civil em Juiz de Fora." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
import { lazy, Suspense, useEffect, useState } from "react";
import { pontosCriticos, type Ponto } from "@/lib/pontos";
import { useAvisos } from "@/lib/inmet";

import AutoAlert from "@/components/AutoAlert";
import RiverLevel from "@/components/RiverLevel";

const RainMap = lazy(() => import("@/components/RainMap"));

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Alerta JF – Chuvas e emergências em Juiz de Fora" },
      { name: "description", content: "Mapa em tempo real de alagamentos, vias interditadas e áreas de risco em Juiz de Fora (MG), com avisos oficiais do INMET." },
      { property: "og:title", content: "Alerta JF – Chuvas e emergências em Juiz de Fora" },
      { property: "og:description", content: "Mapa de chuvas, alagamentos e avisos oficiais do INMET em Juiz de Fora." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const rotulo: Record<Ponto["tipo"], string> = { alagamento: "Alagamento", interdicao: "Via interditada", deslizamento: "Risco de deslizamento", relato: "Relato de cidadão" };

function Index() {
  const [mounted, setMounted] = useState(false);
  const [pontos, setPontos] = useState<Ponto[]>(pontosCriticos);
  const [radar, setRadar] = useState(true);
  const [foco, setFoco] = useState<Ponto | null>(null);
  const [form, setForm] = useState(false);
  const [i, setI] = useState(0);
  const { avisos, status, atualizado } = useAvisos();
  useEffect(() => { setMounted(true); }, []);
  useEffect(() => { if (avisos.length < 2) return; const t = setInterval(() => setI((x) => (x + 1) % avisos.length), 6000); return () => clearInterval(t); }, [avisos.length]);
  const aviso = avisos[i % Math.max(avisos.length, 1)];

  function reportar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const local = String(fd.get("local"));
    const add = (lat: number, lng: number) => {
      const p: Ponto = { id: crypto.randomUUID(), nome: local, tipo: "relato", descricao: String(fd.get("desc") || "Alagamento relatado"), lat, lng };
      setPontos((ps) => [...ps, p]); setFoco(p); setForm(false);
    };
    navigator.geolocation?.getCurrentPosition((pos) => add(pos.coords.latitude, pos.coords.longitude), () => add(-21.7642 + (Math.random() - 0.5) * 0.02, -43.3503 + (Math.random() - 0.5) * 0.02), { timeout: 5000 });
  }

  const [painel, setPainel] = useState(false);
  const cores: Record<Ponto["tipo"], string> = { alagamento: "bg-flood", interdicao: "bg-destructive", deslizamento: "bg-slide", relato: "bg-report" };

  return (
    <div className="relative h-dvh w-full overflow-hidden bg-background text-foreground">
      <div className="absolute inset-0">
        {mounted && <Suspense fallback={null}><RainMap pontos={pontos} showRadar={radar} foco={foco} /></Suspense>}
      </div>

      {/* Topo flutuante */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[1000] space-y-2 p-3">
        <div className="pointer-events-auto flex items-center gap-3 rounded-2xl border bg-card px-3 py-2 shadow-xl md:max-w-xl">
          <div className="font-display text-lg leading-none">Alerta<span className="text-primary">JF</span></div>
          <div className="h-6 w-px bg-border" />
          <p className="min-w-0 flex-1 truncate text-xs"><span className="mr-1 rounded bg-alert px-1.5 py-0.5 font-bold text-alert-foreground">INMET</span>{aviso ? `${aviso.descricao} (${aviso.severidade}) até ${aviso.fim}` : status === "carregando" ? "Buscando avisos oficiais…" : status === "erro" ? "Não foi possível consultar o INMET agora" : "Nenhum aviso do INMET ativo para Juiz de Fora"}</p>
        </div>
        {mounted && <AutoAlert />}
        {mounted && <RiverLevel />}
      </div>

      {/* Botões de emergência */}
      <div className="absolute right-3 top-48 z-[1000] flex flex-col gap-2 md:top-40">
        <a href="tel:199" aria-label="Ligar Defesa Civil 199" className="grid h-14 w-14 place-items-center rounded-full bg-warning text-warning-foreground shadow-xl"><span className="text-center text-[10px] font-bold leading-tight">📞<br/>199</span></a>
        <a href="tel:193" aria-label="Ligar Bombeiros 193" className="grid h-14 w-14 place-items-center rounded-full bg-destructive text-destructive-foreground shadow-xl"><span className="text-center text-[10px] font-bold leading-tight">🚒<br/>193</span></a>
        <button onClick={() => setRadar(!radar)} aria-label="Ligar ou desligar chuva no mapa" className={`grid h-14 w-14 place-items-center rounded-full border shadow-xl ${radar ? "bg-primary text-primary-foreground" : "bg-card"}`}><span className="text-center text-[10px] font-bold leading-tight">🌧<br/>Radar</span></button>
      </div>

      {/* Painel deslizante */}
      <section className={`absolute inset-x-0 bottom-0 z-[1001] flex max-h-[75dvh] flex-col rounded-t-3xl border-t bg-card shadow-2xl transition-transform duration-300 md:inset-x-auto md:bottom-3 md:left-3 md:w-96 md:rounded-3xl md:border ${painel ? "translate-y-0" : "translate-y-[calc(100%-9.5rem)] md:translate-y-[calc(100%-9.5rem)]"}`}>
        <button onClick={() => setPainel(!painel)} className="flex flex-col items-center pt-2" aria-label="Abrir ou fechar painel">
          <span className="h-1.5 w-12 rounded-full bg-muted-foreground/40" />
        </button>
        <div className="flex items-center gap-2 px-4 pb-3 pt-2">
          <button onClick={() => setPainel(!painel)} className="flex-1 text-left">
            <div className="font-display text-base">{pontos.length} pontos críticos</div>
            <div className="text-xs text-muted-foreground">{painel ? "Toque para fechar" : "Toque para ver a lista e os avisos"}</div>
          </button>
          <button onClick={() => { setForm(true); setPainel(true); }} className="rounded-full bg-primary px-4 py-2.5 text-sm font-bold text-primary-foreground shadow-lg">+ Reportar</button>
        </div>
        <div className="flex gap-3 overflow-x-auto px-4 pb-3 text-[11px] text-muted-foreground">
          {(Object.keys(rotulo) as Ponto["tipo"][]).map((t) => <span key={t} className="flex shrink-0 items-center gap-1.5"><span className={`h-2.5 w-2.5 rounded-full ${cores[t]}`} />{rotulo[t]}</span>)}
        </div>
        <div className="flex-1 space-y-5 overflow-y-auto border-t px-4 py-4">
          {form && (
            <form onSubmit={reportar} className="space-y-2 rounded-2xl border bg-secondary p-3">
              <div className="text-sm font-semibold">Reportar alagamento</div>
              <input name="local" required placeholder="Rua / bairro" className="w-full rounded-lg border bg-background px-3 py-2 text-sm" />
              <textarea name="desc" placeholder="O que está acontecendo?" className="w-full rounded-lg border bg-background px-3 py-2 text-sm" />
              <div className="flex gap-2">
                <button className="flex-1 rounded-lg bg-primary py-2 text-sm font-bold text-primary-foreground">Enviar com minha localização</button>
                <button type="button" onClick={() => setForm(false)} className="rounded-lg border px-3 text-sm">Cancelar</button>
              </div>
            </form>
          )}
          <ul className="space-y-2">
            {pontos.map((p) => (
              <li key={p.id}>
                <button onClick={() => { setFoco(p); setPainel(false); }} className="flex w-full items-start gap-3 rounded-xl bg-secondary p-3 text-left hover:bg-accent">
                  <span className={`mt-1 h-3 w-3 shrink-0 rounded-full ${cores[p.tipo]}`} />
                  <span><span className="block font-semibold">{p.nome}</span><span className="block text-xs text-muted-foreground">{rotulo[p.tipo]} · {p.descricao}</span></span>
                </button>
              </li>
            ))}
          </ul>
          <div>
            <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">Avisos oficiais (INMET)</h2>
            {avisos.length === 0 && <p className="mb-2 rounded-xl border-l-4 border-muted-foreground bg-secondary p-3 text-xs">{status === "carregando" ? "Buscando avisos oficiais…" : status === "erro" ? "Não foi possível consultar o INMET agora. Veja os avisos em portal.inmet.gov.br/avisos ou ligue 199." : "Nenhum aviso do INMET ativo para Juiz de Fora neste momento."}</p>}
            {avisos.map((a) => (
              <div key={a.id} className="mb-2 rounded-xl border-l-4 bg-secondary p-3 text-xs" style={{ borderLeftColor: a.cor }}>
                <p><b>{a.descricao}</b> · {a.severidade}</p>
                <p className="text-muted-foreground">De {a.inicio} até {a.fim}</p>
                {a.riscos && <p className="mt-1">{a.riscos}</p>}
                {a.instrucoes.length > 0 && <ul className="mt-1 list-disc pl-4 text-muted-foreground">{a.instrucoes.map((t) => <li key={t}>{t}</li>)}</ul>}
              </div>
            ))}
            {atualizado && <p className="text-[10px] text-muted-foreground">Fonte: INMET (avisos meteorológicos). Atualizado às {atualizado}.</p>}
          </div>
          <p className="rounded-xl border bg-secondary p-3 text-[11px] leading-snug text-muted-foreground">
            Projeto independente, não oficial e sem ligação com a Prefeitura, a Defesa Civil ou o INMET. Os pontos críticos do mapa são exemplos. Em emergência, ligue 199 (Defesa Civil) ou 193 (Bombeiros).
          </p>
        </div>
      </section>
    </div>
  );
}
