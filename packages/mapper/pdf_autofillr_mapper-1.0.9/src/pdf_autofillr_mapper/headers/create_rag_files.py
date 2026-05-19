"""
Create RAG API input files from final form fields.

This module creates two files for RAG API consumption:
1. header_file.json: Contains field metadata with context and headers
2. section_file.json: Contains hierarchical section structure

Source-agnostic: Works with local, S3, Azure, or GCP storage.
File paths are configured in config.ini, not hardcoded.
"""

import json
import os
from typing import Dict, List, Any
from pdf_autofillr_mapper.core.logger import logger


async def create_rag_api_files(
    final_form_fields_path: str,
    header_file_output_path: str,
    section_file_output_path: str,
    user_id: int,
    session_id: str,
    pdf_doc_id: int,
    pdf_hash: str
) -> Dict[str, str]:
    """
    Create RAG API input files from final form fields.
    Source-agnostic - paths come from config.ini.
    
    Creates two files:
    1. header_file.json: Field-level data with context
    2. section_file.json: Section hierarchy structure
    
    Args:
        final_form_fields_path: Path to final_form_fields.json (from config)
        header_file_output_path: Where to save header_file.json (from config)
        section_file_output_path: Where to save section_file.json (from config)
        user_id: User ID
        session_id: Session ID
        pdf_doc_id: PDF document ID
        pdf_hash: PDF fingerprint hash
        
    Returns:
        Dict with paths to created files:
        {
            "header_file": "/path/to/header_file.json",
            "section_file": "/path/to/section_file.json"
        }
    """
    logger.info(f"Creating RAG API files from {final_form_fields_path}")
    
    # Load final form fields (local file - already downloaded by caller)
    with open(final_form_fields_path, 'r') as f:
        data = json.load(f)
    
    # Extract fields and pdf_category
    fields = data.get("fields", [])
    pdf_category = data.get("pdf_category")
    
    logger.info(f"Processing {len(fields)} fields for RAG API")
    
    # Create header_file.json (field-level data)
    header_file_data = create_header_file(
        fields=fields,
        pdf_hash=pdf_hash,
        pdf_category=pdf_category,
        user_id=user_id,
        session_id=session_id,
        pdf_doc_id=pdf_doc_id
    )
    
    # Create section_file.json (hierarchical structure)
    section_file_data = create_section_file(
        fields=fields,
        pdf_category=pdf_category,
        user_id=user_id,
        session_id=session_id,
        pdf_doc_id=pdf_doc_id
    )
    
    # Ensure output directories exist
    os.makedirs(os.path.dirname(header_file_output_path), exist_ok=True)
    os.makedirs(os.path.dirname(section_file_output_path), exist_ok=True)
    
    # Save header_file.json to configured path
    with open(header_file_output_path, 'w', encoding='utf-8') as f:
        json.dump(header_file_data, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ header_file.json created: {header_file_output_path}")
    
    # Save section_file.json to configured path
    with open(section_file_output_path, 'w') as f:
        json.dump(section_file_data, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ section_file.json created: {section_file_output_path}")
    
    return {
        "header_file": header_file_output_path,
        "section_file": section_file_output_path
    }


def create_header_file(
    fields: List[Dict],
    pdf_hash: str,
    pdf_category: Dict,
    user_id: int,
    session_id: str,
    pdf_doc_id: int
) -> Dict:
    """
    Create header_file.json for RAG API.
    
    Format:
    {
        "user_id": "user_1",
        "session_id": "session_1",
        "pdf_id": "pdf_1",
        "pdf_hash": "abc123...",
        "timestamp": "2026-02-18T10:00:00Z",
        "pdf_category": {...},
        "fields": [
            {
                "field_id": "field_001",
                "context": "h3 or h4 text based on field type",
                "section_context": "section context from h2",
                "headers": ["h1", "h2", "h3"],
                "bbox": [left, top, right, bottom]
            }
        ]
    }
    """
    import datetime
    
    header_file_fields = []
    
    for field in fields:
        fid = field.get("fid")
        field_name = field.get("field_name", f"field_{fid}")
        field_type = field.get("field_type")
        bbox = field.get("bbox", {})
        hierarchy = field.get("hierarchy", {})
        
        # Extract hierarchy elements
        h1 = hierarchy.get("h1", "")
        h2 = hierarchy.get("h2", "")
        h3 = hierarchy.get("h3", "")
        h4 = hierarchy.get("h4", "")
        section_context = hierarchy.get("section_context", "")
        
        # Determine context based on field type
        # For blank fields (TEXT), use h3
        # For radio/checkbox fields, use h4
        if field_type in ["CHECKBOX", "RADIOBUTTON", "CHECKBOX_FIELD", "RADIOBUTTON_FIELD"]:
            context = h4 if h4 else h3
        else:
            context = h3 if h3 else ""
        
        # Build headers list (in order: h1, h2, h3)
        headers = []
        if h1:
            headers.append(h1)
        if h2:
            headers.append(h2)
        if h3:
            headers.append(h3)
        
        # Format bbox as [left, top, right, bottom] with integers, remove width/height
        bbox_array = [
            int(round(bbox.get("left", 0))),
            int(round(bbox.get("top", 0))),
            int(round(bbox.get("right", 0))),
            int(round(bbox.get("bottom", 0)))
        ]
        
        header_file_fields.append({
            "field_id": field_name,
            "context": context,
            "section_context": section_context,
            "headers": headers,
            "bbox": bbox_array
        })
    
    header_file = {
        "user_id": str(user_id),
        "session_id": session_id,
        "pdf_id": str(pdf_doc_id),
        "pdf_hash": pdf_hash,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "fields": header_file_fields
    }
    
    # Add pdf_category if available
    if pdf_category:
        header_file["pdf_category"] = pdf_category
    
    logger.info(f"Created header_file with {len(header_file_fields)} fields")
    
    return header_file


def create_section_file(
    fields: List[Dict],
    pdf_category: Dict,
    user_id: int,
    session_id: str,
    pdf_doc_id: int
) -> Dict:
    """
    Create section_file.json for RAG API with hierarchical structure.
    
    Format:
    {
        "user_id": "user_1",
        "session_id": "session_1",
        "pdf_id": "pdf_1",
        "pdf_category": {...},
        "sections": [
            {
                "h1": "Page Title",
                "h2_sections": [
                    {
                        "h2": "Section Heading",
                        "section_context": "Section context",
                        "h3_fields": [
                            {
                                "h3": "Field Label",
                                "field_id": "field_001",
                                "h4_options": [
                                    {"h4": "Option 1", "field_id": "field_002"},
                                    {"h4": "Option 2", "field_id": "field_003"}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    """
    import datetime
    from collections import defaultdict
    
    # Build hierarchy structure
    # Group by: h1 -> h2 -> h3 -> h4
    hierarchy_map = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    for field in fields:
        fid = field.get("fid")
        field_name = field.get("field_name", f"field_{fid}")
        hierarchy = field.get("hierarchy", {})
        
        h1 = hierarchy.get("h1", "Unknown Page")
        h2 = hierarchy.get("h2", "Unknown Section")
        h3 = hierarchy.get("h3", "")
        h4 = hierarchy.get("h4", "")
        section_context = hierarchy.get("section_context", "")
        
        # Build key: (h1, h2, section_context, h3)
        h1_key = h1 if h1 else "Unknown Page"
        h2_key = h2 if h2 else "Unknown Section"
        h3_key = h3 if h3 else field_name  # Use field_name as fallback for h3
        
        # Store field info
        field_info = {
            "field_id": field_name,
            "h3": h3_key,
            "h4": h4 if h4 else None,
            "section_context": section_context
        }
        
        hierarchy_map[h1_key][h2_key][h3_key].append(field_info)
    
    # Convert to sections array
    sections = []
    
    for h1, h2_dict in hierarchy_map.items():
        h2_sections = []
        
        for h2, h3_dict in h2_dict.items():
            # Get section_context (should be same for all fields in this h2)
            section_context = ""
            h3_fields = []
            
            for h3, field_list in h3_dict.items():
                # Separate into h3 field and h4 options
                h4_options = []
                h3_field_id = None
                
                for field_info in field_list:
                    if field_info["section_context"]:
                        section_context = field_info["section_context"]
                    
                    if field_info["h4"]:
                        # This is an h4 option
                        h4_options.append({
                            "h4": field_info["h4"],
                            "field_id": field_info["field_id"]
                        })
                    else:
                        # This is the h3 field itself
                        h3_field_id = field_info["field_id"]
                
                # Build h3_field entry
                h3_field_entry = {
                    "h3": h3,
                    "field_id": h3_field_id
                }
                
                if h4_options:
                    h3_field_entry["h4_options"] = h4_options
                
                h3_fields.append(h3_field_entry)
            
            h2_sections.append({
                "h2": h2,
                "section_context": section_context,
                "h3_fields": h3_fields
            })
        
        sections.append({
            "h1": h1,
            "h2_sections": h2_sections
        })
    
    section_file = {
        "user_id": str(user_id),
        "session_id": session_id,
        "pdf_id": str(pdf_doc_id),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "sections": sections
    }
    
    # Add pdf_category if available
    if pdf_category:
        section_file["pdf_category"] = pdf_category
    
    logger.info(f"Created section_file with {len(sections)} top-level sections")
    
    return section_file
