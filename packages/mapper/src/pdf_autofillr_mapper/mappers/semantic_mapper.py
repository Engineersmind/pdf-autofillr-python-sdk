import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Optional

import tiktoken

from pdf_autofillr_mapper.chunkers import get_chunker
from pdf_autofillr_mapper.groupers.group_by_llm import GroupByLLM
from pdf_autofillr_mapper.utils.storage import save_json
from pdf_autofillr_mapper.utils.timing import timing_decorator

logger = logging.getLogger(__name__)

# executor = ThreadPoolExecutor()


class SemanticMapper:

    def __init__(
        self,
        method_config: Optional[dict] = None,
        chunking_section: Optional[dict] = None,
        llm_provider: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        chunking_strategy: Optional[str] = None,
    ):
        """
        Initialize SemanticMapper with either legacy config dicts or modern parameters.

        Args:
            method_config: Legacy config dict (deprecated)
            chunking_section: Legacy config dict (deprecated)
            llm_provider: LLM provider name ("claude", "openai")
            confidence_threshold: Confidence threshold for mappings
            chunking_strategy: Chunking strategy name
        """
        # Import config system
        from pdf_autofillr_mapper.core.config import (
            get_chunking_config,
            get_semantic_mapper_config,
            settings,
        )

        # Handle legacy constructor calls vs new parameter-based calls
        if method_config is not None or chunking_section is not None:
            # Legacy mode - use provided configs
            logger.warning(
                "Using legacy SemanticMapper constructor. Consider updating to parameter-based constructor."
            )

            if method_config is None:
                method_config = {}
            if chunking_section is None:
                chunking_section = get_chunking_config()

            # Extract values from legacy configs
            llm_name = method_config.get("llm", settings.mapper_method_llm)
            self.confidence_threshold = float(
                method_config.get(
                    "confidence_threshold", settings.mapper_method_confidence_threshold
                )
            )
            self.include_key_variants = method_config.get(
                "include_key_variants", settings.mapper_method_include_key_variants
            )
            self.include_field_name_variants = method_config.get(
                "include_field_name_variants",
                settings.mapper_method_include_field_name_variants,
            )
            self.include_description = method_config.get(
                "include_description", settings.mapper_method_include_description
            )

        else:
            # Modern mode - use parameters with config defaults
            semantic_config = get_semantic_mapper_config()
            chunking_section = get_chunking_config()

            llm_name = llm_provider or semantic_config["llm"]
            self.confidence_threshold = (
                confidence_threshold or semantic_config["confidence_threshold"]
            )
            self.include_key_variants = semantic_config["include_key_variants"]
            self.include_field_name_variants = semantic_config[
                "include_field_name_variants"
            ]
            self.include_description = semantic_config["include_description"]

        # Initialize LLM with UnifiedLLMClient (LiteLLM)
        from pdf_autofillr_mapper.clients.unified_llm_client import UnifiedLLMClient

        # Get LLM config from settings
        llm_model = llm_name  # Model name in LiteLLM format
        llm_temperature = getattr(settings, "llm_temperature", 0.0)
        llm_max_tokens = getattr(settings, "llm_max_tokens", 4096)
        llm_timeout = getattr(settings, "llm_timeout", 120)
        llm_max_retries = getattr(settings, "llm_max_retries", 3)

        self.llm = UnifiedLLMClient(
            model=llm_model,
            temperature=llm_temperature,
            max_tokens=llm_max_tokens,
            timeout=llm_timeout,
            max_retries=llm_max_retries,
        )
        self.max_threads = settings.llm_max_threads

        logger.info(
            f"Initialized SemanticMapper with LLM: {llm_model}, max_threads: {self.max_threads}"
        )
        logger.info(
            f"Config - temperature: {llm_temperature}, confidence_threshold: {self.confidence_threshold}"
        )
        logger.info(
            f"LLM Config - max_tokens: {llm_max_tokens}, timeout: {llm_timeout}s, max_retries: {llm_max_retries}"
        )

        # Initialize tokenizer
        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")

        # Setup chunking strategy
        strategy: Optional[str]
        if chunking_strategy:
            # Override strategy if provided as parameter
            strategy = chunking_strategy
        else:
            strategy = chunking_section.get("current_strategy")

        # Map strategy names to actual chunker names
        strategy_name_map = {
            "page": "page",
            "page_based": "page",
            "window": "window",
            "window_based": "window",
        }

        chunker_strategy = strategy_name_map.get(strategy or "", strategy or "")

        strategy_config: Any = next(
            (
                s
                for s in chunking_section.get("strategies", [])
                if s.get("name") == strategy
            ),
            {},
        )
        strategy_config["name"] = chunker_strategy

        logger.info(f"Using chunking strategy: {strategy} -> {chunker_strategy}")
        logger.debug(f"Chunking config: {strategy_config}")

        self.chunker = get_chunker(chunker_strategy, self.tokenizer, **strategy_config)

    def prepare_updated_input_data(self, input_data):
        """Only keep list of keys, ignore values."""
        return list(input_data.keys())

    def prepare_updated_input_data_with_description(self, input_data) -> dict:
        return {
            key: [info["description"]]
            for key, info in input_data.items()
            if "description" in info
        }

    def flatten_enriched_data(self, enriched: dict) -> dict:
        return {
            key: info["value"]
            for key, info in enriched.items()
            if isinstance(info, dict) and "value" in info
        }

    def build_input_key_section(
        self, input_keys: list, key_variants: Optional[dict[Any, Any]] = None
    ) -> str:
        if not key_variants:
            if self.include_description == 1:
                return f"""
            ---
            Input Keys:
            You are given a dictionary where each key maps to a list containing its description:
            {json.dumps(input_keys, indent=2)}

            - These keys are the only allowed labels for matching.
            - Do not invent, reword, interpret, or create new labels.
            - Only return exact matches from this list in your output's "key" field.
            - Each key has a corresponding description to clarify its meaning.
            - Make use of the description to understand the intent behind each key and guide accurate mapping, check for paranthesis for special instruction in descriptions
            """
            else:
                return f"""
            ---
            Input Keys:
            You are given a flat list of semantic keys:
            {json.dumps(input_keys, indent=2)}

            - These are the only allowed key labels.
            - Do not invent, reword, interpret, or create new labels.
            - Only return exact matches from this list in your output's "key" field.
            """
        else:
            return f"""
    ---
    Input Key Variants:
    You are given a dictionary of semantic key variants.
    Each key has multiple equivalent phrasings that may be used in form labels:

    {json.dumps(key_variants, indent=2)}

    - You must match the field context to one of the variants.
    - Then, return the original key corresponding to that variant.
    - Do not return the variant — only the original key.
    - Only use keys from the original input_keys list.
    """

    def build_key_matching_rules(
        self, key_variants: Optional[dict[Any, Any]] = None
    ) -> str:
        if not key_variants:
            return """
    ---
    Key Matching from Input Only:
    - You must identify what the field is asking for, then select the corresponding label from the input_keys list.
    - The "key" must be a value from the input list only.
    - Do not write inferred or paraphrased labels like "Amount of Investment" unless that exact string is in input_keys.
    - Always return the best matching input key from the list, or null if no clear match.
    """
        else:
            return """
    ---
    Key Matching from Input Variants:
    - You are provided with multiple semantic variants (alternative phrasings) for each input key.
    - Your task is to match the semantic meaning of each field (based on its label/context) to the most relevant variant.
    - Then, return the original key whose variant had the best semantic match.
    - Do not invent or infer keys outside the provided list.
    - The "key" in your final output must be from the original input_keys list — even though matching is done on variants.
    - If none of the variants semantically match well, set "key": null and "con": 0.

    Example:
    If one of the input keys is "investor_full_name" and its variants include:
    - "Full Name of Investor"
    - "Name of the Individual Investor"
    - "Investor's Legal Name"

    And the field label is "Investor Name", then you may semantically match it to one of these variants, and return:
    "key": "investor_full_name"
    """

    def build_field_name_variant_section(self, field_name_variants: dict) -> str:
        """
        Builds a section for the prompt describing semantic variants of field names per fid.

        Args:
            field_name_variants (dict): Dictionary where each key is fid (as str) and value is list of semantic variants,
                                        with the last item being the original field_name.

        Returns:
            str: A formatted section describing the variants for use in prompt instructions.
        """
        if not field_name_variants:
            return ""

        lines = [
            "---",
            "Field Name Variants:",
            "You are provided with multiple semantic variants for certain form fields (by fid).",
            "These are alternative phrasings of the field's intent. The last item in each list is the original field_name.",
            "Use these to better understand the context, but do not use them as input keys.",
            "",
            "FID -> Field Name and Variants:",
        ]

        for fid, variants in field_name_variants.items():
            original_field_name = variants[-1]
            lines.append(f"\nFID {fid} ({original_field_name}):")
            for variant in variants[:-1]:
                lines.append(f"- {variant}")
            lines.append(f"- {original_field_name} (original)")

        lines.append(
            "\nUse these to improve your semantic judgment. Do not use them as keys in your output."
        )
        lines.append("---")

        return "\n".join(lines)

    def remove_duplicate_keys_in_table_columns(
        self, mapping_data: dict, extracted_data: dict
    ) -> dict:
        """
        Remove duplicate key assignments within the same column of tables.
        If multiple rows in the same column are assigned the same key, set them to null.

        Args:
            mapping_data: The mapping dictionary {fid: (key, value, confidence, description)}
            extracted_data: The extracted data with form_fields containing tid, row, col info

        Returns:
            Cleaned mapping dictionary with duplicates in same column removed
        """
        logger.info("🔍 Checking for duplicate key assignments in table columns...")

        # Build structure: {tid: {col: [(fid, row, key)]}}
        table_columns: dict[Any, Any] = {}
        fid_to_info: dict[Any, Any] = {}  # Store field info for each fid

        # First, collect all form fields and their table info
        for page in extracted_data.get("pages", []):
            for field in page.get("form_fields", []):
                fid = field.get("fid")
                tid = field.get("tid")
                row = field.get("row")
                col = field.get("col")

                # Only process table cells with row/col info
                if tid is not None and row is not None and col is not None:
                    fid_to_info[fid] = {
                        "tid": tid,
                        "row": row,
                        "col": col,
                        "field_name": field.get("field_name", "unknown"),
                    }

        # Build table column structure with mappings
        # mapping_data format: {fid: (key, value, confidence, description)}
        for fid, mapping_tuple in mapping_data.items():
            fid_int = int(fid) if isinstance(fid, str) else fid

            # Extract key from tuple
            mapped_key = None
            if isinstance(mapping_tuple, tuple) and len(mapping_tuple) >= 1:
                mapped_key = mapping_tuple[0]  # key is first element
            elif isinstance(mapping_tuple, dict):
                mapped_key = mapping_tuple.get("key")
            else:
                continue  # Skip invalid entries

            # Only check non-null mappings
            if fid_int in fid_to_info and mapped_key:
                info = fid_to_info[fid_int]
                tid = info["tid"]
                col = info["col"]
                row = info["row"]

                if tid not in table_columns:
                    table_columns[tid] = {}
                if col not in table_columns[tid]:
                    table_columns[tid][col] = []

                table_columns[tid][col].append(
                    {
                        "fid": fid,
                        "row": row,
                        "key": mapped_key,
                        "field_name": info["field_name"],
                    }
                )

        # Find and remove duplicates within each column
        cleaned_mapping = mapping_data.copy()
        total_duplicates_removed = 0

        for tid, columns in table_columns.items():
            for col, cells in columns.items():
                # Group by key within this column
                key_counts: dict[Any, Any] = {}
                for cell in cells:
                    key = cell["key"]
                    if key not in key_counts:
                        key_counts[key] = []
                    key_counts[key].append(cell)

                # Find keys that appear multiple times in the same column
                for key, occurrences in key_counts.items():
                    if len(occurrences) > 1:
                        # Sort by row to make logging consistent (ascending)
                        occurrences.sort(key=lambda x: x["row"])

                        # Keep the first occurrence (top row), remove the rest
                        first_occurrence = occurrences[0]
                        duplicates_to_remove = occurrences[1:]

                        removed_desc = [
                            f"Row {occ['row']} (FID {occ['fid']})"
                            for occ in duplicates_to_remove
                        ]
                        logger.warning(
                            f"⚠️  Duplicate key '{key}' found in Table {tid}, Column {col} "
                            f"across {len(occurrences)} rows. Keeping Row {first_occurrence['row']} (FID {first_occurrence['fid']}), "
                            f"removing {len(duplicates_to_remove)} duplicate(s): {removed_desc}"
                        )

                        # Set only the duplicate occurrences to null (skip the first one)
                        # Preserve the tuple structure: (None, value, confidence, description)
                        for occurrence in duplicates_to_remove:
                            fid = occurrence["fid"]

                            # Get the original tuple and replace key with None
                            original_tuple = cleaned_mapping[fid]
                            if (
                                isinstance(original_tuple, tuple)
                                and len(original_tuple) >= 3
                            ):
                                # (key, value, confidence) -> (None, value, confidence)
                                cleaned_mapping[fid] = (
                                    None,
                                    original_tuple[1],
                                    original_tuple[2],
                                )
                            elif (
                                isinstance(original_tuple, tuple)
                                and len(original_tuple) >= 1
                            ):
                                # Handle shorter tuples
                                cleaned_mapping[fid] = (None,) + original_tuple[1:]
                            else:
                                # Fallback
                                cleaned_mapping[fid] = None

                            total_duplicates_removed += 1
                            logger.info(
                                f"   ❌ Removed duplicate mapping: FID {fid} (Row {occurrence['row']}, "
                                f"Field: {occurrence['field_name']}) -> null"
                            )

                        # Log the kept occurrence
                        logger.info(
                            f"   ✅ Kept original mapping: FID {first_occurrence['fid']} (Row {first_occurrence['row']}, "
                            f"Field: {first_occurrence['field_name']}) with key '{key}'"
                        )

        if total_duplicates_removed > 0:
            logger.warning(
                f"⚠️  Total duplicate mappings removed: {total_duplicates_removed} "
                f"(across {sum(len(cols) for cols in table_columns.values())} table columns checked)"
            )
        else:
            logger.info("✅ No duplicate key assignments found in table columns")

        return cleaned_mapping

    def prepare_prompt(
        self,
        context_text,
        input_keys,
        investor_type,
        fid_start,
        fid_end,
        key_variants,
        field_name_variants,
    ):
        instructions_header = """
    You are a highly reliable document assistant that must semantically fill fields in a PDF form using the provided field context and a list of known keys.

    You must follow all instructions very carefully. Do not infer values, do not hallucinate, and do not change the required structure under any circumstance.

    Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output
    """

        pdf_context_section = f"""
    ---
    PDF Context:
    Below is the extracted, line-by-line text from the PDF. It includes tagged form fields that require semantic interpretation.



    -----
    {context_text}
    -----
    Investor_type: {investor_type}, Fill fields only as required for the selected investor type:
    - Investor type is different from Subscriber type.
    - Individuals must provide SSN, DOB, occupation; do not request EIN or entity data.
    - Entities (corporation, trust, LLC, partnership, fund) must provide EIN, business details, country of incorporation, and representative info; do not request SSN, DOB, or individual occupation.
    - Joint accounts or co-investors require all personal details for each party.
    - When 'Other' or specific eligibility is selected, ensure any related descriptive or eligibility fields are completed.
    - Only enforce required fields that logically match the investor type.
    - If there are multiple blanks on same line, it might be that key context is top or bottom of the blank most the times, so make sure to check those above or bottom lines as well along with left and right context.
    - based on the investor_type map only those fields that are relevant to that. Please don't map entity fields for individuals and vice versa.
    - signatory is different from signature. Don't fill signatory fields with signature data.
    - In the same table, don't repeat the same key for multiple fids in the same column mainly in TABLE_CELL_FIELD.

    Each field tag is marked using one of the following formats:
    - [TEXT_FIELD:{{fid}}]
    - [TABLE_CELL_FIELD:{{fid}}]
    - [CHECKBOX_FIELD:{{fid}}]
    - [RADIOBUTTON_FIELD:{{fid}}]

    Each fid is a numeric field ID like 11, 12, 24, etc.
    """

        spacing_layout_section = """Field tags like `[BLANK_FIELD:{fid}]` are spaced based on their visual positions in the PDF — extra spaces are added according to gaps between elements.
        Minor spacing mismatches may still occur.Sometimes, the label (e.g., Name:) and its blank may not be on the same line — the blank could be above, below, or offset.
        There may also be multiple blanks on the same line or under labels.
        Use both horizontal and vertical alignment to infer mappings accurately. Don't assume blanks are always side-by-side with labels."""

        text_field_section = """
---
BLANK Fields:
These fields are represented as `[TEXT_FIELD:{fid}]` or `[TABLE_CELL_FIELD:{fid}]`.

- These are open-ended fields where a user needs to write something.
- If there are multiple blanks on same line, it might be that key context is top or bottom of the blank most the times, so make sure to check those above or bottom lines as well along with left and right context.
- You must analyze the surrounding context (prefix/suffix text, labels) to understand what is being asked.
- For `[TABLE_CELL_FIELD:{fid}]`, it may belong to a structured table. Consider the column name and any nearby header to infer the meaning.

Guidelines:
- Identify the most appropriate key from the input list that semantically represents the intent of the label around the field.
- Use line-level context and avoid guessing.
- If there are multiple blanks on same line, it might be that key context is top or bottom of the blank most the times, so make sure to check those above or bottom lines as well along with left and right context.
- Match based on semantic meaning, not just string similarity.
- If the investor type is individual , we have to take SSN or Social Security Number not EIN. For Corporate entity take EIN.
- Please check the column names in case of table cells to avoid mismatches. We will have columns in the table. Also we should not duplicates in the same table. If there are no enough keys just kill the only keys available making other cells empty.
- Please be careful around the adjacent columns in the table to avoid wrong mappings.
- In the same table and the same column, do not repeat the same key for multiple fids.
- names and signatures are different.
- based on the investor_type map only those fields that are relevant to that. Please don't map entity fields for individuals and vice versa.
- number and # are kind of same like say phone number and phone # or ABA number and ABA #.
"""

        checkbox_field_section = """
---
CHOICE Fields:
These fields are represented as `[CHECKBOX_FIELD:{fid}]`.

- They represent dropdowns or selection lists.
- You must decide what kind of information is being selected here based on the label or line around it.

Additional Tips:
- Keys containing substrings like `check`, `dropdown`, `list`, `type`, `option`, or `selection` are usually better matches for CHOICE fields.
- These fields often appear **together in groups**, such as a series of related dropdowns on the same line or in a table.
- Such groupings may occur **recursively** or across lines, so keep that in mind when interpreting the context.

Guidelines:
- Match to input keys that imply a **selection**.
- Avoid guessing; prioritize semantic meaning based on visible label.
- Example: A label like "Select Investor Type" should match to a key like `investorType`.
-  Subscriber type is different from investor type, So please don't mix them up and look at the label above.
"""

        radio_button_field_section = """
---
BUTTON Fields:
These fields are represented as `[RADIOBUTTON_FIELD:{fid}]`.

- These are checkboxes, toggle buttons, or yes/no fields.
- They typically represent binary decisions or confirmations.

Additional Tips:
- Fields with surrounding text containing words like `check`, `box`, `confirm`, `agree`, or `yes` are often buttons.
- These fields often appear **in groups** (e.g., a list of terms to agree or options to select), and this grouping may be **recursive** across lines or within table rows.
- Use this grouping behavior to guide how multiple buttons should be semantically mapped.

Guidelines:
- Match to input keys that expect a **yes/no** or **true/false** answer.
- Example keys: `isEntityConfirmed`, `hasAgreed`, `checkbox1`, etc.
- Only match if the label clearly implies a binary action or choice.
"""

        table_cell_field_section = """
---
TABLE CELL Fields:
These fields are part of a structured table and represented as `[TABLE_CELL_FIELD:{fid}]`.

- Each cell belongs to a row-column matrix.
- In the same table, don't repeat the same key for multiple fids in the same column
- Contextual meaning is derived from the column header, nearby rows, and any title or label above the table.

Guidelines:
- Identify which **column** and **row context** the field belongs to.
- Use the field's row positioning and the text above the table to decide what kind of data is being filled.
- Not every cell in the table needs to be filled.
- In the same table, don't repeat the same key for multiple fids in the same column
- Match each field to the most semantically appropriate key, based on what that column represents in the table.
"""

        input_keys_section = self.build_input_key_section(input_keys, key_variants)

        fid_range_info = f"""
    ---
    Fid start: {fid_start} and Fid end: {fid_end}

    Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output
    """

        task_description = """
    ---
    Your Task:
    1. For each tagged field (e.g., [BLANK_FIELD:12]) found in the context, analyze the surrounding label to determine what it is asking for.
    1.1 Return only and exactly the fids (field IDs) present in the context. Do not add any fids that are not explicitly tagged in the context text, even if you think they are related.
    2. Based on the semantic meaning of that field label, identify the best-matching key from the input list.
    3. Then, place that matched key (exact string) in the "key" field for that fid. Do not use the label itself.
    4. If no strong match exists, set "key": null and "con": 0.
    """

        formatting_rules = """
    ---
    Field ID Format:
    - The keys in your output JSON must be the raw integer fid values from the context.
    - For example, if the tag is [BLANK_FIELD:11], your JSON should have:
    "11": { "key": ..., "con": ... }
    - Never write "fid11" or similar. Use "11" as the string key.
    - Output key = field number only.
    """

        key_matching_rules = self.build_key_matching_rules(key_variants)
        field_name_section = self.build_field_name_variant_section(field_name_variants)

        semantic_tips = """
    ---
    Semantic Matching:
    - Use only the line of text that contains the [FIELD:X] tag to understand its label.
    - Do not use unrelated or far-away lines.
    - Do not assume meaning. Only use what is clearly visible and relevant.

    Person vs. Entity Detection:
    - based on the investor_type map only those fields that are relevant to that. Please don't map entitity fields for individuals and vice versa.
    - If the label includes terms like "person", "individual", "investor", "whose", or "applicant", it likely refers to a human.
    - If it includes "company", "organization", or "fund", it likely refers to an entity.
    - Use this judgment when mapping date fields or identity fields.

    Special Date Rule:
    - "Date of Birth" refers to a person's birth date only.
    - "Inception Date", "Formation Date", etc., refer to companies or entities only.
    - Never match a Date of Birth field to any key that contains "InceptionDate".
    - If unsure, return "key": null.

    Checkbox Handling:
    - If a label implies Yes/No (like "I confirm", "Is this correct?"), you may treat blanks as checkboxes.
    - Still, match only by the label's semantic meaning to a valid key.
    """

        confidence_score_rules = """
    ---
    Confidence Score:
    You must provide a "con" value with the following rules:
    - 0.90 – 1.00 -> Very strong and clear semantic match
    - 0.60 – 0.89 -> Moderate certainty
    - 0.30 – 0.59 -> Weak match
    - 0.00 – 0.29 -> No match -> set "key": null

    Do not assign high confidence unless the match is clear and unambiguous.
    """

        output_format = """
    ---
    Expected Output Format:
    Return JSON structured exactly like this:

    {
    "11": {
        "key": "input_key_name",
        "con": 0.92
    },
    "12": {
        "key": null,
        "con": 0
    },
    "24": {
        "key": "another_input_key",
        "con": 0.88
    }
    }

    Rules:
    - Field IDs (keys) must be numeric strings like "11", "12", etc.
    - Only return field IDs that appear in the provided context chunk — not more, not less.
    - Do not return any extra or missing fids.
    - Do not include any other text, explanation, or comments. Only valid JSON.
    - Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output
    """

        closing_note = """
    ---
    Final Reminders:
    - Only use keys found in the input list
    - Output keys = numeric fids (e.g., "11"), not "fid11"
    - Confidence score must reflect real certainty
    - Return only fids tagged in the current context
    - Do not guess, hallucinate, reword, or over-infer
    - Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output

    Now begin and return only valid JSON.
    """

        return "\n".join(
            [
                instructions_header,
                pdf_context_section,
                input_keys_section,
                spacing_layout_section,
                text_field_section,
                checkbox_field_section,
                radio_button_field_section,
                table_cell_field_section,
                fid_range_info,
                task_description,
                formatting_rules,
                key_matching_rules,
                field_name_section,
                semantic_tips,
                confidence_score_rules,
                output_format,
                closing_note,
            ]
        )

    def chunk_keys(self, keys, n_chunks):
        chunk_size = max(1, len(keys) // n_chunks)
        for i in range(0, len(keys), chunk_size):
            yield keys[i : i + chunk_size]

    def generate_key_descriptions_bulk(self, keys: list, llm) -> dict:
        prompt = f"""
    You are a helpful assistant. Given a list of JSON keys from a form or document input, generate a human-readable description for each key that clearly explains what the field represents.

    If the meaning of any key is unclear or ambiguous, return "undefined" for that key.

    Strictly return the output as a valid JSON object in the format:
    {{ "key": "description", ... }}

    Try adding better description not just paraphrasing, whos or who are important

    Also retain the numbering in ther say BOwnerCorporationFulllegalname4_ID, it is fourth BOwner...

    Also whenever you find Inception date, tell that it is not data of birth very clearly.

    Do not include any extra commentary, markdown, or explanation — only valid JSON.

    Keys: {keys}

    Output:
    """
        raw_response = llm.complete(prompt)

        # Extract content from LLMResponse object
        if hasattr(raw_response, "content"):
            text = raw_response.content
        elif hasattr(raw_response, "text"):
            text = raw_response.text
        else:
            text = str(raw_response)

        cleaned_json = re.sub(r"^```json\n?|```$", "", text.strip(), flags=re.MULTILINE)
        parsed = json.loads(cleaned_json)
        return parsed

    async def enrich_input_data_llm(self, flat_json: dict, llm) -> dict:
        keys = list(flat_json.keys())
        num_threads = min(self.max_threads, len(keys)) if keys else 1
        key_batches = list(self.chunk_keys(keys, num_threads))
        semaphore = asyncio.Semaphore(self.max_threads)

        logger.info(f"We are running max threads  on input batches on {num_threads}")

        async def process_batch(batch, idx):
            async with semaphore:
                try:
                    descriptions = await asyncio.to_thread(
                        self.generate_key_descriptions_bulk, batch, llm
                    )
                except RuntimeError as _e:
                    if "interpreter shutdown" in str(_e) or "cannot schedule" in str(
                        _e
                    ):
                        return None
                    raise
                return descriptions

        # Launch all batch tasks (they will gate on the semaphore)
        tasks = [
            asyncio.create_task(process_batch(batch, idx))
            for idx, batch in enumerate(key_batches)
        ]
        results = await asyncio.gather(*tasks)

        # Merge output
        descriptions = {}
        for batch_desc in results:
            descriptions.update(batch_desc)

        enriched = {
            key: {"value": value, "description": descriptions.get(key, "undefined")}
            for key, value in flat_json.items()
        }
        return enriched

    async def _process_chunk_async(
        self,
        chunk_key: str,
        chunk_info: dict,
        input_data: dict,
        keys_data: dict,
        investor_type: str,
        input_variants: dict,
        field_name_variants_all: dict,
        semaphore,
    ):
        # Overall chunk timing
        chunk_start_time = time.time()
        wait_start_time = time.time()
        logger.info(
            f"[{chunk_key}] Waiting for semaphore... (Available slots: {semaphore._value})"
        )

        async with semaphore:
            wait_time = time.time() - wait_start_time
            processing_start_time = time.time()
            logger.info(
                f"[{chunk_key}] Started processing after {wait_time:.2f}s wait (Remaining slots: {semaphore._value})"
            )

            context_text = chunk_info["context"]
            start_fid = chunk_info["start_fid"]
            end_fid = chunk_info["end_fid"]
            field_count = end_fid - start_fid + 1 if end_fid >= start_fid else 0

            logger.info(
                f"[{chunk_key}] Processing {field_count} fields (fid: {start_fid} — {end_fid})"
            )

            result_mapping: dict[Any, Any] = {}

            # Track timing for different stages
            timing_info = {
                "wait_time": wait_time,
                "field_count": field_count,
                "prompt_prep_time": 0,
                "llm_call_time": 0,
                "parsing_time": 0,
                "total_processing_time": 0,
            }

            if not context_text.strip() or start_fid < 0:
                logger.warning(
                    f"[{chunk_key}] Skipping due to empty context or no valid FIDs."
                )
                return result_mapping

            # STAGE 1: Filter field name variants for this chunk
            prep_start = time.time()
            field_name_variants_fids = {}
            for fid_str, variants in field_name_variants_all.items():
                try:
                    fid = int(fid_str)
                    if start_fid <= fid <= end_fid:
                        field_name_variants_fids[fid_str] = variants
                except ValueError:
                    logger.warning(
                        f"[{chunk_key}] Skipping invalid fid in field variants: {fid_str}"
                    )

            # STAGE 2: Prepare prompt
            prompt = self.prepare_prompt(
                context_text,
                keys_data,
                investor_type,
                start_fid,
                end_fid,
                input_variants,
                field_name_variants_fids,
            )
            prep_time = time.time() - prep_start
            timing_info["prompt_prep_time"] = prep_time

            input_tokens = len(self.tokenizer.encode(prompt))
            logger.info(
                f"[{chunk_key}] Prompt prepared in {prep_time:.2f}s, tokens: {input_tokens}"
            )

            try:
                # STAGE 3: Send to LLM
                llm_start = time.time()

                # Use UnifiedLLMClient - returns LLMResponse with usage tracking
                messages = [{"role": "user", "content": prompt}]
                llm_response = await asyncio.to_thread(self.llm.complete, messages)

                llm_time = time.time() - llm_start
                timing_info["llm_call_time"] = llm_time

                # Extract response content and usage
                raw_response = llm_response.content
                usage = llm_response.usage

                logger.info(f"[{chunk_key}] LLM call completed in {llm_time:.2f}s")
                logger.info(
                    f"[{chunk_key}] Tokens - Input: {usage.prompt_tokens}, "
                    f"Output: {usage.completion_tokens}, Total: {usage.total_tokens}"
                )
                logger.info(f"[{chunk_key}] Cost: ${usage.cost_usd:.6f}")
                logger.info(
                    f"[{chunk_key}] Processing speed: "
                    f"{usage.prompt_tokens/llm_time:.1f} input tokens/sec, "
                    f"{usage.completion_tokens/llm_time:.1f} output tokens/sec"
                )

                # Log raw response for debugging
                logger.debug(
                    f"[{chunk_key}] Raw LLM response: {raw_response[:200]}..."
                    if len(raw_response) > 200
                    else f"[{chunk_key}] Raw LLM response: {raw_response}"
                )

                # STAGE 4: Parse LLM JSON
                parse_start = time.time()
                cleaned_json = re.sub(
                    r"^```json\n?|```$", "", raw_response.strip(), flags=re.MULTILINE
                )
                parsed = json.loads(cleaned_json)
                parse_time = time.time() - parse_start
                timing_info["parsing_time"] = parse_time

                logger.debug(
                    f"[{chunk_key}] Parsed {len(parsed)} field mappings in {parse_time:.3f}s"
                )

                for fid, info in parsed.items():
                    key = info.get("key")
                    confidence = info.get("con", 0)
                    value = input_data.get(key) if key in input_data else None
                    result_mapping[fid] = (key, value, confidence)
                    logger.debug(
                        f"[{chunk_key}] Mapped fid {fid} -> key: {key}, confidence: {confidence}"
                    )

            except json.JSONDecodeError as e:
                logger.warning(f"[{chunk_key}] Failed to parse LLM JSON response: {e}")
                logger.debug(
                    f"[{chunk_key}] Raw response that failed to parse: {raw_response}"
                )
            except Exception as e:
                logger.error(
                    f"[{chunk_key}] Unexpected error during LLM processing: {e}"
                )

            # Calculate final timing
            processing_time = time.time() - processing_start_time
            total_chunk_time = time.time() - chunk_start_time
            timing_info["total_processing_time"] = processing_time

            # Log comprehensive timing breakdown
            logger.info(f"[{chunk_key}] 🕐 Timing Breakdown:")
            logger.info(f"[{chunk_key}]   Wait time: {timing_info['wait_time']:.2f}s")
            logger.info(
                f"[{chunk_key}]   Prompt prep: {timing_info['prompt_prep_time']:.2f}s"
            )
            logger.info(
                f"[{chunk_key}]   LLM call: {timing_info['llm_call_time']:.2f}s"
            )
            logger.info(
                f"[{chunk_key}]   JSON parsing: {timing_info['parsing_time']:.3f}s"
            )
            logger.info(f"[{chunk_key}]   Total processing: {processing_time:.2f}s")
            logger.info(f"[{chunk_key}]   Total chunk time: {total_chunk_time:.2f}s")
            logger.info(
                f"[{chunk_key}]   Fields/sec: {field_count/processing_time:.1f}"
            )
            logger.info(
                f"[{chunk_key}] ✅ Completed {field_count} fields, {len(result_mapping)} mappings (Slots now: {semaphore._value})"
            )

            return result_mapping

    @timing_decorator
    async def process_and_save(
        self,
        extracted_path,
        input_json_path,
        original_pdf_path,
        storage_config: dict,
        investor_type: Optional[str] = None,
        input_key_json_variants_path: Optional[str] = None,
        field_names_json_variants_path: Optional[str] = None,
    ):
        """
        Process semantic mapping and save results

        Args:
            extracted_path: Path to extracted JSON
            input_json_path: Path to input keys JSON
            original_pdf_path: Path to original PDF
            storage_config: Storage configuration
            input_key_json_variants_path: Optional key variants
            field_names_json_variants_path: Optional field name variants

        Returns:
            dict: Mapping results with timing

        Raises:
            ValueError: If required paths are empty or invalid
            FileNotFoundError: If required files don't exist
            RuntimeError: If mapping fails
        """
        # Validate inputs
        if not extracted_path:
            raise ValueError("extracted_path cannot be empty")
        if not input_json_path:
            raise ValueError("input_json_path cannot be empty")
        if not storage_config:
            raise ValueError("storage_config cannot be empty")

        process_start_time = time.time()
        mapping_path = storage_config.get("output_path")
        radio_path = storage_config.get("radio_groups")

        if not mapping_path:
            raise ValueError("storage_config must contain 'output_path'")
        if not radio_path:
            raise ValueError("storage_config must contain 'radio_groups'")

        logger.info(f"🚀 Starting Field Mapping for: {extracted_path}")

        # Track timing for different stages
        stage_timings: dict[str, float] = {
            "data_loading": 0,
            "key_enrichment": 0,
            "chunking": 0,
            "radio_grouping": 0,
            "chunk_processing": 0,
            "result_saving": 0,
        }

        try:
            # STAGE 1: Load data files
            load_start = time.time()
            logger.info("📂 Loading data files...")

            try:
                # Load extracted data from local file
                if not os.path.exists(extracted_path):
                    raise FileNotFoundError(
                        f"Extracted JSON not found: {extracted_path}"
                    )
                with open(extracted_path, encoding="utf-8") as f:
                    extracted_data = json.load(f)

                if not extracted_data or "pages" not in extracted_data:
                    raise ValueError(
                        f"Invalid extracted data format in: {extracted_path}"
                    )

                # Load input keys from local file
                if not os.path.exists(input_json_path):
                    raise FileNotFoundError(
                        f"Input keys JSON not found: {input_json_path}"
                    )
                with open(input_json_path, encoding="utf-8") as f:
                    input_data = json.load(f)

                if not input_data:
                    raise ValueError(f"Input keys JSON is empty: {input_json_path}")

                load_time = time.time() - load_start
                stage_timings["data_loading"] = load_time
                logger.info(f"📂 Data loading completed in {load_time:.2f}s")

            except (FileNotFoundError, ValueError):
                raise
            except Exception as e:
                logger.error(f"Failed to load data files: {str(e)}", exc_info=True)
                raise RuntimeError(f"Data loading failed: {str(e)}") from e

            # Load optional variants from local files
            input_variants = {}
            if self.include_key_variants and input_key_json_variants_path:
                try:
                    if os.path.exists(input_key_json_variants_path):
                        with open(input_key_json_variants_path, encoding="utf-8") as vf:
                            input_variants = json.load(vf)
                except Exception as e:
                    logger.warning(f"Could not load key variants: {e}")

            field_name_variants_all = {}
            if self.include_field_name_variants and field_names_json_variants_path:
                try:
                    if os.path.exists(field_names_json_variants_path):
                        with open(
                            field_names_json_variants_path, encoding="utf-8"
                        ) as fvf:
                            field_name_variants_all = json.load(fvf)
                except Exception as e:
                    logger.warning(f"Could not load field name variants: {e}")

            # STAGE 2: Prepare keys and enrichment
            try:
                enrich_start = time.time()
                keys_data = self.prepare_updated_input_data(input_data)

                if self.include_description == 1:
                    logger.info(
                        "🔧 Preparing & Including key descriptions in the prompt..."
                    )
                    try:
                        enriched_data = await self.enrich_input_data_llm(
                            input_data, llm=self.llm
                        )
                    except RuntimeError as _e:
                        if "interpreter shutdown" in str(
                            _e
                        ) or "cannot schedule" in str(_e):
                            return None
                        raise
                    keys_data = self.prepare_updated_input_data_with_description(
                        enriched_data
                    )

                enrich_time = time.time() - enrich_start
                stage_timings["key_enrichment"] = enrich_time
                logger.info(f"🔧 Key enrichment completed in {enrich_time:.2f}s")

            except Exception as e:
                logger.error(f"Key enrichment failed: {str(e)}", exc_info=True)
                raise RuntimeError(f"Key enrichment failed: {str(e)}") from e

            # STAGE 3: Generate chunks
            try:
                chunk_start = time.time()
                logger.info("📄 Generating context chunks...")
                context_dict, _ = self.chunker.generate_context_and_stats(
                    extracted_data
                )
                chunk_time = time.time() - chunk_start
                stage_timings["chunking"] = chunk_time
                logger.info(
                    f"📄 Chunking completed in {chunk_time:.2f}s - Generated {len(context_dict)} chunks"
                )

                if not context_dict:
                    raise ValueError("No chunks generated from extracted data")

            except Exception as e:
                logger.error(f"Chunking failed: {str(e)}", exc_info=True)
                raise RuntimeError(f"Context chunking failed: {str(e)}") from e

            final_flat_mapping = {}

            # STAGE 4: Radio button grouping
            try:
                radio_start = time.time()
                logger.info("🔘 Processing radio button groups...")

                groupby_kwargs = {
                    "llm": self.llm,
                    "field_type": "RADIOBUTTON",
                    "threshold": 2,
                    "keys_data": keys_data,
                }

                # Execute radio grouping
                grouper = GroupByLLM(extracted_data, **groupby_kwargs)
                radio_groups_result = grouper.group()

                # Extract just the groups (without llm_usage metadata)
                radio_groups = radio_groups_result.get("groups", {})

                # Log LLM usage stats for radio grouping
                if "llm_usage" in radio_groups_result:
                    usage = radio_groups_result["llm_usage"]
                    logger.info(
                        f"🔘 Radio grouping LLM usage - Model: {usage.get('model')}, "
                        f"Calls: {usage.get('total_calls')}, "
                        f"Tokens: {usage.get('total_tokens')}, "
                        f"Cost: ${usage.get('total_cost_usd', 0):.6f}"
                    )

                # Save radio groups using local storage (only the groups, no metadata)
                radio_storage_config = {"type": "local", "path": radio_path}
                save_json(radio_groups, radio_storage_config)
                # Store local path for operations to reference
                local_radio_path = radio_path

                radio_time = time.time() - radio_start
                stage_timings["radio_grouping"] = radio_time
                logger.info(
                    f"🔘 Radio grouping completed in {radio_time:.2f}s - Found {len(radio_groups)} groups"
                )

            except Exception as e:
                logger.error(f"Radio grouping failed: {str(e)}", exc_info=True)
                raise RuntimeError(f"Radio button grouping failed: {str(e)}") from e

            # STAGE 5: Process chunks async
            try:
                processing_start = time.time()
                semaphore = asyncio.Semaphore(self.max_threads)

                logger.info(
                    f"🧠 Starting async processing with {self.max_threads} max threads for {len(context_dict)} chunks..."
                )

                async def run_all_chunks():
                    tasks = []
                    for _i, (chunk_key, chunk_info) in enumerate(context_dict.items()):
                        task = self._process_chunk_async(
                            chunk_key,
                            chunk_info,
                            input_data,
                            keys_data,
                            investor_type,
                            input_variants,
                            field_name_variants_all,
                            semaphore,
                        )
                        tasks.append(task)
                    results = await asyncio.gather(*tasks)
                    for chunk_result in results:
                        final_flat_mapping.update(chunk_result)

                await run_all_chunks()

                processing_time = time.time() - processing_start
                stage_timings["chunk_processing"] = processing_time
                logger.info(
                    f"🧠 Chunk processing completed in {processing_time:.2f}s - Processed {len(final_flat_mapping)} field mappings"
                )

                if not final_flat_mapping:
                    logger.warning("No field mappings generated from chunk processing")

            except Exception as e:
                logger.error(f"Chunk processing failed: {str(e)}", exc_info=True)
                raise RuntimeError(
                    f"Field mapping chunk processing failed: {str(e)}"
                ) from e

            try:
                logger.info("🧹 Cleaning duplicate key assignments in table columns...")
                final_flat_mapping = self.remove_duplicate_keys_in_table_columns(
                    final_flat_mapping, extracted_data
                )
                logger.info("✅ Duplicate key cleaning completed")
            except Exception as e:
                logger.warning(
                    f"Failed to clean duplicate keys in table columns: {str(e)}"
                )
                # Don't fail the entire process, just log and continue

            # STAGE 6: Save results
            try:
                save_start = time.time()
                logger.info("💾 Saving results...")

                # Use local storage for saving the mapping
                mapping_storage = storage_config.get(
                    "mapping_storage",
                    {"type": "local", "path": storage_config.get("output_path")},
                )
                save_json(final_flat_mapping, mapping_storage)
                # Store local path for operations to reference
                local_mapping_path = mapping_storage.get("path")

                save_time = time.time() - save_start
                stage_timings["result_saving"] = save_time
                logger.info(f"💾 Results saved in {save_time:.2f}s")

            except Exception as e:
                logger.error(f"Result saving failed: {str(e)}", exc_info=True)
                raise RuntimeError(f"Failed to save mapping results: {str(e)}") from e

            # Calculate total time and performance metrics
            total_time = time.time() - process_start_time
            total_fields_mapped = len(final_flat_mapping)

            # Calculate field statistics from extracted data
            total_fields_in_pdf = 0
            field_type_counts: dict[Any, Any] = {}
            for page in extracted_data.get("pages", []):
                for field in page.get("fields", []):
                    total_fields_in_pdf += 1
                    field_type = field.get("field_type", "UNKNOWN")
                    field_type_counts[field_type] = (
                        field_type_counts.get(field_type, 0) + 1
                    )

            # Calculate mapping statistics by type and confidence
            mapped_by_type: dict[Any, Any] = {}
            high_confidence_count = 0
            low_confidence_count = 0

            for fid, mapping_info in final_flat_mapping.items():
                # mapping_info is a tuple: (key, value, confidence)
                # Get field type from extracted data
                field_type = "UNKNOWN"
                for page in extracted_data.get("pages", []):
                    for field in page.get("fields", []):
                        if str(field.get("fid")) == str(fid):
                            field_type = field.get("field_type", "UNKNOWN")
                            break

                mapped_by_type[field_type] = mapped_by_type.get(field_type, 0) + 1

                # Count confidence levels - mapping_info is tuple (key, value, confidence)
                if isinstance(mapping_info, tuple) and len(mapping_info) >= 3:
                    confidence = mapping_info[2]  # confidence is 3rd element
                elif isinstance(mapping_info, dict):
                    confidence = mapping_info.get("confidence", 0)
                else:
                    confidence = 0

                if confidence >= 0.8:
                    high_confidence_count += 1
                else:
                    low_confidence_count += 1

            logger.info("")
            logger.info("🎯 SEMANTIC MAPPING COMPLETE!")
            logger.info("📊 Field Statistics:")
            logger.info(f"   📄 Total fields in PDF: {total_fields_in_pdf}")

            # Log fields by type in extracted data
            for field_type, count in sorted(field_type_counts.items()):
                mapped_count = mapped_by_type.get(field_type, 0)
                percentage = (mapped_count / count * 100) if count > 0 else 0
                logger.info(
                    f"      • {field_type}: {count} total, {mapped_count} mapped ({percentage:.1f}%)"
                )

            # Calculate percentages safely (avoid division by zero)
            mapping_percentage = (
                (total_fields_mapped / total_fields_in_pdf * 100)
                if total_fields_in_pdf > 0
                else 0
            )
            high_conf_percentage = (
                (high_confidence_count / total_fields_mapped * 100)
                if total_fields_mapped > 0
                else 0
            )
            low_conf_percentage = (
                (low_confidence_count / total_fields_mapped * 100)
                if total_fields_mapped > 0
                else 0
            )

            logger.info(
                f"   ✅ Total fields mapped: {total_fields_mapped} ({mapping_percentage:.1f}%)"
            )
            logger.info(
                f"   🎯 High confidence (≥0.8): {high_confidence_count} ({high_conf_percentage:.1f}%)"
            )
            logger.info(
                f"   ⚠️  Low confidence (<0.8): {low_confidence_count} ({low_conf_percentage:.1f}%)"
            )

            logger.info("📊 Performance Summary:")
            logger.info(
                f"   📂 Data loading: {stage_timings['data_loading']:.2f}s ({stage_timings['data_loading']/total_time*100:.1f}%)"
            )
            logger.info(
                f"   🔧 Key enrichment: {stage_timings['key_enrichment']:.2f}s ({stage_timings['key_enrichment']/total_time*100:.1f}%)"
            )
            logger.info(
                f"   📄 Chunking: {stage_timings['chunking']:.2f}s ({stage_timings['chunking']/total_time*100:.1f}%)"
            )
            logger.info(
                f"   🔘 Radio grouping: {stage_timings['radio_grouping']:.2f}s ({stage_timings['radio_grouping']/total_time*100:.1f}%)"
            )
            logger.info(
                f"   🧠 Chunk processing: {stage_timings['chunk_processing']:.2f}s ({stage_timings['chunk_processing']/total_time*100:.1f}%)"
            )
            logger.info(
                f"   💾 Result saving: {stage_timings['result_saving']:.2f}s ({stage_timings['result_saving']/total_time*100:.1f}%)"
            )
            logger.info(f"   🕐 Total time: {total_time:.2f}s")

            # Calculate processing rate safely
            processing_rate = (
                (total_fields_mapped / total_time) if total_time > 0 else 0
            )
            logger.info(f"   ⚡ Processing rate: {processing_rate:.1f} fields/sec")
            logger.info(f"   📄 Chunks processed: {len(context_dict)}")
            logger.info(f"   🧵 Max threads used: {self.max_threads}")
            logger.info(f"   📁 Output: {mapping_path}")

            # Log LLM usage statistics
            llm_stats = self.llm.get_cumulative_stats()
            logger.info("")
            logger.info("💰 LLM USAGE STATISTICS:")
            logger.info(f"   🤖 Model: {llm_stats['model']}")
            logger.info(f"   📞 Total LLM calls: {llm_stats['total_calls']}")
            logger.info(
                f"   📊 Tokens - Prompt: {llm_stats['total_prompt_tokens']:,}, Completion: {llm_stats['total_completion_tokens']:,}, Total: {llm_stats['total_tokens']:,}"
            )
            logger.info(f"   💵 Total cost: ${llm_stats['total_cost_usd']:.6f}")
            if llm_stats["total_calls"] > 0:
                logger.info(
                    f"   💰 Avg cost per call: ${llm_stats['total_cost_usd']/llm_stats['total_calls']:.6f}"
                )
            if total_fields_mapped > 0:
                logger.info(
                    f"   💎 Cost per field mapped: ${llm_stats['total_cost_usd']/total_fields_mapped:.6f}"
                )
            logger.info("")

            # Return detailed statistics with local paths for operations
            return {
                "mapping_path": local_mapping_path,
                "radio_groups_path": local_radio_path,
                "field_statistics": {
                    "total_fields_in_pdf": total_fields_in_pdf,
                    "total_fields_mapped": total_fields_mapped,
                    "mapping_percentage": (
                        round(total_fields_mapped / total_fields_in_pdf * 100, 1)
                        if total_fields_in_pdf > 0
                        else 0
                    ),
                    "fields_by_type": field_type_counts,
                    "mapped_by_type": mapped_by_type,
                    "high_confidence_count": high_confidence_count,
                    "low_confidence_count": low_confidence_count,
                    "high_confidence_percentage": (
                        round(high_confidence_count / total_fields_mapped * 100, 1)
                        if total_fields_mapped > 0
                        else 0
                    ),
                    "low_confidence_percentage": (
                        round(low_confidence_count / total_fields_mapped * 100, 1)
                        if total_fields_mapped > 0
                        else 0
                    ),
                },
                "performance": {
                    "total_time_seconds": round(total_time, 2),
                    "processing_rate_fields_per_sec": (
                        round(total_fields_mapped / total_time, 1)
                        if total_time > 0
                        else 0
                    ),
                    "chunks_processed": len(context_dict),
                    "max_threads": self.max_threads,
                    "stage_timings": {
                        "data_loading": round(stage_timings["data_loading"], 2),
                        "key_enrichment": round(stage_timings["key_enrichment"], 2),
                        "chunking": round(stage_timings["chunking"], 2),
                        "radio_grouping": round(stage_timings["radio_grouping"], 2),
                        "chunk_processing": round(stage_timings["chunk_processing"], 2),
                        "result_saving": round(stage_timings["result_saving"], 2),
                    },
                },
                "llm_usage": {
                    "model": llm_stats["model"],
                    "total_calls": llm_stats["total_calls"],
                    "total_prompt_tokens": llm_stats["total_prompt_tokens"],
                    "total_completion_tokens": llm_stats["total_completion_tokens"],
                    "total_tokens": llm_stats["total_tokens"],
                    "total_cost_usd": round(llm_stats["total_cost_usd"], 6),
                    "avg_cost_per_call": (
                        round(llm_stats["total_cost_usd"] / llm_stats["total_calls"], 6)
                        if llm_stats["total_calls"] > 0
                        else 0
                    ),
                    "cost_per_field": (
                        round(llm_stats["total_cost_usd"] / total_fields_mapped, 6)
                        if total_fields_mapped > 0
                        else 0
                    ),
                },
            }

        except (ValueError, FileNotFoundError, RuntimeError):
            raise
        except Exception as e:
            logger.error(f"Semantic mapping failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"Semantic mapping process failed: {str(e)}") from e

    def map_fields_from_s3(
        self,
        s3_path: str,
        output_s3_path: str,
        radio_groups_s3_path: Optional[str] = None,
        schema_type: str = "form_mapping",
        input_json_path: Optional[str] = None,
    ):
        """
        Map fields from S3 extracted data to semantic keys.

        This method provides the interface expected by lambda handlers.

        Args:
            s3_path: S3 path to extracted JSON data
            output_s3_path: S3 path for mapping output
            radio_groups_s3_path: S3 path for radio groups output
            schema_type: Type of schema to use
            input_json_path: Path to input keys JSON (REQUIRED - must contain target mapping keys)

        Returns:
            Dictionary with processing results
        """
        from pdf_autofillr_mapper.core.config import get_processing_output_config

        logger.info(f"Starting S3-based field mapping from: {s3_path}")
        logger.info(f"Mapping output: {output_s3_path}")

        if radio_groups_s3_path:
            logger.info(f"Radio groups output: {radio_groups_s3_path}")
        else:
            # Auto-generate radio groups path using our config system
            processing_config = get_processing_output_config(s3_path)
            radio_groups_s3_path = processing_config["radio_groups_path"]
            logger.info(f"Auto-generated radio groups output: {radio_groups_s3_path}")

        # Handle input_json_path requirement
        if not input_json_path:
            # Try to auto-generate input keys path based on extracted JSON path
            logger.info(
                "No input_json_path provided. Attempting to auto-generate based on file naming convention."
            )

            if s3_path.startswith("s3://"):
                # Generate input keys path from extracted JSON path
                # Example: s3://bucket/document_extracted.json -> s3://bucket/document_input_keys.json
                if s3_path.endswith("_extracted.json"):
                    base_path = s3_path[:-15]  # Remove "_extracted.json"
                    input_json_path = f"{base_path}_input_keys.json"
                else:
                    # Fallback: replace .json with _input_keys.json
                    base_path = s3_path.rsplit(".json", 1)[0]
                    input_json_path = f"{base_path}_input_keys.json"

                logger.info(f"Auto-generated input_json_path: {input_json_path}")

                # Check if the input keys file exists
                from pdf_autofillr_mapper.clients.s3_client import S3Client

                s3_client = S3Client()
                if not s3_client.object_exists(input_json_path):
                    raise FileNotFoundError(
                        f"Required input keys file not found at: {input_json_path}\n"
                        f"The input keys JSON file is mandatory for semantic mapping. "
                        f"It should contain the target semantic keys that form fields will be mapped to.\n"
                        f"Please create this file with your target mapping keys or provide input_json_path parameter."
                    )
            else:
                # Local path handling
                if s3_path.endswith("_extracted.json"):
                    base_path = s3_path[:-15]  # Remove "_extracted.json"
                    input_json_path = f"{base_path}_input_keys.json"
                else:
                    base_path = s3_path.rsplit(".json", 1)[0]
                    input_json_path = f"{base_path}_input_keys.json"

                logger.info(f"Auto-generated input_json_path: {input_json_path}")

                if not os.path.exists(input_json_path):
                    raise FileNotFoundError(
                        f"Required input keys file not found at: {input_json_path}\n"
                        f"The input keys JSON file is mandatory for semantic mapping. "
                        f"It should contain the target semantic keys that form fields will be mapped to.\n"
                        f"Please create this file with your target mapping keys or provide input_json_path parameter."
                    )

        logger.info(f"Using input keys from: {input_json_path}")

        # Create local storage config for save_json function
        mapping_storage_config = {"type": "local", "path": output_s3_path}

        radio_storage_config = {"type": "local", "path": radio_groups_s3_path}

        # Create storage config dict for process_and_save
        storage_config = {
            "output_path": output_s3_path,
            "radio_groups": radio_groups_s3_path,
            "mapping_storage": mapping_storage_config,
            "radio_storage": radio_storage_config,
        }

        # Run async process_and_save
        try:
            s3_mapping_start = time.time()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result_path = loop.run_until_complete(
                self.process_and_save(
                    extracted_path=s3_path,
                    input_json_path=input_json_path,
                    original_pdf_path="",  # Not needed for current processing
                    storage_config=storage_config,
                )
            )

            total_s3_time = time.time() - s3_mapping_start

            # Load results to get field counts
            field_counts = {"total": 0, "high_confidence": 0, "low_confidence": 0}
            try:
                if output_s3_path.startswith("s3://"):
                    from pdf_autofillr_mapper.clients.s3_client import S3Client

                    s3_client = S3Client()
                    mapping_data = s3_client.load_json_from_s3(output_s3_path)
                else:
                    with open(output_s3_path) as f:
                        mapping_data = json.load(f)

                field_counts["total"] = len(mapping_data)
                for _fid, (_key, _value, confidence) in mapping_data.items():
                    if confidence >= 0.7:
                        field_counts["high_confidence"] += 1
                    else:
                        field_counts["low_confidence"] += 1
            except Exception as e:
                logger.warning(f"Could not load mapping results for field counts: {e}")

            return {
                "status": "success",
                "mapping_path": result_path,
                "radio_groups_path": radio_groups_s3_path,
                "total_fields": field_counts["total"],
                "high_confidence_count": field_counts["high_confidence"],
                "low_confidence_count": field_counts["low_confidence"],
                "processing_time_seconds": round(total_s3_time, 2),
            }

        except Exception as e:
            logger.error(f"Failed to process S3 mapping: {str(e)}")
            raise

    async def map(self, extracted_data: dict, input_schema: dict) -> dict:
        """
        In-memory mapping interface called by PDFPipeline.map().

        Args:
            extracted_data: The extracted PDF data dict (from extract step)
            input_schema:   The input keys/schema dict

        Returns:
            dict with 'mapping' and 'radio_groups' keys
        """
        import tempfile

        # Write inputs to temp files (process_and_save works with file paths)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_extracted.json", delete=False, encoding="utf-8"
        ) as ef:
            json.dump(extracted_data, ef)
            extracted_path = ef.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_schema.json", delete=False, encoding="utf-8"
        ) as sf:
            json.dump(input_schema, sf)
            schema_path = sf.name

        mapping_path = extracted_path.replace("_extracted.json", "_mapping.json")
        radio_path = extracted_path.replace("_extracted.json", "_radio.json")

        storage_config = {
            "output_path": mapping_path,
            "radio_groups": radio_path,
            "mapping_storage": {"type": "local", "path": mapping_path},
            "radio_storage": {"type": "local", "path": radio_path},
        }

        try:
            await self.process_and_save(
                extracted_path=extracted_path,
                input_json_path=schema_path,
                original_pdf_path="",
                storage_config=storage_config,
            )

            with open(mapping_path, encoding="utf-8") as f:
                mapping = json.load(f)
            with open(radio_path, encoding="utf-8") as f:
                radio_groups = json.load(f)

            return {"mapping": mapping, "radio_groups": radio_groups}

        finally:
            for p in [extracted_path, schema_path, mapping_path, radio_path]:
                try:
                    os.unlink(p)
                except OSError:
                    pass  # intentional
