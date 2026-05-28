import logging
import os
from collections import defaultdict

import fitz
import pandas as pd

from pdf_autofillr_mapper.clients.s3_client import S3Client

logger = logging.getLogger(__name__)


def get_field_type_new(widget):
    base = widget.field_type_string.upper()
    if base == "CHOICE":
        return "COMBOBOX" if (widget.field_flags & 0x80) else "LISTBOX"
    if base == "BUTTON":
        if widget.field_flags & 0x100:
            return "RADIOBUTTON"
        return "CHECKBOX"
    return base


def fitz_pdf_to_field_map(pdf_path_or_bytes) -> dict:
    """
    Extract field map from PDF file or bytes.

    Args:
        pdf_path_or_bytes: Either a local file path or PDF bytes from S3

    Returns:
        Dictionary mapping (page_num, bbox) -> (field_name, field_type, field_value)
    """
    doc = None
    try:
        # Handle both file path and bytes
        if isinstance(pdf_path_or_bytes, (str, os.PathLike)):
            doc = fitz.open(pdf_path_or_bytes)
        else:
            # Assume bytes
            doc = fitz.open(stream=pdf_path_or_bytes, filetype="pdf")

        field_map = {}

        for page_num, page in enumerate(doc, start=1):
            for widget in page.widgets():
                rect = widget.rect
                bbox = (int(rect.x0), int(rect.y0), int(rect.x1), int(rect.y1))
                field_name = widget.field_name or ""
                field_value = widget.field_value or ""
                field_type = get_field_type_new(widget)
                key = (page_num, bbox)
                field_map[key] = (
                    field_name.strip(),
                    field_type,
                    str(field_value).strip(),
                )

        return field_map

    finally:
        if doc:
            doc.close()


class EmbedValidator:
    def __init__(self, config: dict):
        self.config = config

    def _compute_stats(self, ground_truth_map, filled_map):
        stats = defaultdict(
            lambda: {
                "total_fields": 0,
                "total_filled": 0,
                "total_mapped": 0,
                "total_unmapped": 0,
                "correctly_filled": 0,
            }
        )

        for key, (gt_field_name, field_type, _) in ground_truth_map.items():
            if "unknown" in gt_field_name.strip().lower():
                continue

            stats[field_type]["total_fields"] += 1

            filled_field_name = filled_map.get(key, ("", "", ""))[0].strip()
            if not filled_field_name:
                continue

            print(filled_field_name, gt_field_name, field_type)

            stats[field_type]["total_filled"] += 1

            mapped_key = filled_field_name.split(".")[-1].strip()

            if "unmapped" in mapped_key.lower():
                stats[field_type]["total_unmapped"] += 1
            else:
                stats[field_type]["total_mapped"] += 1
                if mapped_key == gt_field_name.strip():
                    stats[field_type]["correctly_filled"] += 1

        # Compute derived metrics per field type
        combined = {
            "total_fields": 0,
            "total_filled": 0,
            "total_mapped": 0,
            "total_unmapped": 0,
            "correctly_filled": 0,
        }

        for _field_type, s in stats.items():
            total = s["total_fields"]
            filled = s["total_filled"]
            mapped = s["total_mapped"]
            correct = s["correctly_filled"]

            s["coverage"] = round((filled / total) * 100, 2) if total else 0
            s["accuracy"] = round((correct / filled) * 100, 2) if filled else 0
            s["mapping_precision"] = round((correct / mapped) * 100, 2) if mapped else 0

            for k in combined:
                combined[k] += s[k]

        # Compute overall metrics
        combined["coverage"] = (
            round((combined["total_filled"] / combined["total_fields"]) * 100, 2)
            if combined["total_fields"]
            else 0
        )
        combined["accuracy"] = (
            round((combined["correctly_filled"] / combined["total_filled"]) * 100, 2)
            if combined["total_filled"]
            else 0
        )
        combined["mapping_precision"] = (
            round((combined["correctly_filled"] / combined["total_mapped"]) * 100, 2)
            if combined["total_mapped"]
            else 0
        )

        return stats, combined

    def validate(
        self,
        completed_pdf_s3_path: str,
        embedded_pdf_s3_path: str,
        output_csv_s3_path: str,
    ):
        """
        Validate embedded PDF against completed (ground truth) PDF.

        Args:
            completed_pdf_s3_path: S3 path to completed/ground truth PDF
            embedded_pdf_s3_path: S3 path to embedded PDF to validate
            output_csv_s3_path: S3 path where to save validation CSV

        Returns:
            Dictionary with validation results and output path
        """
        logger.info("Running EmbedValidator...")
        logger.info(f"Completed PDF: {completed_pdf_s3_path}")
        logger.info(f"Embedded PDF: {embedded_pdf_s3_path}")

        s3_client = S3Client()

        # Download PDFs from S3 and read as bytes
        try:
            if completed_pdf_s3_path.startswith("s3://"):
                completed_pdf_bytes = s3_client.read_pdf_from_s3(completed_pdf_s3_path)
            else:
                with open(completed_pdf_s3_path, "rb") as f:
                    completed_pdf_bytes = f.read()

            if embedded_pdf_s3_path.startswith("s3://"):
                embedded_pdf_bytes = s3_client.read_pdf_from_s3(embedded_pdf_s3_path)
            else:
                with open(embedded_pdf_s3_path, "rb") as f:
                    embedded_pdf_bytes = f.read()
        except Exception as e:
            logger.error(f"Failed to read PDF files: {e}")
            raise RuntimeError(f"Failed to read PDF files for validation: {e}") from e

        # Extract field maps from both PDFs
        try:
            ground_truth_map = fitz_pdf_to_field_map(completed_pdf_bytes)
            filled_map = fitz_pdf_to_field_map(embedded_pdf_bytes)
        except Exception as e:
            logger.error(f"Failed to extract field maps: {e}")
            raise RuntimeError(f"Failed to extract field maps from PDFs: {e}") from e

        # Compute validation statistics
        type_stats, combined_stats = self._compute_stats(ground_truth_map, filled_map)

        # Create DataFrame
        df = pd.DataFrame.from_dict(type_stats, orient="index").reset_index()
        df = df.rename(columns={"index": "type"})

        combined_row = {"type": "all", **combined_stats}
        df = pd.concat([df, pd.DataFrame([combined_row])], ignore_index=True)

        # Save CSV to temp location first, then upload to S3
        try:
            local_temp_path = f"/tmp/validation_stats_{os.getpid()}.csv"
            df.to_csv(local_temp_path, index=False)
            logger.info(f"Validation CSV created locally: {local_temp_path}")

            # Upload to S3
            if output_csv_s3_path.startswith("s3://"):
                s3_client.upload_file_to_s3(local_temp_path, output_csv_s3_path)
                logger.info(f"Validation CSV uploaded to S3: {output_csv_s3_path}")
                final_path = output_csv_s3_path
            else:
                # Local path - just move the file
                import shutil

                shutil.move(local_temp_path, output_csv_s3_path)
                final_path = output_csv_s3_path
                logger.info(f"Validation CSV saved locally: {output_csv_s3_path}")

            # Clean up temp file if it still exists
            if os.path.exists(local_temp_path):
                os.remove(local_temp_path)

        except Exception as e:
            logger.error(f"Failed to save validation CSV: {e}")
            raise RuntimeError(f"Failed to save validation results: {e}") from e

        logger.info(f"Embed validation completed. Stats saved to: {final_path}")

        return {
            "validation_csv_path": final_path,
            "stats_summary": combined_stats,
            "dataframe": df,
        }
