#!/usr/bin/env python3
"""Gera o PDF de PRODUÇÃO (gráfica) do livro "Método X1: Vendas no 1 a 1".

Segue o gabarito da editora (Editora/livro-com-64-paginas-4x140x210mm-1x1-com-orelha-sulfite.pdf):

  pág. 1      capa aberta 554 x 216 mm (com 3 mm de sangria): orelha 130 | 4ª capa 142 |
              lombada 4 | 1ª capa 142 | orelha 130 — COLORIDA (convertida para CMYK)
  págs. 2-65  miolo, 64 páginas de 146 x 216 mm (140 x 210 mm + 3 mm de sangria),
              mancha 110 x 185 mm, margem interna 20 mm, externa 10 mm, topo 10 mm,
              faixa de rodapé de 9 mm — 1x1 ESCALA DE CINZA (convertido para DeviceGray)

Uso:  python3 ebook/producao/build_producao.py
      (requer Python com markdown e pymupdf, Google Chrome, Ghostscript e poppler-utils)
Saída: SAIDA/metodo-x1-producao-140x210-64p.pdf
"""
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

AQUI = Path(__file__).resolve().parent
EBOOK = AQUI.parent
RAIZ = EBOOK.parent
sys.path.insert(0, str(EBOOK))
from build import render_chat, slug  # noqa: E402  (reaproveita os balões do ebook digital)

CAPITULOS = AQUI / "capitulos"
TMP = AQUI / "tmp"
SAIDA = RAIZ / "SAIDA"
NOME_FINAL = "metodo-x1-producao-140x210-64p.pdf"
PAGINAS_MIOLO = 64

# Fontes ESTÁTICAS locais (as variáveis do Google Fonts sairiam como Type 3 no PDF, o que a gráfica rejeita)
FONTES = f'<link rel="stylesheet" href="{(AQUI / "fonts" / "fontes.css").as_uri()}">'
MM = 72 / 25.4
SANGRIA = 3 * MM
ICONE_SVG = (EBOOK / "assets" / "icone-viskoo.svg").read_text(encoding="utf-8")
LOGO_PRETO = re.sub(r'<svg[^>]*>', '<svg viewBox="47 59 907 166.5" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Viskoo">',
                    (Path(__file__).parent / "assets" / "viskoo-logo-branco.svg").read_text(encoding="utf-8"), count=1
                    ).replace('fill="white"', 'fill="#000000"')

CALLOUTS = {
    "dica": "Dica", "cuidado": "Cuidado", "framework": "Framework", "exercicio": "Exercício",
    "template": "Modelo", "pratica": "Na prática", "resumo": "Resumo", "aplicar": "Para aplicar hoje",
    "destaque": "",
}


MARCAS = []  # id do capítulo/parte -> marcador só com dígitos (o pdftotext lê melhor que acentos)


def marcador(cid):
    if cid not in MARCAS:
        MARCAS.append(cid)
    return f"@@{MARCAS.index(cid) + 100}@@"


def rotulo_parte(num):
    return f"Parte {num}" if num.isdigit() else num


def preprocessar(texto, toc, contador):
    saida, i = [], 0
    linhas = texto.split("\n")
    item = re.compile(r"^\s*([-*]|\d+\.)\s")
    while i < len(linhas):
        linha = linhas[i]

        m = re.match(r"<!-- PARTE: (.+?) \| (.+?) \| (.+?) -->", linha)
        if m:
            num, titulo, sub = (x.strip() for x in m.groups())
            pid = f"parte-{slug(num)}"
            toc.append(("parte", pid, num, titulo))
            saida.append(
                f'<section class="parte" id="{pid}"><span class="pdf-marker">{marcador(pid)}</span>'
                f'<p class="parte-num">{html.escape(rotulo_parte(num))}</p>'
                f'<h1 class="parte-titulo">{html.escape(titulo)}</h1>'
                f'<p class="parte-sub">{html.escape(sub)}</p><span class="parte-x">X1</span></section>'
            )
            i += 1
            continue

        m = re.match(r"^# (.+)$", linha)
        if m:
            titulo = m.group(1).strip()
            mnum = re.match(r"^(\d+)\.\s+(.+)$", titulo)
            mane = re.match(r"^Anexo ([A-Z])\s*[:—-]\s+(.+)$", titulo)
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
                f'<header class="capitulo" id="{cid}"><span class="pdf-marker">{marcador(cid)}</span>{eb}'
                f'<h1>{html.escape(titulo)}</h1></header>'
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
            chat = render_chat(m.group(1), bloco, contador[0])
            for emo, txt in (("❌ Não faça", "Não faça"), ("✅ Faça", "Faça"), ("💬 Exemplo", "Exemplo")):
                chat = chat.replace(emo, txt)
            chat = chat.replace("\ufe0f", "")  # sem seletor de emoji colorido: usa o Noto Emoji monocromático
            saida += ["", chat, ""]
            i += 1
            continue

        if re.match(r"^::::\s*comparar\s*$", linha):
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

        if item.match(linha) and saida and saida[-1].strip() and not item.match(saida[-1]):
            saida.append("")
        saida.append(linha)
        i += 1
    return "\n".join(saida)


