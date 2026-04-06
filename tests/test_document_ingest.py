from __future__ import annotations

from aria.core.document_ingest import DocumentIngestError, prepare_uploaded_document


def _minimal_text_pdf_bytes(text: str) -> bytes:
    content = f"BT\n/F1 18 Tf\n50 100 Td\n({text}) Tj\nET\n".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


def test_prepare_uploaded_document_chunks_markdown() -> None:
    payload = (
        "# Titel\n\n"
        + "Dies ist ein etwas längerer Markdown-Text. " * 80
        + "\n\n"
        + "Noch ein Abschnitt mit mehr Kontext. " * 60
    ).encode("utf-8")

    prepared = prepare_uploaded_document(filename="wissen.md", data=payload, content_type="text/markdown", chunk_size=500)

    assert prepared.filename == "wissen.md"
    assert prepared.source_type == "md"
    assert prepared.mime_type == "text/markdown"
    assert prepared.summary
    assert prepared.keywords
    assert len(prepared.chunks) >= 2
    assert prepared.chunks[0].index == 1
    assert prepared.chunks[-1].total == len(prepared.chunks)


def test_prepare_uploaded_document_rejects_unknown_extension() -> None:
    try:
        prepare_uploaded_document(filename="wissen.json", data=b"{}", content_type="application/json")
    except DocumentIngestError as exc:
        assert "unterstützt" in str(exc).lower() or "supported" in str(exc).lower()
    else:
        raise AssertionError("Expected DocumentIngestError for unsupported extension")


def test_prepare_uploaded_document_extracts_text_pdf() -> None:
    prepared = prepare_uploaded_document(
        filename="handbuch.pdf",
        data=_minimal_text_pdf_bytes("Atlas NAS Dokumentation"),
        content_type="application/pdf",
        chunk_size=400,
    )

    assert prepared.filename == "handbuch.pdf"
    assert prepared.source_type == "pdf"
    assert prepared.mime_type == "application/pdf"
    assert "Atlas NAS Dokumentation" in prepared.text
    assert "Atlas NAS Dokumentation" in prepared.summary
    assert "atlas" in prepared.keywords
    assert len(prepared.chunks) == 1


def test_prepare_uploaded_document_rejects_pdf_without_embedded_text() -> None:
    try:
        prepare_uploaded_document(
            filename="scan.pdf",
            data=_minimal_text_pdf_bytes(""),
            content_type="application/pdf",
        )
    except DocumentIngestError as exc:
        assert "eingebetteten text" in str(exc).lower() or "embedded text" in str(exc).lower()
    else:
        raise AssertionError("Expected DocumentIngestError for image/scan-like PDF without text")
