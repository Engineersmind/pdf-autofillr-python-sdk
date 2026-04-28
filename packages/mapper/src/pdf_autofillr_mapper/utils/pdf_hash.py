import json
import hashlib
import re
from pathlib import Path


def normalize_text(text):
    """Normalize text to handle minor formatting differences"""
    if not text:
        return ""
    # Convert to lowercase
    text = text.lower()
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    # Remove special characters
    text = re.sub(r'[^\w\s]', '', text)
    return text


def normalize_bbox(bbox, page_width, page_height):
    """Normalize bounding box coordinates to 3 decimal places"""
    return {
        'left': round(bbox['left'] / page_width, 3),
        'top': round(bbox['top'] / page_height, 3),
        'width': round(bbox['width'] / page_width, 3),
        'height': round(bbox['height'] / page_height, 3)
    }


def create_bbox_hash(fields, page_width, page_height):
    """Create hash of normalized bounding boxes"""
    if not fields:
        return ""
    
    # Normalize and sort boxes by position (top to bottom, left to right)
    normalized_boxes = []
    for field in fields:
        norm_bbox = normalize_bbox(field['bbox'], page_width, page_height)
        normalized_boxes.append((norm_bbox['top'], norm_bbox['left'], norm_bbox))
    
    # Sort by top, then left
    normalized_boxes.sort()
    
    # Create stable string representation
    boxes_str = json.dumps([box[2] for box in normalized_boxes], sort_keys=True)
    
    # Hash it
    return hashlib.sha256(boxes_str.encode('utf-8')).hexdigest()


def get_spatial_clusters(fields, page_height):
    """Cluster fields by vertical position (top/middle/bottom thirds)"""
    clusters = {'top': 0, 'middle': 0, 'bottom': 0}
    
    for field in fields:
        # Use center point of field
        center_y = field['bbox']['top'] + (field['bbox']['height'] / 2)
        third = center_y / page_height
        
        if third < 0.33:
            clusters['top'] += 1
        elif third < 0.67:
            clusters['middle'] += 1
        else:
            clusters['bottom'] += 1
    
    return clusters


def extract_page_text(page):
    """Extract and concatenate all text elements from a page"""
    text_parts = []
    for elem in page.get('text_elements', []):
        text_parts.append(elem['text'])
    return ' '.join(text_parts)


def get_text_lines(text):
    """Split text into lines and return first, middle, last"""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return "", "", ""
    
    first = lines[0]
    last = lines[-1]
    middle = lines[len(lines) // 2] if len(lines) > 1 else ""
    
    return first, middle, last


def create_pdf_fingerprint(data):
    """
    Create structural fingerprint from extracted PDF JSON data
    
    Args:
        data: Dictionary containing PDF extraction data (not file path)
        
    Returns:
        tuple: (fingerprint_dict, final_hash_string)
    """
    # Data is already loaded as dict
    pages = data['pages']
    num_pages = len(pages)
    page_width = data.get('page_width', pages[0].get('page_width'))
    page_height = data.get('page_height', pages[0].get('page_height'))
    
    # Initialize fingerprint structure
    fingerprint = {
        'num_pages': num_pages,
        'page_dimensions': {
            'width': round(page_width, 1),
            'height': round(page_height, 1)
        },
        'form_fields': {
            'total_count': 0,
            'by_type': {},
            'per_page_distribution': {},
            'bounding_boxes_hash': {},
            'spatial_clusters': {}
        },
        'first_two_pages': {},
        'quartile_pages': {}
    }
    
    # Process each page for form fields
    for page in pages:
        page_num = page['page_number']
        fields = page.get('form_fields', [])
        
        # Count fields
        fingerprint['form_fields']['total_count'] += len(fields)
        
        # Count by type
        page_type_count = {}
        for field in fields:
            field_type = field.get('field_type', 'UNKNOWN')
            fingerprint['form_fields']['by_type'][field_type] = \
                fingerprint['form_fields']['by_type'].get(field_type, 0) + 1
            page_type_count[field_type] = page_type_count.get(field_type, 0) + 1
        
        # Per-page distribution
        if page_type_count:
            fingerprint['form_fields']['per_page_distribution'][page_num] = page_type_count
        
        # Bounding boxes hash
        if fields:
            fingerprint['form_fields']['bounding_boxes_hash'][page_num] = \
                create_bbox_hash(fields, page_width, page_height)
            
            # Spatial clusters
            fingerprint['form_fields']['spatial_clusters'][page_num] = \
                get_spatial_clusters(fields, page_height)
    
    # Extract text from first two pages
    for i in range(min(2, num_pages)):
        page = pages[i]
        page_num = page['page_number']
        full_text = extract_page_text(page)
        normalized = normalize_text(full_text)
        
        fingerprint['first_two_pages'][page_num] = {
            'text_normalized': normalized,
            'word_count': len(normalized.split()),
            'line_count': len([line for line in full_text.split('\n') if line.strip()]),
            'char_count': len(normalized)
        }
    
    # Quartile page sampling
    if num_pages >= 3:
        quartile_positions = [
            int(num_pages * 0.25),  # Q1
            int(num_pages * 0.50),  # Q2 (median)
            int(num_pages * 0.75)   # Q3
        ]
        quartile_names = ['q1', 'q2', 'q3']
        
        for q_name, q_pos in zip(quartile_names, quartile_positions):
            if q_pos < num_pages:
                page = pages[q_pos]
                page_num = page['page_number']
                full_text = extract_page_text(page)
                first, middle, last = get_text_lines(full_text)
                
                fingerprint['quartile_pages'][q_name] = {
                    'page_num': page_num,
                    'first_line': normalize_text(first),
                    'middle_line': normalize_text(middle),
                    'last_line': normalize_text(last),
                    'char_count': len(normalize_text(full_text))
                }
    
    # Create final hash
    fingerprint_json = json.dumps(fingerprint, sort_keys=True)
    final_hash = hashlib.sha256(fingerprint_json.encode('utf-8')).hexdigest()
    
    return fingerprint, final_hash


def main():
    """Main function to create PDF fingerprint from file (CLI usage)"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_json>")
        print("Example: python script.py extracted_pdf.json")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    # Validate input file
    if not Path(json_path).exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)
    
    print(f"Processing: {json_path}")
    
    # Load JSON data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Create fingerprint (now accepts dict, not path)
    fingerprint, final_hash = create_pdf_fingerprint(data)
    
    # Save fingerprint to file
    output_path = Path(json_path).stem + '_fingerprint.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(fingerprint, f, indent=2)
    
    print(f"\n✓ Fingerprint saved to: {output_path}")
    print(f"\n✓ Final Hash: {final_hash}")
    print(f"\nFingerprint Summary:")
    print(f"  - Pages: {fingerprint['num_pages']}")
    print(f"  - Total Fields: {fingerprint['form_fields']['total_count']}")
    print(f"  - Field Types: {list(fingerprint['form_fields']['by_type'].keys())}")
    
    return final_hash


if __name__ == "__main__":
    main()
