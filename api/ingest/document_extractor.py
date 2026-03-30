from __future__ import annotations

import os
from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".md"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_provider(provider: str) -> str:
    candidate = (provider or "auto").strip().lower()
    if candidate not in {"auto", "local", "azure", "none"}:
        raise ValueError("ocr_provider must be one of: auto, local, azure, none")
    return candidate


def _extract_pdf_embedded_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires pypdf in requirements.txt.") from exc

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def _ocr_with_local_tesseract(path: Path, language: str) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Local OCR requires pytesseract and Pillow. Install them in requirements.txt."
        ) from exc

    try:
        with Image.open(path) as image:
            text = pytesseract.image_to_string(image, lang=language)
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract binary not found. Install Tesseract or use Azure OCR fallback."
        ) from exc

    return text.strip()


def _ocr_with_azure_document_intelligence(path: Path) -> str:
    endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or os.environ.get(
        "AZURE_FORM_RECOGNIZER_ENDPOINT"
    )
    key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY") or os.environ.get(
        "AZURE_FORM_RECOGNIZER_KEY"
    )

    if not endpoint or not key:
        raise RuntimeError(
            "Azure OCR requires AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and "
            "AZURE_DOCUMENT_INTELLIGENCE_KEY (or AZURE_FORM_RECOGNIZER_*)."
        )

    try:
        from azure.ai.formrecognizer import DocumentAnalysisClient
        from azure.core.credentials import AzureKeyCredential
    except ImportError as exc:
        raise RuntimeError(
            "Azure OCR requires azure-ai-formrecognizer in requirements.txt."
        ) from exc

    client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    with open(path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-read", document=f)
    result = poller.result()

    lines: list[str] = []
    for page in result.pages:
        for line in page.lines:
            lines.append(line.content)
    return "\n".join(lines).strip()


def extract_text_from_path(
    path: Path,
    *,
    ocr_provider: str = "auto",
    ocr_language: str = "eng",
    azure_fallback: bool = True,
) -> str:
    provider = _normalize_provider(ocr_provider)
    suffix = path.suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8")

    if suffix in PDF_EXTENSIONS:
        embedded_text = _extract_pdf_embedded_text(path)
        if embedded_text:
            return embedded_text

        if provider == "none":
            return ""
        if provider == "azure":
            return _ocr_with_azure_document_intelligence(path)
        if provider == "local":
            # Local OCR is image-based; scanned PDFs should prefer Azure OCR.
            return ""

        if azure_fallback:
            return _ocr_with_azure_document_intelligence(path)
        return ""

    if suffix in IMAGE_EXTENSIONS:
        if provider == "none":
            return ""
        if provider == "azure":
            return _ocr_with_azure_document_intelligence(path)
        if provider == "local":
            return _ocr_with_local_tesseract(path, ocr_language)

        # auto mode: local OCR first, then optional Azure fallback.
        try:
            local_text = _ocr_with_local_tesseract(path, ocr_language)
            if local_text:
                return local_text
        except RuntimeError:
            if not azure_fallback:
                raise

        if azure_fallback:
            return _ocr_with_azure_document_intelligence(path)
        return ""

    raise ValueError(
        f"Unsupported file extension: {suffix}. Supported: txt, md, pdf, png, jpg, jpeg, tif, tiff, bmp"
    )


def should_use_azure_fallback() -> bool:
    return _is_truthy(os.environ.get("OCR_AZURE_FALLBACK", "true"))
