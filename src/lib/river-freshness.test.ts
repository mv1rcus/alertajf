import { describe, it, expect } from "vitest";
import { riverReadingAge, riverReadingStale } from "./river-freshness";
const now = Date.parse("2026-11-22T14:05:00-03:00");
describe("river measurement freshness", () => {
  it("keeps an exactly 2h old sample recent", () => expect(riverReadingStale("2026-11-22T12:05:00-03:00", now)).toBe(false));
  it("marks a sample older than 2h stale, even by one second", () => expect(riverReadingStale("2026-11-22T12:04:59-03:00", now)).toBe(true));
  it("uses the measurement time, not the query time", () => {
    expect(riverReadingAge("2026-11-22T12:00:00-03:00", now)).toBe(125);
    expect(riverReadingStale("2026-11-22T12:00:00-03:00", now)).toBe(true);
  });
  it("rejects missing, invalid and future times", () => {
    for (const time of [undefined, "bad", "2026-11-22T15:00:00-03:00"])
      expect(riverReadingStale(time, now)).toBe(true);
  });
  it("keeps yesterday's reading stale", () => expect(riverReadingStale("2026-11-21T12:00:00-03:00", now)).toBe(true));
});
