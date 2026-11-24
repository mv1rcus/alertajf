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
            if L.test_login():  # test_login devolve None (não levanta erro) quando a sessão caiu
                return L
            print("sessão salva não está mais logada, logando de novo")
            os.remove(sessao)
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


ERROS_LOGIN = []


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
            if "logged out" in str(e) or "login" in str(e).lower():
                ERROS_LOGIN.append(nome)
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


# ---- Descoberta de perfis novos: só ADICIONA à varredura. Nunca segue ninguém (decisão do Marcus). ----
ESTADO = os.path.join(c.AQUI, "..", ".ig-sessao", "estado.json")  # fica no cache do Actions, junto da sessão
TEMA = ("notícia", "noticia", "jornal", "clima", "tempo", "chuva", "trânsito", "transito", "alagamento",
        "defesa civil", "ocorrência", "ocorrencia", "plantão", "plantao", "informa", "agora", "imprensa", "tv")
MAX_NOVOS_DIA = 3


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


def descobrir(L, itens):
    import re
    hoje = c.agora().date().isoformat()
    e = ler_estado()
    if e.get("dia") != hoje:
        e["dia"], e["novos"] = hoje, 0
    conhecidos = {n.lower() for n in json.load(open(os.path.join(c.AQUI, "fontes.json")))["instagram"]}
    conhecidos |= {n.lower() for n in e.get("extras", [])} | {n.lower() for n in e.get("avaliados", [])}
    mencoes = []
    for it in itens:
        for m in re.findall(r"@([A-Za-z0-9._]{3,30})", it.get("legenda") or ""):
            m = m.strip(".").lower()
            if m not in conhecidos and m not in mencoes:
                mencoes.append(m)
    for nome in mencoes[:4]:  # no máx. 4 consultas de perfil por ciclo
        if e["novos"] >= MAX_NOVOS_DIA:
            break
        time.sleep(random.uniform(3, 6))
        e.setdefault("avaliados", []).append(nome)
        try:
            p = instaloader.Profile.from_username(L.context, nome)
            if p.is_private or not eh_de_jf_e_do_tema(p):
                continue  # privado não dá pra ler sem seguir, e não seguimos
            e["novos"] += 1
            e.setdefault("extras", []).append(nome)
            c.log_robo("robo1_instagram", True, f"perfil novo adicionado à varredura: @{nome}")
        except Exception as ex:
            print(f"descoberta @{nome}: {ex}")
            break  # qualquer erro: para por este ciclo
    gravar_estado(e)


# ---- Backend "app" (API móvel via instagrapi): o scraping web do instaloader leva "deslogado" em IP de servidor ----
APP_DIR = os.path.join(c.AQUI, "..", ".ig-sessao")
APP_SESSAO = os.path.join(APP_DIR, "app.json")
APP_BLOQUEIO = os.path.join(APP_DIR, "bloqueio_app")  # guarda o epoch até quando não tentar de novo


TAG_ATUAL = ""


class FalhaApp(Exception):
    pass


def _novo_cliente():
    from instagrapi import Client
    cl = Client()
    cl.delay_range = [2, 5]
    cl.request_timeout = 30
    return cl


