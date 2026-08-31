"""Private operator surface; no source configuration or credentials are rendered."""
from __future__ import annotations

from html import escape


def render_operator_html(control: dict[str, object]) -> str:
    def field(name: str, value: object) -> str:
        return f"<article><b>{escape(name)}</b><span id='{escape(name.lower().replace(' ', '-'))}'>{escape(str(value or '—'))}</span></article>"
    details = "".join((
        field("FRIDA STATUS", control.get("state")), field("HEARTBEAT", control.get("heartbeat")),
        field("OBSERVATION CADENCE", f"{control.get('cadence_seconds')} seconds"),
        field("LAST OBSERVATION", control.get("last_observation_at")), field("NEXT OBSERVATION", control.get("next_observation_at")),
        field("SOURCE HEALTH", control.get("source_health")),
    ))
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA Operator Control</title>
<style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.5 Georgia,serif}}main{{max-width:900px;margin:auto;padding:44px 24px}}.eyebrow{{font:700 12px Arial;letter-spacing:.12em;color:var(--teal)}}h1{{font-size:46px;line-height:1.05}}.notice{{border-left:5px solid var(--teal);background:#fff;padding:16px 18px;border-radius:12px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:24px 0}}article{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px}}article b{{display:block;font:700 11px Arial;letter-spacing:.07em;color:#516273}}article span{{display:block;margin-top:5px;font:700 16px Arial}}.controls{{display:flex;gap:10px;flex-wrap:wrap;align-items:end}}button{{border:0;border-radius:10px;padding:12px 16px;background:var(--ink);color:#fff;font:bold 13px Arial;cursor:pointer}}button.secondary{{background:#fff;border:1px solid var(--line);color:var(--ink)}}label{{font:bold 12px Arial}}input{{display:block;margin-top:6px;border:1px solid var(--line);border-radius:8px;padding:10px;width:130px}}#result{{min-height:24px;color:#147b79;font:13px Arial}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style>
<main><p class='eyebrow'>FRIDA · PRIVATE OPERATOR CONTROL</p><h1>Observation control</h1><p class='notice'>This surface controls only the generic observation clock. It cannot alter sources, evidence, governance, or public records. A scheduler wake-up never calls a model by itself.</p><section class='grid' id='control-state'>{details}</section><section class='controls'><label>CADENCE (SECONDS)<input id='cadence' type='number' min='60' max='86400' value='{escape(str(control.get('cadence_seconds',300)))}'></label><button data-action='start'>START</button><button class='secondary' data-action='pause'>PAUSE</button><button class='secondary' data-action='resume'>RESUME</button><button class='secondary' data-action='stop'>STOP</button></section><p id='result' aria-live='polite'></p></main>
<script>const result=document.getElementById('result');document.querySelectorAll('button[data-action]').forEach(button=>button.addEventListener('click',async()=>{{const action=button.dataset.action;const body=action==='start'?JSON.stringify({{cadence_seconds:Number(document.getElementById('cadence').value)}}):'{{}}';const r=await fetch('/api/v1/observation/'+action,{{method:'POST',headers:{{'Content-Type':'application/json'}},body}});if(!r.ok){{result.textContent='Control request was not accepted.';return}}result.textContent='FRIDA operational state updated. Refreshing…';location.reload()}}));</script></html>"""
