# ebook-conversoes-x1
Livro com técnicas de abordagens de X1, técnicas de alta conversão via WhatsApp

## Ebook "Método X1 — Vendas no 1 a 1" (Viskoo)

- Briefing do projeto: `CONTEXTO-EBOOK.md`
- Conteúdo: `ebook/capitulos/*.md` (um arquivo por parte, em ordem)
- Visual: `ebook/estilo.css`, `ebook/capa.html`, `ebook/contracapa.html`
- PDF gerado: `ebook/dist/metodo-x1-vendas-no-1a1-viskoo.pdf`

Para gerar de novo (requer Python 3 com `markdown`, Google Chrome e `poppler-utils`):

```bash
python3 ebook/build.py
```

Sintaxe especial nos capítulos:

- Conversa de WhatsApp: bloco ` ```whatsapp sim|nao|ex ` com linhas `@ Contato`, `C: cliente`, `V: vendedor`, `C~ 0:42 | transcrição` (áudio), `V[📄] arquivo.pdf` (anexo), `* 2 dias depois` (aviso), `? nota explicativa`
- Lado a lado: `::::comparar` … `::::`
- Caixas: `:::dica`, `:::cuidado`, `:::framework`, `:::exercicio`, `:::template`, `:::pratica`, `:::resumo`, `:::aplicar`, `:::destaque` … `:::`
- Abertura de parte: `<!-- PARTE: 1 | Título | Subtítulo -->`
