"""ROBÔ 1: varre os perfis de Instagram de JF, analisa com IA e enfileira o que é ocorrência real."""
import json, os, sys, time, random, datetime as dt, urllib.request, urllib.error, urllib.parse
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


# ---- Backend "browser": Chromium de verdade (Playwright) com sessão persistida. Imita o login que funciona no navegador. ----
WEB_ESTADO = os.path.join(APP_DIR, "web_state.json")
WEB_BLOQUEIO = os.path.join(APP_DIR, "bloqueio_web")  # "epoch|tag"
IG_APP_ID = "936619743392459"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "playwright"], check=True)
        from playwright.sync_api import sync_playwright
    return sync_playwright


def _instalar_chromium():
    import subprocess
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _logado(page):
    try:
        return any(ck["name"] == "ds_user_id" for ck in page.context.cookies("https://www.instagram.com"))
    except Exception:
        return False


def _checa_bloqueio(arq, tag):
    if os.path.exists(arq):
        try:
            ate, _, tag_b = open(arq).read().strip().partition("|")
            if float(ate) > time.time() and tag_b == tag:
                raise FalhaApp("em espera por falha anterior (%d min restantes)" % ((float(ate) - time.time()) // 60 + 1))
        except ValueError:
            pass


def _login_navegador(page, user, senha, seed):
    import re
    page.goto("https://www.instagram.com/accounts/login/?hl=en", wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(2500)
    for txt in ("Allow all cookies", "Allow essential and optional cookies", "Decline optional cookies"):
        b = page.get_by_role("button", name=txt)
        if b.count():
            b.first.click()
            page.wait_for_timeout(800)
            break
    campo_u = page.locator('input[name="username"]')
    if not campo_u.count():
        campo_u = page.get_by_role("textbox", name=re.compile("username|email", re.I))
    campo_s = page.locator('input[name="password"]')
    if not campo_s.count():
        campo_s = page.get_by_role("textbox", name=re.compile("password", re.I))
    campo_u.first.fill(user)
    page.wait_for_timeout(random.randint(500, 1200))
    campo_s.first.fill(senha)
    page.wait_for_timeout(random.randint(500, 1200))
    page.get_by_role("button", name=re.compile(r"^log in$", re.I)).first.click()
    page.wait_for_timeout(7000)
    if "two_step" in page.url or "two_factor" in page.url or page.get_by_text(re.compile("authentication app", re.I)).count():
        if not seed:
            raise FalhaApp("pediu 2FA e falta IG_TOTP_SECRET")
        cod = page.locator('input[name="verificationCode"]')
        if not cod.count():
            cod = page.get_by_role("textbox", name=re.compile("code", re.I))
        cod.first.fill(totp(seed))
        page.wait_for_timeout(600)
        page.get_by_role("button", name=re.compile("^(continue|confirm)$", re.I)).first.click()
        page.wait_for_timeout(8000)
    corpo = ""
    try:
        corpo = page.inner_text("body")[:600].lower()
    except Exception:
        pass
    if not _logado(page):
        if "challenge" in page.url or "suspicious" in corpo or "notification" in corpo or "another device" in corpo:
            raise FalhaApp("Instagram pediu aprovação de dispositivo/desafio (%s)" % page.url.split("?")[0][-60:])
        raise FalhaApp("login pelo navegador não completou (%s)" % page.url.split("?")[0][-60:])


def _perfil_web(page, nome):
    r = page.evaluate("""async (a) => {
        const r = await fetch('/api/v1/users/web_profile_info/?username=' + a.nome,
            {headers: {'x-ig-app-id': a.app, 'x-requested-with': 'XMLHttpRequest'}, credentials: 'include'});
        const t = await r.text();
        return {status: r.status, body: t.slice(0, 400000)};
    }""", {"nome": nome, "app": IG_APP_ID})
    if r["status"] in (401, 403) or "login_required" in r["body"][:300]:
        raise PermissionError("sessão sem permissão de leitura (HTTP %s)" % r["status"])
    if r["status"] != 200:
        raise RuntimeError("HTTP %s" % r["status"])
    return json.loads(r["body"])["data"]["user"]


def itens_de_perfil(u, nome, limite):
    midia = (u.get("edge_owner_to_timeline_media") or {}).get("edges", [])
    for e in midia[:12]:
        n = e["node"]
        data = dt.datetime.fromtimestamp(n["taken_at_timestamp"], dt.timezone.utc)
        if data < limite:
            continue
        leg = ((n.get("edge_media_to_caption") or {}).get("edges") or [{}])[0].get("node", {}).get("text", "")
        video = bool(n.get("is_video"))
        yield dict(origem="instagram", post_id=n["shortcode"], autor=f"@{nome}",
                   url=f"https://www.instagram.com/p/{n['shortcode']}/", legenda=leg or "",
                   publicado_em=data.isoformat(), midia_url=n.get("video_url") if video else None, eh_video=video)


def main_browser(cfg, perfis):
    tag = cfg.get("instagram_liberar", "")
    os.makedirs(APP_DIR, exist_ok=True)
    user, senha, seed = os.environ.get("IG_USERNAME"), os.environ.get("IG_PASSWORD"), os.environ.get("IG_TOTP_SECRET")

    def falha(msg, horas=24):
        open(WEB_BLOQUEIO, "w").write("%s|%s" % (time.time() + horas * 3600, tag))
        c.log_robo("robo1_instagram", False, f"Instagram (navegador): {msg}")
        open(os.path.join(c.AQUI, "..", ".ig-falhou"), "w").write(msg[:300])
        return 0

    try:
        _checa_bloqueio(WEB_BLOQUEIO, tag)
        if not user or not senha:
            raise FalhaApp("faltam IG_USERNAME/IG_PASSWORD")
    except FalhaApp as e:
        c.log_robo("robo1_instagram", False, f"Instagram (navegador): {e}")
        open(os.path.join(c.AQUI, "..", ".ig-falhou"), "w").write(str(e)[:300])
        return 0
    try:
        sync_playwright = _playwright()
        _instalar_chromium()
    except Exception as e:
        return falha("não consegui instalar o navegador (%s)" % type(e).__name__, horas=1)
    limite = c.agora() - dt.timedelta(hours=c.JANELA_HORAS)
    novos = analisados = lidos = falhas = 0
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        kw = dict(user_agent=UA, locale="en-US", timezone_id="America/Sao_Paulo", viewport={"width": 1366, "height": 800})
        if os.path.exists(WEB_ESTADO):
            kw["storage_state"] = WEB_ESTADO
        ctx = br.new_context(**kw)
        page = ctx.new_page()
        try:
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            if _logado(page):
                print("sessão do navegador reaproveitada")
            else:
                print("sem sessão válida, login completo (única tentativa)")
                try:
                    _login_navegador(page, user, senha, seed)
                except FalhaApp as e:
                    br.close()
                    return falha(str(e))
                except Exception as e:
                    br.close()
                    return falha("erro no login pelo navegador: %s: %s" % (type(e).__name__, str(e)[:120]))
                ctx.storage_state(path=WEB_ESTADO)
                print("login ok, sessão salva")
            for nome in perfis:
                time.sleep(random.uniform(2, 5))
                try:
                    u = _perfil_web(page, nome)
                except PermissionError as e:
                    br.close()
                    try:
                        os.remove(WEB_ESTADO)
                    except OSError:
                        pass
                    return falha(str(e), horas=1)
                except Exception as e:
                    falhas += 1
                    print(f"perfil {nome}: {type(e).__name__}: {str(e)[:100]}")
                    continue
                if u.get("is_private"):
                    continue
                for it in itens_de_perfil(u, nome, limite):
                    lidos += 1
                    try:
                        if not it["legenda"].strip() and not it["eh_video"]:
                            continue
                        if c.ja_na_fila(it):
                            continue
                        a = c.analisar(it)
                        ok, motivo = c.validar_analise(a)
                        it.update(analise=a, estado="analisado" if ok else "descartado", motivo=motivo or None)
                        if c.fila_inserir(it):
                            novos += 1
                            analisados += ok
                    except Exception as e:
                        print("candidato falhou:", it.get("post_id"), e)
            ctx.storage_state(path=WEB_ESTADO)
        finally:
            try:
                br.close()
            except Exception:
                pass
    if perfis and falhas >= len(perfis):
        return falha("nenhum perfil pôde ser lido (%d falhas)" % falhas, horas=1)
    c.log_robo("robo1_instagram", True, f"navegador: {len(perfis) - falhas} perfis lidos, {lidos} posts recentes, {novos} novos candidatos, {analisados} aprovados pela IA")
    return 0


SERV_USO = os.path.join(APP_DIR, "servicos_uso.json")


def _uso():
    """Contadores de cota: o banco manda (o cache do Actions zera quando o job falha); o arquivo é só reserva."""
    v = c.estado_ler("robo1_uso")
    if isinstance(v, dict) and v:
        return v
    try:
        return json.load(open(SERV_USO))
    except Exception:
        return {}


def _salvar_uso(u):
    os.makedirs(APP_DIR, exist_ok=True)
    json.dump(u, open(SERV_USO, "w"))
    c.estado_gravar("robo1_uso", u)


def _post_json(url, headers, body=None, timeout=150):
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET",
                                 headers=dict(headers, **({"Content-Type": "application/json"} if body is not None else {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _quando(v):
    """Data do post em qualquer formato dos provedores: ISO, epoch em segundos ou em milissegundos (número ou texto)."""
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().replace(".", "", 1).isdigit()):
        x = float(v)
        if x > 1e11:  # milissegundos
            x /= 1000
        return dt.datetime.fromtimestamp(x, dt.timezone.utc)
    d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _link_post(codigo, nome):
    """Link do post: shortcode do Instagram (letras, números, _ e -). Id numérico não abre em /p/, então cai pro perfil."""
    cod = str(codigo or "")
    if cod and not cod.isdigit():
        return f"https://www.instagram.com/p/{cod}/"
    return f"https://www.instagram.com/{nome}/"


def _ler_scrappa(nome, chave):
    d = _post_json("https://scrappa.co/api/instagram/user/posts?username=" + urllib.parse.quote(nome), {"X-API-KEY": chave}, None, 60)
    out = []
    for n in d.get("posts") or []:
        m = (n.get("media") or [{}])[0]
        video = (n.get("media_type") or "") == "video"
        foto = ((m.get("images") or [{}])[0]).get("url") or m.get("thumbnail_url")
        vurl = m.get("video_url") or (((m.get("video_versions") or [{}])[0]).get("url"))
        out.append(dict(shortcode=n.get("shortcode"), legenda=n.get("caption") or "", quando=n.get("taken_at") or "",
                        video=video, midia=vurl if video else foto))
    return out


def _ler_apify(nome, chave):
    itens = _post_json("https://api.apify.com/v2/acts/apify~instagram-profile-scraper/run-sync-get-dataset-items?timeout=120",
                       {"Authorization": "Bearer " + chave}, {"usernames": [nome]}, 150)
    out = []
    for u in itens:
        for n in u.get("latestPosts") or []:
            video = (n.get("type") or "").lower() == "video"
            out.append(dict(shortcode=n.get("shortCode"), legenda=n.get("caption") or "", quando=n.get("timestamp") or "",
                            video=video, midia=n.get("videoUrl") if video else n.get("displayUrl")))
    return out


def _ler_socialtap(nome, chave):
    d = _post_json("https://socialtap.dev/v1/instagram/posts?handle=" + urllib.parse.quote(nome), {"x-api-key": chave}, None, 60)
    out = []
    for n in d.get("data") or []:
        m = (n.get("media") or [{}])[0]
        video = (n.get("type") or m.get("type") or "") == "video"
        out.append(dict(shortcode=n.get("id"), legenda=n.get("text") or "", quando=n.get("published_at") or "",
                        video=video, midia=m.get("url") if video else (m.get("url") or n.get("thumbnail_url"))))
    return out


def _ler_maviapi(nome, chave):
    d = _post_json("https://api.maviapi.com/v1/sites/instagram/profiles/" + urllib.parse.quote(nome) + "/recent-posts", {"Authorization": "Bearer " + chave}, None, 60)
    out = []
    for n in ((d.get("data") or {}).get("posts")) or []:
        video = (n.get("type") or "") == "video" or bool(n.get("video_url"))
        out.append(dict(shortcode=n.get("shortcode"), legenda=n.get("caption") or "", quando=n.get("taken_at") or "",
                        video=video, midia=n.get("video_url") if video else n.get("display_url")))
    return out


def _ler_creatorcrawl(nome, chave):
    d = _post_json("https://api.creatorcrawl.com/instagram/user/posts?handle=" + urllib.parse.quote(nome), {"x-api-key": chave}, None, 60)
    out = []
    for n in d.get("data") or []:
        m = (n.get("media") or [{}])[0]
        video = (n.get("type") or m.get("type") or "") == "video"
        cod = (n.get("url") or "").rstrip("/").split("/")[-1]
        out.append(dict(shortcode=cod, legenda=n.get("text") or "", quando=n.get("created_at") or "", video=video, midia=m.get("url")))
    return out


# nome -> (segredo no ambiente, leitor, custo em unidades por perfil lido)
SERVICOS = {"scrappa": ("SCRAPPA_KEY", _ler_scrappa, 1), "apify": ("APIFY_TOKEN", _ler_apify, 1),
            "socialtap": ("SOCIALTAP_KEY", _ler_socialtap, 1), "maviapi": ("MAVIAPI_KEY", _ler_maviapi, 1),
            "creatorcrawl": ("CREATORCRAWL_KEY", _ler_creatorcrawl, 1)}


def _main_posts(cfg):
    """Instagram por serviços de terceiros em planos grátis (sem cartão). Modo econômico: só com chuva confirmada,
    poucos perfis por varredura em rodízio, intervalo mínimo e tetos por serviço (dia e mês) gravados no estado."""
    sv = cfg.get("servicos", {})
    prior = sv.get("perfis") or cfg["instagram"][:8]
    por_var, intervalo = sv.get("perfis_por_varredura", 5), sv.get("intervalo_min", 20) * 60
    os.makedirs(APP_DIR, exist_ok=True)
    if not c.chuva_confirmada():
        c.log_robo("robo1_instagram", True, "Instagram (serviços): sem chuva confirmada, poupando a cota grátis")
        return 0
    agora = dt.datetime.now(dt.timezone.utc)
    mes, dia = agora.strftime("%Y-%m"), agora.strftime("%Y-%m-%d")
    uso = _uso()
    if time.time() - uso.get("ultimo", 0) < intervalo:
        c.log_robo("robo1_instagram", True, "Instagram (serviços): aguardando o intervalo mínimo entre varreduras")
        return 0
    # escolhe o serviço com mais cota mensal sobrando (em proporção), que tenha chave, não esteja em pausa e caiba no dia
    melhor, sobra = None, -1.0
    reserva, sobra_r = None, None  # reservas (crédito único/trial) só entram se nenhum serviço principal puder
    for nome, (env, _, custo) in SERVICOS.items():
        conf = sv.get("teto", {}).get(nome)
        if not conf or not os.environ.get(env):
            continue
        if conf.get("valido_ate") and agora.strftime("%Y-%m-%d") > conf["valido_ate"]:
            continue  # trial vencido: sai do rodízio sozinho
        u = uso.setdefault("s", {}).setdefault(nome, {})
        if u.get("mes") != mes:
            u.update(mes=mes)
            if not conf.get("credito_unico"):  # crédito único não renova: o uso acumulado nunca zera
                u["usado"] = 0
        u.setdefault("usado", 0)
        if u.get("dia") != dia:
            u.update(dia=dia, dia_usado=0)
        if time.time() < u.get("pausa_ate", 0):
            continue
        if u["usado"] + por_var * custo > conf["mes"] or u["dia_usado"] + por_var * custo > conf["dia"]:
            continue
        fr = 1 - u["usado"] / conf["mes"]
        if conf.get("reserva"):
            ch = (-conf.get("ordem", 9), fr)  # reservas: menor "ordem" primeiro, depois a que tem mais cota sobrando
            if reserva is None or ch > sobra_r:
                reserva, sobra_r = nome, ch
        elif fr > sobra:
            melhor, sobra = nome, fr
    melhor = melhor or reserva
    if not melhor:
        c.log_robo("robo1_instagram", True, "Instagram (serviços): nenhum serviço com cota disponível agora, sem gastar")
        return 0
    env, leitor, custo = SERVICOS[melhor]
    u = uso["s"][melhor]
    i0 = uso.get("rodizio", 0) % len(prior)
    escolha = [prior[(i0 + k) % len(prior)] for k in range(min(por_var, len(prior)))]
    uso["rodizio"] = i0 + len(escolha)
    uso["ultimo"] = time.time()  # grava antes: mesmo se falhar, não repete antes do intervalo
    _salvar_uso(uso)
    limite = c.agora() - dt.timedelta(hours=c.JANELA_HORAS)
    novos = analisados = lidos = lidos_perfis = falhas = brutos = parseados = 0
    for nome in escolha:
        try:
            posts = leitor(nome, os.environ[env])
        except urllib.error.HTTPError as e:
            falhas += 1
            if e.code in (401, 402, 403, 429):  # chave/cota/limite: pausa o serviço e para
                u["pausa_ate"] = time.time() + (24 if e.code != 429 else 1) * 3600
                c.log_robo("robo1_instagram", False, "Instagram (%s): HTTP %s, serviço em pausa" % (melhor, e.code))
                open(os.path.join(c.AQUI, "..", ".ig-falhou"), "w").write("%s HTTP %s" % (melhor, e.code))
                break
            continue
        except Exception as e:
            falhas += 1
            print(f"{melhor} {nome}: {type(e).__name__}: {str(e)[:100]}")
            continue
        u["usado"] += custo
        u["dia_usado"] += custo
        lidos_perfis += 1
        brutos += len(posts[:12])
        for n in posts[:12]:
            try:
                data = _quando(n["quando"])
                parseados += 1
                if data < limite:
                    continue
                if not n.get("shortcode"):
                    continue
                it = dict(origem="instagram", post_id=str(n["shortcode"]), autor=f"@{nome}",
                          url=_link_post(n["shortcode"], nome), legenda=n["legenda"],
                          publicado_em=data.isoformat(), midia_url=n.get("midia"), eh_video=n["video"])
                lidos += 1
                if not it["legenda"].strip() and not it["eh_video"]:
                    continue
                if c.ja_na_fila(it):
                    continue
                a = c.analisar(it)
                ok, motivo = c.validar_analise(a)
                it.update(analise=a, estado="analisado" if ok else "descartado", motivo=motivo or None)
                if c.fila_inserir(it):
                    novos += 1
                    analisados += ok
            except Exception as e:
                print("candidato falhou:", n.get("shortcode"), e)
    _salvar_uso(uso)
    cfgt = sv["teto"][melhor]
    if brutos and parseados == 0:  # formato do provedor mudou: avisa em vez de parecer "sem posts novos"
        c.log_robo("robo1_instagram", False, "Instagram (%s): %d posts lidos, 0 parseados (formato de data/id mudou?)" % (melhor, brutos))
    elif brutos:
        print("%s: %d posts lidos, %d parseados" % (melhor, brutos, parseados))
    msg = "%s: %d/%d perfis lidos, %d posts recentes, %d novos, %d aprovados pela IA (uso do mês %d/%d)" % (melhor, lidos_perfis, len(escolha), lidos, novos, analisados, u["usado"], cfgt["mes"])
    if escolha and lidos_perfis == 0:
        c.log_robo("robo1_instagram", False, "Instagram (" + msg + ")")
        open(os.path.join(c.AQUI, "..", ".ig-falhou"), "w").write("nenhum perfil lido via " + melhor)
        return 0
    c.log_robo("robo1_instagram", True, "Instagram via " + msg)
    return 0


def _ler_stories_apify(nomes, chave):
    """Stories ativos (24h) dos perfis, numa execução só. Cobra por perfil processado, não por story."""
    return _post_json("https://api.apify.com/v2/acts/lance_api~instagram-stories-scraper-api/run-sync-get-dataset-items?timeout=120",
                      {"Authorization": "Bearer " + chave}, {"usernames": nomes, "includeFullStoryData": True}, 150)


def _texto_story(r):
    partes = [r.get("caption") or ""]
    partes += [("Local: " + (l.get("name") or l.get("title") or "")) for l in (r.get("locations") or []) if isinstance(l, dict)]
    partes += ["#" + h for h in (r.get("hashtags") or [])]
    return " ".join(x for x in partes if x).strip()


def main_stories(cfg):
    """Stories dos perfis prioritários (só o Apify lê story ativo no plano grátis). Só com chuva confirmada,
    a cada 30 min, teto de leituras por dia e por mês gravado no estado, pausa em 402/403/429. Story vira candidato igual post."""
    st = cfg.get("servicos", {}).get("stories")
    chave = os.environ.get("APIFY_TOKEN")
    if not st or not chave or not c.chuva_confirmada():
        return 0
    perfis = (st.get("perfis") or cfg["servicos"].get("perfis") or [])[:st.get("max_perfis", 8)]
    agora = dt.datetime.now(dt.timezone.utc)
    mes, dia = agora.strftime("%Y-%m"), agora.strftime("%Y-%m-%d")
    uso = _uso()
    u = uso.setdefault("stories", {})
    if u.get("mes") != mes:
        u.update(mes=mes, usado=0)
    if u.get("dia") != dia:
        u.update(dia=dia, dia_usado=0)
    if time.time() - u.get("ultimo", 0) < st.get("intervalo_min", 30) * 60 - 60:
        return 0
    if time.time() < u.get("pausa_ate", 0):
        print("stories: serviço em pausa")
        return 0
    if u["dia_usado"] + len(perfis) > st.get("teto_dia", 60) or u["usado"] + len(perfis) > st.get("teto_mes", 800):
        c.log_robo("robo1_instagram", True, "Stories: teto de leituras atingido (dia %d, mês %d), sem gastar" % (u["dia_usado"], u["usado"]))
        return 0
    u["ultimo"] = time.time()
    u["usado"] += len(perfis)  # conta antes: se cair no meio, o gasto já está contado
    u["dia_usado"] += len(perfis)
    _salvar_uso(uso)
    try:
        linhas = _ler_stories_apify(perfis, chave)
    except urllib.error.HTTPError as e:
        if e.code in (401, 402, 403, 429):
            u["pausa_ate"] = time.time() + (24 if e.code != 429 else 1) * 3600
            _salvar_uso(uso)
        c.log_robo("robo1_instagram", False, "Stories (apify): HTTP %s" % e.code)
        return 0
    except Exception as e:
        c.log_robo("robo1_instagram", False, "Stories (apify): %s %s" % (type(e).__name__, str(e)[:100]))
        return 0
    limite = c.agora() - dt.timedelta(hours=c.JANELA_HORAS)
    lidos = novos = aprov = 0
    for r in linhas:
        try:
            if r.get("status") != "success" or not r.get("storyId"):
                continue
            nome = r.get("username") or ""
            quando = dt.datetime.fromisoformat(str(r.get("postedAt")).replace("Z", "+00:00"))
            if quando < limite:
                continue
            texto = _texto_story(r)
            lidos += 1
            if not texto:  # a IA só lê texto: story sem legenda/local não dá pra avaliar
                continue
            video = (r.get("mediaType") or "") == "video"
            it = dict(origem="instagram", post_id="story-" + str(r["storyId"]), autor=f"@{nome}",
                      url=f"https://www.instagram.com/stories/{nome}/{r['storyId']}/", legenda="(Story de 24h) " + texto,
                      publicado_em=quando.isoformat(), midia_url=(r.get("videoUrl") if video else (r.get("imageUrl") or r.get("mediaUrl"))) or r.get("mediaUrl"), eh_video=video)
            if c.ja_na_fila(it):
                continue
            a = c.analisar(it)
            ok, motivo = c.validar_analise(a)
            it.update(analise=a, estado="analisado" if ok else "descartado", motivo=motivo or None)
            if c.fila_inserir(it):
                novos += 1
                aprov += ok
        except Exception as e:
            print("story falhou:", r.get("storyId"), e)
    c.log_robo("robo1_instagram", True, "Stories via apify: %d perfis, %d stories recentes com texto, %d novos, %d aprovados pela IA (leituras: dia %d/%d, mês %d/%d)" % (
        len(perfis), lidos, novos, aprov, u["dia_usado"], st.get("teto_dia", 60), u["usado"], st.get("teto_mes", 800)))
    return 0


def main_servicos(cfg):
    r = _main_posts(cfg)
    try:
        main_stories(cfg)
    except Exception as e:
        print("stories falhou:", type(e).__name__, str(e)[:120])
    return r


def main_diag():
    """Diagnóstico sem login: abre a página de login e imprime o que o navegador vê. Não envia credenciais."""
    sync_playwright = _playwright()
    _instalar_chromium()
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(user_agent=UA, locale="en-US", timezone_id="America/Sao_Paulo", viewport={"width": 1366, "height": 800})
        page = ctx.new_page()
        try:
            resp = page.goto("https://www.instagram.com/accounts/login/?hl=en", wait_until="domcontentloaded", timeout=45000)
            print("DIAG status:", resp.status if resp else None)
            for i in (1, 2, 3):
                page.wait_for_timeout(5000)
                print("DIAG t=%ds url=%s title=%r" % (5 * i, page.url[:120], page.title()[:80]))
                print("DIAG inputs:", page.evaluate("[...document.querySelectorAll('input')].map(i=>[i.name,i.type,i.getAttribute('aria-label')])"))
                print("DIAG buttons:", page.evaluate("[...document.querySelectorAll('button,[role=button]')].map(b=>(b.innerText||'').trim().slice(0,40)).filter(x=>x).slice(0,15)"))
                print("DIAG body:", page.inner_text("body")[:400].replace("\n", " | "))
        finally:
            br.close()
    c.log_robo("robo1_instagram", True, "diagnóstico do navegador feito (sem login)")
    return 0


def main():
    if not c.portao_aberto():
        c.log_robo("robo1_instagram", True, "sem chuva nem previsão, dormindo")
        return 0
    if instaloader is None:
        raise RuntimeError("instaloader não instalado")
    cfg = json.load(open(os.path.join(c.AQUI, "fontes.json")))
    if not cfg.get("instagram_ativo", True):
        c.log_robo("robo1_instagram", True, "pausado (instagram_ativo=false em fontes.json): login recusado, sem insistir")
        return 0
    perfis = list(cfg["instagram"])
    backend = cfg.get("instagram_backend", "browser")
    if backend == "servicos":
        return main_servicos(cfg)
    if backend == "diag":
        return main_diag()
    if backend == "browser":
        return main_browser(cfg, perfis)
    if backend == "app":
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
            if c.ja_na_fila(it):
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
                if c.ja_na_fila(it):
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
