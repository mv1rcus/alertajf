"""Leitor de stories LOGADO (conta @mv1thebest, só leitura) via instagrapi.
- Usuário, senha, semente TOTP e sessão ficam na tabela privada public.ajf_segredos (RLS ligada, só a service role lê).
  Nada disso vai pro repositório nem pro log.
- A sessão persiste entre varreduras: só refaz o login (com código TOTP gerado aqui) quando o Instagram a derruba.
- Só lê: uma chamada em lote (GraphQL web) pros perfis. Não segue, não curte, não vê/marca story, não posta.
- Sessão derrubada: reloga sozinho; se o login também falhar, pausa 1h e tenta de novo. Challenge/checkpoint: pausa 2h e tenta de novo. 429: pausa 6h. Nunca fica parado 24h (regra do Marcus, 25/11). Em pausa, quem chama cai pro Apify."""
import json, os, sys, time, hmac, hashlib, struct, base64, random, urllib.parse
import common as c

CHAVE_SEG = "ig_mv1thebest"
CHAVE_EST = "ig_logado"


class Cedo(Exception):
    """Ainda não é hora de ler de novo (ou em pausa): quem chama não deve gastar o Apify também."""


class Falha(Exception):
    """Não deu pra ler logado: quem chama pode cair pro Apify."""


