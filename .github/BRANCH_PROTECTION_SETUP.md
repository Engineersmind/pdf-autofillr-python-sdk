# Branch Protection Setup — `main`

GitHub branch protection cannot be set via a file in the repo — it must be configured once in GitHub Settings. Do this after pushing the new workflows.

---

## Steps

1. Go to: `https://github.com/Engineersmind/pdf-autofillr-python-sdk/settings/branches`
2. Click **Add branch ruleset** (or **Add rule** on older UI)
3. Set **Branch name pattern** to: `main`
4. Enable the following:

---

## Required Settings

### Restrict pushes
- ✅ **Restrict pushes that create matching branches**
- ✅ **Block force pushes**
- ✅ **Require a pull request before merging**
  - Required approvals: **1**
  - ✅ Dismiss stale reviews when new commits are pushed
  - ✅ Require review from code owners (uses CODEOWNERS file)

### Required status checks
- ✅ **Require status checks to pass before merging**
- ✅ **Require branches to be up to date before merging**

Add these as required checks (they appear after the workflows have run once):

| Check name | From workflow |
|---|---|
| `Branch name` | `pr-conventions.yml` |
| `Commit messages` | `pr-conventions.yml` |
| `PR title` | `pr-conventions.yml` |
| `mapper / Python 3.11` | `tests.yml` |
| `mapper / Python 3.12` | `tests.yml` |
| `chatbot / Python 3.11` | `tests.yml` |
| `chatbot / Python 3.12` | `tests.yml` |
| `doc_upload / Python 3.11` | `tests.yml` |
| `doc_upload / Python 3.12` | `tests.yml` |
| `rag / Python 3.11` | `tests.yml` |
| `rag / Python 3.12` | `tests.yml` |

### Additional
- ✅ **Do not allow bypassing the above settings**
  - This applies to admins too — nobody merges without checks passing

---

## Result

Once configured, GitHub will hard-block any PR that:
- Has a branch name that fails the `validate-branch` check
- Has a commit message that fails the `validate-commits` check  
- Has a PR title that fails the `validate-pr-title` check
- Has failing tests
- Has not been reviewed and approved

Direct pushes to `main` will be rejected at the Git level.