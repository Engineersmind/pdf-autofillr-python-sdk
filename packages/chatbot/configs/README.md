# Config Samples

Copy this directory into your project as `./configs/` and edit each file to match your PDF field names.

## Files

| File | Description |
|------|-------------|
| `form_keys.json` | Master form structure — all possible fields across all investor types |
| `mandatory.json` | Required fields per investor type |
| `meta_form_keys.json` | Field type metadata (text vs boolean) |
| `field_questions.json` | Human-readable prompts per field (sequential fill) |
| `form_keys_label.json` | Short display labels for missing-fields lists |
| `global_investor_type_keys/` | Per-investor-type field subsets |

## Rules

- Field values must always be `""` (text) or `null` (boolean) — the chatbot fills them
- Boolean fields use 3-state system: `true` / `false` / `null`
- Fields ending `_id` are text fields; `_check` are booleans
- `mandatory.json` type names must exactly match `INVESTOR_TYPES` in `core/states.py`
