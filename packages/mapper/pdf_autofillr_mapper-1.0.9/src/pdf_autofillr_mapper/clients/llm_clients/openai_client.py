import logging
from .response import LLMResponse
import openai

logger = logging.getLogger(__name__)


class OpenAILLMClient:
    """OpenAI client with model-dependent parameter handling."""

    # Models that DO NOT support temperature, top_p, etc.
    REASONING_MODELS = {"o1", "o3", "o3-mini", "o3-mini-high", "o3-mini-low"}
    
    # Models that use the new reasoning API format
    REASONING_API_MODELS = {"gpt-5-mini"}

    def __init__(self, model_id="gpt-4", api_key=None, temperature=0.1, max_tokens=2048):
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=api_key)

        logger.info(f"Initialized OpenAI client with model: {model_id}")

    def _build_params(self):
        """Build safe model parameters based on model capabilities."""
        params = {
            "model": self.model_id,
            "max_completion_tokens": self.max_tokens,
        }

        # Apply temperature ONLY to non-reasoning models
        if self.model_id not in self.REASONING_MODELS:
            params["temperature"] = self.temperature
        else:
            logger.debug(f"Temperature ignored for reasoning model: {self.model_id}")

        return params

    def complete(self, prompt, session_messages=None):
        """
        Complete a prompt using OpenAI.

        Args:
            prompt (str): User prompt
            session_messages (list, optional): Chat history

        Returns:
            LLMResponse: Wrapped response object
        """
        try:
            # Use reasoning API for gpt-5-mini
            if self.model_id in self.REASONING_API_MODELS:
                return self._complete_with_reasoning_api(prompt, session_messages)
            
            # Build message list
            messages = session_messages.copy() if session_messages else []
            messages.append({"role": "user", "content": prompt})

            # Build params safely
            params = self._build_params()
            params["messages"] = messages

            # API call
            response = self.client.chat.completions.create(**params)

            content = response.choices[0].message.content

            # Update session history
            if session_messages is not None:
                session_messages.append({"role": "user", "content": prompt})
                session_messages.append({"role": "assistant", "content": content})

            return LLMResponse(content)

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return LLMResponse("")  # Fail gracefully
    
    def _complete_with_reasoning_api(self, prompt, session_messages=None):
        """
        Complete using OpenAI Reasoning API for gpt-5-mini.
        
        Args:
            prompt (str): User prompt
            session_messages (list, optional): Chat history (system + previous messages)
        
        Returns:
            LLMResponse: Wrapped response object
        """
        try:
            # Build input messages
            input_messages = []
            
            # Add system message if present in session
            if session_messages:
                for msg in session_messages:
                    if msg.get("role") == "system":
                        input_messages.append({
                            "role": "system",
                            "content": msg.get("content", "")
                        })
                        break
            
            # If no system message found, use default
            if not input_messages:
                input_messages.append({
                    "role": "system",
                    "content": "Expert PDF form analyzer. Extract hierarchy with field placeholders. Split multiple fields on same line. Handle tables (H3 columns, H4 cells) and checkboxes/radios (H3 question, H4 options). Return minimal JSON with a single fid per section."
                })
            
            # Add user prompt
            input_messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Call reasoning API
            response = self.client.responses.create(
                model=self.model_id,
                input=input_messages,
                reasoning={"effort": "medium"}
            )
            
            # Extract content from reasoning API response
            # Response structure: response.output is a list with reasoning and message items
            content = None
            
            if hasattr(response, 'output') and isinstance(response.output, list):
                # Iterate through output items to find the message content
                for item in response.output:
                    # Check if this is a message item with content
                    if hasattr(item, 'content') and isinstance(item.content, list):
                        # Extract text from content list
                        for content_item in item.content:
                            if hasattr(content_item, 'text'):
                                content = content_item.text
                                break
                        if content:
                            break
                    # Also check for direct text attribute
                    elif hasattr(item, 'text'):
                        content = item.text
                        break
            
            # Fallback to old format
            if not content:
                if hasattr(response, 'output') and hasattr(response.output, 'content'):
                    content = response.output.content
                elif hasattr(response, 'choices'):
                    content = response.choices[0].message.content
                else:
                    # Last resort: convert to string
                    content = str(response)
                    logger.warning(f"Unexpected response structure: {type(response)}")
            
            # Update session history if provided
            if session_messages is not None:
                session_messages.append({"role": "user", "content": prompt})
                session_messages.append({"role": "assistant", "content": content})
            
            return LLMResponse(content)
            
        except Exception as e:
            logger.error(f"OpenAI Reasoning API call failed: {e}")
            return LLMResponse("")  # Fail gracefully

