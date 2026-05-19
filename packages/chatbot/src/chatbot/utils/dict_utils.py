# chatbot/utils/dict_utils.py
"""flatten_dict, unflatten_dict, deep_update."""
from __future__ import annotations


def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Recursively flatten a nested dict using dot-notation keys."""
    items: dict = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


def unflatten_dict(d: dict, sep: str = ".") -> dict:
    """Reconstruct a nested dict from dot-notation keys."""
    result: dict = {}
    for k, v in d.items():
        keys = k.split(sep)
        ref = result
        for sub in keys[:-1]:
            if sub not in ref:
                ref[sub] = {}
            ref = ref[sub]
        ref[keys[-1]] = v
    return result


def deep_update(base: dict, updates: dict) -> dict:
    """Merge ``updates`` into ``base``, recursively for nested dicts."""
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base
