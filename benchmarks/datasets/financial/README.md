# Dataset: Financial Forms

## Overview

| | |
|-|-|
| **Category** | financial |
| **Form types** | Investment subscription, loan application, tax forms, fund agreements |
| **Difficulty** | High |
| **Typical field count** | 40–120 per PDF |
| **PDFs** | 0 (pending) |
| **Status** | Placeholder |

## Why difficult

- Dense multi-page forms with complex nesting (e.g. `address_registered.address_registered_line1_id`)
- Many checkbox groups (investor type, entity type)
- Legal boilerplate mixed with data fields
- Numeric formatting (currency, percentages, EIN)

## Planned forms

- [ ] Investment subscription agreement
- [ ] Loan application (residential / commercial)
- [ ] W-9 (tax identification)
- [ ] Form 1040 (individual tax return)
- [ ] Fund subscription form
- [ ] FATCA / KYC compliance form

## Files

```
financial/
├── pdfs/               # PDF files go here
├── schema_keys/        # Schema key JSON files go here
└── ground_truth/       # Ground truth mapping JSON files go here
```
