import { useEffect, useState } from "react";
import { Smartphone } from "lucide-react";

type InstallPrompt = Event & { prompt: () => Promise<void> };
export function InstallApp() {
  const [ready, setReady] = useState(false);
  const [installed, setInstalled] = useState(false);
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [ios, setIos] = useState(false);
  const [android, setAndroid] = useState(false);
  const [note, setNote] = useState("");
  useEffect(() => {
    setReady(true);
    setInstalled(window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true);
    setIos(/iPhone|iPad|iPod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));
    setAndroid(/Android/i.test(navigator.userAgent));
    const before = (event: Event) => { event.preventDefault(); setPrompt(event as InstallPrompt); };
    const done = () => { setInstalled(true); setPrompt(null); };
    window.addEventListener("beforeinstallprompt", before);
    window.addEventListener("appinstalled", done);
    return () => { window.removeEventListener("beforeinstallprompt", before); window.removeEventListener("appinstalled", done); };
  }, []);
  async function install() {
    const pending = prompt;
    setPrompt(null);
    try { await pending?.prompt(); }
    catch { setNote("Use as instruções abaixo para adicionar pelo menu do navegador."); }
  }
  if (!ready || installed) return null;
  return <section className="install-access" aria-label="Instalar Alerta JF">
    <details>
      <summary><Smartphone size={18}/>Adicionar à tela inicial<span>Grátis</span></summary>
      <div className="install-instructions">
        <p>Abra o Alerta JF pelo ícone no seu aparelho. Não precisa de loja de aplicativos.</p>
        {prompt && <button type="button" className="primary" onClick={() => void install()}>Instalar Alerta JF</button>}
        {ios ? <p>No Safari, abra o menu e toque em Compartilhar (ou toque direto no ícone de compartilhar). Depois escolha "Adicionar à Tela de Início" e confirme em "Adicionar". Se a opção não aparecer, procure em "Editar Ações".</p>
          : android ? <p>No Chrome, toque no menu de três pontos e procure "Instalar e criar atalho", "Instalar app" ou "Adicionar à tela inicial". Confirme a instalação. O nome da opção varia conforme a versão.</p>
          : <p>No celular, abra este site no Safari (iPhone) ou Chrome (Android) e use o menu de compartilhar ou instalar. No computador, procure a opção de instalar no menu do navegador, se disponível.</p>}
        <p className="caption">Se abriu dentro de outro app, abra primeiro no Safari ou Chrome. Fechar estas instruções não remove esta opção. Dados atualizados precisam de internet.</p>
        {note && <p role="status">{note}</p>}
      </div>
    </details>
  </section>;
}
