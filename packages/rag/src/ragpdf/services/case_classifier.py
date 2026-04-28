# src/ragpdf/services/case_classifier.py
import logging
from datetime import datetime
from ragpdf.utils.constants import CASE_A, CASE_B, CASE_C, CASE_D, CASE_E, SOURCE_RAG, SOURCE_LLM
from ragpdf.config.settings import PREDICTION_THRESHOLD

logger = logging.getLogger(__name__)


class CaseClassifier:
    """
    Classify each field into one of 5 cases based on RAG + LLM predictions.

    CASE_A — Both RAG and LLM predicted the SAME field name
    CASE_B — Both predicted DIFFERENT field names (conflict)
    CASE_C — Only LLM predicted (RAG confidence below threshold)
    CASE_D — Only RAG predicted (LLM confidence below threshold)
    CASE_E — Neither predicted (both below threshold)
    """

    def classify(self, user_id: str, session_id: str, pdf_id: str,
                 rag_predictions: dict, llm_predictions: dict,
                 final_predictions: dict) -> dict:

        case_breakdown = {
            CASE_A: {"count": 0, "field_ids": [], "description": "Both RAG and LLM predicted same field"},
            CASE_B: {"count": 0, "field_ids": [], "description": "Both predicted different fields",
                     "selections": {"rag_selected": 0, "llm_selected": 0}},
            CASE_C: {"count": 0, "field_ids": [], "description": "LLM predicted, RAG did not"},
            CASE_D: {"count": 0, "field_ids": [], "description": "RAG predicted, LLM did not"},
            CASE_E: {"count": 0, "field_ids": [], "description": "Neither predicted (below threshold)"},
        }

        for field_id, final_pred in final_predictions.items():
            rag_pred = rag_predictions.get(field_id)
            llm_pred = llm_predictions.get(field_id)

            rag_field = None
            if rag_pred and isinstance(rag_pred, dict):
                if rag_pred.get("confidence", 0) >= PREDICTION_THRESHOLD:
                    rag_field = rag_pred.get("predicted_field_name")

            llm_field = None
            if llm_pred and isinstance(llm_pred, dict):
                if llm_pred.get("confidence", 0) >= PREDICTION_THRESHOLD:
                    llm_field = llm_pred.get("predicted_field_name")

            if rag_field and llm_field and rag_field == llm_field:
                case = CASE_A
            elif rag_field and llm_field and rag_field != llm_field:
                case = CASE_B
                sel = final_pred.get("selected_from") if isinstance(final_pred, dict) else None
                if sel == SOURCE_RAG:
                    case_breakdown[CASE_B]["selections"]["rag_selected"] += 1
                elif sel == SOURCE_LLM:
                    case_breakdown[CASE_B]["selections"]["llm_selected"] += 1
            elif llm_field and not rag_field:
                case = CASE_C
            elif rag_field and not llm_field:
                case = CASE_D
            else:
                case = CASE_E

            case_breakdown[case]["count"] += 1
            case_breakdown[case]["field_ids"].append(field_id)

        result = {
            "user_id": user_id, "session_id": session_id, "pdf_id": pdf_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total_fields": len(final_predictions),
            "case_breakdown": case_breakdown,
        }
        logger.info(
            f"Case classification: A={case_breakdown[CASE_A]['count']} "
            f"B={case_breakdown[CASE_B]['count']} C={case_breakdown[CASE_C]['count']} "
            f"D={case_breakdown[CASE_D]['count']} E={case_breakdown[CASE_E]['count']}"
        )
        return result
