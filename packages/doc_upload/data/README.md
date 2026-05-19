# data/

This directory holds sample documents for local testing and functional tests.

## data/input/

Drop any source document here to use it with `python -m entrypoints.local`.

| File | Format | Use |
|------|--------|-----|
| `sample_investor.txt`  | Plain text | Quickest test — no extra deps |
| `sample_investor.json` | JSON       | Tests JSON reader path |
| `sample_investor.csv`  | CSV        | Tests CSV reader path |
| `sample_investor.md`   | Markdown   | Tests Markdown reader path |

To test PDF, DOCX, PPTX, or XLSX, place your own files here:
- `blank_form.pdf`    — a blank investor subscription PDF (used with PDF filling)
- `investor.docx`    — a Word document with investor details
- `investor.pptx`    — a PowerPoint with investor details
- `investor.xlsx`    — an Excel spreadsheet with investor details

## data/output/

Created automatically by the local runner. Contains extracted JSON files:

```
data/output/
└── {job_id}/
    ├── output.json           ← nested dict matching form_keys.json
    └── output_flat.json      ← dot-notation flat dict
```

## Running with a sample file

```bash
# Interactive
python -m entrypoints.local

# Non-interactive
python -m entrypoints.local \
    --document data/input/sample_investor.txt \
    --schema   configs/form_keys.json \
    --output   data/output/result.json
```