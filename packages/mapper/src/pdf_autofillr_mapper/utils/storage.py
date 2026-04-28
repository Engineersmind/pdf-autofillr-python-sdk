import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

def save_json(data: Dict[Any, Any], storage_config: Dict[str, Any]) -> bool:
    """Save JSON data to local file system.
    
    Args:
        data: Dictionary to save as JSON
        storage_config: Configuration dict with storage details
            - Format: {"type": "local", "path": "/local/path/file.json"}
            
    Returns:
        True if successful
        
    Raises:
        ValueError: If storage_config is invalid
        Exception: If storage operation fails
    """
    if not storage_config or "type" not in storage_config or "path" not in storage_config:
        raise ValueError("storage_config must contain 'type' and 'path' keys")
    
    storage_type = storage_config["type"].lower()
    storage_path = storage_config["path"]
    
    if storage_type != "local":
        raise ValueError(f"Only 'local' storage type is supported. Got: {storage_type}")
    
    logger.info(f"Saving JSON to local storage: {storage_path}")
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        
        with open(storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully saved JSON locally: {storage_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save JSON locally: {str(e)}")
        raise