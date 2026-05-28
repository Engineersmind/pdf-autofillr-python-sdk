"""
run_all_tests.py
================
Complete test runner for pdf-autofillr-rag SDK.
Designed for the 113-vector LP subscription vector base with OpenAI embeddings.

Run from AAA/rag-sdk-final/ with venv active:
    python run_all_tests.py

Prerequisites:
    1. .env has OPENAI_API_KEY, RAGPDF_EMBEDDING_BACKEND=openai
    2. ragpdf_data/vectors/vector_database.json has 113 embedded vectors
       (run init_vector_db.py first if not done yet)
    3. ragpdf_data/input/llm_predictions_test.json  in place
    4. ragpdf_data/input/final_predictions_test.json in place
"""

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def green(s):
    return f"\033[92m{s}\033[0m"


def red(s):
    return f"\033[91m{s}\033[0m"


def cyan(s):
    return f"\033[96m{s}\033[0m"


def yellow(s):
    return f"\033[93m{s}\033[0m"


def bold(s):
    return f"\033[1m{s}\033[0m"


PASS = 0
FAIL = 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  {green('[PASS]')} {label}")
        PASS += 1
    else:
        print(f"  {red('[FAIL]')} {label}" + (f"  -- {detail}" if detail else ""))
        FAIL += 1


def section(title):
    print()
    print(cyan("=" * 65))
    print(cyan(f"  {title}"))
    print(cyan("=" * 65))


if not Path("ragpdf_data").exists():
    print(red("ERROR: Run from AAA/rag-sdk-final/"))
    sys.exit(1)

os.environ.setdefault("RAGPDF_STORAGE", "local")
os.environ.setdefault("RAGPDF_DATA_PATH", "./ragpdf_data")
os.environ.setdefault("RAGPDF_VECTOR_STORE", "local")

# ─────────────────────────────────────────────────────────────────────────────
section("0. ENVIRONMENT & VECTOR DB CHECK")
# ─────────────────────────────────────────────────────────────────────────────
check(".env exists", Path(".env").exists())
check(
    "OPENAI_API_KEY set",
    bool(os.environ.get("OPENAI_API_KEY", "")),
    "Add OPENAI_API_KEY to .env",
)
check(
    "vector_database.json",
    Path("ragpdf_data/vectors/vector_database.json").exists(),
    "Run: python init_vector_db.py --source ragpdf_data/vectors/source/vector_base.json",
)
check(
    "source/vector_base.json",
    Path("ragpdf_data/vectors/source/vector_base.json").exists(),
)
check("sample_errors.json", Path("ragpdf_data/input/sample_errors.json").exists())
check(
    "llm_predictions_test",
    Path("ragpdf_data/input/llm_predictions_test.json").exists(),
    "Copy to ragpdf_data/input/",
)
check(
    "final_predictions_test",
    Path("ragpdf_data/input/final_predictions_test.json").exists(),
    "Copy to ragpdf_data/input/",
)

db_path = Path("ragpdf_data/vectors/vector_database.json")
vecs = []
if db_path.exists():
    db = json.loads(db_path.read_text())
    vecs = db["vectors"]
    emb_ok = [
        v for v in vecs if v.get("embedding") and any(x != 0 for x in v["embedding"])
    ]
    emb_miss = len(vecs) - len(emb_ok)
    check(f"vector DB has {len(vecs)} vectors", len(vecs) >= 10)
    check(
        f"all vectors embedded ({emb_miss} missing)",
        emb_miss == 0,
        f"{emb_miss} unembedded — run init_vector_db.py",
    )
    dim = len(emb_ok[0]["embedding"]) if emb_ok else 0
    print(
        f"  {bold(str(len(vecs)))} vectors  |  dim={dim}  |  backend="
        f"{os.environ.get('RAGPDF_EMBEDDING_BACKEND','openai')}"
    )

