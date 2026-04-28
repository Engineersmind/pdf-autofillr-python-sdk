"""
Handler Interface - Abstract handler pattern for operations.

Provides a unified interface for handling operations across all modules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime


class OperationStatus(Enum):
    """Status of an operation."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PARTIAL_SUCCESS = "partial_success"


@dataclass
class HandlerRequest:
    """
    Standard request format for handlers.
    
    All handlers should accept this request format for consistency.
    """
    
    # Operation details
    operation: str  # Operation type: extract, map, embed, fill, etc.
    session_id: Optional[str] = None  # Session ID for tracking
    
    # File/resource paths
    pdf_path: Optional[str] = None
    input_path: Optional[str] = None
    output_path: Optional[str] = None
    
    # Operation-specific data
    data: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None
    
    # Metadata
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None
    
    # Options
    async_mode: bool = False
    callback_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation": self.operation,
            "session_id": self.session_id,
            "pdf_path": self.pdf_path,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "data": self.data,
            "params": self.params,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
            "async_mode": self.async_mode,
            "callback_url": self.callback_url,
        }


@dataclass
class HandlerResponse:
    """
    Standard response format for handlers.
    
    All handlers should return this response format for consistency.
    """
    
    # Status
    status: OperationStatus
    success: bool  # Convenience flag
    
    # Results
    data: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    
    # Error information
    error: Optional[str] = None
    error_type: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    # Metadata
    operation: Optional[str] = None
    session_id: Optional[str] = None
    duration_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Additional info
    warnings: List[str] = field(default_factory=list)
    info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "success": self.success,
            "data": self.data,
            "result": self.result,
            "error": self.error,
            "error_type": self.error_type,
            "error_details": self.error_details,
            "operation": self.operation,
            "session_id": self.session_id,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "warnings": self.warnings,
            "info": self.info,
        }
    
    @classmethod
    def success_response(
        cls,
        data: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> "HandlerResponse":
        """Create a success response."""
        return cls(
            status=OperationStatus.SUCCESS,
            success=True,
            data=data,
            operation=operation,
            session_id=session_id,
            **kwargs
        )
    
    @classmethod
    def error_response(
        cls,
        error: str,
        error_type: Optional[str] = None,
        operation: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> "HandlerResponse":
        """Create an error response."""
        return cls(
            status=OperationStatus.FAILURE,
            success=False,
            error=error,
            error_type=error_type,
            operation=operation,
            session_id=session_id,
            **kwargs
        )


class HandlerInterface(ABC):
    """
    Abstract interface for operation handlers.
    
    All operation handlers should implement this interface for consistency.
    """
    
    @abstractmethod
    def handle(self, request: HandlerRequest) -> HandlerResponse:
        """
        Handle an operation request.
        
        Args:
            request: Handler request
            
        Returns:
            Handler response
        """
        pass
    
    @abstractmethod
    def validate_request(self, request: HandlerRequest) -> bool:
        """
        Validate a request before processing.
        
        Args:
            request: Handler request
            
        Returns:
            True if valid, False otherwise
            
        Raises:
            ValueError: If request is invalid
        """
        pass
    
    def supports_operation(self, operation: str) -> bool:
        """
        Check if handler supports an operation.
        
        Args:
            operation: Operation type
            
        Returns:
            True if supported, False otherwise
        """
        return False


# =============================================================================
# Base Handler Implementation
# =============================================================================

class BaseHandler(HandlerInterface):
    """
    Base handler with common functionality.
    
    Modules can extend this class for consistent behavior.
    """
    
    def __init__(self):
        """Initialize handler."""
        self.supported_operations: List[str] = []
    
    def handle(self, request: HandlerRequest) -> HandlerResponse:
        """
        Handle request with common pre/post processing.
        
        Args:
            request: Handler request
            
        Returns:
            Handler response
        """
        import time
        
        start_time = time.time()
        
        try:
            # Validate request
            self.validate_request(request)
            
            # Process request (implemented by subclass)
            response = self.process(request)
            
            # Add timing information
            duration_ms = (time.time() - start_time) * 1000
            response.duration_ms = duration_ms
            response.operation = request.operation
            response.session_id = request.session_id
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            return HandlerResponse.error_response(
                error=str(e),
                error_type=type(e).__name__,
                operation=request.operation,
                session_id=request.session_id,
                duration_ms=duration_ms
            )
    
    @abstractmethod
    def process(self, request: HandlerRequest) -> HandlerResponse:
        """
        Process the request (must be implemented by subclass).
        
        Args:
            request: Handler request
            
        Returns:
            Handler response
        """
        pass
    
    def validate_request(self, request: HandlerRequest) -> bool:
        """
        Basic validation (can be overridden).
        
        Args:
            request: Handler request
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If request is invalid
        """
        if not request.operation:
            raise ValueError("Operation is required")
        
        if not self.supports_operation(request.operation):
            raise ValueError(f"Unsupported operation: {request.operation}")
        
        return True
    
    def supports_operation(self, operation: str) -> bool:
        """
        Check if operation is supported.
        
        Args:
            operation: Operation type
            
        Returns:
            True if supported
        """
        return operation in self.supported_operations
