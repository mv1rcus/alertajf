"""Código compartilhado dos 4 robôs do AlertaJF. Só biblioteca padrão do Python."""
import json, os, re, sys, time, urllib.request, urllib.error, urllib.parse, uuid, datetime as dt

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://fnpssjnsljhwdoikfwcu.supabase.co")
PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_wGdx39fLd5BbXzet5qSOsQ_thFUqn-m")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
JANELA_HORAS = 2  # cada pino dura 2h (mesma janela de expiração dos relatos do site)
JF_BBOX = (-22.00, -21.52, -43.69, -43.14)  # lat_min, lat_max, lon_min, lon_max: caixa em volta do polígono do município (robos/jf_poligono.json)
UA = "AlertaJF-robos/1.0 (+https://github.com/mvthebest/alertajf)"
try:
    sys.stdout.reconfigure(line_buffering=True)  # log aparece na hora, mesmo se o job for cortado
except Exception:
    pass
_INICIO = time.time()
ORCAMENTO_S = 600  # a IA para de analisar depois de 10 min: o job tem limite de 15 e não pode travar a fila
_GEMINI_ESGOTADO = [False]
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


def ja_na_fila(item):
    """True se (origem, post_id) já está na fila: não gasta IA reanalisando o que já foi visto."""
    try:
        r = _sb("GET", "ajf_fila?select=id&origem=eq.%s&post_id=eq.%s&limit=1" % (urllib.parse.quote(item["origem"]), urllib.parse.quote(str(item["post_id"]))))
        return bool(r)
    except Exception as e:
        print("checagem da fila falhou, seguindo:", e)
        return False


def estado_ler(chave):
    """Estado dos robôs guardado no banco (tabela ajf_estado). None se não existir ou der erro."""
    try:
        r = _sb("GET", "ajf_estado?select=valor&chave=eq." + urllib.parse.quote(chave))
        return r[0]["valor"] if r else None
    except Exception as e:
        print("estado_ler falhou:", e)
        return None


def estado_gravar(chave, valor):
    try:
        _sb("POST", "ajf_estado?on_conflict=chave", {"chave": chave, "valor": valor, "atualizado_em": agora().isoformat()},
            {"Prefer": "resolution=merge-duplicates,return=minimal"})
        return True
    except Exception as e:
        print("estado_gravar falhou:", e)
        return False


def fila_listar(estado, limite=20, ordem="asc"):
    q = urllib.parse.quote(estado)
    return _sb("GET", f"ajf_fila?estado=eq.{q}&order=criado_em.{ordem}&limit={limite}") or []


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
def chuva_confirmada():
    """True só com chuva medida na última hora (sem contar previsão). Usado para economizar cota de serviços pagos no plano grátis."""
    if os.environ.get("FORCAR_VARREDURA") == "1":
        return True
    u = ("https://api.open-meteo.com/v1/forecast?latitude=-21.7642&longitude=-43.3503"
         "&minutely_15=precipitation&past_minutely_15=4&forecast_minutely_15=0&timezone=UTC")
    try:
        mm = [x or 0 for x in http("GET", u)["minutely_15"]["precipitation"]]
        return sum(mm[:4]) >= 0.3
    except Exception:
        return False


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
        if passado >= 0.3:
            return True  # chuva confirmada: varredura contínua (o disparo externo vem a cada 10 min)
        # só previsão: acorda a cada disparo externo (10 em 10 min, o mesmo ritmo do radar ao vivo)
        return futuro >= 0.2
    except Exception as e:
        print("portão de chuva falhou, seguindo por segurança:", e)
        return True


def portao_aberto():
    """No Actions o job só roda se o portão disse chove=true (condição do workflow): confia nele e NÃO consulta de novo,
    senão a regra "só previsão" (1 ciclo por quarto de hora) fazia robôs discordarem do portão. Fora do Actions, consulta."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return True
    return esta_chovendo()


# ---------- IA (Gemini, camada gratuita) ----------
PROMPT_ANALISE = """Você filtra posts para o AlertaJF, um mapa de ocorrências de chuva em Juiz de Fora (MG).
Agora (UTC): {agora}. Post de {autor} publicado em {publicado}.
Texto do post: ---
{legenda}
---
Responda SÓ com JSON no formato:
{{"valido": bool, "motivo": "curto", "tipo": "alagamento|deslizamento|enxurrada|interdicao|sem_luz|nenhum", "rua": "", "bairro": "", "referencia": "", "ocorrido_em": "ISO-8601 UTC ou vazio", "descricao": "1-2 frases em português, só fatos do texto", "confianca": 0.0}}

