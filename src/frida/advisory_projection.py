"""Presentation-only views for persisted London advisory appraisals."""
from __future__ import annotations

from html import escape
from typing import Any
import json


def select_advisory(items: list[dict[str, Any]], record_id: str | None = None) -> dict[str, Any] | None:
    if record_id:
        return next((item for item in items if str(item["record_id"]) == record_id), None)
    return next((item for item in items if str(item.get("result", {}).get("strategic_interest")) == "POSSIBLE"), None)


def render_advisory_html(item: dict[str, Any]) -> str:
    value=item["result"]
    evidence=", ".join(str(x) for x in value.get("evidence_ids_used", [])) or "None"
    missing="".join(f"<li>{escape(str(x))}</li>" for x in value.get("missing_evidence", [])) or "<li>None retained.</li>"
    uncertainty="".join(f"<li>{escape(str(x))}</li>" for x in value.get("uncertainties", [])) or "<li>None retained.</li>"
    return f"""<!doctype html><title>FRIDA — Advisory</title><style>body{{margin:0;background:#f7f3eb;color:#10243a;font:17px/1.6 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.hero{{background:#10243a;color:#fff;border-radius:22px;padding:34px}}.eyebrow{{font:bold 12px Arial;letter-spacing:.12em;color:#147b79}}.flag{{color:#f3c66f;font:bold 14px Arial}}h1{{font-size:clamp(38px,6vw,64px);line-height:1.04}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:18px}}article{{background:#fff;border:1px solid #d8d0c3;border-radius:16px;padding:20px}}.button{{display:inline-block;background:#10243a;color:#fff;padding:12px 16px;border-radius:9px;text-decoration:none;font:bold 13px Arial}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style><main><p class='eyebrow'>FRIDA · LONDON STRATEGIC INTELLIGENCE</p><p><a class='button' href='/'>← BACK TO FRIDA</a></p><section class='hero'><p class='eyebrow'>PERSISTED FIRST APPRAISAL · NON-AUTHORIZING</p><p class='flag'>⚑ YELLOW FLAG · ADVISORY HYPOTHESIS</p><h1>{escape(str(value.get('strategic_question','Strategic question retained.')))}</h1><p>{escape(str(value.get('why_it_might_matter','Why it matters is retained in the governed appraisal.')))}</p></section><section class='grid'><article><b>SEMANTIC STATUS</b><p>POSSIBLE / {escape(str(value.get('opportunity_family','UNKNOWN')).replace('_',' '))}</p><p>This is not canonical FRIDA Attention, Signal, Candidate or Case.</p></article><article><b>BOUNDED RESEARCH STATUS</b><p>{'Warranted — held pending governance' if value.get('research_warranted') else 'Not requested'}</p><p>Requested next: {escape(', '.join(str(x) for x in value.get('allowed_context_requests',[])) or 'None')}</p></article><article><b>EVIDENCE & PROVENANCE</b><p>{escape(evidence)}</p></article><article><b>WHAT FRIDA DID NOT CLAIM</b><p>No causation, emergency, individual behaviour, policing outcome or final recommendation.</p></article></section><section class='grid'><article><h2>Missing evidence</h2><ul>{missing}</ul></article><article><h2>Uncertainty retained</h2><ul>{uncertainty}</ul></article></section><p><a class='button' href='/technical-record?appraisal_id={escape(str(item['record_id']))}'>VIEW RAW GOVERNED APPRAISAL RECORD</a></p></main>"""


def render_advisory_raw_html(item: dict[str, Any]) -> str:
    safe={"record_id":item["record_id"],"created_at":item["created_at"],"kind":item["kind"],"result":item["result"],"bundle":item["bundle"]}
    advisory_url = "/advisory?appraisal_id=" + escape(str(item["record_id"]))
    raw = escape(json.dumps(safe, indent=2, sort_keys=True, default=str))
    return f"""<!doctype html><title>FRIDA — Raw governed appraisal record</title>
<style>main.raw-governed-record{{max-width:1120px;margin:0 auto;padding:30px 24px 72px}}.raw-return{{display:inline-block;background:#fff;border:1px solid #d8d0c3;border-radius:10px;padding:10px 14px;color:#10243a;font:bold 13px Arial,sans-serif;text-decoration:none}}.raw-governed-record pre{{margin-top:22px;padding:18px;background:#fff;border:1px solid #d8d0c3;overflow:auto;white-space:pre-wrap;font:14px/1.45 Consolas,monospace}}</style>
<main class='raw-governed-record'><p><a class='raw-return' href='/'>← BACK TO FRIDA</a> <a class='raw-return' href='{advisory_url}'>BACK TO ADVISORY</a></p><p>RAW GOVERNED APPRAISAL RECORD · Read-only technical evidence</p><pre>{raw}</pre></main>"""
