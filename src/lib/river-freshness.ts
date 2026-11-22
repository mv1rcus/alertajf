export function riverReadingAge(time: string | undefined, now: number): number | null {
  const measuredAt = time ? Date.parse(time) : NaN;
  return Number.isFinite(measuredAt) && measuredAt <= now + 60000
    ? Math.max(0, Math.floor((now - measuredAt) / 60000)) : null;
}
export function riverReadingStale(time: string | undefined, now: number): boolean {
  return riverReadingAge(time, now) === null || now - Date.parse(time!) > 120 * 60000;
}
