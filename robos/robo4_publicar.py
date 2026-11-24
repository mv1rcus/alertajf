"""ROBÔ 4: publica no site pela função pública ajf_submit (mesmas regras do formulário) e confere se a mídia abre."""
import json, os, subprocess, sys, tempfile, time, uuid
import common as c

AVISO = "Não verificado."


def sessao_anonima():
    d = c.http("POST", f"{c.SUPABASE_URL}/auth/v1/signup", {"apikey": c.PUBLISHABLE_KEY}, {"data": {"app": "alertajf-robo"}})
    return d["access_token"]


def limpar(txt):
    """O ajf_submit recusa < e >: desfaz entidades (&lt; &amp;) e tira os sinais em vez de perder o pin."""
    import html
    return html.unescape(str(txt or "")).replace("<", "").replace(">", "")


def descricao(it, a):
    fonte = limpar(it["autor"]) + (" (Instagram)" if it["origem"] == "instagram" else "")
    return limpar(f'{limpar(a["descricao"]).strip()} Fonte: {fonte}. Post original: {it["url"]} {AVISO}')[:900]


def conferir_video(path):
    url = f"{c.SUPABASE_URL}/storage/v1/object/public/relatos-midia/{path}"
    with tempfile.TemporaryDirectory() as d:
        arq = os.path.join(d, "v.mp4")
        open(arq, "wb").write(c.http("GET", url, raw=True, timeout=90))
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name", "-of", "json", arq], capture_output=True, text=True)
        s = {x["codec_type"]: x["codec_name"] for x in json.loads(r.stdout)["streams"]}
        return s.get("video") == "h264" and s.get("audio", "aac") == "aac"


def _metros(la1, lo1, la2, lo2):
    import math
    r = 6371000
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


RAIO_DUPLICADO_M = 250  # mesmo tipo a até 250 m = mesmo fato (cada execução usa um usuário anônimo novo, o site não pega isso)


def duplicado(no_ar, rua, bairro, tipo, lat, lon):
    for r in no_ar:
        if r.get("kind") != tipo:
            continue
        if (r.get("street") or "").lower() == rua.lower() and (r.get("neighborhood") or "").lower() == bairro.lower():
            return True
        try:
            if _metros(lat, lon, float(r["lat"]), float(r["lng"])) <= RAIO_DUPLICADO_M:
                return True
        except (KeyError, TypeError, ValueError):
            pass
    return False


def publicados_agora():
    d = c.http("POST", f"{c.SUPABASE_URL}/rest/v1/rpc/ajf_reports", {"apikey": c.PUBLISHABLE_KEY}, {})
    return d if isinstance(d, list) else []


def retirar_do_ar():
    """Retira pins listados em retirar.json (duplicados/erros) marcando withdrawn pela service role. Arquivo vazio = nada a fazer."""
    try:
        ids = json.load(open(os.path.join(c.AQUI, "retirar.json")))
    except Exception:
        return
    for rid in ids:
        try:
            h = {"apikey": c.SERVICE_KEY, "Authorization": f"Bearer {c.SERVICE_KEY}", "Accept-Profile": "ajf_private", "Content-Profile": "ajf_private", "Prefer": "return=representation"}
            r = c.http("PATCH", f"{c.SUPABASE_URL}/rest/v1/reports?id=eq.{rid}", h, {"withdrawn": True})
            print("retirado do ar:", rid, "linhas:", len(r or []))
        except Exception as e:
            print("FALHOU ao retirar", rid, e)


