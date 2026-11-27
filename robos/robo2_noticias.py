"""ROBÔ 2: varre o Google Notícias (RSS, sem login) e links de Instagram citados, analisa com IA e enfileira."""
import json, os, re, sys, urllib.parse, datetime as dt, email.utils, html as html_lib
import xml.etree.ElementTree as ET
import common as c


def feed(busca):
    u = "https://news.google.com/rss/search?hl=pt-BR&gl=BR&ceid=BR:pt-419&q=" + urllib.parse.quote(busca + " when:1d")
    root = ET.fromstring(c.http("GET", u, raw=True))
    for i in root.iter("item"):
        yield dict(titulo=(i.findtext("title") or ""), link=(i.findtext("link") or ""),
                   data=i.findtext("pubDate"), resumo=re.sub(r"<[^>]+>", " ", i.findtext("description") or ""),
                   fonte=(i.findtext("source") or ""))


PALAVRAS = re.compile(r"chuv|alag|deslizament|enxurrad|temporal|interdi|barranco|queda de [aá]rvore|sem luz|sem energia|inunda|transbord", re.I)


def data_real(url):
    """Data real da matéria lida da própria página (article:published_time, JSON-LD datePublished). None se não der para ler.
    Links do Google Notícias não abrem sem redirecionamento: devolvem None e a IA só aprova se o texto disser 'agora'."""
    if "news.google.com" in url:
        return None
    try:
        h = c.http("GET", url, {"Accept": "text/html"}, raw=True, timeout=25)[:400000].decode("utf-8", "replace")
    except Exception:
        return None
    achados = re.findall(r'(?:article:published_time|og:published_time|datePublished|article:modified_time)["\']?\s*(?:content=|:)\s*["\']([0-9T:+\-.Z]{10,35})', h) or \
        re.findall(r'"datePublished"\s*:\s*"([^"]+)"', h)
    datas = []
    for a in achados:
        try:
            d = dt.datetime.fromisoformat(a.replace("Z", "+00:00"))
            datas.append(d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc))
        except ValueError:
            continue
    return min(datas).astimezone(dt.timezone.utc) if datas else None  # a mais antiga: published, não a atualização


def imagem_do_item(i):
    """URL da imagem do item do RSS (enclosure, media:content/thumbnail ou primeira <img>). Vazio se não houver."""
    for el in i.iter():
        tag = el.tag.split("}")[-1]
        u = el.get("url") or ""
        if tag in ("content", "thumbnail", "enclosure") and u.startswith("http"):
            t = (el.get("type") or el.get("medium") or "").lower()
            if tag == "thumbnail" or "image" in t or re.search(r"\.(jpe?g|png|webp)(\?|$)", u, re.I):
                return u
    raw = ET.tostring(i, encoding="unicode")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw) or re.search(r'&lt;img[^&]*?src=(?:&quot;|["\'])([^"\'&]+)', raw)
    return m.group(1) if m and m.group(1).startswith("http") else ""


def feed_local(nome, url):
    """RSS direto de veículo local (grátis, sem login). Só entram itens com palavra de chuva; G1 só se citar Juiz de Fora."""
    root = ET.fromstring(c.http("GET", url, raw=True))
    for i in root.iter("item"):
        titulo = i.findtext("title") or ""
        resumo = re.sub(r"<[^>]+>", " ", i.findtext("description") or "")
        texto = f"{titulo} {resumo}"
        if not PALAVRAS.search(texto):
            continue
        if "g1.globo" in url and "juiz de fora" not in texto.lower():
            continue
        yield dict(titulo=titulo, link=(i.findtext("link") or ""), data=i.findtext("pubDate"), resumo=resumo, fonte=nome, imagem=imagem_do_item(i))


