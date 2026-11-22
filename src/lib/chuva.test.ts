import { describe, expect, it } from "vitest";
import { resumirChuva, type LeituraChuva } from "./chuva";

const base = Date.parse("2026-11-22T20:00:00-03:00");
const serie = (horas: number, mm: (i: number) => number): LeituraChuva[] =>
  Array.from({ length: horas }, (_, i) => ({ time: new Date(base - (horas - 1 - i) * 3600000).toISOString(), mm: mm(i) }));

describe("resumirChuva", () => {
  it("soma apenas as últimas 24h e pega a última hora", () => {
    const r = resumirChuva(serie(30, () => 1), base);
    expect(r?.ultimaHora).toBe(1);
    expect(r?.acumulado24h).toBe(24);
    expect(r?.fresca).toBe(true);
  });
  it("marca como atrasada leitura com mais de 2h30", () => {
    const r = resumirChuva([{ time: new Date(base - 3 * 3600000).toISOString(), mm: 5 }], base);
    expect(r?.fresca).toBe(false);
    expect(r?.ultimaHora).toBe(5);
  });
  it("ignora leituras futuras e inválidas", () => {
    const r = resumirChuva([
      { time: new Date(base - 3600000).toISOString(), mm: 2 },
      { time: new Date(base + 3600000).toISOString(), mm: 99 },
      { time: "lixo", mm: 5 },
      { time: new Date(base - 2 * 3600000).toISOString(), mm: -1 },
    ], base);
    expect(r?.ultimaHora).toBe(2);
    expect(r?.acumulado24h).toBe(2);
  });
  it("retorna null sem leituras válidas", () => {
    expect(resumirChuva([], base)).toBeNull();
    expect(resumirChuva([{ time: "x", mm: 1 }], base)).toBeNull();
  });
  it("arredonda o acumulado para 1 casa decimal", () => {
    const r = resumirChuva(serie(3, () => 0.15), base);
    expect(r?.acumulado24h).toBe(0.5);
  });
});
