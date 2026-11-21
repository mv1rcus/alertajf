#!/usr/bin/env python3
"""Baixa o feed CAP da IDAP (Defesa Civil Alerta) e guarda os alertas que valem para Juiz de Fora.

Uso: python scripts/defesa_civil.py [arquivo_xml_local]
Saída: public/defesa-civil.json (só é reescrito se o conteúdo mudar).
"""
import json, os, subprocess, sys, tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

FEED = "https://idapfile.mdr.gov.br/idap/api/rss/cap"
GEOCODE_JF = "3136702"
JF = (-21.7642, -43.3503)  # lat, lon
SAIDA = os.path.join(os.path.dirname(__file__), "..", "public", "defesa-civil.json")
CAP = "{urn:oasis:names:tc:emergency:cap:1.2}"
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


def vale_para_jf(info):
    for area in info.findall(CAP + "area"):
        for g in area.findall(CAP + "geocode"):
            if (g.findtext(CAP + "value") or "").strip() == GEOCODE_JF:
                return True
        for pts in poligonos(area):
            if len(pts) >= 3 and ponto_em_poligono(JF[0], JF[1], pts):
                return True
    return False


def t(el, tag):
    return (el.findtext(CAP + tag) or "").strip()


def ler(caminho):
    achados = []
    for _, el in ET.iterparse(caminho, events=("end",)):
        if el.tag != CAP + "alert":
            continue
        if t(el, "status") != "Actual" or t(el, "msgType") == "Cancel":
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


def baixar():
    tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False).name
    subprocess.run(["curl", "-sS", "--fail", "--compressed", "-m", "280", "-A", "alertajf/1.0 (+https://alertajf.vercel.app)", "-o", tmp, FEED], check=True)
    return tmp


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else baixar()
    novos = ler(caminho)
    antigos = []
    if os.path.exists(SAIDA):
        try:
            antigos = json.load(open(SAIDA, encoding="utf-8")).get("alertas", [])
        except Exception:
            antigos = []
    por_id = {a["id"]: a for a in antigos}
    por_id.update({a["id"]: a for a in novos})
    corte = (datetime.now(timezone.utc) - timedelta(days=GUARDAR_DIAS)).isoformat()
    lista = [a for a in por_id.values() if datetime.fromisoformat(a["emitido"]).astimezone(timezone.utc).isoformat() >= corte]
    lista.sort(key=lambda a: datetime.fromisoformat(a["emitido"]), reverse=True)
    saida = {"fonte": "Defesa Civil Alerta (IDAP/MIDR)", "alertas": lista[:MAX_ALERTAS]}
    novo = json.dumps(saida, ensure_ascii=False, indent=2) + "\n"
    if os.path.exists(SAIDA) and open(SAIDA, encoding="utf-8").read() == novo:
        print("sem mudanças")
        return
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    open(SAIDA, "w", encoding="utf-8").write(novo)
    print(f"{len(lista)} alertas, mais recente: {lista[0]['emitido'] if lista else '-'}")


if __name__ == "__main__":
    main()
