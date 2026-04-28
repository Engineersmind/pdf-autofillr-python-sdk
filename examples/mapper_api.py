"""
Mapper — call via REST API.

Start the server first: pdf-mapper-server
Requires: pip install httpx
"""
import httpx

BASE = "http://localhost:8000"

print(httpx.get(f"{BASE}/health").json())

with open("data/input/blank_form.pdf", "rb") as f:
    r = httpx.post(f"{BASE}/embed", files={"pdf": f}, data={
        "user_id": "user_001",
        "pdf_doc_id": "lp_sub_v1",
    })
print("Embed:", r.json())

with open("data/input/blank_form.pdf", "rb") as f:
    r = httpx.post(f"{BASE}/fill", files={"pdf": f}, data={
        "user_id": "user_001",
        "pdf_doc_id": "lp_sub_v1",
        "user_data": '{"investor_name": "Jane Smith", "commitment_amount": "500000"}',
    })
print("Fill:", r.json())
