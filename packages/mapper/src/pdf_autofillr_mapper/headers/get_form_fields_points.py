"""

Module for extracting hierarchical headers and form field data points from extracted PDF data.

This module processes extracted JSON to identify document structure (h1, h2, h3, h4 hierarchies)

and associate form fields with their semantic labels.

"""

import asyncio
import json
import re
import time
from typing import Any, Optional

# S3Client imported conditionally where needed (only for AWS mode)
from pdf_autofillr_mapper.clients.unified_llm_client import UnifiedLLMClient
from pdf_autofillr_mapper.core.config import settings
from pdf_autofillr_mapper.core.logger import setup_logging

# Setup logging
setup_logging()
import logging  # noqa: E402

logger = logging.getLogger(__name__)


async def get_form_fields_points(
    extracted_json_path: str,
    headers_output_path: str,
    final_fields_output_path: str,
    chunk_size: Optional[int] = None,
    max_workers: Optional[int] = None,
) -> dict[str, Any]:
    """
    Extract hierarchical headers and build final form fields with data points.

    This function orchestrates the two-step process:
    1. Extract headers with field mappings (headers_with_fields.json)
    2. Build final form fields with complete hierarchy (final_form_fields.json)

    Args:
        extracted_json_path: S3 or local path to extracted JSON
        headers_output_path: S3 or local path for headers_with_fields.json output
        final_fields_output_path: S3 or local path for final_form_fields.json output
        chunk_size: Number of pages per chunk (default from config)
        max_workers: Max parallel workers (default from config)

    Returns:
        Dictionary with operation results and statistics

    Example:
        result = await get_form_fields_points(
            extracted_json_path="s3://bucket/doc_extracted.json",
            headers_output_path="s3://bucket/doc_headers_with_fields.json",
            final_fields_output_path="s3://bucket/doc_final_form_fields.json"
        )
    """
    start_time = time.time()

    # Use config defaults if not provided
    if chunk_size is None:
        chunk_size = settings.headers_chunk_size
    if max_workers is None:
        max_workers = settings.headers_max_workers

    logger.info("Starting headers and form fields extraction")
    logger.info(f"Extracted JSON: {extracted_json_path}")
    logger.info(f"Chunk size: {chunk_size}, Max workers: {max_workers}")

    try:
        # Step 1: Extract headers with fields
        logger.info("Step 1/2: Extracting hierarchical headers with field mappings")
        headers_result = await extract_headers_with_fields(
            extracted_json_path=extracted_json_path,
            output_path=headers_output_path,
            chunk_size=chunk_size,
            max_workers=max_workers,
        )

        logger.info(
            f"Headers extraction completed: {len(headers_result['sections'])} sections found"
        )

        # Step 2: Build final form fields
        logger.info("Step 2/2: Building final form fields with complete hierarchy")
        final_fields_result = await build_final_form_fields(
            extracted_json_path=extracted_json_path,
            headers_with_fields_path=headers_output_path,
            output_path=final_fields_output_path,
        )

        logger.info(
            f"Final form fields built: {len(final_fields_result['fields'])} fields processed"
        )

        end_time = time.time()
        duration = round(end_time - start_time, 2)

        result = {
            "operation": "get_form_fields_points",
            "status": "success",
            "execution_time_seconds": duration,
            "outputs": {
                "headers_with_fields": headers_output_path,
                "final_form_fields": final_fields_output_path,
            },
            "pdf_category": headers_result.get(
                "pdf_category"
            ),  # Add document classification
            "statistics": {
                "total_pages": headers_result.get("total_pages", 0),
                "total_sections": len(headers_result["sections"]),
                "sections_by_level": {
                    "title": headers_result.get("sections_by_level", {}).get(
                        "title", 0
                    ),
                    "h1": headers_result.get("sections_by_level", {}).get("h1", 0),
                    "h2": headers_result.get("sections_by_level", {}).get("h2", 0),
                    "h3": headers_result.get("sections_by_level", {}).get("h3", 0),
                    "h4": headers_result.get("sections_by_level", {}).get("h4", 0),
                },
                "fields_with_hierarchy": len(final_fields_result["fields"]),
                "processing_time": {
                    "headers_extraction": headers_result.get(
                        "execution_time_seconds", 0
                    ),
                    "final_fields_building": final_fields_result.get(
                        "execution_time_seconds", 0
                    ),
                    "total": duration,
                },
            },
            "llm_usage": headers_result.get("llm_usage", {}),
        }

        logger.info(
            f"Form fields data points extraction completed in {duration} seconds"
        )
        return result

    except Exception as e:
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        logger.error(
            f"Form fields data points extraction failed after {duration} seconds: {str(e)}"
        )
        raise RuntimeError(f"Headers extraction failed: {str(e)}") from e


