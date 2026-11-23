// Leitura do radar observado (RainViewer) sobre um ponto de Juiz de Fora.
// Os tiles do RainViewer aceitam leitura de pixel (CORS aberto) e só existem até o zoom 7.
export type NivelRadar = "nenhum" | "fraca" | "moderada" | "forte";
export const ZOOM_RADAR = 7;

export function tileDoPonto(lat: number, lon: number, z = ZOOM_RADAR) {
  const n = 2 ** z;
  const fx = ((lon + 180) / 360) * n;
  const fy = ((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2) * n;
  const x = Math.floor(fx), y = Math.floor(fy);
  return { z, x, y, px: Math.floor((fx - x) * 256), py: Math.floor((fy - y) * 256) };
}

/** Escala "Universal Blue" do RainViewer: azul = fraca, amarelo/laranja = moderada, vermelho/magenta = forte.
 * Cinza ou bege (halo de suavização) e pixel transparente não contam como chuva. */
export function classificarPixel(r: number, g: number, b: number, a: number): NivelRadar {
  if (a < 40) return "nenhum";
  if (Math.max(r, g, b) - Math.min(r, g, b) < 45) return "nenhum";
  if (b > r + 40 && b >= g - 20) return "fraca";
  if (r > 200 && g < 110) return "forte";
  if (r > 200 && b > 150) return "forte";
  if (r > 180) return "moderada";
  return "fraca";
}

const ORDEM: NivelRadar[] = ["nenhum", "fraca", "moderada", "forte"];
export function maiorNivel(a: NivelRadar, b: NivelRadar): NivelRadar { return ORDEM.indexOf(a) >= ORDEM.indexOf(b) ? a : b; }

/** Maior nível numa janela 5x5 pixels (~ poucos km) ao redor do ponto. */
export function nivelNaImagem(data: Uint8ClampedArray, largura: number, px: number, py: number): NivelRadar {
  let nivel: NivelRadar = "nenhum";
  for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
    const x = px + dx, y = py + dy;
    if (x < 0 || y < 0 || x >= largura || y >= largura) continue;
    const i = (y * largura + x) * 4;
    nivel = maiorNivel(nivel, classificarPixel(data[i]!, data[i + 1]!, data[i + 2]!, data[i + 3]!));
  }
  return nivel;
}

export async function lerRadarNoPonto(host: string, path: string, lat: number, lon: number): Promise<NivelRadar> {
  const t = tileDoPonto(lat, lon);
  const img = new Image();
  img.crossOrigin = "anonymous";
  await new Promise<void>((ok, erro) => {
    const timer = setTimeout(() => erro(new Error("radar")), 12000);
    img.onload = () => { clearTimeout(timer); ok(); };
    img.onerror = () => { clearTimeout(timer); erro(new Error("radar")); };
    img.src = `${host}${path}/256/${t.z}/${t.x}/${t.y}/2/1_1.png`;
  });
  const canvas = document.createElement("canvas"); canvas.width = 256; canvas.height = 256;
  const ctx = canvas.getContext("2d"); if (!ctx) throw new Error("radar");
  ctx.drawImage(img, 0, 0);
  return nivelNaImagem(ctx.getImageData(0, 0, 256, 256).data, 256, t.px, t.py);
}

export type Cruzamento = { tom: "ok" | "aviso" | "info"; texto: string };

/** Compara a previsão por modelo (hora atual) com o que o radar observa. */
export function cruzarPrevisaoRadar(radar: NivelRadar | null, modelo: { mm: number; probabilidade: number } | null): Cruzamento | null {
  if (!radar || !modelo) return null;
  const modeloChuva = modelo.mm >= 0.5 || modelo.probabilidade >= 70;
  const radarChuva = radar !== "nenhum";
  if (modeloChuva && !radarChuva) return { tom: "aviso", texto: "A previsão marca chuva para esta hora, mas o radar não vê chuva sobre o ponto agora. Previsão é modelo e erra o horário; o radar é o que está acontecendo." };
  if (!modeloChuva && radarChuva) return { tom: "aviso", texto: "O radar vê chuva sobre o ponto, mesmo sem a previsão marcar. Vale confirmar pela janela." };
  if (modeloChuva && radarChuva) return { tom: "ok", texto: "Previsão e radar concordam: tem chuva sobre o ponto." };
  return { tom: "info", texto: "Previsão e radar concordam: sem chuva sobre o ponto agora." };
}
