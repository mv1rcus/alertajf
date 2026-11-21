import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { Ponto } from "@/lib/pontos";

maplibregl.setWorkerUrl(workerUrl);
(window as unknown as { maplibregl: typeof maplibregl }).maplibregl = maplibregl;

const estilo: Record<Ponto["tipo"], { cor: string; icone: string }> = {
  alagamento: { cor: "var(--flood)", icone: "🌊" },
  interdicao: { cor: "var(--destructive)", icone: "🚧" },
  deslizamento: { cor: "var(--slide)", icone: "⛰️" },
  relato: { cor: "var(--report)", icone: "📣" },
};

type Frame = { time: number; path: string };

export default function RainMap({ pontos, showRadar, foco }: { pontos: Ponto[]; showRadar: boolean; foco: Ponto | null }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef<L.LayerGroup | null>(null);
  const radar = useRef<L.TileLayer | null>(null);
  const [frames, setFrames] = useState<{ host: string; list: Frame[] } | null>(null);
  const [idx, setIdx] = useState(0);
  const [play, setPlay] = useState(true);

  useEffect(() => {
    if (!el.current || map.current) return;
    let m: L.Map | null = L.map(el.current, { zoomControl: false }).setView([-21.7642, -43.3503], 13);
    import("@maplibre/maplibre-gl-leaflet").then(() => {
      if (!m) return;
      (L as unknown as { maplibreGL: (o: object) => L.Layer }).maplibreGL({ style: "https://tiles.openfreemap.org/styles/dark" }).addTo(m);
    });
    markers.current = L.layerGroup().addTo(m);
    map.current = m;
    return () => { m?.remove(); m = null; map.current = null; };
  }, []);

  useEffect(() => {
    const g = markers.current; if (!g) return;
    g.clearLayers();
    pontos.forEach((p) => {
      const s = estilo[p.tipo];
      const icon = L.divIcon({ className: "", html: `<div class="pin" style="background:${s.cor}">${s.icone}</div>`, iconSize: [38, 38], iconAnchor: [19, 19] });
      L.marker([p.lat, p.lng], { icon }).bindPopup(`<b>${p.nome}</b><br/>${p.descricao}`).addTo(g);
    });
  }, [pontos]);

  useEffect(() => {
    if (!showRadar) { setFrames(null); return; }
    let cancel = false;
    fetch("https://api.rainviewer.com/public/weather-maps.json").then((r) => r.json()).then((d) => {
      if (cancel) return;
      const list: Frame[] = [...(d.radar?.past ?? []), ...(d.radar?.nowcast ?? [])];
      setFrames({ host: d.host, list }); setIdx(list.length - 1);
    }).catch(() => {});
    return () => { cancel = true; };
  }, [showRadar]);

  useEffect(() => {
    if (!frames || !play) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % frames.list.length), 700);
    return () => clearInterval(t);
  }, [frames, play]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    const f = frames?.list[idx];
    if (!f || !frames) { radar.current?.remove(); radar.current = null; return; }
    const url = `${frames.host}${f.path}/256/{z}/{x}/{y}/4/1_1.png`;
    if (radar.current) radar.current.setUrl(url);
    else radar.current = L.tileLayer(url, { opacity: 0.4, attribution: "Radar: RainViewer", zIndex: 400, maxNativeZoom: 7 }).addTo(m);
  }, [frames, idx]);

  useEffect(() => { if (foco && map.current) map.current.flyTo([foco.lat, foco.lng], 15); }, [foco]);

  const atual = frames?.list[idx];
  return (
    <div className="relative h-full w-full">
      <div ref={el} className="h-full w-full" />
      {frames && atual && (
        <div className="absolute right-3 top-36 z-[1000] flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-xs shadow-lg backdrop-blur">
          <button onClick={() => setPlay(!play)} aria-label={play ? "Pausar radar" : "Animar radar"} className="font-bold text-primary">{play ? "❚❚" : "▶"}</button>
          <span>🌧 {new Date(atual.time * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span>
        </div>
      )}
    </div>
  );
}
