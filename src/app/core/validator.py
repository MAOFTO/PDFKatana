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
                            # Check if page has Contents attribute
                            if hasattr(page, "Contents"):
                                contents = page.Contents
                                # Contents can be a Stream, Array of Streams, or None
                                if contents is not None:
                                    # Check if it's a valid pikepdf object type
                                    if isinstance(contents, (pikepdf.Stream, pikepdf.Array)):
                                        # Valid Contents object
                                        pass
                                    elif isinstance(contents, pikepdf.Dictionary):
                                        # Sometimes Contents can be a Dictionary reference
                                        pass
                                    else:
                                        # Try to access it anyway - might be a valid indirect object
                                        try:
                                            _ = str(contents)
                                        except Exception:
                                            issues.append(
                                                f"Page {i + 1} has inaccessible Contents object"
                                            )
                        except Exception:
                            # Contents access failed - this is actually okay for many PDFs
                            # Don't add this as an issue since many valid PDFs don't have explicit Contents
                            pass

                    except Exception as e:
                        # Only report serious page validation errors
                        error_msg = str(e)
                        if "Object is not a Dictionary or Stream" not in error_msg:
                            issues.append(f"Page {i + 1} validation failed: {error_msg}")
                        # Skip the common "Object is not a Dictionary or Stream" errors

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

                # Check PDF version (informational only, not a validation failure)
                try:
                    # Note: PDF version warnings are now handled separately
                    pass
                except Exception:
                    pass

        except Exception as e:
            issues.append(f"PDF structure validation failed: {str(e)}")
            return False, issues

        # Only consider critical issues as validation failures
        critical_issues = []
        for issue in issues:
            # Filter out non-critical issues
            if any(
                keyword in issue.lower()
                for keyword in [
                    "has no pages",
                    "has no mediabox",
                    "invalid dimensions",
                    "could not repair",
                ]
            ):
                critical_issues.append(issue)

        return len(critical_issues) == 0, issues

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

                # Copy pages with validation and repair
                for i, page in enumerate(pdf.pages):
                    try:
                        # Create a new page for the repaired PDF
                        new_page = repaired_pdf.copy_foreign(page)

                        # Ensure page has valid mediabox
                        if not hasattr(new_page, "mediabox") or new_page.mediabox is None:
                            repair_notes.append(f"Page {i + 1}: Created default mediabox")
                            # Create a default A4 mediabox
                            new_page.MediaBox = pikepdf.Array([0, 0, 595, 842])

                        # Add the repaired page
                        repaired_pdf.pages.append(new_page)

                    except Exception as e:
                        # Try a simpler page copy approach
                        try:
                            repaired_pdf.pages.append(page)
                            repair_notes.append(f"Page {i + 1}: Used fallback copy method")
                        except Exception as e2:
                            repair_notes.append(
                                f"Page {i + 1}: Could not repair, skipping: {str(e)} / {str(e2)}"
                            )
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

                # Save repaired PDF with proper buffer handling
                repaired_buffer = BytesIO()
                repaired_pdf.save(repaired_buffer)
                repaired_buffer.seek(0)  # Reset position for reading

                return repaired_buffer, True, repair_notes

        except Exception as e:
            repair_notes.append(f"Repair failed: {str(e)}")
            pdf_buffer.seek(0)  # Reset original buffer position
            return pdf_buffer, False, repair_notes

    @staticmethod
    def comprehensive_validation(
        pdf_buffer: BytesIO, include_repair: bool = True
    ) -> Dict[str, any]:
        """
        Performs comprehensive PDF validation and returns detailed results.
        """
        pdf_buffer.seek(0)

        # Basic structure validation
        is_valid, issues = PDFValidator.validate_pdf_structure(pdf_buffer)

        # File size check
        file_size = len(pdf_buffer.getvalue())

        # Try to get page count and collect informational warnings
        page_count = 0
        info_warnings = []
        try:
            pdf_buffer.seek(0)
            with pikepdf.open(pdf_buffer) as pdf:
                page_count = len(pdf.pages)

                # Check PDF version (informational)
                try:
                    version = pdf.pdf_version
                    if version < "1.4":
                        info_warnings.append(
                            f"PDF version {version} is old - consider upgrading for better compatibility"
                        )
                except Exception:
                    pass
        except Exception:
            pass

        # Determine if repair is needed
        needs_repair = not is_valid and len(issues) > 0

        result = {
            "is_valid": is_valid,
            "file_size_bytes": file_size,
            "page_count": page_count,
            "issues": issues,
            "info_warnings": info_warnings,
            "needs_repair": needs_repair,
            "repair_attempted": False,
            "repair_successful": False,
            "repair_notes": [],
            "repaired_buffer": None,
        }

        # Attempt repair if needed and requested
        if needs_repair and include_repair:
            result["repair_attempted"] = True
            repaired_buffer, repair_success, repair_notes = PDFValidator.repair_pdf(pdf_buffer)
            result["repair_successful"] = repair_success
            result["repair_notes"] = repair_notes

            if repair_success:
                # Store the repaired buffer
                result["repaired_buffer"] = repaired_buffer
                # Validate the repaired version
                is_repaired_valid, repaired_issues = PDFValidator.validate_pdf_structure(
                    repaired_buffer
                )
                result["is_valid"] = is_repaired_valid
                result["issues"] = repaired_issues
                result["file_size_bytes"] = len(repaired_buffer.getvalue())

        return result


def validate_pdf_for_paperless(
    pdf_buffer: BytesIO, validation_result: Dict = None
) -> Tuple[BytesIO, bool, str]:
    """
    Specialized validation for paperless-ngx compatibility.
    Returns (validated_buffer, is_compatible, compatibility_notes).
    """
    pdf_buffer.seek(0)

    # paperless-ngx specific requirements
    compatibility_notes = []
    info_warnings = []

    try:
        with pikepdf.open(pdf_buffer) as pdf:
            # Check for encryption (paperless-ngx doesn't handle encrypted PDFs well)
            if pdf.is_encrypted:
                compatibility_notes.append("PDF is encrypted - paperless-ngx may have issues")

            # Check PDF version (paperless-ngx works best with PDF 1.4+)
            try:
                version = pdf.pdf_version
                if version < "1.4":
                    info_warnings.append(
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

        # Use existing validation result if provided, otherwise perform validation
        if validation_result is None:
            validator = PDFValidator()
            validation_result = validator.comprehensive_validation(pdf_buffer)

        # Combine warnings
        all_notes = compatibility_notes + info_warnings + validation_result.get("info_warnings", [])

        if validation_result["is_valid"]:
            # Return the validated/repaired buffer
            if validation_result["repair_successful"] and validation_result.get("repaired_buffer"):
                repaired_buffer = validation_result["repaired_buffer"]
                repaired_buffer.seek(0)
                notes_text = "PDF validated and repaired for paperless-ngx compatibility"
                if all_notes:
                    notes_text += f"; {'; '.join(all_notes)}"
                return repaired_buffer, True, notes_text
            else:
                notes_text = "PDF is already compatible with paperless-ngx"
                if all_notes:
                    notes_text += f"; {'; '.join(all_notes)}"
                return pdf_buffer, True, notes_text
        else:
            all_issues = compatibility_notes + validation_result["issues"]
            notes_text = f"PDF validation failed: {'; '.join(all_issues)}"
            if info_warnings:
                notes_text += f"; {'; '.join(info_warnings)}"
            return pdf_buffer, False, notes_text

    except Exception as e:
        return pdf_buffer, False, f"PDF compatibility check failed: {str(e)}"
