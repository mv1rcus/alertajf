import { useEffect, useState } from "react";
import { avaliarRio, buscarRio, type Rio } from "@/lib/rio";

export default function RiverLevel() {
  const [rio, setRio] = useState<Rio | null>(null);
  const [aberto, setAberto] = useState(false);
  useEffect(() => {
    const go = () => buscarRio().then(setRio).catch(() => {});
    go(); const t = setInterval(go, 60 * 60 * 1000); return () => clearInterval(t);
  }, []);
  if (!rio) return null;
  const nivel = avaliarRio(rio.hoje, rio.normal);
  const cor = nivel === "critico" ? "bg-destructive text-destructive-foreground animate-pulse" : nivel === "atencao" ? "bg-warning text-warning-foreground" : "bg-flood text-primary-foreground";
  const nome = nivel === "critico" ? "Muito acima do normal" : nivel === "atencao" ? "Acima do normal" : "Normal";
  const pct = Math.round((rio.hoje / (rio.normal || 1)) * 100);
  const max = Math.max(...rio.dias.map((d) => d.vazao), rio.normal * 2.5);
  return (
    <div className="pointer-events-auto w-fit max-w-full">
      <button onClick={() => setAberto(!aberto)} className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold shadow-lg ${cor}`}>
        🌊 Rio Paraibuna: {nome} · {pct}% {aberto ? "▴" : "▾"}
      </button>
      {aberto && (
        <div className="mt-2 w-72 rounded-2xl border bg-card p-3 text-xs shadow-xl backdrop-blur">
          <div className="mb-1 flex justify-between"><span>Água passando hoje</span><b>{Math.round(rio.hoje)} m³/s</b></div>
          <div className="mb-3 flex justify-between text-muted-foreground"><span>Normal da época</span><span>{Math.round(rio.normal)} m³/s</span></div>
          <div className="relative flex h-24 items-end gap-1">
            <div className="absolute inset-x-0 border-t border-dashed border-destructive" style={{ bottom: `${(rio.normal * 2.5 / max) * 100}%` }} />
            <div className="absolute inset-x-0 border-t border-dashed border-warning" style={{ bottom: `${(rio.normal * 1.6 / max) * 100}%` }} />
            {rio.dias.map((d) => {
              const n = avaliarRio(d.vazao, rio.normal);
              const c = n === "critico" ? "bg-destructive" : n === "atencao" ? "bg-warning" : "bg-flood";
              return <div key={d.data} title={`${d.data}: ${Math.round(d.vazao)} m³/s`} className={`flex-1 rounded-t ${c} ${d.previsao ? "opacity-40" : ""}`} style={{ height: `${(d.vazao / max) * 100}%` }} />;
            })}
          </div>
          <div className="mt-1 flex justify-between text-[10px] text-muted-foreground"><span>7 dias atrás</span><span>hoje</span><span>previsão</span></div>
          <p className="mt-2 text-[10px] text-muted-foreground">Linha amarela: atenção · vermelha: risco de transbordar. Estimativa por satélite (GloFAS), atualizada 1x ao dia.</p>
        </div>
      )}
    </div>
  );
}