async def extract_headers_with_fields(
    extracted_json_path: str, output_path: str, chunk_size: int, max_workers: int
) -> dict[str, Any]:
    """
    Extract hierarchical headers with field ID mappings from extracted JSON.

    This is the first step that processes the extracted PDF data to identify:
    - Document title
    - Page-level headings (h1)
    - Section headings (h2)
    - Field labels (h3)
    - Options/sub-labels (h4)

    Each heading is associated with form field IDs (fid) where applicable.

    Args:
        extracted_json_path: Path to extracted JSON file
        output_path: Path for headers output
        chunk_size: Number of pages to process per chunk
        max_workers: Maximum parallel workers

    Returns:
        Dictionary with extraction results and statistics
    """
    start_time = time.time()

    logger.info("Loading extracted data...")
    extracted_data = await load_json_from_storage(extracted_json_path)

    pages = extracted_data.get("pages", [])
    total_pages = len(pages)

    logger.info(f"Preparing {total_pages} pages with field placeholders...")
    prepared_pages = prepare_pages_with_placeholders(pages)

    logger.info(f"Processing {total_pages} pages in chunks of {chunk_size}...")

    # Create chunks
    chunks = []
    for i in range(0, total_pages, chunk_size):
        chunk_pages = prepared_pages[i : i + chunk_size]
        chunk_num = i // chunk_size + 1
        is_first = i == 0
        chunks.append((chunk_pages, chunk_num, is_first))

    total_chunks = len(chunks)
    logger.info(
        f"Created {total_chunks} chunks, processing in parallel with max {max_workers} concurrent workers..."
    )

    # Process all chunks in parallel
    # Each process_chunk uses run_in_executor internally for the blocking LLM call
    chunk_tasks = [
        process_chunk(chunk_pages, chunk_num, is_first)
        for chunk_pages, chunk_num, is_first in chunks
    ]

    chunk_results = await asyncio.gather(*chunk_tasks)

    # Log results
    for result in chunk_results:
        chunk_num = int(result.get("chunk_num") or 0)
        pages = result.get("pages", "N/A")
        sections_count = len(result.get("sections", []))
        elapsed = result.get("time", 0)
        logger.info(
            f"Chunk {chunk_num}: {sections_count} sections from pages {pages} ({elapsed:.2f}s)"
        )

    # Combine all sections
    all_sections = []
    pdf_category = None  # Extract pdf_category from first chunk

    for result in chunk_results:
        all_sections.extend(result.get("sections", []))
        # Capture pdf_category from first chunk only
        if result.get("pdf_category") and pdf_category is None:
            pdf_category = result.get("pdf_category")

    # Log pdf_category
    if pdf_category:
        logger.info(
            f"Document classification: "
            f"category={pdf_category.get('category')}, "
            f"sub_category={pdf_category.get('sub_category')}, "
            f"document_type={pdf_category.get('document_type')}"
        )
    else:
        logger.warning("No document classification extracted from first chunk")

    # Calculate statistics
    sections_by_level = {
        "title": sum(1 for s in all_sections if s.get("level") == "title"),
        "h1": sum(1 for s in all_sections if s.get("level") == "h1"),
        "h2": sum(1 for s in all_sections if s.get("level") == "h2"),
        "h3": sum(1 for s in all_sections if s.get("level") == "h3"),
        "h4": sum(1 for s in all_sections if s.get("level") == "h4"),
    }

    total_fields_linked = sum(1 for s in all_sections if s.get("fid") is not None)

    # Prepare output data with pdf_category
    output_data = {"sections": all_sections}

    # Add pdf_category if available
    if pdf_category:
        output_data["pdf_category"] = pdf_category

    # Save to storage
    await save_json_to_storage(output_data, output_path)

    end_time = time.time()
    duration = round(end_time - start_time, 2)

    # Calculate cumulative LLM usage stats from all chunks
    total_chunks = len(chunk_results)
    total_prompt_tokens = sum(
        r.get("llm_usage", {}).get("prompt_tokens", 0) for r in chunk_results
    )
    total_completion_tokens = sum(
        r.get("llm_usage", {}).get("completion_tokens", 0) for r in chunk_results
    )
    total_tokens = total_prompt_tokens + total_completion_tokens
    total_cost_usd = sum(
        r.get("llm_usage", {}).get("cost_usd", 0.0) for r in chunk_results
    )

    # Get model name from first chunk if available
    llm_model = (
        chunk_results[0].get("llm_usage", {}).get("model", "unknown")
        if chunk_results
        else "unknown"
    )

    # Calculate average cost per call and per section
    avg_cost_per_call = total_cost_usd / total_chunks if total_chunks > 0 else 0.0
    cost_per_section = (
        total_cost_usd / len(all_sections) if len(all_sections) > 0 else 0.0
    )

    # Log cumulative LLM stats
    logger.info("=" * 80)
    logger.info("HEADERS LLM USAGE SUMMARY")
    logger.info(f"Model: {llm_model}")
    logger.info(f"Total Chunks: {total_chunks}")
    logger.info(f"Total Prompt Tokens: {total_prompt_tokens:,}")
    logger.info(f"Total Completion Tokens: {total_completion_tokens:,}")
    logger.info(f"Total Tokens: {total_tokens:,}")
    logger.info(f"Total Cost: ${total_cost_usd:.6f}")
    logger.info(f"Average Cost per Chunk: ${avg_cost_per_call:.6f}")
    logger.info(f"Cost per Section: ${cost_per_section:.6f}")
    logger.info("=" * 80)

    result = {
        "sections": all_sections,
        "pdf_category": pdf_category,  # Include in result
        "total_pages": total_pages,
        "sections_by_level": sections_by_level,
        "fields_linked": total_fields_linked,
        "execution_time_seconds": duration,
        "llm_usage": {
            "model": llm_model,
            "total_chunks": total_chunks,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost_usd,
            "avg_cost_per_chunk": avg_cost_per_call,
            "cost_per_section": cost_per_section,
        },
    }

    logger.info(
        f"Headers extraction completed: {len(all_sections)} sections, {total_fields_linked} fields linked"
    )
    return result


