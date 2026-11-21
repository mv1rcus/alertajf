/** Descargas elétricas quase em tempo real (rede de detecção do INPE/CPTEC). */

export type Raios = { descargas: number; celulas: number; atualizado: string };

/** Contorno simplificado do município de Juiz de Fora (IBGE 3136702), [lon, lat]. */
const JF: number[][] = [[-43.4317,-21.5396],[-43.4193,-21.5309],[-43.3871,-21.5441],[-43.3861,-21.5577],[-43.377,-21.5575],[-43.3512,-21.5958],[-43.3573,-21.6031],[-43.3482,-21.6178],[-43.3596,-21.6265],[-43.3554,-21.6364],[-43.3355,-21.6444],[-43.3398,-21.6519],[-43.3251,-21.6626],[-43.3029,-21.6537],[-43.2797,-21.6861],[-43.2595,-21.6807],[-43.2661,-21.6981],[-43.2592,-21.7164],[-43.2577,-21.742],[-43.2632,-21.7445],[-43.2579,-21.7548],[-43.2407,-21.7537],[-43.247,-21.7683],[-43.1878,-21.743],[-43.1689,-21.7685],[-43.1773,-21.7939],[-43.1473,-21.8127],[-43.189,-21.8547],[-43.209,-21.8416],[-43.2371,-21.8617],[-43.2486,-21.8494],[-43.2429,-21.8347],[-43.2521,-21.828],[-43.2743,-21.8389],[-43.2826,-21.8223],[-43.31,-21.8249],[-43.3416,-21.8109],[-43.3666,-21.828],[-43.3764,-21.8261],[-43.3903,-21.8458],[-43.3941,-21.8582],[-43.3748,-21.8961],[-43.4067,-21.8774],[-43.4185,-21.8939],[-43.427,-21.8822],[-43.4171,-21.8762],[-43.4163,-21.855],[-43.4439,-21.8592],[-43.4418,-21.8764],[-43.4608,-21.8742],[-43.457,-21.8877],[-43.4655,-21.8832],[-43.4748,-21.8912],[-43.4805,-21.8793],[-43.4985,-21.8812],[-43.4914,-21.8875],[-43.4951,-21.9042],[-43.4884,-21.9053],[-43.4963,-21.9154],[-43.4906,-21.9356],[-43.5855,-21.9991],[-43.5959,-21.9784],[-43.5771,-21.9637],[-43.5794,-21.9538],[-43.6119,-21.9049],[-43.6519,-21.9059],[-43.6521,-21.8945],[-43.6383,-21.8918],[-43.6379,-21.8845],[-43.6448,-21.8685],[-43.6575,-21.8661],[-43.6662,-21.8531],[-43.6413,-21.8218],[-43.6306,-21.8183],[-43.6365,-21.796],[-43.6526,-21.7886],[-43.6545,-21.768],[-43.6679,-21.7505],[-43.6603,-21.7229],[-43.6711,-21.7237],[-43.6812,-21.7024],[-43.6701,-21.6706],[-43.685,-21.6612],[-43.6799,-21.6535],[-43.6847,-21.6282],[-43.6563,-21.5971],[-43.6352,-21.6131],[-43.6209,-21.6142],[-43.6115,-21.6403],[-43.5967,-21.6146],[-43.5417,-21.6203],[-43.5272,-21.5917],[-43.5161,-21.5881],[-43.511,-21.5595],[-43.4935,-21.5554],[-43.4962,-21.533],[-43.4774,-21.5432],[-43.4728,-21.5308],[-43.4505,-21.5205],[-43.4391,-21.5246],[-43.4371,-21.5368]];

/** Ponto dentro de polígono (raio horizontal). */
function dentro(poly: number[][], x: number, y: number): boolean {
  let ok = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) ok = !ok;
  }
  return ok;
}

function cruza(a: number[], b: number[], c: number[], d: number[]): boolean {
  const s = (p: number[], q: number[], r: number[]) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const d1 = s(c, d, a), d2 = s(c, d, b), d3 = s(a, b, c), d4 = s(a, b, d);
  return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
}

/** A célula de tempestade toca o município? (vértice dentro ou arestas que se cruzam) */
function sobreJF(anel: number[][]): boolean {
  if (anel.some(p => dentro(JF, p[0], p[1]))) return true;
  if (JF.some(p => dentro(anel, p[0], p[1]))) return true;
  for (let i = 0; i < anel.length - 1; i++)
    for (let j = 0; j < JF.length; j++)
      if (cruza(anel[i], anel[i + 1], JF[j], JF[(j + 1) % JF.length])) return true;
  return false;
}

/** Nome do arquivo mais recente do INPE (janelas de 5 min, UTC), tentando as últimas 6 janelas. */
async function buscarArquivo(): Promise<Record<string, unknown> | null> {
  const base = "https://granizo1.cptec.inpe.br/nowcasting/RAIOS";
  const agora = Date.now() - 8 * 60000;
  for (let i = 0; i < 6; i++) {
    const t = new Date(agora - i * 5 * 60000);
    t.setUTCMinutes(Math.floor(t.getUTCMinutes() / 5) * 5, 0, 0);
    const p = (n: number) => String(n).padStart(2, "0");
    const nome = `RAIOS_${t.getUTCFullYear()}${p(t.getUTCMonth() + 1)}${p(t.getUTCDate())}${p(t.getUTCHours())}${p(t.getUTCMinutes())}.json`;
    try {
      const r = await fetch(`${base}/${t.getUTCFullYear()}/${p(t.getUTCMonth() + 1)}/${nome}`, { signal: AbortSignal.timeout(12000) });
      if (r.ok) return (await r.json()) as Record<string, unknown>;
    } catch { /* tenta a janela anterior */ }
  }
  return null;
}

/** Descargas sobre Juiz de Fora na janela mais recente (~5 min). Erro -> lança exceção. */
export async function buscarRaios(): Promise<Raios> {
  const d = await buscarArquivo();
  const features = (d as { features?: unknown[] })?.features;
  if (!Array.isArray(features)) throw new Error("Sem leitura do INPE");
  let descargas = 0, celulas = 0, atualizado = "";
  for (const f of features as { properties?: Record<string, unknown>; geometry?: { coordinates?: number[][][] } }[]) {
    const anel = f.geometry?.coordinates?.[0];
    if (!Array.isArray(anel) || anel.length < 3) continue;
    if (!sobreJF(anel)) continue;
    celulas += 1;
    descargas += Number(f.properties?.count ?? 0);
    atualizado = String(f.properties?.timestamp ?? atualizado);
  }
  if (!atualizado) {
    const t = new Date(Date.now() - 8 * 60000);
    atualizado = t.toISOString();
  }
  return { descargas, celulas, atualizado };
                                                                        }
