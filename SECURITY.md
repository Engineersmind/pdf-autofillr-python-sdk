# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.x | ✅ |
| < 1.0 | ❌ |

## Reporting a vulnerability

**GitHub Security Advisories (preferred):**
https://github.com/Engineersmind/pdf-autofillr/security/advisories/new

**Email:** Security@pdffillr.ai
Subject: `[SECURITY] <brief description>`

We respond within 48 hours and follow coordinated disclosure.

## Security best practices

```bash
# Never commit .env — use .env.example
cp .env.example .env && echo ".env" >> .gitignore

# Scan dependencies
pip-audit

# Scan source
bandit -r packages/mapper/src/ packages/chatbot/src/ \
       packages/doc_upload/src/ packages/rag/src/
```
