import boto3
import logging
from typing import Tuple
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

class S3Client:
    """S3 client for handling PDF and JSON operations in Lambda environment."""
    
    def __init__(self, region_name: str = None, profile_name: str = None):
        """Initialize S3 client with optional region and profile.
        
        Args:
            region_name: AWS region name (e.g., 'us-east-1')
            profile_name: AWS profile name from ~/.aws/credentials (e.g., 'default', 'raghava.revi')
        """
        try:
            if profile_name:
                session = boto3.Session(profile_name=profile_name)
                self.s3_client = session.client('s3', region_name=region_name)
                logger.info(f"S3 client initialized with profile '{profile_name}' successfully")
            else:
                self.s3_client = boto3.client('s3', region_name=region_name)
                logger.info("S3 client initialized successfully")
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            raise

    def parse_s3_path(self, s3_path: str) -> Tuple[str, str]:
        """Parse S3 path into bucket and key components.
        
        Args:
            s3_path: Full S3 path (e.g., 's3://bucket-name/path/to/file.pdf')
            
        Returns:
            Tuple of (bucket, key)
            
        Raises:
            ValueError: If s3_path is not in correct format
        """
        if not s3_path.startswith('s3://'):
            raise ValueError(f"Invalid S3 path format: {s3_path}. Must start with 's3://'")
        
        # Remove 's3://' prefix and split on first '/'
        path_without_prefix = s3_path[5:]  # Remove 's3://'
        if '/' not in path_without_prefix:
            raise ValueError(f"Invalid S3 path format: {s3_path}. Must include bucket and key")
        
        bucket, key = path_without_prefix.split('/', 1)
        
        if not bucket or not key:
            raise ValueError(f"Invalid S3 path format: {s3_path}. Both bucket and key must be specified")
        
        return bucket, key

    def read_pdf_from_s3(self, s3_path: str) -> bytes:
        """Read PDF file from S3 and return as bytes.
        
        Args:
            s3_path: Full S3 path to PDF file (e.g., 's3://bucket-name/path/to/file.pdf')
            
        Returns:
            PDF file content as bytes
            
        Raises:
            ClientError: If S3 operation fails
            ValueError: If s3_path format is invalid
        """
        try:
            bucket, key = self.parse_s3_path(s3_path)
            logger.info(f"Reading PDF from S3: bucket={bucket}, key={key}")
            
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            pdf_bytes = response['Body'].read()
            
            logger.info(f"Successfully read PDF from S3: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"PDF file not found in S3: {s3_path}")
                raise FileNotFoundError(f"PDF file not found in S3: {s3_path}")
            elif error_code == 'NoSuchBucket':
                logger.error(f"S3 bucket not found: {bucket}")
                raise FileNotFoundError(f"S3 bucket not found: {bucket}")
            else:
                logger.error(f"S3 error reading PDF: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error reading PDF from S3: {str(e)}")
            raise

    def load_json_from_s3(self, s3_path: str) -> dict:
        """Load JSON data from S3.
        
        Args:
            s3_path: Full S3 path to JSON file (e.g., 's3://bucket-name/path/to/file.json')
            
        Returns:
            Dictionary loaded from JSON file
            
        Raises:
            ClientError: If S3 operation fails
            ValueError: If s3_path format is invalid or JSON is invalid
            FileNotFoundError: If file doesn't exist
        """
        import json
        
        try:
            bucket, key = self.parse_s3_path(s3_path)
            logger.info(f"Loading JSON from S3: bucket={bucket}, key={key}")
            
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            json_content = response['Body'].read().decode('utf-8')
            
            data = json.loads(json_content)
            logger.info(f"Successfully loaded JSON from S3: {s3_path}")
            return data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"JSON file not found in S3: {s3_path}")
                raise FileNotFoundError(f"JSON file not found in S3: {s3_path}")
            elif error_code == 'NoSuchBucket':
                logger.error(f"S3 bucket not found: {bucket}")
                raise FileNotFoundError(f"S3 bucket not found: {bucket}")
            else:
                logger.error(f"S3 error loading JSON: {str(e)}")
                raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON content in S3 file {s3_path}: {str(e)}")
            raise ValueError(f"Invalid JSON content in S3 file {s3_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error loading JSON from S3: {str(e)}")
            raise

    def save_json_to_s3(self, data: dict, s3_path: str) -> bool:
        """Save JSON data to S3.
        
        Args:
            data: Dictionary to save as JSON
            s3_path: Full S3 path where to save the JSON file
            
        Returns:
            True if successful
            
        Raises:
            ClientError: If S3 operation fails
            ValueError: If s3_path format is invalid
        """
        import json
        
        try:
            bucket, key = self.parse_s3_path(s3_path)
            logger.info(f"Saving JSON to S3: bucket={bucket}, key={key}")
            
            json_string = json.dumps(data, indent=2, ensure_ascii=False)
            
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json_string.encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.info(f"Successfully saved JSON to S3: {s3_path}")
            return True
            
        except ClientError as e:
            logger.error(f"S3 error saving JSON: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving JSON to S3: {str(e)}")
            raise

    def download_file_from_s3(self, s3_path: str, local_path: str = None) -> str:
        """Download file from S3 to local filesystem.
        
        Args:
            s3_path: Full S3 path to the file (e.g., 's3://bucket-name/path/to/file.pdf')
            local_path: Local path where to save the file. If None, saves to /tmp/ with original filename
            
        Returns:
            Local path where the file was saved
            
        Raises:
            ClientError: If S3 operation fails
            ValueError: If s3_path format is invalid
            FileNotFoundError: If S3 file doesn't exist
        """
        import os
        
        try:
            bucket, key = self.parse_s3_path(s3_path)
            
            # Generate local path if not provided (default to /tmp for Lambda)
            if local_path is None:
                filename = os.path.basename(key)
                local_path = f"/tmp/{filename}"
            
            # Ensure directory exists
            local_dir = os.path.dirname(local_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
            
            logger.info(f"Downloading file from S3: bucket={bucket}, key={key} -> {local_path}")
            
            # Check if file exists first to provide better error messages
            try:
                self.s3_client.head_object(Bucket=bucket, Key=key)
            except ClientError as head_error:
                if head_error.response['Error']['Code'] == '404':
                    logger.error(f"File not found in S3: {s3_path}")
                    raise FileNotFoundError(f"S3 file does not exist: {s3_path}")
                elif head_error.response['Error']['Code'] == 'NoSuchBucket':
                    logger.error(f"S3 bucket not found: {bucket}")
                    raise FileNotFoundError(f"S3 bucket does not exist: {bucket}")
                else:
                    raise head_error
            
            # Download the file
            self.s3_client.download_file(bucket, key, local_path)
            
            # Verify the file was downloaded
            if not os.path.exists(local_path):
                raise RuntimeError(f"File download completed but file not found at: {local_path}")
            
            file_size = os.path.getsize(local_path)
            logger.info(f"Successfully downloaded file from S3: {local_path} ({file_size} bytes)")
            return local_path
            
        except FileNotFoundError:
            # Re-raise FileNotFoundError as-is (already has clear message)
            raise
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['NoSuchKey', '404']:
                logger.error(f"File not found in S3: {s3_path}")
                raise FileNotFoundError(f"S3 file does not exist: {s3_path}")
            elif error_code == 'NoSuchBucket':
                logger.error(f"S3 bucket not found: {bucket}")
                raise FileNotFoundError(f"S3 bucket does not exist: {bucket}")
            else:
                logger.error(f"S3 error downloading file: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error downloading file from S3: {str(e)}")
            raise

    def upload_file_to_s3(self, local_path: str, s3_path: str) -> bool:
        """Upload local file to S3.
        
        Args:
            local_path: Path to local file to upload
            s3_path: Full S3 path where to save the file (e.g., 's3://bucket-name/path/to/file.pdf')
            
        Returns:
            True if successful
            
        Raises:
            ClientError: If S3 operation fails
            ValueError: If s3_path format is invalid
            FileNotFoundError: If local file doesn't exist
        """
        import os
        
        try:
            # Verify local file exists
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local file not found: {local_path}")
            
            bucket, key = self.parse_s3_path(s3_path)
            
            logger.info(f"Uploading file to S3: {local_path} -> bucket={bucket}, key={key}")
            
            # Upload the file
            self.s3_client.upload_file(local_path, bucket, key)
            
            logger.info(f"Successfully uploaded file to S3: {s3_path}")
            return True
            
        except ClientError as e:
            logger.error(f"S3 error uploading file: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading file to S3: {str(e)}")
            raise

    def object_exists(self, s3_path: str) -> bool:
        """Check if an object exists in S3.
        
        Args:
            s3_path: Full S3 path to check
            
        Returns:
            True if object exists, False otherwise
        """
        try:
            bucket, key = self.parse_s3_path(s3_path)
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

    def list_bucket_objects(self, bucket_name: str, prefix: str = "") -> list:
        """List objects in S3 bucket with optional prefix.
        
        Args:
            bucket_name: Name of the S3 bucket
            prefix: Optional prefix to filter objects
            
        Returns:
            List of object keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=20  # Limit for debugging
            )
            
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            else:
                return []
                
        except ClientError as e:
            logger.error(f"Error listing bucket objects: {str(e)}")
            raise

    def check_bucket_access(self, bucket_name: str) -> dict:
        """Check if we can access the bucket and get basic info.
        
        Args:
            bucket_name: Name of the S3 bucket
            
        Returns:
            Dictionary with access info
        """
        try:
            # Try to list objects (limited)
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                MaxKeys=1
            )
            
            return {
                "accessible": True,
                "bucket_exists": True,
                "can_list": True,
                "object_count": response.get('KeyCount', 0)
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            return {
                "accessible": False,
                "bucket_exists": error_code != 'NoSuchBucket',
                "can_list": False,
                "error": error_code,
                "message": str(e)
            }

    def generate_presigned_url(self, s3_path: str, expires_in: int = 3600, inline: bool = True) -> str:
        """
        Generate a presigned URL for viewing an S3 object in the browser (inline preview).

        Args:
            s3_path: Full S3 path to the object (e.g., 's3://bucket/key')
            expires_in: Expiration time in seconds for the presigned URL
            inline: If True, sets Content-Disposition to inline for browser viewing

        Returns:
            A presigned URL string valid for the specified duration

        Raises:
            ValueError: If s3_path is not a valid S3 URI
            ClientError: If generating the presigned URL fails
        """
        if not s3_path.startswith('s3://'):
            raise ValueError(f"Cannot generate presigned URL for non-S3 path: {s3_path}")

        try:
            bucket, key = self.parse_s3_path(s3_path)
            params = {'Bucket': bucket, 'Key': key}
            if inline:
                params['ResponseContentDisposition'] = 'inline'
                params['ResponseContentType'] = 'application/pdf'
            return self.s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params=params,
                ExpiresIn=expires_in
            )
        except ClientError:
            logger.exception(f"Failed to generate presigned URL for {s3_path}")
            raise
        except Exception:
            logger.exception(f"Unexpected error generating presigned URL for {s3_path}")
            raise
    def copy_object(self, source_s3_path: str, target_s3_path: str) -> bool:
        """
        Copy an S3 object from source to target using server-side copy.
        This is much faster than downloading and re-uploading as it happens within AWS.

        Args:
            source_s3_path: Full S3 path to source object (e.g., 's3://bucket/source/file.pdf')
            target_s3_path: Full S3 path to target location (e.g., 's3://bucket/target/file.pdf')

        Returns:
            True if copy was successful

        Raises:
            ValueError: If paths are not valid S3 URIs
            ClientError: If S3 copy operation fails
        """
        if not source_s3_path.startswith('s3://'):
            raise ValueError(f"Source path must be an S3 URI: {source_s3_path}")
        
        if not target_s3_path.startswith('s3://'):
            raise ValueError(f"Target path must be an S3 URI: {target_s3_path}")

        try:
            source_bucket, source_key = self.parse_s3_path(source_s3_path)
            target_bucket, target_key = self.parse_s3_path(target_s3_path)
            
            copy_source = {'Bucket': source_bucket, 'Key': source_key}
            
            logger.info(f"Copying S3 object: {source_s3_path} -> {target_s3_path}")
            
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=target_bucket,
                Key=target_key
            )
            
            logger.info(f"Successfully copied S3 object to {target_s3_path}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"Source object not found: {source_s3_path}")
                raise FileNotFoundError(f"Source object not found: {source_s3_path}")
            elif error_code == 'NoSuchBucket':
                logger.error(f"Bucket not found in copy operation")
                raise FileNotFoundError(f"Bucket not found during copy operation")
            else:
                logger.error(f"S3 copy error: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error copying S3 object: {str(e)}")
            raise
