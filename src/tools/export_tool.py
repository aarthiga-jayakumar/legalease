# src/tools/export_tool.py
import os
from ..utils.logger import logger

def save_markdown(text: str, target_dir: str, filename: str):
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info(f"Saved markdown to {path}")
    return path

# Optional: convert to PDF using weasyprint if available
def markdown_to_pdf(md_path: str, pdf_path: str):
    try:
        from markdown2 import markdown
        from weasyprint import HTML
        with open(md_path, "r", encoding="utf-8") as f:
            html = markdown(f.read())
        HTML(string=html).write_pdf(pdf_path)
        logger.info(f"Exported PDF to {pdf_path}")
        return pdf_path
    except Exception as e:
        logger.exception("PDF export failed. PDF conversion requires markdown2 and weasyprint.")
        raise e
