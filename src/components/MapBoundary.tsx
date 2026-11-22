import { Component, type ReactNode } from "react";

// Mantém um erro do mapa/radar dentro do card: o restante da página
// (previsão, rio, alertas, relatos) continua funcionando.
export class MapBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  override state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  override componentDidCatch(error: unknown) {
    console.error("Mapa falhou", error);
  }
  override render() {
    if (this.state.failed) {
      return (
        <div className="radar-status" role="status" style={{ padding: 16 }}>
          Mapa indisponível no momento. A previsão e os alertas acima continuam valendo.
        </div>
      );
    }
    return this.props.children;
  }
}
