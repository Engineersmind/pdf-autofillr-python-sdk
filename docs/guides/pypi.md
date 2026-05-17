# Publishing to PyPI

## Are all packages set up the same way?

Yes. All five packages follow the same structure:

| Package | Build system | CLI scripts | All entrypoints in `src/` |
|---|---|---|---|
| `pdf-autofillr-chatbot` | hatchling | `chatbot-cli`, `chatbot-server` | cli, server, fastapi_app, aws_lambda, azure_function, gcp_function |
| `pdf-autofillr-doc-upload` | hatchling | `doc-upload-cli`, `doc-upload-server` | cli, server, fastapi_app, aws_lambda, azure_function, gcp_function |
| `pdf-autofillr-rag` | hatchling | `ragpdf`, `ragpdf-server` | cli, fastapi_app, aws_lambda, azure_function, gcp_function |
| `pdf-autofillr-mapper` | hatchling | `pdf-mapper`, `pdf-mapper-server` | cli, server, fastapi_app, aws_lambda, azure_function, gcp_function |
| `pdf-autofillr` (umbrella) | hatchling | — | — |

---

## Automated publish process

Publishing is fully automated via GitHub Actions (`.github/workflows/publish-pypi.yml`).

**You never manually upload to PyPI.** You just push a git tag — the workflow handles testing, building, and publishing.

It uses **PyPI Trusted Publishing (OIDC)** — no API token is stored anywhere. GitHub authenticates directly with PyPI via the `pypi` Actions environment.

### How it works

```
git tag pushed
      │
      ▼
  resolve job        maps tag → package dir + name + version
      │
      ▼
   test job          pip install -e ".[dev]" → pytest tests/
      │
      ▼
  build job          verifies tag version == pyproject.toml version
                     python -m build  →  dist/*.whl + dist/*.tar.gz
      │
      ▼
 publish job         uploads dist/ to PyPI via OIDC (no token)
```

---

## Tag format → package mapping

| Git tag | Package published |
|---|---|
| `mapper-v1.0.8` | `pdf-autofillr-mapper` |
| `chatbot-v0.2.9` | `pdf-autofillr-chatbot` |
| `doc-upload-v0.1.4` | `pdf-autofillr-doc-upload` |
| `rag-v0.2.3` | `pdf-autofillr-rag` |
| `umbrella-v1.1.3` | `pdf-autofillr` (umbrella) |

---

## Release steps (one package)

### 1. Bump the version

Edit `packages/<pkg>/pyproject.toml`:
```toml
[project]
version = "1.0.9"   # ← bump this
```

Also bump `__version__` in `packages/<pkg>/src/<module>/__init__.py` and `entrypoints/__init__.py` to match.

### 2. Update CHANGELOG.md

Add an entry at the top of `packages/<pkg>/CHANGELOG.md`:
```markdown
## [1.0.9] - 2026-04-29
### Fixed
- ...
### Added
- ...
```

### 3. Merge to main

Commit, push branch, merge PR to `main`. The publish workflow only runs on tags — merging alone does nothing.

### 4. Push the tag

```bash
git checkout main && git pull
git tag mapper-v1.0.9
git push origin mapper-v1.0.9
```

GitHub Actions triggers immediately. Watch the run at:
`https://github.com/Engineersmind/pdf-autofillr-python-sdk/actions`

### 5. Verify on PyPI

After the workflow succeeds (~2–3 min):
```bash
pip install pdf-autofillr-mapper==1.0.9
python -c "import pdf_autofillr_mapper; print(pdf_autofillr_mapper.__version__)"
```

---

## One-time setup (already done, for reference)

For Trusted Publishing to work, the following must be configured once:

1. **PyPI project exists** — first publish must be done manually with a token, or the project created at pypi.org
2. **Trusted Publisher configured** on pypi.org:
   - Owner: `Engineersmind`
   - Repo: `pdf-autofillr-python-sdk`
   - Workflow: `publish-pypi.yml`
   - Environment: `pypi`
3. **GitHub Actions environment `pypi`** exists in the repo settings with `id-token: write` permission

---

## Common mistakes

| Mistake | What happens | Fix |
|---|---|---|
| Tag version doesn't match `pyproject.toml` | Build job fails with "Version mismatch" | Bump version in `pyproject.toml` first |
| Tests fail | Build never runs | Fix the test before tagging |
| Tag pushed to wrong branch | Workflow runs but may publish stale code | Always tag from `main` after merge |
| Forgot to bump `__version__` in `__init__.py` | Package installs but `.__version__` shows old value | Bump all three places together |