def main():
    retirar_do_ar()
    itens = c.fila_listar("baixado", 10, "desc")
    if not itens:
        c.log_robo("robo4_publicar", True, "nada na fila para publicar")
        return 0
    if any(i.get("midia_path") and not i["midia_path"].endswith(".jpg") for i in itens):
        import robo3_baixar
        robo3_baixar.garantir_ffmpeg()
    try:
        token = sessao_anonima()
        no_ar = publicados_agora()
    except Exception as e:  # sem sessão não dá para publicar: falha visível, itens continuam na fila
        c.log_robo("robo4_publicar", False, f"{len(itens)} na fila, nada publicado: sessão/lista pública falhou ({str(e)[:120]})")
        return 1
    pub = falhas = desc = enviados = 0
    for it in itens:
        try:
            a = it["analise"]
            ok, motivo = c.validar_analise(a)  # revalida: o tempo passou desde a análise
            if not ok:
                print("descartado:", it["post_id"], motivo)
                c.fila_atualizar(it["id"], estado="descartado", motivo=motivo)
                desc += 1
                continue
            geo = c.geocodificar(a.get("rua", ""), a.get("bairro", ""))
            if not geo:
                print("descartado:", it["post_id"], "local não encontrado em JF", a.get("rua"), a.get("bairro"))
                c.fila_atualizar(it["id"], estado="descartado", motivo="local não encontrado em JF")
                desc += 1
                continue
            lat, lon, bairro = geo
            tipo = a["tipo"] if a["tipo"] != "enxurrada" else "alagamento"
            rua = a.get("rua") or bairro
            if duplicado(no_ar, rua, bairro, tipo, lat, lon):
                print("descartado:", it["post_id"], "já há pin igual no ar")
                c.fila_atualizar(it["id"], estado="descartado", motivo="já há pin igual no ar")
                desc += 1
                continue
            midia = []
            if it.get("midia_path"):
                midia = [{"path": it["midia_path"], "kind": "image" if it["midia_path"].endswith(".jpg") else "video", "credit": (f'{it["autor"]} (Instagram)' if it["origem"] == "instagram" else f'Imagem: {it["autor"]}')[:120]}]
                if midia[0]["kind"] == "video" and not conferir_video(it["midia_path"]):  # confere a mídia ANTES de publicar
                    raise RuntimeError("vídeo não é H.264/AAC ou não abre; não publicado")
            payload = {"street": limpar(rua), "neighborhood": limpar(bairro), "kind": tipo,
                       "description": descricao(it, a), "lat": lat, "lng": lon, "observed_at": a["ocorrido_em"], "request_id": str(it["request_id"]), "media": midia}
            if enviados:  # o ajf_submit aceita 1 relato por minuto por sessão: espera, nunca descarta por causa disso
                time.sleep(62)
            enviados += 1
            rid = c.http("POST", f"{c.SUPABASE_URL}/rest/v1/rpc/ajf_submit", {"apikey": c.PUBLISHABLE_KEY, "Authorization": f"Bearer {token}"}, {"payload": payload})
            c.fila_atualizar(it["id"], estado="publicado", motivo=f"id={rid}")  # marca na hora: nunca republica o mesmo item
            if not any(r.get("id") == rid for r in publicados_agora()):
                raise RuntimeError(f"enviado (id={rid}) mas não apareceu na lista pública")
            no_ar.append({"id": rid, "kind": tipo, "street": rua, "neighborhood": bairro, "lat": lat, "lng": lon})
            print("publicado:", it["post_id"], "id", rid)
            pub += 1
        except Exception as e:
            msg = str(e)
            if "Você já enviou" in msg:  # pin igual já no ar: não republicar
                c.fila_atualizar(it["id"], estado="descartado", motivo=msg[:200])
                desc += 1
            elif "Limite" in msg:  # limite de envio do site: o item continua na fila e sobe na próxima execução
                print("limite do site, item fica na fila:", it["post_id"], msg[:120])
                falhas += 1
            else:
                falhas += 1
                print("FALHOU:", it["post_id"], e)
                if it.get("estado") == "baixado":
                    c.fila_erro(it, e)
    c.log_robo("robo4_publicar", falhas == 0, f"{len(itens)} na fila: {pub} publicados, {falhas} falharam, {desc} descartados")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
