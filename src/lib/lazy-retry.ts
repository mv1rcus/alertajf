import { lazy, type ComponentType } from "react";

// Logo após um deploy, um navegador que ainda tem o HTML antigo pode pedir um
// chunk dinâmico que já não existe no servidor (404) — sem tratamento, o erro
// do import() derruba a página inteira no error boundary. Aqui recarregamos a
// página uma única vez por chunk; se mesmo assim falhar, o erro sobe para o
// boundary local do componente em vez de derrubar o app.
export function lazyWithRetry<T extends ComponentType<never>>(
  factory: () => Promise<{ default: T }>,
) {
  return lazy(async () => {
    try {
      return await factory();
    } catch (error) {
      const key = `lazy-retry:${String((error as Error)?.message ?? error).slice(0, 60)}`;
      if (typeof window !== "undefined" && !window.sessionStorage.getItem(key)) {
        window.sessionStorage.setItem(key, "1");
        window.location.reload();
        return new Promise<{ default: T }>(() => {});
      }
      throw error;
    }
  });
}
