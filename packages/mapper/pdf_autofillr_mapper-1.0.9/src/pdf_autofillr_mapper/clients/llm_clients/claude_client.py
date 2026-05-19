import json
import boto3
from botocore.config import Config
import logging
from .response import LLMResponse

logger = logging.getLogger(__name__)


class ClaudeLLMClient:
    """Clean Claude client using AWS Bedrock"""
    
    def __init__(self, model_id="anthropic.claude-3-sonnet-20240229-v1:0", 
                 region="us-east-1", temperature=0.1, max_tokens=20000):
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize Bedrock client
        config = Config(region_name=region, read_timeout=300, connect_timeout=60)
        self.bedrock = boto3.client("bedrock-runtime", config=config)
        
        logger.info(f"Initialized Claude client with model: {model_id}")

    def complete(self, prompt, session_messages=None):
        """
        Complete a prompt using Claude via Bedrock
        
        Args:
            prompt (str): The user prompt
            session_messages (list, optional): Previous conversation messages
            
        Returns:
            LLMResponse: Object with .text attribute containing the response
        """
        try:
            # Build messages array
            if session_messages:
                messages = session_messages + [{"role": "user", "content": prompt}]
            else:
                messages = [{"role": "user", "content": prompt}]

            # Prepare request body
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }

            # Call Bedrock
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body)
            )

            # Parse response
            result = json.loads(response['body'].read())
            content = result["content"][0]["text"]

            # Update session messages if provided
            if session_messages is not None:
                session_messages.append({"role": "user", "content": prompt})
                session_messages.append({"role": "assistant", "content": content})

            return LLMResponse(content)

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return LLMResponse("")  # Return empty response instead of None