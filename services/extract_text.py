from pypdf import PdfReader


def from_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        return '\n'.join((page.extract_text() or '') for page in reader.pages)
    except Exception:
        return ''