async def build_final_form_fields(
    extracted_json_path: str, headers_with_fields_path: str, output_path: str
) -> dict[str, Any]:
    """
    Build final form fields with complete hierarchy data.

    This is the second step that combines:
    - Original extracted form fields (with bbox, field_type, etc.)
    - Headers hierarchy (title, h1, h2, h3, h4)

    to create a comprehensive data structure for each form field.

    Args:
        extracted_json_path: Path to extracted JSON
        headers_with_fields_path: Path to headers with fields JSON
        output_path: Path for final output

    Returns:
        Dictionary with build results
    """
    start_time = time.time()

    logger.info("Loading extracted data and headers...")
    extracted_data = await load_json_from_storage(extracted_json_path)
    headers_data = await load_json_from_storage(headers_with_fields_path)

    # Extract sections and pdf_category
    if isinstance(headers_data, dict):
        headers = headers_data.get("sections", [])
        pdf_category = headers_data.get("pdf_category")
    else:
        # Legacy format: just a list of sections
        headers = headers_data
        pdf_category = None

    # Build indexes
    fid_to_header, page_to_structural, fid_to_h2_map = build_header_index(headers)

    final_fields = []

    for page in extracted_data.get("pages", []):
        page_num = page.get("page_number")
        form_fields = page.get("form_fields", [])

        structural = page_to_structural.get(page_num, [])
        page_title, page_h1, page_h2_default, page_section_context_default = (
            find_page_hierarchy(page_num, structural)
        )

        for field in form_fields:
            fid = field.get("fid")
            field_type = field.get("field_type")
            field_name = field.get("field_name")
            bbox = field.get("bbox")
            gid = field.get("gid")

            # Default header values
            h1_text = page_h1
            h2_text = page_h2_default
            section_context = page_section_context_default
            h3_text = None
            h4_text = None

            # Get the correct H2 and section_context for this field from the hierarchy map
            if fid in fid_to_h2_map:
                h2_info = fid_to_h2_map[fid]
                h2_text = h2_info.get("h2") or h2_text
                section_context = h2_info.get("section_context") or section_context
                # For H4 fields, set H3 from parent_h3 if not already set
                if h2_info.get("parent_h3") and not h3_text:
                    h3_text = h2_info.get("parent_h3")

            # Get H3/H4 from field-linked headers
            header = fid_to_header.get(fid)

            if header:
                level = header.get("level")
                text = header.get("text")

                if level == "h3":
                    h3_text = text
                elif level == "h4":
                    h4_text = text
                    # If H4 exists but H3 not set, try to get from hierarchy map
                    if not h3_text and fid in fid_to_h2_map:
                        h3_text = fid_to_h2_map[fid].get("parent_h3")

            final_entry = {
                "fid": fid,
                "page": page_num,
                "field_name": field_name,
                "field_type": field_type,
                "gid": gid,
                "bbox": bbox,
                "hierarchy": {
                    "title": page_title,
                    "h1": h1_text,
                    "h2": h2_text,
                    "section_context": section_context,  # NEW: Add section context
                    "h3": h3_text,
                    "h4": h4_text,
                },
            }

            final_fields.append(final_entry)

    # Prepare output data
    output_data = {"fields": final_fields}

    # Add pdf_category if available
    if pdf_category:
        output_data["pdf_category"] = pdf_category

    # Save to storage
    await save_json_to_storage(output_data, output_path)

    end_time = time.time()
    duration = round(end_time - start_time, 2)

    logger.info(
        f"Final form fields built: {len(final_fields)} fields processed in {duration}s"
    )

    return {
        "fields": final_fields,
        "pdf_category": pdf_category,
        "execution_time_seconds": duration,
    }


# Helper functions


def prepare_pages_with_placeholders(pages: list[dict]) -> list[dict]:
    """
    Convert extracted JSON pages to format with field placeholders embedded in text.
    Merges text_elements with form_fields to create lines with [FIELD_TYPE:ID] tokens.
    """
    prepared_pages = []

    for page in pages:
        page_num = page.get("page_number", 1)
        text_elements = page.get("text_elements", [])
        form_fields = page.get("form_fields", [])

        # Create a map of form fields by position for quick lookup
        field_map = {}
        for field in form_fields:
            fid = field.get("fid")
            field_type = field.get("field_type", "UNKNOWN")
            bbox = field.get("bbox", {})

            # Store field info
            field_map[fid] = {
                "type": field_type,
                "bbox": bbox,
                "top": bbox.get("top", 0),
                "left": bbox.get("left", 0),
            }

        # Build lines with embedded placeholders
        lines = []

        for idx, elem in enumerate(text_elements):
            text = elem.get("text", "").strip()
            bbox = elem.get("bbox", {})
            font_size = elem.get("font_size")
            is_bold = elem.get("font_weight", "").lower() == "bold"

            elem_top = bbox.get("top", 0)
            elem_left = bbox.get("left", 0)
            elem_right = bbox.get("right", elem_left + 100)

            # Find fields that are spatially near this text element
            # (within 50pt vertically, to the right horizontally)
            nearby_fields = []

            for fid, field_info in field_map.items():
                field_top = field_info["top"]
                field_left = field_info["left"]

                # Check if field is on same line (within 15pt vertical) and to the right
                vertical_diff = abs(field_top - elem_top)

                if (
                    vertical_diff < 15
                    and field_left >= elem_left
                    and field_left - elem_right < 200
                ):
                    nearby_fields.append(
                        {
                            "fid": fid,
                            "type": field_info["type"],
                            "left": field_left,
                            "distance": field_left - elem_right,
                        }
                    )

            # Sort by left position
            nearby_fields.sort(key=lambda x: x["left"])

            # Embed field placeholders in text
            if nearby_fields:
                for field in nearby_fields:
                    text += f" [{field['type']}:{field['fid']}]"

            # Create line entry
            line = {
                "lid": f"p{page_num}_l{idx + 1}",
                "text": text,
                "bbox": {"left": elem_left, "top": elem_top},
                "font_size": font_size,
                "is_bold": is_bold,
            }

            lines.append(line)

        # Also add standalone fields that weren't matched to text
        matched_fids = set()
        for line in lines:
            # Extract field IDs from placeholders in text
            placeholders = re.findall(r"\[(\w+):(\d+)\]", line["text"])
            for _, fid_str in placeholders:
                matched_fids.add(int(fid_str))

        # Add unmatched fields as separate lines
        for fid, field_info in field_map.items():
            if fid not in matched_fids:
                line = {
                    "lid": f"p{page_num}_f{fid}",
                    "text": f"[{field_info['type']}:{fid}]",
                    "bbox": {
                        "left": field_info["bbox"].get("left", 0),
                        "top": field_info["bbox"].get("top", 0),
                    },
                    "font_size": 10,
                    "is_bold": False,
                }
                lines.append(line)

        # Sort lines by position (top, then left)
        lines.sort(key=lambda x: (x["bbox"]["top"], x["bbox"]["left"]))

        prepared_pages.append({"page_number": page_num, "lines": lines})

    return prepared_pages


