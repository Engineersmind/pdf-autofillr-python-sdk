"""
API client for backend API operations
"""
import aiohttp
import logging
from typing import Optional
from pdf_autofillr_mapper.core.config import settings
from pdf_autofillr_mapper.clients.auth_client import AuthClient

logger = logging.getLogger(__name__)


class APIClient:
    """Client for backend API operations"""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_client: Optional[AuthClient] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize API client
        
        Args:
            base_url: Base URL for API (defaults to settings.auth_api_base_url)
            auth_client: AuthClient instance (optional, will create if not provided)
            timeout: Request timeout in seconds (defaults to settings.auth_timeout_seconds)
        """
        self.base_url = (base_url or settings.auth_api_base_url).rstrip('/')
        self.auth_client = auth_client
        self.timeout = timeout or settings.auth_timeout_seconds
        self._session: Optional[aiohttp.ClientSession] = None
        self._token: Optional[str] = None
        self._own_auth_client = auth_client is None  # Track if we created the auth client
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        # Create auth client if not provided
        if self.auth_client is None:
            self.auth_client = AuthClient()
            await self.auth_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure HTTP session exists"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close HTTP session and auth client"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("API client HTTP session closed")
        
        # Close auth client if we created it
        if self._own_auth_client and self.auth_client:
            await self.auth_client.close()
    
    async def _ensure_token(self):
        """Ensure we have a valid authentication token"""
        if self._token is None:
            if self.auth_client is None:
                raise RuntimeError("Auth client not initialized. Use async context manager.")
            self._token = await self.auth_client.get_token()
    
    async def get_document_s3_url(self, doc_id: int, is_presigned: bool = False) -> str:
        """
        Get S3 URL for a document by its ID
        
        Args:
            doc_id: Document ID
            is_presigned: Whether to get presigned URL (default: False)
            
        Returns:
            S3 URL as string (s3:// format)
            
        Raises:
            ValueError: If doc_id is invalid
            RuntimeError: If API request fails
        """
        if not doc_id or doc_id <= 0:
            raise ValueError("doc_id must be a positive integer")
        
        await self._ensure_session()
        await self._ensure_token()
        
        # Construct API URL
        api_url = f"{self.base_url}/docs/id/{doc_id}/url"
        
        try:
            logger.debug(f"Fetching document URL for doc_id: {doc_id}")
            
            async with self._session.get(
                api_url,
                params={"is_presigned": str(is_presigned).lower()},
                headers={
                    "accept": "*/*",
                    "Authorization": f"Bearer {self._token}"
                }
            ) as response:
                response_text = await response.text()
                
                if response.status not in (200, 201):
                    logger.error(
                        f"Failed to get document URL: HTTP {response.status} - {response_text}"
                    )
                    raise RuntimeError(
                        f"Failed to get document URL with status {response.status}: {response_text}"
                    )
                
                response_data = await response.json()
                
                # Log full response for debugging
                logger.info(f"API Response for doc_id {doc_id}: {response_data}")

                # Extract s3_key and s3_url from response_data['data']
                data = response_data.get("data", {})
                s3_key = data.get("s3_key")
                if not s3_key:
                    logger.error(f"No s3_key in response: {response_data}")
                    raise RuntimeError("Response missing s3_key")

                s3_url = data.get("s3_url", "")
                logger.info(f"s3_url from API: {s3_url}")

                if s3_url and ".s3." in s3_url:
                    # Parse bucket name from https://bucket.s3.region.amazonaws.com/key
                    bucket_name = s3_url.split("//")[1].split(".s3.")[0]
                    logger.info(f"Parsed bucket name: {bucket_name}")
                else:
                    # Default bucket if not found
                    bucket_name = "pdf-autofiller-dev"
                    logger.warning(f"Could not parse bucket from s3_url, using default: {bucket_name}")

                # Construct S3 URI (s3://bucket/key format)
                s3_uri = f"s3://{bucket_name}/{s3_key}"

                logger.info(f"✅ Document URL retrieved: {s3_uri}")
                logger.info(f"   File name: {data.get('file_name', 'N/A')}")
                logger.info(f"   S3 key: {s3_key}")
                logger.info(f"   Bucket: {bucket_name}")

                return s3_uri
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error while getting document URL: {str(e)}")
            raise RuntimeError(f"Document URL request failed: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error while getting document URL: {str(e)}")
            raise RuntimeError(f"Failed to get document URL: {str(e)}") from e
