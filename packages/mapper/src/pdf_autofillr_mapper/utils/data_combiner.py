"""
Utility for combining user profile and session data
"""
import json
import logging
from typing import Dict, Any
from pdf_autofillr_mapper.clients.s3_client import S3Client
from pdf_autofillr_mapper.core.config import settings

logger = logging.getLogger(__name__)


async def combine_user_and_session_data(
    user_id: int,
    session_id: int,
    use_profile_info: bool = True
) -> str:
    """
    Combine user profile information with session data.
    
    Creates a combined JSON file with user information first (if use_profile_info=True),
    followed by session data (only keys not already present).
    
    Args:
        user_id: User ID
        session_id: Session ID
        use_profile_info: Whether to include user profile info (default: True)
        
    Returns:
        S3 path to the combined JSON file
        
    File structure:
        - User info: s3://{bucket}/user_id/user_information_flat.json
        - Session data: s3://{bucket}/user_id/session_id/final_output_flat.json
        - Combined output: s3://{bucket}/user_id/session_id/final_combined_output_flat.json
    """
    bucket = settings.s3_input_data_bucket
    if not bucket:
        raise ValueError("S3_INPUT_DATA_BUCKET environment variable not configured")
    
    # Construct S3 paths
    user_info_path = f"s3://{bucket}/{user_id}/user_information_flat.json"
    session_data_path = f"s3://{bucket}/{user_id}/sessions/{session_id}/final_output_flat.json"
    combined_output_path = f"s3://{bucket}/{user_id}/sessions/{session_id}/final_combined_output_flat.json"
    
    logger.info(f"Combining data for user_id={user_id}, session_id={session_id}")
    logger.info(f"User info path: {user_info_path}")
    logger.info(f"Session data path: {session_data_path}")
    logger.info(f"Output path: {combined_output_path}")
    
    s3_client = S3Client()
    
    try:
        # Load session data (always required)
        logger.info("Loading session data...")
        session_data = s3_client.load_json_from_s3(session_data_path)
        logger.info(f"Session data loaded: {len(session_data)} keys")
        
        if use_profile_info:
            # Load user profile information
            logger.info("Loading user profile information...")
            try:
                user_info = s3_client.load_json_from_s3(user_info_path)
                logger.info(f"User profile loaded: {len(user_info)} keys")
            except FileNotFoundError:
                logger.warning(f"User profile not found at {user_info_path}, using session data only")
                user_info = {}
            
            # Combine: user_info first, then session_data for remaining keys
            combined_data = {}
            
            # Add all user info first
            for key, value in user_info.items():
                combined_data[key] = value
            
            # Add session data for keys not already present
            added_from_session = 0
            for key, value in session_data.items():
                if key not in combined_data:
                    combined_data[key] = value
                    added_from_session += 1
            
            logger.info(f"Combined data created:")
            logger.info(f"  - Keys from user profile: {len(user_info)}")
            logger.info(f"  - Keys from session data: {added_from_session}")
            logger.info(f"  - Total keys: {len(combined_data)}")
            
        else:
            # Use session data only
            combined_data = session_data
            logger.info("Using session data only (use_profile_info=False)")
        
        # Save combined data to S3
        logger.info(f"Saving combined data to: {combined_output_path}")
        s3_client.save_json_to_s3(combined_data, combined_output_path)
        logger.info("✅ Combined data saved successfully")
        
        return combined_output_path
        
    except FileNotFoundError as e:
        logger.error(f"Required file not found: {str(e)}")
        raise RuntimeError(f"Failed to load required data files: {str(e)}") from e
    except Exception as e:
        logger.error(f"Error combining user and session data: {str(e)}")
        raise RuntimeError(f"Data combination failed: {str(e)}") from e


def get_user_info_path(user_id: int) -> str:
    """Get S3 path for user information file"""
    bucket = settings.s3_input_data_bucket
    if not bucket:
        raise ValueError("S3_INPUT_DATA_BUCKET environment variable not configured")
    return f"s3://{bucket}/{user_id}/user_information_flat.json"


def get_session_data_path(user_id: int, session_id: int) -> str:
    """Get S3 path for session data file"""
    bucket = settings.s3_input_data_bucket
    if not bucket:
        raise ValueError("S3_INPUT_DATA_BUCKET environment variable not configured")
    return f"s3://{bucket}/{user_id}/sessions/{session_id}/final_output_flat.json"


def get_combined_output_path(user_id: int, session_id: int) -> str:
    """Get S3 path for combined output file"""
    bucket = settings.s3_input_data_bucket
    if not bucket:
        raise ValueError("S3_INPUT_DATA_BUCKET environment variable not configured")
    return f"s3://{bucket}/{user_id}/sessions/{session_id}/final_combined_output_flat.json"
