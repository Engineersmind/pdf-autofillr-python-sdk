# src/ragpdf/services/analytics_service.py
import logging
from datetime import datetime
from ragpdf.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Query metrics, time series, system info, and error analytics.
    Supports metric_type: pdf | category | subcategory | doctype |
                          global | compare | pdf_hash | system_info
    """

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def get_metrics(self, body: dict) -> dict:
        mt = body.get("metric_type")
        dispatch = {
            "pdf":         self._pdf_metrics,
            "category":    self._category_metrics,
            "subcategory": self._subcategory_metrics,
            "doctype":     self._doctype_metrics,
            "global":      self._global_metrics,
            "compare":     self._compare_pdfs,
            "pdf_hash":    self._pdf_hash_metrics,
            "system_info": lambda _: self._system_info(),
        }
        fn = dispatch.get(mt)
        if not fn:
            raise ValueError(f"Unknown metric_type: {mt}")
        return fn(body)

    def _pdf_metrics(self, body):
        uid, sid, pid = body.get("user_id"), body.get("session_id"), body.get("pdf_id")
        if not all([uid, sid, pid]):
            raise ValueError("user_id, session_id, pdf_id required")
        base = f"predictions/{uid}/{sid}/{pid}"
        snap    = self.storage.load_json(f"{base}/analysis/metrics_snapshot.json")
        updated = self.storage.load_json(f"{base}/errors/metrics_snapshot_updated.json")
        sub     = self.storage.load_json(f"{base}/metadata/submission_info.json")
        pdf     = self.storage.load_json(f"{base}/metadata/pdf_info.json")
        cc      = self.storage.load_json(f"{base}/analysis/case_classification.json")
        ea      = self.storage.load_json(f"{base}/errors/error_analysis.json")
        return {
            "user_id": uid, "session_id": sid, "pdf_id": pid,
            "submission_id": sub.get("submission_id") if sub else None,
            "pdf_hash":      pdf.get("pdf_hash") if pdf else None,
            "initial_metrics": snap, "current_metrics": updated or snap,
            "case_classification": cc.get("case_breakdown") if cc else None,
            "errors": ea.get("errors", []) if ea else [],
        }

    def _category_metrics(self, body):
        cat = body.get("category")
        if not cat: raise ValueError("category required")
        ts = self.storage.load_json(f"metrics/time_series/category/{cat}/time_series.json")
        if not ts: return {"metric_type": "category", "category": cat, "time_series": [], "aggregated": None}
        entries = ts.get("entries", [])
        return {"metric_type": "category", "category": cat,
                "time_range": {"start": ts["metadata"]["first_entry"], "end": ts["metadata"]["last_entry"]} if ts.get("metadata") else None,
                "time_series": entries, "aggregated": _agg(entries)}

    def _subcategory_metrics(self, body):
        cat, sub = body.get("category"), body.get("subcategory")
        if not all([cat, sub]): raise ValueError("category and subcategory required")
        ts = self.storage.load_json(f"metrics/time_series/subcategory/{cat}/{sub}/time_series.json")
        return {"metric_type": "subcategory", "category": cat, "subcategory": sub,
                "time_series": ts.get("entries", []) if ts else []}

    def _doctype_metrics(self, body):
        cat, sub, doc = body.get("category"), body.get("subcategory"), body.get("doctype")
        if not all([cat, sub, doc]): raise ValueError("category, subcategory, doctype required")
        ts = self.storage.load_json(f"metrics/time_series/doctype/{cat}/{sub}/{doc}/time_series.json")
        return {"metric_type": "doctype", "category": cat, "subcategory": sub, "doctype": doc,
                "time_series": ts.get("entries", []) if ts else []}

    def _global_metrics(self, body):
        ts = self.storage.load_json("metrics/time_series/global/time_series.json")
        if not ts: return {"metric_type": "global", "overall_stats": None, "llm_vs_rag": None, "time_series": []}
        entries = ts.get("entries", [])
        if not entries: return {"metric_type": "global", "overall_stats": None, "llm_vs_rag": None, "time_series": []}

        def avg(k): vs=[e["metrics"][k] for e in entries if e["metrics"].get(k) is not None]; return round(sum(vs)/len(vs),4) if vs else 0.0
        def tot(k): return sum(e["metrics"].get(k,0) for e in entries)
        def win_high(a,b): return "llm" if a>b else ("rag" if b>a else "tie")
        def win_low(a,b):  return "llm" if a<b else ("rag" if b<a else "tie")

        overall = {
            "total_pdfs_processed": len(entries),
            "total_fields_predicted": {"llm": tot("predicted_llm"), "rag": tot("predicted_rag"), "ensemble": tot("predicted_ensemble")},
            "total_errors":  {"llm": tot("errors_llm"), "rag": tot("errors_rag"), "ensemble": tot("errors_ensemble")},
            "avg_accuracy":  {"llm": avg("accuracy_llm"), "rag": avg("accuracy_rag"), "ensemble": avg("accuracy_ensemble")},
            "avg_coverage":  {"llm": avg("coverage_llm"), "rag": avg("coverage_rag"), "ensemble": avg("coverage_ensemble")},
            "avg_confidence":{"llm": avg("avg_conf_llm"), "rag": avg("avg_conf_rag"), "ensemble": avg("avg_conf_ensemble")},
            "agreement_rate": avg("agreement_rate"), "conflict_rate": avg("conflict_rate"),
            "recovery": {"rag_recovers_llm_misses": avg("rag_recovery"), "llm_recovers_rag_misses": avg("llm_recovery")},
        }
        llm_rag = {
            "accuracy":   {"llm": avg("accuracy_llm"),    "rag": avg("accuracy_rag"),    "winner": win_high(avg("accuracy_llm"), avg("accuracy_rag"))},
            "coverage":   {"llm": avg("coverage_llm"),    "rag": avg("coverage_rag"),    "winner": win_high(avg("coverage_llm"), avg("coverage_rag"))},
            "confidence": {"llm": avg("avg_conf_llm"),    "rag": avg("avg_conf_rag"),    "winner": win_high(avg("avg_conf_llm"), avg("avg_conf_rag"))},
            "errors":     {"llm": tot("errors_llm"),      "rag": tot("errors_rag"),      "winner": win_low(tot("errors_llm"), tot("errors_rag"))},
            "agreement_rate": avg("agreement_rate"), "conflict_rate": avg("conflict_rate"),
        }
        return {"metric_type": "global", "overall_stats": overall, "llm_vs_rag": llm_rag, "time_series": entries}

    def _compare_pdfs(self, body):
        pdfs = body.get("pdfs", [])
        if not pdfs: raise ValueError("pdfs array required")
        comparison = []
        for pdf in pdfs:
            uid, sid, pid = pdf.get("user_id"), pdf.get("session_id"), pdf.get("pdf_id")
            if not all([uid, sid, pid]): continue
            snap = self.storage.load_json(f"predictions/{uid}/{sid}/{pid}/analysis/metrics_snapshot.json")
            upd  = self.storage.load_json(f"predictions/{uid}/{sid}/{pid}/errors/metrics_snapshot_updated.json")
            cur  = upd or snap
            if cur:
                comparison.append({"user_id": uid, "session_id": sid, "pdf_id": pid,
                    "accuracy": cur["accuracy"]["accuracy_ensemble"],
                    "coverage": cur["coverage"]["coverage_ensemble"],
                    "errors":   cur["accuracy"]["errors_ensemble"]})
        return {"metric_type": "compare", "comparison": comparison}

    def _pdf_hash_metrics(self, body):
        ph = body.get("pdf_hash")
        if not ph: raise ValueError("pdf_hash required")
        mapping = self.storage.load_json("pdf_hash_mapping/mapping.json") or {}
        entry = mapping.get(ph)
        if not entry: return {"metric_type": "pdf_hash", "pdf_hash": ph, "found": False, "submissions": []}
        subs = []
        for s in entry.get("submissions", []):
            uid, sid, pid = s.get("user_id"), s.get("session_id"), s.get("pdf_id")
            base = f"predictions/{uid}/{sid}/{pid}"
            snap = self.storage.load_json(f"{base}/analysis/metrics_snapshot.json")
            upd  = self.storage.load_json(f"{base}/errors/metrics_snapshot_updated.json")
            ea   = self.storage.load_json(f"{base}/errors/error_analysis.json")
            subs.append({**s, "metrics": (upd or snap), "errors": ea.get("errors", []) if ea else [], "total_errors": len(ea.get("errors", [])) if ea else 0})
        return {"metric_type": "pdf_hash", "pdf_hash": ph, "found": True,
                "category": entry.get("category"), "sub_category": entry.get("sub_category"),
                "document_type": entry.get("document_type"), "total_submissions": entry.get("total_submissions", 0),
                "submissions": subs}

    def _system_info(self):
        mapping = self.storage.load_json("pdf_hash_mapping/mapping.json") or {}
        vdb = self.storage.load_json("vectors/vector_database.json") or {}
        vectors = vdb.get("vectors", [])
        all_users, all_sessions = set(), set()
        for e in mapping.values():
            for s in e.get("submissions", []):
                if s.get("user_id"): all_users.add(s["user_id"])
                if s.get("session_id"): all_sessions.add(s["session_id"])
        cats, subs, docs = {}, {}, {}
        for ph, e in mapping.items():
            cat, sub, doc = e.get("category","?"), e.get("sub_category","?"), e.get("document_type","?")
            cnt, tot = e.get("pdf_count",0), e.get("total_submissions",0)
            cats.setdefault(cat, {"pdf_count":0,"submission_count":0}); cats[cat]["pdf_count"]+=cnt; cats[cat]["submission_count"]+=tot
            sk=f"{cat}/{sub}"; subs.setdefault(sk,{"category":cat,"sub_category":sub,"pdf_count":0,"submission_count":0}); subs[sk]["pdf_count"]+=cnt; subs[sk]["submission_count"]+=tot
            dk=f"{cat}/{sub}/{doc}"; docs.setdefault(dk,{"category":cat,"sub_category":sub,"document_type":doc,"pdf_count":0,"submission_count":0}); docs[dk]["pdf_count"]+=cnt; docs[dk]["submission_count"]+=tot
        return {
            "metric_type": "system_info", "generated_at": datetime.utcnow().isoformat()+"Z",
            "summary": {"total_pdf_hashes": len(mapping),
                        "total_submissions": sum(e.get("total_submissions",0) for e in mapping.values()),
                        "total_unique_users": len(all_users), "total_unique_sessions": len(all_sessions),
                        "total_categories": len(cats), "total_subcategories": len(subs),
                        "total_document_types": len(docs), "total_vectors": len(vectors)},
            "categories": [{"category":k,**v} for k,v in sorted(cats.items())],
            "subcategories": [v for v in sorted(subs.values(), key=lambda x:(x["category"],x["sub_category"]))],
            "document_types": [v for v in sorted(docs.values(), key=lambda x:(x["category"],x["sub_category"],x["document_type"]))],
            "vector_db": {"total_vectors": len(vectors),
                          "last_updated": vdb.get("metadata",{}).get("last_updated"),
                          "sources": {"rag": sum(1 for v in vectors if v.get("prediction_source")=="rag"),
                                      "llm": sum(1 for v in vectors if v.get("prediction_source")=="llm"),
                                      "manual": sum(1 for v in vectors if v.get("prediction_source")=="manual")}},
        }

    def get_error_analytics(self, body: dict) -> dict:
        df, dt = body.get("date_from"), body.get("date_to")
        fc, fs, fd = body.get("category"), body.get("subcategory"), body.get("doctype")
        from datetime import timezone
        dt_from = datetime.fromisoformat(df.replace("Z","+00:00")) if df else None
        dt_to   = datetime.fromisoformat(dt.replace("Z","+00:00")) if dt else None
        mapping = self.storage.load_json("pdf_hash_mapping/mapping.json") or {}
        all_errors = []
        for ph, he in mapping.items():
            cat,sub,doc = he.get("category","?"), he.get("sub_category","?"), he.get("document_type","?")
            if fc and cat!=fc: continue
            if fs and sub!=fs: continue
            if fd and doc!=fd: continue
            for s in he.get("submissions",[]):
                uid,sid,pid = s.get("user_id"),s.get("session_id"),s.get("pdf_id")
                if not (uid and sid and pid): continue
                ea = self.storage.load_json(f"predictions/{uid}/{sid}/{pid}/errors/error_analysis.json")
                if not ea: continue
                for err in ea.get("errors",[]):
                    ts_str = err.get("timestamp") or ea.get("timestamp")
                    if ts_str and (dt_from or dt_to):
                        try:
                            ets = datetime.fromisoformat(ts_str.replace("Z","+00:00"))
                            if dt_from and ets < dt_from: continue
                            if dt_to   and ets > dt_to:   continue
                        except: pass
                    all_errors.append({**err, "submission_id":s.get("submission_id"),
                        "user_id":uid,"session_id":sid,"pdf_id":pid,
                        "pdf_hash":ph,"category":cat,"sub_category":sub,"document_type":doc,"timestamp":ts_str})
        by_cat,by_sub,by_doc,by_date,by_et,by_ct = {},{},{},{},{},{}
        for e in all_errors:
            by_cat[e["category"]] = by_cat.get(e["category"],0)+1
            sk=f"{e['category']}/{e['sub_category']}"; by_sub[sk]=by_sub.get(sk,0)+1
            dk=f"{e['category']}/{e['sub_category']}/{e['document_type']}"; by_doc[dk]=by_doc.get(dk,0)+1
            day=(e.get("timestamp") or "")[:10]
            if day: by_date[day]=by_date.get(day,0)+1
            et=e.get("error_type","unknown"); by_et[et]=by_et.get(et,0)+1
            ct=e.get("case_type","unknown");  by_ct[ct]=by_ct.get(ct,0)+1
        return {"filters_applied":{"date_from":df,"date_to":dt,"category":fc,"subcategory":fs,"doctype":fd},
                "total_errors": len(all_errors),
                "breakdown":{"by_category":[{"category":k,"error_count":v} for k,v in sorted(by_cat.items())],
                             "by_subcategory":[{"path":k,"error_count":v} for k,v in sorted(by_sub.items())],
                             "by_doctype":[{"path":k,"error_count":v} for k,v in sorted(by_doc.items())],
                             "by_date":[{"date":k,"error_count":v} for k,v in sorted(by_date.items())],
                             "by_error_type":[{"error_type":k,"error_count":v} for k,v in sorted(by_et.items())],
                             "by_case_type":[{"case_type":k,"error_count":v} for k,v in sorted(by_ct.items())]},
                "errors": all_errors}


def _agg(entries):
    if not entries: return None
    accs = [e["metrics"]["accuracy_ensemble"] for e in entries]
    covs = [e["metrics"]["coverage_ensemble"] for e in entries]
    errs = [e["metrics"]["errors_ensemble"] for e in entries]
    return {"avg_accuracy": round(sum(accs)/len(accs),4), "avg_coverage": round(sum(covs)/len(covs),4),
            "total_submissions": len(entries), "total_errors": sum(errs)}
