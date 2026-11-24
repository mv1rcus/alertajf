"""Código compartilhado dos 4 robôs do AlertaJF. Só biblioteca padrão do Python."""
import json, os, re, sys, time, urllib.request, urllib.error, urllib.parse, uuid, datetime as dt

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://fnpssjnsljhwdoikfwcu.supabase.co")
PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_wGdx39fLd5BbXzet5qSOsQ_thFUqn-m")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
JANELA_HORAS = 5  # mesma janela de expiração dos relatos do site
JF_BBOX = (-21.90, -21.60, -43.60, -43.15)  # lat_min, lat_max, lon_min, lon_max
UA = "AlertaJF-robos/1.0 (+https://github.com/mvthebest/alertajf)"
AQUI = os.path.dirname(os.path.abspath(__file__))


def agora():
    return dt.datetime.now(dt.timezone.utc)


def http(method, url, headers=None, body=None, timeout=40, raw=False):
    h = {"User-Agent": UA}
    h.update(headers or {})
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    if isinstance(body, (dict, list)):
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = r.read()
            return out if raw else (json.loads(out) if out else None)
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {e.code} em {method} {url.split('?')[0]}: {corpo}")


# ---------- fila (Supabase, service role) ----------
def _sb(method, caminho, body=None, extra=None):
    if not SERVICE_KEY:
        raise RuntimeError("Falta o secret SUPABASE_SERVICE_ROLE")
    h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Prefer": "return=representation"}
    h.update(extra or {})
    return http(method, f"{SUPABASE_URL}/rest/v1/{caminho}", h, body)


def fila_inserir(item):
    """Insere candidato novo; ignora se (origem, post_id) já existe. Devolve True se inseriu."""
    r = _sb("POST", "ajf_fila?on_conflict=origem,post_id", item, {"Prefer": "resolution=ignore-duplicates,return=representation"})
    return bool(r)


def fila_listar(estado, limite=20):
    q = urllib.parse.quote(estado)
    return _sb("GET", f"ajf_fila?estado=eq.{q}&order=criado_em.asc&limit={limite}") or []


def fila_atualizar(id_, **campos):
    campos["atualizado_em"] = agora().isoformat()
    return _sb("PATCH", f"ajf_fila?id=eq.{id_}", campos)


def fila_erro(item, msg, max_tentativas=3):
    n = int(item.get("tentativas") or 0) + 1
    estado = "erro" if n >= max_tentativas else item["estado"]
    fila_atualizar(item["id"], tentativas=n, motivo=str(msg)[:400], estado=estado)


def log_robo(robo, ok, resumo):
    print(f"[{robo}] {'OK' if ok else 'FALHA'}: {resumo}")
    try:
        _sb("POST", "ajf_robos_log", {"robo": robo, "ok": ok, "resumo": resumo[:500]})
    except Exception as e:  # log nunca derruba o robô
        print("log falhou:", e)


# ---------- portão de chuva ----------
def esta_chovendo():
    """Acorda os robôs se choveu em JF na última hora OU se há chuva prevista na próxima hora.
    Fonte: Open-Meteo (grátis, sem chave). Sem chuva nem previsão, os robôs dormem."""
    if os.environ.get("FORCAR_VARREDURA") == "1":
        return True
    u = ("https://api.open-meteo.com/v1/forecast?latitude=-21.7642&longitude=-43.3503"
         "&minutely_15=precipitation,precipitation_probability&past_minutely_15=4&forecast_minutely_15=4&timezone=UTC")
    try:
        d = http("GET", u)["minutely_15"]
        mm = [x or 0 for x in d["precipitation"]]
        passado, futuro = sum(mm[:4]), sum(mm[4:])
        print(f"chuva na última hora: {passado:.1f} mm | previsão próxima 1h: {futuro:.1f} mm")
        return passado >= 0.3 or futuro >= 0.2
    except Exception as e:
        print("portão de chuva falhou, seguindo por segurança:", e)
        return True


