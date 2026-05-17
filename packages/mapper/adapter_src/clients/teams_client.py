"""
Microsoft Teams HTTP Client

Simple HTTP client for sending messages to MS Teams via incoming webhooks.
Supports both simple text messages and adaptive card payloads.
"""

import asyncio
import aiohttp
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)


@dataclass
class TeamsResponse:
    """Teams webhook response wrapper"""
    success: bool
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    response_time_ms: Optional[int] = None
    retry_count: int = 0


class TeamsClient:
    """Simple HTTP client for MS Teams incoming webhooks"""
    
    def __init__(
        self,
        webhook_url: str,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize Teams client
        
        Args:
            webhook_url: MS Teams incoming webhook URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = None
        
        logger.info(f"Teams client initialized")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=5,
                limit_per_host=3,
                keepalive_timeout=30
            )
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "TeamsClient/1.0"
            }
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers
            )
            
            logger.debug("Created new Teams HTTP session")
        
        return self._session
    
    def _create_retry_decorator(self):
        """Create tenacity retry decorator"""
        return retry(
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
            retry=retry_if_exception_type((
                asyncio.TimeoutError,
                aiohttp.ClientError
            )),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
    
    async def send_message(
        self,
        payload: Dict[str, Any],
        operation_name: str = "teams_message"
    ) -> TeamsResponse:
        """
        Send message to Teams webhook
        
        Args:
            payload: Message payload (MessageCard format or simple dict with 'text' key)
            operation_name: Operation name for logging
            
        Returns:
            TeamsResponse: Response with success status
            
        Example payloads:
            Simple text:
                {"text": "Hello from Teams!"}
            
            MessageCard:
                {
                    "@type": "MessageCard",
                    "@context": "http://schema.org/extensions",
                    "summary": "Summary text",
                    "sections": [{
                        "activityTitle": "Title",
                        "facts": [{"title": "Key", "value": "Value"}]
                    }]
                }
        """
        retry_decorator = self._create_retry_decorator()
        send_with_retry = retry_decorator(self._send_request)
        
        try:
            return await send_with_retry(payload, operation_name)
        except Exception as e:
            logger.error(f"❌ [Teams {operation_name}] All retries exhausted: {str(e)}")
            return TeamsResponse(
                success=False,
                error_message=f"All {self.max_retries + 1} attempts failed: {str(e)}",
                retry_count=self.max_retries
            )
    
    async def _send_request(
        self,
        payload: Dict[str, Any],
        operation_name: str
    ) -> TeamsResponse:
        """
        Send request to Teams webhook
        
        Args:
            payload: JSON payload
            operation_name: Operation name
            
        Returns:
            TeamsResponse
        """
        session = await self._get_session()
        start_time = time.time()
        
        logger.debug(f"[{operation_name}] Sending to Teams webhook")
        
        async with session.post(
            self.webhook_url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as response:
            
            response_time = (time.time() - start_time) * 1000
            
            # Teams webhook returns 200 or 202 on success
            # 200 = OK, 202 = Accepted (async processing)
            if response.status in [200, 202]:
                logger.info(f"✅ [Teams {operation_name}] Sent successfully ({response_time:.0f}ms)")
                
                return TeamsResponse(
                    success=True,
                    status_code=response.status,
                    response_time_ms=int(response_time),
                    retry_count=0
                )
            
            # Handle errors
            else:
                try:
                    error_data = await response.text()
                except:
                    error_data = "Could not read response"
                
                error_message = f"HTTP {response.status}: {error_data[:200]}"
                logger.warning(f"⚠️  [Teams {operation_name}] Error: {error_message}")
                
                # Retry on server errors (5xx)
                if response.status >= 500:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=error_message
                    )
                
                return TeamsResponse(
                    success=False,
                    status_code=response.status,
                    error_message=error_message,
                    response_time_ms=int(response_time),
                    retry_count=0
                )
    
    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Teams HTTP session closed")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


def create_teams_client_from_config() -> Optional[TeamsClient]:
    """
    Create Teams client from pdf_autofillr_mapper.core.config
    
    Returns:
        TeamsClient instance or None if disabled
    """
    try:
        from pdf_autofillr_mapper.core.config import settings
        
        webhook_url = settings.teams_webhook_url
        
        if not webhook_url:
            logger.info("Teams webhook URL not configured - Teams notifications disabled")
            return None
        
        timeout = getattr(settings, 'teams_timeout_seconds', 30)
        max_retries = getattr(settings, 'teams_max_retries', 3)
        
        return TeamsClient(
            webhook_url=webhook_url,
            timeout=timeout,
            max_retries=max_retries
        )
        
    except Exception as e:
        logger.error(f"Failed to create Teams client from config: {e}")
        return None
