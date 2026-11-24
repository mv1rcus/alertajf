"""ROBÔ 1: varre os perfis de Instagram de JF, analisa com IA e enfileira o que é ocorrência real."""
import json, os, sys, datetime as dt
import common as c

try:
    import instaloader
except ImportError:
    instaloader = None


def totp(segredo, agora=None):
    """Código de 6 dígitos (RFC 6238, SHA1, 30s) a partir da seed base32. Só stdlib."""
    import base64, hmac, hashlib, struct, time
    s = segredo.strip().replace(" ", "").upper()
    chave = base64.b32decode(s + "=" * (-len(s) % 8))
    n = int((agora or time.time()) // 30)
    h = hmac.new(chave, struct.pack(">Q", n), hashlib.sha1).digest()
    o = h[-1] & 15
    return "%06d" % ((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)


def logar():
    L = instaloader.Instaloader(quiet=True, download_pictures=False, download_videos=False, save_metadata=False,
                                compress_json=False, max_connection_attempts=1, request_timeout=30)
    user, senha = os.environ.get("IG_USERNAME"), os.environ.get("IG_PASSWORD")
    if not user or not senha:
        raise RuntimeError("Faltam os secrets IG_USERNAME/IG_PASSWORD")
    sessao = os.path.join(c.AQUI, "..", ".ig-sessao")
    if os.path.exists(sessao):
        try:
            L.load_session_from_file(user, sessao)
            L.test_login()
            return L
        except Exception as e:
            print("sessão salva não serviu, logando de novo:", e)
    try:
        L.login(user, senha)
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        seed = os.environ.get("IG_TOTP_SECRET")
        if not seed:
            raise RuntimeError("Instagram pediu 2FA e falta o secret IG_TOTP_SECRET")
        L.two_factor_login(totp(seed))
    L.save_session_to_file(sessao)
    return L


def candidatos(L, perfis):
    limite = c.agora() - dt.timedelta(hours=c.JANELA_HORAS)
    for nome in perfis:
        try:
            p = instaloader.Profile.from_username(L.context, nome)
            for i, post in enumerate(p.get_posts()):
                if post.date_utc.replace(tzinfo=dt.timezone.utc) < limite and not post.is_pinned:
                    break  # posts vêm do mais novo pro mais velho
                if i >= 12:
                    break
                yield dict(origem="instagram", post_id=post.shortcode, autor=f"@{nome}",
                           url=f"https://www.instagram.com/p/{post.shortcode}/", legenda=post.caption or "",
                           publicado_em=post.date_utc.replace(tzinfo=dt.timezone.utc).isoformat(),
                           midia_url=post.video_url if post.is_video else None, eh_video=bool(post.is_video))
        except instaloader.exceptions.LoginRequiredException:
            raise
        except Exception as e:
            print(f"perfil {nome}: {e}")
    try:  # stories (alguns jornalistas postam só ali)
        ids = [instaloader.Profile.from_username(L.context, n).userid for n in perfis[:6]]
        for st in L.get_stories(ids):
            for it in st.get_items():
                if it.date_utc.replace(tzinfo=dt.timezone.utc) < limite:
                    continue
                yield dict(origem="instagram", post_id=f"story-{it.mediaid}", autor=f"@{st.owner_username} (stories)",
                           url=f"https://www.instagram.com/stories/{st.owner_username}/{it.mediaid}/", legenda=it.caption or "",
                           publicado_em=it.date_utc.replace(tzinfo=dt.timezone.utc).isoformat(),
                           midia_url=it.video_url if it.is_video else it.url, eh_video=bool(it.is_video))
    except Exception as e:
        print("stories:", e)


def main():
    if not c.esta_chovendo():
        c.log_robo("robo1_instagram", True, "sem chuva nem previsão, dormindo")
        return 0
    if instaloader is None:
        raise RuntimeError("instaloader não instalado")
    perfis = json.load(open(os.path.join(c.AQUI, "fontes.json")))["instagram"]
    try:
        L = logar()
    except Exception as e:
        c.log_robo("robo1_instagram", False, f"login do Instagram falhou: {e}")
        open(os.path.join(c.AQUI, "..", ".ig-falhou"), "w").write(str(e)[:300])
        return 0  # não derruba o fluxo; o workflow abre uma issue
    novos = analisados = 0
    for it in candidatos(L, perfis):
        try:
            if not it["legenda"].strip() and not it["eh_video"]:
                continue
            a = c.analisar(it)
            ok, motivo = c.validar_analise(a)
            it.update(analise=a, estado="analisado" if ok else "descartado", motivo=motivo or None)
            if c.fila_inserir(it):
                novos += 1
                analisados += ok
        except Exception as e:
            print("candidato falhou:", it.get("post_id"), e)
    c.log_robo("robo1_instagram", True, f"{novos} novos candidatos, {analisados} aprovados pela IA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
