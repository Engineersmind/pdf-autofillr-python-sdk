import os
import subprocess


import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def refresh_with_java(
    input_pdf: str,
    storage_config: dict = None
):
    """
    Refreshes PDF form using Java utility.
    
    Args:
        input_pdf (str): Path to the input PDF file to refresh
        storage_config (dict): Storage configuration for output
        
    Returns:
        str: Path to the refreshed PDF
        
    Raises:
        FileNotFoundError: If any required input file is missing
        RuntimeError: If Java refresh process fails
    """
    logger.info("[🧩] Starting PDF form refresh with Java utility...")

    # Generate output path by adding _refreshed suffix to input PDF
    # If input is S3 path, create local temp output path
    if input_pdf.startswith("s3://") or "/tmp/" in input_pdf:
        # For S3 or temp files, create output in /tmp/
        base_name = os.path.splitext(os.path.basename(input_pdf))[0]
        refreshed_pdf = f"/tmp/{base_name}_refreshed.pdf"
    else:
        # For local files, create output in same directory
        base_name = os.path.splitext(input_pdf)[0]
        refreshed_pdf = f"{base_name}_refreshed.pdf"
    
    # JAR file path - check multiple locations in order of preference
    possible_jar_paths = [
        "refresher.jar",                       # Root directory (RECOMMENDED)
        "assets/refresher.jar",                # Assets directory in root
        "src/assets/refresher.jar",            # Assets in src directory
        "/opt/refresher.jar",                  # Lambda layer location
        os.path.join(os.getcwd(), "refresher.jar"),  # Current working directory
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "refresher.jar")  # Relative to this module
    ]
    
    jar_path = None
    for path in possible_jar_paths:
        if os.path.exists(path):
            jar_path = path
            logger.info(f"[📦] Found Java refresher at: {jar_path}")
            break
    
    if not jar_path:
        logger.error(f"[❌] Java refresher JAR not found in any of these locations: {possible_jar_paths}")
        raise FileNotFoundError(f"Java refresher JAR not found. Expected locations: {possible_jar_paths}")
    
    # Validate input file exists
    if not os.path.exists(input_pdf):
        logger.error(f"[❌] Missing required file for Java refresh: {input_pdf}")
        raise FileNotFoundError(f"Missing required file: {input_pdf}")

    # Build command for Java subprocess
    cmd = [
        "java", "-jar", jar_path,
        input_pdf,
        refreshed_pdf
    ]
    
    logger.info(f"[🔧] Running Java command: {' '.join(cmd)}")

    try:
        # Execute Java subprocess
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True,
            timeout=300  # 5 minute timeout
        )
        
        # Log successful execution
        if result.stdout:
            logger.info(f"[📝] Java output: {result.stdout.strip()}")
            
        # Verify output file was created
        if not os.path.exists(refreshed_pdf):
            raise RuntimeError(f"Java process completed but output file not found: {refreshed_pdf}")
            
        logger.info(f"[✅] Java refresh completed successfully. Output: {refreshed_pdf}")
        return refreshed_pdf
        
    except subprocess.TimeoutExpired as e:
        logger.error("[❌] Java refresh process timed out after 5 minutes")
        raise RuntimeError("Java refresh process timed out") from e
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else "Unknown Java error"
        logger.error(f"[❌] Java refresh failed: {error_msg}")
        
        # Log stdout for additional context
        if e.stdout:
            logger.error(f"[📝] Java stdout: {e.stdout.strip()}")
            
        raise RuntimeError(f"Java refresh step failed: {error_msg}") from e
        
    except Exception as e:
        logger.error(f"[❌] Unexpected error during Java refresh: {str(e)}")
        raise RuntimeError(f"Unexpected error in Java refresh: {str(e)}") from e
