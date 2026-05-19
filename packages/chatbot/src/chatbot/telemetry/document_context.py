# chatbot/telemetry/document_context.py
"""DocumentContext — document taxonomy metadata for telemetry."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DocumentContext:
    """
    Adds category/sub-category/document type to every telemetry event.

    Example::

        DocumentContext(
            category='Private Markets',
            sub_category='Private Equity',
            document_type='LP Subscription Agreement',
            extra={'fund_name': 'Acme Capital Fund III', 'vintage_year': '2024'}
        )
    """
    category: str = ""
    sub_category: str = ""
    document_type: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "sub_category": self.sub_category,
            "document_type": self.document_type,
            **{f"extra_{k}": v for k, v in self.extra.items()},
        }
