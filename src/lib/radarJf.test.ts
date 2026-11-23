import { describe, expect, it } from "vitest";
import { classificarPixel, cruzarPrevisaoRadar, tileDoPonto } from "./radarJf";

describe("radarJf", () => {
  it("acha o tile z7 de Juiz de Fora", () => {
    const t = tileDoPonto(-21.7642, -43.3503);
    expect([t.x, t.y]).toEqual([48, 71]);
  });
  it("classifica cores da escala Universal Blue", () => {
    expect(classificarPixel(0, 0, 0, 0)).toBe("nenhum");
    expect(classificarPixel(215, 205, 180, 200)).toBe("nenhum");
    expect(classificarPixel(0, 145, 202, 255)).toBe("fraca");
    expect(classificarPixel(255, 220, 0, 255)).toBe("moderada");
    expect(classificarPixel(230, 40, 20, 255)).toBe("forte");
  });
  it("avisa quando a previsão discorda do radar", () => {
    expect(cruzarPrevisaoRadar("nenhum", { mm: 0.6, probabilidade: 80 })?.tom).toBe("aviso");
    expect(cruzarPrevisaoRadar("fraca", { mm: 0, probabilidade: 10 })?.tom).toBe("aviso");
    expect(cruzarPrevisaoRadar("fraca", { mm: 2, probabilidade: 90 })?.tom).toBe("ok");
    expect(cruzarPrevisaoRadar(null, { mm: 2, probabilidade: 90 })).toBeNull();
  });
});
