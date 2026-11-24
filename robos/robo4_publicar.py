"""ROBÔ 4: publica no site pela função pública ajf_submit (mesmas regras do formulário) e confere se a mídia abre."""
import json, os, subprocess, sys, tempfile, uuid
import common as c

AVISO = "Não verificado."


def sessao_anonima():
    d = c.http("POST", f"{c.SUPABASE_URL}/auth/v1/signup", {"apikey": c.PUBLISHABLE_KEY}, {"data": {"app": "alertajf-robo"}})
    return d["access_token"]


def descricao(it, a):
    fonte = it["autor"] + (" (Instagram)" if it["origem"] == "instagram" else "")
    return f'{a["descricao"].strip()} Fonte: {fonte}. Post original: {it["url"]} {AVISO}'[:900]


def conferir_video(path):
    url = f"{c.SUPABASE_URL}/storage/v1/object/public/relatos-midia/{path}"
    with tempfile.TemporaryDirectory() as d:
        arq = os.path.join(d, "v.mp4")
        open(arq, "wb").write(c.http("GET", url, raw=True, timeout=90))
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name", "-of", "json", arq], capture_output=True, text=True)
        s = {x["codec_type"]: x["codec_name"] for x in json.loads(r.stdout)["streams"]}
        return s.get("video") == "h264" and s.get("audio", "aac") == "aac"


def publicados_agora():
    d = c.http("POST", f"{c.SUPABASE_URL}/rest/v1/rpc/ajf_reports", {"apikey": c.PUBLISHABLE_KEY}, {})
    return d if isinstance(d, list) else []


def main():
    itens = c.fila_listar("baixado", 10)
    if not itens:
        c.log_robo("robo4_publicar", True, "nada na fila para publicar")
        return 0
    if any(i.get("midia_path") and not i["midia_path"].endswith(".jpg") for i in itens):
        import robo3_baixar
        robo3_baixar.garantir_ffmpeg()
    token = sessao_anonima()
    no_ar = publicados_agora()
    pub = falhas = desc = 0
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
            if any((r.get("street") or "").lower() == rua.lower() and (r.get("neighborhood") or "").lower() == bairro.lower() and r.get("kind") == tipo for r in no_ar):
                print("descartado:", it["post_id"], "já há pin igual no ar")
                c.fila_atualizar(it["id"], estado="descartado", motivo="já há pin igual no ar")
                desc += 1
                continue
            midia = []
            if it.get("midia_path"):
                midia = [{"path": it["midia_path"], "kind": "image" if it["midia_path"].endswith(".jpg") else "video", "credit": f'{it["autor"]} (Instagram)'[:120]}]
                if midia[0]["kind"] == "video" and not conferir_video(it["midia_path"]):  # confere a mídia ANTES de publicar
                    raise RuntimeError("vídeo não é H.264/AAC ou não abre; não publicado")
            payload = {"street": rua, "neighborhood": bairro, "kind": tipo,
                       "description": descricao(it, a), "lat": lat, "lng": lon, "observed_at": a["ocorrido_em"], "request_id": str(it["request_id"]), "media": midia}
            rid = c.http("POST", f"{c.SUPABASE_URL}/rest/v1/rpc/ajf_submit", {"apikey": c.PUBLISHABLE_KEY, "Authorization": f"Bearer {token}"}, {"payload": payload})
            c.fila_atualizar(it["id"], estado="publicado", motivo=f"id={rid}")  # marca na hora: nunca republica o mesmo item
            if not any(r.get("id") == rid for r in publicados_agora()):
                raise RuntimeError(f"enviado (id={rid}) mas não apareceu na lista pública")
            print("publicado:", it["post_id"], "id", rid)
            pub += 1
        except Exception as e:
            msg = str(e)
            if "Você já enviou" in msg or "Limite" in msg:  # duplicado/limite do site: não insistir
                c.fila_atualizar(it["id"], estado="descartado", motivo=msg[:200])
                desc += 1
            else:
                falhas += 1
                print("FALHOU:", it["post_id"], e)
                if it.get("estado") == "baixado":
                    c.fila_erro(it, e)
    c.log_robo("robo4_publicar", falhas == 0, f"{len(itens)} na fila: {pub} publicados, {falhas} falharam, {desc} descartados")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
