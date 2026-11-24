"""ROBÔ 3: baixa o vídeo/foto dos itens aprovados e converte tudo para H.264/AAC mp4 (toca em iPhone, Android e desktop)."""
import datetime as dt, json, os, re, subprocess, sys, tempfile
import common as c

TETO = 7 * 1024 * 1024  # mesmo teto de vídeo do formulário do site


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def baixar_ig(item, destino):
    """Baixa com a URL fresca guardada pelo Robô 1; se expirou, tenta de novo pelo yt-dlp."""
    if item.get("midia_url"):
        try:
            open(destino, "wb").write(c.http("GET", item["midia_url"], raw=True, timeout=90))
            return True
        except Exception as e:
            print("URL direta falhou:", e)
    r = sh(["yt-dlp", "-q", "--no-warnings", "-o", destino, "--merge-output-format", "mp4", item["url"]])
    return r.returncode == 0 and os.path.exists(destino)


def converter(origem, destino):
    # H.264 (perfil main, yuv420p) + AAC, moov no começo, máx. 720p, tamanho dentro do teto
    for crf in (26, 30, 34):
        r = sh(["ffmpeg", "-y", "-loglevel", "error", "-i", origem, "-vf", "scale='min(720,iw)':-2", "-c:v", "libx264", "-profile:v", "main",
                "-pix_fmt", "yuv420p", "-crf", str(crf), "-preset", "veryfast", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-t", "60", destino])
        if r.returncode == 0 and os.path.getsize(destino) <= TETO:
            return True
    return False


def codec_ok(arq):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name", "-of", "json", arq])
    try:
        s = {x["codec_type"]: x["codec_name"] for x in json.loads(r.stdout)["streams"]}
    except Exception:
        return False
    return s.get("video") == "h264" and s.get("audio", "aac") == "aac"


def garantir_ffmpeg():
    """A imagem nova do runner (ubuntu 26) veio sem ffmpeg: instala na hora se faltar."""
    import shutil
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    sh(["sudo", "apt-get", "update", "-qq"])
    r = sh(["sudo", "apt-get", "install", "-y", "-qq", "ffmpeg"])
    print("ffmpeg instalado" if r.returncode == 0 else "ffmpeg não instalou: " + r.stderr[-200:])


def main():
    todos = c.fila_listar("analisado", 40, "desc")  # mais novos primeiro: na tempestade o fato recente vale mais que o antigo
    itens = []
    for it in todos:
        try:
            t = dt.datetime.fromisoformat(it["analise"]["ocorrido_em"].replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            if t < c.agora() - dt.timedelta(hours=c.JANELA_HORAS):
                c.fila_atualizar(it["id"], estado="descartado", motivo="fora da janela de 2h (descartado antes de baixar)")
                continue
        except Exception:
            pass
        itens.append(it)
    itens = itens[:10]
    if not itens:
        c.log_robo("robo3_baixar", True, "nada na fila para baixar")
        return 0
    if any((i["origem"] == "instagram" and i["eh_video"]) or (i["origem"] == "noticias" and i.get("midia_url")) for i in itens):
        garantir_ffmpeg()
    ok_n = 0
    for it in itens:
        try:
            if it["origem"] == "noticias" and it.get("midia_url"):
                # notícia de RSS local: baixa a imagem da matéria, converte para JPEG (ffmpeg) e serve do nosso Storage
                path = None
                try:
                    url_img = it["midia_url"]
                    img = b""
                    grande = re.sub(r"-\d+x\d+(\.\w+)(\?.*)?$", r"\1", url_img)  # WordPress serve miniatura 150x150; o arquivo original não tem o sufixo
                    for cand in ([grande, url_img] if grande != url_img else [url_img]):
                        try:
                            img = c.http("GET", cand, raw=True, timeout=60)
                            if len(img) > 2000:
                                break
                        except Exception:
                            img = b""
                    if len(img) > 2000:
                        with tempfile.TemporaryDirectory() as d:
                            a, b = os.path.join(d, "in"), os.path.join(d, "out.jpg")
                            open(a, "wb").write(img)
                            r = sh(["ffmpeg", "-y", "-loglevel", "error", "-i", a, "-vf", "scale='min(1280,iw)':-2", "-q:v", "4", "-frames:v", "1", b])
                            if r.returncode == 0 and 2000 < os.path.getsize(b) <= 6 * 1024 * 1024:
                                jpg = open(b, "rb").read()
                                if jpg[:3] == b"\xff\xd8\xff":
                                    path = f"r/{it['request_id']}-1.jpg"
                                    c.http("POST", f"{c.SUPABASE_URL}/storage/v1/object/relatos-midia/{path}",
                                           {"apikey": c.SERVICE_KEY, "Authorization": f"Bearer {c.SERVICE_KEY}", "Content-Type": "image/jpeg", "x-upsert": "true"}, jpg, timeout=60)
                except Exception as e:
                    print("imagem da notícia não baixada, publica sem imagem:", it["post_id"], e)
                    path = None
                c.fila_atualizar(it["id"], estado="baixado", midia_path=path)
                ok_n += 1
                continue
            if it["origem"] != "instagram":
                c.fila_atualizar(it["id"], estado="baixado", midia_path=None)
                ok_n += 1
                continue
            if not it["eh_video"]:
                # foto: baixa a miniatura agora (o link do Instagram expira), guarda no nosso Storage e serve do nosso domínio
                path = None
                if it.get("midia_url"):
                    try:
                        img = c.http("GET", it["midia_url"], raw=True, timeout=60)
                        if 2000 < len(img) <= 6 * 1024 * 1024 and img[:3] == b"\xff\xd8\xff":
                            path = f"r/{it['request_id']}-1.jpg"
                            c.http("POST", f"{c.SUPABASE_URL}/storage/v1/object/relatos-midia/{path}",
                                   {"apikey": c.SERVICE_KEY, "Authorization": f"Bearer {c.SERVICE_KEY}", "Content-Type": "image/jpeg", "x-upsert": "true"}, img, timeout=60)
                    except Exception as e:
                        print("foto não baixada, publica sem foto:", it["post_id"], e)
                        path = None
                c.fila_atualizar(it["id"], estado="baixado", midia_path=path)
                ok_n += 1
                continue
            with tempfile.TemporaryDirectory() as d:
                bruto, final = os.path.join(d, "bruto.mp4"), os.path.join(d, "final.mp4")
                if not baixar_ig(it, bruto):
                    raise RuntimeError("download falhou")
                if not converter(bruto, final) or not codec_ok(final):
                    raise RuntimeError("conversão H.264/AAC falhou")
                path = f"r/{it['request_id']}-1.mp4"
                c.http("POST", f"{c.SUPABASE_URL}/storage/v1/object/relatos-midia/{path}",
                       {"apikey": c.SERVICE_KEY, "Authorization": f"Bearer {c.SERVICE_KEY}", "Content-Type": "video/mp4", "x-upsert": "true"},
                       open(final, "rb").read(), timeout=120)
                c.fila_atualizar(it["id"], estado="baixado", midia_path=path)
                ok_n += 1
        except Exception as e:
            print("falhou:", it["post_id"], e)
            c.fila_erro(it, e)
    c.log_robo("robo3_baixar", True, f"{ok_n}/{len(itens)} itens baixados e convertidos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
