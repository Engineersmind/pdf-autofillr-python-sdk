# Contributing to pdf-autofillr-python-sdk

Thank you for your interest in contributing. This document covers everything external contributors need to open a great pull request.

---

## Important Rules

- Never push directly to `main`
- Never commit directly to protected branches
- All changes must go through Pull Requests
- Every contribution must start from a dedicated branch
- Commit messages must follow the convention below

---

## 1. Fork & Clone

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/<your-username>/pdf-autofillr-python-sdk.git
cd pdf-autofillr-python-sdk
```

---

## 2. Branch Naming Convention

Create a new branch before making any changes.

**Format:**

```
<type>/<module>-<short-description>
```

**Examples:**

```
feature/mapper-semantic-grouping
fix/rag-empty-response
docs/sdk-installation-guide
perf/storage-cache-optimization
test/chatbot-handler-tests
chore/repo-cleanup
```

**Allowed types:**

| Type | Use for |
|------|---------|
| `feature` | New functionality |
| `fix` | Bug fixes |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `chore` | Maintenance, config, tooling |
| `perf` | Performance improvements |
| `bug` | Reporting/fixing a confirmed bug |

```bash
git checkout main
git pull origin main
git checkout -b feature/mapper-semantic-grouping
```

---

## 3. Make Your Changes

Implement your feature, fix, or improvement. Keep changes focused — one branch, one purpose.

---

## 4. Commit Convention

**Format:**

```
<type>/<module>: short description
```

**Examples:**

```bash
git commit -m "feature/mapper: add semantic grouping support"
git commit -m "fix/rag: handle empty embeddings"
git commit -m "docs/sdk: update quickstart guide"
git commit -m "test/chatbot: add handler edge case tests"
git commit -m "chore/repo: update .gitignore"
```

**Allowed commit types:** `feature/` · `fix/` · `bug/` · `docs/` · `test/` · `chore/` · `perf/`

Any other format will be rejected during review.

---

## 5. Push Your Branch

```bash
git push origin feature/mapper-semantic-grouping
```

---

## 6. Open a Pull Request

Open a PR from your branch into `main` on GitHub.

**Every PR must include:**

- Clear summary of what changed and why
- How you tested it
- Related issue number (if applicable)
- Clean commit history following the convention above

**PR checklist — check all before submitting:**

- [ ] Branch named correctly (`<type>/<module>-<description>`)
- [ ] No direct commits to `main`
- [ ] All commit messages follow the convention
- [ ] Changes tested locally
- [ ] Documentation updated if behaviour changed
- [ ] No unnecessary files included (build artifacts, `.env`, `__pycache__`, etc.)

---

## 7. Full Example Workflow

```bash
# Start from a clean main
git checkout main
git pull origin main

# Create your branch
git checkout -b fix/rag-empty-response

# Make changes, then commit
git add .
git commit -m "fix/rag: handle empty embeddings gracefully"

# Push and open PR
git push origin fix/rag-empty-response
```

Then open a Pull Request on GitHub targeting `main`.

---

## Questions?

Open an issue or start a discussion on the [repository](https://github.com/Engineersmind/pdf-autofillr-python-sdk).