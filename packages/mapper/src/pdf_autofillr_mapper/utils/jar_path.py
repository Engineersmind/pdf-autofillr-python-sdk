"""
JAR path resolution utility.

Single source of truth for locating the three Java JARs used by the mapper:
  - rebuilder.jar  (embed stage)
  - filler.jar     (fill stage)
  - refresher.jar  (refresh stage)

Search order (first match wins):
  1. src/assets/<name>          — canonical location inside the mapper module
  2. assets/<name>              — when running from the module root
  3. <name>                     — when the JAR sits at the working directory root
  4. /opt/<name>                — Docker / Lambda layer mount point
  5. modules/mapper/sdk/pdf_autofiller_mapper/jars/<name>  — bundled inside the installed SDK
  6. PDF_AUTOFILLER_JAR_DIR env var / <name> — user-supplied override

Callers::

    from pdf_autofillr_mapper.utils.jar_path import find_jar

    jar = find_jar("filler.jar")   # raises FileNotFoundError if not found
"""

import os

# ── Resolved at import time so the paths are stable across calls ──────────────

# Directory that contains THIS file  →  pdf_autofillr_mapper/utils/
_UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
# One level up                       →  pdf_autofillr_mapper/
_PKG_DIR = os.path.dirname(_UTILS_DIR)
# Canonical assets dir               →  pdf_autofillr_mapper/assets/
_ASSETS_DIR = os.path.join(_PKG_DIR, "assets")


def find_jar(name: str) -> str:
    """
    Return the absolute path to *name* (e.g. ``"filler.jar"``).

    Raises:
        FileNotFoundError: JAR not found in any expected location.
    """
    candidates = [
        os.path.join(_ASSETS_DIR, name),  # pdf_autofillr_mapper/assets/
        os.path.join(_PKG_DIR, "..", "assets", name),  # assets/ (module root)
        os.path.join(os.getcwd(), name),  # working directory root
        os.path.join("/opt", name),  # Docker / Lambda layer
        _sdk_jars_path(name),  # bundled SDK jars/
        _env_override(name),  # PDF_AUTOFILLER_JAR_DIR
    ]

    for path in candidates:
        if path and os.path.exists(path):
            return os.path.abspath(path)

    raise FileNotFoundError(
        f"{name!r} not found. Checked:\n" + "\n".join(f"  {p}" for p in candidates if p)
    )


# ── Private helpers ───────────────────────────────────────────────────────────


def _sdk_jars_path(name: str) -> str:
    """Path inside the installed pdf-autofiller SDK package (jars/ sub-dir)."""
    try:
        import importlib.resources as _ir

        # Python 3.9+: importlib.resources.files()
        pkg = _ir.files("pdf_autofiller").joinpath("jars").joinpath(name)
        candidate = str(pkg)
        return candidate if os.path.exists(candidate) else ""
    except Exception:
        return ""


def _env_override(name: str) -> str:
    """Optional user-supplied directory via PDF_AUTOFILLER_JAR_DIR."""
    jar_dir = os.environ.get("PDF_AUTOFILLER_JAR_DIR", "")
    return os.path.join(jar_dir, name) if jar_dir else ""
