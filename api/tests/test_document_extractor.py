from pathlib import Path

import pytest

from ingest import document_extractor as dx


def test_extract_text_from_txt(tmp_path: Path):
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello world", encoding="utf-8")

    result = dx.extract_text_from_path(file_path)

    assert result == "hello world"


def test_extract_pdf_uses_embedded_text(monkeypatch, tmp_path: Path):
    file_path = tmp_path / "doc.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(dx, "_extract_pdf_embedded_text", lambda _path: "embedded text")

    result = dx.extract_text_from_path(file_path, ocr_provider="auto", azure_fallback=True)

    assert result == "embedded text"


def test_extract_pdf_falls_back_to_azure(monkeypatch, tmp_path: Path):
    file_path = tmp_path / "scan.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(dx, "_extract_pdf_embedded_text", lambda _path: "")
    monkeypatch.setattr(dx, "_ocr_with_azure_document_intelligence", lambda _path: "ocr text")

    result = dx.extract_text_from_path(file_path, ocr_provider="auto", azure_fallback=True)

    assert result == "ocr text"


def test_extract_image_auto_prefers_local_then_azure(monkeypatch, tmp_path: Path):
    file_path = tmp_path / "scan.png"
    file_path.write_bytes(b"not-a-real-png")

    monkeypatch.setattr(dx, "_ocr_with_local_tesseract", lambda _path, _lang: "")
    monkeypatch.setattr(dx, "_ocr_with_azure_document_intelligence", lambda _path: "azure text")

    result = dx.extract_text_from_path(file_path, ocr_provider="auto", azure_fallback=True)

    assert result == "azure text"


def test_extract_image_auto_raises_without_fallback(monkeypatch, tmp_path: Path):
    file_path = tmp_path / "scan.jpg"
    file_path.write_bytes(b"not-a-real-jpg")

    def _raise_local(_path, _lang):
        raise RuntimeError("missing tesseract")

    monkeypatch.setattr(dx, "_ocr_with_local_tesseract", _raise_local)

    with pytest.raises(RuntimeError, match="missing tesseract"):
        dx.extract_text_from_path(file_path, ocr_provider="auto", azure_fallback=False)


def test_unsupported_extension_raises(tmp_path: Path):
    file_path = tmp_path / "data.csv"
    file_path.write_text("a,b,c", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file extension"):
        dx.extract_text_from_path(file_path)
