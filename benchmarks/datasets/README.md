# Benchmark Datasets

Each category is a collection of real PDF forms with ground truth field mappings.

---

## Categories

| Category | Typical forms | Difficulty | PDFs |
|----------|--------------|------------|------|
| [financial](financial/README.md) | Investment subscription, loan application, tax | High — dense fields, complex nesting | 0 |
| [medical](medical/README.md) | Patient intake, prior auth, HIPAA consent | Medium — clinical terminology | 0 |
| [legal](legal/README.md) | NDA, compliance, power of attorney | High — verbose labels, legal phrasing | 0 |
| [government](government/README.md) | W-2, I-9, visa application, benefits | Medium — standardised but terse | 0 |
| [hr](hr/README.md) | Onboarding, direct deposit, emergency contact | Low — common field names | 0 |
| [insurance](insurance/README.md) | Life, health, property claim | Medium — provider-specific jargon | 0 |

---

## Folder layout per category

```
<category>/
├── README.md           # Dataset card
├── pdfs/               # The PDF files
├── schema_keys/        # Input JSON schemas (keys only, values empty)
└── ground_truth/       # Expected mappings
```

---

## Ground truth format

Each PDF has a matching JSON file in `ground_truth/` with this structure:

```json
{
  "pdf": "financial/pdfs/investment_form.pdf",
  "schema": "financial/schema_keys/investment_schema.json",
  "total_fields": 42,
  "mappable_fields": 38,
  "fields": {
    "2": {
      "pdf_label": "Full Legal Name",
      "expected_key": "investor_full_legal_name_id",
      "confidence": 0.95
    },
    "3": {
      "pdf_label": "SSN / Tax ID",
      "expected_key": "investor_ssn_id",
      "confidence": 0.95
    },
    "7": {
      "pdf_label": "Signature",
      "expected_key": null,
      "confidence": 0
    }
  }
}
```

`expected_key: null` means the field intentionally has no mapping (e.g. signature boxes).

---

## Adding a new PDF

1. Place PDF in `<category>/pdfs/<name>.pdf`
2. Place schema keys in `<category>/schema_keys/<name>_schema.json`
3. Create ground truth in `<category>/ground_truth/<name>_gt.json`
4. Update the count in this README and in `<category>/README.md`