# ─────────────────────────────────────────────────────────────────────────────
section("1. UNIT TESTS  (noop backends — no API keys)")
# ─────────────────────────────────────────────────────────────────────────────
env_noop = {
    **os.environ,
    "RAGPDF_EMBEDDING_BACKEND": "noop",
    "RAGPDF_CORRECTOR_BACKEND": "noop",
}
r = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/unit/", "-v", "--tb=short"],
    capture_output=True,
    text=True,
    env=env_noop,
)
tail = r.stdout[-4000:] if len(r.stdout) > 4000 else r.stdout
print(tail)
lines = r.stdout.splitlines()
passed = sum(1 for ln in lines if " PASSED" in ln)
failed = sum(1 for ln in lines if " FAILED" in ln)
check(f"unit tests: {passed} passed, {failed} failed", failed == 0)

# ─────────────────────────────────────────────────────────────────────────────
section("2. EMBEDDING SANITY CHECK  (5 vectors self-match via OpenAI)")
# ─────────────────────────────────────────────────────────────────────────────
sanity_code = r"""
import json, os, sys, numpy as np
from dotenv import load_dotenv; load_dotenv()
os.environ.setdefault("RAGPDF_STORAGE","local")
os.environ.setdefault("RAGPDF_DATA_PATH","./ragpdf_data")
os.environ.setdefault("RAGPDF_VECTOR_STORE","local")
from ragpdf.embeddings.factory import EmbeddingFactory
from sklearn.metrics.pairwise import cosine_similarity
db    = json.loads(open("ragpdf_data/vectors/vector_database.json").read())
vecs  = db["vectors"]
step  = max(1, len(vecs)//5)
samp  = [vecs[i] for i in range(0, len(vecs), step)][:5]
back  = EmbeddingFactory.create()
all_e = np.array([v["embedding"] for v in vecs])
out   = []
for v in samp:
    t = " ".join(x for x in [v.get("field_name",""),v.get("context",""),
                  v.get("section_context","")," ".join(v.get("headers",[]))] if x)
    q = np.array(back.embed(t)); q = q/(np.linalg.norm(q) or 1)
    s = cosine_similarity([q], all_e)[0]
    bi = int(np.argmax(s))
    out.append({"vid":v["vector_id"],"exp":v["field_name"],
                "got":vecs[bi]["field_name"],"conf":float(s[bi]),
                "ok":vecs[bi]["field_name"]==v["field_name"]})
print(json.dumps(out))
"""
tmp = Path("_sanity_tmp.py")
tmp.write_text(sanity_code)
r = subprocess.run([sys.executable, str(tmp)], capture_output=True, text=True)
tmp.unlink(missing_ok=True)
try:
    results = json.loads(r.stdout.strip().splitlines()[-1])
    print(f"\n  {'VID':<8} {'Expected':<38} {'Got':<38} {'Conf':>7}  Result")
    print(f"  {'-'*99}")
    correct = 0
    for res in results:
        ok = res["ok"]
        if ok:
            correct += 1
        flag = green("PASS") if ok else red("FAIL")
        print(
            f"  {res['vid']:<8} {res['exp']:<38} {res['got']:<38} {res['conf']:>7.4f}  {flag}"
        )
    check(
        f"sanity: {correct}/5 correct",
        correct >= 4,
        "check OPENAI_API_KEY and that all vectors are embedded",
    )
