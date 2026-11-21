export type RainViewerFrame = { time: number; path: string };
export type RainViewerData = { host: string; frames: RainViewerFrame[]; fetchedAt: number };

// RainViewer public Weather Maps API: https://www.rainviewer.com/api.html
// Free for small community projects, attribution required, no key.
export async function getRainViewer(): Promise<RainViewerData> {
  const response = await fetch("https://api.rainviewer.com/public/weather-maps.json", { signal: AbortSignal.timeout(12000) });
  if (!response.ok) throw Error("RainViewer indisponível");
  const data = await response.json();
  const host = typeof data?.host === "string" && data.host.startsWith("https://") ? data.host : "";
  const frames: RainViewerFrame[] = (Array.isArray(data?.radar?.past) ? data.radar.past : [])
    .filter((f: unknown) => Number.isSafeInteger((f as RainViewerFrame)?.time) && typeof (f as RainViewerFrame)?.path === "string" && (f as RainViewerFrame).path.startsWith("/v2/radar/"))
    .map((f: RainViewerFrame) => ({ time: f.time, path: f.path }))
    .filter((f: RainViewerFrame) => f.time * 1000 <= Date.now() + 5 * 60000)
    .sort((a: RainViewerFrame, b: RainViewerFrame) => a.time - b.time)
    .slice(-13);
  if (!host || !frames.length) throw Error("RainViewer sem quadros");
  return { host, frames, fetchedAt: Date.now() };
}