# ---------- IA (Gemini, camada gratuita) ----------
PROMPT_ANALISE = """Você filtra posts para o AlertaJF, um mapa de ocorrências de chuva em Juiz de Fora (MG).
Agora (UTC): {agora}. Post de {autor} publicado em {publicado}.
Texto do post: ---
{legenda}
---
Responda SÓ com JSON no formato:
{{"valido": bool, "motivo": "curto", "tipo": "alagamento|deslizamento|enxurrada|interdicao|sem_luz|nenhum", "rua": "", "bairro": "", "ocorrido_em": "ISO-8601 UTC ou vazio", "descricao": "1-2 frases em português, só fatos do texto", "confianca": 0.0}}

REGRAS (todas obrigatórias, na dúvida valido=false):
1. Só vale OCORRÊNCIA REAL da chuva ATUAL, em Juiz de Fora (MG): alagamento, deslizamento/queda de barranco, enxurrada, via interditada, queda de energia por chuva.
2. Precisa ter local identificável: rua OU bairro de Juiz de Fora citado no texto. Não invente local.
3. Descarte (valido=false): foto/vídeo genérico de céu ou chuva caindo; imagem de alerta, aviso da Defesa Civil, previsão ou gráfico; notícia de outra cidade; balanço geral sem local específico; post de dias anteriores (temporal passado), mesmo que o perfil tenha postado agora.
4. ocorrido_em: horário do fato segundo o texto (ex.: "hoje às 18h", "agora há pouco"), em UTC. Use o horário de publicação se o texto indicar que é agora. Se não der para saber, deixe vazio e valido=false.
5. Timezone do texto: Brasília (UTC-3)."""


def _modelo():
    global _MODELO
    if "_MODELO" in globals():
        return _MODELO
    pref = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-flash-latest"]
    try:
        d = http("GET", f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}&pageSize=200")
        nomes = [m["name"].split("/")[-1] for m in d.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        for p in pref:
            if p in nomes:
                _MODELO = p
                return p
        flash = [n for n in nomes if "flash" in n and "image" not in n and "tts" not in n]
        _MODELO = sorted(flash)[0] if flash else pref[0]
    except Exception:
        _MODELO = pref[0]
    return _MODELO


def analisar(item):
    """Roda a IA sobre um candidato. Devolve dict de análise (com campo 'valido')."""
    if not GEMINI_KEY:
        raise RuntimeError("Falta o secret GEMINI_API_KEY")
    prompt = PROMPT_ANALISE.format(agora=agora().isoformat(timespec="minutes"), autor=item.get("autor", ""),
                                   publicado=item.get("publicado_em") or "desconhecido", legenda=(item.get("legenda") or "")[:3000])
    corpo = {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
    for tentativa in range(4):
        try:
            d = http("POST", f"https://generativelanguage.googleapis.com/v1beta/models/{_modelo()}:generateContent?key={GEMINI_KEY}", body=corpo, timeout=60)
            txt = d["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(txt)
        except RuntimeError as e:
            if "HTTP 429" in str(e) or "HTTP 503" in str(e):
                time.sleep(15 * (tentativa + 1))
                continue
            raise
    raise RuntimeError("Gemini indisponível/limite (429) após 4 tentativas")


def validar_analise(a):
    """Regras duras aplicadas em código, além do que a IA respondeu. Devolve (ok, motivo)."""
    if not a.get("valido"):
        return False, a.get("motivo") or "IA marcou como inválido"
    if a.get("tipo") not in ("alagamento", "deslizamento", "enxurrada", "interdicao", "sem_luz"):
        return False, "tipo inválido"
    if not (a.get("rua") or a.get("bairro")):
        return False, "sem local"
    if float(a.get("confianca") or 0) < 0.6:
        return False, "confiança baixa"
    try:
        t = dt.datetime.fromisoformat(a["ocorrido_em"].replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return False, "sem horário do ocorrido"
    idade = agora() - t
    if idade > dt.timedelta(hours=JANELA_HORAS - 0.25) or idade < dt.timedelta(minutes=-5):
        return False, "fora da janela de 5h (chuva atual)"
    return True, ""


# ---------- geocodificação ----------
def _bairros():
    return json.load(open(os.path.join(AQUI, "bairros.json"), encoding="utf-8"))


def _norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()


def geocodificar(rua, bairro):
    """(lat, lon, bairro_final) ou None. Nominatim restrito a JF; cai no centro do bairro."""
    b_norm = _norm(bairro or "")
    centro = next((b for b in _bairros() if _norm(b["nome"]) == b_norm), None)
    if rua:
        q = ", ".join(x for x in [rua, bairro, "Juiz de Fora", "MG", "Brasil"] if x)
        u = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=br"
             f"&viewbox={JF_BBOX[2]},{JF_BBOX[1]},{JF_BBOX[3]},{JF_BBOX[0]}&bounded=1&q=" + urllib.parse.quote(q))
        try:
            time.sleep(1.1)  # política de uso: 1 requisição por segundo
            r = http("GET", u)
            if r:
                la, lo = float(r[0]["lat"]), float(r[0]["lon"])
                if JF_BBOX[0] <= la <= JF_BBOX[1] and JF_BBOX[2] <= lo <= JF_BBOX[3]:
                    return la, lo, (centro["nome"] if centro else (bairro or "Juiz de Fora"))
        except Exception as e:
            print("nominatim falhou:", e)
    if centro:
        return centro["lat"], centro["lon"], centro["nome"]
    return None