except Exception as e:
    print(yellow(r.stdout[-300:]))
    print(yellow(r.stderr[-200:]))
    check("sanity check ran", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("3. CLI — SYSTEM INFO")
# ─────────────────────────────────────────────────────────────────────────────
r = subprocess.run(
    [sys.executable, "-m", "ragpdf.entrypoints.cli", "system-info"],
    capture_output=True,
    text=True,
)
try:
    info = json.loads(r.stdout)
    tv = info["summary"]["total_vectors"]
    print(
        f"  total_vectors={tv}  total_submissions={info['summary']['total_submissions']}"
    )
    check("system-info: total_vectors >= 10", tv >= 10, f"got {tv}")
except Exception as e:
    print(r.stdout[:300])
    print(r.stderr[:200])
    check("system-info: valid JSON", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("4. CLI — PREDICT  (API 1)  5 fields built from source vectors")
# ─────────────────────────────────────────────────────────────────────────────
src_path = Path("ragpdf_data/vectors/source/vector_base.json")
if not src_path.exists():
    print(yellow("  SKIP — source/vector_base.json not found"))
    check("predict test ran", False, "No source file")
else:
    src_raw = json.loads(src_path.read_text())
    src_vecs = src_raw if isinstance(src_raw, list) else src_raw.get("vectors", [])
    step = max(1, len(src_vecs) // 5)
    test_sv = [src_vecs[i] for i in range(0, len(src_vecs), step)][:5]
    test_fields = [
        {
            "field_id": f"tf_{i+1:03d}",
            "field_name": v["field_name"],
            "context": v.get("context", ""),
            "section_context": v.get("section_context", ""),
            "headers": v.get("headers", []),
        }
        for i, v in enumerate(test_sv)
    ]
    expected = {f["field_id"]: f["field_name"] for f in test_fields}
    n_test = len(test_fields)

    tmp_fields = Path("_predict_fields_tmp.json")
    tmp_cat = Path("_predict_cat_tmp.json")
    tmp_fields.write_text(json.dumps(test_fields, indent=2))
    tmp_cat.write_text(
        json.dumps(
            {
                "category": "Private Markets",
                "sub_category": "Private Equity",
                "document_type": "LP Subscription Agreement",
            }
        )
    )

    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "ragpdf.entrypoints.cli",
            "predict",
            "--user",
            "test_u",
            "--session",
            "test_s",
            "--pdf",
            "test_p",
            "--fields",
            str(tmp_fields),
            "--hash",
            "testhash001",
            "--category",
            str(tmp_cat),
        ],
        capture_output=True,
        text=True,
    )
    tmp_fields.unlink(missing_ok=True)
    tmp_cat.unlink(missing_ok=True)

    print(r.stdout)
    if r.returncode != 0 and r.stderr:
        print(yellow(r.stderr[-300:]))

    preds_path = Path(
        "ragpdf_data/predictions/test_u/test_s/test_p/predictions/rag_predictions.json"
    )
    sub_path = Path(
        "ragpdf_data/predictions/test_u/test_s/test_p/metadata/submission_info.json"
    )
    check("rag_predictions.json created", preds_path.exists())
    check("submission_info.json created", sub_path.exists())

    if preds_path.exists():
        preds = json.loads(preds_path.read_text())
        matched = preds["summary"]["predicted_fields"]
        total = preds["summary"]["total_fields"]
        avg_c = preds["summary"]["avg_confidence"]
        print(f"\n  Predicted {matched}/{total}  avg_confidence={avg_c:.4f}\n")
        print(f"  {'FID':<10} {'Got':<40} {'Expected':<40} {'Conf':>7}  Result")
        print(f"  {'-'*105}")
        correct = 0
        for fid, p in preds["predictions"].items():
            exp = expected.get(fid, "?")
            if p:
                ok = p["predicted_field_name"] == exp
                if ok:
                    correct += 1
                flag = green("PASS") if ok else red("FAIL")
                print(
                    f"  {fid:<10} {p['predicted_field_name']:<40} {exp:<40} {p['confidence']:>7.4f}  {flag}"
                )
            else:
                print(f"  {fid:<10} {'None':<40} {exp:<40} {'':>7}  {red('MISS')}")
        print(f"  {'-'*105}")
        check(
            f"predict: {correct}/{n_test} correct",
            correct == n_test,
            f"{correct}/{n_test}",
        )
        check("predict: avg_confidence >= 0.75", avg_c >= 0.75, f"{avg_c:.4f}")
        check(
            f"predict: all {n_test} fields matched",
            matched == n_test,
            f"{matched}/{n_test}",
        )

# ─────────────────────────────────────────────────────────────────────────────
section("5. PROCESSING PIPELINE  (API 2)")
# ─────────────────────────────────────────────────────────────────────────────
llm_p = Path("ragpdf_data/input/llm_predictions_test.json")
final_p = Path("ragpdf_data/input/final_predictions_test.json")
if not llm_p.exists() or not final_p.exists():
    print(
        yellow("  SKIP — copy llm_predictions_test.json + final_predictions_test.json")
    )
    print(yellow("         to ragpdf_data/input/"))
else:
    r = subprocess.run([sys.executable, "test_api2.py"], capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(yellow(r.stderr[-300:]))

    cc = Path(
        "ragpdf_data/predictions/user_test/session_test/pdf_test/analysis/case_classification.json"
    )
    ms = Path(
        "ragpdf_data/predictions/user_test/session_test/pdf_test/analysis/metrics_snapshot.json"
    )
    vu = Path(
        "ragpdf_data/predictions/user_test/session_test/pdf_test/analysis/vector_update_summary.json"
    )
    check("case_classification.json created", cc.exists())
    check("metrics_snapshot.json created", ms.exists())
    check("vector_update_summary.json created", vu.exists())
    if ms.exists():
        snap = json.loads(ms.read_text())
        acc = snap["accuracy"]["accuracy_ensemble"]
        cov = snap["coverage"]["coverage_ensemble"]
        print(f"\n  accuracy_ensemble={acc}  coverage_ensemble={cov}")
        check("API2: accuracy_ensemble = 1.0", acc == 1.0, f"got {acc}")
        check("API2: coverage_ensemble = 1.0", cov == 1.0, f"got {cov}")

# ─────────────────────────────────────────────────────────────────────────────
section("6. FEEDBACK  (API 4)  noop corrector — no API call")
# ─────────────────────────────────────────────────────────────────────────────
# First build API-2 data for test_u/test_s/test_p so feedback has files to read.
preds_path = Path(
    "ragpdf_data/predictions/test_u/test_s/test_p/predictions/rag_predictions.json"
)
if not preds_path.exists():
    print(yellow("  SKIP — run predict (section 4) first"))
else:
    # Build minimal API-2 from the predict output
    api2_code = """
import json, os
from dotenv import load_dotenv; load_dotenv()
os.environ.setdefault("RAGPDF_STORAGE","local")
os.environ.setdefault("RAGPDF_DATA_PATH","./ragpdf_data")
os.environ.setdefault("RAGPDF_VECTOR_STORE","local")
from ragpdf import RAGPDFClient
client = RAGPDFClient.from_env()
rag = json.loads(open("ragpdf_data/predictions/test_u/test_s/test_p/predictions/rag_predictions.json").read())
fp  = {fid: p for fid, p in rag["predictions"].items() if p}
llm = {"user_id":"test_u","session_id":"test_s","pdf_id":"test_p","model":"llm",
       "predictions":{fid:{"predicted_field_name":p["predicted_field_name"],"confidence":p["confidence"]}
                      for fid,p in fp.items()},
       "summary":{"total_fields":len(fp),"predicted_fields":len(fp),"unpredicted_fields":0,"avg_confidence":0.9}}
fin = {"user_id":"test_u","session_id":"test_s","pdf_id":"test_p",
       "final_predictions":{fid:{"selected_field_name":p["predicted_field_name"],
                                  "selected_from":"rag","rag_confidence":p["confidence"],
                                  "llm_confidence":p["confidence"]} for fid,p in fp.items()}}
r = client.save_filled_pdf(user_id="test_u",session_id="test_s",pdf_id="test_p",
                            llm_predictions=llm,final_predictions=fin)
print("api2_done:", r.get("submission_id","?"))
"""
    tmp_a2 = Path("_api2_fb_tmp.py")
    tmp_a2.write_text(api2_code)
    subprocess.run([sys.executable, str(tmp_a2)], capture_output=True)
    tmp_a2.unlink(missing_ok=True)

    # Pick any matched field for the error
    rag_data = json.loads(preds_path.read_text())
    fp_dict = {fid: p for fid, p in rag_data["predictions"].items() if p}
    err_field = (
        list(fp_dict.values())[0]["predicted_field_name"]
        if fp_dict
        else "investor_type"
    )

    tmp_err = Path("_errors_tmp.json")
    tmp_err.write_text(
        json.dumps(
            [
                {
                    "error_type": "wrong_field_name",
                    "field_name": err_field,
                    "field_type": "text",
                    "value": "test_value",
                    "feedback": "Testing feedback pipeline",
                    "page_number": 1,
                }
            ]
        )
    )
    env_n = {**os.environ, "RAGPDF_CORRECTOR_BACKEND": "noop"}
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "ragpdf.entrypoints.cli",
            "feedback",
            "--user",
            "test_u",
            "--session",
            "test_s",
            "--pdf",
            "test_p",
            "--errors",
            str(tmp_err),
        ],
        capture_output=True,
        text=True,
        env=env_n,
    )
    tmp_err.unlink(missing_ok=True)
    print(r.stdout)
    if r.returncode != 0:
        print(yellow(r.stderr[-200:]))

    fb_path = Path(
        "ragpdf_data/predictions/test_u/test_s/test_p/errors/user_feedback_raw.jsonl"
    )
    check("feedback: user_feedback_raw.jsonl created", fb_path.exists())
    try:
        fb = json.loads(r.stdout)
        check("feedback: errors_processed >= 1", fb.get("errors_processed", 0) >= 1)
        check("feedback: vectors_updated >= 1", fb.get("vectors_updated", 0) >= 1)
    except Exception:
        check("feedback: returned valid JSON", False, r.stdout[:100])