async def process_chunk(
    chunk_pages: list[dict], chunk_num: int, is_first: bool
) -> dict[str, Any]:
    """
    Process a chunk of pages to extract headers with LLM.

    Uses configured LLM provider (OpenAI or Claude) to extract hierarchical headers
    from pages with embedded field placeholders.

    This runs the synchronous LLM call in a thread pool to avoid blocking.
    """
    start_time = time.time()

    page_range = f"{chunk_pages[0]['page_number']}-{chunk_pages[-1]['page_number']}"
    logger.info(f"Processing chunk {chunk_num}: pages {page_range}")

    # Create prompt
    prompt = create_header_and_field_prompt(chunk_pages, is_first)

    # Get LLM client with headers-specific configuration
    provider = settings.headers_llm_provider
    if not provider:
        raise ValueError(
            "headers_llm_provider is not set. "
            "Add 'headers_llm_provider = openai' (or 'claude') to the [headers] "
            "section of your mapper_config.ini."
        )

    # Get model ID based on provider (for backwards compatibility)
    # With LiteLLM, we use model names directly
    if provider == "openai":
        model_id = settings.headers_openai_model_id or "gpt-4o"
    elif provider == "claude":
        model_id = settings.headers_claude_model_id or "claude-3-5-sonnet-20241022"
    else:
        # Default to gpt-4o if provider not recognized
        model_id = "gpt-4o"
        logger.warning(
            f"Unsupported headers LLM provider: {provider}, using default: {model_id}"
        )

    logger.info(f"Using model: {model_id}")

    # Create UnifiedLLMClient
    llm_client = UnifiedLLMClient(
        model=model_id,
        temperature=settings.headers_temperature,
        max_tokens=settings.headers_max_tokens,
        timeout=getattr(settings, "llm_timeout", 120),
        max_retries=getattr(settings, "llm_max_retries", 3),
    )

    logger.info(
        f"LLM client configured - "
        f"model: {model_id}, "
        f"temp: {settings.headers_temperature}, "
        f"max_tokens: {settings.headers_max_tokens}"
    )

    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Prepare messages for LLM
            system_message_content = (
                "Expert PDF form analyzer. Extract hierarchy with field placeholders. "
                "Split multiple fields on same line. Handle tables (H3 columns, H4 cells) and "
                "checkboxes/radios (H3 question, H4 options). For H2 sections, generate section_context "
                "(max 10 words) that includes the key entity/role from H1 (investor, patient, entity, "
                "co-investor, spouse, etc.) combined with the H2 topic. "
                "Return minimal JSON with a single fid per section."
            )

            messages = [
                {"role": "system", "content": system_message_content},
                {"role": "user", "content": prompt},
            ]

            # Run the synchronous LLM call in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()

            def call_llm(msgs=messages):
                return llm_client.complete(msgs)

            llm_response = await loop.run_in_executor(None, call_llm)

            # Extract response and usage
            response_text = llm_response.content
            usage = llm_response.usage

            # Log token usage and cost
            logger.info(
                f"Chunk {chunk_num} LLM call - "
                f"Tokens: {usage.total_tokens} "
                f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens}), "
                f"Cost: ${usage.cost_usd:.6f}"
            )

            # Try to extract JSON from response (handle markdown code blocks)
            json_match = re.search(
                r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL
            )
            if json_match:
                json_text = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(
                    r'(\{.*"sections".*\})', response_text, re.DOTALL
                )
                if json_match:
                    json_text = json_match.group(1)
                else:
                    json_text = response_text

            chunk_sections = json.loads(json_text)
            elapsed_time = time.time() - start_time

            # Get LLM usage stats from the response
            usage_stats = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost_usd": usage.cost_usd,
                "model": usage.model,
            }

            sections = chunk_sections.get("sections", [])
            pdf_category = chunk_sections.get(
                "pdf_category"
            )  # Extract pdf_category from first chunk

            if not sections:
                if attempt < max_retries - 1:
                    logger.warning(f"Chunk {chunk_num}: No sections found, retrying...")
                    time.sleep(1)
                    continue
                else:
                    logger.warning(
                        f"Chunk {chunk_num}: No sections found after retries"
                    )

            # Log pdf_category if present (first chunk)
            if pdf_category:
                logger.info(
                    f"Chunk {chunk_num} classification: "
                    f"category={pdf_category.get('category')}, "
                    f"sub_category={pdf_category.get('sub_category')}, "
                    f"document_type={pdf_category.get('document_type')}"
                )

            logger.info(
                f"Chunk {chunk_num} completed: {len(sections)} sections found in {elapsed_time:.2f}s"
            )

            result = {
                "chunk_num": chunk_num,
                "pages": page_range,
                "sections": sections,
                "input_tokens": usage.prompt_tokens,  # Legacy compatibility
                "output_tokens": usage.completion_tokens,  # Legacy compatibility
                "llm_usage": usage_stats,  # Full LLM usage stats
                "time": elapsed_time,
            }

            # Add pdf_category only if present (first chunk)
            if pdf_category:
                result["pdf_category"] = pdf_category

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Chunk {chunk_num}: JSON parsing failed: {e}")
            logger.error(f"Response text: {response_text[:500]}...")
            if attempt < max_retries - 1:
                logger.info(f"Retrying chunk {chunk_num}...")
                time.sleep(1)
            else:
                return {
                    "chunk_num": chunk_num,
                    "pages": page_range,
                    "sections": [],
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "time": time.time() - start_time,
                    "error": f"JSON parsing failed: {str(e)}",
                }

        except Exception as e:

            _es = str(e)
            if (
                "interpreter shutdown" in _es
                or "cannot schedule" in _es
                or "atexit after shutdown" in _es
            ):
                return {
                    "chunk_num": chunk_num,
                    "pages": page_range,
                    "sections": [],
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "time": time.time() - start_time,
                    "error": None,
                }
            logger.error(f"Chunk {chunk_num}: Processing failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying chunk {chunk_num}...")
                time.sleep(1)
            else:
                return {
                    "chunk_num": chunk_num,
                    "pages": page_range,
                    "sections": [],
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "time": time.time() - start_time,
                    "error": str(e),
                }

    # Should never reach here, but return empty result
    return {
        "chunk_num": chunk_num,
        "pages": page_range,
        "sections": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "time": time.time() - start_time,
    }


