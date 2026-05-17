## Description
<!-- What does this PR do? Be specific. -->

## Why
<!-- Why is this change needed? Link to an issue if applicable. -->
Closes #

## Changes Made
<!-- List the key changes -->
-
-

## Testing
<!-- How did you test this? What commands did you run? -->
```bash

```

## Screenshots (if applicable)

---

## Checklist

**Branch & commits**
- [ ] Branch named correctly — `<type>/<module>-<short-description>` (e.g. `fix/rag-empty-response`)
- [ ] All commit messages follow `<type>/<module>: description` (e.g. `fix/rag: handle empty embeddings`)
- [ ] PR title follows the same format
- [ ] No direct commits to `main`

**Code**
- [ ] `pip install -e ".[dev]"` succeeds
- [ ] `pytest tests/` passes locally
- [ ] New behaviour has test coverage
- [ ] No build artifacts, `.env`, `__pycache__`, or `.egg-info` included

**Docs**
- [ ] `.env.example` updated if new env vars added
- [ ] `CHANGELOG.md` entry added in the affected package
- [ ] Root `README.md` version table updated if version was bumped