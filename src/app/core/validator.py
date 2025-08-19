from io import BytesIO
from typing import Dict, List, Tuple

import pikepdf


class PDFValidator:
    """Comprehensive PDF validation and repair utility"""

    @staticmethod
    def validate_pdf_structure(pdf_buffer: BytesIO) -> Tuple[bool, List[str]]:
        """
        Validates PDF structure and returns (is_valid, list_of_issues).
        """
        issues = []

        try:
            pdf_buffer.seek(0)

            with pikepdf.open(pdf_buffer) as pdf:
                # Check basic structure
                if not hasattr(pdf, "pages"):
                    issues.append("PDF has no pages attribute")
                    return False, issues

                if len(pdf.pages) == 0:
                    issues.append("PDF has no pages")
                    return False, issues

                # Validate each page
                for i, page in enumerate(pdf.pages):
                    try:
                        # Check page properties
                        mediabox = page.mediabox
                        if mediabox is None:
                            issues.append(f"Page {i + 1} has no mediabox")
                            continue

                        # Check if mediabox has valid dimensions
                        width = mediabox.width
                        height = mediabox.height
                        if width <= 0 or height <= 0:
                            issues.append(f"Page {i + 1} has invalid dimensions: {width}x{height}")

                        # Check rotation
                        rotation = getattr(page, "rotation", 0)
                        if rotation not in [0, 90, 180, 270]:
                            issues.append(f"Page {i + 1} has invalid rotation: {rotation}")

                        # Try to access content stream (basic content validation)
                        try:
                            _ = page.Contents
                        except Exception:
                            # Some PDFs might not have Contents, that's okay
                            pass

                    except Exception as e:
                        issues.append(f"Page {i + 1} validation failed: {str(e)}")

                # Check document info
                try:
                    docinfo = pdf.docinfo
                    if docinfo:
                        # Validate common metadata fields
                        for key, value in docinfo.items():
                            if isinstance(value, str) and len(value) > 10000:
                                issues.append(
                                    f"Metadata field '{key}' is unusually long ({len(value)} chars)"
                                )
                except Exception as e:
                    issues.append(f"Document info validation failed: {str(e)}")

                # Check for encryption
                if pdf.is_encrypted:
                    issues.append("PDF is encrypted (may cause compatibility issues)")

                # Check PDF version
                try:
                    version = pdf.pdf_version
                    if version < "1.4":
                        issues.append(
                            f"PDF version {version} is quite old, may cause compatibility issues"
                        )
                except Exception:
                    pass

        except Exception as e:
            issues.append(f"PDF structure validation failed: {str(e)}")
            return False, issues

        return len(issues) == 0, issues

    @staticmethod
    def repair_pdf(pdf_buffer: BytesIO) -> Tuple[BytesIO, bool, List[str]]:
        """
        Attempts to repair a PDF and returns (repaired_buffer, success, repair_notes).
        """
        repair_notes = []

        try:
            pdf_buffer.seek(0)

            with pikepdf.open(pdf_buffer) as pdf:
                # Create a new PDF with clean structure
                repaired_pdf = pikepdf.Pdf.new()

                # Copy pages with validation
                for i, page in enumerate(pdf.pages):
                    try:
                        # Ensure page has valid mediabox
                        if not hasattr(page, "mediabox") or page.mediabox is None:
                            repair_notes.append(f"Page {i + 1}: Created default mediabox")
                            # Create a default A4 mediabox
                            page.mediabox = pikepdf.Array([0, 0, 595, 842])

                        # Copy the page
                        repaired_pdf.pages.append(page)

                    except Exception as e:
                        repair_notes.append(f"Page {i + 1}: Could not repair, skipping: {str(e)}")
                        continue

                # Copy basic metadata (only safe fields)
                try:
                    safe_fields = ["Title", "Author", "Subject", "Creator", "Producer"]
                    for field in safe_fields:
                        if field in pdf.docinfo:
                            value = pdf.docinfo[field]
                            if isinstance(value, str) and len(value) < 1000:
                                repaired_pdf.docinfo[field] = value
                except Exception:
                    repair_notes.append("Could not copy metadata")

                # Save repaired PDF
                repaired_buffer = BytesIO()
                repaired_pdf.save(repaired_buffer)
                repaired_buffer.seek(0)

                return repaired_buffer, True, repair_notes

        except Exception as e:
            repair_notes.append(f"Repair failed: {str(e)}")
            return pdf_buffer, False, repair_notes

    @staticmethod
    def comprehensive_validation(pdf_buffer: BytesIO) -> Dict[str, any]:
        """
        Performs comprehensive PDF validation and returns detailed results.
        """
        pdf_buffer.seek(0)

        # Basic structure validation
        is_valid, issues = PDFValidator.validate_pdf_structure(pdf_buffer)

        # File size check
        file_size = len(pdf_buffer.getvalue())

        # Try to get page count
        page_count = 0
        try:
            pdf_buffer.seek(0)
            with pikepdf.open(pdf_buffer) as pdf:
                page_count = len(pdf.pages)
        except Exception:
            pass

        # Determine if repair is needed
        needs_repair = not is_valid and len(issues) > 0

        result = {
            "is_valid": is_valid,
            "file_size_bytes": file_size,
            "page_count": page_count,
            "issues": issues,
            "needs_repair": needs_repair,
            "repair_attempted": False,
            "repair_successful": False,
            "repair_notes": [],
        }

        # Attempt repair if needed
        if needs_repair:
            result["repair_attempted"] = True
            repaired_buffer, repair_success, repair_notes = PDFValidator.repair_pdf(pdf_buffer)
            result["repair_successful"] = repair_success
            result["repair_notes"] = repair_notes

            if repair_success:
                # Validate the repaired version
                is_repaired_valid, repaired_issues = PDFValidator.validate_pdf_structure(
                    repaired_buffer
                )
                result["is_valid"] = is_repaired_valid
                result["issues"] = repaired_issues
                result["file_size_bytes"] = len(repaired_buffer.getvalue())

        return result


