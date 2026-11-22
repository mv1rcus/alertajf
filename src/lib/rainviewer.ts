export type RainViewerFrame = { time: number; path: string; forecast?: boolean };
export type RainViewerData = { host: string; frames: RainViewerFrame[]; fetchedAt: number };

// RainViewer public Weather Maps API: https://www.rainviewer.com/api.html
// Free for small community projects, attribution required, no key.
export async function getRainViewer(): Promise<RainViewerData> {
  const response = await fetch("https://api.rainviewer.com/public/weather-maps.json", { signal: AbortSignal.timeout(12000) });
  if (!response.ok) throw Error("RainViewer indisponível");
  const data = await response.json();
  const host = typeof data?.host === "string" && data.host.startsWith("https://") ? data.host : "";
  const valid = (f: unknown): f is RainViewerFrame => Number.isSafeInteger((f as RainViewerFrame)?.time) && typeof (f as RainViewerFrame)?.path === "string" && (f as RainViewerFrame).path.startsWith("/v2/radar/");
  const past: RainViewerFrame[] = (Array.isArray(data?.radar?.past) ? data.radar.past : [])
    .filter(valid)
    .map((f: RainViewerFrame) => ({ time: f.time, path: f.path }))
    .filter((f: RainViewerFrame) => f.time * 1000 <= Date.now() + 5 * 60000)
    .sort((a: RainViewerFrame, b: RainViewerFrame) => a.time - b.time)
    .slice(-13);
  const nowcast: RainViewerFrame[] = (Array.isArray(data?.radar?.nowcast) ? data.radar.nowcast : [])
    .filter(valid)
    .map((f: RainViewerFrame) => ({ time: f.time, path: f.path, forecast: true as const }))
    .sort((a: RainViewerFrame, b: RainViewerFrame) => a.time - b.time)
    .slice(0, 4);
  if (!host || !past.length) throw Error("RainViewer sem quadros");
  return { host, frames: [...past, ...nowcast], fetchedAt: Date.now() };
}
