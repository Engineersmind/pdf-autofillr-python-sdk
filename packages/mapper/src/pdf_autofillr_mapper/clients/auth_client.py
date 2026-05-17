"""
Authentication client for backend API login
"""
import aiohttp
import logging
from typing import Optional
from pdf_autofillr_mapper.core.config import settings

logger = logging.getLogger(__name__)


class AuthClient:
    """Client for authenticating with the backend API"""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize auth client
        
        Args:
            base_url: Base API URL (defaults to settings.auth_api_base_url)
            email: User email (defaults to settings.auth_email)
            password: User password (defaults to settings.auth_password)
            timeout: Request timeout in seconds (defaults to settings.auth_timeout_seconds)
        """
        base = base_url or settings.auth_api_base_url
        self.api_url = f"{base.rstrip('/')}/auth/login"
        self.email = email or settings.auth_email
        self.password = password or settings.auth_password
        self.timeout = timeout or settings.auth_timeout_seconds
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
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
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Auth client HTTP session closed")
    
    async def get_token(self) -> str:
        """
        Get authentication token
        
        Returns:
            JWT access token
            
        Raises:
            ValueError: If credentials are not configured
            RuntimeError: If authentication fails
        """
        # Validate credentials
        if not self.email or not self.password:
            raise ValueError(
                "Authentication credentials not configured. "
                "Set AUTH_EMAIL and AUTH_PASSWORD environment variables."
            )
        
        if not self.api_url:
            raise ValueError(
                "Authentication API URL not configured. "
                "Set AUTH_API_URL environment variable."
            )
        
        await self._ensure_session()
        
        # Prepare login payload
        payload = {
            "email": self.email,
            "password": self.password
        }
        
        try:
            logger.debug(f"Authenticating with API: {self.api_url}")
            
            async with self._session.post(
                self.api_url,
                json=payload,
                headers={
                    "accept": "*/*",
                    "Content-Type": "application/json"
                }
            ) as response:
                response_text = await response.text()
                
                # Accept both 200 and 201 status codes
                if response.status not in (200, 201):
                    logger.error(
                        f"Authentication failed: HTTP {response.status} - {response_text}"
                    )
                    raise RuntimeError(
                        f"Authentication failed with status {response.status}: {response_text}"
                    )
                
                response_data = await response.json()
                
                # Extract access token from response['data']['access_token']
                access_token = None
                if "data" in response_data and isinstance(response_data["data"], dict):
                    access_token = response_data["data"].get("access_token")
                if not access_token:
                    logger.error(f"No access_token in response: {response_data}")
                    raise RuntimeError("Authentication response missing access_token")
                logger.info("✅ Authentication successful, token obtained")
                return access_token
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error during authentication: {str(e)}")
            raise RuntimeError(f"Authentication request failed: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {str(e)}")
            raise RuntimeError(f"Authentication failed: {str(e)}") from e
    
    async def login(self) -> dict:
        """
        Login and get full authentication response
        
        Returns:
            Full authentication response dictionary
            
        Raises:
            ValueError: If credentials are not configured
            RuntimeError: If authentication fails
        """
        # Validate credentials
        if not self.email or not self.password:
            raise ValueError(
                "Authentication credentials not configured. "
                "Set AUTH_EMAIL and AUTH_PASSWORD environment variables."
            )
        
        if not self.api_url:
            raise ValueError(
                "Authentication API URL not configured. "
                "Set AUTH_API_URL environment variable."
            )
        
        await self._ensure_session()
        
        # Prepare login payload
        payload = {
            "email": self.email,
            "password": self.password
        }
        
        try:
            logger.debug(f"Logging in to API: {self.api_url}")
            
            async with self._session.post(
                self.api_url,
                json=payload,
                headers={
                    "accept": "*/*",
                    "Content-Type": "application/json"
                }
            ) as response:
                response_text = await response.text()
                
                # Accept both 200 and 201 status codes
                if response.status not in (200, 201):
                    logger.error(
                        f"Login failed: HTTP {response.status} - {response_text}"
                    )
                    raise RuntimeError(
                        f"Login failed with status {response.status}: {response_text}"
                    )
                
                response_data = await response.json()
                
                logger.info("✅ Login successful")
                
                return response_data
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error during login: {str(e)}")
            raise RuntimeError(f"Login request failed: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}")
            raise RuntimeError(f"Login failed: {str(e)}") from e
    
    def get_auth_header(self, token: str) -> dict:
        """
        Get authorization header with Bearer token
        
        Args:
            token: JWT token
            
        Returns:
            Dictionary with Authorization header
        """
        return {
            "Authorization": f"Bearer {token}"
        }
