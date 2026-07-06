# app/services/resume_parser.py
import os
import asyncio
import logging
from pypdf import PdfReader
from docx import Document

logger = logging.getLogger(__name__)

def parse_pdf(file_path: str) -> str:
    """Parse text from a PDF file."""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text.strip()

def parse_docx(file_path: str) -> str:
    """Parse text from a DOCX file."""
    doc = Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        if paragraph.text:
            text += paragraph.text + "\n"
    return text.strip()

class ParsingException(Exception):
    pass

async def parse_resume(file_path: str) -> str:
    """
    Asynchronously parses a resume file (.pdf or .docx) and returns its text.
    Raises ParsingException if parsing fails or text is empty/scanned.
    """
    if not os.path.exists(file_path):
        raise ParsingException(f"Resume file at {file_path} does not exist.")

    _, ext = os.path.splitext(file_path.lower())
    
    try:
        if ext == ".pdf":
            text = await asyncio.to_thread(parse_pdf, file_path)
        elif ext in [".docx", ".doc"]:
            text = await asyncio.to_thread(parse_docx, file_path)
        else:
            raise ParsingException(f"Unsupported file format: {ext}")
    except Exception as e:
        logger.error(f"Error parsing file {file_path}: {e}")
        raise ParsingException(f"Failed to parse resume: {str(e)}")

    # Check for empty/scanned text
    if not text or len(text.strip()) < 50:
        raise ParsingException(
            "The uploaded resume appears to be empty or contains very little text. "
            "If it is a scanned image, please upload a text-based PDF or Word document."
        )

    return text
