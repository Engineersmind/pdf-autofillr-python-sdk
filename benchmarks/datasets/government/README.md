# Dataset: Government Forms

## Overview

| | |
|-|-|
| **Category** | government |
| **Form types** | Tax, immigration, benefits, identification |
| **Difficulty** | Medium |
| **Typical field count** | 30–80 per PDF |
| **PDFs** | 0 (pending) |
| **Status** | Placeholder |

## Why medium difficulty

- Standardised but terse field labels (box numbers instead of names on some IRS forms)
- Many conditional sections (if yes, complete Part B)
- Mix of checkboxes, text, and numeric fields
- Strict formatting requirements (SSN, EIN, date formats)

## Planned forms

- [ ] W-2 (Wage and Tax Statement)
- [ ] W-4 (Employee Withholding)
- [ ] I-9 (Employment Eligibility Verification)
- [ ] DS-160 (Nonimmigrant Visa Application)
- [ ] SS-5 (Social Security Card Application)
- [ ] SNAP / benefits application

## Files

```
government/
├── pdfs/
├── schema_keys/
└── ground_truth/
```
