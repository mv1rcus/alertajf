import { describe, expect, it } from "vitest";
import { resumirChuva, normalizarChuva, escolherEstacaoChuva, type LeituraChuva } from "./chuva";
const H = 3600000;
const base = Date.parse("2026-11-23T04:00:00-03:00");
const serie = (horas = 24, fim = base): LeituraChuva[] => Array.from({ length: horas }, (_, i) => ({ time: new Date(fim - (horas - 1 - i) * H).toISOString(), mm: 1 }));
describe("chuva horária e referência estável", () => {
  it("soma 24 horas, excluindo o limite inicial", () => {
    const r = resumirChuva(serie(30), base + 15 * 60000)!;
    expect(r.acumulado24h).toBe(24); expect(r.completa).toBe(true);
    expect(r.horasValidas).toBe(24); expect(Date.parse(r.inicioEm)).toBe(base - 24 * H);
  });
  it("leitura atrasada conserva a janela até essa leitura, não perde horas pelo relógio", () => {
    const r = resumirChuva(serie(), base + 5 * H)!;
    expect(r.fresca).toBe(false); expect(r.acumulado24h).toBe(24);
    expect(r.completa).toBe(true); expect(Date.parse(r.leituraEm)).toBe(base);
  });
  it("hora faltando dá cobertura incompleta, não zero medido", () => {
    const r = resumirChuva(serie().filter((_, i) => i !== 10), base)!;
    expect(r.acumulado24h).toBe(23); expect(r.horasValidas).toBe(23); expect(r.completa).toBe(false);
  });
  it("ignora duplicados com o mesmo timestamp", () => {
    const s = serie(); const r = resumirChuva([...s, s[5]!, s[5]!], base)!;
    expect(r.acumulado24h).toBe(24); expect(r.horasValidas).toBe(24);
  });
  it("conflito no timestamp tem resultado determinístico e não soma as duplicatas", () => {
    const s = [...serie(), { time: new Date(base).toISOString(), mm: 3 }];
    expect(resumirChuva(s, base)?.acumulado24h).toBe(26);
    expect(resumirChuva(s.reverse(), base)?.acumulado24h).toBe(26);
  });
  it("ordena leituras e exclui inválidas, futuras e hora ainda não completa", () => {
    const s = [...serie().reverse(), {time: "lixo", mm: 4}, {time: new Date(base + H).toISOString(), mm: 99}, {time: new Date(base + H / 2).toISOString(), mm: 99}, {time: new Date(base - H).toISOString(), mm: -1}];
    expect(resumirChuva(s, base + H / 2)?.acumulado24h).toBe(24);
    expect(normalizarChuva(s, base + H / 2)).toHaveLength(24);
  });
  it("empate de horários e ordem de chegada não trocam estação de referência", () => {
    const principal = { ordem: 0, leituras: serie() }; const outra = { ordem: 1, leituras: serie() };
    expect(escolherEstacaoChuva([outra, principal], base)).toBe(principal);
    expect(escolherEstacaoChuva([principal, outra], base)).toBe(principal);
  });
  it("outra estação mais recente não troca a referência atrasada; sem dado há fallback", () => {
    const principal = { ordem: 0, leituras: serie(24, base - 3 * H) }; const outra = { ordem: 1, leituras: serie() };
    expect(escolherEstacaoChuva([outra, principal], base)).toBe(principal);
    expect(escolherEstacaoChuva([{ordem: 0, leituras: []}, outra], base)).toBe(outra);
  });
  it("sem dado não produz zero e arredonda a soma para uma casa", () => {
    expect(resumirChuva([], base)).toBeNull();
    expect(resumirChuva(serie(3).map(l => ({...l, mm: .15})), base)?.acumulado24h).toBe(.5);
  });
});
