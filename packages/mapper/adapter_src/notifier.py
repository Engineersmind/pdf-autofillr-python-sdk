"""
Simple Pipeline Notifier

Wraps HTTP client for easy use in lambda_handler.py
Compatible API with existing http_notifier.py for easy migration.
Supports multiple notification channels: HTTP backend and MS Teams.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum

from .clients.http_client import SimpleHttpClient, create_http_client_from_config
from .clients.teams_client import TeamsClient, create_teams_client_from_config

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Pipeline stages"""
    REFRESH = "refresh"
    EXTRACT = "extract"
    MAP = "map"
    EMBED = "embed"
    FILL = "fill"
    RUN_ALL = "run_all"


class StageStatus(Enum):
    """Stage status"""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class NotificationLevel(Enum):
    """Notification priority"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class PipelineNotifier:
    """
    Simple pipeline notifier that sends events to backend and MS Teams.
    
    Compatible API with src.notifications.http_notifier.HTTPNotifier
    for easy migration from old system.
    
    Supports multiple notification channels:
    - HTTP backend webhook (for API integration)
    - MS Teams webhook (for team notifications)
    """
    
    def __init__(
        self, 
        http_client: Optional[SimpleHttpClient] = None,
        teams_client: Optional[TeamsClient] = None
    ):
        """
        Initialize notifier with HTTP and/or Teams clients
        
        Args:
            http_client: Optional HTTP client for backend notifications
            teams_client: Optional Teams client for Teams notifications
        """
        self.http_client = http_client
        self.teams_client = teams_client
        self._pipeline_id: Optional[str] = None
        self._pipeline_start_time: Optional[float] = None
        self._notification_count = 0
        self._failed_notifications = 0
        
        logger.info("Pipeline notifier initialized")
    
    def start_pipeline(self, pipeline_id: str = None, metadata: Dict[str, Any] = None) -> str:
        """
        Start tracking a new pipeline.
        
        Args:
            pipeline_id: Optional custom pipeline ID
            metadata: Additional pipeline metadata
            
        Returns:
            Pipeline ID
        """
        import uuid
        self._pipeline_id = pipeline_id or f"pipeline_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self._pipeline_start_time = time.time()
        self._notification_count = 0
        self._failed_notifications = 0
        
        logger.info(f"Started pipeline tracking: {self._pipeline_id}")
        return self._pipeline_id
    
    async def notify_stage_completion(
        self,
        stage: PipelineStage,
        status: StageStatus,
        execution_time: Optional[float] = None,
        input_files: Optional[Dict[str, str]] = None,
        output_files: Optional[Dict[str, str]] = None,
        user_input_details: Optional[Dict[str, Any]] = None,
        timing_breakdown: Optional[Dict[str, float]] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        level: NotificationLevel = NotificationLevel.NORMAL
    ) -> bool:
        """
        Send stage completion notification.
        
        Args:
            stage: Pipeline stage
            status: Stage status
            execution_time: Execution time in seconds
            input_files: Input files dict
            output_files: Output files dict
            user_input_details: User input tracking details (user_id, pdf_doc_id, input_json_doc_id)
            timing_breakdown: Timing breakdown dict
            performance_metrics: Performance metrics dict
            error_message: Error message if failed
            metadata: Additional metadata
            level: Notification level
            
        Returns:
            True if successful
        """
        if not self._pipeline_id:
            logger.warning("No active pipeline - call start_pipeline() first")
            return False
        
        # Build payload
        payload = {
            "event_type": "pipeline_stage_completed",
            "pipeline_id": self._pipeline_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage.value,
            "status": status.value,
            "level": level.value
        }
        
        # Add optional fields
        if execution_time is not None:
            payload["execution_time_seconds"] = execution_time
        
        if self._pipeline_start_time:
            elapsed = time.time() - self._pipeline_start_time
            payload["pipeline_elapsed_seconds"] = round(elapsed, 2)
        
        if input_files:
            payload["input_files"] = input_files
        
        if output_files:
            payload["output_files"] = output_files
        
        if user_input_details:
            payload["user_input_details"] = user_input_details
        
        if timing_breakdown:
            payload["timing_breakdown"] = timing_breakdown
        
        if performance_metrics:
            payload["performance_metrics"] = performance_metrics
        
        if error_message:
            payload["error_message"] = error_message
        
        if metadata:
            payload["metadata"] = metadata
        
        # Send notification
        self._notification_count += 1
        
        # Track success for both channels
        http_success = False
        teams_success = False
        
        # Send to HTTP backend
        if self.http_client:
            try:
                response = await self.http_client.send_notification(
                    payload=payload,
                    operation_name=f"{stage.value}_stage"
                )
                
                if response.success:
                    http_success = True
                    logger.info(f"✅ HTTP Stage notification sent: {stage.value} -> {status.value}")
                else:
                    logger.warning(f"❌ HTTP Stage notification failed: {stage.value} -> {status.value}")
                    
            except Exception as e:
                logger.error(f"HTTP Stage notification error: {e}")
        
        # Send to Teams
        if self.teams_client:
            try:
                # Build Teams-specific MessageCard payload
                teams_payload = self._build_teams_stage_card(
                    stage=stage.value,
                    status=status.value,
                    pipeline_id=self._pipeline_id,
                    execution_time=execution_time,
                    output_files=output_files,
                    user_input_details=user_input_details,
                    error_message=error_message
                )
                
                response = await self.teams_client.send_message(
                    payload=teams_payload,
                    operation_name=f"{stage.value}_stage"
                )
                
                if response.success:
                    teams_success = True
                    logger.info(f"✅ Teams Stage notification sent: {stage.value} -> {status.value}")
                else:
                    logger.warning(f"❌ Teams Stage notification failed: {stage.value} -> {status.value}")
                    
            except Exception as e:
                logger.error(f"Teams Stage notification error: {e}")
        
        # Consider success if at least one channel succeeded
        if http_success or teams_success:
            return True
        else:
            self._failed_notifications += 1
            return False
    
    async def notify_pipeline_completion(
        self,
        status: StageStatus,
        total_time: Optional[float] = None,
        final_output: Optional[str] = None,
        stage_breakdown: Optional[Dict[str, float]] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        input_files: Optional[Dict[str, str]] = None,
        output_files: Optional[Dict[str, str]] = None,
        user_input_details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send pipeline completion notification.
        
        Args:
            status: Final pipeline status
            total_time: Total execution time
            final_output: Final output file
            stage_breakdown: Stage timing breakdown
            performance_metrics: Performance metrics
            input_files: Input files dict
            output_files: Output files dict
            user_input_details: User input tracking details (user_id, pdf_doc_id, input_json_doc_id)
            error_message: Error message if failed
            metadata: Additional metadata
            
        Returns:
            True if successful
        """
        if not self._pipeline_id:
            logger.warning("No active pipeline - call start_pipeline() first")
            return False
        
        # Calculate total time
        if total_time is None and self._pipeline_start_time:
            total_time = round(time.time() - self._pipeline_start_time, 2)
        
        # Determine level
        level = NotificationLevel.CRITICAL if status == StageStatus.FAILED else NotificationLevel.HIGH
        
        # Build payload
        payload = {
            "event_type": "pipeline_completed",
            "pipeline_id": self._pipeline_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status.value,
            "level": level.value
        }
        
        # Add optional fields
        if total_time is not None:
            payload["execution_time_seconds"] = total_time
        
        if final_output:
            if not output_files:
                output_files = {}
            output_files["final_output"] = final_output
        
        if input_files:
            payload["input_files"] = input_files
        
        if output_files:
            payload["output_files"] = output_files
        
        if user_input_details:
            payload["user_input_details"] = user_input_details
        
        if stage_breakdown:
            payload["timing_breakdown"] = stage_breakdown
        
        if performance_metrics:
            if not performance_metrics:
                performance_metrics = {}
            performance_metrics.update({
                "total_notifications_sent": self._notification_count,
                "failed_notifications": self._failed_notifications
            })
            payload["performance_metrics"] = performance_metrics
        
        if error_message:
            payload["error_message"] = error_message
        
        if metadata:
            payload["metadata"] = metadata
        
        # Send notification
        self._notification_count += 1
        
        # Track success for both channels
        http_success = False
        teams_success = False
        
        # Send to HTTP backend
        if self.http_client:
            try:
                response = await self.http_client.send_notification(
                    payload=payload,
                    operation_name="pipeline_completion"
                )
                
                if response.success:
                    http_success = True
                    logger.info(f"🎉 HTTP Pipeline completion notification sent: {status.value}")
                else:
                    logger.error(f"💥 HTTP Pipeline completion notification failed: {status.value}")
                    
            except Exception as e:
                logger.error(f"HTTP Pipeline completion notification error: {e}")
        
        # Send to Teams
        if self.teams_client:
            try:
                # Build Teams-specific MessageCard payload
                teams_payload = self._build_teams_pipeline_card(
                    status=status.value,
                    pipeline_id=self._pipeline_id,
                    total_time=total_time,
                    output_files=output_files,
                    user_input_details=user_input_details,
                    stage_breakdown=stage_breakdown,
                    error_message=error_message
                )
                
                response = await self.teams_client.send_message(
                    payload=teams_payload,
                    operation_name="pipeline_completion"
                )
                
                if response.success:
                    teams_success = True
                    logger.info(f"🎉 Teams Pipeline completion notification sent: {status.value}")
                else:
                    logger.error(f"💥 Teams Pipeline completion notification failed: {status.value}")
                    
            except Exception as e:
                logger.error(f"Teams Pipeline completion notification error: {e}")
        
        # Consider success if at least one channel succeeded
        if http_success or teams_success:
            return True
        else:
            self._failed_notifications += 1
            return False
    
    def _build_teams_stage_card(
        self,
        stage: str,
        status: str,
        pipeline_id: str,
        execution_time: Optional[float] = None,
        output_files: Optional[Dict[str, str]] = None,
        user_input_details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build Teams MessageCard for stage completion"""
        icon = "✅" if status == "completed" else "❌"
        color = "28a745" if status == "completed" else "dc3545"
        
        facts = [
            {"title": "Stage", "value": stage.upper()},
            {"title": "Status", "value": status.upper()}
        ]
        
        if execution_time:
            facts.append({"title": "Time", "value": f"{execution_time:.1f}s"})
        
        if user_input_details:
            if user_input_details.get("user_id"):
                facts.append({"title": "User", "value": str(user_input_details["user_id"])})
            if user_input_details.get("session_id"):
                facts.append({"title": "Session", "value": str(user_input_details["session_id"])})
        
        if error_message:
            facts.append({"title": "Error", "value": error_message[:100]})
        
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": f"{stage} {status}",
            "themeColor": color,
            "sections": [{
                "activityTitle": f"{icon} {stage.upper()} Stage {status.title()}",
                "activitySubtitle": f"Pipeline: {pipeline_id}",
                "facts": facts
            }]
        }
    
    def _build_teams_pipeline_card(
        self,
        status: str,
        pipeline_id: str,
        total_time: Optional[float] = None,
        output_files: Optional[Dict[str, str]] = None,
        user_input_details: Optional[Dict[str, Any]] = None,
        stage_breakdown: Optional[Dict[str, float]] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build Teams MessageCard for pipeline completion"""
        icon = "🎉" if status in ["success", "completed"] else "❌"
        color = "28a745" if status in ["success", "completed"] else "dc3545"
        
        facts = [{"title": "Status", "value": status.upper()}]
        
        if total_time:
            facts.append({"title": "Total Time", "value": f"{total_time:.1f}s"})
        
        if user_input_details:
            if user_input_details.get("user_id"):
                facts.append({"title": "User", "value": str(user_input_details["user_id"])})
            if user_input_details.get("session_id"):
                facts.append({"title": "Session", "value": str(user_input_details["session_id"])})
        
        if error_message:
            facts.append({"title": "Error", "value": error_message[:100]})
        
        sections = [{
            "activityTitle": f"{icon} Pipeline {status.title()}",
            "activitySubtitle": f"Pipeline: {pipeline_id}",
            "facts": facts
        }]
        
        # Add stage timing if available
        if stage_breakdown:
            timing_facts = [
                {"title": k.upper(), "value": f"{v:.1f}s"}
                for k, v in stage_breakdown.items()
            ]
            sections.append({
                "activityTitle": "⏱️ Stage Timing",
                "facts": timing_facts
            })
        
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": f"Pipeline {status}",
            "themeColor": color,
            "sections": sections
        }
    
    async def close(self):
        """Close HTTP and Teams clients"""
        if self.http_client:
            await self.http_client.close()
        if self.teams_client:
            await self.teams_client.close()


def create_pipeline_notifier() -> Optional[PipelineNotifier]:
    """
    Create pipeline notifier from environment configuration.
    Supports both HTTP backend and MS Teams notifications.
    
    Returns:
        PipelineNotifier instance or None if all channels disabled
    """
    http_client = create_http_client_from_config()
    teams_client = create_teams_client_from_config()
    
    # Return None if both clients are disabled
    if not http_client and not teams_client:
        logger.info("All notification channels are disabled")
        return None
    
    # Log enabled channels
    enabled_channels = []
    if http_client:
        enabled_channels.append("HTTP Backend")
    if teams_client:
        enabled_channels.append("MS Teams")
    
    logger.info(f"Notification channels enabled: {', '.join(enabled_channels)}")
    
    return PipelineNotifier(http_client=http_client, teams_client=teams_client)