# ─────────────────────────────────────────────────────────────────────────────
section("7. METRICS  (API 5)")
# ─────────────────────────────────────────────────────────────────────────────
for args, label, key in [
    (["--type", "global"], "global", "overall_stats"),
    (
        ["--type", "pdf", "--user", "test_u", "--session", "test_s", "--pdf", "test_p"],
        "pdf",
        "submission_id",
    ),
    (
        ["--type", "category", "--category", "Private Markets"],
        "category",
        "time_series",
    ),
]:
    r = subprocess.run(
        [sys.executable, "-m", "ragpdf.entrypoints.cli", "metrics"] + args,
        capture_output=True,
        text=True,
    )
    try:
        d = json.loads(r.stdout)
        check(f"metrics {label}: '{key}' present", key in d)
    except Exception:
        print(r.stdout[:200])
        print(r.stderr[:100])
        check(f"metrics {label}: valid JSON", False)

# ─────────────────────────────────────────────────────────────────────────────
section("8. LAMBDA HANDLER — local")
# ─────────────────────────────────────────────────────────────────────────────
src_raw = (
    json.loads(Path("ragpdf_data/vectors/source/vector_base.json").read_text())
    if Path("ragpdf_data/vectors/source/vector_base.json").exists()
    else []
)
src_list = src_raw if isinstance(src_raw, list) else src_raw.get("vectors", [])
lf = (
    src_list[0]
    if src_list
    else {
        "field_name": "investor_type",
        "context": "Type of investor entity",
        "section_context": "Investor Classification",
        "headers": ["Investor Information"],
    }
)

