# src/ragpdf/init_vectors.py
"""
Vector database initialisation and embedding generation.

This module handles the full lifecycle of vector_database.json:

  1. FIRST RUN (no vector_database.json exists):
     - Reads vector_source.json (field definitions, no embeddings)
     - Generates embeddings using the configured backend
     - Writes vector_database.json with full embeddings + metadata

  2. SOURCE UPDATE (new fields added to vector_source.json):
     - Merges new vectors into existing vector_database.json
     - Generates embeddings only for the new vectors
     - Preserves all confidence history, usage counts, error history
       for existing vectors (non-destructive)

  3. FORCE RE-EMBED (--force flag):
     - Re-generates embeddings for every vector
     - Preserves all metadata (confidence history etc.)

File layout (under RAGPDF_DATA_PATH):
    vectors/
        source/
            vector_source.json    <- shipped with package, NEVER modified
        vector_database.json      <- runtime DB, grows forever

Called from:
  - ragpdf init-vectors           (explicit CLI command)
  - LocalVectorStore.__init__()   (auto-bootstrap on first load)
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Colour helpers (terminal only, stripped by logger) ───────────────────────


def _c(code: str, text: str) -> str:
    """Wrap text in ANSI colour if stdout is a TTY."""
    import sys

    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def green(s):
    return _c("92", s)


def red(s):
    return _c("91", s)


def cyan(s):
    return _c("96", s)


def yellow(s):
    return _c("93", s)


def bold(s):
    return _c("1", s)


# ── Timestamp ─────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ── Source file helpers ───────────────────────────────────────────────────────


def _needs_embedding(v: dict) -> bool:
    """Return True if this vector has no usable embedding."""
    emb = v.get("embedding")
    if not emb:
        return True
    if len(emb) == 0:
        return True
    if not any(x != 0.0 for x in emb):
        return True  # all-zero = noop / placeholder
    return False


def _build_text(v: dict) -> str:
    """
    Build the text string to embed from a vector's metadata.
    Matches EmbeddingBackend.create_text_from_field() exactly.
    """
    parts = [
        v.get("field_name", ""),
        v.get("context", ""),
        v.get("section_context", ""),
        " ".join(v.get("headers", [])),
    ]
    return " ".join(p for p in parts if p).strip()


def _load_source(source_path: Path) -> list:
    """Load and normalise a source vector file."""
    raw = json.loads(source_path.read_text(encoding="utf-8"))

    # Accept: plain list  OR  {"vectors": [...]}
    if isinstance(raw, list):
        vectors = raw
    elif isinstance(raw, dict) and "vectors" in raw:
        vectors = raw["vectors"]
    else:
        raise ValueError(
            f"Unrecognised format in {source_path}. "
            'Expected a JSON list or {"vectors": [...]}.'
        )

    required = {"vector_id", "field_name", "context"}
    for i, v in enumerate(vectors):
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"vector[{i}] missing required fields: {missing}")

    return vectors


def _merge_source_into_runtime(
    source_vectors: list, runtime_vectors: list
) -> tuple[list, int]:
    """
    Merge source definitions into the runtime DB.

    Rules:
      - vector_id already in runtime  → keep runtime (preserves confidence history,
        usage counts, error history); refresh context/headers/field_name from source.
      - vector_id new in source       → add skeleton entry (embedding to be filled).

    Returns (merged_list, added_count).
    """
    runtime_by_id = {v["vector_id"]: v for v in runtime_vectors}
    added = 0

    for sv in source_vectors:
        vid = sv["vector_id"]
        if vid not in runtime_by_id:
            # New vector — add skeleton, embedding will be generated next
            runtime_by_id[vid] = {
                "vector_id": vid,
                "field_name": sv["field_name"],
                "context": sv.get("context", ""),
                "section_context": sv.get("section_context", ""),
                "headers": sv.get("headers", []),
                "embedding": [],
                "confidence": sv.get("confidence", 0.75),
                "confidence_history": [sv.get("confidence", 0.75)],
                "positive_count": 0,
                "negative_count": 0,
                "usage_count": 0,
                "stability_score": 1.0,
                "avg_confidence": sv.get("confidence", 0.75),
                "error_history": [],
                "created_at": _now(),
                "last_updated": _now(),
                "last_used": _now(),
            }
            added += 1
        else:
            # Already exists — refresh metadata from source, keep all learned data
            rv = runtime_by_id[vid]
            rv["field_name"] = sv["field_name"]
            rv["context"] = sv.get("context", rv.get("context", ""))
            rv["section_context"] = sv.get(
                "section_context", rv.get("section_context", "")
            )
            rv["headers"] = sv.get("headers", rv.get("headers", []))

    # Preserve source order, append any runtime-only vectors at the end
    source_ids = [v["vector_id"] for v in source_vectors]
    runtime_only = [v for v in runtime_vectors if v["vector_id"] not in set(source_ids)]
    merged = [runtime_by_id[vid] for vid in source_ids] + runtime_only

    return merged, added


def _get_embedder(backend: str, model: str):
    """
    Return (embed_batch_fn, model_name).

    embed_batch_fn(texts: list[str]) -> list[list[float]]
    Embeddings are L2-normalised before return.
    """
    import numpy as np

    if backend == "openai":
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise OSError(
                "OPENAI_API_KEY is not set.\n"
                "Add it to your .env file or set it as an environment variable."
            )
        used_model = model or "text-embedding-3-small"
        client = OpenAI(api_key=api_key)

        def embed_batch(texts: list) -> list:
            resp = client.embeddings.create(input=texts, model=used_model)
            embs = [d.embedding for d in resp.data]
            # Normalise
            result = []
            for emb in embs:
                arr = np.array(emb, dtype=float)
                norm = np.linalg.norm(arr)
                result.append((arr / norm).tolist() if norm > 1e-9 else emb)
            return result

        return embed_batch, used_model

    else:  # sentence_transformer
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for this backend.\n"
                "Install with: pip install 'pdf-autofillr-rag[transformers]'"
            ) from e
        used_model = model or "all-MiniLM-L6-v2"
        st = SentenceTransformer(used_model)

        def embed_batch(texts: list) -> list:
            embs = st.encode(texts, show_progress_bar=False, convert_to_numpy=True)
            norms = np.linalg.norm(embs, axis=1, keepdims=True)
            norms = np.where(norms < 1e-9, 1.0, norms)
            return (embs / norms).tolist()

        return embed_batch, used_model


def _write_runtime(runtime_path: Path, merged: list, existing_db: dict) -> None:
    """Write the final runtime vector_database.json."""
    existing_db["vectors"] = merged
    existing_db["metadata"]["total_count"] = len(merged)
    existing_db["metadata"]["last_updated"] = _now()
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(json.dumps(existing_db, indent=2), encoding="utf-8")


def _sanity_check(
    sample_vectors: list,
    embed_batch_fn,
    runtime_path: Path,
    verbose: bool = True,
) -> bool:
    """
    Embed the first N vectors and verify each one is its own nearest neighbour
    with cosine similarity >= 0.99. Returns True if all pass.
    """
    if not sample_vectors or not runtime_path.exists():
        return True

    try:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim

        db = json.loads(runtime_path.read_text(encoding="utf-8"))
        all_vecs = db["vectors"]
        all_embs = np.array([v["embedding"] for v in all_vecs])

        texts = [_build_text(v) for v in sample_vectors]
        embeddings = embed_batch_fn(texts)

        if verbose:
            print()
            print(cyan("─" * 60))
            print(cyan("  SANITY CHECK — vectors match themselves"))
            print(cyan("─" * 60))
            print()
            print(f"  {'VID':<8} {'Field name':<38} {'Conf':>7}  Result")
            print(f"  {'-'*65}")

        all_pass = True
        for v, emb in zip(sample_vectors, embeddings, strict=False):
            q = np.array(emb) / np.linalg.norm(emb)
            sims = cos_sim([q], all_embs)[0]
            best_i = int(np.argmax(sims))
            best_n = all_vecs[best_i]["field_name"]
            best_c = float(sims[best_i])
            ok = best_n == v["field_name"] and best_c >= 0.99
            if not ok:
                all_pass = False
            if verbose:
                flag = green("PASS") if ok else red(f"FAIL (got {best_n})")
                print(
                    f"  {v['vector_id']:<8} {v['field_name']:<38} {best_c:>7.4f}  {flag}"
                )

        if verbose:
            print()
            if all_pass:
                print(green("  ✓ Sanity check passed."))
            else:
                print(
                    red("  ✗ Sanity check failed — check embedding model consistency.")
                )

        return all_pass

    except Exception as e:
        if verbose:
            print(yellow(f"  WARNING: Sanity check skipped — {e}"))
        logger.warning("Sanity check failed: %s", e)
        return True  # Don't block startup on check failure


# ── Main public function ──────────────────────────────────────────────────────


def run_init_vectors(
    data_path: str = "./data/rag",
    source_path: str | None = None,
    backend: str = "openai",
    model: str = "",
    force: bool = False,
    batch_size: int = 50,
    verbose: bool = True,
    sanity_check: bool = True,
) -> dict:
    """
    Initialise or update the vector database.

    Args:
        data_path:    RAGPDF_DATA_PATH root (default: ./data/rag)
        source_path:  Path to source JSON. Defaults to
                      {data_path}/vectors/source/vector_source.json
        backend:      "openai" | "sentence_transformer"
        model:        Embedding model name (blank = use backend default)
        force:        Re-embed all vectors, even already-embedded ones
        batch_size:   Vectors per API call
        verbose:      Print progress to stdout
        sanity_check: Run self-test after embedding

    Returns:
        dict with keys: vectors_total, vectors_embedded, vectors_skipped,
                        runtime_path, model_used
    """
    import numpy as np

    dp = Path(data_path)
    runtime_path = dp / "vectors" / "vector_database.json"
    source_dir = dp / "vectors" / "source"

    # ── Locate source file ────────────────────────────────────────────────────
    sp: Path | None
    if source_path:
        sp = Path(source_path)
    else:
        # Try both names for backwards compatibility
        for name in ("vector_source.json", "vector_base.json"):
            candidate = source_dir / name
            if candidate.exists():
                sp = candidate
                break
        else:
            # Try bundled package data as a last resort
            sp = _find_bundled_source()

    if sp is None or not sp.exists():
        raise FileNotFoundError(
            f"Source vector file not found.\n"
            f"Expected at: {source_dir / 'vector_source.json'}\n\n"
            f"Drop your vector_source.json there, or pass --source /path/to/file.json"
        )

    if verbose:
        print()
        print(bold(cyan("=" * 60)))
        print(bold(cyan("  pdf-autofillr-rag — Vector DB Initialisation")))
        print(bold(cyan("=" * 60)))
        print()
        print(f"  Source:     {sp}")
        print(f"  Runtime DB: {runtime_path}")
        print(f"  Backend:    {backend}")

    # ── Copy source to canonical location ─────────────────────────────────────
    source_dir.mkdir(parents=True, exist_ok=True)
    canonical = source_dir / "vector_source.json"
    if sp.resolve() != canonical.resolve() and not canonical.exists():
        shutil.copy2(sp, canonical)
        if verbose:
            print(f"  Copied to:  {canonical}")

    # ── Load source ───────────────────────────────────────────────────────────
    source_vectors = _load_source(sp)
    if verbose:
        print(f"  Vectors:    {len(source_vectors)} in source")

    # ── Load or create runtime DB ─────────────────────────────────────────────
    if runtime_path.exists():
        raw = runtime_path.read_text(encoding="utf-8").strip()
        if raw:
            runtime_db = json.loads(raw)
            runtime_vecs = runtime_db.get("vectors", [])
            if verbose:
                print(f"  Existing:   {len(runtime_vecs)} vectors in runtime DB")
        else:
            runtime_db = {
                "metadata": {"total_count": 0, "last_updated": _now()},
                "vectors": [],
            }
            runtime_vecs = []
    else:
        runtime_db = {
            "metadata": {"total_count": 0, "last_updated": _now()},
            "vectors": [],
        }
        runtime_vecs = []

    # ── Merge ─────────────────────────────────────────────────────────────────
    merged, added = _merge_source_into_runtime(source_vectors, runtime_vecs)
    if added and verbose:
        print(f"  {green(f'+{added} new vectors added from source')}")

    # ── Find what needs embedding ─────────────────────────────────────────────
    to_embed = [v for v in merged if force or _needs_embedding(v)]
    already_done = len(merged) - len(to_embed)

    if verbose:
        print()
        print(f"  Need embedding:   {len(to_embed)}")
        print(f"  Already embedded: {already_done}")

    if not to_embed:
        if verbose:
            print()
            print(green("  All vectors already embedded. Nothing to do."))
            print(green("  Run with --force to regenerate all embeddings."))
        _write_runtime(runtime_path, merged, runtime_db)
        if sanity_check and merged:
            try:
                embed_fn, _ = _get_embedder(backend, model)
                _sanity_check(merged[:3], embed_fn, runtime_path, verbose=verbose)
            except Exception:
                pass
        return {
            "vectors_total": len(merged),
            "vectors_embedded": 0,
            "vectors_skipped": already_done,
            "runtime_path": str(runtime_path),
            "model_used": model or "(unchanged)",
        }

    # ── Load embedder ─────────────────────────────────────────────────────────
    if verbose:
        print()
        print("  Loading embedding backend...")
    embed_fn, used_model = _get_embedder(backend, model)
    if verbose:
        print(f"  Model:      {bold(used_model)}")

    # ── Embed in batches ──────────────────────────────────────────────────────
    texts = [_build_text(v) for v in to_embed]
    ids = [v["vector_id"] for v in to_embed]
    n_batches = math.ceil(len(texts) / batch_size)
    idx_map = {v["vector_id"]: i for i, v in enumerate(merged)}
    embedded = 0

    if verbose:
        print()
        print(f"  Embedding {len(to_embed)} vectors in {n_batches} batch(es)...")
        print()

    for b in range(n_batches):
        batch_texts = texts[b * batch_size : (b + 1) * batch_size]
        batch_ids = ids[b * batch_size : (b + 1) * batch_size]

        try:
            embeddings = embed_fn(batch_texts)
        except Exception as e:
            # Save progress before aborting
            _write_runtime(runtime_path, merged, runtime_db)
            raise RuntimeError(
                f"Embedding failed on batch {b + 1}/{n_batches}: {e}\n"
                f"Progress saved ({embedded} vectors embedded so far)."
            ) from e

        for vid, emb in zip(batch_ids, embeddings, strict=False):
            arr = np.array(emb, dtype=float)
            norm = np.linalg.norm(arr)
            normalised = (arr / norm).tolist() if norm > 1e-9 else emb
            merged[idx_map[vid]]["embedding"] = [round(x, 8) for x in normalised]
            merged[idx_map[vid]]["last_updated"] = _now()
            embedded += 1

        if verbose:
            pct = int((b + 1) / n_batches * 40)
            bar = "█" * pct + "░" * (40 - pct)
            print(
                f"  [{bar}] {embedded}/{len(to_embed)}  batch {b + 1}/{n_batches}",
                end="\r",
            )

    if verbose:
        print()
        print()
        print(green(f"  ✓ Embedded {embedded} vectors successfully."))

    # ── Save ──────────────────────────────────────────────────────────────────
    _write_runtime(runtime_path, merged, runtime_db)
    if verbose:
        print(f"  {green('Saved:')} {runtime_path}")
        print(f"  Total vectors in runtime DB: {bold(str(len(merged)))}")

    # ── Sanity check ──────────────────────────────────────────────────────────
    if sanity_check:
        _sanity_check(merged[:3], embed_fn, runtime_path, verbose=verbose)

    return {
        "vectors_total": len(merged),
        "vectors_embedded": embedded,
        "vectors_skipped": already_done,
        "runtime_path": str(runtime_path),
        "model_used": used_model,
    }


def _find_bundled_source() -> Path | None:
    """Try to find vector_source.json bundled with the ragpdf package."""
    try:
        import importlib.resources

        pkg_files = importlib.resources.files("ragpdf")
        p = pkg_files / "data" / "vector_source.json"
        # importlib.resources gives a non-Path object on older Python — extract to temp
        import tempfile

        tmp = Path(tempfile.mktemp(suffix=".json"))
        with p.open("rb") as src, open(tmp, "wb") as dst:
            dst.write(src.read())
        return tmp
    except Exception:
        pass

    try:
        import ragpdf as pkg_mod

        p = Path(os.path.dirname(pkg_mod.__file__)) / "data" / "vector_source.json"
        if p.exists():
            return p
    except Exception:
        pass

    return None


def auto_bootstrap(data_path: str, verbose: bool = False) -> bool:
    """
    Called by LocalVectorStore.__init__() when vector_database.json does not exist
    but a source file is present.

    Returns True if bootstrap ran, False if nothing to do.
    Reads backend and model from environment (RAGPDF_EMBEDDING_BACKEND etc.)
    so it respects whatever the user configured in .env.
    """
    from ragpdf.config.settings import (
        RAGPDF_EMBEDDING_BACKEND,
        RAGPDF_OPENAI_EMBEDDING_MODEL,
        RAGPDF_ST_MODEL,
    )

    dp = Path(data_path)
    runtime_path = dp / "vectors" / "vector_database.json"

    # Only bootstrap if runtime DB is missing or empty
    if runtime_path.exists():
        raw = runtime_path.read_text(encoding="utf-8").strip()
        if raw:
            db = json.loads(raw)
            if db.get("vectors"):
                return False  # already have vectors, nothing to do

    # Check if a source file exists
    source_dir = dp / "vectors" / "source"
    source_file = None
    for name in ("vector_source.json", "vector_base.json"):
        candidate = source_dir / name
        if candidate.exists():
            source_file = str(candidate)
            break

    # Also check bundled package data
    if source_file is None:
        bundled = _find_bundled_source()
        if bundled:
            source_file = str(bundled)

    if source_file is None:
        logger.debug(
            "auto_bootstrap: no source file found, starting with empty vector DB"
        )
        return False

    backend = RAGPDF_EMBEDDING_BACKEND
    model = RAGPDF_OPENAI_EMBEDDING_MODEL if backend == "openai" else RAGPDF_ST_MODEL

    # Don't auto-bootstrap with noop — that would silently create garbage vectors
    if backend == "noop":
        logger.debug(
            "auto_bootstrap: RAGPDF_EMBEDDING_BACKEND=noop — skipping bootstrap"
        )
        return False

    logger.info(
        "auto_bootstrap: vector_database.json missing, bootstrapping from %s using %s/%s",
        source_file,
        backend,
        model,
    )

    if verbose:
        print(f"\n  📦 First run — generating vector embeddings from {source_file}")
        print(f"     Backend: {backend}  Model: {model or '(default)'}")
        print("     This takes ~30s for OpenAI or ~60s for sentence_transformer.")
        print("     Run once only — subsequent starts are instant.\n")

    try:
        run_init_vectors(
            data_path=data_path,
            source_path=source_file,
            backend=backend,
            model=model,
            force=False,
            batch_size=50,
            verbose=verbose,
            sanity_check=False,  # Skip sanity check during auto-bootstrap for speed
        )
        return True
    except Exception as e:
        logger.warning(
            "auto_bootstrap failed (%s) — starting with empty vector DB. "
            "Run 'ragpdf init-vectors' manually to retry.",
            e,
        )
        return False
