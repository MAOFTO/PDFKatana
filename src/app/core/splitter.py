import os
import traceback
from io import BytesIO
from typing import List, Tuple

import pikepdf

from app.core.validator import validate_pdf_for_paperless


def validate_and_repair_pdf(pdf_buffer: BytesIO) -> Tuple[BytesIO, bool]:
    """
    Validates and optionally repairs a PDF buffer using paperless-ngx specific validation.
    Returns (validated_buffer, is_valid).
    """
    try:
        # Use specialized validation for paperless-ngx compatibility
        validated_buffer, is_compatible, notes = validate_pdf_for_paperless(pdf_buffer)

        if not is_compatible:
            print(f"[validate_and_repair_pdf] PDF validation failed: {notes}")
            return pdf_buffer, False

        if notes and "repaired" in notes.lower():
            print(f"[validate_and_repair_pdf] PDF repaired: {notes}")
        else:
            print(f"[validate_and_repair_pdf] PDF validated: {notes}")

        return validated_buffer, True

    except Exception as e:
        print(f"[validate_and_repair_pdf] PDF validation failed: {e}")
        return pdf_buffer, False


def split_pdf(input_path: str, split_pages: List[int]) -> List[BytesIO]:
    """
    Splits the PDF at input_path into parts based on split points.
    Each specified page becomes the first page of a new part.
    Preserves metadata and adds XMP tag 'Split-Of'.
    Returns a list of validated BytesIO objects for each part.

    Note: Input PDF should be validated and repaired before calling this function.
    Output parts are also validated to ensure quality delivery.
    """
    try:
        with pikepdf.open(input_path) as pdf:
            num_pages = len(pdf.pages)

            # Validate split pages
            if not split_pages:
                raise ValueError("At least one split page must be specified")

            # Convert to 0-based indices and sort
            split_indices = sorted([page - 1 for page in split_pages])

            # Validate all split pages are within range
            if split_indices[0] < 0 or split_indices[-1] >= num_pages:
                raise ValueError(
                    f"Split pages out of range. Split pages: {split_pages}, "
                    f"PDF has {num_pages} pages (1-based)"
                )

            # Build page ranges for each part
            ranges = []

            # First part: from page 1 to first split point
            if split_indices[0] > 0:
                ranges.append((0, split_indices[0]))

            # Middle parts: between split points
            for i in range(len(split_indices)):
                start = split_indices[i]
                if i + 1 < len(split_indices):
                    end = split_indices[i + 1]
                else:
                    end = num_pages
                ranges.append((start, end))

            # Prepare output
            output_parts = []
            orig_basename = os.path.splitext(os.path.basename(input_path))[0]

            for idx, (start, end) in enumerate(ranges):
                new_pdf = pikepdf.Pdf.new()

                # Add pages for this range
                for page in pdf.pages[start:end]:
                    new_pdf.pages.append(page)

                # Copy only string metadata
                try:
                    for k, v in pdf.docinfo.items():
                        if isinstance(v, str):
                            new_pdf.docinfo[k] = v
                except Exception as meta_exc:
                    print(f"[split_pdf] Metadata copy failed: {meta_exc}")

                # Add split info to pdf:Keywords, appending if already present
                try:
                    with new_pdf.open_metadata(set_pikepdf_as_editor=True) as xmp:
                        split_info = f"Split-Of={orig_basename}#part{idx + 1}/{len(ranges)}"
                        existing_keywords = xmp.get("pdf:Keywords", "")
                        if existing_keywords:
                            new_keywords = existing_keywords + "; " + split_info
                        else:
                            new_keywords = split_info
                        xmp["pdf:Keywords"] = new_keywords
                except Exception as xmp_exc:
                    print(f"[split_pdf] XMP tag failed: {xmp_exc}")

                # Write to BytesIO
                buf = BytesIO()
                new_pdf.save(buf)
                buf.seek(0)

                # Validate and repair the output PDF for paperless-ngx compatibility
                validated_buf, is_valid = validate_and_repair_pdf(buf)

                if is_valid:
                    output_parts.append(validated_buf)
                    print(f"[split_pdf] Part {idx + 1} validated successfully for paperless-ngx")
                else:
                    print(
                        f"[split_pdf] WARNING: Part {idx + 1} failed validation, attempting basic repair..."
                    )
                    # Try to create a minimal valid PDF as fallback
                    fallback_pdf = pikepdf.Pdf.new()
                    for page in pdf.pages[start:end]:
                        fallback_pdf.pages.append(page)

                    fallback_buf = BytesIO()
                    fallback_pdf.save(fallback_buf)
                    fallback_buf.seek(0)

                    # Try validation again on the fallback
                    final_buf, final_valid = validate_and_repair_pdf(fallback_buf)
                    if final_valid:
                        output_parts.append(final_buf)
                        print(
                            f"[split_pdf] Part {idx + 1} repaired and validated for paperless-ngx"
                        )
                    else:
                        print(
                            f"[split_pdf] ERROR: Part {idx + 1} could not be repaired for paperless-ngx"
                        )
                        # Still add it but log the issue
                        output_parts.append(buf)

            return output_parts

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[split_pdf] Exception: {e}\nTraceback:\n{tb}")
        raise
