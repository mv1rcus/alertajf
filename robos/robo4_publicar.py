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


def main():
    itens = c.fila_listar("baixado", 10)
    if not itens:
        c.log_robo("robo4_publicar", True, "nada na fila para publicar")
        return 0
    token = sessao_anonima()
    pub = 0
    for it in itens:
        try:
            a = it["analise"]
            ok, motivo = c.validar_analise(a)  # revalida: o tempo passou desde a análise
            if not ok:
                print("descartado:", it["post_id"], motivo)
                c.fila_atualizar(it["id"], estado="descartado", motivo=motivo)
                continue
            geo = c.geocodificar(a.get("rua", ""), a.get("bairro", ""))
            if not geo:
                print("descartado:", it["post_id"], "local não encontrado em JF", a.get("rua"), a.get("bairro"))
                c.fila_atualizar(it["id"], estado="descartado", motivo="local não encontrado em JF")
                continue
            lat, lon, bairro = geo
            midia = []
            if it.get("midia_path"):
                midia = [{"path": it["midia_path"], "kind": "image" if it["midia_path"].endswith(".jpg") else "video", "credit": f'{it["autor"]} (Instagram)'[:120]}]
            payload = {"street": a.get("rua") or bairro, "neighborhood": bairro, "kind": a["tipo"] if a["tipo"] != "enxurrada" else "alagamento",
                       "description": descricao(it, a), "lat": lat, "lng": lon, "observed_at": a["ocorrido_em"], "request_id": str(it["request_id"]), "media": midia}
            c.http("POST", f"{c.SUPABASE_URL}/rest/v1/rpc/ajf_submit", {"apikey": c.PUBLISHABLE_KEY, "Authorization": f"Bearer {token}"}, {"payload": payload})
            if midia and midia[0]["kind"] == "video" and not conferir_video(it["midia_path"]):
                raise RuntimeError("publicado, mas o vídeo servido não é H.264/AAC")
            c.fila_atualizar(it["id"], estado="publicado", motivo=None)
            pub += 1
        except Exception as e:
            msg = str(e)
            if "Você já enviou" in msg or "Limite" in msg:  # duplicado/limite do site: não insistir
                c.fila_atualizar(it["id"], estado="descartado", motivo=msg[:200])
            else:
                print("falhou:", it["post_id"], e)
                c.fila_erro(it, e)
    c.log_robo("robo4_publicar", True, f"{pub}/{len(itens)} publicados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