def logar_app(tag=""):
    try:
        import instagrapi  # noqa
    except ImportError:  # o workflow só instala instaloader; instala aqui pra não precisar mexer no YAML
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "instagrapi"], check=True)
    import instagrapi.exceptions as ex
    os.makedirs(APP_DIR, exist_ok=True)
    if os.path.exists(APP_BLOQUEIO):
        try:
            ate, _, tag_b = open(APP_BLOQUEIO).read().strip().partition("|")
            ate = float(ate)
        except Exception:
            ate, tag_b = 0, ""
        if ate > time.time() and tag_b == tag:  # trocar "instagram_liberar" em fontes.json libera uma nova tentativa
            raise FalhaApp("em espera por falha anterior (%d min restantes)" % ((ate - time.time()) // 60 + 1))
    user, senha, seed = os.environ.get("IG_USERNAME"), os.environ.get("IG_PASSWORD"), os.environ.get("IG_TOTP_SECRET")
    if not user or not senha:
        raise FalhaApp("faltam IG_USERNAME/IG_PASSWORD")
    cl = _novo_cliente()
    if os.path.exists(APP_SESSAO):
        try:
            cl.load_settings(APP_SESSAO)  # traz o MESMO aparelho (uuids) e a sessão, se houver
        except Exception:
            cl = _novo_cliente()
        if cl.authorization_data:
            try:
                cl.get_timeline_feed()  # chamada leve pra ver se a sessão ainda vale
                print("sessão do app reaproveitada")
                return cl
            except Exception as e:
                print("sessão do app não serviu:", type(e).__name__)
    cl.dump_settings(APP_SESSAO)  # guarda o aparelho ANTES do login: o que o Marcus aprovar vale nas próximas vezes
    erro = None
    for tentativa in (1, 2):
        try:
            cl.login(user, senha, verification_code=totp(seed) if seed else "")
            erro = None
            break
        except Exception as e:
            erro = e
            cl.dump_settings(APP_SESSAO)
            # Só na 1ª falha: pode ser a telinha "aprovar dispositivo" no celular. Espera 3 min e tenta de novo, mesmo aparelho.
            if tentativa == 1 and "Bloks" in str(e) or (tentativa == 1 and type(e).__name__ == "TwoFactorRequired"):
                print("login pendente (provável aprovação de dispositivo), espera 3 min e tenta uma última vez")
                time.sleep(180)
                continue
            break
    if erro is not None:
        open(APP_BLOQUEIO, "w").write("%s|%s" % (time.time() + 24 * 3600, tag))
        raise FalhaApp("login do app falhou (%s): %s" % (type(erro).__name__, str(erro)[:150]))
    cl.dump_settings(APP_SESSAO)
    return cl


def candidatos_app(cl, perfis):
    import instagrapi.exceptions as ex
    limite = c.agora() - dt.timedelta(hours=c.JANELA_HORAS)
    for nome in perfis:
        time.sleep(random.uniform(2, 5))
        try:
            u = cl.user_info_by_username_v1(nome)
            if u.is_private:
                print(f"perfil {nome}: privado, pulando")
                continue
            for m in cl.user_medias_v1(int(u.pk), amount=12):
                data = m.taken_at.astimezone(dt.timezone.utc) if m.taken_at.tzinfo else m.taken_at.replace(tzinfo=dt.timezone.utc)
                if data < limite:
                    continue
                video = m.media_type == 2
                yield dict(origem="instagram", post_id=m.code, autor=f"@{nome}",
                           url=f"https://www.instagram.com/p/{m.code}/", legenda=m.caption_text or "",
                           publicado_em=data.isoformat(), midia_url=str(m.video_url) if video and m.video_url else None,
                           eh_video=bool(video))
        except (ex.ChallengeRequired, ex.FeedbackRequired, ex.LoginRequired, ex.ChallengeError) as e:
            open(APP_BLOQUEIO, "w").write("%s|%s" % (time.time() + 24 * 3600, TAG_ATUAL))
            raise FalhaApp("Instagram barrou a conta no meio da leitura (%s)" % type(e).__name__)
        except Exception as e:
            print(f"perfil {nome}: {type(e).__name__}: {str(e)[:120]}")


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
    if cfg.get("instagram_backend", "app") == "app":
        return main_app(cfg, perfis)
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
    if perfis and len(ERROS_LOGIN) >= len(perfis):  # nenhum perfil leu: sessão sem permissão de leitura
        try:
            os.remove(os.path.join(c.AQUI, "..", ".ig-sessao", "sessao"))
            open(os.path.join(c.AQUI, "..", ".ig-sessao", "bloqueio"), "w").write(str(time.time()))
        except Exception:
            pass
        msg = "Instagram recusou a leitura de todos os %d perfis (sessão deslogada)" % len(perfis)
        c.log_robo("robo1_instagram", False, msg)
        open(os.path.join(c.AQUI, "..", ".ig-falhou"), "w").write(msg)
        return 0
    try:
        descobrir(L, vistos)
    except Exception as ex:
        print("descoberta:", ex)
    c.log_robo("robo1_instagram", True, f"{novos} novos candidatos, {analisados} aprovados pela IA")
    return 0



def main_app(cfg, perfis):
    global TAG_ATUAL
    TAG_ATUAL = cfg.get("instagram_liberar", "")
    try:
        cl = logar_app(cfg.get("instagram_liberar", ""))
    except FalhaApp as e:
        c.log_robo("robo1_instagram", False, f"Instagram (app): {e}")
        open(os.path.join(c.AQUI, "..", ".ig-falhou"), "w").write(str(e)[:300])
        return 0
    novos = analisados = lidos = 0
    try:
        for it in candidatos_app(cl, perfis):
            lidos += 1
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
    except FalhaApp as e:
        c.log_robo("robo1_instagram", False, f"Instagram (app): {e}")
        open(os.path.join(c.AQUI, "..", ".ig-falhou"), "w").write(str(e)[:300])
        return 0
    c.log_robo("robo1_instagram", True, f"app: {lidos} posts recentes lidos, {novos} novos candidatos, {analisados} aprovados pela IA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