def create_header_and_field_prompt(pages_data: list[dict], is_first_chunk: bool) -> str:
    """
    Create prompt for header extraction with field placeholder support.
    Rules stay the same; only output format is slimmed to a single fid.
    """
    title_instruction = (
        "- title: Document name/title. Extract ONLY from first chunk."
        if is_first_chunk
        else "- title: SKIP extracting title in this chunk."
    )

    classification_instruction = ""
    if is_first_chunk:
        classification_instruction = """

══════════════════════════════════════════════
DOCUMENT CLASSIFICATION (FIRST CHUNK ONLY)
══════════════════════════════════════════════

In addition to sections, you must classify the document into a hierarchical taxonomy:

**pdf_category**: A 3-level hierarchical classification:

1. **category**: Broad domain/industry
   Examples: finance, legal, healthcare, government, insurance, real_estate,
   education, human_resources, technology, manufacturing

2. **sub_category**: Specific area within the category
   Examples (for finance): investment, banking, taxation, accounting, trading, wealth_management
   Examples (for legal): contract, compliance, litigation, corporate, intellectual_property
   Examples (for healthcare): patient_intake, medical_records, insurance_claims, consent_forms

3. **document_type**: Specific document classification
   Examples: subscription_form, investment_agreement, tax_return, license_application,
   patient_consent, employment_contract, loan_application, insurance_claim,
   questionnaire, certification, registration, disclosure, terms_and_conditions

Analyze the document title, content, headers, and field types to determine this classification.
Return the "pdf_category" object in the top-level JSON output (NOT inside sections array).

Example:
{
  "pdf_category": {
    "category": "finance",
    "sub_category": "investment",
    "document_type": "subscription_form"
  },
  "sections": [...]
}
"""

    return f"""
You are analyzing structured JSON extracted from a PDF. Each line may contain:
- Plain text
- One or more form field placeholders:
  [TEXT_FIELD:<id>], [CHECKBOX_FIELD:<id>], [RADIOBUTTON_FIELD:<id>], [TABLE_CELL_FIELD:<id>]

The numeric id inside each placeholder is the UNIQUE form field id we must tag.

You must output a clean hierarchy of headings and field labels:

  - title: Document-level title (only once, first chunk only)
  - h1: Page-level main heading (ONE per page)
  - h2: Section headings on the page
  - h3: Field labels (questions / prompts / column headers)
  - h4: Options / table cells belonging to an h3

PAGES_DATA (JSON):
{json.dumps(pages_data, indent=2)}

══════════════════════════════════════════════
PLACEHOLDER SYNTAX (VERY IMPORTANT)
══════════════════════════════════════════════

The text can contain any of these placeholders:

- [TEXT_FIELD:123]
- [RADIOBUTTON_FIELD:90]
- [CHECKBOX_FIELD:7]
- [TABLE_CELL_FIELD:50]

Rules:

1. The number after colon is the form field id.
   Example: [TEXT_FIELD:1] -> form_field_id = 1

2. One line may contain MULTIPLE placeholders.
   Example:
   "City [TEXT_FIELD:10] State [TEXT_FIELD:11] Zip [TEXT_FIELD:12]"
   This means there are THREE distinct fields on the same line.
   You MUST treat each as a separate h3 (separate labels), not one combined heading.

3. [TABLE_CELL_FIELD:id] appears inside table cells.
   You must infer the table structure from context:
   - The column header text (top row) is an h3.
   - Each cell under that column with a [TABLE_CELL_FIELD:id] is an h4 belonging to that h3.

4. [CHECKBOX_FIELD:id] and [RADIOBUTTON_FIELD:id] are choice fields.
   - The question or group label above or on the same line is h3.
   - Each individual choice (often on the same line as the placeholder) is h4.

══════════════════════════════════════════════
HIERARCHY DEFINITIONS
══════════════════════════════════════════════

{title_instruction}

**H1 (Page Title):**
- ONE per page.
- Largest font_size on the page OR bold and near top.
- Represents overall topic of the page.
- Example: "Investor Profile", "Subscription Agreement".

**H2 (Section Heading):**
- Larger or bolder than normal text (font_size ~10–12, is_bold = true).
- Groups a set of fields below it.
- **CRITICAL: H2 SEPARATION RULES**:
  1. **VISUAL SEPARATION**: Look for whitespace gaps, horizontal lines, or clear visual breaks to identify separate H2 sections.
  2. **SEMANTIC GROUPING**: Fields that serve different purposes should be in separate H2 sections:
     - Basic identity fields (Name, SSN, Address) -> One H2 (e.g., "Basic Information")
     - Classification/type selection (checkboxes for investor type, entity type) -> Different H2 (e.g., "Investor Classification")
     - Contact details -> Different H2 (e.g., "Contact Information")
  3. **FIELD TYPE CLUSTERING**: Don't mix simple text fields at the top with choice fields (checkboxes/radios) in the middle under the same H2.
     They likely belong to different sections.
  4. **VERTICAL SPACING**: If there's >100 pixels vertical gap between field groups, they likely belong to different H2 sections.

  **Example from Investor Form**:
  ```
  [Top of page]
  Name of Investor: [TEXT_FIELD:1]
  Social Security Number: [TEXT_FIELD:2]
  Amount of Subscription: [TEXT_FIELD:3]
  -> H2: "Basic Investor Information"

  [After whitespace gap]
  Type of Investor—Please check one:
  ☐ Individual [CHECKBOX:7]
  ☐ Partnership [CHECKBOX:8]
  ☐ Corporation [CHECKBOX:9]
  -> H2: "Investor Classification" (SEPARATE H2)

  Form PF Investor Type:
  (A) Is the Investor acting as agent... [CHECKBOX:20]
  -> H3: "Form PF Investor Type" (under same H2="Investor Classification")
  ```

- **SPATIAL RULE**: H2 must appear BELOW its parent H1 on the same page (bbox.top of H2 > bbox.top of H1).
  If text appears ABOVE H1, it CANNOT be H2 for that H1.
- Examples: "Contact Information", "Tax Status", "Form PF Investor Type".
- **VALIDATION RULE FOR TEXT FIELDS**: If the H2 section contains primarily blank/text fields (TEXT_FIELD),
  the H2 should be DESCRIPTIVE and NOT phrased as a question asking for a choice.
  Examples:
    BAD: H2="Select Your Tax Status" for section with [TEXT_FIELD:5] Name _______
    GOOD: H2="Tax Information" for section with text fields
    BAD: H2="Choose Your Department" for section with [TEXT_FIELD:10] Title _______
    GOOD: H2="Department Information" for section with text fields
  Choice-like H2 is ONLY appropriate when the section contains CHECKBOX_FIELD or RADIOBUTTON_FIELD.
- **CRITICAL: section_context MUST MATCH FIELD TYPES IN THE SECTION**:
  - For TEXT_FIELD sections (Name, SSN, Address, Amount): Use DESCRIPTIVE context about what information is collected
    Examples: "Investor identity and contact details", "Subscription amount and interests", "Basic personal information"
    **WRONG**: "Investor type and entity classification" (this is for checkboxes!)
    **WRONG**: "Investor classification selection" (this is for choice fields!)
  - For CHECKBOX/RADIO sections: Use context describing the CHOICE/SELECTION being made
    Examples: "Investor entity type selection", "Investor classification choice", "Marital status selection"
    **WRONG**: "Investor name and contact details" (this is for text fields!)
  - **KEY RULE**: section_context should describe WHAT TYPE OF INTERACTION the fields require:
    - TEXT fields -> "information", "details", "data", "identification"
    - CHECKBOX/RADIO -> "selection", "choice", "classification", "type", "category"
- **NEW REQUIREMENT**: For each H2, you MUST generate a "section_context" field (max 10 words)
  that summarizes what this section is about in simple, clear terms.
  **IMPORTANT**: Include key entity/role from H1 (e.g., "investor", "entity", "co-investor", "patient", "doctor", "parent", "spouse", "guarantor")
  to identify WHO this section is about, combined with WHAT the H2 is about.
  Example:
    H1="Investor Profile Form", H2="Basic Information" (with TEXT fields Name, SSN, Amount)
      -> section_context="Investor identity and subscription details"
    H1="Investor Profile Form", H2="Investor Classification" (with CHECKBOX fields for entity type)
      -> section_context="Investor entity type selection"
    H1="Patient Information", H2="Medical History" (with CHECKBOX fields for conditions)
      -> section_context="Patient medical condition selection"
    H1="Entity Details", H2="Ownership Structure" (with TEXT fields for owners)
      -> section_context="Entity ownership information and details"

  **Key Identifying Words to Extract from H1:**
  - investor, co-investor, primary investor, secondary investor
  - entity, corporation, partnership, trust
  - patient, doctor, physician, provider
  - parent, guardian, spouse, dependent
  - guarantor, co-signer, authorized person
  - employee, employer, beneficiary

  Always include the identifying role/entity in the section_context to make it clear WHO the section describes.

**H3 (Field Label):**
- Label for a specific field or group of related fields.
- Typically short (1–15 words), may end with ":".
- **CRITICAL SPATIAL RULES FOR H3**:
  1. Must be within 50 pixels vertically of the field placeholder
  2. Prefer text DIRECTLY LEFT or DIRECTLY ABOVE the field (same line or line immediately above)
  3. **IGNORE text in extreme corners** (> 300 pixels away horizontally) unless it's the ONLY candidate
  4. Do NOT extract page headers, footers, watermarks, or unrelated corner text as H3
  5. Look for text on the SAME LINE first, then the line IMMEDIATELY ABOVE
- **CRITICAL GROUPING RULE**:
  - If you see a line like "Type of Investor—Please check one:" followed by checkboxes,
    this is an H3 for a checkbox group, NOT related to text fields above it (like Name, SSN).
  - Text fields (Name, SSN, Amount) at the top should have their own H3 labels.
  - Checkbox/radio groups in the middle should be separate H3 under a different H2.
  - Example:
    ✅ CORRECT:
    H2: "Basic Information"
      H3: "Name of Investor" (fid: 1)
      H3: "Social Security Number" (fid: 2)
    H2: "Investor Classification"  ← SEPARATE H2
      H3: "Type of Investor" (fid: null)
        H4: "Individual" (fid: 7)
        H4: "Corporation" (fid: 8)

    ❌ WRONG:
    H2: "Basic Information"
      H3: "Name of Investor" (fid: 1)
      H3: "Type of Investor" (fid: null) ← DON'T mix with text fields above
- **MANDATORY: ALWAYS CREATE H3 FOR CHECKBOX/RADIO GROUPS**:
  - When you see H4 options (Individual, Corporation, Partnership, etc.), you MUST create an H3 parent.
  - **NEVER leave h3=null when h4 has a value!**
  - If no explicit label exists above the options, INFER the H3 from the H4 option types.
- **INFER H3 FROM H4 OPTIONS** (CRITICAL - DO NOT SKIP):
  - If H3 label is unclear or missing, but H4 options exist, you MUST INFER the H3 from the option types:
  - **COMMON PATTERNS TO DETECT**:
    H4 options: "Individual", "Corporation", "Partnership", "Trust", "LLC" -> H3: "Type of Investor" or "Entity Type"
    H4 options: "Mr", "Mrs", "Ms", "Dr" -> H3: "Salutation"
    H4 options: "Computer Science", "Electrical", "Mechanical" -> H3: "Department"
    H4 options: "Male", "Female" -> H3: "Gender"
    H4 options: "Single", "Married", "Divorced", "Widowed" -> H3: "Marital Status"
    H4 options: "Yes", "No" -> H3: (use context from nearby text or section)
    H4 options: "Registered Investment Company", "Joint Tenants", "Tenants in Common" -> H3: "Type of Investor"
  - **ALWAYS analyze the semantic meaning of options to determine the question being asked**
- Examples:
  - "Name of Investor"
  - "Social Security Number"
  - "Type of Investor"
  - Column names in a table: "Country", "Amount", "Currency"
- If text is a question followed by blanks, the question is h3.
- For line with multiple blanks, each blank must be mapped to its own h3, using the nearby words.

**H4 (Option / Child Cell):**
- For choice fields: individual checkbox/radio options under an h3 question.
  Example:
    H3: "Type of Investor"
    H4: "Individual [CHECKBOX_FIELD:7]"
    H4: "Corporation [CHECKBOX_FIELD:8]"
- For tables: each [TABLE_CELL_FIELD:id] is h4 under its column's h3.
  Example:
    H3: "Country"
    H4: row cell with [TABLE_CELL_FIELD:50] under "Country".

══════════════════════════════════════════════
MULTIPLE FIELDS ON SAME LINE
══════════════════════════════════════════════

DO NOT treat a whole line as a single heading when it contains multiple placeholders.
You must split by placeholder and create separate entries.

Example line:
"City [TEXT_FIELD:10] State [TEXT_FIELD:11] Zip [TEXT_FIELD:12]"

You must produce THREE h3 entries:

- h3 for field id 10 -> text: "City", fid: 10
- h3 for field id 11 -> text: "State", fid: 11
- h3 for field id 12 -> text: "Zip", fid: 12

Use the nearest words to the left (or sometimes right) of each placeholder as the label text.
Strip colons and underscores: "Name: [TEXT_FIELD:1]" -> "Name".

══════════════════════════════════════════════
TABLE HANDLING WITH [TABLE_CELL_FIELD]
══════════════════════════════════════════════

1. Detect table-like structures:
   - Several consecutive lines arranged in columns (similar top increments, different left positions).
   - Header row without placeholders, followed by rows WITH [TABLE_CELL_FIELD:id].

2. Column headers (first table row) become h3:
   - Example header row: "Country  |  Amount  |  Currency"
   - Create h3 entries:
     - h3: "Country" (structural, fid: null)
     - h3: "Amount" (fid: null)
     - h3: "Currency" (fid: null)

3. Each cell with [TABLE_CELL_FIELD:id] becomes h4 under the corresponding column h3:
   - Determine which column a cell belongs to by comparing bbox.left to header bbox.left.
   - Each such h4 must have fid = that TABLE_CELL_FIELD id.
   - **IMPORTANT**: Include the row number in the h4 text to distinguish multiple rows.
   - Example:
     Column header: "Name"
     Row 1 cell: h4 text = "Name_row_1" with fid = 50
     Row 2 cell: h4 text = "Name_row_2" with fid = 51
     Row 3 cell: h4 text = "Name_row_3" with fid = 52

4. Track row numbers by counting consecutive cells under the same column header.
   Start row numbering from 1 for the first data row after the header.

5. Do NOT create redundant h3/h4 for decorative or empty cells.

══════════════════════════════════════════════
CHOICE FIELDS: CHECKBOX / RADIO (CRITICAL)
══════════════════════════════════════════════

For [CHECKBOX_FIELD:id] and [RADIOBUTTON_FIELD:id]:

1. Identify the parent question or group label (h3):
   - Look for text above the options or at the start of the line.
   - Example:
     "Type of Investor (check one):"
     "[CHECKBOX_FIELD:7] Individual   [CHECKBOX_FIELD:8] Corporation"

   Output:
   - h3: "Type of Investor" with fid = null (remove "(check one)")
   - h4: "Individual" with fid = 7
   - h4: "Corporation" with fid = 8

2. **INFER H3 LABEL FROM OPTIONS** (when H3 is unclear/missing):
   - Analyze the H4 option values to determine what the question is asking:

   **Example 1: Salutation/Title**
   Options: "[RADIO:1] Mr  [RADIO:2] Mrs  [RADIO:3] Ms  [RADIO:4] Dr"
   -> Inferred H3: "Salutation" (fid: null)
   -> H4: "Mr" (fid: 1), "Mrs" (fid: 2), "Ms" (fid: 3), "Dr" (fid: 4)

   **Example 2: Department**
   Options: "[CHECKBOX:10] Computer Science  [CHECKBOX:11] Electrical  [CHECKBOX:12] Mechanical"
   -> Inferred H3: "Department" (fid: null)
   -> H4: "Computer Science" (fid: 10), "Electrical" (fid: 11), "Mechanical" (fid: 12)

   **Example 3: Gender**
   Options: "[RADIO:5] Male  [RADIO:6] Female"
   -> Inferred H3: "Gender" (fid: null)
   -> H4: "Male" (fid: 5), "Female" (fid: 6)

   **Example 4: Marital Status**
   Options: "[RADIO:20] Single  [RADIO:21] Married  [RADIO:22] Divorced  [RADIO:23] Widowed"
   -> Inferred H3: "Marital Status" (fid: null)
   -> H4: "Single" (fid: 20), "Married" (fid: 21), etc.

   **Example 5: Entity Type**
   Options: "[RADIO:30] Individual  [RADIO:31] Corporation  [RADIO:32] Partnership  [RADIO:33] Trust"
   -> Inferred H3: "Entity Type" (fid: null)
   -> H4: "Individual" (fid: 30), "Corporation" (fid: 31), etc.

3. **DO NOT use question-like text for H3 that looks like it's asking for a choice**:
   - Bad: "Please select your department:" -> Use "Department" instead
   - Bad: "What is your marital status?" -> Use "Marital Status" instead
   - Bad: "Choose one of the following:" -> Infer from options instead
   - Good: Clean, simple label derived from the option context

4. Do NOT create extra h3 if a field is clearly just a simple checkbox label like:
   "[CHECKBOX_FIELD:20] I agree to the terms" -> This is a single h4 with fid = 20 under the closest section h2.

══════════════════════════════════════════════
WHAT NOT TO TAG AS H3/H4
══════════════════════════════════════════════

Avoid creating h3/h4 for:

- Pure decorative text, watermarks, or page numbers.
- Long paragraphs that are instructions, unless they clearly contain a fill-in-the-blank question.
- Labels with NO associated placeholders (unless they are genuine structural headings like h1/h2).

══════════════════════════════════════════════
OUTPUT FORMAT (JSON ONLY, MINIMAL)
══════════════════════════════════════════════

Return JSON with a flat list of sections:

{{
  "sections": [
    {{
      "text": "heading or label text (clean, no colons/underscores)",
      "level": "title|h1|h2|h3|h4",
      "page": page_number,
      "lid": "line_id_from_input",
      "fid": fid_or_null,
      "section_context": "simple 10-word summary (ONLY for h2, null for others)"
    }}
  ]
}}

{classification_instruction.strip() and '''
FIRST CHUNK ONLY - Add document classification at top level:

{
  "pdf_category": {
    "category": "finance",
    "sub_category": "investment",
    "document_type": "subscription_form"
  },
  "sections": [...]
}
''' if is_first_chunk else ''}

Rules for output:

- For title / h1 / h2, set "fid": null (pure headings).
- **For h2 ONLY**: Include "section_context" (max 10 words summary of what the section is about).
  **CRITICAL**: section_context MUST match the actual field types in that H2 section:
    - TEXT fields -> Use "information", "details", "data", "identification"
    - CHECKBOX/RADIO -> Use "selection", "choice", "classification", "type"
- For h1, h3, h4, title: set "section_context": null
- For h3 that directly labels a single field placeholder, set "fid" to that field's id.
- For h3 that is a group question for multiple checkboxes/radios, set "fid": null (children carry fids).
- **MANDATORY RULE**: If you create h4 entries, you MUST create a parent h3 for them!
  - NEVER output h3=null when h4 has values
  - If no explicit label exists, INFER h3 from the h4 option types (Individual/Corporation -> "Type of Investor")
- For every h4 (checkbox/radio option or table cell), set "fid" to the placeholder id.
- Do NOT include bbox, field_ids arrays, field_types, or any other extra keys.

Return ONLY valid JSON. No markdown, no explanation.
"""


