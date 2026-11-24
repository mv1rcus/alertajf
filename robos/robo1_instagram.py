"""ROBÔ 1: varre os perfis de Instagram de JF, analisa com IA e enfileira o que é ocorrência real."""
import json, os, sys, time, random, datetime as dt
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
    pasta = os.path.join(c.AQUI, "..", ".ig-sessao")  # pasta guardada no cache do Actions entre runs
    if os.path.isfile(pasta):  # formato antigo (arquivo): troca por pasta
        os.remove(pasta)
    os.makedirs(pasta, exist_ok=True)
    sessao = os.path.join(pasta, "sessao")
    bloqueio = os.path.join(pasta, "bloqueio")
    if os.path.exists(sessao):
        try:
            L.load_session_from_file(user, sessao)
            L.test_login()
            return L
        except Exception as e:
            print("sessão salva não serviu, logando de novo:", e)
    # Login completo é raro: no máximo 1 tentativa por hora (depois de falhar, espera, sem martelar).
    if os.path.exists(bloqueio):
        try:
            falta = 3600 - (time.time() - float(open(bloqueio).read().strip()))
        except Exception:
            falta = 0
        if falta > 0:
            raise RuntimeError("login em espera depois de falha recente (%d min restantes)" % (falta // 60 + 1))
    try:
        try:
            L.login(user, senha)
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            seed = os.environ.get("IG_TOTP_SECRET")
            if not seed:
                raise RuntimeError("Instagram pediu 2FA e falta o secret IG_TOTP_SECRET")
            L.two_factor_login(totp(seed))
    except Exception:
        open(bloqueio, "w").write(str(time.time()))
        raise
    if os.path.exists(bloqueio):
        os.remove(bloqueio)
    L.save_session_to_file(sessao)
    return L


def candidatos(L, perfis):
    limite = c.agora() - dt.timedelta(hours=c.JANELA_HORAS)
    for nome in perfis:
        time.sleep(random.uniform(2, 5))  # respiro entre perfis, pra o Instagram não estranhar
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


# ---- Descoberta de perfis novos (autorizado pelo Marcus): segue no máximo 3 por dia, sem retry ----
ESTADO = os.path.join(c.AQUI, "..", ".ig-sessao", "estado.json")  # fica no cache do Actions, junto da sessão
TEMA = ("notícia", "noticia", "jornal", "clima", "tempo", "chuva", "trânsito", "transito", "alagamento",
        "defesa civil", "ocorrência", "ocorrencia", "plantão", "plantao", "informa", "agora", "imprensa", "tv")
MAX_FOLLOWS_DIA = 3
PAUSA_FOLLOW_MIN = 5


def ler_estado():
    try:
        return json.load(open(ESTADO))
    except Exception:
        return {}


def gravar_estado(e):
    os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
    json.dump(e, open(ESTADO, "w"))


def eh_de_jf_e_do_tema(p):
    texto = " ".join([p.username or "", p.full_name or "", p.biography or ""]).lower()
    import re
    de_jf = "juiz de fora" in texto or "juizdefora" in texto or bool(re.search(r"(^|[^a-z])jf|jf($|[^a-z])", texto))
    return de_jf and any(t in texto for t in TEMA)


def seguir(L, p):
    """Segue via sessão logada. Endpoint não oficial: qualquer recusa vira parada do dia."""
    ctx = L.context
    r = ctx._session.post(f"https://www.instagram.com/api/v1/friendships/create/{p.userid}/",
                          headers={"x-csrftoken": ctx._session.cookies.get("csrftoken", ""), "x-ig-app-id": "936619743392459",
                                   "x-requested-with": "XMLHttpRequest", "referer": f"https://www.instagram.com/{p.username}/"},
                          timeout=30)
    if r.status_code != 200 or '"status":"ok"' not in r.text.replace(" ", ""):
        raise RuntimeError(f"follow recusado (HTTP {r.status_code})")


def descobrir(L, itens):
    import re
    hoje = c.agora().date().isoformat()
    e = ler_estado()
    if e.get("dia") != hoje:
        e["dia"], e["follows"] = hoje, 0
    if e.get("parado_ate_dia") == hoje:
        return
    conhecidos = {n.lower() for n in json.load(open(os.path.join(c.AQUI, "fontes.json")))["instagram"]}
    conhecidos |= {n.lower() for n in e.get("extras", [])} | {n.lower() for n in e.get("avaliados", [])}
    mencoes = []
    for it in itens:
        for m in re.findall(r"@([A-Za-z0-9._]{3,30})", it.get("legenda") or ""):
            m = m.strip(".").lower()
            if m not in conhecidos and m not in mencoes:
                mencoes.append(m)
    pendente = e.get("pendente")
    if pendente and time.time() - pendente.get("ts", 0) > 7 * 86400:
        e.pop("pendente")
        pendente = None
    for nome in mencoes[:4]:  # no máx. 4 consultas por ciclo
        if e["follows"] >= MAX_FOLLOWS_DIA:
            break
        if time.time() - e.get("ultimo_follow", 0) < PAUSA_FOLLOW_MIN * 60:
            break
        time.sleep(random.uniform(3, 6))
        e.setdefault("avaliados", []).append(nome)
        try:
            p = instaloader.Profile.from_username(L.context, nome)
            if not eh_de_jf_e_do_tema(p):
                continue
            if p.is_private and pendente:
                continue  # no máx. 1 solicitação pendente por vez
            seguir(L, p)
            e["follows"] += 1
            e["ultimo_follow"] = time.time()
            e.setdefault("extras", []).append(nome)
            if p.is_private:
                e["pendente"] = pendente = {"nome": nome, "ts": time.time()}
            c.log_robo("robo1_instagram", True, f"perfil novo seguido: @{nome}")
        except Exception as ex:
            e["parado_ate_dia"] = hoje  # recusou ou erro: para o dia, sem retry
            c.log_robo("robo1_instagram", False, f"descoberta parou hoje ({nome}): {str(ex)[:120]}")
            break
    gravar_estado(e)


def main():
    if not c.esta_chovendo():
        c.log_robo("robo1_instagram", True, "sem chuva nem previsão, dormindo")
        return 0
    if instaloader is None:
        raise RuntimeError("instaloader não instalado")
    cfg = json.load(open(os.path.join(c.AQUI, "fontes.json")))
    if not cfg.get("instagram_ativo", True):
        c.log_robo("robo1_instagram", True, "pausado (instagram_ativo=false em fontes.json): login recusado, sem insistir")
        return 0
    perfis = list(cfg["instagram"])
    perfis += [n for n in ler_estado().get("extras", []) if n not in perfis]
    try:
        L = logar()
    except Exception as e:
        c.log_robo("robo1_instagram", False, f"login do Instagram falhou: {e}")
        open(os.path.join(c.AQUI, "..", ".ig-falhou"), "w").write(str(e)[:300])
        return 0  # não derruba o fluxo; o workflow abre uma issue
    novos = analisados = 0
    vistos = []
    for it in candidatos(L, perfis):
        vistos.append(it)
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
    try:
        descobrir(L, vistos)
    except Exception as ex:
        print("descoberta:", ex)
    c.log_robo("robo1_instagram", True, f"{novos} novos candidatos, {analisados} aprovados pela IA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
