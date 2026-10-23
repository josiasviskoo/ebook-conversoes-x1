#!/usr/bin/env python3
"""Gera o ebook "Método X1 — Vendas no 1 a 1" (Viskoo) em HTML e PDF.

Fluxo: capitulos/*.md -> pré-processamento (balões, caixas, partes) -> HTML
-> PDF via Google Chrome headless. Roda duas vezes para preencher o número
das páginas no sumário.

Uso: python3 ebook/build.py
"""
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
CAPITULOS = ROOT / "capitulos"
DIST = ROOT / "dist"
NOME_PDF = "metodo-x1-vendas-no-1a1-viskoo.pdf"
RODAPE = "E-book de Conversões no X1 da Viskoo para empresas que vendem no X1"
# Ícone laranja da Viskoo; nas páginas claras entra pelo @page do CSS,
# nas escuras (capa, contracapa, partes) entra por este elemento.
ICONE = (ROOT / "assets" / "icone-viskoo.svg").read_text(encoding="utf-8").replace(
    "<svg ", '<svg class="icone-canto" aria-hidden="true" ', 1)

CALLOUTS = {
    "dica": "💡 Dica",
    "cuidado": "⚠️ Cuidado",
    "framework": "🧩 Framework",
    "exercicio": "🏋️ Exercício",
    "template": "📋 Template",
    "pratica": "🎯 Na prática",
    "resumo": "📌 Resumo em 3 linhas",
    "aplicar": "🚀 Para aplicar hoje",
    "destaque": "",
}

ROTULOS_CHAT = {
    "nao": ("❌ Não faça", "nao"),
    "sim": ("✅ Faça", "sim"),
    "ex": ("💬 Exemplo", "ex"),
}


def inline(texto):
    """Formatação mínima dentro dos balões: **negrito**, *itálico*, quebras."""
    t = html.escape(texto)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", t)
    return t.replace("\n", "<br>")


def onda(seed):
    alturas = [30, 55, 80, 45, 95, 60, 35, 70, 90, 50, 25, 65, 85, 40, 75, 55, 30, 60, 45, 20]
    k = seed % len(alturas)
    barras = alturas[k:] + alturas[:k]
    return "".join(f'<i style="height:{h}%"></i>' for h in barras)


def render_chat(variante, linhas, seed):
    rotulo, classe = ROTULOS_CHAT.get(variante, ROTULOS_CHAT["ex"])
    contato, hora = "Cliente", 9 * 60 + 12 + (seed * 37) % 400
    itens, nota = [], []

    for bruta in linhas:
        if not bruta.strip():
            continue
        if bruta.startswith("@hora "):
            h, m = bruta[6:].strip().split(":")
            hora = int(h) * 60 + int(m)
            continue
        if bruta.startswith("@ "):
            contato = bruta[2:].strip()
            continue
        if bruta.startswith("? "):
            nota.append(bruta[2:].strip())
            continue
        if bruta.startswith("* "):
            itens.append(("sistema", bruta[2:].strip(), None))
            continue
        m = re.match(r"^([CV])(~|\[[^\]]*\]|:)\s?(.*)$", bruta)
        if m:
            quem, tipo, txt = m.groups()
            itens.append(("msg", (quem, tipo, txt), None))
        elif itens and itens[-1][0] == "msg":
            quem, tipo, txt = itens[-1][1]
            itens[-1] = ("msg", (quem, tipo, txt + "\n" + bruta.strip()), None)
        elif nota:
            nota[-1] += " " + bruta.strip()

    corpo = []
    for n, (kind, dado, _) in enumerate(itens):
        if kind == "sistema":
            corpo.append(f'<div class="wa-sistema">{inline(dado)}</div>')
            hora += 90
            continue
        quem, tipo, txt = dado
        hora += 1 if n else 0
        hh = f"{(hora // 60) % 24:02d}:{hora % 60:02d}"
        lado = "out" if quem == "V" else "in"
        checks = '<span class="wa-check">✓✓</span>' if lado == "out" else ""
        meta = f'<span class="wa-meta">{hh}{checks}</span>'
        if tipo == "~":
            dur, _, transc = txt.partition("|")
            conteudo = (
                f'<div class="wa-audio"><span class="wa-play">▶</span>'
                f'<span class="wa-onda">{onda(seed + n)}</span>'
                f'<span class="wa-dur">{html.escape(dur.strip())}</span></div>'
            )
            if transc.strip():
                conteudo += f'<div class="wa-transc">🎤 {inline(transc.strip())}</div>'
        elif tipo.startswith("["):
            icone = tipo[1:-1] or "📄"
            conteudo = f'<div class="wa-anexo"><span>{icone}</span>{inline(txt)}</div>'
        else:
            conteudo = inline(txt)
        corpo.append(f'<div class="wa-msg {lado}">{conteudo}{meta}</div>')

    nota_html = ""
    if nota:
        nota_html = f'<div class="wa-nota">{inline(" ".join(nota))}</div>'
    inicial = html.escape(contato.strip()[:1].upper())
    return (
        f'<figure class="wa {classe}">'
        f'<figcaption class="wa-rotulo">{rotulo}</figcaption>'
        f'<div class="wa-tela">'
        f'<div class="wa-topo"><span class="wa-avatar">{inicial}</span>'
        f'<span class="wa-contato">{html.escape(contato)}</span><span class="wa-online">online</span></div>'
        f'<div class="wa-corpo">{"".join(corpo)}</div></div>{nota_html}</figure>'
    )


