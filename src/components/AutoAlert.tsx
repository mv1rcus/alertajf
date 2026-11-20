import { useEffect, useRef, useState } from "react";
import { avaliarRisco, buscarClima, type Nivel } from "@/lib/clima";

function sirene() {
  try {
    const ctx = new AudioContext();
    const o = ctx.createOscillator(); const g = ctx.createGain();
    o.type = "sawtooth"; o.connect(g); g.connect(ctx.destination); g.gain.value = 0.15;
    for (let i = 0; i < 6; i++) { o.frequency.setValueAtTime(i % 2 ? 600 : 900, ctx.currentTime + i * 0.4); }
    o.start(); o.stop(ctx.currentTime + 2.4);
  } catch { /* som bloqueado */ }
}

export default function AutoAlert() {
  const [nivel, setNivel] = useState<Nivel>("normal");
  const [motivos, setMotivos] = useState<string[]>([]);
  const [aberto, setAberto] = useState(false);
  const [hora, setHora] = useState("");
  const anterior = useRef<Nivel>("normal");

  useEffect(() => {
    let vivo = true;
    const checar = async () => {
      try {
        const r = avaliarRisco(await buscarClima());
        if (!vivo) return;
        setNivel(r.nivel); setMotivos(r.motivos);
        setHora(new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }));
        if (r.nivel === "critico" && anterior.current !== "critico") { setAberto(true); sirene(); }
        anterior.current = r.nivel;
      } catch { /* sem conexão */ }
    };
    checar();
    const t = setInterval(checar, 5 * 60 * 1000);
    return () => { vivo = false; clearInterval(t); };
  }, []);

  const cor = nivel === "critico" ? "bg-destructive text-destructive-foreground animate-pulse" : nivel === "atencao" ? "bg-warning text-warning-foreground" : "bg-muted text-muted-foreground";
  const texto = nivel === "critico" ? "🚨 RISCO CRÍTICO AGORA" : nivel === "atencao" ? "⚠ Atenção: tempo instável" : "✓ Sem risco detectado no momento";

  return (
    <>
      <div className={`px-4 py-1.5 text-center text-xs font-semibold ${cor}`}>
        {texto}{motivos.length > 0 && ` — ${motivos.join(" · ")}`}{hora && ` · verificado às ${hora}`}
      </div>
      {aberto && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-foreground/60 p-4" role="alertdialog">
          <div className="w-full max-w-md rounded-lg bg-destructive p-6 text-destructive-foreground shadow-xl">
            <h2 className="mb-2 text-2xl font-bold">🚨 ALERTA CRÍTICO</h2>
            <p className="mb-3">Condição perigosa detectada em Juiz de Fora:</p>
            <ul className="mb-4 list-disc pl-5 font-semibold">{motivos.map((m) => <li key={m}>{m}</li>)}</ul>
            <p className="mb-4 text-sm">Evite áreas de risco, encostas e ruas alagadas. Procure um lugar seguro.</p>
            <div className="flex flex-wrap gap-2">
              <a href="tel:199" className="rounded bg-destructive-foreground px-4 py-2 font-bold text-destructive">📞 Ligar 199</a>
              <button onClick={() => setAberto(false)} className="rounded border border-destructive-foreground px-4 py-2">Entendi</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