lambda_code = f"""
import json, os
from dotenv import load_dotenv; load_dotenv()
os.environ.setdefault("RAGPDF_STORAGE","local")
os.environ.setdefault("RAGPDF_DATA_PATH","./ragpdf_data")
os.environ.setdefault("RAGPDF_VECTOR_STORE","local")
from ragpdf.entrypoints.aws_lambda import lambda_handler
out = {{}}
# system_info
b = json.loads(lambda_handler({{"headers":{{"x-api-key":"dev-key"}},"body":json.dumps({{"api_name":"get_system_info"}})}},None)["body"])
out["si_status"]  = b["status"]
out["si_vectors"] = b["data"]["vector_db"]["total_vectors"]
# predict
field = {json.dumps(lf)}
payload = {{"api_name":"get_rag_predictions","user_id":"lu","session_id":"ls",
            "pdf_id":"lp","pdf_hash":"lhash001",
            "pdf_category":{{"category":"Private Markets","sub_category":"Private Equity","document_type":"LP"}},
            "fields":[{{"field_id":"lf001","field_name":field["field_name"],
                        "context":field.get("context",""),"section_context":field.get("section_context",""),
                        "headers":field.get("headers",[])}}]}}
b2 = json.loads(lambda_handler({{"headers":{{"x-api-key":"dev-key"}},"body":json.dumps(payload)}},None)["body"])
out["pred_status"]  = b2["status"]
out["pred_matched"] = b2["data"]["summary"]["predicted_fields"]
# predictions are saved to file, not in the lambda response dict
preds_path = "ragpdf_data/predictions/lu/ls/lp/predictions/rag_predictions.json"
if os.path.exists(preds_path):
    pf = json.loads(open(preds_path).read())
    pv = [p for p in pf["predictions"].values() if p]
    out["pred_name"] = pv[0]["predicted_field_name"] if pv else "None"
else:
    out["pred_name"] = "file_not_found"
# bad key + bad api
out["bad_key"] = lambda_handler({{"headers":{{"x-api-key":"wrongkey"}},"body":json.dumps({{"api_name":"get_system_info"}})}},None)["statusCode"]
out["bad_api"] = lambda_handler({{"headers":{{"x-api-key":"dev-key"}},"body":json.dumps({{"api_name":"not_real"}})}},None)["statusCode"]
print(json.dumps(out))
"""
tmp = Path("_lambda_tmp.py")
tmp.write_text(lambda_code)
r = subprocess.run([sys.executable, str(tmp)], capture_output=True, text=True)
tmp.unlink(missing_ok=True)
try:
    res = json.loads(r.stdout.strip().splitlines()[-1])
    print(f"  system_info:  {res['si_status']}  vectors={res['si_vectors']}")
    print(
        f"  predict:      {res['pred_status']}  matched={res['pred_matched']}/1  -> {res.get('pred_name','?')}"
    )
    print(f"  bad key:      HTTP {res['bad_key']}")
    print(f"  bad api:      HTTP {res['bad_api']}")
    check("lambda: system_info success", res["si_status"] == "success")
    check("lambda: total_vectors >= 10", res["si_vectors"] >= 10)
    check(
        "lambda: predict success 1/1",
        res["pred_status"] == "success" and res["pred_matched"] == 1,
    )
    check(
        "lambda: predicted correct field",
        res.get("pred_name") == lf["field_name"],
        f"got '{res.get('pred_name')}' expected '{lf['field_name']}'",
    )
    check("lambda: bad key -> 401", res["bad_key"] == 401)
    check("lambda: bad api_name -> 400", res["bad_api"] == 400)
