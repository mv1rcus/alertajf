import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InstallApp } from "./InstallApp";
afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });
describe("InstallApp", () => {
  it("remains accessible after an earlier permanent dismissal", () => {
    localStorage.setItem("ajf-install-off", "1");
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("iPhone Safari");
    render(<InstallApp/>);
    expect(screen.getByText("Adicionar à tela inicial")).toBeInTheDocument();
    expect(screen.getByText(/No Safari/)).toBeInTheDocument();
  });
  it("offers Android instructions without beforeinstallprompt or storage", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("Android Chrome");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw Error("disabled"); });
    render(<InstallApp/>);
    expect(screen.getByText(/três pontos/)).toBeInTheDocument();
  });
  it("uses the native prompt only once and hides after installation", async () => {
    render(<InstallApp/>);
    const prompt = vi.fn(async () => {});
    const event = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), { prompt });
    act(() => { window.dispatchEvent(event); });
    await act(async () => { fireEvent.click(screen.getByRole("button", {name:"Instalar Alerta JF"})); });
    expect(prompt).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", {name:"Instalar Alerta JF"})).not.toBeInTheDocument();
    act(() => { window.dispatchEvent(new Event("appinstalled")); });
    expect(screen.queryByText("Adicionar à tela inicial")).not.toBeInTheDocument();
  });
  it("does not offer installation inside the installed app", () => {
    vi.spyOn(window, "matchMedia").mockReturnValue({matches:true} as MediaQueryList);
    render(<InstallApp/>);
    expect(screen.queryByText("Adicionar à tela inicial")).not.toBeInTheDocument();
  });
});
