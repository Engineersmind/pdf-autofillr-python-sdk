# Dataset: Legal Forms

## Overview

| | |
|-|-|
| **Category** | legal |
| **Form types** | NDA, power of attorney, compliance disclosure, contract addendum |
| **Difficulty** | High |
| **Typical field count** | 15–50 per PDF |
| **PDFs** | 0 (pending) |
| **Status** | Placeholder |

## Why difficult

- Verbose, legalese field labels that don't map cleanly to data keys
- Many signature and date fields with ambiguous context
- Inline fill-in fields within paragraphs (not standard form fields)
- Party names repeat in different roles (grantor, grantee, witness)

## Planned forms

- [ ] Non-disclosure agreement (NDA)
- [ ] Power of attorney
- [ ] Retainer agreement
- [ ] Compliance / conflict of interest disclosure
- [ ] Contract addendum / amendment
- [ ] Settlement agreement

## Files

```
legal/
├── pdfs/
├── schema_keys/
└── ground_truth/
```
