"""

Output File Handler - Saves files to source storage as soon as they're created.



This handler detects the source type (local/aws/azure/gcp) and automatically

uploads files to the appropriate destination immediately after creation.



Usage in operations:

    from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

    

    handler = OutputFileHandler(config)

    

    # After creating a file:

    local_path = "/tmp/processing/file.json"

    handler.save_output(local_path, 'extracted_json')

"""



import os
import time
import logging

import shutil

from typing import Optional

from pathlib import Path



logger = logging.getLogger(__name__)



class OutputFileHandler:

    """

    Handles saving output files to source storage based on source type.

    

    For local storage: copies to output directory

    For AWS: uploads to S3

    For Azure: uploads to Blob Storage

    For GCP: uploads to Cloud Storage

    """

    

    def __init__(self, config):

        """

        Initialize output handler.

        

        Args:

            config: Storage config (LocalStorageConfig, AWSStorageConfig, etc.)

        """

        self.config = config

        self.source_type = config.source_type

        logger.info(f"OutputFileHandler initialized for source_type: {self.source_type}")

    

    def save_output(

        self, 

        local_path: str, 

        file_type: str,

        destination_path: Optional[str] = None

    ) -> str:

        """

        Save output file to source storage immediately.

        

        Args:

            local_path: Path to file in /tmp/processing/

            file_type: Type of file (e.g., 'extracted_json', 'mapped_json', 'embedded_pdf')

            destination_path: Optional explicit destination path (overrides auto-detection)

        

        Returns:

            Path in source storage where file was saved

        

        Example:

            # Local storage:

            handler.save_output('/tmp/processing/553_990_extracted.json', 'extracted_json')

            # Copies to: ../../data/output/553_990_extracted.json

            

            # AWS storage:

            handler.save_output('/tmp/553_990_extracted.json', 'extracted_json')

            # Uploads to: s3://bucket/path/553_990_extracted.json

        """

        if not os.path.exists(local_path):

            logger.warning(f"File does not exist, skipping save: {local_path}")

            return None

        

        # Determine destination path

        if destination_path:

            dest_path = destination_path

        else:

            dest_path = self._get_destination_path(file_type)

        

        if not dest_path:

            logger.warning(f"No destination path configured for {file_type}, skipping save")

            return None

        

        # Save based on source type

        if self.source_type == 'local':

            return self._save_local(local_path, dest_path)

        elif self.source_type == 'aws':

            return self._save_aws(local_path, dest_path)

        elif self.source_type == 'azure':

            return self._save_azure(local_path, dest_path)

        elif self.source_type == 'gcp':

            return self._save_gcp(local_path, dest_path)

        else:

            logger.error(f"Unknown source type: {self.source_type}")

            return None

    

    def _get_destination_path(self, file_type: str) -> Optional[str]:

        """

        Get destination path from config based on file type.

        

        Maps file_type to config attributes:

            Local:

                - extracted_json -> config.dest_extracted_json

                - mapped_json -> config.dest_mapped_json

            AWS:

                - extracted_json -> config.s3_extracted_json

                - mapped_json -> config.s3_mapped_json

            Azure:

                - extracted_json -> config.blob_extracted_json

            GCP:

                - extracted_json -> config.gcs_extracted_json

        """

        # Build attribute name based on source type

        if self.source_type == 'local':

            # Local uses dest_ prefix (destination paths in source storage)

            attr_name = f'dest_{file_type}'

        elif self.source_type == 'aws':

            attr_name = f's3_{file_type}'

        elif self.source_type == 'azure':

            attr_name = f'blob_{file_type}'

        elif self.source_type == 'gcp':

            attr_name = f'gcs_{file_type}'

        else:

            return None

        

        # Get path from config

        dest_path = getattr(self.config, attr_name, None)

        

        if not dest_path:

            logger.debug(f"No destination path found in config.{attr_name}")

        

        return dest_path

    

    def _save_local(self, local_path: str, dest_path: str) -> str:

        """

        Save to local file system (copy file).

        Retries on PermissionError to handle Windows file locking — on Windows,

        the Java filler holds the file handle briefly after writing, causing a

        WinError 32 if we copy immediately. Retrying releases the lock.

        

        Example:

            /tmp/processing/file.json -> ../../data/output/file.json

        """

        try:

            # Create destination directory if needed

            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Skip copy if source and destination are the same file (avoids WinError 32 self-lock)
            if os.path.abspath(local_path) == os.path.abspath(dest_path):
                logger.info(f"✅ Same file, skipping copy: {local_path}")
                return dest_path

            # Retry loop — handles Windows file locking (WinError 32)
            # Java holds the handle briefly after writing; wait for release.
            # max_attempts = 10
            # for attempt in range(max_attempts):
            #     try:
            #         shutil.copy2(local_path, dest_path)
            #         break
            #     except PermissionError:
            #         if attempt >= max_attempts - 1:
            #             raise
            #         logger.debug(
            #             f"File locked (attempt {attempt + 1}/{max_attempts}), "
            #             f"retrying in 0.5s: {local_path}"
            #         )
            #         time.sleep(0.5)

            max_attempts = 50
            for attempt in range(max_attempts):
                try:
                    shutil.copy2(local_path, dest_path)
                    break
                except PermissionError:
                    if attempt >= max_attempts - 1:
                        raise
                    logger.debug(
                        f"File locked (attempt {attempt + 1}/{max_attempts}), "
                        f"retrying in 1s: {local_path}"
                    )
                    time.sleep(1)

            logger.info(f"✅ Saved to local: {local_path} -> {dest_path}")

            return dest_path

        

        except Exception as e:

            logger.error(f"Failed to save local file: {e}", exc_info=True)

            return None

    

    def _save_aws(self, local_path: str, dest_path: str) -> str:

        """

        Save to AWS S3 (upload file).

        

        Example:

            /tmp/file.json -> s3://bucket/path/file.json

        """

        try:

            # Use config's upload method

            self.config.upload_file(local_path, dest_path)

            

            logger.info(f"✅ Uploaded to S3: {local_path} -> {dest_path}")

            return dest_path

        

        except Exception as e:

            logger.error(f"Failed to upload to S3: {e}", exc_info=True)

            return None

    

    def _save_azure(self, local_path: str, dest_path: str) -> str:

        """

        Save to Azure Blob Storage (upload file).

        

        Example:

            /tmp/file.json -> azure://container/path/file.json

        """

        try:

            # Use config's upload method

            self.config.upload_file(local_path, dest_path)

            

            logger.info(f"✅ Uploaded to Azure: {local_path} -> {dest_path}")

            return dest_path

        

        except Exception as e:

            logger.error(f"Failed to upload to Azure: {e}", exc_info=True)

            return None

    

    def _save_gcp(self, local_path: str, dest_path: str) -> str:

        """

        Save to GCP Cloud Storage (upload file).

        

        Example:

            /tmp/file.json -> gs://bucket/path/file.json

        """

        try:

            # Use config's upload method

            self.config.upload_file(local_path, dest_path)

            

            logger.info(f"✅ Uploaded to GCS: {local_path} -> {dest_path}")

            return dest_path

        

        except Exception as e:

            logger.error(f"Failed to upload to GCS: {e}", exc_info=True)

            return None

    

    def save_multiple_outputs(self, file_mappings: dict) -> dict:

        """

        Save multiple output files at once.

        

        Args:

            file_mappings: Dict mapping file_type to local_path

                {

                    'extracted_json': '/tmp/processing/file_extracted.json',

                    'mapped_json': '/tmp/processing/file_mapped.json',

                    'embedded_pdf': '/tmp/processing/file_embedded.pdf'

                }

        

        Returns:

            Dict mapping file_type to destination_path

        """

        results = {}

        

        for file_type, local_path in file_mappings.items():

            dest_path = self.save_output(local_path, file_type)

            if dest_path:

                results[file_type] = dest_path

        

        return results



def create_output_handler(config):

    """

    Factory function to create OutputFileHandler from config.

    

    Args:

        config: Storage config (LocalStorageConfig, AWSStorageConfig, etc.)

    

    Returns:

        OutputFileHandler instance

    """

    return OutputFileHandler(config)