REGRAS (todas obrigatórias, na dúvida valido=false):
1. Só vale OCORRÊNCIA REAL da chuva ATUAL, em Juiz de Fora (MG): alagamento, deslizamento/queda de barranco, enxurrada, via interditada, queda de energia por chuva.
2. Precisa ter local identificável: rua OU bairro de Juiz de Fora citado no texto. Não invente local. Em "referencia" ponha o ponto de referência citado junto (ponte, cruzamento, número, prédio, praça) ou vazio; se o texto citar bairro, preencha "bairro". Rua sem bairro nem referência é aceita, mas o pin sai marcado como trecho aproximado.
3. Descarte (valido=false): foto/vídeo genérico de céu ou chuva caindo; imagem de alerta, aviso da Defesa Civil, previsão ou gráfico; notícia de outra cidade; balanço geral sem local específico; post de dias anteriores (temporal passado), mesmo que o perfil tenha postado agora.
4. ocorrido_em: horário do fato segundo o texto (ex.: "hoje às 18h", "agora há pouco"), em UTC. Use o horário de publicação se o texto indicar que é agora. Se não der para saber, deixe vazio e valido=false.
5. Timezone do texto: Brasília (UTC-3).
6. NOTÍCIA (origem notícias): a data do feed NÃO é o horário do fato (o Google Notícias reindexa matéria velha). Hoje é {hoje_br}. Só vale se o próprio texto mostrar que o fato é de AGORA: "agora", "neste momento", "há pouco", "nesta tarde/hoje" com data de hoje. Se falar em "ontem", "noite de segunda", "segunda-feira (23)", data anterior, balanço do temporal passado, ou se não der para saber o dia do fato, valido=false. Quando a linha "Data real da matéria" existir, ela manda: ocorrido_em nunca pode ser depois dela."""


_RUINS = set()


def _modelo():
    """Escolhe o modelo Gemini disponível pra esta chave (pula os que deram 404 / saíram do plano grátis)."""
    global _MODELO
    if "_MODELO" in globals() and _MODELO not in _RUINS:
        return _MODELO
    pref = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest", "gemini-3.8-flash"]
    try:
        d = http("GET", f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}&pageSize=200")
        nomes = [m["name"].split("/")[-1] for m in d.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        cand = [p for p in pref if p in nomes and p not in _RUINS]
        cand += [n for n in sorted(nomes, reverse=True) if "flash" in n and not any(x in n for x in ("image", "tts", "live", "audio", "preview", "exp")) and n not in cand and n not in _RUINS]
        _MODELO = cand[0] if cand else next(p for p in pref if p not in _RUINS)
    except Exception:
        _MODELO = next((p for p in pref if p not in _RUINS), pref[0])
    return _MODELO


_ULTIMA = [0.0]


def _ritmo():
    """Free tier do Gemini tem poucos pedidos por minuto: espaça as chamadas: 10 s por processo, robo1+robo2 em paralelo somam ~12/min."""
    falta = 10 - (time.time() - _ULTIMA[0])
    if falta > 0:
        time.sleep(falta)
    _ULTIMA[0] = time.time()


def _contar(modelo, tipo):
    """Contador de chamadas ao Gemini por modelo, por dia do Pacífico (a cota diária zera à meia-noite de lá).
    Fica em ajf_estado.gemini_uso: {dia, modelos: {modelo: {texto, imagem, 429, 503}}}. Tentativas contam, mesmo as que falham."""
    try:
        dia = agora().astimezone(dt.timezone(dt.timedelta(hours=-8))).strftime("%Y-%m-%d")
        u = estado_ler("gemini_uso") or {}
        if u.get("dia") != dia:
            u = {"dia": dia, "modelos": {}}
        m = u["modelos"].setdefault(modelo, {})
        m[tipo] = m.get(tipo, 0) + 1
        estado_gravar("gemini_uso", u)
    except Exception as e:
        print("contador gemini falhou:", str(e)[:80])


def analisar(item, imagem=None):
    """Roda a IA sobre um candidato. Devolve dict de análise (com campo 'valido').
    imagem = (bytes, mime) opcional: o Gemini lê também o texto que aparece dentro da imagem (OCR, mesma cota)."""
    if not GEMINI_KEY:
        raise RuntimeError("Falta o secret GEMINI_API_KEY")
    dias = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
    br = agora().astimezone(dt.timezone(dt.timedelta(hours=-3)))
    prompt = PROMPT_ANALISE.format(hoje_br=f"{dias[br.weekday()]}, {br.strftime('%d/%m/%Y %H:%M')} (Brasília)", agora=agora().isoformat(timespec="minutes"), autor=item.get("autor", ""),
                                   publicado=item.get("publicado_em") or "desconhecido", legenda=(item.get("legenda") or "")[:3000])
    partes = [{"text": prompt}]
    if imagem:
        partes.append({"inline_data": {"mime_type": imagem[1], "data": __import__("base64").b64encode(imagem[0]).decode()}})
        partes[0]["text"] += ("\n\nIMAGEM ANEXA: leia o texto que aparece dentro dela (manchete, legenda sobreposta, placa) e use como texto do post. "
                             "Só vale se esse texto descrever ocorrência real de AGORA em Juiz de Fora com local identificável; "
                             "foto sem texto útil, print de previsão/alerta ou arte genérica => valido=false.")
    corpo = {"contents": [{"parts": partes}],
             "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
    if _GEMINI_ESGOTADO[0]:
        raise RuntimeError("Gemini esgotado nesta execução (429/503), análise pulada")
    if time.time() - _INICIO > ORCAMENTO_S:
        raise RuntimeError("orçamento de tempo da execução acabou, análise pulada")
    for tentativa in range(5):
        try:
            _ritmo()
            _m = _modelo()
            _contar(_m, "imagem" if imagem else "texto")
            d = http("POST", f"https://generativelanguage.googleapis.com/v1beta/models/{_m}:generateContent?key={GEMINI_KEY}", body=corpo, timeout=60)
            txt = d["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(txt)
        except RuntimeError as e:
            if "HTTP 404" in str(e) and _modelo() not in _RUINS:
                _RUINS.add(_modelo())
                print(f"modelo {_modelo()} indisponível; tentando outro")
                continue
            if "HTTP 429" in str(e) or "HTTP 503" in str(e):
                _contar(_modelo(), "429" if "HTTP 429" in str(e) else "503")
            if "HTTP 429" in str(e):
                # cada modelo tem a própria cota grátis: marca este como esgotado nesta execução e tenta o próximo da lista
                print("Gemini 429 no modelo", _modelo(), "|", str(e)[-260:].replace("\n", " "))
                _RUINS.add(_modelo())
                time.sleep(3)
                continue
            if "HTTP 503" in str(e):
                time.sleep(10 * (tentativa + 1))
                continue
            raise
    _GEMINI_ESGOTADO[0] = True  # não gasta o resto do tempo tentando item por item
    raise RuntimeError("Gemini indisponível/limite (429) em todos os modelos tentados")


_OCR_RODADA = [0]


def ocr_imagem(cfg, url):
    """Baixa a imagem pra IA ler o texto dela. Devolve (bytes, mime) ou None se desligado, sem cota ou sem imagem.
    Limites (fontes.json -> ocr): max_por_rodada e max_dia, pra não comer a cota grátis do Gemini."""
    o = (cfg or {}).get("ocr") or {}
    if not o.get("ativo") or not url or not GEMINI_KEY or _GEMINI_ESGOTADO[0]:
        return None
    if _OCR_RODADA[0] >= o.get("max_por_rodada", 12):
        return None
    dia = agora().astimezone(dt.timezone(dt.timedelta(hours=-3))).strftime("%Y-%m-%d")
    uso = estado_ler("ocr_uso") or {}
    if uso.get("dia") != dia:
        uso = {"dia": dia, "n": 0}
    if uso["n"] >= o.get("max_dia", 150):
        return None
    try:
        b = http("GET", url, {"Referer": "https://www.instagram.com/"}, timeout=30, raw=True)
    except Exception as e:
        print("ocr: imagem não baixou:", str(e)[:100])
        return None
    if not b or len(b) > 4_000_000:
        return None
    mime = "image/jpeg" if b[:3] == b"\xff\xd8\xff" else "image/png" if b[:8] == b"\x89PNG\r\n\x1a\n" else "image/webp" if b[:4] == b"RIFF" and b[8:12] == b"WEBP" else None
    if not mime:
        return None
    _OCR_RODADA[0] += 1
    uso["n"] += 1  # conta antes da chamada: se cair no meio, o gasto já está contado
    estado_gravar("ocr_uso", uso)
    return (b, mime)


def validar_analise(a):
    """Regras duras aplicadas em código, além do que a IA respondeu. Devolve (ok, motivo)."""
    if not a.get("valido"):
        return False, a.get("motivo") or "IA marcou como inválido"
    if a.get("tipo") not in ("alagamento", "deslizamento", "enxurrada", "interdicao", "sem_luz"):
        return False, "tipo inválido"
    if not (a.get("rua") or a.get("bairro")):
        return False, "sem local"
    try:
        conf = float(a.get("confianca") or 0)
    except (TypeError, ValueError):  # a IA às vezes devolve "alta" ou "0,8"
        return False, "confiança inválida"
    if conf < 0.6:
        return False, "confiança baixa"
    try:
        t = dt.datetime.fromisoformat(a["ocorrido_em"].replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return False, "sem horário do ocorrido"
    idade = agora() - t
    if idade > dt.timedelta(hours=JANELA_HORAS - 0.25) or idade < dt.timedelta(minutes=-5):
        return False, "fora da janela de 2h (chuva atual)"
    return True, ""


# ---------- geocodificação ----------
def _bairros():
    return json.load(open(os.path.join(AQUI, "bairros.json"), encoding="utf-8"))


def _norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()


def ponto_em_jf(lat, lon):
    """True se o ponto está dentro do polígono do município (mesmo de src/lib/raios.ts)."""
    pts = json.load(open(os.path.join(AQUI, "jf_poligono.json")))["pontos"]
    dentro, j = False, len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def _nominatim(q, limit=1):
    u = ("https://nominatim.openstreetmap.org/search?format=json&limit=%d&countrycodes=br" % limit
         + f"&viewbox={JF_BBOX[2]},{JF_BBOX[1]},{JF_BBOX[3]},{JF_BBOX[0]}&bounded=1&q=" + urllib.parse.quote(q))
    time.sleep(1.1)  # política de uso: 1 requisição por segundo
    r = http("GET", u) or []
    return [(float(x["lat"]), float(x["lon"])) for x in r if ponto_em_jf(float(x["lat"]), float(x["lon"]))]


def geocodificar_info(rua, bairro, referencia=""):
    """{lat, lon, bairro, aproximado} ou None. Prioriza ponto de referência/bairro citado; rua sem nada disso
    é a rua certa com trecho incerto (aproximado=True), nunca um ponto exato inventado."""
    b_norm = _norm(bairro or "")
    centro = next((b for b in _bairros() if _norm(b["nome"]) == b_norm), None)
    nome_b = centro["nome"] if centro else (bairro or "Juiz de Fora")
    consultas = []
    if rua and referencia:
        consultas.append(([rua, referencia, bairro], False))
    if referencia and not rua:
        consultas.append(([referencia, bairro], False))
    if rua:
        consultas.append(([rua, bairro], not bairro))  # sem bairro nem referência: trecho incerto
    for partes, aprox in consultas:
        q = ", ".join(x for x in partes + ["Juiz de Fora", "MG", "Brasil"] if x)
        try:
            pts = _nominatim(q)
        except Exception as e:
            print("nominatim falhou:", e)
            continue
        if pts:
            return {"lat": pts[0][0], "lon": pts[0][1], "bairro": nome_b, "aproximado": aprox}
    if centro:
        return {"lat": centro["lat"], "lon": centro["lon"], "bairro": centro["nome"], "aproximado": True}
    return None


def geocodificar(rua, bairro, referencia=""):
    """(lat, lon, bairro_final) ou None (compatível com os chamadores antigos)."""
    g = geocodificar_info(rua, bairro, referencia)
    return (g["lat"], g["lon"], g["bairro"]) if g else None
