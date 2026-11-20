import { describe, it, expect } from "vitest";
import { avaliarRisco } from "./clima";
describe("avaliarRisco", () => {
  it("chuva de 10 mm/h é crítico", () => expect(avaliarRisco({ chuvaMm: 10, rajadaKmh: 0, codigo: 0 }).nivel).toBe("critico"));
  it("rajada de 60 km/h é crítico", () => expect(avaliarRisco({ chuvaMm: 0, rajadaKmh: 60, codigo: 0 }).nivel).toBe("critico"));
  it("trovoada é crítico", () => expect(avaliarRisco({ chuvaMm: 0, rajadaKmh: 0, codigo: 95 }).nivel).toBe("critico"));
  it("chuva de 5 mm/h é atenção", () => expect(avaliarRisco({ chuvaMm: 5, rajadaKmh: 0, codigo: 0 }).nivel).toBe("atencao"));
  it("tempo calmo é normal", () => expect(avaliarRisco({ chuvaMm: 1, rajadaKmh: 20, codigo: 3 }).nivel).toBe("normal"));
});
