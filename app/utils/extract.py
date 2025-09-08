from typing import BinaryIO
import re, os

def _beautify_preview(text: str) -> str:
    """
    Deixa a prévia mais legível:
    - troca NBSP por espaço
    - colapsa espaços múltiplos
    - preserva parágrafos (linhas em branco)
    - junta quebras de linha no meio de frases
    """
    if not text:
        return ""

    t = text.replace("\u00A0", " ")

    # normaliza finais de linha (Windows/Mac)
    t = t.replace("\r\n", "\n").replace("\r", "\n")

    # preserva parágrafos: marca blocos com um marcador temporário
    t = re.sub(r"\n{2,}", "\n<PARA>\n", t)

    # junta quebras de linha no meio de frases:
    # se a linha anterior NÃO termina com pontuação forte, une com espaço
    t = re.sub(r"([^\.\!\?\:\;])\n(?=\S)", r"\1 ", t)

    # restaura quebras de parágrafo
    t = t.replace("<PARA>", "")

    # colapsa espaços múltiplos
    t = re.sub(r"[ \t]{2,}", " ", t)

    # tira espaços antes de pontuação
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)

    return t.strip()

def extract_text_from_pdf(fh: BinaryIO) -> str:
    """
    Extrai texto de PDF com PyMuPDF (preferido) e cai para PyPDF2 se falhar.
    Respeita PDF_MAX_PAGES (env) e garante fechamento de doc/reposition do stream.
    """
    MAX_PAGES = int(os.getenv("PDF_MAX_PAGES", "40"))

    # -------- TENTATIVA 1: PyMuPDF --------
    try:
        import fitz  # PyMuPDF
    except Exception:
        fitz = None

    if fitz is not None:
        doc = None
        try:
            data = fh.read()  # lê tudo (SpooledTemporaryFile etc.)
            doc = fitz.open(stream=data, filetype="pdf")
            pages = []
            for i, page in enumerate(doc):
                if i >= MAX_PAGES:
                    break
                pages.append(page.get_text("text"))
            raw = "\n\n".join(pages)
            return _beautify_preview(raw)
        except Exception:
            # cai para o fallback
            pass
        finally:
            try:
                if doc is not None:
                    doc.close()
            except Exception:
                pass

    # -------- TENTATIVA 2: PyPDF2 (fallback) --------
    try:
        from PyPDF2 import PdfReader
        try:
            fh.seek(0)  # reposiciona o ponteiro caso já tenha lido acima
        except Exception:
            pass
        reader = PdfReader(fh)
        text = []
        for i, page in enumerate(reader.pages):
            if i >= MAX_PAGES:
                break
            text.append(page.extract_text() or "")
        raw = "\n\n".join(text)
        return _beautify_preview(raw)
    except Exception:
        return ""


def extract_text_from_txt(fh: BinaryIO) -> str:
    data = fh.read()
    if isinstance(data, bytes):
        for enc in ("utf-8", "latin-1"):
            try:
                return data.decode(enc)
            except Exception:
                continue
        return data.decode("utf-8", errors="ignore")
    return str(data or "")
