import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Ponto } from "@/lib/pontos";

const cores: Record<string, string> = { alagamento: "#2563eb", interdicao: "#dc2626", deslizamento: "#d97706", relato: "#7c3aed" };

export default function RainMap({ pontos, showRadar, foco }: { pontos: Ponto[]; showRadar: boolean; foco: Ponto | null }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef<L.LayerGroup | null>(null);
  const radar = useRef<L.TileLayer | null>(null);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current).setView([-21.7642, -43.3503], 13);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors", maxZoom: 19 }).addTo(m);
    markers.current = L.layerGroup().addTo(m);
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const g = markers.current; if (!g) return;
    g.clearLayers();
    pontos.forEach((p) => {
      L.circleMarker([p.lat, p.lng], { radius: 10, color: "#fff", weight: 2, fillColor: cores[p.tipo], fillOpacity: 0.9 })
        .bindPopup(`<b>${p.nome}</b><br/>${p.descricao}`).addTo(g);
    });
  }, [pontos]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    radar.current?.remove(); radar.current = null;
    if (!showRadar) return;
    let cancel = false;
    fetch("https://api.rainviewer.com/public/weather-maps.json").then((r) => r.json()).then((d) => {
      if (cancel) return;
      const frames = [...(d.radar?.past ?? []), ...(d.radar?.nowcast ?? [])];
      const f = frames[frames.length - 1]; if (!f) return;
      radar.current = L.tileLayer(`${d.host}${f.path}/256/{z}/{x}/{y}/2/1_1.png`, { opacity: 0.6, attribution: "Radar: RainViewer" }).addTo(m);
    }).catch(() => {});
    return () => { cancel = true; };
  }, [showRadar]);

  useEffect(() => { if (foco && map.current) map.current.flyTo([foco.lat, foco.lng], 15); }, [foco]);

  return <div ref={el} className="h-full w-full" />;
}
