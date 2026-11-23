import { useEffect, useState } from "react";
import type { RainViewerData } from "@/lib/rainviewer";
import { cruzarPrevisaoRadar, lerRadarNoPonto, type NivelRadar } from "@/lib/radarJf";

const ROTULO: Record<NivelRadar, string> = { nenhum: "Sem eco de chuva", fraca: "Chuva fraca", moderada: "Chuva moderada", forte: "Chuva forte" };
const JF = { lat: -21.7642, lon: -43.3503 };

/** Selo "radar sobre JF agora". Se o radar não puder ser lido, cai para a estação ANA Marmelos. */
export function RadarSelo({ rv, local, nomeLocal, modelo, estacao }: {
  rv: RainViewerData | null;
  local: { lat: number; lon: number } | null;
  nomeLocal: string | null;
  modelo: { mm: number; probabilidade: number } | null;
  estacao: { ultimaHora: number; leituraEm: string; fresca: boolean } | null;
}) {
  const ponto = local ?? JF;
  const past = rv?.frames.filter(f => !f.forecast).at(-1);
  const [nivel, setNivel] = useState<NivelRadar | null>(null);
  const [falhou, setFalhou] = useState(false);
  const host = rv?.host, path = past?.path;
  useEffect(() => {
    if (!host || !path) { setNivel(null); return; }
    let vivo = true;
    setFalhou(false);
    lerRadarNoPonto(host, path, ponto.lat, ponto.lon).then(n => { if (vivo) setNivel(n); }, () => { if (vivo) { setNivel(null); setFalhou(true); } });
    return () => { vivo = false; };
  }, [host, path, ponto.lat, ponto.lon]);
  const idadeMin = past ? Math.max(0, Math.round((Date.now() - past.time * 1000) / 60000)) : null;
  const velho = idadeMin === null || idadeMin > 30;
  const onde = nomeLocal ? `sobre ${nomeLocal}` : "sobre o centro de JF";
  const lido = nivel && !velho ? nivel : null;
  const cruz = cruzarPrevisaoRadar(lido, modelo);
  const hora = past ? new Date(past.time * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" }) : "";
  let corpo: string;
  if (lido) corpo = `${ROTULO[lido]} ${onde} · quadro das ${hora} (há ${idadeMin} min)`;
  else if (estacao && estacao.fresca) corpo = `Radar indisponível para leitura. Estação ANA Marmelos: ${estacao.ultimaHora.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mm na última hora`;
  else corpo = falhou || velho ? "Radar sem leitura recente. Sem dado não significa ausência de chuva." : "Lendo o radar…";
  return <div className="radar-selo" role="status" style={{ margin: "8px 0", padding: "8px 10px", borderRadius: 10, border: "1px solid rgba(34,170,168,.4)", fontSize: 14 }}>
    <b>Radar {onde} agora</b><br />{corpo}
    {cruz ? <small style={{ display: "block", marginTop: 4 }}>{cruz.texto}</small> : null}
    <small style={{ display: "block", marginTop: 4, opacity: .8 }}>O radar mede a chuva do alto, com resolução de alguns km. Não é medição na sua rua.</small>
  </div>;
}
