import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense, useEffect, useState } from "react";
import { pontosCriticos, alertas, type Ponto } from "@/lib/pontos";

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
  useEffect(() => { setMounted(true); const t = setInterval(() => setI((x) => (x + 1) % alertas.length), 6000); return () => clearInterval(t); }, []);

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

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <div className="bg-alert px-4 py-2 text-alert-foreground">
        <div className="mx-auto flex max-w-7xl items-center gap-3 text-sm">
          <span className="shrink-0 rounded bg-alert-foreground px-2 py-0.5 text-xs font-bold text-alert">⚠ DEFESA CIVIL · 40199</span>
          <p className="truncate"><b>{alertas[i]?.quando}:</b> {alertas[i]?.texto}</p>
        </div>
      </div>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <h1 className="font-display text-2xl font-bold">Alerta <span className="text-primary">JF</span> <span className="text-sm font-normal text-muted-foreground">Chuvas em tempo real · Juiz de Fora (MG)</span></h1>
        <div className="flex gap-2">
          <a href="tel:199" className="rounded-md bg-warning px-4 py-2 font-bold text-warning-foreground">📞 Defesa Civil 199</a>
          <a href="tel:193" className="rounded-md bg-destructive px-4 py-2 font-bold text-destructive-foreground">🚒 Bombeiros 193</a>
        </div>
      </header>
      <main className="flex flex-1 flex-col overflow-hidden md:flex-row">
        <aside className="w-full space-y-4 overflow-y-auto border-r p-4 md:w-80">
          <button onClick={() => setForm(!form)} className="w-full rounded-md bg-primary py-3 font-semibold text-primary-foreground">+ Reportar alagamento</button>
          {form && (
            <form onSubmit={reportar} className="space-y-2 rounded-md border p-3">
              <input name="local" required placeholder="Rua / bairro" className="w-full rounded border bg-background px-2 py-1.5 text-sm" />
              <textarea name="desc" placeholder="O que está acontecendo?" className="w-full rounded border bg-background px-2 py-1.5 text-sm" />
              <button className="w-full rounded bg-primary py-1.5 text-sm text-primary-foreground">Enviar (usa sua localização)</button>
            </form>
          )}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={radar} onChange={(e) => setRadar(e.target.checked)} /> Mostrar radar de chuva</label>
          <div>
            <h2 className="mb-2 font-semibold">Pontos críticos</h2>
            <ul className="space-y-2">
              {pontos.map((p) => (
                <li key={p.id}>
                  <button onClick={() => setFoco(p)} className="w-full rounded-md border p-2 text-left hover:bg-accent">
                    <div className="font-medium">{p.nome}</div>
                    <div className="text-xs text-muted-foreground">{rotulo[p.tipo]} · {p.descricao}</div>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="mb-2 font-semibold">Últimos alertas</h2>
            {alertas.map((a) => <p key={a.quando} className="mb-2 rounded border-l-4 border-alert bg-muted p-2 text-xs"><b>{a.quando}</b> — {a.texto}</p>)}
          </div>
        </aside>
        <section className="relative min-h-[400px] flex-1">
          {mounted && <Suspense fallback={null}><RainMap pontos={pontos} showRadar={radar} foco={foco} /></Suspense>}
          <div className="absolute bottom-4 left-4 z-[1000] space-y-1 rounded-md bg-card p-2 text-xs shadow">
            {[["#2563eb", "Alagamento"], ["#dc2626", "Via interditada"], ["#d97706", "Deslizamento"], ["#7c3aed", "Relato"]].map(([c, l]) => (
              <div key={l} className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ background: c }} />{l}</div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
