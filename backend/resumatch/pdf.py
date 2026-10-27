import fitz  # PyMuPDF


class PDFError(ValueError):
    pass


MAX_PAGES = 6


def extract_text(data: bytes) -> str:
    if not data.startswith(b"%PDF"):
        raise PDFError("That file isn't a PDF.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:  # fitz raises a few different types here
        raise PDFError("Couldn't open the PDF, it may be corrupted.") from e

    with doc:
        if doc.needs_pass:
            raise PDFError("The PDF is password-protected.")
        if doc.page_count > MAX_PAGES:
            raise PDFError(f"Resumes over {MAX_PAGES} pages aren't supported.")
        # sort=True orders blocks top-to-bottom, left-to-right. Helps with PDFs
        # exported from Word/Canva where the text order is all over the place.
        text = "\n".join(page.get_text("text", sort=True) for page in doc)

    if len(text.strip()) < 50:
        raise PDFError(
            "Found almost no text in the PDF. If it's a scanned image, export it from the original document instead."
        )
    return text
