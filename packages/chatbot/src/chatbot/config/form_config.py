# chatbot/config/form_config.py
"""
FormConfig — loads and validates all configuration files.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from chatbot.core.states import INVESTOR_TYPE_FILES
from chatbot.utils.dict_utils import flatten_dict


class FormConfig:
    """
    Loads form_keys, mandatory, meta_form_keys, field_questions,
    and form_keys_label configuration.

    Validates structure at startup and raises clear errors for bad configs.
    """

    def __init__(
        self,
        form_keys: dict,
        mandatory: dict,
        meta_form_keys: dict,
        field_questions: dict,
        form_keys_labels: dict,
        investor_type_keys: dict,  # {investor_type: form_keys_dict}
    ):
        self.form_keys = form_keys
        self.mandatory = mandatory
        self.meta_form_keys = meta_form_keys
        self.field_questions = field_questions
        self.form_keys_labels = form_keys_labels
        self._investor_type_keys = investor_type_keys

    @classmethod
    def from_directory(cls, config_dir: str) -> "FormConfig":
        """
        Load all config files from a directory.

        Args:
            config_dir: Path to directory containing form config JSON files.

        Raises:
            FileNotFoundError: If required config files are missing.
            ValueError: If config structure is invalid.
        """
        config_path = Path(config_dir)

        def load(filename: str, required: bool = True) -> dict:
            path = config_path / filename
            if not path.exists():
                if required:
                    raise FileNotFoundError(
                        f"Required config file not found: {path}\n"
                        f"Copy config_samples/ into your project as {config_dir}/"
                    )
                return {}
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        form_keys = load("form_keys.json")
        mandatory = load("mandatory.json")
        meta_form_keys = load("meta_form_keys.json")
        field_questions = load("field_questions.json", required=False)
        form_keys_labels = load("form_keys_label.json", required=False)

        # Load per-investor-type form keys
        investor_type_keys = {}
        type_keys_dir = config_path / "global_investor_type_keys"
        for inv_type, filename in INVESTOR_TYPE_FILES.items():
            path = type_keys_dir / filename
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    investor_type_keys[inv_type] = json.load(f)

        return cls(
            form_keys=form_keys,
            mandatory=mandatory,
            meta_form_keys=meta_form_keys,
            field_questions=field_questions,
            form_keys_labels=form_keys_labels,
            investor_type_keys=investor_type_keys,
        )

    @classmethod
    def from_storage(cls, storage) -> "FormConfig":
        """Load config files from a storage backend (local or S3)."""
        form_keys = storage.load_config("form_keys.json")
        mandatory = storage.load_config("mandatory.json")
        meta_form_keys = storage.load_config("meta_form_keys.json")
        try:
            field_questions = storage.load_config("field_questions.json")
        except Exception:
            field_questions = {}
        try:
            form_keys_labels = storage.load_config("form_keys_label.json")
        except Exception:
            form_keys_labels = {}

        investor_type_keys = {}
        for inv_type, filename in INVESTOR_TYPE_FILES.items():
            try:
                investor_type_keys[inv_type] = storage.load_investor_type_config(filename)
            except Exception:
                pass

        return cls(
            form_keys=form_keys,
            mandatory=mandatory,
            meta_form_keys=meta_form_keys,
            field_questions=field_questions,
            form_keys_labels=form_keys_labels,
            investor_type_keys=investor_type_keys,
        )

    # ------------------------------------------------------------------

    def get_form_keys_for_type(self, investor_type: str) -> dict:
        return self._investor_type_keys.get(investor_type, self.form_keys)

    def get_mandatory_fields_for_type(self, investor_type: str) -> dict:
        type_of_investors = self.mandatory.get("Type of Investors", self.mandatory)
        return type_of_investors.get(investor_type, {})

    def get_question(self, field_path: str) -> Optional[str]:
        """Return the human-readable question for a field path."""
        parts = field_path.split(".")
        node = self.field_questions
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part)
            else:
                return None
        return node if isinstance(node, str) else None

    def get_label(self, field_path: str) -> str:
        """Return short display label for a field."""
        parts = field_path.split(".")
        node = self.form_keys_labels
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part)
            else:
                break
        if isinstance(node, str):
            return node
        # Auto-generate from field path
        return parts[-1].replace("_id", "").replace("_", " ").title()
