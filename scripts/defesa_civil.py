#!/usr/bin/env python3
"""Baixa o feed CAP da IDAP (Defesa Civil Alerta) e guarda os alertas que valem para Juiz de Fora.

Uso: python scripts/defesa_civil.py [arquivo_xml_local]
Saída: public/defesa-civil.json (só é reescrito se o conteúdo mudar).
"""
import json, os, re, subprocess, sys, tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

FEED = "https://idapfile.mdr.gov.br/idap/api/rss/cap"
GEOCODE_JF = "3136702"
JF = (-21.7642, -43.3503)  # lat, lon
SAIDA = os.path.join(os.path.dirname(__file__), "..", "public", "defesa-civil.json")
CAP = "{urn:oasis:names:tc:emergency:cap:1.2}"
CANCELADOS = set()  # ids de alertas cancelados no feed
MAX_ALERTAS = 5
GUARDAR_DIAS = 7


def ponto_em_poligono(lat, lon, pts):
    dentro = False
    j = len(pts) - 1
    for i in range(len(pts)):
        yi, xi = pts[i]
        yj, xj = pts[j]
        if (xi > lon) != (xj > lon) and lat < (yj - yi) * (lon - xi) / (xj - xi) + yi:
            dentro = not dentro
        j = i
    return dentro


def poligonos(area):
    for p in area.findall(CAP + "polygon"):
        try:
            yield [tuple(float(v) for v in par.split(",")) for par in (p.text or "").split()]
        except ValueError:
            continue


def _poligono_jf():
    """Polígono do município (pares lat, lon), o mesmo de src/lib/raios.ts."""
    arq = os.path.join(os.path.dirname(__file__), "..", "robos", "jf_poligono.json")
    return [(la, lo) for lo, la in json.load(open(arq))["pontos"]]


def _cruzam(p1, p2, p3, p4):
    def o(a, b, c):
        return (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    return (o(p1, p2, p3) > 0) != (o(p1, p2, p4) > 0) and (o(p3, p4, p1) > 0) != (o(p3, p4, p2) > 0)


def poligonos_se_tocam(a, b):
    """True se dois polígonos (lat, lon) se tocam: algum vértice de um dentro do outro, ou arestas que se cruzam."""
    if any(ponto_em_poligono(la, lo, b) for la, lo in a) or any(ponto_em_poligono(la, lo, a) for la, lo in b):
        return True
    for i in range(len(a)):
        for j in range(len(b)):
            if _cruzam(a[i], a[(i + 1) % len(a)], b[j], b[(j + 1) % len(b)]):
                return True
    return False


def vale_para_jf(info):
    jf = _poligono_jf()
    for area in info.findall(CAP + "area"):
        for g in area.findall(CAP + "geocode"):
            if (g.findtext(CAP + "value") or "").strip() == GEOCODE_JF:
                return True
        for pts in poligonos(area):
            # alerta cobrindo só parte do município também vale: basta o polígono tocar o município
            if len(pts) >= 3 and (ponto_em_poligono(JF[0], JF[1], pts) or poligonos_se_tocam(pts, jf)):
                return True
    return False


def t(el, tag):
    return (el.findtext(CAP + tag) or "").strip()


def _data(v):
    """Data ISO com fuso em UTC, ou None se vier vazia/malformada."""
    try:
        d = datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def ler(caminho):
    achados = []
    for _, el in ET.iterparse(caminho, events=("end",)):
        if el.tag != CAP + "alert":
            continue
        if t(el, "status") != "Actual":
            el.clear()
            continue
        if t(el, "msgType") == "Cancel":
            # "Cancel" derruba o alerta original: <references> = "remetente,identificador,enviado"
            for ref in t(el, "references").split():
                partes = ref.split(",")
                if len(partes) >= 2:
                    CANCELADOS.add(partes[1])
            el.clear()
            continue
        for info in el.findall(CAP + "info"):
            if vale_para_jf(info):
                achados.append({
                    "id": t(el, "identifier"),
                    "evento": t(info, "event"),
                    "texto": (t(info, "description") or t(info, "headline")).replace("Defesa Civil:", "").strip(),
                    "emitido": t(el, "sent"),
                    "expira": t(info, "expires"),
                    "severidade": t(info, "severity"),
                    "origem": t(info, "senderName") or "Defesa Civil",
                })
                break
        el.clear()
    return achados


def cabecalho_feed(caminho):
    """Lê o <updated> do cabeçalho Atom do feed (quando a fonte foi atualizada pela última vez)."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as f:
            m = re.search(r"<updated>([^<]+)</updated>", f.read(4096))
        return m.group(1).strip() if m else None
    except OSError:
        return None


def baixar():
    tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False).name
    subprocess.run(["curl", "-sS", "--fail", "--compressed", "-m", "280", "-A", "alertajf/1.0 (+https://alertajf.vercel.app)", "-o", tmp, FEED], check=True)
    return tmp


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else baixar()
    novos = ler(caminho)
    feed_atualizado = cabecalho_feed(caminho)
    antigos = []
    fonte_atualizada_antiga = None
    if os.path.exists(SAIDA):
        try:
            dados = json.load(open(SAIDA, encoding="utf-8"))
            antigos = dados.get("alertas", [])
            fonte_atualizada_antiga = dados.get("fonte_atualizada_em")
        except Exception:
            antigos = []
    por_id = {a["id"]: a for a in antigos}
    por_id.update({a["id"]: a for a in novos})
    for cid in CANCELADOS:
        por_id.pop(cid, None)  # alerta cancelado sai do arquivo
    agora_utc = datetime.now(timezone.utc)
    corte = agora_utc - timedelta(days=GUARDAR_DIAS)
    lista = []
    for a in por_id.values():
        # um alerta com data ruim é pulado sozinho; nunca congela o arquivo inteiro
        emitido = _data(a.get("emitido"))
        if emitido is None or emitido < corte:
            continue
        exp = _data(a.get("expira"))
        if exp is not None and exp < agora_utc:  # vencido não fica como atual
            continue
        lista.append((emitido, a))
    lista.sort(key=lambda x: x[0], reverse=True)
    lista = [a for _, a in lista]
    saida = {"fonte": "Defesa Civil Alerta (IDAP/MIDR)", "fonte_atualizada_em": feed_atualizado or fonte_atualizada_antiga, "alertas": lista[:MAX_ALERTAS]}
    novo = json.dumps(saida, ensure_ascii=False, indent=2) + "\n"
    if os.path.exists(SAIDA) and open(SAIDA, encoding="utf-8").read() == novo:
        print("sem mudanças")
        return
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    open(SAIDA, "w", encoding="utf-8").write(novo)
    print(f"{len(lista)} alertas, mais recente: {lista[0]['emitido'] if lista else '-'}")


if __name__ == "__main__":
    main()
