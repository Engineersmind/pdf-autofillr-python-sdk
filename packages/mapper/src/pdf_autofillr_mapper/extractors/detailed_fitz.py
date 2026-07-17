import io as _io
import sys as _sys

_old_stdout, _old_stderr = _sys.stdout, _sys.stderr
_sys.stdout = _sys.stderr = _io.StringIO()
import fitz  # noqa: E402

_sys.stdout, _sys.stderr = _old_stdout, _old_stderr

import logging  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
from collections import defaultdict  # noqa: E402
from typing import Any  # noqa: E402

from pdf_autofillr_mapper.models.bounding_box import BoundingBox  # noqa: E402
from pdf_autofillr_mapper.utils.storage import save_json  # noqa: E402

os.environ.setdefault("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "0")

logger = logging.getLogger(__name__)


class DocumentAnalyzer:
    """
    Phase 4: Document-level analysis for cross-page context.
    Learns font patterns, validates consistency, and refines classifications.
    """

    def __init__(self):
        # Font pattern learning: track which fonts/sizes map to which heading levels
        self.font_patterns = defaultdict(
            lambda: defaultdict(int)
        )  # {(font_name, size): {h1: count, h2: count}}

        # Cross-page consistency tracking
        self.heading_sequences = []  # [(page_num, heading_type, text, font_size), ...]

        # Repeated text detection (for headers/footers)
        self.text_occurrences = defaultdict(list)  # {text: [(page_num, position), ...]}

        # Document structure validation
        self.pages_with_h1 = set()
        self.pages_with_h2 = set()
        self.pages_with_h3 = set()

        # Style signature tracking
        self.style_signatures = defaultdict(int)  # {(font_name, size, is_bold): count}

        # Numbering pattern tracking
        self.numbering_patterns = []  # Track numbered headings across pages

        # Font size statistics across entire document
        self.all_font_sizes = []
        self.heading_font_sizes = []

    def learn_from_page(self, page_num, text_elements, page_stats):
        """
        Learn patterns from a single page's extracted elements.

        Args:
            page_num: Page number (0-based)
            text_elements: List of extracted text elements with classifications
            page_stats: Font statistics for this page
        """
        for element in text_elements:
            heading_type = element.get("heading_type", "normal")
            text = element.get("text", "").strip()
            font_name = element.get("font_name", "unknown")
            font_size = element.get("font_size", 12)
            is_bold = element.get("is_bold", False)
            is_header = element.get("is_header", False)
            is_footer = element.get("is_footer", False)

            # Track all font sizes
            self.all_font_sizes.append(font_size)

            # Skip headers/footers for pattern learning
            if is_header or is_footer:
                continue

            # Learn font patterns for headings
            if heading_type in ["h1", "h2", "h3"]:
                font_key = (font_name, round(font_size, 1))
                self.font_patterns[font_key][heading_type] += 1
                self.heading_font_sizes.append(font_size)

                # Track heading sequences
                self.heading_sequences.append(
                    {
                        "page": page_num,
                        "type": heading_type,
                        "text": text,
                        "font_size": font_size,
                        "is_bold": is_bold,
                    }
                )

            # Track repeated text (for better header/footer detection)
            text_normalized = text.lower().strip()
            if len(text_normalized) > 5:  # Ignore very short text
                self.text_occurrences[text_normalized].append(
                    {
                        "page": page_num,
                        "position": element.get("bbox", {}).get("top", 0),
                        "heading_type": heading_type,
                    }
                )

            # Track style signatures
            style_key = (font_name, round(font_size, 1), is_bold)
            self.style_signatures[style_key] += 1

            # Track numbering patterns in headings
            if heading_type in ["h1", "h2", "h3"]:
                has_pattern, level, pattern_type = self._detect_numbering_pattern(text)
                if has_pattern:
                    self.numbering_patterns.append(
                        {
                            "page": page_num,
                            "text": text,
                            "pattern_type": pattern_type,
                            "suggested_level": level,
                            "current_type": heading_type,
                        }
                    )

            # Track which pages have which heading levels
            if heading_type == "h1":
                self.pages_with_h1.add(page_num)
            elif heading_type == "h2":
                self.pages_with_h2.add(page_num)
            elif heading_type == "h3":
                self.pages_with_h3.add(page_num)

    def _detect_numbering_pattern(self, text):
        """Helper to detect numbering patterns (reuse from main class)."""
        text = text.strip()

        # Level 1 patterns: "1.", "1 ", "Chapter 1", "Section 1", "Part I"
        if re.match(r"^\d+\.?\s+[A-Z]", text) or re.match(
            r"^(Chapter|Section|Part|Article)\s+[IVX\d]+", text, re.IGNORECASE
        ):
            return (True, 1, "decimal_1")

        # Level 2 patterns: "1.1", "1.2", "A.", "I."
        if re.match(r"^\d+\.\d+\.?\s+[A-Z]", text):
            return (True, 2, "decimal_2")
        if re.match(r"^[A-Z]\.?\s+[A-Z]", text):
            return (True, 2, "alpha")
        if re.match(r"^[IVX]+\.?\s+[A-Z]", text):
            return (True, 2, "roman")

        # Level 3 patterns: "1.1.1", "a)", "(i)"
        if re.match(r"^\d+\.\d+\.\d+\.?\s+", text):
            return (True, 3, "decimal_3")
        if re.match(r"^[a-z]\)?\s+[A-Z]", text):
            return (True, 3, "lower_alpha")
        if re.match(r"^\([ivx]+\)\s+", text):
            return (True, 3, "lower_roman")

        return (False, None, None)

    def detect_repeated_elements(self, min_occurrences=3):
        """
        Detect text that appears repeatedly across pages (better header/footer detection).

        Args:
            min_occurrences: Minimum number of times text must appear

        Returns:
            dict: {text: {'pages': [page_nums], 'likely_type': 'header'/'footer'}}
        """
        repeated = {}

        for text, occurrences in self.text_occurrences.items():
            if len(occurrences) >= min_occurrences:
                pages = [occ["page"] for occ in occurrences]
                positions = [occ["position"] for occ in occurrences]

                # Determine if header or footer based on position consistency
                avg_position = sum(positions) / len(positions)
                likely_type = "header" if avg_position < 100 else "footer"

                repeated[text] = {
                    "pages": pages,
                    "occurrences": len(occurrences),
                    "likely_type": likely_type,
                    "avg_position": avg_position,
                }

        return repeated

    def get_dominant_font_patterns(self):
        """
        Get the most common font patterns for each heading level.

        Returns:
            dict: {heading_type: [(font_name, size, confidence), ...]}
        """
        patterns = {"h1": [], "h2": [], "h3": []}

        for font_key, heading_counts in self.font_patterns.items():
            font_name, size = font_key
            total = sum(heading_counts.values())

            for heading_type in ["h1", "h2", "h3"]:
                count = heading_counts[heading_type]
                if count > 0:
                    confidence = count / total if total > 0 else 0
                    patterns[heading_type].append((font_name, size, confidence, count))

        # Sort by count (most common first)
        for heading_type in patterns:
            patterns[heading_type].sort(key=lambda x: x[3], reverse=True)

        return patterns

    def validate_heading_sequences(self):
        """
        Validate heading hierarchy across pages.
        Detect common issues: H3 without H2, inconsistent numbering, etc.

        Returns:
            list: Issues found with suggested corrections
        """
        issues = []

        # Check for H3 on pages without H2
        for page in self.pages_with_h3:
            if page not in self.pages_with_h2 and page not in self.pages_with_h1:
                issues.append(
                    {
                        "page": page,
                        "issue": "h3_without_parent",
                        "description": "H3 found without H1 or H2 on this page",
                    }
                )

        # Check numbering pattern consistency
        decimal_sequences = [
            p for p in self.numbering_patterns if "decimal" in p["pattern_type"]
        ]
        if decimal_sequences:
            # Check if numbering levels match heading levels
            mismatches = []
            for pattern in decimal_sequences:
                expected_level = pattern["suggested_level"]
                actual_type = pattern["current_type"]
                expected_type = f"h{expected_level}"

                if expected_type != actual_type:
                    mismatches.append(pattern)

            if mismatches:
                issues.append(
                    {
                        "issue": "numbering_level_mismatch",
                        "count": len(mismatches),
                        "description": f"{len(mismatches)} headings have numbering that suggests different level",
                        "examples": mismatches[:3],
                    }
                )

        return issues

    def get_document_statistics(self):
        """
        Get document-wide statistics for reporting.

        Returns:
            dict: Comprehensive statistics
        """
        repeated = self.detect_repeated_elements()
        font_patterns = self.get_dominant_font_patterns()
        issues = self.validate_heading_sequences()

        return {
            "total_pages_analyzed": (
                len(set(seq["page"] for seq in self.heading_sequences))
                if self.heading_sequences
                else 0
            ),
            "pages_with_h1": len(self.pages_with_h1),
            "pages_with_h2": len(self.pages_with_h2),
            "pages_with_h3": len(self.pages_with_h3),
            "total_headings": len(self.heading_sequences),
            "repeated_elements": len(repeated),
            "likely_headers_footers": {
                text: info
                for text, info in repeated.items()
                if info["occurrences"] >= 3
            },
            "font_patterns": {
                "h1": font_patterns["h1"][:3] if font_patterns["h1"] else [],
                "h2": font_patterns["h2"][:3] if font_patterns["h2"] else [],
                "h3": font_patterns["h3"][:3] if font_patterns["h3"] else [],
            },
            "numbering_patterns": len(self.numbering_patterns),
            "validation_issues": issues,
            "font_size_range": {
                "min": min(self.all_font_sizes) if self.all_font_sizes else 0,
                "max": max(self.all_font_sizes) if self.all_font_sizes else 0,
                "heading_min": (
                    min(self.heading_font_sizes) if self.heading_font_sizes else 0
                ),
                "heading_max": (
                    max(self.heading_font_sizes) if self.heading_font_sizes else 0
                ),
            },
        }

    def refine_classifications(self, all_pages_elements):
        """
        Phase 4 refinement: Use learned patterns to correct misclassifications.

        Args:
            all_pages_elements: List of all text elements from all pages

        Returns:
            list: Refined text elements with Phase 4 corrections
        """
        refined = []
        self.get_dominant_font_patterns()
        repeated = self.detect_repeated_elements()

        # Create lookup for repeated text (likely headers/footers)
        repeated_text = {text.lower().strip() for text in repeated.keys()}

        for element in all_pages_elements:
            refined_element = element.copy()
            text = element.get("text", "").strip()
            text_lower = text.lower().strip()
            font_name = element.get("font_name", "unknown")
            font_size = element.get("font_size", 12)
            heading_type = element.get("heading_type", "normal")
            element.get("page", 0)

            phase4_corrections = []

            # Correction 1: Mark repeated text as header/footer if not already marked
            if (
                text_lower in repeated_text
                and not element.get("is_header")
                and not element.get("is_footer")
            ):
                repeated_info = repeated.get(text_lower, {})
                if repeated_info.get("occurrences", 0) >= 3:
                    likely_type = repeated_info.get("likely_type", "header")
                    if likely_type == "header":
                        refined_element["is_header"] = True
                        phase4_corrections.append("repeated_header_detected")
                    else:
                        refined_element["is_footer"] = True
                        phase4_corrections.append("repeated_footer_detected")

                    # Downgrade heading if it's a repeated element
                    if heading_type in ["h1", "h2", "h3"]:
                        refined_element["heading_type"] = "normal"
                        phase4_corrections.append(
                            f"downgraded_{heading_type}_to_normal"
                        )

            # Correction 2: Apply dominant font patterns
            if (
                heading_type in ["h1", "h2", "h3"]
                and not refined_element.get("is_header")
                and not refined_element.get("is_footer")
            ):
                font_key = (font_name, round(font_size, 1))

                # Check if this font pattern is strongly associated with a different level
                if font_key in self.font_patterns:
                    pattern_votes = self.font_patterns[font_key]
                    if pattern_votes:
                        # Get the most common heading level for this font
                        most_common_level = max(
                            pattern_votes.items(), key=lambda x: x[1]
                        )
                        most_common_type = most_common_level[0]
                        most_common_count = most_common_level[1]
                        total_count = sum(pattern_votes.values())

                        # If >70% of uses are for a different level, suggest correction
                        if (
                            most_common_count / total_count > 0.7
                            and most_common_type != heading_type
                        ):
                            phase4_corrections.append(
                                f"font_pattern_suggests_{most_common_type}"
                            )
                            # Store suggestion but don't auto-correct (conservative approach)
                            refined_element["phase4_suggestion"] = most_common_type

            # Correction 3: Validate numbering patterns against heading level
            has_pattern, suggested_level, pattern_type = self._detect_numbering_pattern(
                text
            )
            if has_pattern and heading_type in ["h1", "h2", "h3"]:
                expected_type = f"h{suggested_level}"
                if expected_type != heading_type:
                    phase4_corrections.append(f"numbering_suggests_{expected_type}")
                    # For strong numbering patterns, we can be more confident
                    if pattern_type in ["decimal_1", "decimal_2", "decimal_3"]:
                        refined_element["phase4_suggestion"] = expected_type

            # Add Phase 4 metadata
            if phase4_corrections:
                refined_element["phase4_corrections"] = phase4_corrections
                confidence = refined_element.get("confidence", 1.0)
                # Adjust confidence based on corrections
                if (
                    "repeated_header_detected" in phase4_corrections
                    or "repeated_footer_detected" in phase4_corrections
                ):
                    refined_element["confidence"] = (
                        1.0  # High confidence for repeated elements
                    )
                elif refined_element.get("phase4_suggestion"):
                    refined_element["confidence"] = max(
                        0.6, confidence * 0.8
                    )  # Lower confidence if suggested change

            refined.append(refined_element)

        return refined


def debug_font_flags(pdf_path, max_samples=50):
    """
    Debug utility to print actual font flags found in a PDF.
    Helps verify bold/italic detection is working correctly.

    Args:
        pdf_path: Path to PDF file
        max_samples: Maximum number of unique font samples to show
    """
    try:
        doc = fitz.open(pdf_path)
        logger.info("\n" + "=" * 80)
        logger.info("Font Flags Debug Information")
        logger.info("=" * 80)
        logger.info("PyMuPDF Font Flag Bits:")
        logger.info("  bit 0 (1): superscript")
        logger.info("  bit 1 (2): italic")
        logger.info("  bit 2 (4): serifed")
        logger.info("  bit 3 (8): monospaced")
        logger.info("  bit 4 (16): bold")
        logger.info("=" * 80)

        seen_combinations = {}
        sample_count = 0

        for page_num in range(min(3, len(doc))):  # Check first 3 pages
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if text and sample_count < max_samples:
                                font_name = span.get("font", "unknown")
                                flags = span.get("flags", 0)
                                span.get("size", 12)

                                key = (font_name, flags)
                                if key not in seen_combinations:
                                    seen_combinations[key] = []
                                    sample_count += 1

                                if (
                                    len(seen_combinations[key]) < 3
                                ):  # Store up to 3 samples per combo
                                    seen_combinations[key].append(text[:40])

        # Print results
        logger.info(
            f"\nFound {len(seen_combinations)} unique font+flag combinations:\n"
        )

        for (font_name, flags), samples in sorted(seen_combinations.items()):
            is_bold = bool(flags & (1 << 4))
            is_italic = bool(flags & (1 << 1))
            is_super = bool(flags & (1 << 0))
            is_serif = bool(flags & (1 << 2))
            is_mono = bool(flags & (1 << 3))

            # Check if font name contains bold/semibold indicators
            font_name_lower = font_name.lower()
            has_bold_in_name = any(
                indicator in font_name_lower
                for indicator in ["bold", "semibold", "demi", "heavy", "black"]
            )

            style_tags = []
            if is_bold or has_bold_in_name:
                if has_bold_in_name and not is_bold:
                    style_tags.append("BOLD(name)")
                else:
                    style_tags.append("BOLD")
            if is_italic:
                style_tags.append("ITALIC")
            if is_super:
                style_tags.append("SUPER")
            if is_serif:
                style_tags.append("SERIF")
            if is_mono:
                style_tags.append("MONO")

            style_str = "+".join(style_tags) if style_tags else "NORMAL"

            logger.info(
                f"Font: {font_name:30} | Flags: {flags:3} (binary: {bin(flags):10}) | {style_str}"
            )
            for sample in samples[:2]:
                logger.info(f'      Sample: "{sample}"')
            logger.info("")

        doc.close()
        logger.info("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Error in debug_font_flags: {e}", exc_info=True)


class DetailedFitzExtractor:
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

    def _extract_pdf_outline(self, doc):
        """
        Extract PDF outline/bookmarks (Table of Contents) if available.

        Args:
            doc: PyMuPDF document object

        Returns:
            dict: Outline structure with page mapping
                  Format: {page_num: [(level, title, bbox), ...]}
        """
        outline_by_page = {}

        try:
            toc = doc.get_toc()  # Returns [(level, title, page_num, dest), ...]

            if toc:
                logger.info(f"PDF has {len(toc)} outline entries (bookmarks)")

                for entry in toc:
                    level = entry[0]  # 1=H1, 2=H2, 3=H3, etc.
                    title = entry[1]
                    page_num = entry[2]  # 1-based page number

                    if page_num not in outline_by_page:
                        outline_by_page[page_num] = []

                    outline_by_page[page_num].append(
                        {
                            "level": level,
                            "title": title.strip(),
                            "heading_type": f"h{min(level, 3)}",  # Cap at h3
                        }
                    )
            else:
                logger.info(
                    "PDF has no outline/bookmarks - will use font-based detection"
                )

        except Exception as e:
            logger.warning(f"Error extracting PDF outline: {e}")

        return outline_by_page

    def _match_text_to_outline(self, text_element, outline_entries):
        """
        Try to match a text element to an outline entry.

        Args:
            text_element: Text element dict with 'text' field
            outline_entries: List of outline entries for this page

        Returns:
            str or None: Matched heading type (h1, h2, h3) or None
        """
        if not outline_entries:
            return None

        text = text_element.strip().lower()

        # Try exact match first
        for entry in outline_entries:
            outline_title = entry["title"].lower()
            if text == outline_title:
                logger.debug(f"Exact match: '{text[:50]}' -> {entry['heading_type']}")
                return entry["heading_type"]

        # Try partial match (outline title contained in text or vice versa)
        for entry in outline_entries:
            outline_title = entry["title"].lower()
            # Remove common prefixes/suffixes for better matching
            cleaned_text = text.strip(".:;-– ")
            cleaned_title = outline_title.strip(".:;-– ")

            if len(cleaned_title) > 10:  # Only match longer titles
                if (
                    cleaned_title in cleaned_text
                    or cleaned_text in cleaned_title
                    or cleaned_text.startswith(cleaned_title)
                    or cleaned_title.startswith(cleaned_text)
                ):
                    logger.debug(
                        f"Partial match: '{text[:50]}' -> {entry['heading_type']}"
                    )
                    return entry["heading_type"]

        return None

    def _detect_underlines(self, page):
        """
        Detect underlined regions on the page by analyzing drawing paths.

        Args:
            page: PyMuPDF page object

        Returns:
            list: List of (y_start, y_end) tuples representing underlined vertical positions
        """
        underlined_regions = []

        try:
            # Get page drawings (lines, rectangles, etc.)
            drawings = page.get_drawings()

            for drawing in drawings:
                # Check if it's a horizontal line (potential underline)
                if drawing.get("type") == "l":  # Line
                    items = drawing.get("items", [])
                    for item in items:
                        if len(item) >= 2:
                            # Get line coordinates
                            start = item[1] if len(item) > 1 else None
                            end = item[2] if len(item) > 2 else None

                            if start and end:
                                x1, y1 = start
                                x2, y2 = end

                                # Check if line is mostly horizontal (underline)
                                if (
                                    abs(y2 - y1) < 2 and abs(x2 - x1) > 20
                                ):  # Horizontal line
                                    underlined_regions.append(
                                        (min(y1, y2) - 5, max(y1, y2) + 5)
                                    )
        except Exception as e:
            logger.debug(f"Could not detect underlines: {e}")

        return underlined_regions

    def _is_text_underlined(self, bbox, underlined_regions):
        """
        Check if text at given bbox is underlined.

        Args:
            bbox: BoundingBox object
            underlined_regions: List of (y_start, y_end) tuples

        Returns:
            bool: True if text is underlined
        """
        if not underlined_regions:
            return False

        # Check if bottom of text bbox is near any underline
        text_bottom = bbox.b

        for y_start, y_end in underlined_regions:
            # Check if underline is just below the text (within 10 pixels)
            if y_start <= text_bottom <= y_end + 10:
                return True

        return False

    def _extract_text_with_fonts(self, page):
        """
        Extract text with detailed font information including size, style, and position.

        PyMuPDF font flags:
        - bit 0 (1): superscripted (2^0)
        - bit 1 (2): italic (2^1)
        - bit 2 (4): serifed (2^2)
        - bit 3 (8): monospaced (2^3)
        - bit 4 (16): bold (2^4)

        Args:
            page: PyMuPDF page object

        Returns:
            list: List of dictionaries containing text and font metadata
        """
        text_data = []

        try:
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if span.get(
                                "text", ""
                            ).strip():  # Only process non-empty text
                                flags = span.get("flags", 0)
                                font_name = span.get("font", "unknown")

                                # Check both flag and font name for bold/semibold
                                flag_bold = bool(flags & (1 << 4))
                                font_name_lower = font_name.lower()
                                name_bold = any(
                                    indicator in font_name_lower
                                    for indicator in [
                                        "bold",
                                        "semibold",
                                        "demi",
                                        "heavy",
                                        "black",
                                    ]
                                )
                                is_bold = flag_bold or name_bold

                                text_data.append(
                                    {
                                        "text": span["text"],
                                        "font_size": span.get("size", 12),
                                        "font_name": font_name,
                                        "flags": flags,
                                        "is_bold": is_bold,  # Combined check
                                        "is_italic": bool(flags & (1 << 1)),  # bit 1
                                        "is_superscript": bool(
                                            flags & (1 << 0)
                                        ),  # bit 0
                                        "bbox": span.get("bbox", (0, 0, 0, 0)),
                                        "color": span.get("color", 0),
                                        "origin": span.get("origin", (0, 0)),
                                    }
                                )
        except Exception as e:
            logger.warning(f"Error extracting text with fonts: {e}")

        return text_data

    def _calculate_font_statistics(self, text_data):
        """
        Calculate font size statistics for the page to determine baseline for heading detection.

        Args:
            text_data: List of text items with font information

        Returns:
            dict: Statistics including average, median, max, min font sizes
        """
        if not text_data:
            return {"average": 12, "median": 12, "max": 12, "min": 12}

        # Filter out very small or very large outliers that might skew statistics
        font_sizes = [item["font_size"] for item in text_data if item["text"].strip()]
        font_sizes = [
            size for size in font_sizes if 6 <= size <= 72
        ]  # Reasonable range

        if not font_sizes:
            return {"average": 12, "median": 12, "max": 12, "min": 12}

        sorted_sizes = sorted(font_sizes)

        return {
            "average": sum(font_sizes) / len(font_sizes),
            "median": sorted_sizes[len(sorted_sizes) // 2],
            "max": max(font_sizes),
            "min": min(font_sizes),
        }

    def _detect_numbering_pattern(self, text):
        """
        Phase 3: Detect if text follows a numbering pattern typical of headings.

        Returns:
            tuple: (has_pattern, suggested_level, pattern_type)
        """
        text_stripped = text.strip()

        # Pattern 1: "1. ", "2.3 ", "1.1.1 " style numbering
        match = re.match(r"^(\d+)\.(\d+)?\.?(\d+)?\s+", text_stripped)
        if match:
            if match.group(3):  # 1.1.1
                return (True, 3, "decimal_3")
            elif match.group(2):  # 1.1
                return (True, 2, "decimal_2")
            else:  # 1.
                return (True, 1, "decimal_1")

        # Pattern 2: "A. ", "B. " style (uppercase letters)
        if re.match(r"^[A-Z]\.\s+", text_stripped):
            return (True, 2, "letter_upper")

        # Pattern 3: "a) ", "b) " style (lowercase letters with parenthesis)
        if re.match(r"^[a-z]\)\s+", text_stripped):
            return (True, 3, "letter_lower_paren")

        # Pattern 4: Roman numerals "I. ", "II. ", "III. "
        if re.match(r"^[IVX]+\.\s+", text_stripped):
            return (True, 2, "roman")

        # Pattern 5: Chapter/Section keywords
        if re.match(
            r"^(Chapter|Section|Part|Appendix)\s+\d+", text_stripped, re.IGNORECASE
        ):
            return (True, 1, "chapter")

        # Not a numbered heading
        return (False, 0, None)

    def _analyze_text_position(self, bbox, page_width, page_height):
        """
        Phase 3: Analyze text position for contextual clues.

        Args:
            bbox: BoundingBox object representing the ENTIRE LINE (not individual word)
            page_width: Width of the page
            page_height: Height of the page

        Returns:
            dict: Position analysis with is_centered, is_indented, relative_y
        """
        # Line dimensions
        line_width = bbox.width
        line_left = bbox.l
        line_right = bbox.r

        # Calculate actual margins (whitespace on left and right)
        left_margin = line_left  # Space from left edge to start of text
        right_margin = page_width - line_right  # Space from end of text to right edge

        # Check if centered: left and right margins should be roughly equal
        # Calculate the difference between margins
        margin_difference = abs(left_margin - right_margin)

        # Threshold: margins are "equal" if difference is < 10% of page width
        margin_threshold = page_width * 0.1

        # Centered if:
        # 1. Left and right margins are roughly equal
        # 2. Line is not too wide (< 80% of page width)
        is_centered = (margin_difference < margin_threshold) and (
            line_width / page_width < 0.8
        )

        # Also ensure there IS some margin (not edge-to-edge)
        min_margin = page_width * 0.05  # At least 5% margin on each side
        if left_margin < min_margin or right_margin < min_margin:
            is_centered = False

        # Check if line is indented (left margin > 15% of page width)
        left_margin_threshold = page_width * 0.15
        is_indented = line_left > left_margin_threshold

        # Calculate relative position on page (0 = top, 1 = bottom)
        relative_y = bbox.t / page_height if page_height > 0 else 0

        # Check if near page top (within 20%)
        is_near_top = relative_y < 0.2

        return {
            "is_centered": is_centered,
            "is_indented": is_indented,
            "is_near_top": is_near_top,
            "relative_y": relative_y,
            "text_width_ratio": line_width / page_width if page_width > 0 else 0,
            "left_margin": left_margin,
            "right_margin": right_margin,
            "margin_difference": margin_difference,
        }

    def _analyze_text_capitalization(self, text):
        """
        Phase 3: Analyze text capitalization patterns.

        Returns:
            dict: Capitalization analysis
        """
        text_stripped = text.strip()

        # Remove leading numbers/bullets for analysis
        text_for_analysis = re.sub(r"^[\d\.\)\]\•\◦\▪\->-]+\s*", "", text_stripped)

        if not text_for_analysis:
            return {"is_all_caps": False, "is_title_case": False, "caps_ratio": 0}

        # Count uppercase vs total letters
        letters = [c for c in text_for_analysis if c.isalpha()]
        if not letters:
            return {"is_all_caps": False, "is_title_case": False, "caps_ratio": 0}

        uppercase_count = sum(1 for c in letters if c.isupper())
        caps_ratio = uppercase_count / len(letters)

        # All caps: >90% uppercase
        is_all_caps = caps_ratio > 0.9

        # Title case: First letter of most words is uppercase
        words = text_for_analysis.split()
        if words:
            title_words = sum(1 for w in words if w and w[0].isupper())
            is_title_case = (title_words / len(words)) > 0.7
        else:
            is_title_case = False

        return {
            "is_all_caps": is_all_caps,
            "is_title_case": is_title_case,
            "caps_ratio": caps_ratio,
        }

    def _calculate_whitespace_context(self, line_key, all_line_keys):
        """
        Phase 3: Analyze whitespace around the line.

        Returns:
            dict: Whitespace analysis with space_above, space_below, is_isolated
        """
        sorted_keys = sorted(all_line_keys)
        try:
            current_idx = sorted_keys.index(line_key)
        except ValueError:
            return {"space_above": 0, "space_below": 0, "is_isolated": False}

        # Calculate space above
        if current_idx > 0:
            prev_line_bottom = sorted_keys[current_idx - 1][1]
            current_line_top = line_key[0]
            space_above = current_line_top - prev_line_bottom
        else:
            space_above = 0

        # Calculate space below
        if current_idx < len(sorted_keys) - 1:
            next_line_top = sorted_keys[current_idx + 1][0]
            current_line_bottom = line_key[1]
            space_below = next_line_top - current_line_bottom
        else:
            space_below = 0

        # Line height
        line_height = line_key[1] - line_key[0]

        # Isolated if significant whitespace on both sides (>50% of line height)
        is_isolated = (
            space_above > line_height * 0.5 and space_below > line_height * 0.5
        )

        return {
            "space_above": space_above,
            "space_below": space_below,
            "is_isolated": is_isolated,
            "line_height": line_height,
        }

    def _classify_text_type(self, font_size, flags, text_length, font_stats):
        """
        Determine if text is H1, H2, H3, or normal based on font properties.
        Uses dynamic thresholds based on page-level font statistics.

        STRICTER RULES:
        - H3 MUST be bold (not just larger text)
        - Focus on bold text for heading detection

        Args:
            font_size: Size of the font in points
            flags: Font flags (includes bold, italic, etc.)
            text_length: Length of the text string
            font_stats: Page-level font statistics

        Returns:
            str: Classification - "h1", "h2", "h3", or "normal"
        """
        # Extract bold and italic flags using bit shift operations
        is_bold = bool(flags & (1 << 4))  # bit 4 = bold (value 16)

        avg_size = font_stats["average"]
        max_size = font_stats["max"]
        min_size = font_stats["min"]

        # Calculate relative size ratio
        size_ratio = font_size / avg_size if avg_size > 0 else 1

        # Calculate position in the range (0 = min, 1 = max)
        size_range = max_size - min_size
        if size_range > 0:
            normalized_position = (font_size - min_size) / size_range
        else:
            normalized_position = 0.5

        # Dynamic classification based on statistics
        # STRICTER: Prioritize bold text for headings

        # H1: Maximum font size (with or without bold)
        # - Font size is max OR
        # - Font size >= 90% of max OR
        # - Font size >= 80% of max AND bold
        if (
            font_size >= max_size
            or normalized_position >= 0.9
            or (normalized_position >= 0.8 and is_bold)
        ):
            return "h1"

        # H2: Very large text with bold, or significantly larger
        # - Font size >= 70% of max AND bold OR
        # - Size ratio >= 1.5 (significantly larger without bold) OR
        # - Size ratio >= 1.25 AND bold
        elif (
            (normalized_position >= 0.7 and is_bold)
            or size_ratio >= 1.5
            or (size_ratio >= 1.25 and is_bold)
        ):
            return "h2"

        # H3: MUST be bold (stricter rule)
        # - Any bold text should be at least H3
        # - Bold AND (moderately larger OR short text OR any bold)
        elif is_bold:
            # If bold and significantly larger, might be H2
            if size_ratio >= 1.2:
                return "h2"
            # Otherwise, any bold text is at least H3
            return "h3"

        # Normal text: Everything else
        # - Non-bold text only
        else:
            return "normal"

    def _classify_with_phase3_context(
        self,
        base_classification,
        text,
        bbox,
        page_width,
        page_height,
        font_size,
        is_bold,
        font_stats,
        line_key,
        all_line_keys,
        is_underlined=False,
    ):
        """
        Phase 3: Enhanced classification using position, patterns, and context.
        Refines the base font-based classification with contextual clues.

        Args:
            base_classification: Initial classification from Phase 2
            text: The text content
            bbox: BoundingBox object with l, t, r, b properties
            page_width: Width of the page
            page_height: Height of the page
            font_size: Font size
            is_bold: Whether text is bold
            font_stats: Page font statistics
            line_key: Line position key
            all_line_keys: All line keys on the page
            is_underlined: Whether text is underlined

        Returns:
            tuple: (refined_classification, confidence_score, phase3_hints)
        """
        text_stripped = text.strip()
        text_length = len(text_stripped)

        # Start with base classification
        classification = base_classification
        confidence = 0.5  # Base confidence
        hints = []

        # Skip very short or empty text
        if text_length < 3:
            return ("normal", 0.9, ["too_short"])

        # Analyze numbering patterns
        has_numbering, suggested_level, pattern_type = self._detect_numbering_pattern(
            text_stripped
        )
        if has_numbering:
            hints.append(f"numbered_{pattern_type}")
            confidence += 0.2

            # Numbering strongly suggests heading level
            if suggested_level == 1:
                classification = "h1"
                confidence += 0.2
            elif suggested_level == 2:
                classification = "h2"
                confidence += 0.15
            elif suggested_level == 3:
                classification = "h3"
                confidence += 0.1

        # Analyze position
        position = self._analyze_text_position(bbox, page_width, page_height)

        if position["is_centered"]:
            hints.append("centered")
            confidence += 0.15
            # Centered text is more likely to be H1/H2
            if is_bold and classification == "h3":
                classification = "h2"
            elif is_bold and classification == "normal":
                classification = "h3"

        if position["is_near_top"]:
            hints.append("near_top")
            confidence += 0.1
            # Text near page top more likely to be title/H1
            if is_bold and base_classification in ["h2", "h3"]:
                classification = "h1"

        if position["is_indented"]:
            hints.append("indented")
            # Indented text less likely to be high-level heading
            if classification == "h1":
                classification = "h2"
                hints.append("demoted_indented")

        # Analyze capitalization
        caps = self._analyze_text_capitalization(text_stripped)

        if caps["is_all_caps"]:
            hints.append("all_caps")
            confidence += 0.15
            # ALL CAPS text should be treated as heading
            # Promote to heading based on hierarchy and context
            if classification == "normal":
                # If normal text is ALL CAPS, make it at least H3
                classification = "h3"
                hints.append("promoted_all_caps")

            # Further promote if bold or centered
            if is_bold:
                if classification == "h3":
                    classification = "h2"
                    hints.append("promoted_bold_caps")
                elif classification == "h2" and position["is_centered"]:
                    classification = "h1"
                    hints.append("promoted_centered_caps")

        if caps["is_title_case"]:
            hints.append("title_case")
            confidence += 0.1

        # Analyze whitespace
        whitespace = self._calculate_whitespace_context(line_key, all_line_keys)

        if whitespace["is_isolated"]:
            hints.append("isolated")
            confidence += 0.1
            # Isolated text more likely to be heading
            if is_bold and classification == "normal":
                classification = "h3"

        # Text length considerations
        if text_length < 50:
            hints.append("short_text")
            confidence += 0.05
            # Short bold text more likely heading
        elif text_length > 200:
            hints.append("long_text")
            # Very long text less likely to be heading (unless it's really the title)
            if classification in ["h2", "h3"] and not has_numbering:
                if not (caps["is_all_caps"] or position["is_centered"]):
                    classification = "normal"
                    hints.append("demoted_long")

        # Bold is a strong indicator - already handled in Phase 2
        if is_bold:
            hints.append("bold")
            confidence += 0.1

        # Underline is a strong heading indicator
        if is_underlined:
            hints.append("underlined")
            confidence += 0.2  # Strong signal

            # Underlined text should be treated as heading
            if classification == "normal":
                # Promote to at least H3
                classification = "h3"
                hints.append("promoted_underlined")

            # Further promote if also bold or centered
            if is_bold and classification == "h3":
                classification = "h2"
                hints.append("promoted_underlined_bold")
            elif position["is_centered"] and classification in ["h3", "h2"]:
                classification = "h1"
                hints.append("promoted_underlined_centered")

        # Font size boost
        size_ratio = (
            font_size / font_stats["average"] if font_stats["average"] > 0 else 1
        )
        if size_ratio >= 1.3:
            hints.append("large_font")
            confidence += 0.1

        # Normalize confidence to 0-1 range
        confidence = min(1.0, max(0.0, confidence))

        return (classification, confidence, hints)

    def _extract_words_by_line_with_fonts(self, page, line_tolerance=1):
        """
        Extract words organized by line with font information for heading detection.

        Args:
            page: PyMuPDF page object
            line_tolerance: Vertical tolerance (pixels) for grouping words into lines

        Returns:
            tuple: (lines dict, font_info dict, font_stats dict)
        """
        words = page.get_text("words")
        text_with_fonts = self._extract_text_with_fonts(page)
        font_stats = self._calculate_font_statistics(text_with_fonts)

        lines = {}
        line_font_info = {}  # Store font info per line

        for word in words:
            x0, y0, x1, y1, text, *_ = word

            # For normal text, apply tolerance to group slightly offset lines
            # Round to nearest tolerance value
            y0_rounded = round(y0 / line_tolerance) * line_tolerance
            y1_rounded = round(y1 / line_tolerance) * line_tolerance
            line_key = (y0_rounded, y1_rounded)

            if line_key not in lines:
                lines[line_key] = []
                line_font_info[line_key] = {
                    "font_sizes": [],
                    "flags": [],
                    "text_lengths": [],
                    "matched_count": 0,
                }

            # Handle underscores/dots (field placeholders)
            if re.match(r"[._\u2026-]{2,}", text):
                lines[line_key].append(("", (x0, y0, x1, y1), word[-1]))
            else:
                lines[line_key].append((text, (x0, y0, x1, y1), word[-1]))

            # Find matching font info for this word - improved matching with overlap detection
            matched = False
            for font_data in text_with_fonts:
                font_bbox = font_data["bbox"]
                # Check if word bbox significantly overlaps with font span bbox
                # Use better overlap detection
                x_overlap = max(0, min(x1, font_bbox[2]) - max(x0, font_bbox[0]))
                y_overlap = max(0, min(y1, font_bbox[3]) - max(y0, font_bbox[1]))

                if x_overlap > 0 and y_overlap > 0:
                    # Check if the text matches (case-insensitive partial match)
                    if (
                        text.lower() in font_data["text"].lower()
                        or font_data["text"].lower() in text.lower()
                    ):
                        line_font_info[line_key]["font_sizes"].append(
                            font_data["font_size"]
                        )
                        line_font_info[line_key]["flags"].append(font_data["flags"])
                        line_font_info[line_key]["text_lengths"].append(len(text))
                        line_font_info[line_key]["matched_count"] += 1
                        matched = True
                        break

            # If no match found, use default values but log it
            if not matched and text.strip():
                logger.debug(
                    f"No font match found for word: '{text}' at ({x0:.1f}, {y0:.1f})"
                )

        return lines, line_font_info, font_stats

    def _assign_gids_to_lines(self, lines):
        line_map = {}
        for line_key in sorted(lines.keys(), key=lambda k: k[0]):
            line_map[line_key] = self.global_id
            self.global_id += 1
        return line_map

    def _extract_tables(self, page, global_tid):
        """Extract tables with their structure including cell boundaries."""
        tables = []
        table_objects = []

        for table in page.find_tables():
            tables.append(
                {
                    "tid": global_tid,
                    "bbox": list(table.bbox),
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                    "table_obj": table,
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

            if (
                bbox.l >= table_bbox[0]
                and bbox.r <= table_bbox[2]
                and bbox.t >= table_bbox[1]
                and bbox.b <= table_bbox[3]
            ):

                table_obj = table_info.get("table_obj")
                if not table_obj:
                    row_idx, col_idx = self._estimate_cell_position(bbox, table_info)
                    return table_info["tid"], row_idx, col_idx

                cell_center_x = (bbox.l + bbox.r) / 2
                cell_center_y = (bbox.t + bbox.b) / 2

                try:
                    # Method 1: Try to find exact match using cell center point
                    for row_idx in range(table_info["row_count"]):
                        for col_idx in range(table_info["col_count"]):
                            try:
                                cell = table_obj.cell(row_idx, col_idx)
                                if cell:
                                    cell_bbox = cell.bbox
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
                                    cell_cx = (cell_bbox[0] + cell_bbox[2]) / 2
                                    cell_cy = (cell_bbox[1] + cell_bbox[3]) / 2
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

                logger.warning(
                    f"Could not determine row/col for field in table {table_info['tid']}"
                )
                return table_info["tid"], None, None

        return None, None, None

    def _estimate_cell_position(self, bbox, table_info):
        """
        Estimate cell position based on bbox location within table.
        This is a fallback when exact cell lookup fails.
        """
        try:
            table_bbox = table_info["bbox"]
            row_count = table_info["row_count"]
            col_count = table_info["col_count"]

            table_width = table_bbox[2] - table_bbox[0]
            table_height = table_bbox[3] - table_bbox[1]
            cell_height = table_height / row_count
            cell_width = table_width / col_count

            field_center_x = (bbox.l + bbox.r) / 2
            field_center_y = (bbox.t + bbox.b) / 2

            row_offset = field_center_y - table_bbox[1]
            estimated_row = int(row_offset / cell_height)
            estimated_row = max(0, min(estimated_row, row_count - 1))

            col_offset = field_center_x - table_bbox[0]
            estimated_col = int(col_offset / cell_width)
            estimated_col = max(0, min(estimated_col, col_count - 1))

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

        gid = line_map[line_key]
        self.fid_to_gid_map[fid] = gid

        form_field = {
            "type_inferred": field_tag,
            "field_type": field_type_str,
            "field_type_new": field_type_str,
            "field_flag": widget.field_flags,
            "bbox": bbox.to_dict(),
            "fid": fid,
            "page": page_num,
            "field_name": widget.field_name or None,
            "field_value": widget.field_value,
            "gid": gid,
        }

        if assigned_table_tid is not None:
            form_field["tid"] = assigned_table_tid
            if row_idx is not None:
                form_field["row"] = row_idx
            if col_idx is not None:
                form_field["col"] = col_idx

        self.global_fid += 1
        return fid, gid, form_field, assigned_table_tid

    def _detect_header_footer_regions(self, page, lines):
        """
        Detect header and footer regions based on page dimensions and text positions.

        Args:
            page: PyMuPDF page object
            lines: Dictionary of line_key -> words

        Returns:
            tuple: (header_threshold, footer_threshold) - Y coordinates defining header/footer regions
        """
        page_height = page.rect.height

        # Typical header/footer margins (adjustable)
        HEADER_MARGIN_RATIO = 0.08  # Top 8% of page
        FOOTER_MARGIN_RATIO = 0.92  # Bottom 8% of page (92% from top)

        header_threshold = page_height * HEADER_MARGIN_RATIO
        footer_threshold = page_height * FOOTER_MARGIN_RATIO

        # Get all line Y positions
        line_y_positions = sorted([line_key[0] for line_key in lines.keys()])

        if not line_y_positions:
            return header_threshold, footer_threshold

        # If there are very few lines at the extremes, adjust thresholds
        lines_in_header = [y for y in line_y_positions if y < header_threshold]
        lines_in_footer = [y for y in line_y_positions if y > footer_threshold]

        # If no lines in default header region, try a smaller margin
        if not lines_in_header:
            header_threshold = page_height * 0.05

        # If no lines in default footer region, try a smaller margin
        if not lines_in_footer:
            footer_threshold = page_height * 0.95

        return header_threshold, footer_threshold

    def _process_lines_with_headings(
        self,
        lines,
        line_map,
        line_font_info,
        font_stats,
        page_num,
        global_tid,
        page_outline=None,
        page=None,
    ):
        """
        Process lines with heading detection based on font information.

        Args:
            lines: Dictionary of line_key -> words
            line_map: Dictionary of line_key -> gid
            line_font_info: Dictionary of line_key -> font information
            font_stats: Page-level font statistics
            page_num: Current page number
            global_tid: Global table ID
            page_outline: List of outline entries for this page (optional)
            page: PyMuPDF page object (for header/footer detection)

        Returns:
            list: Processed text elements with heading classification
        """
        processed = []
        outline_matched = 0

        # Detect header and footer regions
        header_threshold = 0
        footer_threshold = float("inf")
        underlined_regions = []
        if page:
            header_threshold, footer_threshold = self._detect_header_footer_regions(
                page, lines
            )
            underlined_regions = self._detect_underlines(page)

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

            # Determine heading type based on font info
            heading_type = "normal"
            avg_font_size = 12
            is_bold = False
            is_italic = False
            is_underlined = False
            outline_source = False
            is_header = False
            is_footer = False
            confidence = None
            phase3_hints = []

            # Check if text is underlined
            is_underlined = self._is_text_underlined(bbox, underlined_regions)

            # Check if line is in header or footer region
            line_y = line_key[0]  # Top Y coordinate of the line
            if line_y < header_threshold:
                is_header = True
                heading_type = "normal"  # Headers are always normal text
            elif line_y > footer_threshold:
                is_footer = True
                heading_type = "normal"  # Footers are always normal text
            else:
                # Only classify headings for body text (not in header/footer)

                # Phase 1: Try to match with PDF outline first
                if page_outline:
                    matched_type = self._match_text_to_outline(full_text, page_outline)
                    if matched_type:
                        heading_type = matched_type
                        outline_matched += 1
                        outline_source = True

                # If no outline match, use font-based detection (Phase 2)
                if not outline_source and line_key in line_font_info:
                    font_info = line_font_info[line_key]
                    if font_info["font_sizes"]:
                        # Use the maximum font size in the line (typically the dominant one)
                        avg_font_size = max(font_info["font_sizes"])
                        # Check if any word in the line is bold or italic
                        is_bold = (
                            any(flags & (1 << 4) for flags in font_info["flags"])
                            if font_info["flags"]
                            else False
                        )
                        is_italic = (
                            any(flags & (1 << 1) for flags in font_info["flags"])
                            if font_info["flags"]
                            else False
                        )
                        # Get text length
                        text_length = len(full_text.strip())

                        # Classify the text type (Phase 2: Font-based)
                        # Create flags value for classification
                        combined_flags = 0
                        if is_bold:
                            combined_flags |= 1 << 4
                        if is_italic:
                            combined_flags |= 1 << 1

                        base_classification = self._classify_text_type(
                            avg_font_size, combined_flags, text_length, font_stats
                        )

                        # Phase 3: Apply contextual refinement
                        if page:
                            page_width = page.rect.width
                            page_height = page.rect.height
                            heading_type, confidence, phase3_hints = (
                                self._classify_with_phase3_context(
                                    base_classification,
                                    full_text,
                                    bbox,  # Pass BoundingBox object directly
                                    page_width,
                                    page_height,
                                    avg_font_size,
                                    is_bold,
                                    font_stats,
                                    line_key,
                                    lines.keys(),
                                    is_underlined,  # Pass underline detection
                                )
                            )
                        else:
                            heading_type = base_classification
                            confidence = 0.5
                            phase3_hints = []
                            phase3_hints = []

            # Get font size and style info even for headers/footers
            if line_key in line_font_info and line_font_info[line_key]["font_sizes"]:
                avg_font_size = max(line_font_info[line_key]["font_sizes"])
                is_bold = (
                    any(flags & (1 << 4) for flags in line_font_info[line_key]["flags"])
                    if line_font_info[line_key]["flags"]
                    else False
                )
                is_italic = (
                    any(flags & (1 << 1) for flags in line_font_info[line_key]["flags"])
                    if line_font_info[line_key]["flags"]
                    else False
                )

            element = {
                "text": full_text,
                "bbox": bbox.to_dict(),  # Convert to dict for JSON output
                "gid": line_map[line_key],
                "pid": page_pid,
                # tid removed - only needed for TABLE_CELL_FIELD form fields
                "page": page_num,
                "heading_type": heading_type,
                "font_size": round(avg_font_size, 1),  # Round to 1 decimal place
                "is_bold": is_bold,
                "is_italic": is_italic,
                "outline_source": outline_source,  # Track if heading came from outline
            }

            # Add Phase 3 metadata if available
            if not is_header and not is_footer and not outline_source:
                if confidence is not None:
                    element["confidence"] = round(confidence, 2)
                if phase3_hints:
                    element["phase3_hints"] = phase3_hints

            # Add header/footer markers
            if is_header:
                element["is_header"] = True
            if is_footer:
                element["is_footer"] = True

            processed.append(element)

        # Chain bullet points together
        processed = self._chain_bullet_points(processed)

        return processed

    def _chain_bullet_points(self, text_elements):
        """
        Chain consecutive bullet points together into groups.
        Detects patterns like:
        - 1. item, 2. item, 3. item (numbered)
        - a. item, b. item, c. item (lettered)
        - • item, • item (bullet symbols)
        - - item, - item (dashes)

        Args:
            text_elements: List of text elements

        Returns:
            list: Text elements with bullet_group_id added to chained bullets
        """
        if not text_elements:
            return text_elements

        bullet_group_id = 1
        in_bullet_group = False
        current_pattern = None
        last_bullet_value = None

        for _i, element in enumerate(text_elements):
            text = element.get("text", "").strip()

            # Skip headers/footers and headings
            if element.get("is_header") or element.get("is_footer"):
                in_bullet_group = False
                current_pattern = None
                continue

            if element.get("heading_type") in ["h1", "h2", "h3"]:
                in_bullet_group = False
                current_pattern = None
                continue

            # Detect bullet pattern
            bullet_info = self._detect_bullet_pattern(text)

            if bullet_info["is_bullet"]:
                pattern = bullet_info["pattern"]
                value = bullet_info["value"]

                # Check if this continues the current bullet group
                if in_bullet_group and pattern == current_pattern:
                    # Verify sequence continuity
                    if self._is_next_in_sequence(last_bullet_value, value, pattern):
                        element["bullet_group_id"] = bullet_group_id
                        element["bullet_type"] = pattern
                        element["bullet_index"] = value
                        last_bullet_value = value
                    else:
                        # Sequence broken, start new group
                        bullet_group_id += 1
                        element["bullet_group_id"] = bullet_group_id
                        element["bullet_type"] = pattern
                        element["bullet_index"] = value
                        last_bullet_value = value
                else:
                    # Start new bullet group
                    bullet_group_id += 1
                    in_bullet_group = True
                    current_pattern = pattern
                    element["bullet_group_id"] = bullet_group_id
                    element["bullet_type"] = pattern
                    element["bullet_index"] = value
                    last_bullet_value = value
            else:
                # Not a bullet, reset
                in_bullet_group = False
                current_pattern = None
                last_bullet_value = None

        return text_elements

    def _detect_bullet_pattern(self, text):
        """
        Detect if text starts with a bullet pattern.

        Returns:
            dict: {
                'is_bullet': bool,
                'pattern': str (numeric, lower_alpha, upper_alpha, roman, symbol, dash),
                'value': int/str/None
            }
        """
        text = text.strip()

        # Pattern 1: Numeric bullets "1. ", "2) ", "1 ", etc.
        match = re.match(r"^(\d+)[.)]\s+", text)
        if match:
            return {
                "is_bullet": True,
                "pattern": "numeric",
                "value": int(match.group(1)),
            }

        # Pattern 2: Lowercase letter bullets "a. ", "b) ", etc.
        match = re.match(r"^([a-z])[.)]\s+", text)
        if match:
            return {
                "is_bullet": True,
                "pattern": "lower_alpha",
                "value": ord(match.group(1)) - ord("a"),  # Convert to 0-based index
            }

        # Pattern 3: Uppercase letter bullets "A. ", "B) ", etc.
        match = re.match(r"^([A-Z])[.)]\s+", text)
        if match:
            return {
                "is_bullet": True,
                "pattern": "upper_alpha",
                "value": ord(match.group(1)) - ord("A"),  # Convert to 0-based index
            }

        # Pattern 4: Roman numerals "i. ", "ii. ", "I. ", "II. "
        match = re.match(r"^([ivxIVX]+)[.)]\s+", text)
        if match:
            roman = match.group(1)
            # Simple roman to int conversion for common cases
            try:
                roman_value = self._roman_to_int(roman)
                return {"is_bullet": True, "pattern": "roman", "value": roman_value}
            except Exception:
                pass

        # Pattern 5: Symbol bullets "• ", "○ ", "■ ", "- ", "* "
        if re.match(r"^[•○■▪▫►▸\-⇒✓✔⇨◆◇*]\s+", text):
            return {
                "is_bullet": True,
                "pattern": "symbol",
                "value": None,  # No sequence value for symbols
            }

        return {"is_bullet": False, "pattern": None, "value": None}

    def _roman_to_int(self, s):
        """Convert Roman numeral to integer (basic implementation)."""
        roman_values = {
            "I": 1,
            "V": 5,
            "X": 10,
            "L": 50,
            "C": 100,
            "D": 500,
            "M": 1000,
            "i": 1,
            "v": 5,
            "x": 10,
            "l": 50,
            "c": 100,
            "d": 500,
            "m": 1000,
        }
        total = 0
        prev_value = 0

        for char in reversed(s):
            value = roman_values.get(char, 0)
            if value < prev_value:
                total -= value
            else:
                total += value
            prev_value = value

        return total

    def _is_next_in_sequence(self, prev_value, curr_value, pattern):
        """Check if curr_value is next in sequence after prev_value."""
        if prev_value is None or curr_value is None:
            return pattern == "symbol"  # Symbols always continue if same pattern

        if pattern in ["numeric", "lower_alpha", "upper_alpha", "roman"]:
            # Check if current is exactly prev + 1
            return curr_value == prev_value + 1

        return True  # For symbols, always continue

    def _enforce_heading_hierarchy(self, text_elements, font_stats):
        """
        Phase 2: Enforce logical heading hierarchy rules.

        Rules:
        1. Only ONE H1 per page (the first/largest heading)
        2. H2 can only appear after H1 is found
        3. H3 can only appear after H2 is found
        4. No skipping levels (H1 -> H3 without H2)
        5. Subsequent large headings are demoted to H2

        Args:
            text_elements: List of text elements with initial heading classification
            font_stats: Font statistics for the page

        Returns:
            list: Text elements with enforced hierarchy
        """
        if not text_elements:
            return text_elements

        processed = []
        h1_found = False
        h2_found = False

        # First pass: identify the true H1 (largest or first significant heading)
        [el for el in text_elements if el["heading_type"] in ["h1", "h2"]]

        for element in text_elements:
            # Skip header/footer elements - they don't participate in hierarchy
            if element.get("is_header") or element.get("is_footer"):
                processed.append(element)
                continue

            original_type = element["heading_type"]
            text = element["text"].strip()
            text_length = len(text)

            # Skip empty or very short text (likely not a heading)
            if not text or text_length < 3:
                processed.append(element)
                continue

            new_type = original_type

            # Rule 1: Only ONE H1 per page
            if original_type == "h1":
                if not h1_found:
                    # This is our H1
                    new_type = "h1"
                    h1_found = True
                    h2_found = False  # Reset H2 tracking after H1
                else:
                    # Already have H1, demote to H2
                    new_type = "h2"
                    h2_found = True
                    logger.debug(f"Demoted H1->H2: '{text[:50]}'")

            # Rule 2: H2 requires H1 first
            elif original_type == "h2":
                if not h1_found:
                    # No H1 yet, promote this to H1
                    new_type = "h1"
                    h1_found = True
                    logger.debug(f"Promoted H2->H1: '{text[:50]}'")
                else:
                    # Have H1, this is valid H2
                    new_type = "h2"
                    h2_found = True

            # Rule 3: H3 requires both H1 and H2
            elif original_type == "h3":
                if not h1_found:
                    # No H1 yet, promote to H1
                    new_type = "h1"
                    h1_found = True
                    logger.debug(f"Promoted H3->H1: '{text[:50]}'")
                elif not h2_found:
                    # Have H1 but no H2, promote to H2
                    new_type = "h2"
                    h2_found = True
                    logger.debug(f"Promoted H3->H2: '{text[:50]}'")
                else:
                    # Have both H1 and H2, valid H3
                    new_type = "h3"

            # Update the element
            element["heading_type"] = new_type
            element["hierarchy_adjusted"] = new_type != original_type
            processed.append(element)

        return processed

    def _compute_page_metadata(self, page_fids, page_gids):
        return {
            "start_fid": min(page_fids) if page_fids else -1,
            "end_fid": max(page_fids) if page_fids else -1,
            "total_fids": len(page_fids),
            "start_gid": min(page_gids) if page_gids else -1,
            "end_gid": max(page_gids) if page_gids else -1,
        }

    def _read_pdf(self, pdf_path: str):
        """
        Read PDF from local file system.

        Args:
            pdf_path: Local file path to PDF

        Returns:
            bytes: PDF file content

        Raises:
            FileNotFoundError: If PDF not found
            ValueError: If PDF is empty or invalid
        """
        logger.info(f"Reading PDF from local file: {pdf_path}")

        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        except FileNotFoundError as e:
            logger.error(f"PDF file not found: {pdf_path}")
            raise FileNotFoundError(f"PDF not found: {pdf_path}") from e
        except Exception as e:
            logger.error(f"Failed to read PDF file: {pdf_path}")
            raise RuntimeError(f"Failed to read PDF: {str(e)}") from e

        if not pdf_bytes:
            raise ValueError(f"PDF file is empty: {pdf_path}")

        return pdf_bytes

    def extract(self, pdf_path: str, storage_config: dict) -> dict:
        """
        Extract form fields and text from PDF with heading detection.

        Args:
            pdf_path: Local file path to PDF
            storage_config: Configuration for saving output

        Returns:
            dict: Extracted data with pages, fields, tables, and heading information

        Raises:
            ValueError: If pdf_path is invalid
            FileNotFoundError: If PDF not found
            RuntimeError: If extraction fails
        """
        if not pdf_path:
            raise ValueError("pdf_path cannot be empty")

        if not storage_config:
            raise ValueError("storage_config cannot be empty")

        doc = None

        try:
            # Read PDF from local file system
            pdf_bytes = self._read_pdf(pdf_path)

            try:
                doc = fitz.open("pdf", pdf_bytes)
            except Exception as e:
                logger.error(f"Failed to open PDF with PyMuPDF: {str(e)}")
                raise RuntimeError(f"Invalid or corrupted PDF file: {pdf_path}") from e

            if doc.page_count == 0:
                raise ValueError(f"PDF has no pages: {pdf_path}")

            logger.info(
                f"Starting extraction from PDF: {pdf_path} ({doc.page_count} pages)"
            )

            # Phase 1: Try to extract PDF outline/bookmarks first
            pdf_outline = self._extract_pdf_outline(doc)
            has_outline = len(pdf_outline) > 0

            # Phase 4: Initialize document-level analyzer
            doc_analyzer = DocumentAnalyzer()

            # Get page dimensions from first page
            first_page = doc[0]
            page_rect = first_page.rect
            page_width = page_rect.width
            page_height = page_rect.height

            extracted_data = {
                "pages": [],
                "page_width": round(page_width, 2),
                "page_height": round(page_height, 2),
            }
            global_tid = 1
            all_text_elements = []  # Collect all elements for Phase 4 refinement

        except (ValueError, FileNotFoundError, RuntimeError):
            raise
        except Exception as e:
            logger.error(
                f"Failed to initialize PDF extraction: {str(e)}", exc_info=True
            )
            raise RuntimeError(f"PDF extraction initialization failed: {str(e)}") from e

        try:
            for page_num, page in enumerate(doc, start=1):
                # Get outline entries for this page (if available)
                page_outline = pdf_outline.get(page_num, [])

                # Extract words with font information
                # Using line_tolerance=1 to group slightly offset lines (±1 pixel)
                lines, line_font_info, font_stats = (
                    self._extract_words_by_line_with_fonts(page, line_tolerance=1)
                )
                line_map = self._assign_gids_to_lines(lines)

                # Extract widgets (form fields)
                widgets = {w.rect: w for w in page.widgets()}

                # Extract tables
                table_data, global_tid = self._extract_tables(page, global_tid)
                form_fields, page_fids, page_gids, table_cell_info = [], [], [], {}

                # Process form fields
                for rect, widget in widgets.items():
                    fid, gid, form_field, table_id = self._assign_fid_and_gid_to_field(
                        rect, widget, lines, line_map, table_data, page_num
                    )
                    form_fields.append(form_field)
                    page_fids.append(fid)
                    page_gids.append(gid)
                    if table_id is not None:
                        cell_info = {"tid": table_id}
                        if "row" in form_field:
                            cell_info["row"] = form_field["row"]
                        if "col" in form_field:
                            cell_info["col"] = form_field["col"]
                        table_cell_info[fid] = cell_info

                # Process text elements with heading detection
                text_elements = self._process_lines_with_headings(
                    lines,
                    line_map,
                    line_font_info,
                    font_stats,
                    page_num,
                    global_tid,
                    page_outline,
                    page,
                )

                # Phase 2: Enforce heading hierarchy rules (skip header/footer text)
                text_elements = self._enforce_heading_hierarchy(
                    text_elements, font_stats
                )

                # Phase 4: Learn patterns from this page
                doc_analyzer.learn_from_page(page_num - 1, text_elements, font_stats)

                # Add page number to each element for Phase 4
                for element in text_elements:
                    element["page"] = page_num - 1  # 0-based for analyzer
                    all_text_elements.append(element)

                page_metadata = self._compute_page_metadata(page_fids, page_gids)

                form_fields.sort(
                    key=lambda el: (el["bbox"]["bottom"], el["bbox"]["right"])
                )

                # Clean table_data by removing non-serializable table_obj
                clean_table_data = [
                    {k: v for k, v in table.items() if k != "table_obj"}
                    for table in table_data
                ]

                # Add font statistics to page metadata
                page_metadata["font_stats"] = font_stats

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

            # Phase 4: Apply document-level refinements
            doc_stats = doc_analyzer.get_document_statistics()
            refined_elements = doc_analyzer.refine_classifications(all_text_elements)

            # Update pages with refined elements
            element_index = 0
            for page_data in extracted_data["pages"]:
                page_element_count = len(page_data["text_elements"])
                page_data["text_elements"] = refined_elements[
                    element_index : element_index + page_element_count
                ]
                element_index += page_element_count

            # Add Phase 4 statistics to extracted data
            extracted_data["phase4_statistics"] = doc_stats

            logger.info(
                f"Extraction completed successfully: {len(extracted_data['pages'])} pages processed"
            )

            # Clean up internal metadata fields before saving
            self._cleanup_output_metadata(extracted_data)

            # Save extracted data
            try:
                save_json(extracted_data, storage_config)
                local_path = storage_config.get("path")
                logger.info(f"Extracted data saved to: {local_path}")
                # Add local_path to result for operations to reference
                extracted_data["local_path"] = local_path
            except Exception as e:
                logger.error(f"Failed to save extracted data: {str(e)}", exc_info=True)
                raise RuntimeError(
                    f"Failed to save extraction results: {str(e)}"
                ) from e

            # Generate PDF fingerprint hash from extracted JSON
            pdf_hash = None
            try:
                # Import the custom pdf_hash function from utils
                from pdf_autofillr_mapper.utils.pdf_hash import create_pdf_fingerprint

                # Calculate hash directly from extracted_data dict (no file I/O needed)
                fingerprint, pdf_hash = create_pdf_fingerprint(extracted_data)

                logger.info(f"Generated PDF fingerprint hash: {pdf_hash[:16]}...")
                extracted_data["pdf_hash"] = pdf_hash

            except Exception as hash_error:
                logger.warning(f"Failed to generate PDF fingerprint hash: {hash_error}")
                # Don't fail extraction if hash generation fails
                extracted_data["pdf_hash"] = None

            return extracted_data

        except Exception as e:
            logger.error(
                f"Extraction failed on page {page_num if 'page_num' in locals() else 'unknown'}: {str(e)}",
                exc_info=True,
            )
            raise RuntimeError(f"PDF extraction failed: {str(e)}") from e
        finally:
            if doc:
                try:
                    doc.close()
                    logger.debug("PDF document closed")
                except Exception as e:
                    logger.warning(f"Error closing PDF document: {e}")

    def _cleanup_output_metadata(self, extracted_data):
        """
        Remove internal metadata fields used for calculations but not needed in output.

        Fields removed:
        - is_bold, is_italic: Internal style flags
        - outline_source: Whether heading came from PDF outline
        - confidence: Phase 3 confidence score
        - phase3_hints: Phase 3 classification hints
        - hierarchy_adjusted: Phase 2 hierarchy flag
        - phase4_corrections: Phase 4 correction list
        - phase4_suggestion: Phase 4 alternative classification

        Args:
            extracted_data: The full extraction data dictionary
        """
        fields_to_remove = [
            "is_bold",
            "is_italic",
            "outline_source",
            "confidence",
            "phase3_hints",
            "hierarchy_adjusted",
            "phase4_corrections",
            "phase4_suggestion",
        ]

        for page_data in extracted_data.get("pages", []):
            for element in page_data.get("text_elements", []):
                for field in fields_to_remove:
                    element.pop(field, None)


def main():
    """
    Main function for local testing of DetailedFitzExtractor
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Configuration for the extractor
    config = {"WIDGET_LINE_DISTANCE_THRESHOLD": 10, "rounding": 1}

    # Path to your test PDF (local file path only)
    pdf_path = "/Users/raghava/Documents/EMC/pdf_autofiller/data/small_4page.pdf"

    # Create output directory if it doesn't exist (data in root)
    output_dir = "./data"
    os.makedirs(output_dir, exist_ok=True)

    # Storage configuration for local files only
    storage_config = {
        "type": "local",
        "path": os.path.join(output_dir, "small_4page_extracted_data_detailed.json"),
    }

    try:
        logger.info("=" * 80)
        logger.info("Starting DetailedFitzExtractor Test")
        logger.info("=" * 80)

        # First, run debug to show actual font flags in the PDF
        logger.info("\nStep 1: Analyzing font flags in PDF...")
        debug_font_flags(pdf_path, max_samples=50)

        # Create extractor instance
        extractor = DetailedFitzExtractor(config)

        # Extract data from PDF
        logger.info("\nStep 2: Extracting text with heading detection...")
        logger.info(f"Extracting from: {pdf_path}")
        extracted_data = extractor.extract(
            pdf_path=pdf_path, storage_config=storage_config
        )

        # Print summary statistics
        logger.info("=" * 80)
        logger.info("Extraction Summary")
        logger.info("=" * 80)
        logger.info(f"Total pages: {len(extracted_data['pages'])}")

        # Basic statistics
        total_text = 0
        total_h1 = 0
        total_h2 = 0
        total_h3 = 0
        total_fields = 0
        total_tables = 0

        for page in extracted_data["pages"]:
            total_text += len(page["text_elements"])
            total_h1 += sum(
                1 for el in page["text_elements"] if el.get("heading_type") == "h1"
            )
            total_h2 += sum(
                1 for el in page["text_elements"] if el.get("heading_type") == "h2"
            )
            total_h3 += sum(
                1 for el in page["text_elements"] if el.get("heading_type") == "h3"
            )
            total_fields += len(page["form_fields"])
            total_tables += len(page["tables"])

        logger.info(f"Text elements: {total_text}")
        logger.info(f"  - H1: {total_h1}, H2: {total_h2}, H3: {total_h3}")
        logger.info(f"Form fields: {total_fields}")
        logger.info(f"Tables: {total_tables}")
        logger.info(f"\nOutput saved to: {storage_config['path']}")
        logger.info("=" * 80)

    except FileNotFoundError as e:
        logger.error(f"PDF file not found: {e}")
        logger.error("Please update the 'pdf_path' variable in the main() function")
    except Exception as e:
        logger.error(f"Error during extraction: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