def feed_telegram(nome, url):
    """Canal publico de Telegram lido pela pagina web (t.me/s/<canal>), sem login e sem cota.
    So entram mensagens com palavra de chuva; o filtro pesado fica com a IA como nos outros feeds."""
    doc = c.http("GET", url, raw=True, timeout=40).decode("utf-8", "replace")
    for parte in re.split(r'(?=data-post=")', doc):
        m = re.match(r'data-post="([A-Za-z0-9_]+)/(\d+)"', parte)
        if not m:
            continue
        canal, num = m.group(1), m.group(2)
        t = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', parte, re.S)
        texto = re.sub(r"<[^>]+>", " ", t.group(1)) if t else ""
        texto = html_lib.unescape(re.sub(r"\s+", " ", texto)).strip()
        if not texto or not PALAVRAS.search(texto):
            continue
        d = re.search(r'<time datetime="([^"]+)"', parte)
        if not d:
            continue
        try:
            pub = dt.datetime.fromisoformat(d.group(1)).astimezone(dt.timezone.utc)
        except ValueError:
            continue
        img = re.search(r"background-image:url\('([^']+)'\)", parte)
        yield dict(titulo=texto[:180], link="https://t.me/%s/%s" % (canal, num),
                   data=email.utils.format_datetime(pub), resumo=texto, fonte=nome,
                   imagem=(img.group(1) if img else ""))


def main():
    if not c.portao_aberto():
        c.log_robo("robo2_noticias", True, "sem chuva nem previsão, dormindo")
        return 0
    fontes = json.load(open(os.path.join(c.AQUI, "fontes.json")))
    buscas = fontes["noticias_buscas"]
    limite = c.agora() - dt.timedelta(hours=c.JANELA_HORAS)
    vistos, novos, aprov = set(), 0, 0
    fim = c.agora() + dt.timedelta(minutes=9)  # orçamento de tempo do robô
    fontes_feed = [(b, lambda b=b: feed(b)) for b in buscas]
    fontes_feed += [(nome, lambda n=nome, u=url: feed_local(n, u)) for nome, url in fontes.get("rss_locais", [])]
    fontes_feed += [(nome, lambda n=nome, u=url: feed_telegram(n, u)) for nome, url in fontes.get("telegram_canais", [])]
    for b, gerar in fontes_feed:
        try:
            itens = list(gerar())
        except Exception as e:
            print("feed falhou:", b, e)
            continue
        for n in itens:
            if c.agora() > fim:
                break
            if n["link"] in vistos:
                continue
            vistos.add(n["link"])
            try:
                pub = email.utils.parsedate_to_datetime(n["data"]).astimezone(dt.timezone.utc)
            except Exception:
                continue
            if pub < limite:
                continue
            real = data_real(n["link"])
            if real is not None and real < limite:
                print("descartado: matéria de", real.isoformat(), "mais velha que a janela, mesmo com data nova no feed:", n["link"][:80])
                continue
            extra = f"\nData real da matéria: {real.isoformat()}" if real else "\nData real da matéria: não foi possível ler (suspeito: só vale se o texto disser que é agora)"
            it = dict(origem="noticias", post_id=re.sub(r"\W+", "", n["link"])[-60:], autor=n["fonte"] or "Google Notícias",
                      url=n["link"], legenda=f'{n["titulo"]}\n{n["resumo"]}'.strip() + extra, publicado_em=pub.isoformat(), eh_video=False, midia_url=n.get("imagem") or None)
            try:
                if c.ja_na_fila(it):
                    continue
                a = c.analisar(it)
                if real is not None:  # o fato não pode ser depois da publicação real
                    try:
                        oc = dt.datetime.fromisoformat(str(a.get("ocorrido_em")).replace("Z", "+00:00"))
                        if oc.tzinfo is None:
                            oc = oc.replace(tzinfo=dt.timezone.utc)
                        if oc > real:
                            a["ocorrido_em"] = real.isoformat()
                    except ValueError:
                        pass
                ok, motivo = c.validar_analise(a)
                it.update(analise=a, estado="analisado" if ok else "descartado", motivo=motivo or None)
                if c.fila_inserir(it):
                    novos += 1
                    aprov += ok
            except Exception as e:
                print("candidato falhou:", it["post_id"], e)
    c.log_robo("robo2_noticias", True, f"{novos} novos candidatos, {aprov} aprovados pela IA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
