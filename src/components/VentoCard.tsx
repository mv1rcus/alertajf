import { useEffect, useState } from "react";
import { Share2 } from "lucide-react";

type Hora = { h: string; raj: number };
type Vento = { vel: number; raj: number; dir: number; agora: string; horas: Hora[] };

const URL_VENTO = "https://api.open-meteo.com/v1/forecast?latitude=-21.7642&longitude=-43.3503&current=wind_speed_10m,wind_gusts_10m,wind_direction_10m&hourly=wind_gusts_10m&wind_speed_unit=kmh&forecast_days=2&timezone=America%2FSao_Paulo";
const SITE = "https://alertajf.vercel.app";
const PONTOS = ["N", "NE", "L", "SE", "S", "SO", "O", "NO"];

async function buscarVento(): Promise<Vento> {
  const r = await fetch(URL_VENTO, { signal: AbortSignal.timeout(15000) });
  if (!r.ok) throw new Error(`Open-Meteo ${r.status}`);
  const d = await r.json();
  const c = d?.current;
  if (!c || !Number.isFinite(c.wind_speed_10m) || !Number.isFinite(c.wind_gusts_10m)) throw new Error("Resposta inválida");
  const tempos: string[] = d?.hourly?.time ?? [];
  const rajs: number[] = d?.hourly?.wind_gusts_10m ?? [];
  const inicio = String(c.time).slice(0, 13) + ":00";
  const horas: Hora[] = [];
  for (let i = 0; i < tempos.length && horas.length < 12; i++) {
    if (tempos[i] > inicio && Number.isFinite(rajs[i])) horas.push({ h: tempos[i].slice(11, 13), raj: rajs[i] });
  }
  return { vel: c.wind_speed_10m, raj: c.wind_gusts_10m, dir: c.wind_direction_10m, agora: String(c.time), horas };
}

function nivel(raj: number) {
  if (raj >= 90) return "Rajadas muito fortes";
  if (raj >= 60) return "Rajadas fortes";
  if (raj >= 40) return "Rajadas moderadas";
  return "Sem rajadas fortes";
}

function corNivel(raj: number) {
  if (raj >= 60) return "#e5484d";
  if (raj >= 40) return "#f5a524";
  return "#2fa4a9";
}

export function VentoCard() {
  const [v, setV] = useState<Vento | null>(null);
  const [erro, setErro] = useState(false);
  useEffect(() => {
    let vivo = true;
    async function carregar() {
      try { const x = await buscarVento(); if (vivo) { setV(x); setErro(false); } } catch { if (vivo) setErro(true); }
    }
    void carregar();
    const t = setInterval(carregar, 10 * 60000);
    return () => { vivo = false; clearInterval(t); };
  }, []);
  const ok = v && !erro;
  const maxRaj = ok ? Math.max(60, ...v.horas.map((x) => x.raj)) : 60;
  const picoProx = ok && v.horas.length ? v.horas.reduce((a, b) => (b.raj > a.raj ? b : a)) : null;
  const texto = ok
    ? `Vento em Juiz de Fora agora: ${Math.round(v.vel)} km/h, rajadas de ${Math.round(v.raj)} km/h (${nivel(v.raj).toLowerCase()}), segundo o modelo Open-Meteo. Acompanhe no Alerta JF (projeto independente): ${SITE}`
    : `Chuva, raios, vento e Rio Paraibuna em Juiz de Fora, no Alerta JF (projeto independente): ${SITE}`;
  const wa = `https://wa.me/?text=${encodeURIComponent(texto)}`;
  const tocar = (e: { preventDefault: () => void }) => { if (typeof navigator.share === "function") { e.preventDefault(); navigator.share({ text: texto }).catch(() => {}); } };
  return (
    <article className="card env-card">
      <div className="eyebrow">VENTO · OPEN-METEO (MODELO)</div>
      <h3>Vento e rajadas em Juiz de Fora</h3>
      <strong className="big-number alert-text">{ok ? `${Math.round(v.vel)} km/h` : "Sem consulta"}</strong>
      {ok ? (
        <>
          <p className="mm-line">
            Rajadas de <b>{Math.round(v.raj)} km/h</b> agora · vindo de <b>{PONTOS[Math.round(v.dir / 45) % 8]}</b> · <b style={{ color: corNivel(v.raj) }}>{nivel(v.raj)}</b>
          </p>
          <p className="mm-line">
            {picoProx && picoProx.raj >= 40
              ? <>Pico previsto: <b>{Math.round(picoProx.raj)} km/h</b> por volta das <b>{picoProx.h}h</b></>
              : "Sem rajadas de 40 km/h ou mais previstas nas próximas 12h"}
          </p>
        </>
      ) : (
        <p>Consulta indisponível. Isso não significa ausência de vento forte na cidade.</p>
      )}
      {ok && v.horas.length > 0 && (
        <>
          <div aria-label="Rajadas previstas nas próximas 12 horas, em km/h" style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 40, margin: "10px 0 0" }}>
            {v.horas.map((x) => (
              <div key={x.h} title={`${x.h}h: ${Math.round(x.raj)} km/h`} style={{ flex: 1, height: `${Math.max(8, (x.raj / maxRaj) * 100)}%`, borderRadius: 2, background: corNivel(x.raj), opacity: x === picoProx ? 1 : 0.45 }} />
            ))}
          </div>
          <div style={{ display: "flex", gap: 3, marginTop: 2 }} aria-hidden="true">
            {v.horas.map((x, i) => (
              <div key={x.h} style={{ flex: 1, textAlign: "center", fontSize: 9, color: "#7d97a3" }}>
                {i % 3 === 0 || i === v.horas.length - 1 ? `${x.h}h` : ""}
              </div>
            ))}
          </div>
        </>
      )}
      <small className="mm-src">
        {ok
          ? `Rajada máx. por hora, ${v.horas[0].h}h a ${v.horas[v.horas.length - 1].h}h · modelo Open-Meteo ${v.agora.slice(11, 16)} · atualiza a cada 15 min · não é sensor de rua`
          : "Consultando o Open-Meteo…"}
      </small>
      <details>
        <summary>Sobre esta medição</summary>
        <p>Valores de modelo numérico para o centro de Juiz de Fora, a 10 m de altura. Rajadas locais em tempestade podem ser maiores, e o relevo muda o vento de bairro para bairro. Faixas: abaixo de 40 km/h sem alerta, 40 a 59 moderadas, 60 a 89 fortes, 90 ou mais muito fortes. Em caso de risco, ligue 199 (Defesa Civil).</p>
        <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Fonte: Open-Meteo (CC BY 4.0) ↗</a>
      </details>
      <a className="wa-share" href={wa} onClick={tocar} target="_blank" rel="noopener noreferrer"><Share2 size={14} />Compartilhar no WhatsApp</a>
    </article>
  );
}
