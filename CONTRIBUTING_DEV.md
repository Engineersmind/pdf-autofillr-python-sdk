# Developer Guide — pdf-autofillr-python-sdk

Internal reference for the Engineersmind team. Covers local setup, testing, and the release process for all packages.

---

## Repository Layout

```
pdf-autofillr-python-sdk/
├── packages/
│   ├── mapper/          → pdf-autofillr-mapper
│   ├── chatbot/         → pdf-autofillr-chatbot
│   ├── doc_upload/      → pdf-autofillr-doc-upload
│   ├── rag/             → pdf-autofillr-rag
│   └── pdf_autofillr/   → pdf-autofillr (umbrella)
├── plugins/
│   ├── core/            → pdf-autofiller-core
│   └── pdf_autofillr/   → pdf-autofiller-plugins
├── docs/
├── examples/
├── benchmarks/
└── deployment/
```

---

## Local Setup

```bash
git clone https://github.com/Engineersmind/pdf-autofillr-python-sdk.git
cd pdf-autofillr-python-sdk

# Work inside the package you're changing
cd packages/mapper        # or chatbot, rag, doc_upload, pdf_autofillr

python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env      # fill in your LLM API key
```

---

## Running Tests

From inside any package directory:

```bash
pytest tests/ -v
```

Per-package shortcuts:

```bash
cd packages/mapper     && pytest tests/ -q
cd packages/chatbot    && pytest tests/ -q
cd packages/doc_upload && python run_all_tests.py
cd packages/rag        && python run_all_tests.py
```

---

## Branch Reference

| Branch | Purpose |
|--------|---------|
| `main` | Stable — never push directly |
| `feature/<module>-<name>` | New functionality |
| `fix/<module>-<name>` | Bug fixes |
| `docs/<module>-<name>` | Documentation only |
| `test/<module>-<name>` | Test additions |
| `chore/<module>-<name>` | Maintenance / tooling |
| `perf/<module>-<name>` | Performance improvements |

Same rules as external contributors — no exceptions for internal team:

- **Never push directly to `main`**
- All changes go through a PR
- Branch format: `<type>/<module>-<short-description>`
- Commit format: `<type>/<module>: short description`

---

## PR Checklist

- [ ] `pip install -e ".[dev]"` succeeds cleanly
- [ ] `pytest tests/` passes with no failures
- [ ] New behaviour has test coverage
- [ ] `.env.example` updated if new env vars added
- [ ] `CHANGELOG.md` entry added in the affected package
- [ ] Root `README.md` version table updated if version bumped
- [ ] No build artifacts, `.env`, `__pycache__`, or `.egg-info` committed

---

## Release Process

### Steps

1. Bump `version` in the package's `pyproject.toml`
2. Add an entry to that package's `CHANGELOG.md`
3. Update the versions table in the root `README.md` and root `CHANGELOG.md`
4. Merge to `main` via PR
5. Push the version tag — CI publishes to PyPI automatically

### Current versions

| Tag | PyPI package | Version |
|-----|-------------|---------|
| `mapper-v*` | pdf-autofillr-mapper | **1.0.11** |
| `chatbot-v*` | pdf-autofillr-chatbot | **0.3.1** |
| `doc-upload-v*` | pdf-autofillr-doc-upload | **0.1.6** |
| `rag-v*` | pdf-autofillr-rag | **0.2.5** |
| `umbrella-v*` | pdf-autofillr (umbrella) | **1.1.5** |
| `core-v*` | pdf-autofiller-core | **1.0.0** |
| `plugins-v*` | pdf-autofiller-plugins | **0.1.0** |

### Tagging a release

```bash
git tag mapper-v1.0.11    && git push origin mapper-v1.0.11
git tag chatbot-v0.3.1    && git push origin chatbot-v0.3.1
git tag doc-upload-v0.1.6 && git push origin doc-upload-v0.1.6
git tag rag-v0.2.5        && git push origin rag-v0.2.5
git tag umbrella-v1.1.5   && git push origin umbrella-v1.1.5
git tag core-v1.0.0       && git push origin core-v1.0.0
git tag plugins-v0.1.0    && git push origin plugins-v0.1.0
```

---

## Adding a New `.env` Variable

1. Add it to the package's `.env.example` with a comment explaining it
2. Add it to the `Settings` class in `settings.py` with a sensible default
3. Document it in the package's `USAGE.md` under Configuration Reference
4. Add a `CHANGELOG.md` entry

---

## Windows Long-Path Workaround (mapper wheel only)

The mapper package has deep nested paths that break `python -m build` on Windows. Use this workaround:

```powershell
# 1. Remove old build artifacts
Remove-Item -Recurse -Force "packages\mapper\dist" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "packages\mapper\build" -ErrorAction SilentlyContinue

# 2. Copy to a short path, build, copy dist back
New-Item -ItemType Directory -Path "C:\p" -Force
Copy-Item -Recurse "packages\mapper" "C:\p\mapper"
cd C:\p\mapper
python -m build --wheel
Copy-Item -Recurse "C:\p\mapper\dist" "<full-repo-path>\packages\mapper\dist"
Remove-Item -Recurse -Force "C:\p"

# 3. Upload to PyPI
cd <full-repo-path>\packages
twine upload mapper\dist\*.whl
```