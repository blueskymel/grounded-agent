from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ExtractionProvenance:
    """Metadata about how text was extracted."""
    source_file: str
    extraction_method: str  # 'text_read', 'pdf_embedded', 'ocr_local', 'ocr_azure'
    ocr_provider: str | None = None  # 'tesseract', 'azure_document_intelligence'
    ocr_language: str | None = None
    ocr_confidence: float | None = None  # 0.0-1.0 if available
    fallback_used: bool = False
    page_count: int | None = None
    extraction_notes: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


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


def _extract_pdf_embedded_text(path: Path) -> tuple[str, ExtractionProvenance]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires pypdf in requirements.txt.") from exc

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = "\n".join(pages).strip()
    provenance = ExtractionProvenance(
        source_file=path.name,
        extraction_method="pdf_embedded",
        page_count=len(reader.pages),
    )
    return text, provenance


def _ocr_with_local_tesseract(path: Path, language: str) -> tuple[str, ExtractionProvenance]:
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

    provenance = ExtractionProvenance(
        source_file=path.name,
        extraction_method="ocr_local",
        ocr_provider="tesseract",
        ocr_language=language,
    )
    return text.strip(), provenance


def _ocr_with_azure_document_intelligence(path: Path) -> tuple[str, ExtractionProvenance]:
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
    text = "\n".join(lines).strip()
    provenance = ExtractionProvenance(
        source_file=path.name,
        extraction_method="ocr_azure",
        ocr_provider="azure_document_intelligence",
        page_count=len(result.pages),
    )
    return text, provenance


def extract_text_from_path(
    path: Path,
    *,
    ocr_provider: str = "auto",
    ocr_language: str = "eng",
    azure_fallback: bool = True,
) -> tuple[str, ExtractionProvenance]:
    provider = _normalize_provider(ocr_provider)
    suffix = path.suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        text = path.read_text(encoding="utf-8")
        provenance = ExtractionProvenance(
            source_file=path.name,
            extraction_method="text_read",
        )
        return text, provenance

    if suffix in PDF_EXTENSIONS:
        embedded_text, prov = _extract_pdf_embedded_text(path)
        if embedded_text:
            return embedded_text, prov

        if provider == "none":
            return "", prov
        if provider == "azure":
            ocr_text, ocr_prov = _ocr_with_azure_document_intelligence(path)
            ocr_prov.fallback_used = True
            return ocr_text, ocr_prov
        if provider == "local":
            # Local OCR is image-based; scanned PDFs should prefer Azure OCR.
            return "", prov

        if azure_fallback:
            ocr_text, ocr_prov = _ocr_with_azure_document_intelligence(path)
            ocr_prov.fallback_used = True
            return ocr_text, ocr_prov
        return "", prov

    if suffix in IMAGE_EXTENSIONS:
        if provider == "none":
            prov = ExtractionProvenance(
                source_file=path.name,
                extraction_method="ocr_none",
            )
            return "", prov
        if provider == "azure":
            return _ocr_with_azure_document_intelligence(path)
        if provider == "local":
            return _ocr_with_local_tesseract(path, ocr_language)

        # auto mode: local OCR first, then optional Azure fallback.
        try:
            local_text, local_prov = _ocr_with_local_tesseract(path, ocr_language)
            if local_text:
                return local_text, local_prov
        except RuntimeError:
            if not azure_fallback:
                raise

        if azure_fallback:
            azure_text, azure_prov = _ocr_with_azure_document_intelligence(path)
            azure_prov.fallback_used = True
            return azure_text, azure_prov
        prov = ExtractionProvenance(
            source_file=path.name,
            extraction_method="ocr_auto_failed",
        )
        return "", prov

    raise ValueError(
        f"Unsupported file extension: {suffix}. Supported: txt, md, pdf, png, jpg, jpeg, tif, tiff, bmp"
    )


def should_use_azure_fallback() -> bool:
    return _is_truthy(os.environ.get("OCR_AZURE_FALLBACK", "true"))
