import os
import traceback
from io import BytesIO
from typing import List

import pikepdf


def split_pdf(input_path: str, separators: List[int]) -> List[BytesIO]:
    """
    Splits the PDF at input_path into slices based on 1-based page separators.
    Each separator page starts a new slice and is included in its own part.
    Preserves metadata and adds XMP tag 'Split-Of'.
    Returns a list of BytesIO objects for each part.
    """
    try:
        with pikepdf.open(input_path) as pdf:
            num_pages = len(pdf.pages)
            # Validate separators
            if not separators:
                separators = [1]
            separators = sorted(set(separators))
            if separators[0] < 1 or separators[-1] > num_pages:
                raise ValueError(
                    f"Separator out of range. Separators: {separators}, Num pages: {num_pages}"
                )
            # Build slice ranges
            ranges = []
            for i, sep in enumerate(separators):
                start = sep - 1
                end = separators[i + 1] - 1 if i + 1 < len(separators) else num_pages
                ranges.append((start, end))
            # Prepare output
            output_parts = []
            orig_basename = os.path.splitext(os.path.basename(input_path))[0]
            for idx, (start, end) in enumerate(ranges):
                new_pdf = pikepdf.Pdf.new()
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
                output_parts.append(buf)
            return output_parts
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[split_pdf] Exception: {e}\nTraceback:\n{tb}")
        raise