def montar_toc(toc, paginas):
    itens = []
    for tipo, cid, rot, titulo in toc:
        pg = paginas.get(cid, "")
        classe = "toc-parte" if tipo == "parte" else "toc-cap"
        r = rotulo_parte(rot) if tipo == "parte" else rot
        itens.append(f'<li class="{classe}"><span class="toc-rot">{html.escape(r)}</span>'
                     f'<span class="toc-tit">{html.escape(titulo)}</span><span class="toc-pg">{pg}</span></li>')
    return f'<section class="sumario"><h1>Sumário</h1><ol>{"".join(itens)}</ol></section>'


ABERTURA = """
<section class="rosto">
  <div class="rosto-x">X1</div>
  <p class="rosto-metodo">Método <b>X1</b></p>
  <p class="rosto-sub">Vendas no 1 a 1</p>
  <p class="rosto-desc">Como atender no WhatsApp os leads que chegam dos anúncios e transformar conversas em vendas</p>
  <p class="rosto-autor">Josias Viskoo</p>
  <div class="rosto-marca">{logo}</div>
</section>
<section class="creditos">
  <p><b>Método X1: Vendas no 1 a 1</b><br>Guia do atendimento comercial para leads do tráfego pago</p>
  <p>Autor: Josias Viskoo</p>
  <p>© 2026 Josias Viskoo · Viskoo. Todos os direitos reservados. Nenhuma parte desta obra pode ser reproduzida
  ou transmitida, por qualquer meio, sem autorização prévia e por escrito da Viskoo.</p>
  <p>Os nomes de pessoas, empresas e os valores usados nos exemplos são fictícios. Qualquer
  semelhança com casos reais é coincidência.</p>
  <p>Este livro é a edição impressa e condensada do e-book <i>Método X1: Vendas no 1 a 1</i>.</p>
</section>
<!--SUMARIO-->
<section class="promessa">
  <p class="promessa-aspas">“</p>
  <p class="promessa-txt">Seu cliente não quer falar com um script. Quer falar com <b>alguém que entende
  o problema dele</b>.</p>
  <p class="promessa-sub">Este livro ensina a usar o script <b>por trás</b> da conversa, nunca <b>na frente</b> dela.</p>
</section>
"""


