"""ROBÔ 2: varre o Google Notícias (RSS, sem login) e links de Instagram citados, analisa com IA e enfileira."""
import json, os, re, sys, urllib.parse, datetime as dt, email.utils
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
        yield dict(titulo=titulo, link=(i.findtext("link") or ""), data=i.findtext("pubDate"), resumo=resumo, fonte=nome)


def main():
    if not c.esta_chovendo():
        c.log_robo("robo2_noticias", True, "sem chuva nem previsão, dormindo")
        return 0
    fontes = json.load(open(os.path.join(c.AQUI, "fontes.json")))
    buscas = fontes["noticias_buscas"]
    limite = c.agora() - dt.timedelta(hours=c.JANELA_HORAS)
    vistos, novos, aprov = set(), 0, 0
    fim = c.agora() + dt.timedelta(minutes=9)  # orçamento de tempo do robô
    fontes_feed = [(b, lambda b=b: feed(b)) for b in buscas]
    fontes_feed += [(nome, lambda n=nome, u=url: feed_local(n, u)) for nome, url in fontes.get("rss_locais", [])]
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
            it = dict(origem="noticias", post_id=re.sub(r"\W+", "", n["link"])[-60:], autor=n["fonte"] or "Google Notícias",
                      url=n["link"], legenda=f'{n["titulo"]}\n{n["resumo"]}'.strip(), publicado_em=pub.isoformat(), eh_video=False)
            try:
                a = c.analisar(it)
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
