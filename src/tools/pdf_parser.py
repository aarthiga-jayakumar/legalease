# src/tools/pdf_parser.py
import pdfplumber
from ..utils.logger import logger

def extract_text_from_pdf(path: str) -> str:
    logger.info(f"Extracting text from PDF: {path}")
    text_parts = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
    except Exception as e:
        logger.exception("PDF parsing failed")
        raise e
    return "\n\n".join(text_parts)
