from typing import Any, Optional


async def fill_with_java_safe(
    embedded_pdf: str, input_json: str, storage_config: Optional[dict[Any, Any]] = None
):
    """
    Wrapper for fill_with_java that checks if the embedded PDF exists before filling.
    If the embedded file is missing, returns a response indicating the missing file.
    Always returns a dict with status and pdf_file_path (filled or missing).
    """
    if not os.path.exists(embedded_pdf):
        logger.error(f"[❌] Embedded PDF file not found: {embedded_pdf}")
        return {
            "status": "error",
            "error": f"Embedded PDF file not found: {embedded_pdf}",
            "pdf_file_path": None,
        }
    try:
        filled_pdf = await fill_with_java(embedded_pdf, input_json, storage_config)
        return {"status": "success", "pdf_file_path": filled_pdf}
    except Exception as e:
        logger.error(f"[❌] Fill operation failed: {str(e)}")
        return {"status": "error", "error": str(e), "pdf_file_path": None}


import logging  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fill_with_java(
    embedded_pdf: str, input_json: str, storage_config: Optional[dict[Any, Any]] = None
):
    """
    Fills PDF form using Java Itext utility.

    Args:
        embedded_pdf (str): Path to the embedded PDF file (output from embed operation)
        input_json (str): Path to the input JSON file with form data
        storage_config (dict): Storage configuration for output

    Returns:
        str: Path to the filled PDF

    Raises:
        FileNotFoundError: If any required input file is missing
        RuntimeError: If Java filling process fails
    """
    logger.info("[🧩] Starting PDF form filling with Java Itext utility...")

    # Generate output path by adding _filled suffix to embedded PDF
    if "/tmp/" in embedded_pdf:
        # For temp files, create output in /tmp/
        base_name = os.path.splitext(os.path.basename(embedded_pdf))[0]
        filled_pdf = f"/tmp/{base_name}_filled.pdf"
    else:
        # For local files, create output in same directory
        base_name = os.path.splitext(embedded_pdf)[0]
        filled_pdf = f"{base_name}_filled.pdf"

    # JAR file path - check multiple locations in order of preference
    # Also check the path bundled inside the installed pdf_autofillr_mapper package
    possible_jar_paths = [
        # os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "java_utils", "form_field_filler", "target", "form_field_filler-1.0.0-jar-with-dependencies.jar"),  # Bundled in wheel
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "java_utils",
            "form_field_filler",
            "target",
            "form_field_filler-1.0.0-jar-with-dependencies.jar",
        ),  # Bundled in wheel
        "filler.jar",  # Root directory (RECOMMENDED)
        "assets/filler.jar",  # Assets directory in root
        "src/assets/filler.jar",  # Assets in src directory
        "/opt/filler.jar",  # Lambda layer location
        os.path.join(os.getcwd(), "filler.jar"),  # Current working directory
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "filler.jar"
        ),  # Relative to this module
    ]

    jar_path = None
    for path in possible_jar_paths:
        if os.path.exists(path):
            jar_path = path
            logger.info(f"[📦] Found Java filler at: {jar_path}")
            break

    if not jar_path:
        logger.error(
            f"[❌] Java filler JAR not found in any of these locations: {possible_jar_paths}"
        )
        raise FileNotFoundError(
            f"Java filler JAR not found. Expected locations: {possible_jar_paths}"
        )

    # Validate all required input files exist
    required_files = {"embedded_pdf": embedded_pdf, "input_json": input_json}

    for file_type, file_path in required_files.items():
        if not os.path.exists(file_path):
            logger.error(f"[❌] Missing required file for Java filling: {file_path}")
            raise FileNotFoundError(f"Missing required file ({file_type}): {file_path}")

    # Build command for Java subprocess
    cmd = ["java", "-jar", jar_path, embedded_pdf, input_json, filled_pdf]

    logger.info(f"[🔧] Running Java command: {' '.join(cmd)}")

    try:
        # Execute Java subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,  # 5 minute timeout
        )

        # Log successful execution
        if result.stdout:
            logger.info(f"[📝] Java output: {result.stdout.strip()}")

        # Verify output file was created
        if not os.path.exists(filled_pdf):
            raise RuntimeError(
                f"Java process completed but output file not found: {filled_pdf}"
            )

        logger.info(f"[✅] Java filling completed successfully. Output: {filled_pdf}")
        return filled_pdf

    except subprocess.TimeoutExpired as e:
        logger.error("[❌] Java filling process timed out after 5 minutes")
        raise RuntimeError("Java filling process timed out") from e

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else "Unknown Java error"
        logger.error(f"[❌] Java filling failed: {error_msg}")

        # Log stdout for additional context
        if e.stdout:
            logger.error(f"[📝] Java stdout: {e.stdout.strip()}")

        raise RuntimeError(f"Java filling step failed: {error_msg}") from e

    except Exception as e:
        logger.error(f"[❌] Unexpected error during Java filling: {str(e)}")
        raise RuntimeError(f"Unexpected error in Java filling: {str(e)}") from e
