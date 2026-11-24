import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Ponto } from "@/lib/pontos";
import type { RainViewerData } from "@/lib/rainviewer";
import { reportMediaUrl, type ReportMedia } from "@/lib/reports";

const icons = { alagamento: "🌊", interdicao: "🚧", deslizamento: "⛰", sem_luz: "💡", relato: "📍" };
const colors = { alagamento: "#137eac", interdicao: "#bc5234", deslizamento: "#a0742a", sem_luz: "#6b5bb5", relato: "#127e86" };
const RADAR_LEGEND: [string, string, string?][] = [["#6cd1eb", "fraca"], ["#0091ca", "fraca a média"], ["#ffd200", "moderada"], ["#f07a00", "forte"], ["#d8212a", "muito forte"], ["#d94fc0", "extrema", "granizo possível"]];

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
  const markerLayers = useRef(new Map<string, L.Marker>());
  const markerSigs = useRef(new Map<string, string>());
  const selectedLayer = useRef<L.CircleMarker | null>(null);
  const openPonto = useRef<string | null>(null);
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
  // Mantém os marcadores entre atualizações dos dados: só recria o pino quando
  // o conteúdo do ponto muda, para não derrubar um popup aberto (ex.: vídeo tocando).
  useEffect(() => {
    const group = markers.current; if (!group) return;
    const buildPopup = (p: Ponto) => {
      const popup = document.createElement("div");
      // Cliques dentro do popup (controles do player de vídeo) chegam até
      // o contêiner do mapa: o Leaflet os trata como clique no mapa e fecha o popup,
      // cortando o vídeo. Bloqueamos a propagação na raiz do conteúdo do popup.
      L.DomEvent.disableClickPropagation(popup);
      popup.addEventListener("click", (e) => e.stopPropagation());
      popup.addEventListener("dblclick", (e) => e.stopPropagation());
      const name = document.createElement("strong"); name.textContent = p.nome;
      const text = document.createElement("p"); text.textContent = p.descricao;
      popup.append(name, text);
      if (p.media?.length) {
        const box = document.createElement("div"); box.className = "popup-media";
        const makeItem = (m: ReportMedia) => {
          const url = reportMediaUrl(m.path);
          if (m.kind === "video") {
            // O src precisa estar no elemento desde já: sem ele o play nativo dos
            // controles fica carregando para sempre. Com preload="none" o navegador
            // não baixa nada até a pessoa tocar no play do próprio player.
            const v = document.createElement("video"); v.controls = true; v.playsInline = true; v.preload = "none"; v.src = url;
            return v;
          }
          const a = document.createElement("a"); a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer";
          const img = document.createElement("img"); img.src = url; img.alt = `Foto do relato em ${p.nome}`; img.loading = "lazy";
          a.append(img); return a;
        };
        if (p.media.length === 1) {
          const m = p.media[0]!;
          box.append(makeItem(m));
          if (m.credit) { const c = document.createElement("small"); c.textContent = `Mídia: ${m.credit}`; box.append(c); }
        } else {
          // Várias mídias empilhadas estouram a altura do popup no celular e o
          // conteúdo não rola. Carrossel: uma mídia por vez, setas e indicadores.
          const car = document.createElement("div"); car.className = "popup-media-carousel";
          const vp = document.createElement("div"); vp.className = "popup-media-viewport";
          const track = document.createElement("div"); track.className = "popup-media-track";
          p.media.forEach(m => { const slide = document.createElement("div"); slide.className = "popup-media-slide"; slide.append(makeItem(m)); track.append(slide); });
          vp.append(track); car.append(vp);
          const dots = document.createElement("div"); dots.className = "popup-media-dots";
          const credit = document.createElement("small"); credit.className = "popup-media-credit";
          let i = 0;
          const go = (k: number) => {
            i = (k + p.media!.length) % p.media!.length;
            track.style.transform = `translateX(-${i * 100}%)`;
            [...dots.children].forEach((d, k2) => d.classList.toggle("on", k2 === i));
            track.querySelectorAll("video").forEach((v, k2) => { if (k2 !== i) v.pause(); });
            const cr = p.media![i]!.credit;
            credit.textContent = cr ? `Mídia: ${cr}` : ""; credit.style.display = cr ? "" : "none";
          };
          p.media.forEach((_, k) => { const d = document.createElement("button"); d.type = "button"; d.setAttribute("aria-label", `Mídia ${k + 1} de ${p.media!.length}`); d.addEventListener("click", () => go(k)); dots.append(d); });
          const nav = (label: string, cls: string, step: number, aria: string) => {
            const b = document.createElement("button"); b.type = "button"; b.className = `popup-media-nav ${cls}`; b.textContent = label; b.setAttribute("aria-label", aria);
            b.addEventListener("click", () => go(i + step)); return b;
          };
          car.append(nav("\u2039", "prev", -1, "Mídia anterior"), nav("\u203a", "next", 1, "Próxima mídia"));
          box.append(car, dots, credit); go(0);
        }
        popup.append(box);
      }
      return popup;
    };
    const seen = new Set<string>();
    pontos.forEach(p => {
      seen.add(p.id);
      const sig = JSON.stringify(p);
      if (markerSigs.current.get(p.id) === sig) return;
      const old = markerLayers.current.get(p.id);
      if (old) group.removeLayer(old);
      const icon = L.divIcon({ className: "", html: `<div class="pin" style="background:${colors[p.tipo]}">${icons[p.tipo]}</div>`, iconSize: [32, 32], iconAnchor: [16, 16] });
      const marker = L.marker([p.lat, p.lng], { icon }).bindPopup(buildPopup(p), { maxWidth: Math.min(250, window.innerWidth - 56), keepInView: true, autoPanPadding: L.point(28, 90) });
      marker.on("popupopen", () => { openPonto.current = p.id; });
      marker.on("popupclose", () => { if (openPonto.current === p.id) openPonto.current = null; });
      marker.addTo(group);
      markerLayers.current.set(p.id, marker);
      markerSigs.current.set(p.id, sig);
      if (openPonto.current === p.id) marker.openPopup();
    });
    markerLayers.current.forEach((layer, id) => {
      if (!seen.has(id)) { group.removeLayer(layer); markerLayers.current.delete(id); markerSigs.current.delete(id); }
    });
    if (selectedLayer.current) { group.removeLayer(selectedLayer.current); selectedLayer.current = null; }
    if (selected) selectedLayer.current = L.circleMarker([selected.lat, selected.lng], { color: "#127e86", fillColor: "#127e86", fillOpacity: .3, radius: 13 }).bindTooltip("Local selecionado").addTo(group);
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
  const hasForecast = source === "rainviewer" && !!rvFrames?.some(f => f.forecast);
  return <div className="rain-map-layout"><div className="rain-map-canvas"><div ref={el} style={{ height: "100%" }}/><div className="map-views"><button onClick={() => map.current?.setView([-21.7642, -43.3503], 9)}>Região / chuva</button><button onClick={() => map.current?.setView([-21.7642, -43.3503], 13)}>Ruas de JF</button></div>{basemapError && <div className="radar-status" role="status">Mapa de fundo indisponível. Consulte a lista de relatos ao lado.</div>}</div>{showRadar && source === "rainviewer" && <div className="radar-legend" role="group" aria-label="Legenda de intensidade do radar"><div className="radar-legend-head"><b>Intensidade da chuva</b><span>do mais fraco ao mais forte</span></div><div className="radar-legend-bar" aria-hidden="true">{RADAR_LEGEND.map(([c]) => <i key={c} style={{ background: c }}/>)}</div><ul className="radar-legend-items">{RADAR_LEGEND.map(([c, t, d]) => <li key={t}><i style={{ background: c }} aria-hidden="true"/><span><b>{t}</b>{d && <small>{d}</small>}</span></li>)}</ul><p className="radar-legend-note">Cores aproximadas, escala do RainViewer. O mapa mostra eco de chuva, não milímetros.</p></div>}{showRadar && <div className="radar-caption-outside" role="status">{radarError || !source ? "Radar recente indisponível. Mapa vazio não indica ausência de chuva." : currentTime !== null ? <><button onClick={() => setPlaying(p => !p)} aria-label={playing ? "Voltar ao quadro mais recente" : hasForecast ? "Animar histórico e previsão do radar" : "Animar histórico de chuva observada"} style={{ border: 0, background: "transparent", marginRight: 8 }}>{playing ? "■" : "▶"}</button>{playing ? <>Animação · quadro {index + 1}/{frameCount} · {new Date(currentTime).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" })} · {currentForecast ? `previsão daqui a ${Math.max(0, Math.round((currentTime - now) / 60000))} min` : `há ${ageMin} min`} · ■ volta ao quadro mais recente.</> : <>AO VIVO · {source === "rainviewer" ? "RainViewer · mosaico de radares" : "INPE / Pico do Couto"} · quadro mais recente: {new Date(currentTime).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" })} (há {ageMin} min), atualiza a cada ~10 min. O radar mede a chuva do alto e a imagem chega com alguns minutos de atraso. ▶ anima as últimas 2h{hasForecast ? " e a previsão dos próximos ~30 min" : ""}.</>}</> : "Consultando radar passado…"}</div>}</div>;
               }