def montar_html(paginas, extras):
    toc, contador, corpo = [], [0], []
    md = markdown.Markdown(extensions=["tables", "md_in_html", "sane_lists", "attr_list"])
    for arq in sorted(CAPITULOS.glob("*.md")):
        md.reset()
        corpo.append(md.convert(preprocessar(arq.read_text(encoding="utf-8"), toc, contador)))
    abertura = ABERTURA.replace("{logo}", LOGO_PRETO).replace("<!--SUMARIO-->", montar_toc(toc, paginas))
    notas = "".join('<section class="anotacoes"><h2>Anotações</h2><div class="pauta">' + "<i></i>" * 21 + '</div></section>'
                    for _ in range(extras))
    css = (AQUI / "miolo.css").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Método X1: miolo</title>
{FONTES}<style>{css}</style></head><body>
{abertura}<main>{"".join(corpo)}</main>{notas}
</body></html>"""


def chrome_pdf(html_path, pdf_path):
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        sys.exit("Google Chrome/Chromium não encontrado.")
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={perfil}", "--virtual-time-budget=20000",
             f"--print-to-pdf={pdf_path}", html_path.as_uri()],
            check=True, capture_output=True,
        )


def contar_paginas(pdf):
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    return int(re.search(r"Pages:\s+(\d+)", info).group(1))


def localizar(pdf):
    paginas = {}
    for p in range(1, contar_paginas(pdf) + 1):
        txt = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), str(pdf), "-"],
                             capture_output=True, text=True).stdout
        for k in re.findall(r"@@(\d+)@@", txt):
            paginas.setdefault(MARCAS[int(k) - 100], p)
    return paginas


def gs(args):
    subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite",
                    "-dCompatibilityLevel=1.4", "-dPDFSETTINGS=/prepress",
                    "-dEmbedAllFonts=true", "-dSubsetFonts=true", *args], check=True)


def preto_rico(pdf):
    """A conversão RGB->CMYK do Ghostscript transforma o preto do fundo em ~C72 M68 Y67 K88 (≈295%
    de tinta). Troca todo preto "carregado" por um preto rico padrão de gráfica: C60 M40 Y40 K100."""
    import pymupdf
    doc = pymupdf.open(pdf)
    padrao = re.compile(rb"(?<![\d.])(0?\.\d+|1) (0?\.\d+|1) (0?\.\d+|1) (0?\.\d+|1) ([kK])\b")

    def troca(m):
        c, mg, y, k = (float(x) for x in m.groups()[:4])
        if k >= 0.85 and min(c, mg, y) >= 0.55:
            return b"0.6 0.4 0.4 1 " + m.group(5)
        return m.group(0)

    for xref in range(1, doc.xref_length()):
        if doc.xref_is_stream(xref) and not doc.xref_get_key(xref, "Subtype")[1] == "/Image":
            try:
                dados = doc.xref_stream(xref)
            except Exception:
                continue
            novo = padrao.sub(troca, dados)
            if novo != dados:
                doc.update_stream(xref, novo)
    doc.save(pdf, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)


def ajustar_caixas(origem, destino):
    """O Chrome arredonda o tamanho da página para pontos inteiros (414 x 612 pt). Reassenta cada
    página no tamanho exato do gabarito (capa 554 x 216 mm, miolo 146 x 216 mm) e grava
    MediaBox/BleedBox e TrimBox (refile = 3 mm para dentro), como a gráfica espera."""
    import pymupdf
    src, out = pymupdf.open(origem), pymupdf.open()
    for n, pg in enumerate(src):
        larg = (554 if n == 0 else 146) * MM
        nova = out.new_page(width=larg, height=216 * MM)
        nova.show_pdf_page(nova.rect, src, n, keep_proportion=False)
        r = nova.rect
        nova.set_bleedbox(r)
        nova.set_trimbox(pymupdf.Rect(r.x0 + SANGRIA, r.y0 + SANGRIA, r.x1 - SANGRIA, r.y1 - SANGRIA))
    out.set_metadata({"title": "Método X1: Vendas no 1 a 1 (produção)", "author": "Viskoo",
                      "subject": "Capa aberta 4x0 + miolo 64 p. 1x1, 140 x 210 mm, lombada 4 mm"})
    out.save(destino, garbage=3, deflate=True)


def main():
    TMP.mkdir(exist_ok=True)
    SAIDA.mkdir(exist_ok=True)

    # 1) Miolo: até estabilizar sumário e completar 64 páginas com "Anotações"
    html_m, pdf_m = TMP / "miolo.html", TMP / "miolo-rgb.pdf"
    paginas, extras = {}, 0
    for _ in range(6):
        html_m.write_text(montar_html(paginas, extras), encoding="utf-8")
        chrome_pdf(html_m, pdf_m)
        total = contar_paginas(pdf_m)
        novas = localizar(pdf_m)
        if total > PAGINAS_MIOLO:
            sys.exit(f"ERRO: o miolo tem {total} páginas (limite {PAGINAS_MIOLO}). Condense o texto.")
        if novas == paginas and total == PAGINAS_MIOLO:
            break
        paginas = novas
        extras += PAGINAS_MIOLO - total
    else:
        sys.exit("ERRO: não foi possível estabilizar a paginação.")

    # 2) Miolo 1x1: converte tudo para escala de cinza (DeviceGray)
    pdf_m_gray = TMP / "miolo-cinza.pdf"
    gs(["-sColorConversionStrategy=Gray", "-dProcessColorModel=/DeviceGray",
        "-dAutoRotatePages=/None", f"-sOutputFile={pdf_m_gray}", str(pdf_m)])

    # 3) Capa aberta colorida -> CMYK
    html_c, pdf_c = TMP / "capa.html", TMP / "capa-rgb.pdf"
    capa = (AQUI / "capa.html").read_text(encoding="utf-8")
    capa = capa.replace("<!--FONTES-->", FONTES).replace("<!--ICONE-->", ICONE_SVG)
    capa = capa.replace("<!--FOTOCAPA-->", (AQUI / "assets" / "josias-viskoo-capa.png").as_uri())
    capa = capa.replace("<!--FOTO-->", (AQUI / "assets" / "josias-viskoo.jpg").as_uri())
    # Logo oficial (SVG do site viskoo.com.br), com o viewBox ajustado ao desenho
    logo = (AQUI / "assets" / "viskoo-logo-branco.svg").read_text(encoding="utf-8")
    logo = re.sub(r'<svg[^>]*>', '<svg viewBox="47 59 907 166.5" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Viskoo">', logo, count=1)
    capa = capa.replace("<!--LOGO-->", logo)
    for cid, pg in paginas.items():
        capa = capa.replace(f"<!--PG:{cid}-->", str(pg))
    html_c.write_text(capa, encoding="utf-8")
    chrome_pdf(html_c, pdf_c)
    if contar_paginas(pdf_c) != 1:
        sys.exit("ERRO: a capa deveria ter 1 página.")
    pdf_c_cmyk = TMP / "capa-cmyk.pdf"
    gs(["-sColorConversionStrategy=CMYK", "-dProcessColorModel=/DeviceCMYK",
        "-dAutoRotatePages=/None", f"-sOutputFile={pdf_c_cmyk}", str(pdf_c)])
    preto_rico(pdf_c_cmyk)

    # 4) Arquivo final na ordem do gabarito: capa aberta + 64 páginas de miolo
    final = SAIDA / NOME_FINAL
    juntos = TMP / "juntos.pdf"
    gs(["-sColorConversionStrategy=LeaveColorUnchanged", "-dAutoRotatePages=/None",
        f"-sOutputFile={juntos}", str(pdf_c_cmyk), str(pdf_m_gray)])
    ajustar_caixas(juntos, final)
    print(f"OK: {final} ({contar_paginas(final)} páginas: 1 capa aberta + {PAGINAS_MIOLO} de miolo, "
          f"{extras} página(s) de anotações)")


if __name__ == "__main__":
    main()
