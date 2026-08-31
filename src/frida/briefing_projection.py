from html import escape
from typing import Any
STYLE="""<style>body{margin:0;background:#f7f3eb;color:#10243a;font:17px/1.6 Georgia,serif}main{max-width:1000px;margin:auto;padding:42px 24px 80px}.tag{color:#147b79;font:bold 12px Arial;letter-spacing:.11em}.brief-card,article{background:#fff;border:1px solid #d8d0c3;border-radius:18px;padding:24px;margin:16px 0;box-shadow:0 8px 24px #10243a0b}.brief-card h2{font-size:21px;line-height:1.3;margin:10px 0}.brief-card a,a{color:#10243a;font:bold 13px Arial;text-decoration:none}.brief-back{display:inline-block;background:#fff;border:1px solid #d8d0c3;border-radius:10px;padding:10px 14px;box-shadow:0 3px 10px #10243a0a}.hero{background:#10243a;color:#fff;border-radius:22px;padding:34px}.hero h1{font-size:clamp(24px,2.4vw,30px);line-height:1.25}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.posture{display:inline-flex;align-items:center;gap:6px;font:700 12px Arial,sans-serif;letter-spacing:.08em}.posture-flag{font-size:17px;line-height:1}.posture-green{color:#168254}.posture-yellow{color:#b27700}.posture-red{color:#b53838}.hero .posture{color:inherit}.hero .posture-green{color:#7de0aa}.hero .posture-yellow{color:#ffd561}.hero .posture-red{color:#ff9696}@media(max-width:650px){.grid{grid-template-columns:1fr}}</style>"""

def posture_badge(posture: object) -> str:
 value = str(posture).upper()
 tone = value.lower() if value in {"GREEN", "YELLOW", "RED"} else "green"
 return f"<span class='posture posture-{tone}'><span class='posture-flag' aria-hidden='true'>⚑</span>{escape(value)}</span>"

def render_briefings_html(items:list[dict[str,Any]])->str:
 current = sorted((item for item in items if not item.get('historical_as_of')), key=lambda item: str(item['created_at']), reverse=True)
 historical = sorted((item for item in items if item.get('historical_as_of')), key=lambda item: str(item['created_at']), reverse=True)
 ordered = [*current, *historical]
 def card(item: dict[str, Any]) -> str:
  historical_label = ('HISTORICAL STRATEGIC BRIEF · Evidence cutoff: ' + escape(str(item['historical_as_of']))) if item.get('historical_as_of') else 'CURRENT STRATEGIC BRIEF · Current authorized evidence window'
  return f"<article class='brief-card'><p class='tag'>{historical_label} · {posture_badge(item['brief']['executive_posture'])}</p><h2>{escape(str(item['brief']['executive_summary']))}</h2><p>Published {escape(str(item['created_at']))}</p><a href='/briefing?brief_id={escape(str(item['brief_id']))}'>OPEN BRIEF →</a></article>"
 rows=''.join(card(item) for item in ordered) or '<article><h2>No Strategic Brief has been published.</h2></article>'
 return f"<!doctype html><html><head><title>FRIDA — Strategic Briefings</title><link rel='icon' type='image/png' href='/assets/frida-logo.png'>{STYLE}</head><main><p><a class='brief-back' href='/'>← BACK TO FRIDA</a></p><p class='tag'>FRIDA · LONDON STRATEGIC MEMORY</p><h1>Strategic Briefings</h1><p>Durable, attributable FRIDA brief artifacts.</p><section>{rows}</section></main></html>"
def render_brief_html(item:dict[str,Any])->str:
 b,f=item['brief'],item['foresight']; lis=lambda v:''.join('<li>'+escape(str(x))+'</li>' for x in v)
 label=('HISTORICAL STRATEGIC BRIEF · Evidence cutoff: '+str(item['historical_as_of'])+' · Generated: '+str(item['created_at'])) if item.get('historical_as_of') else 'CURRENT STRATEGIC BRIEF · Current authorized evidence window · Generated: '+str(item['created_at'])
 title=('FRIDA — Historical Strategic Brief' if item.get('historical_as_of') else 'FRIDA — Current Strategic Brief')
 return f"<!doctype html><html><head><title>{title}</title><link rel='icon' type='image/png' href='/assets/frida-logo.png'>{STYLE}</head><main><p><a class='brief-back' href='/briefings'>← BRIEFING HISTORY</a></p><p class='tag'>{escape(label)}</p><section class='hero'><h1>{escape(str(b['executive_summary']))}</h1><p>{posture_badge(b['executive_posture'])} · <b>{escape(str(b['semantic_status']))}</b></p></section><section class='grid'><article><h2>What FRIDA observed</h2><p>{escape(str(b['why_it_may_matter']))}</p></article><article><h2>Foresight</h2><p>{escape(str(f['trajectory']))}</p></article><article><h2>What FRIDA will watch next</h2><ul>{lis(b['what_frida_will_watch_next'])}</ul></article><article><h2>Leading indicators</h2><ul>{lis(f['leading_indicators'])}</ul></article></section><h2>Remaining uncertainty</h2><ul>{lis(b['remaining_uncertainty'])}</ul><p>{escape(str(b['evidence_scope_disclosure']))}</p><p>Evidence: {escape(', '.join(item['evidence_ids']))}</p></main></html>"