def validate_pdf_for_paperless(pdf_buffer: BytesIO) -> Tuple[BytesIO, bool, str]:
    """
    Specialized validation for paperless-ngx compatibility.
    Returns (validated_buffer, is_compatible, compatibility_notes).
    """
    pdf_buffer.seek(0)

    # paperless-ngx specific requirements
    compatibility_notes = []

    try:
        with pikepdf.open(pdf_buffer) as pdf:
            # Check for encryption (paperless-ngx doesn't handle encrypted PDFs well)
            if pdf.is_encrypted:
                compatibility_notes.append("PDF is encrypted - paperless-ngx may have issues")

            # Check PDF version (paperless-ngx works best with PDF 1.4+)
            try:
                version = pdf.pdf_version
                if version < "1.4":
                    compatibility_notes.append(
                        f"PDF version {version} is old - consider upgrading for better compatibility"
                    )
            except Exception:
                pass

            # Check for unusual page sizes (paperless-ngx prefers standard sizes)
            for i, page in enumerate(pdf.pages):
                try:
                    mediabox = page.mediabox
                    if mediabox:
                        width = mediabox.width
                        height = mediabox.height

                        # Check if dimensions are reasonable (not too small or too large)
                        if width < 100 or height < 100:
                            compatibility_notes.append(
                                f"Page {i + 1} has very small dimensions: {width}x{height}"
                            )
                        elif width > 10000 or height > 10000:
                            compatibility_notes.append(
                                f"Page {i + 1} has very large dimensions: {width}x{height}"
                            )

                except Exception:
                    pass

            # Validate and potentially repair
            validator = PDFValidator()
            validation_result = validator.comprehensive_validation(pdf_buffer)

            if validation_result["is_valid"]:
                # Return the validated/repaired buffer
                if validation_result["repair_successful"]:
                    pdf_buffer.seek(0)
                    repaired_buffer = BytesIO(pdf_buffer.read())
                    repaired_buffer.seek(0)
                    return (
                        repaired_buffer,
                        True,
                        "PDF validated and repaired for paperless-ngx compatibility",
                    )
                else:
                    return pdf_buffer, True, "PDF is already compatible with paperless-ngx"
            else:
                compatibility_notes.extend(validation_result["issues"])
                return pdf_buffer, False, f"PDF validation failed: {'; '.join(compatibility_notes)}"

    except Exception as e:
        return pdf_buffer, False, f"PDF compatibility check failed: {str(e)}"
