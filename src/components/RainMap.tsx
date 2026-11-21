import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Ponto } from "@/lib/pontos";

type Frame = { time: number; path: string };
type Radar = { host: string; frames: Frame[] };
const icons = { alagamento: "🌊", interdicao: "🚧", deslizamento: "⛰", relato: "📍" };
const colors = { alagamento: "#137eac", interdicao: "#bc5234", deslizamento: "#a0742a", relato: "#127e86" };
export default function RainMap({ pontos, showRadar, foco, onPick, selected }: {
  pontos: Ponto[]; showRadar: boolean; foco: Ponto | null;
  onPick?: ((lat: number, lng: number) => void) | undefined;
  selected?: { lat: number; lng: number } | null;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef<L.LayerGroup | null>(null);
  const layers = useRef<L.TileLayer[]>([]);
  const [radar, setRadar] = useState<Radar | null>(null);
  const [radarError, setRadarError] = useState(false);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [now, setNow] = useState(Date.now());
  const [basemapError, setBasemapError] = useState(false);
  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { scrollWheelZoom: false }).setView([-21.7642, -43.3503], 12);
    const base = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(m);
    base.on("tileerror", () => setBasemapError(true));
    markers.current = L.layerGroup().addTo(m); map.current = m;
    const resize = new ResizeObserver(() => m.invalidateSize()); resize.observe(el.current);
    return () => { resize.disconnect(); m.remove(); map.current = null; };
  }, []);
  useEffect(() => {
    const group = markers.current; if (!group) return;
    group.clearLayers();
    pontos.forEach(p => {
      const icon = L.divIcon({ className: "", html: `<div class="pin" style="background:${colors[p.tipo]}">${icons[p.tipo]}</div>`, iconSize: [32, 32], iconAnchor: [16, 16] });
      const popup = document.createElement("div");
      const name = document.createElement("strong"); name.textContent = p.nome;
      const text = document.createElement("p"); text.textContent = p.descricao;
      popup.append(name, text);
      L.marker([p.lat, p.lng], { icon }).bindPopup(popup).addTo(group);
    });
    if (selected) L.circleMarker([selected.lat, selected.lng], { color: "#127e86", fillColor: "#127e86", fillOpacity: .3, radius: 13 }).bindTooltip("Local selecionado").addTo(group);
  }, [pontos, selected]);
  useEffect(() => {
    const m = map.current; if (!m || !onPick) return;
    const click = (e: L.LeafletMouseEvent) => onPick(e.latlng.lat, e.latlng.lng);
    m.on("click", click); m.getContainer().style.cursor = "crosshair";
    return () => { m.off("click", click); m.getContainer().style.cursor = ""; };
  }, [onPick]);
  useEffect(() => { if (foco) map.current?.flyTo([foco.lat, foco.lng], 15); }, [foco]);
  useEffect(() => {
    if (!showRadar) { setRadar(null); return; }
    let alive = true; const controller = new AbortController();
    async function load() {
      try {
        const r = await fetch("https://api.rainviewer.com/public/weather-maps.json", { signal: controller.signal });
        if (!r.ok) throw Error("radar");
        const d = await r.json();
        const frames: Frame[] = (d.radar?.past || []).filter((f: Frame) => Number.isFinite(f.time) && /^\/v2\/radar\//.test(f.path)).slice(-6);
        if (!frames.length || typeof d.host !== "string" || !/^https:\/\/[^/]*rainviewer\.com$/.test(d.host) || Date.now() - frames[frames.length - 1]!.time * 1000 > 30 * 60000) throw Error("radar");
        if (alive) { setRadar({ host: d.host, frames }); setIndex(frames.length - 1); setRadarError(false); }
      } catch { if (alive) { setRadarError(true); setRadar(null); } }
    }
    void load(); const t = setInterval(load, 10 * 60000);
    return () => { alive = false; controller.abort(); clearInterval(t); };
  }, [showRadar]);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(t); }, []);
  const stale = !!radar && now - radar.frames[radar.frames.length - 1]!.time * 1000 > 30 * 60000;
  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.forEach(l => l.remove()); layers.current = [];
    if (radar && !stale) layers.current = radar.frames.map(f => {
      const layer = L.tileLayer(`${radar.host}${f.path}/256/{z}/{x}/{y}/2/1_0.png`, { opacity: 0, attribution: '<a href="https://www.rainviewer.com/">Radar: RainViewer</a>', maxNativeZoom: 7, zIndex: 400, updateWhenIdle: true }).addTo(m);
      layer.on("tileerror", () => setRadarError(true)); return layer;
    });
    return () => { layers.current.forEach(l => l.remove()); layers.current = []; };
  }, [radar, stale]);
  useEffect(() => { layers.current.forEach((l, i) => l.setOpacity(i === index && !radarError ? .55 : 0)); }, [index, radar, radarError]);
  useEffect(() => { if (!radar || !playing || stale) return; const t = setInterval(() => setIndex(i => (i + 1) % radar.frames.length), 1600); return () => clearInterval(t); }, [radar, playing, stale]);
  const current = radar?.frames[index];
  return <div style={{ height: "100%", position: "relative" }}><div ref={el} style={{ height: "100%" }}/>{basemapError && <div className="radar-status" role="status">Mapa de fundo indisponível. Consulte a lista de relatos ao lado.</div>}{showRadar && <div className="radar-status" role="status">{radarError || stale ? "Radar indisponível ou desatualizado. Mapa vazio não indica ausência de chuva." : current ? <><button onClick={() => setPlaying(p => !p)} aria-label={playing ? "Pausar animação" : "Animar radar"} style={{ border: 0, background: "transparent", marginRight: 8 }}>{playing ? "❚❚" : "▶"}</button>Radar passado · {new Date(current.time * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" })} · cobertura pode ser incompleta. Não é previsão.</> : "Consultando radar passado…"}</div>}</div>;
}
