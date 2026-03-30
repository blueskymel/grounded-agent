from pathlib import Path

import pytest

from ingest import document_extractor as dx


def test_extract_text_from_txt(tmp_path: Path):
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello world", encoding="utf-8")

    text, prov = dx.extract_text_from_path(file_path)

    assert text == "hello world"
    assert prov.source_file == "note.txt"
    assert prov.extraction_method == "text_read"


def test_extract_provenance_includes_source_file(tmp_path: Path):
    file_path = tmp_path / "doc.md"
    file_path.write_text("markdown content", encoding="utf-8")

    text, prov = dx.extract_text_from_path(file_path)

    assert prov.to_dict()["source_file"] == "doc.md"
    assert "extraction_method" in prov.to_dict()


def test_extract_pdf_uses_embedded_text(monkeypatch, tmp_path: Path):
    file_path = tmp_path / "doc.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        dx,
        "_extract_pdf_embedded_text",
        lambda _path: ("embedded text", dx.ExtractionProvenance(
            source_file="doc.pdf",
            extraction_method="pdf_embedded",
            page_count=1,
        )),
    )

    text, prov = dx.extract_text_from_path(file_path, ocr_provider="auto", azure_fallback=True)

    assert text == "embedded text"
    assert prov.extraction_method == "pdf_embedded"


def test_extract_pdf_falls_back_to_azure(monkeypatch, tmp_path: Path):
    file_path = tmp_path / "scan.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        dx,
        "_extract_pdf_embedded_text",
        lambda _path: ("", dx.ExtractionProvenance(
            source_file="scan.pdf",
            extraction_method="pdf_embedded",
        )),
    )
    monkeypatch.setattr(
        dx,
        "_ocr_with_azure_document_intelligence",
        lambda _path: ("ocr text", dx.ExtractionProvenance(
            source_file="scan.pdf",
            extraction_method="ocr_azure",
            ocr_provider="azure_document_intelligence",
        )),
    )

    text, prov = dx.extract_text_from_path(file_path, ocr_provider="auto", azure_fallback=True)

    assert text == "ocr text"
    assert prov.extraction_method == "ocr_azure"
    assert prov.fallback_used is True


def test_extract_image_auto_prefers_local_then_azure(monkeypatch, tmp_path: Path):
    file_path = tmp_path / "scan.png"
    file_path.write_bytes(b"not-a-real-png")

    monkeypatch.setattr(
        dx,
        "_ocr_with_local_tesseract",
        lambda _path, _lang: ("", dx.ExtractionProvenance(
            source_file="scan.png",
            extraction_method="ocr_local",
        )),
    )
    monkeypatch.setattr(
        dx,
        "_ocr_with_azure_document_intelligence",
        lambda _path: ("azure text", dx.ExtractionProvenance(
            source_file="scan.png",
            extraction_method="ocr_azure",
        )),
    )

    text, prov = dx.extract_text_from_path(file_path, ocr_provider="auto", azure_fallback=True)

    assert text == "azure text"
    assert prov.extraction_method == "ocr_azure"
    assert prov.fallback_used is True


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
