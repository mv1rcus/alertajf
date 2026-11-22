import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Ponto } from "@/lib/pontos";
import type { RainViewerData } from "@/lib/rainviewer";

const icons = { alagamento: "🌊", interdicao: "🚧", deslizamento: "⛰", sem_luz: "💡", relato: "📍" };
const colors = { alagamento: "#137eac", interdicao: "#bc5234", deslizamento: "#a0742a", sem_luz: "#6b5bb5", relato: "#127e86" };
export default function RainMap({ pontos, showRadar, foco, onPick, selected, radarFrames, rv }: {
  radarFrames?: { time: string; url: string; bbox: number[] }[] | undefined; radarStatus?: string | undefined;
  rv?: RainViewerData | null | undefined;
  pontos: Ponto[]; showRadar: boolean; foco: Ponto | null;
  onPick?: ((lat: number, lng: number) => void) | undefined;
  selected?: { lat: number; lng: number } | null;
}) {

  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef<L.LayerGroup | null>(null);
  const layers = useRef<L.GridLayer[]>([]);
  const radar = radarFrames?.length ? radarFrames : null;
  const [radarError, setRadarError] = useState(false);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [basemapError, setBasemapError] = useState(false);
  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { scrollWheelZoom: false }).setView([-21.7642, -43.3503], 9);
    const base = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, className: "dark-base", attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(m);
    base.on("tileerror", () => setBasemapError(true));
    L.circleMarker([-21.7642, -43.3503], { color: "#e0fafa", fillColor: "#22aaa8", fillOpacity: 1, radius: 6, weight: 2 }).bindTooltip("Juiz de Fora", { permanent: true, direction: "right" }).addTo(m);
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
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(t); }, []);
  const rvFrames = rv?.frames.length ? rv.frames : null;
  const rvStale = !rvFrames || now - rvFrames[rvFrames.length - 1]!.time * 1000 > 30 * 60000;
  const inpeStale = !!radar && now - Date.parse(radar[radar.length - 1]!.time) > 90 * 60000;
  const source: "rainviewer" | "inpe" | null = rvFrames && !rvStale ? "rainviewer" : radar && !inpeStale ? "inpe" : null;
  const frameCount = source === "rainviewer" ? rvFrames!.length : source === "inpe" ? radar!.length : 0;
  const lastPastIndex = source === "rainviewer" && rvFrames ? Math.max(0, rvFrames.reduce((acc, f, i) => (f.forecast ? acc : i), 0)) : Math.max(0, frameCount - 1);
  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.forEach(l => l.remove()); layers.current = [];
    if (source === "rainviewer" && rv && showRadar) {
      layers.current = rvFrames!.map(f => {
        const layer = L.tileLayer(`${rv.host}${f.path}/256/{z}/{x}/{y}/4/1_1.png`, { maxNativeZoom: 7, opacity: 0, zIndex: 400, attribution: 'Radar: <a href="https://www.rainviewer.com/" target="_blank" rel="noreferrer">RainViewer</a>' });
        layer.on("tileerror", () => setRadarError(true));
        return layer.addTo(m);
      });
    } else if (source === "inpe" && radar && showRadar) {
      layers.current = radar.map(f => {
        const [west, south, east, north] = f.bbox as [number, number, number, number];
        const image = new Image(); image.src = f.url;
        const makeTile = (coords: L.Coords, done: L.DoneCallback) => {
          const canvas = document.createElement("canvas"); canvas.width = 256; canvas.height = 256;
          const paint = () => {
            const ctx = canvas.getContext("2d"); if (!ctx) { done(undefined, canvas); return; }
            const left = m.unproject(L.point(coords.x * 256, coords.y * 256), coords.z).lng;
            const right = m.unproject(L.point((coords.x + 1) * 256, coords.y * 256), coords.z).lng;
            const sx = (left - west) / (east - west) * image.width;
            const sw = (right - left) / (east - west) * image.width;
            for (let y = 0; y < 256; y++) {
              const latTop = m.unproject(L.point(coords.x * 256, coords.y * 256 + y), coords.z).lat;
              const latBottom = m.unproject(L.point(coords.x * 256, coords.y * 256 + y + 1), coords.z).lat;
              const sy = (north - latTop) / (north - south) * image.height;
              const sh = (latTop - latBottom) / (north - south) * image.height;
              if (sy >= 0 && sy < image.height) ctx.drawImage(image, sx, sy, sw, Math.max(sh, .01), 0, y, 256, 1);
            }
            done(undefined, canvas);
          };
          if (image.complete && image.naturalWidth) paint();
          else { image.addEventListener("load", paint, { once: true }); image.addEventListener("error", () => { setRadarError(true); done(new Error("Radar indisponível"), canvas); }, { once: true }); }
          return canvas;
        };
        class RadarLayer extends L.GridLayer { public override createTile(coords: L.Coords, done: L.DoneCallback): HTMLElement { return makeTile(coords, done); } }
        return new RadarLayer({ opacity: 0, zIndex: 400, attribution: '<a href="https://data.inpe.br/dados/radares-meteorologicos/">Radar: INPE / DECEA</a>' }).addTo(m);
      });
    }
    return () => { layers.current.forEach(l => l.remove()); layers.current = []; };
  }, [source, rv, radarFrames, showRadar]);
  useEffect(() => { layers.current.forEach((l, i) => l.setOpacity(i === index && !radarError ? .55 : 0)); }, [index, source, rv, radarFrames, radarError, showRadar]);
  useEffect(() => { if (!frameCount || !playing) return; const t = setInterval(() => setIndex(i => (i + 1) % frameCount), source === "rainviewer" ? 900 : 1600); return () => clearInterval(t); }, [source, frameCount, playing]);
  useEffect(() => { setRadarError(false); setIndex(lastPastIndex); }, [source, rv, radarFrames, lastPastIndex]);
  useEffect(() => { if (!playing) setIndex(lastPastIndex); }, [playing, lastPastIndex]);
  const current = source === "rainviewer" && rvFrames ? rvFrames[Math.min(index, rvFrames.length - 1)]! : source === "inpe" && radar ? radar[Math.min(index, radar.length - 1)]! : null;
  const currentTime = current ? (typeof current.time === "number" ? current.time * 1000 : Date.parse(current.time)) : null;
  const ageMin = currentTime ? Math.max(0, Math.round((now - currentTime) / 60000)) : null;
  const currentForecast = source === "rainviewer" && current ? Boolean((current as { forecast?: boolean }).forecast) : false;
  return <div style={{ height: "100%", position: "relative" }}><div ref={el} style={{ height: "100%" }}/><div className="map-views"><button onClick={() => map.current?.setView([-21.7642, -43.3503], 9)}>Região / chuva</button><button onClick={() => map.current?.setView([-21.7642, -43.3503], 13)}>Ruas de JF</button></div>{basemapError && <div className="radar-status" role="status">Mapa de fundo indisponível. Consulte a lista de relatos ao lado.</div>}{showRadar && <div className="radar-status" role="status">{radarError || !source ? "Radar recente indisponível. Mapa vazio não indica ausência de chuva." : currentTime !== null ? <><button onClick={() => setPlaying(p => !p)} aria-label={playing ? "Voltar ao quadro mais recente" : "Animar histórico e previsão do radar"} style={{ border: 0, background: "transparent", marginRight: 8 }}>{playing ? "■" : "▶"}</button>{playing ? <>Animação · quadro {index + 1}/{frameCount} · {new Date(currentTime).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" })} · {currentForecast ? `previsão daqui a ${Math.max(0, Math.round((currentTime - now) / 60000))} min` : `há ${ageMin} min`} · ■ volta ao quadro mais recente.</> : <>AO VIVO · {source === "rainviewer" ? "RainViewer · mosaico de radares" : "INPE / Pico do Couto"} · quadro mais recente: {new Date(currentTime).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" })} (há {ageMin} min), atualiza a cada ~10 min. O radar mede a chuva do alto e a imagem chega com alguns minutos de atraso. ▶ anima as últimas 2h e a previsão dos próximos ~30 min.</>}</> : "Consultando radar passado…"}</div>}</div>;
               }

