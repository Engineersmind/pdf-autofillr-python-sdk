import logging
import re
from typing import Any

import fitz

from pdf_autofillr_mapper.models.bounding_box import BoundingBox
from pdf_autofillr_mapper.utils.storage import save_json

logger = logging.getLogger(__name__)


class FitzExtractorLine:
    def __init__(self, config: dict):
        self.WIDGET_LINE_DISTANCE_THRESHOLD = config.get(
            "WIDGET_LINE_DISTANCE_THRESHOLD", 10
        )
        self.rounding = config.get("rounding", 1)
        self.global_id = 1
        self.global_fid = 1
        self.AVG_CHAR_WIDTH = 7
        self.LEFT_MARGIN = 70
        self.fid_to_gid_map: dict[Any, Any] = {}

    def _get_field_type_new(self, widget):
        base = widget.field_type_string.upper()
        if base == "CHOICE":
            return "COMBOBOX" if (widget.field_flags & 0x80) else "LISTBOX"
        if base == "BUTTON":
            if widget.field_flags & 0x100:
                return "RADIOBUTTON"
            return "CHECKBOX"
        return base

    def _extract_words_by_line(self, words):
        lines = {}
        for word in words:
            x0, y0, x1, y1, text, *_ = word
            line_key = (round(y0, self.rounding), round(y1, self.rounding))
            if line_key not in lines:
                lines[line_key] = []
            if re.match(r"[._\u2026-]{2,}", text):
                lines[line_key].append(("", (x0, y0, x1, y1), word[-1]))
            else:
                lines[line_key].append((text, (x0, y0, x1, y1), word[-1]))
        return lines

    def _assign_gids_to_lines(self, lines):
        line_map = {}
        for line_key in sorted(lines.keys(), key=lambda k: k[0]):
            line_map[line_key] = self.global_id
            self.global_id += 1
        return line_map

    def _extract_tables(self, page, global_tid):
        """Extract tables with their structure including cell boundaries."""
        tables = []
        table_objects = []  # Keep reference to table objects for cell position lookup

        for table in page.find_tables():
            tables.append(
                {
                    "tid": global_tid,
                    "bbox": list(table.bbox),
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                    "table_obj": table,  # Store table object for cell lookup
                }
            )
            table_objects.append(table)
            global_tid += 1
        return tables, global_tid

    def _find_cell_position_in_table(self, bbox, table_data):
        """
        Find the row and column position of a cell within a table.

        Args:
            bbox: BoundingBox of the field
            table_data: List of table dictionaries with table objects

        Returns:
            tuple: (tid, row_index, col_index) or (None, None, None) if not in table
        """
        for table_info in table_data:
            table_bbox = table_info["bbox"]

            # Check if cell is within table bounds
            if (
                bbox.l >= table_bbox[0]
                and bbox.r <= table_bbox[2]
                and bbox.t >= table_bbox[1]
                and bbox.b <= table_bbox[3]
            ):

                table_obj = table_info.get("table_obj")
                if not table_obj:
                    # If no table object, try to estimate position based on bbox
                    row_idx, col_idx = self._estimate_cell_position(bbox, table_info)
                    return table_info["tid"], row_idx, col_idx

                # Calculate cell position based on bbox
                # PyMuPDF tables have cells accessible via table.cells
                cell_center_x = (bbox.l + bbox.r) / 2
                cell_center_y = (bbox.t + bbox.b) / 2

                # Find which row and column this cell belongs to
                try:
                    # Method 1: Try to find exact match using cell center point
                    for row_idx in range(table_info["row_count"]):
                        for col_idx in range(table_info["col_count"]):
                            try:
                                cell = table_obj.cell(row_idx, col_idx)
                                if cell:
                                    cell_bbox = cell.bbox
                                    # Check if center point is within this cell
                                    if (
                                        cell_bbox[0] <= cell_center_x <= cell_bbox[2]
                                        and cell_bbox[1]
                                        <= cell_center_y
                                        <= cell_bbox[3]
                                    ):
                                        return table_info["tid"], row_idx, col_idx
                            except Exception:
                                continue

                    # Method 2: If exact match fails, find closest cell
                    logger.info(
                        f"Exact cell position not found for field in table {table_info['tid']}, using closest match"
                    )
                    min_distance = float("inf")
                    best_row, best_col = None, None

                    for row_idx in range(table_info["row_count"]):
                        for col_idx in range(table_info["col_count"]):
                            try:
                                cell = table_obj.cell(row_idx, col_idx)
                                if cell:
                                    cell_bbox = cell.bbox
                                    # Calculate center of table cell
                                    cell_cx = (cell_bbox[0] + cell_bbox[2]) / 2
                                    cell_cy = (cell_bbox[1] + cell_bbox[3]) / 2
                                    # Distance from field center to cell center
                                    distance = (
                                        (cell_cx - cell_center_x) ** 2
                                        + (cell_cy - cell_center_y) ** 2
                                    ) ** 0.5
                                    if distance < min_distance:
                                        min_distance = distance
                                        best_row, best_col = row_idx, col_idx
                            except Exception:
                                continue

                    if best_row is not None and best_col is not None:
                        logger.info(
                            f"Found closest cell: row={best_row}, col={best_col} (distance={min_distance:.2f})"
                        )
                        return table_info["tid"], best_row, best_col

                except Exception as e:
                    logger.warning(
                        f"Error determining cell position in table {table_info['tid']}: {e}"
                    )

                # Method 3: Fallback - estimate based on bbox position
                row_idx, col_idx = self._estimate_cell_position(bbox, table_info)
                if row_idx is not None and col_idx is not None:
                    logger.info(
                        f"Using estimated position: row={row_idx}, col={col_idx}"
                    )
                    return table_info["tid"], row_idx, col_idx

                # Last resort: return tid with unknown row/col
                logger.warning(
                    f"Could not determine row/col for field in table {table_info['tid']}"
                )
                return table_info["tid"], None, None

        return None, None, None

    def _estimate_cell_position(self, bbox, table_info):
        """
        Estimate cell position based on bbox location within table.
        This is a fallback when exact cell lookup fails.

        Args:
            bbox: BoundingBox of the field
            table_info: Table dictionary with bbox, row_count, col_count

        Returns:
            tuple: (row_index, col_index) estimated position
        """
        try:
            table_bbox = table_info["bbox"]
            row_count = table_info["row_count"]
            col_count = table_info["col_count"]

            # Calculate approximate cell dimensions
            table_width = table_bbox[2] - table_bbox[0]
            table_height = table_bbox[3] - table_bbox[1]
            cell_height = table_height / row_count
            cell_width = table_width / col_count

            # Calculate field center
            field_center_x = (bbox.l + bbox.r) / 2
            field_center_y = (bbox.t + bbox.b) / 2

            # Estimate row (based on vertical position)
            row_offset = field_center_y - table_bbox[1]
            estimated_row = int(row_offset / cell_height)
            estimated_row = max(
                0, min(estimated_row, row_count - 1)
            )  # Clamp to valid range

            # Estimate column (based on horizontal position)
            col_offset = field_center_x - table_bbox[0]
            estimated_col = int(col_offset / cell_width)
            estimated_col = max(
                0, min(estimated_col, col_count - 1)
            )  # Clamp to valid range

            return estimated_row, estimated_col

        except Exception as e:
            logger.warning(f"Could not estimate cell position: {e}")
            return None, None

    def _assign_fid_and_gid_to_field(
        self, rect, widget, lines, line_map, table_data, page_num
    ):
        fid = self.global_fid
        bbox = BoundingBox(
            left=rect.x0, t=rect.y0, r=rect.x1, b=rect.y1, rounding=self.rounding
        )

        field_type_str = self._get_field_type_new(widget)

        # Find table assignment with row and column information
        assigned_table_tid, row_idx, col_idx = self._find_cell_position_in_table(
            bbox, table_data
        )

        min_distance = float("inf")
        closest_line = None
        for (y0, y1), words in lines.items():
            if words:
                _, (_, _, _, line_y1), _ = words[0]
                distance = abs(rect.y1 - line_y1)
                if distance < min_distance:
                    min_distance = distance
                    closest_line = (y0, y1)

        if closest_line and min_distance <= self.WIDGET_LINE_DISTANCE_THRESHOLD:
            line_key = closest_line
        else:
            line_key = (round(rect.y0, self.rounding), round(rect.y1, self.rounding))
            if line_key not in lines:
                lines[line_key] = []
                line_map[line_key] = self.global_id
                self.global_id += 1

        field_tag = f"{field_type_str}_FIELD"

        if assigned_table_tid:
            field_tag = "TABLE_CELL_FIELD"

        field_text = f"[{field_tag}:{fid}]"
        synthetic_width = len(field_text) * self.AVG_CHAR_WIDTH
        x0 = rect.x0
        x1 = x0 + synthetic_width
        lines[line_key].append((field_text, (x0, rect.y0, x1, rect.y1), 9999))

        # lines[line_key].append((f"[{field_tag}:{fid}]", (rect.x0, rect.y0, rect.x1, rect.y1), 9999))

        gid = line_map[line_key]
        self.fid_to_gid_map[fid] = gid

        form_field = {
            "type_inferred": field_tag,
            "field_type": field_type_str,
            "field_type_new": self._get_field_type_new(widget),
            "field_flag": widget.field_flags,
            "bbox": bbox.to_dict(),
            "fid": fid,
            "page": page_num,
            "field_name": widget.field_name or None,
            "field_value": widget.field_value,
            "gid": gid,
        }

        # Add table cell information if field is in a table
        if assigned_table_tid is not None:
            form_field["tid"] = assigned_table_tid
            if row_idx is not None:
                form_field["row"] = row_idx
            if col_idx is not None:
                form_field["col"] = col_idx

        self.global_fid += 1
        return fid, gid, form_field, assigned_table_tid

    def _process_lines(self, lines, line_map, page_num, global_tid):
        processed = []

        for page_pid, line_key in enumerate(sorted(lines.keys()), start=1):
            words = sorted(lines[line_key], key=lambda w: w[1][0])
            if not words:
                continue

            full_text = ""
            previous_x1 = None

            for i, (word, (x0, _y0, x1, _y1), _) in enumerate(words):

                if i == 0:
                    gap = max(0, x0 - self.LEFT_MARGIN)
                    space_count = int(gap / self.AVG_CHAR_WIDTH)
                    full_text += " " * space_count
                else:
                    gap = max(0, x0 - previous_x1)
                    space_count = int(gap / self.AVG_CHAR_WIDTH)
                    full_text += " " * max(1, space_count)

                full_text += word
                previous_x1 = x1

            bbox = BoundingBox(
                left=min(w[1][0] for w in words),
                t=line_key[0],
                r=max(w[1][2] for w in words),
                b=line_key[1],
                rounding=self.rounding,
            )

            processed.append(
                {
                    "text": full_text,
                    "bbox": bbox.to_dict(),
                    "gid": line_map[line_key],
                    "pid": page_pid,
                    "tid": global_tid,
                    "page": page_num,
                }
            )

        return processed

    def _compute_page_metadata(self, page_fids, page_gids):
        return {
            "start_fid": min(page_fids) if page_fids else -1,
            "end_fid": max(page_fids) if page_fids else -1,
            "total_fids": len(page_fids),
            "start_gid": min(page_gids) if page_gids else -1,
            "end_gid": max(page_gids) if page_gids else -1,
        }

    def extract(self, s3_pdf_path: str, storage_config: dict) -> dict:
        """
        Extract form fields and text from PDF

        Args:
            s3_pdf_path: S3 path to PDF file
            storage_config: Configuration for saving output

        Returns:
            dict: Extracted data with pages, fields, tables

        Raises:
            ValueError: If s3_pdf_path is invalid
            FileNotFoundError: If PDF not found in S3
            RuntimeError: If extraction fails
        """
        if not s3_pdf_path:
            raise ValueError("s3_pdf_path cannot be empty")

        if not storage_config:
            raise ValueError("storage_config cannot be empty")

        from pdf_autofillr_mapper.clients.s3_client import S3Client

        doc = None

        try:
            # Read PDF from S3 as bytes
            s3_client = S3Client()
            logger.info(f"Reading PDF from S3: {s3_pdf_path}")

            try:
                pdf_bytes = s3_client.read_pdf_from_s3(s3_pdf_path)
            except Exception as e:
                logger.error(f"Failed to read PDF from S3: {s3_pdf_path}")
                raise FileNotFoundError(f"PDF not found in S3: {s3_pdf_path}") from e

            if not pdf_bytes:
                raise ValueError(f"PDF file is empty: {s3_pdf_path}")

            try:
                doc = fitz.open("pdf", pdf_bytes)
            except Exception as e:
                logger.error(f"Failed to open PDF with PyMuPDF: {str(e)}")
                raise RuntimeError(
                    f"Invalid or corrupted PDF file: {s3_pdf_path}"
                ) from e

            if doc.page_count == 0:
                raise ValueError(f"PDF has no pages: {s3_pdf_path}")

            logger.info(
                f"Starting extraction from PDF: {s3_pdf_path} ({doc.page_count} pages)"
            )
            extracted_data: dict[Any, Any] = {"pages": []}
            global_tid = 1

        except (ValueError, FileNotFoundError, RuntimeError):
            raise
        except Exception as e:
            logger.error(
                f"Failed to initialize PDF extraction: {str(e)}", exc_info=True
            )
            raise RuntimeError(f"PDF extraction initialization failed: {str(e)}") from e

        try:
            for page_num, page in enumerate(doc, start=1):
                words = page.get_text("words")
                widgets = {w.rect: w for w in page.widgets()}
                lines = self._extract_words_by_line(words)
                line_map = self._assign_gids_to_lines(lines)

                table_data, global_tid = self._extract_tables(page, global_tid)
                form_fields, page_fids, page_gids, table_cell_info = [], [], [], {}

                for rect, widget in widgets.items():
                    fid, gid, form_field, table_id = self._assign_fid_and_gid_to_field(
                        rect, widget, lines, line_map, table_data, page_num
                    )
                    form_fields.append(form_field)
                    page_fids.append(fid)
                    page_gids.append(gid)
                    if table_id is not None:
                        # Build table_cell_info with tid, row, and col from form_field
                        cell_info = {"tid": table_id}
                        if "row" in form_field:
                            cell_info["row"] = form_field["row"]
                        if "col" in form_field:
                            cell_info["col"] = form_field["col"]
                        table_cell_info[fid] = cell_info

                text_elements = self._process_lines(
                    lines, line_map, page_num, global_tid
                )
                page_metadata = self._compute_page_metadata(page_fids, page_gids)

                form_fields.sort(
                    key=lambda el: (el["bbox"]["bottom"], el["bbox"]["right"])
                )

                # Clean table_data by removing non-serializable table_obj before adding to output
                clean_table_data = [
                    {k: v for k, v in table.items() if k != "table_obj"}
                    for table in table_data
                ]

                extracted_data["pages"].append(
                    {
                        "page_number": page_num,
                        "text_elements": text_elements,
                        "form_fields": form_fields,
                        "tables": clean_table_data,
                        "table_cell_info": table_cell_info,
                        "metadata": page_metadata,
                    }
                )

            logger.info(
                f"Extraction completed successfully: {len(extracted_data['pages'])} pages processed"
            )

            # Save extracted data
            try:
                save_json(extracted_data, storage_config)
                logger.info(
                    f"Extracted data saved to: {storage_config.get('path', 'unknown')}"
                )
            except Exception as e:
                logger.error(f"Failed to save extracted data: {str(e)}", exc_info=True)
                raise RuntimeError(
                    f"Failed to save extraction results: {str(e)}"
                ) from e

            return extracted_data

        except Exception as e:
            logger.error(
                f"Extraction failed on page {page_num if 'page_num' in locals() else 'unknown'}: {str(e)}",
                exc_info=True,
            )
            raise RuntimeError(f"PDF extraction failed: {str(e)}") from e
        finally:
            # Ensure PDF document is properly closed to free memory
            if doc:
                try:
                    doc.close()
                    logger.debug("PDF document closed")
                except Exception as e:
                    logger.warning(f"Error closing PDF document: {e}")
