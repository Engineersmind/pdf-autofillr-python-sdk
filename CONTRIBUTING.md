# Contributing to pdf-autofillr

## Setup

```bash
git clone https://github.com/Engineersmind/pdf-autofillr.git
cd pdf-autofillr

cd packages/mapper      # or chatbot, rag, doc_upload, pdf_autofillr
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env    # add your LLM key
```

## Tests

```bash
pytest tests/ -v                           # from inside the package dir
```

Or from root:
```bash
cd packages/mapper    && pytest tests/ -q
cd packages/chatbot   && pytest tests/ -q
cd packages/doc_upload && python run_all_tests.py
cd packages/rag       && python run_all_tests.py
```

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Stable — never push directly |
| `dev` | All PRs merge here |
| `feature/<name>` | Feature work |
| `fix/<name>` | Bug fixes |

## PR checklist

- [ ] `pip install -e ".[dev]"` succeeds
- [ ] `pytest tests/` passes
- [ ] New behaviour has tests
- [ ] `.env.example` updated if new env vars added
- [ ] `CHANGELOG.md` entry added

## Releasing

1. Bump `version` in `pyproject.toml`
2. Add entry to `CHANGELOG.md`
3. Merge to `main`
4. Push a version tag — CI publishes to PyPI automatically

| Tag | PyPI package |
|-----|-------------|
| `mapper-v1.0.8` | pdf-autofillr-mapper |
| `chatbot-v0.2.9` | pdf-autofillr-chatbot |
| `doc-upload-v0.1.4` | pdf-autofillr-doc-upload |
| `rag-v0.2.3` | pdf-autofillr-rag |
| `umbrella-v1.1.2` | pdf-autofillr (umbrella) |
| `core-v1.0.0` | pdf-autofiller-core |
| `plugins-v0.1.0` | pdf-autofiller-plugins |

```bash
git tag mapper-v1.0.8 && git push origin mapper-v1.0.8
```