def build_header_index(headers: list[dict]) -> tuple:
    """
    Build indexes for efficient header lookup:
    - fid -> header section (for h3/h4 that reference a field)
    - page -> list of structural headings (title/h1/h2 with section_context)
    - Build hierarchy map: fid -> (h2, section_context, parent_h3) to know which H2 and H3 each field belongs to
    """
    fid_to_header: dict[Any, Any] = {}
    page_to_structural: dict[Any, Any] = {}
    fid_to_h2_map = {}  # NEW: Map fid to its parent H2 and H3

    # Track current hierarchy context as we iterate through headers
    current_h2 = None
    current_h2_section_context = None
    current_h3 = None

    for h in headers:
        level = h.get("level")
        page = h.get("page")
        fid = h.get("fid")
        text = h.get("text")

        # Index structural headings by page
        if page is not None and level in ("title", "h1", "h2"):
            page_to_structural.setdefault(page, []).append(h)

        # Track current H2 context
        if level == "h2":
            current_h2 = text
            current_h2_section_context = h.get("section_context")
            current_h3 = None  # Reset H3 when entering new H2

        # Track current H3 context
        if level == "h3":
            current_h3 = text

        # Map fields to their H2/H3 context
        if fid is not None:
            # Determine the correct H3 for this field
            field_h3 = None
            if level == "h3":
                # This field IS the H3 (text field with direct label)
                field_h3 = text
            elif level == "h4":
                # This is an H4, use the current H3 context
                field_h3 = current_h3

            # This field belongs to current H2
            fid_to_h2_map[fid] = {
                "h2": current_h2,
                "section_context": current_h2_section_context,
                "parent_h3": field_h3,  # Store the parent H3 for H4 fields
            }

        # Index field-linked headings by fid
        if fid is not None and level in ("h3", "h4"):
            fid_to_header[fid] = h

    return fid_to_header, page_to_structural, fid_to_h2_map


