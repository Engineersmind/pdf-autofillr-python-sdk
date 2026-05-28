"""
PromptRenderer - Jinja2-based template renderer for LLM prompts.

Uses non-standard delimiters (<< >>, <% %>) to avoid conflicts with
JSON curly braces and {fid} / {variable} placeholders that appear
literally inside prompt text.

Usage:
    from pdf_autofillr_mapper.prompts.renderer import render

    prompt = render('semantic/mapping_prompt.j2',
                    context_text=...,
                    investor_type=...,
                    ...)
"""

import json
import logging
from pathlib import Path
from typing import Optional

import jinja2

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_PROMPTS_DIR)),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
    variable_start_string="<<",
    variable_end_string=">>",
    block_start_string="<%",
    block_end_string="%>",
    comment_start_string="<#",
    comment_end_string="#>",
    keep_trailing_newline=True,
    undefined=jinja2.StrictUndefined,
)

# Allow json.dumps with optional indent inside templates:
#   << my_dict | tojson >>          → compact JSON
#   << my_dict | tojson(indent=2) >> → pretty JSON
_env.filters["tojson"] = lambda v, indent=None: json.dumps(v, indent=indent)


_CACHE_SPLIT_MARKER = "##CACHE_SPLIT##"


def _is_claude(model: str) -> bool:
    """Return True for any Anthropic/Bedrock Claude model."""
    m = model.lower()
    return "claude" in m or "anthropic" in m


def render(template_path: str, **kwargs) -> str:
    """
    Render a prompt template.

    Args:
        template_path: Path relative to pdf_autofillr_mapper/prompts/
                       e.g. 'semantic/mapping_prompt.j2'
        **kwargs:      Variables to inject into the template.

    Returns:
        Rendered prompt string.
    """
    template = _env.get_template(template_path)
    return template.render(**kwargs)


def build_messages(model: str, prompt: str, system: Optional[str] = None) -> list:
    """
    Build an LLM messages list, adding cache_control blocks for Claude.

    For Claude (Anthropic direct or Bedrock):
      - System message (if given) gets cache_control so it is cached once.
      - User prompt is split at ##CACHE_SPLIT## into a cached static block
        and an uncached dynamic block.

    For OpenAI / all other models:
      - Returns plain string content — OpenAI auto-caches identical prefixes
        ≥ 1024 tokens with no extra configuration needed.
      - cache_control is NOT added; if the model somehow receives it,
        litellm.drop_params=True silently removes it anyway.

    If ##CACHE_SPLIT## is absent the full prompt is sent as a single message
    (graceful fallback — no errors, full functionality preserved).
    """
    msgs = []

    if system:
        if _is_claude(model):
            msgs.append(
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            )
        else:
            msgs.append({"role": "system", "content": system})

    if _is_claude(model) and _CACHE_SPLIT_MARKER in prompt:
        static, dynamic = prompt.split(_CACHE_SPLIT_MARKER, 1)
        msgs.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": static.rstrip(),
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": dynamic.lstrip()},
                ],
            }
        )
    else:
        # OpenAI (auto-caches prefix) or any model without cache support
        # Strip the marker so it doesn't appear in the sent prompt
        msgs.append(
            {"role": "user", "content": prompt.replace(_CACHE_SPLIT_MARKER, "")}
        )

    return msgs
