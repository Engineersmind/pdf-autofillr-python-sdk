"""
HTTP Client for Pipeline Notifications

Simple HTTP client with tenacity retry logic and exponential backoff.
Reads configuration from pdf_autofillr_mapper.core.config.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


@dataclass
class HttpResponse:
    """HTTP response wrapper with timing and metadata"""

    success: bool
    status_code: Optional[int] = None
    response_data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    response_time_ms: Optional[int] = None
    retry_count: int = 0


class SimpleHttpClient:
    """Simple HTTP client for pipeline notifications with tenacity retry"""

    def __init__(
        self, backend_url: str, auth_key: str, timeout: int = 30, max_retries: int = 3
    ):
        """
        Initialize HTTP client

        Args:
            backend_url: Backend notification URL
            auth_key: Authentication key for x-event-key header
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.backend_url = backend_url
        self.auth_key = auth_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(f"HTTP client initialized for: {backend_url}")

    async def _get_session(self) -> Optional[aiohttp.ClientSession]:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
            )

            timeout = aiohttp.ClientTimeout(total=self.timeout)

            # Build headers with x-event-key authentication
            headers = {
                "Content-Type": "application/json",
                "x-event-key": self.auth_key,
                "User-Agent": "PDF-Pipeline-Notifier/1.0",
            }

            self._session = aiohttp.ClientSession(
                connector=connector, timeout=timeout, headers=headers
            )

            logger.debug("Created new HTTP session")

        return self._session

    def _create_retry_decorator(self):
        """Create tenacity retry decorator with exponential backoff"""
        return retry(
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
            retry=retry_if_exception_type((asyncio.TimeoutError, aiohttp.ClientError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

    async def send_notification(
        self, payload: dict[str, Any], operation_name: str = "notification"
    ) -> HttpResponse:
        """
        Send notification to backend with tenacity retry logic

        Args:
            payload: JSON payload to send
            operation_name: Operation name for logging

        Returns:
            HttpResponse: Response with success status and metadata
        """
        # Create retry wrapper for the actual send method
        retry_decorator = self._create_retry_decorator()
        send_with_retry = retry_decorator(self._send_request)

        try:
            return await send_with_retry(payload, operation_name)
        except Exception as e:
            logger.error(f"❌ [{operation_name}] All retries exhausted: {str(e)}")
            return HttpResponse(
                success=False,
                error_message=f"All {self.max_retries + 1} attempts failed: {str(e)}",
                retry_count=self.max_retries,
            )

    async def _send_request(
        self, payload: dict[str, Any], operation_name: str
    ) -> HttpResponse:
        """
        Internal method to send single request (called by tenacity)

        Args:
            payload: JSON payload
            operation_name: Operation name for logging

        Returns:
            HttpResponse: Response with success status
        """
        session = await self._get_session()
        assert session is not None
        start_time = time.time()

        logger.debug(f"[{operation_name}] Sending to {self.backend_url}")

        async with session.post(
            self.backend_url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        ) as response:

            response_time = (time.time() - start_time) * 1000

            # Handle successful responses (2xx)
            if 200 <= response.status < 300:
                try:
                    response_data = await response.json()
                except Exception:
                    response_data = {"status": "ok"}

                logger.info(
                    f"✅ [{operation_name}] HTTP {response.status} ({response_time:.0f}ms)"
                )

                return HttpResponse(
                    success=True,
                    status_code=response.status,
                    response_data=response_data,
                    response_time_ms=int(response_time),
                    retry_count=0,
                )

            # Handle client errors (4xx) - don't retry
            elif 400 <= response.status < 500:
                try:
                    error_data = await response.text()
                except Exception:
                    error_data = "Could not read response"

                error_message = f"HTTP {response.status}: {error_data[:200]}"
                logger.error(f"❌ [{operation_name}] Client error: {error_message}")

                return HttpResponse(
                    success=False,
                    status_code=response.status,
                    error_message=error_message,
                    response_time_ms=int(response_time),
                    retry_count=0,
                )

            # Handle server errors (5xx) - tenacity will retry
            else:
                try:
                    error_data = await response.text()
                except Exception:
                    error_data = "Could not read response"

                error_message = f"HTTP {response.status}: {error_data[:200]}"
                logger.warning(
                    f"⚠️  [{operation_name}] Server error: {error_message} - will retry"
                )

                # Raise exception so tenacity retries
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=error_message,
                )

    async def close(self):
        """Close HTTP session and cleanup resources"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("HTTP session closed")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# Factory function to create client from pdf_autofillr_mapper.core.config
def create_http_client_from_config() -> Optional[SimpleHttpClient]:
    """
    Create HTTP client from pdf_autofillr_mapper.core.config

    Returns:
        SimpleHttpClient instance or None if disabled
    """
    try:
        from pdf_autofillr_mapper.core.config import get_notification_config

        config = get_notification_config()

        if not config.get("enabled", True):
            logger.info("Notifications are disabled")
            return None

        backend_url = config.get("backend_url")
        auth_key = config.get("api_token") or config.get("api_key")

        if not backend_url:
            logger.warning("backend_url not set - notifications disabled")
            return None

        if not auth_key:
            logger.warning("api_token not set - using empty auth key")
            auth_key = ""

        timeout = config.get("timeout_seconds", 30)
        max_retries = config.get("max_retries", 3)

        return SimpleHttpClient(
            backend_url=backend_url,
            auth_key=auth_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    except Exception as e:
        logger.error(f"Failed to create HTTP client from config: {e}")
        return None