def find_page_hierarchy(page: int, structural_headings: list[dict]) -> tuple:
    """
    Find title/h1/h2/section_context for a given page from structural headings.
    Returns (title, h1, h2, section_context)
    """
    title = None
    h1 = None
    h2 = None
    section_context = None

    for h in structural_headings:
        lvl = h.get("level")
        if lvl == "title" and title is None:
            title = h.get("text")
        elif lvl == "h1" and h1 is None:
            h1 = h.get("text")
        elif lvl == "h2":
            h2 = h.get("text")  # Take last h2 on page
            section_context = h.get("section_context")  # Get section_context from h2

    return title, h1, h2, section_context


async def load_json_from_storage(path: str) -> dict:
    """Load JSON from S3 or local storage"""
    if path.startswith("s3://"):
        from pdf_autofillr_mapper.clients.s3_client import S3Client

        s3_client = S3Client()
        local_temp_path = f"/tmp/headers_temp_{path.split('/')[-1]}"
        s3_client.download_file_from_s3(path, local_temp_path)
        with open(local_temp_path, encoding="utf-8") as f:
            return json.load(f)
    else:
        with open(path, encoding="utf-8") as f:
            return json.load(f)


async def save_json_to_storage(data: Any, path: str):
    """Save JSON to S3 or local storage"""
    if path.startswith("s3://"):
        from pdf_autofillr_mapper.clients.s3_client import S3Client

        s3_client = S3Client()
        local_temp_path = f"/tmp/headers_output_{path.split('/')[-1]}"
        with open(local_temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        s3_client.upload_file_to_s3(local_temp_path, path)
        logger.info(f"Saved to S3: {path}")
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved locally: {path}")
