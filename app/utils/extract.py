from typing import BinaryIO
import re

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
    Tenta extrair com PyMuPDF (melhor qualidade). Se não houver, usa PyPDF2.
    Sempre aplica _beautify_preview no resultado.
    """
    # Tenta PyMuPDF
    try:
        import fitz  # PyMuPDF
        data = fh.read()
        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        raw = "\n\n".join(pages)
        return _beautify_preview(raw)
    except Exception:
        pass

    # Fallback: PyPDF2
    try:
        from PyPDF2 import PdfReader
        fh.seek(0)
        reader = PdfReader(fh)
        text = []
        for page in reader.pages:
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