def _totp(seed):
    k = base64.b32decode(seed.replace(" ", "").upper() + "=" * (-len(seed.replace(" ", "")) % 8))
    h = hmac.new(k, struct.pack(">Q", int(time.time() // 30)), hashlib.sha1).digest()
    o = h[-1] & 15
    return "%06d" % ((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)


def _seg():
    r = c._sb("GET", "ajf_segredos?select=valor&chave=eq." + CHAVE_SEG)
    if not r:
        raise Falha("sem credenciais em ajf_segredos")
    return r[0]["valor"]


def _gravar_seg(v):
    c._sb("POST", "ajf_segredos?on_conflict=chave", {"chave": CHAVE_SEG, "valor": v, "atualizado_em": c.agora().isoformat()},
          {"Prefer": "resolution=merge-duplicates,return=minimal"})


def _pausar(est, horas, motivo):
    est["pausa_ate"] = time.time() + horas * 3600
    est["motivo"] = motivo
    c.estado_gravar(CHAVE_EST, est)
    c.log_robo("robo1_instagram", False, "Stories logado: pausa de %dh (%s)" % (horas, motivo))


def _instalar():
    try:
        import instagrapi  # noqa
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "instagrapi>=3.2.9"], check=True)


def _cliente(seg):
    from instagrapi import Client
    cl = Client()
    cl.delay_range = [2, 4]
    cl.request_timeout = 30
    if seg.get("sessao"):
        cl.set_settings(seg["sessao"])
    return cl


def _login(cl, seg):
    cl.login(seg["user"], seg["senha"], verification_code=_totp(seg["totp"]))
    seg["sessao"] = cl.get_settings()
    _gravar_seg(seg)
    print("stories logado: login novo feito")


def _lote(cl, ids):
    body = cl.graphql_request(data={
        "variables": json.dumps({"reel_ids_arr": [str(i) for i in ids],
                                 "__relay_internal__pv__PolarisCommunityNoteStoriesLabelEnabledrelayprovider": True}),
        "doc_id": "29184890191114309", "fb_dtsg": cl.fb_dtsg, "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "PolarisStoriesV3ReelPageStandaloneQuery", "server_timestamps": "true"})
    try:
        return body["data"]["xdt_api__v1__feed__reels_media"]["reels_media"]
    except (KeyError, TypeError):
        raise Falha("resposta de stories fora do formato")


def _ids(cl, nomes, est):
    pks = est.setdefault("pks", {})
    novos = [n for n in nomes if n not in pks]
    for n in novos[:6]:  # no máximo 6 buscas por varredura (cada uma é uma chamada)
        try:
            pks[n] = int(cl.user_id_from_username(n))
        except Exception as e:
            pks[n] = 0  # não existe/mudou de nome: não tenta de novo
            print("stories logado: sem id de", n, type(e).__name__)
        time.sleep(random.uniform(2, 4))
    return [(n, pks[n]) for n in nomes if pks.get(n)]


def _linha(r, nome_por_id):
    """Item de story da API -> mesmo formato das linhas do Apify, pra reaproveitar o resto do robô."""
    u = r.get("user") or {}
    nome = u.get("username") or nome_por_id.get(str(u.get("pk") or u.get("id")), "")
    cap = r.get("caption")
    cap = cap.get("text") if isinstance(cap, dict) else (cap or "")
    locs = []
    for sl in (r.get("story_locations") or []):
        loc = (sl or {}).get("location") or {}
        if loc.get("name"):
            locs.append({"name": loc["name"]})
    tags = []
    for sh in (r.get("story_hashtags") or []):
        h = ((sh or {}).get("hashtag") or {}).get("name")
        if h:
            tags.append(h)
    video = r.get("media_type") == 2 and bool(r.get("video_versions"))
    cands = ((r.get("image_versions2") or {}).get("candidates")) or []
    img = cands[0].get("url") if cands else None
    import datetime as dt
    return {"status": "success", "storyId": str(r.get("pk") or r.get("id")).split("_")[0], "username": nome,
            "postedAt": dt.datetime.fromtimestamp(int(r["taken_at"]), dt.timezone.utc).isoformat(),
            "caption": cap, "locations": locs, "hashtags": tags,
            "mediaType": "video" if video else "image",
            "videoUrl": r["video_versions"][0].get("url") if video else None, "imageUrl": img, "mediaUrl": img}


def ler_stories(perfis, cfg):
    est = c.estado_ler(CHAVE_EST) or {}
    if time.time() < est.get("pausa_ate", 0):
        raise Falha("em pausa (%s)" % est.get("motivo", ""))  # pausado: deixa o Apify cobrir
    if time.time() - est.get("ultimo", 0) < cfg.get("intervalo_min", 20) * 60 - 60:
        raise Cedo()
    try:
        seg = _seg()
        _instalar()
        import instagrapi.exceptions as ex
    except Exception as e:
        raise Falha("preparo: %s %s" % (type(e).__name__, str(e)[:100]))
    est["ultimo"] = time.time()
    c.estado_gravar(CHAVE_EST, est)
    try:
        cl = _cliente(seg)
        if not seg.get("sessao"):
            _login(cl, seg)
        alvo = _ids(cl, perfis, est)
        nome_por_id = {str(i): n for n, i in alvo}
        try:
            reels = _lote(cl, [i for _, i in alvo])
        except ex.LoginRequired:  # sessão caiu: um único login novo
            _login(cl, seg)
            reels = _lote(cl, [i for _, i in alvo])
        seg["sessao"] = cl.get_settings()
        _gravar_seg(seg)  # guarda a sessão renovada
        linhas = []
        for reel in reels:
            for it in (reel.get("items") or []):
                try:
                    linhas.append(_linha(dict(it, user=it.get("user") or reel.get("user") or {}), nome_por_id))
                except Exception as e:
                    print("stories logado: item ignorado", type(e).__name__)
        est["ok"] = time.time()
        c.estado_gravar(CHAVE_EST, est)
        return linhas
    except ex.LoginRequired as e:
        _pausar(est, 1, type(e).__name__)  # sessão derrubada e o relogin falhou: respira 1h e tenta de novo
        raise Falha(type(e).__name__)
    except (ex.ChallengeRequired, ex.ChallengeError, ex.FeedbackRequired, ex.TwoFactorRequired) as e:
        _pausar(est, 2, type(e).__name__)  # challenge/checkpoint: com calma, espaçado, sem martelar (regra do Marcus, 25/11)
        raise Falha(type(e).__name__)
    except ex.ClientError as e:
        msg = str(e)[:120]
        if "429" in msg or "Too Many" in msg or "wait a few minutes" in msg.lower():
            _pausar(est, 6, "429")
        raise Falha("%s %s" % (type(e).__name__, msg))
    except Falha:
        raise
    except Exception as e:
        raise Falha("%s %s" % (type(e).__name__, str(e)[:100]))