except Exception as e:
    print(r.stdout[-400:])
    print(r.stderr[-200:])
    check("lambda test completed", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("9. ACCURACY BENCHMARK — all 113 vectors self-match")
# ─────────────────────────────────────────────────────────────────────────────
# Every vector's own context, when re-embedded, must map back to itself.
# Uses embed_batch in batches of 50 = 3 API calls total (~$0.001).

bench_code = r"""
import json, os, sys, numpy as np
from dotenv import load_dotenv; load_dotenv()
os.environ.setdefault("RAGPDF_STORAGE","local")
os.environ.setdefault("RAGPDF_DATA_PATH","./ragpdf_data")
os.environ.setdefault("RAGPDF_VECTOR_STORE","local")
from sklearn.metrics.pairwise import cosine_similarity
from ragpdf.embeddings.factory import EmbeddingFactory

db   = json.loads(open("ragpdf_data/vectors/vector_database.json").read())
vecs = db["vectors"]
all_embs  = np.array([v["embedding"] for v in vecs])
all_names = [v["field_name"] for v in vecs]

src_raw = json.loads(open("ragpdf_data/vectors/source/vector_base.json").read())
src     = src_raw if isinstance(src_raw, list) else src_raw.get("vectors", [])

backend = EmbeddingFactory.create()
BATCH   = 50

texts = []
for v in src:
    t = " ".join(x for x in [v.get("field_name",""), v.get("context",""),
                  v.get("section_context",""), " ".join(v.get("headers",[]))] if x)
    texts.append(t)

embeddings = []
for i in range(0, len(texts), BATCH):
    batch_embs = backend.embed_batch(texts[i:i+BATCH])
    embeddings.extend(batch_embs)
    sys.stderr.write(f"  Embedded {min(i+BATCH,len(texts))}/{len(texts)}...\r")
sys.stderr.write("\n")

correct = 0
fails   = []
for v, emb in zip(src, embeddings):
    q      = np.array(emb); q = q / (np.linalg.norm(q) or 1)
    sims   = cosine_similarity([q], all_embs)[0]
    best_i = int(np.argmax(sims))
    got    = all_names[best_i]
    conf   = float(sims[best_i])
    ok     = got == v["field_name"]
    if ok:
        correct += 1
    else:
        fails.append({"vid": v["vector_id"], "expected": v["field_name"],
                      "got": got, "conf": conf})
print(json.dumps({"correct": correct, "total": len(src), "fails": fails}))
"""
bench = Path("_bench_tmp.py")
bench.write_text(bench_code)
print(f"  Embedding {len(src_list)} source vectors in batches of 50...")
print(f"  ({max(1, (len(src_list)+49)//50)} API calls  ~$0.001 total)\n")
r = subprocess.run(
    [sys.executable, str(bench)], capture_output=True, text=True, timeout=180
)
bench.unlink(missing_ok=True)

if r.stderr:
    print(yellow(f"  {r.stderr.strip()}"))
try:
    out = json.loads(r.stdout.strip().splitlines()[-1])
    correct = out["correct"]
    total = out["total"]
    fails = out["fails"]
    pct = correct / total * 100 if total else 0

    print(f"\n  Accuracy: {bold(f'{correct}/{total}')}  ({pct:.1f}%)\n")
    if fails:
        print(f"  {red(f'{len(fails)} mismatches:')}")
        print(f"  {'VID':<8} {'Expected':<40} {'Got':<40} {'Conf':>7}")
        print(f"  {'-'*98}")
        for row in fails:
            print(
                f"  {row['vid']:<8} {row['expected']:<40} {row['got']:<40} {row['conf']:>7.4f}"
            )
    else:
        print(f"  {green('Perfect — every vector maps back to itself.')}")

    check(
        f"benchmark: {correct}/{total} correct",
        correct == total,
        f"{total-correct} mismatches — check init_vector_db.py was run with same model",
    )
    check("benchmark: accuracy >= 95%", pct >= 95.0, f"got {pct:.1f}%")
except Exception as e:
    print(r.stdout[-400:])
    print(r.stderr[-200:])
    check("benchmark completed", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("SUMMARY")
# ─────────────────────────────────────────────────────────────────────────────
total_checks = PASS + FAIL
print(f"\n  {green(f'PASSED: {PASS}/{total_checks}')}")
if FAIL:
    print(f"  {red(f'FAILED: {FAIL}/{total_checks}')}")
print()
if FAIL == 0:
    print(green("ALL TESTS PASSED"))
    print()
    print("Next:")
    print(
        "  Server tests:    python test_api_server.py  (start server first in another terminal)"
    )
    print("  OpenAI feedback: python test_feedback_openai.py")
else:
    print(red("Some tests failed — see above."))
    sys.exit(1)
