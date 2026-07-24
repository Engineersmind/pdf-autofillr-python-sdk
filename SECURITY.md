# Security Policy

## Supported Versions

| Package | Version | Supported |
|---------|---------|-----------|
| pdf-autofillr-mapper | 1.0.11 | ✅ |
| pdf-autofillr-chatbot | 0.3.1 | ✅ |
| pdf-autofillr-doc-upload | 0.1.6 | ✅ |
| pdf-autofillr-rag | 0.2.5 | ✅ |
| pdf-autofillr (umbrella) | 1.1.5 | ✅ |
| Any previous version | < latest | ❌ |

---

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**  
Public issues expose users to 0-days before a fix is available.

### Preferred — GitHub Security Advisories (private)
https://github.com/Engineersmind/pdf-autofillr-python-sdk/security/advisories/new

GitHub keeps this completely private until a fix is released.

### Alternative — Email
**security@engineersmind.com**  
Subject: `[SECURITY] <brief description>`

---

## Response Timeline

| Severity | First Response | Patch Target |
|----------|---------------|--------------|
| Critical | 24 hours | 7 days |
| High | 48 hours | 14 days |
| Medium / Low | 5 business days | Next release |

We follow coordinated disclosure — we'll work with you on timing before anything is made public.

---

## Scope

Areas most relevant for security research in this codebase:

- **LLM prompt injection** — chatbot and doc-upload extraction prompts
- **PDF parsing** — PyMuPDF field extraction in mapper
- **File upload handling** — doc-upload document reader (path traversal, malicious files)
- **API key exposure** — `.env` handling, storage backends
- **Cloud storage** — S3, Azure Blob, GCS backend access controls
- **Java subprocess calls** — form_field_filler, form_field_rebuilder, form_field_refresher

---

## Security Best Practices (for contributors)

```bash
# Never commit .env — always use .env.example
cp .env.example .env
echo ".env" >> .gitignore

# Scan dependencies for known CVEs
pip-audit

# Static analysis
bandit -r packages/mapper/src/ \
          packages/chatbot/src/ \
          packages/doc_upload/src/ \
          packages/rag/src/
```

- Never log API keys, LLM responses containing PII, or raw user input
- All storage backends must use the configured credentials — never hardcode
- `.env` files are in `.gitignore` and must never be committed

---

## After Reporting

Once a vulnerability is confirmed:

1. We open a private GitHub Security Advisory
2. We develop and test a fix on a private branch
3. We coordinate a disclosure date with the reporter
4. We release the patch and publish the advisory simultaneously
5. Reporter is credited in the advisory (unless they prefer anonymity)