import { describe, it, expect } from "vitest";
import { avaliarRio } from "./rio";
describe("avaliarRio", () => {
  it("2,5x o normal é crítico", () => expect(avaliarRio(50, 20)).toBe("critico"));
  it("1,6x o normal é atenção", () => expect(avaliarRio(32, 20)).toBe("atencao"));
  it("abaixo de 1,6x é normal", () => expect(avaliarRio(31, 20)).toBe("normal"));
});
