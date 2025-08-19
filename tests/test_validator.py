from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.core.validator import PDFValidator, validate_pdf_for_paperless


def test_pdf_validator_initialization():
    """Test PDFValidator class initialization"""
    validator = PDFValidator()
    assert validator is not None


def test_validate_pdf_structure_valid_pdf():
    """Test validation of a valid PDF structure"""
    # Create a mock valid PDF buffer
    with patch("pikepdf.open") as mock_open:
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock(), MagicMock()]  # 2 pages

        # Mock page properties
        for page in mock_pdf.pages:
            page.mediabox = MagicMock()
            page.mediabox.width = 595
            page.mediabox.height = 842
            page.rotation = 0

        mock_pdf.docinfo = {}
        mock_pdf.is_encrypted = False
        mock_pdf.pdf_version = "1.7"

        mock_open.return_value.__enter__.return_value = mock_pdf

        # Create a mock buffer
        buffer = BytesIO(b"mock pdf content")

        is_valid, issues = PDFValidator.validate_pdf_structure(buffer)

        assert is_valid is True
        assert len(issues) == 0


def test_validate_pdf_structure_invalid_pdf():
    """Test validation of an invalid PDF structure"""
    with patch("pikepdf.open") as mock_open:
        mock_open.side_effect = Exception("Invalid PDF")

        buffer = BytesIO(b"invalid content")

        is_valid, issues = PDFValidator.validate_pdf_structure(buffer)

        assert is_valid is False
        assert len(issues) > 0
        assert "PDF structure validation failed" in issues[0]


def test_validate_pdf_structure_empty_pages():
    """Test validation of PDF with no pages"""
    with patch("pikepdf.open") as mock_open:
        mock_pdf = MagicMock()
        mock_pdf.pages = []  # No pages

        mock_open.return_value.__enter__.return_value = mock_pdf

        buffer = BytesIO(b"mock pdf content")

        is_valid, issues = PDFValidator.validate_pdf_structure(buffer)

        assert is_valid is False
        assert "PDF has no pages" in issues[0]


def test_validate_pdf_structure_invalid_page_dimensions():
    """Test validation of PDF with invalid page dimensions"""
    with patch("pikepdf.open") as mock_open:
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock()]

        # Mock invalid page properties
        page = mock_pdf.pages[0]
        page.mediabox = MagicMock()
        page.mediabox.width = -100  # Invalid width
        page.mediabox.height = 842
        page.rotation = 0

        mock_pdf.docinfo = {}
        mock_pdf.is_encrypted = False

        mock_open.return_value.__enter__.return_value = mock_pdf

        buffer = BytesIO(b"mock pdf content")

        is_valid, issues = PDFValidator.validate_pdf_structure(buffer)

        assert is_valid is False
        assert any("invalid dimensions" in issue for issue in issues)


def test_repair_pdf_success():
    """Test successful PDF repair"""
    with patch("pikepdf.open") as mock_open:
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock()]

        # Mock page with missing mediabox
        page = mock_pdf.pages[0]
        page.mediabox = None

        mock_pdf.docinfo = {"Title": "Test Document"}

        mock_open.return_value.__enter__.return_value = mock_pdf

        buffer = BytesIO(b"mock pdf content")

        repaired_buffer, success, notes = PDFValidator.repair_pdf(buffer)

        assert success is True
        assert len(notes) > 0
        assert "Created default mediabox" in notes[0]


def test_repair_pdf_failure():
    """Test PDF repair failure"""
    with patch("pikepdf.open") as mock_open:
        mock_open.side_effect = Exception("Cannot open PDF")

        buffer = BytesIO(b"invalid content")

        repaired_buffer, success, notes = PDFValidator.repair_pdf(buffer)

        assert success is False
        assert len(notes) > 0
        assert "Repair failed" in notes[0]


def test_comprehensive_validation():
    """Test comprehensive PDF validation"""
    with patch.object(PDFValidator, "validate_pdf_structure") as mock_validate:
        mock_validate.return_value = (True, [])  # Valid PDF

        buffer = BytesIO(b"mock pdf content")

        result = PDFValidator.comprehensive_validation(buffer)

        assert result["is_valid"] is True
        assert result["needs_repair"] is False
        assert result["repair_attempted"] is False
        assert "file_size_bytes" in result
        assert "page_count" in result


def test_comprehensive_validation_with_repair():
    """Test comprehensive validation that requires repair"""
    with patch.object(PDFValidator, "validate_pdf_structure") as mock_validate:
        # First validation fails, then repair succeeds
        mock_validate.side_effect = [(False, ["Invalid page"]), (True, [])]

        with patch.object(PDFValidator, "repair_pdf") as mock_repair:
            mock_repair.return_value = (BytesIO(b"repaired"), True, ["Repaired successfully"])

            buffer = BytesIO(b"mock pdf content")

            result = PDFValidator.comprehensive_validation(buffer)

            assert result["is_valid"] is True
            assert result["needs_repair"] is True
            assert result["repair_attempted"] is True
            assert result["repair_successful"] is True


def test_validate_pdf_for_paperless():
    """Test paperless-ngx specific validation"""
    with patch("pikepdf.open") as mock_open:
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock()]

        # Mock valid page
        page = mock_pdf.pages[0]
        page.mediabox = MagicMock()
        page.mediabox.width = 595
        page.mediabox.height = 842

        mock_pdf.is_encrypted = False
        mock_pdf.pdf_version = "1.7"

        mock_open.return_value.__enter__.return_value = mock_pdf

        with patch.object(PDFValidator, "comprehensive_validation") as mock_comp:
            mock_comp.return_value = {"is_valid": True, "repair_successful": False}

            buffer = BytesIO(b"mock pdf content")

            validated_buffer, is_compatible, notes = validate_pdf_for_paperless(buffer)

            assert is_compatible is True
            assert "already compatible" in notes


def test_validate_pdf_for_paperless_encrypted():
    """Test paperless-ngx validation with encrypted PDF"""
    with patch("pikepdf.open") as mock_open:
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock()]

        # Mock page
        page = mock_pdf.pages[0]
        page.mediabox = MagicMock()
        page.mediabox.width = 595
        page.mediabox.height = 842

        mock_pdf.is_encrypted = True  # Encrypted PDF
        mock_pdf.pdf_version = "1.7"

        mock_open.return_value.__enter__.return_value = mock_pdf

        # Mock the comprehensive validation to return a valid result
        with patch.object(PDFValidator, "comprehensive_validation") as mock_comp:
            mock_comp.return_value = {"is_valid": True, "repair_successful": False, "issues": []}

            buffer = BytesIO(b"mock pdf content")

            validated_buffer, is_compatible, notes = validate_pdf_for_paperless(buffer)

            assert is_compatible is True
            # The notes should contain information about encryption
            assert "encrypted" in notes.lower() or "paperless-ngx may have issues" in notes


if __name__ == "__main__":
    pytest.main([__file__])
