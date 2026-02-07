from pathlib import Path
from typing import List, Iterator
import pdfplumber
import docx

def _extract_text_from_pdf(file_path: Path) -> str:
    """Extracts text from a PDF file."""
    text = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
    return "\n".join(text)

def _extract_text_from_docx(file_path: Path) -> str:
    """Extracts text from a DOCX file."""
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def _extract_text_from_txt(file_path: Path) -> str:
    """Extracts text from a TXT file."""
    try:
        return file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        # Fallback for other common encodings if utf-8 fails
        try:
            return file_path.read_text(encoding='latin-1')
        except Exception:
            return "" # Return empty string if all fails

def extract_text(file_path: Path) -> str:
    """
    Extracts text from a supported file type by dispatching to the correct helper.
    
    Returns an empty string if the file type is not supported or an error occurs.
    """
    extension = file_path.suffix.lower()
    if extension == ".pdf":
        return _extract_text_from_pdf(file_path)
    elif extension == ".docx":
        return _extract_text_from_docx(file_path)
    elif extension == ".txt":
        return _extract_text_from_txt(file_path)
    else:
        # Silently ignore unsupported files
        return ""

def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Iterator[str]:
    """
    Splits a text into overlapping chunks.
    
    Args:
        text: The input text.
        chunk_size: The desired size of each chunk (in characters).
        chunk_overlap: The number of characters to overlap between chunks.
        
    Returns:
        An iterator of text chunks.
    """
    if not text:
        return
        
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        
        # As per the plan, normalize whitespace and drop empty chunks
        chunk = " ".join(chunk.split())
        if chunk:
            yield chunk
            
        # Move the start position forward, considering the overlap
        start += chunk_size - chunk_overlap
        if start >= text_len:
            break