def rotulo_parte(num):
    return f"Parte {num}" if num.isdigit() else num


def slug(t):
    t = re.sub(r"[^\w\s-]", "", t.lower())
    return re.sub(r"\s+", "-", t).strip("-")[:60]


def preprocessar(texto, toc, contador):
    saida, i = [], 0
    linhas = texto.split("\n")
    while i < len(linhas):
        linha = linhas[i]

        m = re.match(r"<!-- PARTE: (.+?) \| (.+?) \| (.+?) -->", linha)
        if m:
            num, titulo, sub = (x.strip() for x in m.groups())
            pid = f"parte-{slug(num)}"
            toc.append(("parte", pid, num, titulo))
            saida.append(
                f'<section class="parte" id="{pid}">{ICONE}<div class="parte-x">X1</div>'
                f'<p class="parte-num">{html.escape(rotulo_parte(num))}</p>'
                f'<h1 class="parte-titulo">{html.escape(titulo)}</h1>'
                f'<p class="parte-sub">{html.escape(sub)}</p>'
                f'<p class="rodape-escuro">{html.escape(RODAPE)}</p>'
                f'<span class="pdf-marker">@@{pid}@@</span></section>'
            )
            i += 1
            continue

        m = re.match(r"^# (.+)$", linha)
        if m:
            titulo = m.group(1).strip()
            mnum = re.match(r"^(\d+)\.\s+(.+)$", titulo)
            mane = re.match(r"^Anexo ([A-Z])\s+[—-]\s+(.+)$", titulo)
            if mnum:
                num, titulo = mnum.groups()
                eyebrow, rot = f"Capítulo {int(num):02d}", f"{int(num):02d}"
            elif mane:
                num, titulo = mane.groups()
                eyebrow, rot = f"Anexo {num}", num
            else:
                eyebrow, rot = "", ""
            cid = f"c-{slug(titulo)}"
            toc.append(("cap", cid, rot, titulo))
            eb = f'<p class="cap-eyebrow">{eyebrow}</p>' if eyebrow else ""
            saida.append(
                f'<header class="capitulo" id="{cid}">{eb}'
                f'<h1>{html.escape(titulo)}</h1><span class="pdf-marker">@@{cid}@@</span></header>'
            )
            i += 1
            continue

        m = re.match(r"^```whatsapp\s*(\w*)\s*$", linha)
        if m:
            bloco = []
            i += 1
            while i < len(linhas) and not linhas[i].startswith("```"):
                bloco.append(linhas[i])
                i += 1
            contador[0] += 1
            saida += ["", render_chat(m.group(1), bloco, contador[0]), ""]
            i += 1
            continue

        m = re.match(r"^::::\s*comparar\s*$", linha)
        if m:
            saida += ["", '<div class="comparar" markdown="1">', ""]
            i += 1
            continue
        if linha.strip() == "::::":
            saida += ["", "</div>", ""]
            i += 1
            continue

        m = re.match(r"^:::\s*(\w+)\s*(.*)$", linha)
        if m and m.group(1) in CALLOUTS:
            tipo, titulo = m.group(1), m.group(2).strip()
            rotulo = CALLOUTS[tipo]
            if titulo:
                rotulo = f"{rotulo} · {titulo}" if rotulo else titulo
            cab = f'<p class="callout-rotulo">{html.escape(rotulo)}</p>' if rotulo else ""
            saida += ["", f'<div class="callout {tipo}" markdown="1">', cab, ""]
            i += 1
            continue
        if linha.strip() == ":::":
            saida += ["", "</div>", ""]
            i += 1
            continue

        # Python-Markdown só reconhece listas precedidas de linha em branco.
        item = re.compile(r"^\s*([-*]|\d+\.)\s")
        if item.match(linha) and saida and saida[-1].strip() and not item.match(saida[-1]):
            saida.append("")
        saida.append(linha)
        i += 1
    return "\n".join(saida)


