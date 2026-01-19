import os
import uuid
import fitz  # PyMuPDF
from werkzeug.utils import secure_filename


class PdfService:
    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        self.pdf_registry: dict[str, dict] = {}

    def save_and_process(self, file) -> dict:
        """Save uploaded PDF and extract basic info."""
        pdf_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        filepath = os.path.join(self.upload_folder, f"{pdf_id}_{filename}")

        file.save(filepath)

        # Open PDF to get page count
        doc = fitz.open(filepath)
        page_count = len(doc)
        doc.close()

        # Store in registry
        self.pdf_registry[pdf_id] = {
            'id': pdf_id,
            'filename': filename,
            'filepath': filepath,
            'pageCount': page_count
        }

        return {
            'id': pdf_id,
            'filename': filename,
            'pageCount': page_count
        }

    def get_filepath(self, pdf_id: str) -> str:
        """Get filepath for a PDF by ID."""
        if pdf_id in self.pdf_registry:
            return self.pdf_registry[pdf_id]['filepath']

        # Search in upload folder if not in registry
        for filename in os.listdir(self.upload_folder):
            if filename.startswith(pdf_id):
                filepath = os.path.join(self.upload_folder, filename)
                return filepath

        raise FileNotFoundError(f"PDF not found: {pdf_id}")

    def get_info(self, pdf_id: str) -> dict:
        """Get PDF info by ID."""
        filepath = self.get_filepath(pdf_id)
        doc = fitz.open(filepath)

        info = {
            'id': pdf_id,
            'pageCount': len(doc),
            'metadata': doc.metadata
        }

        doc.close()
        return info

    def extract_text(self, pdf_id: str, page_number: int = None) -> dict:
        """Extract text from PDF, optionally from specific page."""
        filepath = self.get_filepath(pdf_id)
        doc = fitz.open(filepath)

        blocks = []
        full_text = []

        if page_number is not None:
            # Extract from specific page (1-indexed)
            if page_number < 1 or page_number > len(doc):
                doc.close()
                raise ValueError(f"Invalid page number: {page_number}")

            page = doc[page_number - 1]
            page_blocks = self._extract_page_blocks(page, page_number)
            blocks.extend(page_blocks)
            full_text.append(page.get_text())
        else:
            # Extract from all pages
            for i, page in enumerate(doc):
                page_blocks = self._extract_page_blocks(page, i + 1)
                blocks.extend(page_blocks)
                full_text.append(page.get_text())

        doc.close()

        return {
            'text': '\n\n'.join(full_text),
            'blocks': blocks
        }

    def _extract_page_blocks(self, page, page_number: int) -> list:
        """Extract text blocks with bounding boxes from a page."""
        blocks = []
        dict_blocks = page.get_text("dict")["blocks"]

        for block in dict_blocks:
            if block.get("type") == 0:  # Text block
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "")
                    text += "\n"

                text = text.strip()
                if text:
                    blocks.append({
                        'text': text,
                        'pageNumber': page_number,
                        'bbox': list(block['bbox'])  # [x0, y0, x1, y1]
                    })

        return blocks
