# chatbot/pdf/fill_report.py
"""
FillReport — generates a field-level statistics report after a session completes.

Shows how many fields were in the config vs how many got filled,
broken down by mandatory/optional, and per field key.

Usage (automatic — triggered by ConversationEngine on session complete):
    report = FillReport.generate(
        form_config=form_config,
        investor_type="Individual",
        filled_data=final_output_flat,
        user_id="investor_123",
        session_id="session_abc",
    )
    storage.save_fill_report(user_id, session_id, report)

Or manually:
    from chatbot.pdf.fill_report import FillReport
    report = FillReport.generate(...)
    print(FillReport.format_text(report))
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


class FillReport:
    """
    Computes and formats fill statistics for a completed session.

    Report structure::

        {
            "generated_at": "2024-01-15T10:30:00Z",
            "user_id": "investor_123",
            "session_id": "session_abc",
            "investor_type": "Individual",
            "summary": {
                "total_fields_in_config": 42,
                "total_fields_filled": 38,
                "fill_rate_pct": 90.5,
                "mandatory_total": 20,
                "mandatory_filled": 20,
                "mandatory_fill_rate_pct": 100.0,
                "optional_total": 22,
                "optional_filled": 18,
                "optional_fill_rate_pct": 81.8,
            },
            "fields": {
                "filled": ["first_name", "last_name", ...],
                "missing_mandatory": [],
                "missing_optional": ["middle_name", ...],
            }
        }
    """

    @staticmethod
    def generate(
        form_config,
        investor_type: str,
        filled_data: dict,
        user_id: str = "",
        session_id: str = "",
    ) -> dict:
        """
        Generate fill statistics report.

        Args:
            form_config:   FormConfig instance (to read config field lists).
            investor_type: Selected investor type (e.g. "Individual").
            filled_data:   The final_output_flat dict — keys are field paths, values are filled values.
            user_id:       For report metadata.
            session_id:    For report metadata.

        Returns:
            Report dict (JSON-serialisable).
        """
        from chatbot.utils.dict_utils import flatten_dict

        # Get all fields for this investor type
        type_keys = form_config.get_form_keys_for_type(investor_type)
        all_config_fields = set(flatten_dict(type_keys).keys())

        # Get mandatory fields for this investor type
        mandatory_raw = form_config.get_mandatory_fields_for_type(investor_type)
        mandatory_fields = set(flatten_dict(mandatory_raw).keys()) if mandatory_raw else set()

        optional_fields = all_config_fields - mandatory_fields

        # Determine which fields are filled (non-empty value)
        filled_keys = {
            k for k, v in filled_data.items()
            if v not in (None, "", [], {})
        }

        # Intersection with config fields (ignore any extra keys from extraction)
        filled_in_config = filled_keys & all_config_fields

        mandatory_filled = mandatory_fields & filled_in_config
        mandatory_missing = mandatory_fields - filled_in_config

        optional_filled = optional_fields & filled_in_config
        optional_missing = optional_fields - filled_in_config

        total = len(all_config_fields)
        total_filled = len(filled_in_config)

        def pct(num, den):
            return round(num / den * 100, 1) if den > 0 else 0.0

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "session_id": session_id,
            "investor_type": investor_type,
            "summary": {
                "total_fields_in_config": total,
                "total_fields_filled": total_filled,
                "fill_rate_pct": pct(total_filled, total),
                "mandatory_total": len(mandatory_fields),
                "mandatory_filled": len(mandatory_filled),
                "mandatory_fill_rate_pct": pct(len(mandatory_filled), len(mandatory_fields)),
                "optional_total": len(optional_fields),
                "optional_filled": len(optional_filled),
                "optional_fill_rate_pct": pct(len(optional_filled), len(optional_fields)),
            },
            "fields": {
                "filled": sorted(filled_in_config),
                "missing_mandatory": sorted(mandatory_missing),
                "missing_optional": sorted(optional_missing),
            },
        }
        return report

    @staticmethod
    def format_text(report: dict) -> str:
        """
        Return a human-readable text summary of the report.

        Example output::

            ═══════════════════════════════════════
             FILL REPORT — Individual
             Session: session_abc  |  2024-01-15 10:30 UTC
            ═══════════════════════════════════════

            OVERALL       38 / 42 fields filled  (90.5%)
            MANDATORY     20 / 20 filled          (100.0%)  ✓
            OPTIONAL      18 / 22 filled          (81.8%)

            MISSING MANDATORY (0):
              None — all mandatory fields complete

            MISSING OPTIONAL (4):
              • middle_name
              • fax_number
              • secondary_email
              • linkedin_url
            ═══════════════════════════════════════
        """
        s = report["summary"]
        f = report["fields"]
        inv = report.get("investor_type", "")
        ts = report.get("generated_at", "")[:16].replace("T", " ")
        sid = report.get("session_id", "")

        mandatory_ok = "✓" if s["mandatory_fill_rate_pct"] == 100.0 else "⚠"
        divider = "═" * 45

        lines = [
            divider,
            f" FILL REPORT — {inv}",
            f" Session: {sid}  |  {ts} UTC",
            divider,
            "",
            f"{'OVERALL':<14} {s['total_fields_filled']} / {s['total_fields_in_config']} fields filled"
            f"  ({s['fill_rate_pct']}%)",
            f"{'MANDATORY':<14} {s['mandatory_filled']} / {s['mandatory_total']} filled"
            f"  ({s['mandatory_fill_rate_pct']}%)  {mandatory_ok}",
            f"{'OPTIONAL':<14} {s['optional_filled']} / {s['optional_total']} filled"
            f"  ({s['optional_fill_rate_pct']}%)",
            "",
        ]

        missing_mandatory = f["missing_mandatory"]
        lines.append(f"MISSING MANDATORY ({len(missing_mandatory)}):")
        if missing_mandatory:
            for field in missing_mandatory:
                lines.append(f"  • {field}")
        else:
            lines.append("  None — all mandatory fields complete")

        lines.append("")
        missing_optional = f["missing_optional"]
        lines.append(f"MISSING OPTIONAL ({len(missing_optional)}):")
        if missing_optional:
            for field in missing_optional[:20]:  # cap at 20 for readability
                lines.append(f"  • {field}")
            if len(missing_optional) > 20:
                lines.append(f"  ... and {len(missing_optional) - 20} more")
        else:
            lines.append("  None")

        lines.append(divider)
        return "\n".join(lines)
