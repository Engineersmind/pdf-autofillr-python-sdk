# Dataset: Medical Forms

## Overview

| | |
|-|-|
| **Category** | medical |
| **Form types** | Patient intake, prior authorization, HIPAA consent, referral |
| **Difficulty** | Medium |
| **Typical field count** | 20–60 per PDF |
| **PDFs** | 0 (pending) |
| **Status** | Placeholder |

## Why medium difficulty

- Clinical terminology in field labels (ICD codes, CPT codes, NPI numbers)
- Mix of text, checkbox, and date fields
- HIPAA-specific fields with non-obvious mapping targets
- Provider vs patient sections must not be confused

## Planned forms

- [ ] Patient intake / registration form
- [ ] Prior authorization request
- [ ] HIPAA authorization and consent
- [ ] Medical history questionnaire
- [ ] Referral form
- [ ] Insurance claim (CMS-1500)

## Files

```
medical/
├── pdfs/
├── schema_keys/
└── ground_truth/
```
