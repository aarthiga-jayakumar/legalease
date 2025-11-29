# src/main.py
import argparse
from src.utils.logger import logger
from src.agents.orchestrator import handle_text_case
from src.tools.pdf_parser import extract_text_from_pdf

def run_text_flow(text, jurisdiction, goal):
    resp = handle_text_case(text, jurisdiction, goal)
    print("Case created:", resp["case_id"])
    print("Markdown saved at:", resp["markdown"])

def run_pdf_flow(pdf_path, jurisdiction, goal):
    text = extract_text_from_pdf(pdf_path)
    run_text_flow(text, jurisdiction, goal)

def cli():
    parser = argparse.ArgumentParser(description="LegalEase demo CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="User problem as text")
    group.add_argument("--pdf", help="Path to PDF file")
    parser.add_argument("--jurisdiction", default="Unknown")
    parser.add_argument("--goal", default="Request compliance")
    args = parser.parse_args()
    if args.text:
        run_text_flow(args.text, args.jurisdiction, args.goal)
    else:
        run_pdf_flow(args.pdf, args.jurisdiction, args.goal)

if __name__ == "__main__":
    cli()