def montar_toc(toc, paginas):
    itens = []
    for tipo, cid, rot, titulo in toc:
        pg = paginas.get(cid, "")
        if tipo == "parte":
            itens.append(
                f'<li class="toc-parte"><a href="#{cid}"><span class="toc-rot">{html.escape(rotulo_parte(rot))}</span>'
                f'<span class="toc-tit">{html.escape(titulo)}</span><span class="toc-pg">{pg}</span></a></li>'
            )
        else:
            itens.append(
                f'<li class="toc-cap"><a href="#{cid}"><span class="toc-rot">{rot}</span>'
                f'<span class="toc-tit">{html.escape(titulo)}</span><span class="toc-pg">{pg}</span></a></li>'
            )
    return f'<section class="sumario"><p class="cap-eyebrow">Mapa do livro</p><h1>Sumário</h1><ol>{"".join(itens)}</ol></section>'


def montar_html(paginas):
    toc, contador, corpo = [], [0], []
    md = markdown.Markdown(extensions=["tables", "md_in_html", "sane_lists", "attr_list"])
    for arq in sorted(CAPITULOS.glob("*.md")):
        md.reset()
        corpo.append(md.convert(preprocessar(arq.read_text(encoding="utf-8"), toc, contador)))
    capa = (ROOT / "capa.html").read_text(encoding="utf-8").replace("<!--ICONE-->", ICONE)
    contracapa = (ROOT / "contracapa.html").read_text(encoding="utf-8").replace("<!--ICONE-->", ICONE)
    css = (ROOT / "estilo.css").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Método X1 — Vendas no 1 a 1 | Viskoo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&family=Inter:ital,wght@0,400;0,500;0,600;0,700;1,400&display=block" rel="stylesheet">
<style>{css}</style></head><body>
{capa}
{montar_toc(toc, paginas)}
<main>{"".join(corpo)}</main>
{contracapa}
</body></html>"""


def imprimir(html_path, pdf_path):
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        sys.exit("Google Chrome/Chromium não encontrado.")
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             "--generate-pdf-document-outline", f"--user-data-dir={perfil}",
             "--virtual-time-budget=20000", f"--print-to-pdf={pdf_path}", html_path.as_uri()],
            check=True, capture_output=True,
        )


def localizar_paginas(pdf_path):
    info = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True).stdout
    total = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    paginas = {}
    for p in range(1, total + 1):
        txt = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), str(pdf_path), "-"],
                             capture_output=True, text=True).stdout
        for cid in re.findall(r"@@([\w-]+)@@", txt):
            paginas.setdefault(cid, p)
    return paginas, total


def main():
    DIST.mkdir(exist_ok=True)
    html_path, pdf_path = DIST / "ebook.html", DIST / NOME_PDF
    paginas = {}
    for passada in (1, 2):
        html_path.write_text(montar_html(paginas), encoding="utf-8")
        imprimir(html_path, pdf_path)
        novas, total = localizar_paginas(pdf_path)
        if novas == paginas:
            break
        paginas = novas
    print(f"OK: {pdf_path} ({total} páginas, {len(paginas)} capítulos/partes localizados)")


if __name__ == "__main__":
    main()
