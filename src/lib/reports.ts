// Only the public project URL and publishable key belong here. No service_role key.
import { projectUrl, publishableKey } from './reports-config';
export type CommunityReport = { id: string; street: string; neighborhood: string; kind: 'alagamento'|'interdicao'|'deslizamento'; description: string; lat: number; lng: number; observed_at: string; expires_at: string; status: 'community'; source: 'citizen'; seen_count: number };
type Session = { access_token: string; refresh_token: string; expires_at: number };
const storageKey = 'alertajf-community-session-v1';
let pendingSession: Promise<string> | null = null;
export class ReportError extends Error {}
async function request(path: string, body: unknown, token?: string) {
  let r: Response;
  try { r = await fetch(`${projectUrl}${path}`, { method: 'POST', headers: { apikey: publishableKey, 'Content-Type': 'application/json', ...(token ? {Authorization: `Bearer ${token}`} : {}) }, body: JSON.stringify(body), signal: AbortSignal.timeout(15000) }); }
  catch { throw new ReportError('Não foi possível confirmar a resposta. Atualize a lista antes de tentar de novo.'); }
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    const msg = typeof data?.message === 'string' ? data.message : '';
    if (r.status === 429) throw new ReportError('Muitas tentativas. Aguarde alguns minutos.');
    if (msg.startsWith('Limite') || msg.startsWith('Você já') || msg.startsWith('Não é possível') || msg.startsWith('Relato indisponível') || msg.startsWith('Observação deve')) throw new ReportError(msg);
    throw new ReportError('O serviço não confirmou a operação. Atualize a lista e tente mais tarde.');
  }
  return data;
}
async function obtainSession(): Promise<string> {
  let saved: Session | null = null;
  try { saved = JSON.parse(localStorage.getItem(storageKey) || 'null'); } catch { /* disabled storage or invalid data */ }
  if (saved?.access_token && saved.expires_at > Date.now()/1000 + 60) return saved.access_token;
  const data = saved?.refresh_token
    ? await request('/auth/v1/token?grant_type=refresh_token', {refresh_token: saved.refresh_token})
    : await request('/auth/v1/signup', {data: {app: 'alertajf'}});
  if (!data?.access_token || !data?.refresh_token) throw new ReportError('Não foi possível iniciar a sessão anônima. Tente mais tarde.');
  const session: Session = {access_token: data.access_token, refresh_token: data.refresh_token, expires_at: data.expires_at || Date.now()/1000 + data.expires_in};
  try { localStorage.setItem(storageKey, JSON.stringify(session)); }
  catch { throw new ReportError('Permita o armazenamento local deste site para manter seu limite de envios e apoios.'); }
  return session.access_token;
}
function session() {
  if (!pendingSession) pendingSession = obtainSession().finally(() => {pendingSession = null;});
  return pendingSession;
}
export async function loadCommunityReports(): Promise<CommunityReport[]> {
  const data = await request('/rest/v1/rpc/ajf_reports', {});
  if (!Array.isArray(data)) throw new ReportError('Resposta de relatos inválida.');
  return data;
}
export async function submitCommunityReport(payload: Record<string, unknown>) {
  return request('/rest/v1/rpc/ajf_submit', {payload}, await session());
}
export async function reactToCommunityReport(reportId: string, reaction: 'seen'|'flag') {
  return request('/rest/v1/rpc/ajf_react', {report_id: reportId, reaction}, await session());
}

export async function withdrawCommunityReport(reportId: string) {
 return request("/rest/v1/rpc/ajf_withdraw", {report_id: reportId}, await session());
}
