"""Small, read-only Golden Path demonstration view model and HTML renderer."""
from __future__ import annotations

from html import escape
from typing import Any
import json
from pathlib import Path
import sqlite3

def render_shell(page: str, current: str) -> str:
    tabs=[]
    for key,title,subtitle,url in (("action","FRIDA IN ACTION","End User Interface","/"),("explained","FRIDA EXPLAINED","Judge View","/foresight"),("history","HISTORY","Recent Observations","/history")):
        tabs.append(f"<span class='frida-tab active'>{title}<small>{subtitle}</small></span>" if key==current else f"<a class='frida-tab' href='{url}'>{title}<small>{subtitle}</small></a>")
    indicator = "<span id='frida-heartbeat' class='frida-heartbeat idle' aria-label='FRIDA observing' title='FRIDA is observing'></span>"
    if current == "action":
        indicator += "<a class='briefings-entry' href='/briefings'>BRIEFINGS <small>Latest strategic brief</small></a>"
    indicator += "<script>document.addEventListener('DOMContentLoaded',()=>{const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);for(let node;node=walker.nextNode();){node.nodeValue=node.nodeValue.replaceAll('MUNICIPAL STRATEGIC INTELLIGENCE','STRATEGIC URBAN INTELLIGENCE').replaceAll('Municipal strategic intelligence','Strategic urban intelligence')}});</script>"
    indicator += "<script>document.addEventListener('DOMContentLoaded',async()=>{const nav=document.querySelector('.frida-tabs');if(!nav||document.querySelector('.frida-city'))return;try{const r=await fetch('/api/v1/assignment/active',{cache:'no-store'}),v=await r.json(),a=v.assignment||{},city=document.createElement('div'),name=String(a.city_name||'FRIDA'),country=String(a.country_name||''),coat=String(a.identity_asset_url||'');city.className='frida-city';city.innerHTML=(coat?'<img src=\"'+coat+'\" alt=\"City of London coat of arms\">':'')+'<span><b>'+name.toUpperCase()+(country?', '+country.toUpperCase():'')+'</b><small>FRIDA is observing '+name+'</small></span>';nav.before(city)}catch(_){}});</script>"
    if current == "action":
        indicator += "<script>document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll(\"a[href^='/case?']\").forEach(link=>{const url=new URL(link.href);url.searchParams.set('from','action');link.href=url.pathname+url.search})});</script>"
        indicator += """<script>document.addEventListener('DOMContentLoaded',()=>{const heading=document.getElementById('city-activity-heading')||[...document.querySelectorAll('h2')].find(h=>h.textContent.trim()==='City activity — live window');if(!heading||document.getElementById('live-observation-ticker'))return;const tools=document.createElement('div'),hint=document.createElement('small'),dot=document.createElement('span'),ticker=document.createElement('section');tools.className='activity-live-tools';hint.className='activity-hint';hint.textContent='Click any row for details — routine activity';dot.id='city-heartbeat';dot.className='frida-heartbeat idle';dot.title='FRIDA activity';ticker.id='live-observation-ticker';ticker.setAttribute('aria-live','polite');ticker.innerHTML='<span>FRIDA is preparing the live observation window.</span>';tools.append(hint,dot,ticker);heading.after(tools)});</script>"""
        indicator += """<script>document.addEventListener('DOMContentLoaded',()=>{const box=document.getElementById('city-activity');if(!box)return;const status=document.createElement('p');status.id='observation-public-status';status.className='observation-public-status';box.after(status);const refresh=async()=>{try{const r=await fetch('/api/v1/observation/status');if(!r.ok)return;const v=await r.json(),state=String(v.heartbeat||v.state||'STOPPED'),health=String(v.source_health||'UNKNOWN');status.textContent='FRIDA observation: '+state.replaceAll('_',' ')+' · source health: '+health.replaceAll('_',' ');document.querySelectorAll('.frida-heartbeat').forEach(dot=>{dot.classList.toggle('active',state==='OBSERVING');dot.title='FRIDA is '+state.toLowerCase().replaceAll('_',' ')})}catch(_){}};refresh();setInterval(refresh,3000)});</script>"""
        indicator += """<script>document.addEventListener('DOMContentLoaded',()=>{const box=document.getElementById('city-activity');if(!box)return;let signature='';const labelFor=event=>{const state=String((event.payload||{}).classification||'');if(event.event_type==='cycle.started')return ['OBSERVING','New autonomous observation cycle started.'];if(event.event_type==='observe.source_examined')return ['OBSERVE',state==='SAME_STATE'?'Official source confirmed its existing state.':state==='ORDINARY_CHANGE'?'Official source refreshed — ordinary variation.':state==='POTENTIALLY_ELIGIBLE_CHANGE'?'Official source change retained for governed review.':'Official source examined.'];if(event.event_type==='pattern.assessed')return ['MEMORY','Deterministic pattern memory updated; it does not authorize a signal.'];if(event.event_type==='triage.no_candidate')return ['TRIAGE','No candidate qualified for semantic dispatch.'];if(event.event_type==='cycle.completed')return ['RESULT','Observation cycle completed without strategic dispatch.'];return ['ACTIVITY','Governed observation activity recorded.']};const timestamp=value=>{const date=new Date(value);return Number.isNaN(date.valueOf())?String(value||'—'):date.toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'})};const follow=()=>box.scrollTop<28;const refresh=async()=>{try{const response=await fetch('/api/v1/observation/recent',{cache:'no-store'});if(!response.ok)return;const cycles=await response.json(),events=cycles.flatMap(c=>c.events||[]),next=events.map(e=>String(e.occurred_at||'')+String(e.event_type||'')).join('|');if(next===signature)return;const atLatest=follow();box.replaceChildren();for(const event of events.slice().reverse()){const row=document.createElement('a'),time=document.createElement('time'),kind=document.createElement('b'),text=document.createElement('span'),label=labelFor(event);row.className='activity-row activity-arrived';row.href='/glass-hood';time.dateTime=String(event.occurred_at||'');time.title=String(event.occurred_at||'');time.textContent=timestamp(event.occurred_at);kind.textContent=label[0];text.textContent=label[1];row.append(time,kind,text);box.prepend(row)}signature=next;box.dataset.eventCount=String(events.length);document.querySelectorAll('.frida-heartbeat').forEach(dot=>{dot.classList.add('active','pulse');setTimeout(()=>dot.classList.remove('pulse'),1000)});if(atLatest)box.scrollTop=0;else document.getElementById('return-to-latest').hidden=false}catch(_){}};const latest=document.createElement('button');latest.id='return-to-latest';latest.hidden=true;latest.className='return-latest';latest.textContent='Return to latest activity';latest.onclick=()=>{box.scrollTop=0;latest.hidden=true};box.after(latest);box.addEventListener('scroll',()=>{if(follow())latest.hidden=true});refresh();setInterval(refresh,3000)});</script>"""
        indicator += """<script>document.addEventListener('DOMContentLoaded',()=>{const box=document.getElementById('replay-events');if(!box)return;const sequence=box.querySelector('.sequence');let count=Number(box.dataset.eventCount||0);const refresh=async()=>{try{const r=await fetch('/api/v1/replay/status');if(!r.ok)return;const replay=await r.json(),events=replay.events||[];if(events.length<=count)return;for(const event of events.slice(count)){const row=document.createElement('div'),time=document.createElement('time'),kind=document.createElement('b'),text=document.createElement('span');row.className='replay-row activity-arrived';time.textContent=String(event.occurred_at||'');kind.textContent=String(event.event_type||'activity').toUpperCase();text.textContent=String(event.message||'Governed activity recorded');row.append(time,kind,text);sequence.append(row)}count=events.length;box.dataset.eventCount=String(count)}catch(_){}};setInterval(refresh,1200)});</script>"""
        indicator += """<script>document.addEventListener('DOMContentLoaded',()=>{const ticker=document.getElementById('live-observation-ticker'),summary=document.getElementById('observation-pulse');if(!ticker)return;let prior='';const friendly=id=>({LONDON_TFL_VICTORIA:'TfL Victoria line',LONDON_EA_THAMES_TIDEWAY:'Environment Agency Thames Tideway',LONDON_PLANNING_SW8:'Planning London Datahub — SW8'})[id]||'Official city source';const phrase=e=>{const p=e.payload||{},name=friendly(String(p.source_id||'')),state=String(p.classification||'');return state==='SAME_STATE'?name+' confirmed its existing state':state==='ORDINARY_CHANGE'?name+' refreshed — ordinary variation':state==='POTENTIALLY_ELIGIBLE_CHANGE'?name+' change retained for governed review':name+' was checked'};const refresh=async()=>{try{const r=await fetch('/api/v1/observation/recent',{cache:'no-store'});if(!r.ok)return;const cycles=await r.json(),examined=cycles.flatMap(c=>c.events||[]).filter(e=>e.event_type==='observe.source_examined'),sources=new Set(examined.map(e=>String((e.payload||{}).source_id)).filter(Boolean)),latest=examined.map(e=>String(e.occurred_at||'')).sort().at(-1)||'',signature=[examined.length,sources.size,latest].join('/'),recent=examined.slice(-3).reverse().map(phrase);const text=['FRIDA IS WATCHING '+sources.size+' OFFICIAL LONDON SOURCES',...recent,'FRIDA CONTINUES WATCHING'].join('  ◆  ');ticker.innerHTML='<span class="ticker-track">'+text+'  ◆  '+text+'</span>';if(summary)summary.innerHTML='<b>OBSERVATION PULSE</b><span>'+sources.size+' official London sources · '+examined.length+' recent checks</span><small>Routine source activity is filtered until a governed pattern warrants FRIDA’s attention.</small>';if(prior&&prior!==signature){ticker.classList.add('pulse');document.querySelectorAll('.frida-heartbeat').forEach(dot=>{dot.classList.add('active','pulse');setTimeout(()=>dot.classList.remove('pulse'),1000)});setTimeout(()=>ticker.classList.remove('pulse'),1000)}prior=signature}catch(_){}};refresh();setInterval(refresh,3000)});</script>"""
    header=f"""<style>
    .frida-shell-wrap{{width:100%;background:#f7f3eb;border-bottom:1px solid #e2dbcf}}
    .frida-shell{{display:flex;justify-content:space-between;align-items:center;gap:18px;max-width:1000px;min-height:82px;margin:0 auto;padding:6px 24px}}
    .frida-brand{{display:block;line-height:0;border-radius:8px;flex:0 0 auto}}
    .frida-brand:focus-visible{{outline:3px solid #147b79;outline-offset:3px}}
    .frida-shell img{{width:205px;height:68px;object-fit:contain}}
    .frida-tabs{{display:flex;align-items:stretch;gap:8px;margin:0}}
    .frida-city{{display:flex;align-items:center;justify-content:center;gap:8px;min-width:190px;margin-left:auto;margin-right:auto;color:#10243a;font:11px Arial,sans-serif;letter-spacing:.08em;white-space:nowrap}}
    .frida-city img{{width:42px;height:46px;object-fit:contain;flex:0 0 auto}}
    .frida-city b,.frida-city small{{display:block}}.frida-city small{{margin-top:3px;color:#71808c;font-size:10px;letter-spacing:0}}
    .frida-heartbeat-row{{max-width:1000px;margin:0 auto;padding:10px 24px 0 80px;line-height:0;display:flex;align-items:center;gap:36px}}
    .briefings-entry{{display:inline-flex;align-items:center;gap:7px;background:#10243a;color:#fff;border-radius:9px;padding:9px 13px;text-decoration:none;font:700 11px Arial,sans-serif;letter-spacing:.07em;line-height:1}}.briefings-entry small{{font:11px Arial,sans-serif;letter-spacing:0;color:#e5f0ef}}
    .frida-heartbeat{{display:inline-block;width:15px;height:15px;border-radius:50%;background:#6f8e8c;box-shadow:0 0 0 4px #e5efec;animation:frida-idle-tick 5s ease-out infinite}}
    .frida-heartbeat.active{{background:#147b79;box-shadow:0 0 0 4px #d7eeea}}
    .frida-heartbeat.pulse{{animation:frida-pulse .9s ease-out}}@keyframes frida-pulse{{0%{{transform:scale(1);box-shadow:0 0 0 3px #e5efec}}45%{{transform:scale(1.5);box-shadow:0 0 0 8px #c4e6df}}100%{{transform:scale(1);box-shadow:0 0 0 3px #e5efec}}}}
    @keyframes frida-idle-tick{{0%,80%,100%{{transform:scale(1);filter:brightness(1)}}88%{{transform:scale(1.32);filter:brightness(1.35)}}}}
    .activity-row{{cursor:pointer;transition:background-color .16s ease,padding-left .16s ease;position:relative}}
    .activity-live-tools{{display:flex;align-items:center;gap:16px;margin:-5px 0 10px}}.activity-live-tools .activity-hint{{margin:0;white-space:nowrap}}
    #live-observation-ticker{{flex:1;min-width:0;border:1px solid #d8e5e0;border-radius:12px;background:#edf5f3;color:#10243a;font:12px Arial,sans-serif;overflow:hidden;white-space:nowrap;transition:background .25s ease,box-shadow .25s ease}}
    #live-observation-ticker .ticker-track{{display:inline-block;padding:11px 0;color:#147b79;font:bold 11px Arial,sans-serif;letter-spacing:.09em;animation:frida-ticker 38s linear infinite}}@keyframes frida-ticker{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}#live-observation-ticker.pulse{{background:#dff2ed;box-shadow:0 0 0 3px #c4e6df}}
    #observation-pulse{{margin:12px 0 0;padding:12px 14px;border:1px solid #d8e5e0;border-radius:12px;background:#edf5f3;color:#10243a;font:12px Arial,sans-serif;transition:background .25s ease,box-shadow .25s ease}}
    #observation-pulse b{{display:block;color:#147b79;font-size:11px;letter-spacing:.1em}}#observation-pulse span{{display:block;margin-top:3px;font-weight:bold}}#observation-pulse small{{display:block;margin-top:4px;color:#516273;font-size:11px}}
    .activity-row:hover{{background:#edf5f3;padding-left:8px}}
    .activity-arrived{{animation:frida-row-arrival .6s ease-out}}@keyframes frida-row-arrival{{from{{background:#dff2ed;transform:translateY(4px)}}to{{background:transparent;transform:translateY(0)}}}}
    .return-latest{{margin-top:8px;padding:7px 10px;border:1px solid #d8d0c3;border-radius:8px;background:#fff;color:#10243a;font:bold 12px Arial,sans-serif;cursor:pointer}}
    .activity-row::after{{content:'›';align-self:center;color:#147b79;font:700 22px Arial,sans-serif}}
    .activity-hint{{display:block;margin-top:3px;color:#71808c;font:12px Arial,sans-serif;font-weight:normal;letter-spacing:0;text-transform:none}}
    .observation-public-status{{margin:9px 0 0;color:#516273;font:12px Arial,sans-serif}}
    .product-identity{{margin:0 0 16px;font:700 12px Arial,sans-serif;letter-spacing:.12em;color:#147b79}}
    .frida-heartbeat-row ~ main > .eyebrow{{margin:0 0 16px}}
    .metrics{{margin-top:12px}}
    .frida-tab{{box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;min-width:142px;height:58px;padding:10px 12px;border:1px solid #d8d0c3;border-radius:12px;text-decoration:none;color:#10243a;font:bold 12px Arial,sans-serif;letter-spacing:.02em}}
    .frida-tab small{{display:block;margin-top:4px;color:#516273;font:11px Arial,sans-serif;letter-spacing:0}}
    .frida-tab.active{{background:#10243a;border-color:#10243a;color:#fff;cursor:default}}
    .frida-tab.active small{{color:#e5f0ef}}
    @media(max-width:700px){{.frida-shell{{align-items:flex-start;flex-direction:column}}.frida-city{{order:3;margin:0}}.frida-tabs{{width:100%}}.frida-tab{{flex:1;min-width:0}}.frida-heartbeat-row{{padding-left:24px}}.activity-live-tools{{flex-wrap:wrap;gap:12px}}#live-observation-ticker{{flex-basis:100%}}}}
    </style><div class='frida-shell-wrap'><header class='frida-shell'><a class='frida-brand' href='/' aria-label='Back to FRIDA in Action'><img src='/assets/frida-logo.png' alt='FRIDA portrait and logo'></a><nav class='frida-tabs'>{''.join(tabs)}</nav></header></div><div class='frida-heartbeat-row'>{indicator}</div>"""
    # Active-assignment pages scope their own CSS with ``<main class=...>``.
    # The application shell belongs before either form of the root main tag.
    footer = ("<footer class='frida-build-footer'>FRIDA · London build 0.9.0 · "
              "public Judge surface is read-only</footer>")
    favicon = "<link rel='icon' type='image/png' href='/assets/frida-flower-icon.png'>"
    # Social messengers do not use a browser favicon for a shared-link card.
    # Give them a small, public Open Graph identity instead, using the same
    # flower users see in the browser tab.
    social_preview = (
        "<meta property='og:type' content='website'>"
        "<meta property='og:site_name' content='FRIDA'>"
        "<meta property='og:title' content='FRIDA — Strategic Urban Intelligence'>"
        "<meta property='og:description' content='FRIDA observes London’s authorized public evidence and surfaces strategic questions with governed uncertainty.'>"
        "<meta property='og:url' content='https://frida-zz37olzlja-pv.a.run.app/'>"
        "<meta property='og:image' content='https://frida-zz37olzlja-pv.a.run.app/assets/frida-flower-icon.png'>"
        "<meta property='og:image:alt' content='FRIDA flower mark'>"
        "<meta name='twitter:card' content='summary'>"
        "<meta name='twitter:title' content='FRIDA — Strategic Urban Intelligence'>"
        "<meta name='twitter:description' content='Governed strategic urban intelligence for London.'>"
        "<meta name='twitter:image' content='https://frida-zz37olzlja-pv.a.run.app/assets/frida-flower-icon.png'>"
    )
    page = page.replace(
        "rel='icon' type='image/png' href='/assets/frida-logo.png'",
        "rel='icon' type='image/png' href='/assets/frida-flower-icon.png'",
    )
    # Some projections provide a complete document (including ``<head>``), while
    # others provide only page content.  In both cases the shared application
    # shell belongs immediately before the first main element.
    # A few older projections start with ``<html ...><meta ...>`` rather than
    # an explicit head element.  Insert a real head in that form too: otherwise
    # browsers fall back to ``/favicon.ico`` and the shared FRIDA identity
    # disappears from those pages.
    metadata = favicon + social_preview
    if "og:site_name" in page:
        rendered = page
    elif '<head>' in page:
        rendered = page.replace('<head>', '<head>' + metadata, 1)
    elif '<html' in page:
        html_end = page.find('>', page.find('<html'))
        main_start = page.find('<main', html_end + 1)
        # Legacy projections placed their meta/title/style block immediately
        # after ``<html>``. Browsers tolerate that; social scrapers often do
        # not. Move that complete block into the real head with our shared
        # favicon and social metadata.
        if main_start != -1:
            document_head = page[html_end + 1:main_start]
            rendered = page[:html_end + 1] + '<head>' + metadata + document_head + '</head>' + page[main_start:]
        else:
            rendered = page[:html_end + 1] + '<head>' + metadata + '</head>' + page[html_end + 1:]
    else:
        rendered = metadata + page
    rendered = rendered.replace('<main', header + '<main', 1)
    return rendered.replace('</html>', footer + '</html>') if '</html>' in rendered else rendered + footer


def render_html(view: dict[str, Any]) -> str:
    rows = "".join(f"<li><b>{escape(event['stage'])}</b> — {escape(event['detail'])}</li>" for event in view["audit"])
    disposition = escape(str(view.get("disposition") or "PENDING"))
    replay = view.get("execution_mode") == "CONTROLLED_REPLAY_DEMO"
    source_label = "Historical real INEGI DENUE observation" if replay else "Current real source observation"
    original_detection = "Autonomously noticed by FRIDA without a user semantic prompt" if replay else "Autonomously noticed by FRIDA"
    current_execution = "CONTROLLED_REPLAY_DEMO — not a new external event" if replay else escape(str(view.get("execution_mode", "LIVE_WORLD_OBSERVATION")))
    historical = (f"<p>Original execution: immutable historical GOLDEN_PATH_BLOCKED attempt — "
                  f"{escape(str(view.get('original_execution_reference') or 'reference required'))}</p>") if replay else ""
    return f"""<!doctype html><title>FRIDA — Golden Path</title>
<main><h1>FRIDA noticed.</h1><p>Source observation: {source_label}</p>
<p>Original detection: {original_detection}</p><p>Current execution: {current_execution}</p>{historical}<p>Run: {escape(view['run_id'])}</p>
<p>Signal: {escape(view['signal_id'])} · State: {escape(view['state'])}</p>
<h2>Autonomous audit</h2><ol>{rows}</ol>
<h2>Governed disposition</h2><p><strong>{disposition}</strong></p>
<p>Re-entry: {escape(str(view.get('reentry_condition') or 'None'))}</p></main>"""


def foresight_projection(database_path: str | Path | Any) -> dict[str, Any] | None:
    """Read only validated persisted artifacts; no model output beyond approved fields."""
    if hasattr(database_path, "foresight_projection"):
        return database_path.foresight_projection()
    path = Path(database_path)
    if not path.exists(): return None
    db = sqlite3.connect(path); db.row_factory = sqlite3.Row
    try:
        execution = db.execute("SELECT foresight_execution_id,source_state_id FROM foresight_executions ORDER BY created_at DESC LIMIT 1").fetchone()
        if not execution: return None
        events = {row["event_type"]: json.loads(row["payload_json"]) for row in db.execute("SELECT event_type,payload_json FROM foresight_execution_events WHERE foresight_execution_id=? ORDER BY event_id", (execution["foresight_execution_id"],))}
        source = db.execute("SELECT payload_json FROM foresight_source_states WHERE source_state_id=?", (execution["source_state_id"],)).fetchone()
    finally: db.close()
    if "foresight.governance_persisted" not in events: return None
    state=json.loads(source["payload_json"]) if source else {}
    facts=state.get("facts", [])
    primary=next((fact for fact in facts if str(fact.get("value", "")).startswith("-")), facts[0] if facts else {})
    selected={"case_id":state.get("source_state_id", execution["source_state_id"]),"bundle_id":state.get("bundle_id", "GOVERNED_CASE"),"geography":primary.get("geographic_scope", state.get("geography", "Governed geographic scope")),"measure":primary.get("measure", "governed observed condition"),"value":primary.get("value", "—"),"unit":primary.get("unit", ""),"as_of":primary.get("as_of", ""),"limitation":primary.get("limitation", "Evidence limits are retained."),"source_ids":[item.get("source_id", "") for item in state.get("sources", [])],"fact_ids":[item.get("fact_id", "") for item in facts]}
    return {"execution_id":execution["foresight_execution_id"],"assessment":events["foresight.artifact_persisted"],"challenge":events["foresight.challenge_artifact_persisted"],"governance":events["foresight.governance_persisted"],"scenario":events["foresight.scenarios_persisted"],"selected":selected}


def render_foresight_html(view: dict[str, Any]) -> str:
    a,c,g=view["assessment"],view["challenge"],view["governance"]
    selected=view.get("selected") or {"value":"−65.556761","unit":"hm³/year","geography":"Valle de Querétaro aquifer","measure":"Official annual availability","as_of":"2024","limitation":"This is observed evidence with governed limitations; it is not a prediction."}
    cards="".join(f"<article><span class='tag projected'>{escape(label)}</span><h3>{escape(label.title())}</h3><p>{escape(text)}</p></article>" for label,text in zip(("BASELINE","STRESS","MITIGATION"),a["decision_relevant_differences"]))
    observed=f"<li><strong>OBSERVED</strong> · {escape(selected['measure'])}: <b>{escape(str(selected['value']))} {escape(str(selected['unit']))}</b> · {escape(selected['geography'])}</li>"
    assumed="<li><strong>ASSUMED</strong> · A bounded scenario variation is declared explicitly; it is not observed evidence.</li>"
    limits="".join(f"<li>{escape(x)}</li>" for x in a["limitations"])
    quals="".join(f"<li>{escape(x)}</li>" for x in g["qualifications"])
    page=f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA Explained — Governed Case</title>
<style>:root{{--ink:#10243a;--cream:#f6f1e8;--coral:#e96b4b;--teal:#147b79;--gold:#d8a645;--line:#d7d0c4}}*{{box-sizing:border-box}}body{{margin:0;background:var(--cream);color:var(--ink);font:16px/1.55 Georgia,serif}}main{{max-width:1080px;margin:auto;padding:44px 24px 80px}}.eyebrow,.tag{{font:700 12px Arial,sans-serif;letter-spacing:.11em;text-transform:uppercase}}.eyebrow{{color:var(--teal)}}h1{{font-size:clamp(38px,7vw,74px);line-height:1.03;margin:8px 0 18px}}h2{{font-size:29px;margin:42px 0 12px}}.hero{{padding:32px;border-radius:20px;background:var(--ink);color:#fff}}.hero p{{max-width:700px;font-size:20px}}.number{{color:#f7c86f;font:bold clamp(28px,5vw,48px) Arial}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}article,.panel{{background:#fff;padding:22px;border:1px solid var(--line);border-radius:14px}}.observed{{color:var(--teal)}}.assumed{{color:#a15621}}.projected{{color:#6a508f}}.cause{{display:grid;grid-template-columns:1fr 42px 1fr 42px 1fr;align-items:center;gap:8px;text-align:center}}.cause article{{background:#fff}}.arrow{{font:28px Arial;color:var(--coral)}}details{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:13px;margin:10px 0}}summary{{cursor:pointer;font-weight:bold}}.restricted{{border-left:6px solid var(--coral);background:#fff4ef;padding:22px;border-radius:10px}}@media(max-width:700px){{.grid,.cause{{grid-template-columns:1fr}}.arrow{{transform:rotate(90deg)}}}}</style>
<main><p class='eyebrow'>FRIDA · Municipal strategic intelligence</p><section class='hero'><p class='eyebrow'>She watches the city, not people</p><h1>FRIDA noticed a water-resilience condition.</h1><p>In the Valle de Querétaro aquifer, the official current annual availability is:</p><div class='number'>−65.556761 hm³/year</div><p>This is a governed observed condition — not a prediction.</p></section>
<h2>What FRIDA knows — and what she does not claim</h2><section class='panel'><ul>{observed}{assumed}<li><strong>PROJECTED</strong> · Bounded qualitative implications from evidence plus declared assumptions. Not a forecast.</li></ul></section>
<h2>12 months · qualitative scenarios</h2><div class='grid'>{cards}</div><p><em>FRIDA does not aim to predict the future. She projects plausible scenarios from governed evidence, explicit assumptions, and bounded horizons.</em></p>
<h2>Agents by purpose, not headcount</h2><div class='grid'><article><span class='tag observed'>Foresight specialist</span><p>Interpreted governed strategic implications, tradeoffs and uncertainty.</p></article><article><span class='tag assumed'>Independent Challenger</span><p>Tested whether the scenario reasoning remained supported by its evidence and assumptions.</p></article><article><span class='tag projected'>Deterministic governance</span><p>Applied the policy. The model did not choose the outcome.</p></article></div>
<h2>The Challenger moment</h2><section class='cause'><article><b>Independent Challenger</b><p class='tag assumed'>Finding: MATERIAL</p><p>{escape(c['reason'])}</p></article><div class='arrow'>↓</div><article><b>Deterministic governance</b><p>Applied the frozen policy, not a model preference.</p></article><div class='arrow'>↓</div><article><b>Current status</b><p class='tag assumed'>RESTRICTED</p><p>{escape(c['required_effect'])}</p></article></section>
<section class='restricted'><b>What FRIDA is allowed to say now</b><p>She may present the governed condition, assumptions, bounded qualitative scenarios and their limits. She may not claim demand magnitude, probability, supply failure or mitigation effectiveness.</p><ul>{quals}</ul></section>
<h2 id='inspect'>Inspect the governance</h2><details><summary>Evidence & provenance</summary><p>Evidence IDs: {escape(', '.join(a['evidence_ids']))}. The observed condition is source-governed; contextual facts are not converted into unsupported causal claims.</p></details><details><summary>Assumptions & Stress bounds</summary><p>Assumption IDs: {escape(', '.join(a['assumption_ids']))}.</p><ul><li>Stop if integrity/provenance fails.</li><li>Stop if an assumption is presented as observed.</li><li>Stop if unsupported magnitude, probability, or effect is required.</li></ul></details><details><summary>Audit & verified execution</summary><p>Execution: {escape(view['execution_id'])}. Validated Foresight → validated Challenger → deterministic RESTRICTED governance. No briefing, delivery or deployment occurred.</p></details><details><summary>Foresight limitations</summary><ul>{limits}</ul></details></main></html>"""
    # Keep the Judge hero on the exact same content rail and vertical starting line
    # as FRIDA in Action; only the page content changes between these views.
    page=page.replace("</style>", "main{max-width:1000px;padding:36px 24px 80px}.eyebrow{margin:0 0 16px}</style>", 1)
    metric=f"{selected.get('value', '—')} {selected.get('unit', '')}".strip()
    return (page.replace("FRIDA noticed a water-resilience condition.", "FRIDA noticed a governed strategic condition.")
        .replace("In the Valle de Querétaro aquifer, the official current annual availability is:", f"In {selected.get('geography', 'the selected governed geography')}, the persisted observed measure is:")
        .replace("−65.556761 hm³/year", metric)
        .replace("Official annual availability · Valle de Querétaro aquifer", f"{selected.get('measure', 'Observed condition')} · as of {selected.get('as_of', 'governed source date')}")
        .replace("The current aquifer-level condition is a strategic planning constraint. It is observed evidence, not a prediction about future supply.", selected.get("limitation", "This is observed evidence with governed limitations; it is not a prediction.")))


def _render_action_legacy(view: dict[str, Any]) -> str:
    """Executive view over the same verified projection, deliberately not a chatbot."""
    c,g=view["challenge"],view["governance"]
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA in Action</title><style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--orange:#e76d4a;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.55 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 72px}}.product-identity{{margin:0 0 16px;font:700 12px Arial;letter-spacing:.13em;color:var(--teal)}}.hello{{background:var(--ink);color:#fff;padding:38px;border-radius:22px}}.hello h1{{font-size:clamp(38px,6vw,64px);line-height:1.05;margin:6px 0}}.label{{font:bold 12px Arial;letter-spacing:.1em;color:var(--teal)}}.number{{font:bold 38px Arial;color:#f2be61}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:18px}}section{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:23px}}h2{{margin:0 0 8px;font-size:25px}}.restricted{{border-left:6px solid var(--orange)}}a.button{{display:inline-block;background:var(--ink);color:#fff;padding:12px 16px;border-radius:8px;text-decoration:none;font:bold 14px Arial}}small{{color:#516273}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style><main><p class='product-identity'>FRIDA · MUNICIPAL STRATEGIC INTELLIGENCE</p><section class='hello'><p class='label'>GOOD MORNING</p><h1>I found something that deserves your attention.</h1><p>FRIDA has been observing the city. A governed water-resilience condition now merits strategic review.</p><p class='number'>−65.556761 hm³/year</p><p>Official annual availability · Valle de Querétaro aquifer</p></section><div class='grid'><section><p class='label'>WHAT I NOTICED</p><h2>Why it matters</h2><p>The current aquifer-level condition is a strategic planning constraint. It is observed evidence, not a prediction about future supply.</p></section><section><p class='label'>WHAT I CAN PROJECT</p><h2>Three bounded scenarios</h2><p><b>Baseline:</b> current condition remains a planning constraint.<br><b>Stress:</b> additional assumed pressure.<br><b>Mitigation:</b> a bounded resilience review.</p><small>12 months · qualitative mode · none is a forecast.</small></section><section><p class='label'>WHAT I AM WATCHING</p><h2>Evidence, assumptions and limits</h2><p>I keep observed facts separate from assumptions. I do not convert population context into water demand or create unsupported precision.</p></section><section class='restricted'><p class='label'>CURRENT AUTHORITY</p><h2>RESTRICTED</h2><p>The Independent Challenger found a material limit: {escape(c['reason'])}</p><p>I cannot responsibly go beyond the governed bounds yet.</p><a class='button' href='/foresight#inspect'>Why is this restricted?</a></section></div><section style='margin-top:16px'><p class='label'>WHAT A DECISION-MAKER SHOULD UNDERSTAND NEXT</p><h2>Review resilience options without pretending certainty.</h2><p>FRIDA can surface the condition, compare bounded scenarios and preserve uncertainty. The same evidence and governance are available for inspection.</p><a class='button' href='/foresight'>Inspect evidence & governance</a></section></main></html>"""

def render_enduser_explanation(view: dict[str, Any], kind: str) -> str:
    c=view['challenge']; title='Why this is restricted' if kind=='restricted' else 'Evidence & governance'
    if kind == 'restricted':
        lead = "FRIDA is protecting the quality of the decision, not withholding a conclusion."
        body = f"The Independent Challenger found: {escape(c['reason'])}. FRIDA can present the governed condition and bounded scenarios, but cannot support stronger operational conclusions yet."
        detail = "The current result remains RESTRICTED until the scenario has explicit qualitative bounds and failure conditions that are supported by the governed evidence."
        label = "CURRENT GOVERNED STATUS"
    else:
        lead = "Every FRIDA conclusion starts with evidence that can be inspected."
        body = "FRIDA separates observed evidence, explicit assumptions and bounded projections. She does not turn context into unsupported facts, precision or forecasts."
        detail = "The complete provenance, assumptions, limitations and deterministic governance path remain available for technical inspection."
        label = "TRACEABILITY BY DESIGN"
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA — {title}</title>
    <style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--orange:#e76d4a;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:40px 24px 76px}}.eyebrow{{font:700 12px Arial,sans-serif;letter-spacing:.11em;color:var(--teal)}}h1{{max-width:760px;margin:8px 0 16px;font-size:clamp(38px,6vw,64px);line-height:1.06}}.lead{{max-width:720px;font-size:22px}}.card{{margin-top:22px;padding:28px;border:1px solid var(--line);border-radius:16px;background:#fff}}.status{{border-left:6px solid var(--orange)}}.detail{{color:#516273}}.actions{{display:flex;flex-wrap:wrap;gap:10px;margin-top:26px}}.button{{display:inline-block;border-radius:9px;padding:12px 16px;background:var(--ink);color:#fff;text-decoration:none;font:bold 13px Arial,sans-serif}}.button.secondary{{background:#fff;border:1px solid var(--line);color:var(--ink)}}</style>
    <main><p class='eyebrow'>{label}</p><h1>{title}</h1><p class='lead'>{lead}</p><section class='card status'><p>{body}</p><p class='detail'>{detail}</p></section><div class='actions'><a class='button' href='/'>Back to FRIDA in Action</a><a class='button secondary' href='/foresight#inspect'>Open FRIDA Explained</a></div></main></html>"""


def render_case_presentation_html(case: dict[str, Any]) -> str:
    """One truthful presentation template for every persisted Case projection."""
    evidence="".join(f"<li>{escape(str(item))}</li>" for item in case.get("evidence_ids", [])) or "<li>No evidence IDs are available for this presentation.</li>"
    limits="".join(f"<li>{escape(str(item))}</li>" for item in case.get("limitations", [])) or "<li>Governed limitations are retained.</li>"
    specialists=" · ".join(escape(str(item)) for item in case.get("specialists", []))
    glass=(f"<a class='button' href='{escape(case['glass_hood_url'])}'>Inspect how FRIDA worked</a>" if case.get("glass_hood_url") else "")
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA — Case</title>
    <style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--orange:#e76d4a;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.eyebrow,.tag{{font:700 12px Arial,sans-serif;letter-spacing:.11em;color:var(--teal)}}h1{{font-size:clamp(40px,6vw,64px);line-height:1.05;margin:8px 0 16px}}.hero,.card{{border:1px solid var(--line);border-radius:16px;padding:26px;background:#fff}}.hero{{background:var(--ink);color:#fff}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}}h2{{margin:0 0 8px;font-size:25px}}.status{{border-left:6px solid var(--orange)}}.button{{display:inline-block;margin-top:16px;padding:11px 15px;border-radius:9px;background:var(--ink);color:#fff;text-decoration:none;font:bold 13px Arial}}small{{color:#516273}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style>
    <main><p class='eyebrow'>FRIDA · GOVERNED CASE PRESENTATION</p><section class='hero'><p class='tag'>{escape(str(case['label']))}</p><h1>{escape(str(case['title']))}</h1><p>{escape(str(case['source']))}</p><small>Case ID: {escape(str(case['case_id']))} · Execution: {escape(str(case['execution_id']))}</small></section><div class='grid'><section class='card'><p class='tag'>FRIDA ATTENTION</p><h2>{escape(str(case['attention']))}</h2><p>{escape(str(case['question']))}</p><p><small>{specialists}</small></p></section><section class='card status'><p class='tag'>GOVERNED RESULT</p><h2>{escape(str(case['disposition']))}</h2><p>Challenger: {escape(str(case['challenger']))} · Interpretation: {escape(str(case['interpretation']))}</p></section><section class='card'><p class='tag'>EVIDENCE</p><ul>{evidence}</ul></section><section class='card'><p class='tag'>LIMITS</p><ul>{limits}</ul></section></div>{glass}<p><a href='/history'>Back to History</a></p></main></html>"""


def render_case_presentation_html(case: dict[str, Any], origin: str = "history", historical: bool = False) -> str:
    """A case remembers whether the visitor arrived from Action or History."""
    from_action = origin == "action"
    back_url, back_label = ("/", "← BACK TO FRIDA") if from_action else (("/history?scope=archive", "← BACK TO HISTORY") if historical else ("/history", "← BACK TO HISTORY"))
    evidence = "".join(f"<li>{escape(str(item))}</li>" for item in case.get("evidence_ids", [])) or "<li>No evidence IDs are available for this presentation.</li>"
    limits = "".join(f"<li>{escape(str(item))}</li>" for item in case.get("limitations", [])) or "<li>Governed limitations are retained.</li>"
    specialists = " · ".join(escape(str(item)) for item in case.get("specialists", []))
    strategic = case.get("strategic") or {}
    so_what = f"""<section class='so-what' aria-label='FRIDA strategic interpretation'>
    <article><p class='tag'>WHAT FRIDA NOTICED</p><p>{escape(str(strategic.get('noticed') or case.get('source', 'A governed case was retained.')))}</p></article>
    <article><p class='tag'>WHY FRIDA THINKS IT MATTERS</p><p>{escape(str(strategic.get('why') or case.get('question', 'The governed case remains available for review.')))}</p></article>
    <article><p class='tag'>WHAT FRIDA RECOMMENDS NOW</p><p>{escape(str(strategic.get('now') or 'Follow the governed disposition and its retained limitations.'))}</p>{("<p class='limits-note'><b>Limits retained:</b> " + escape('; '.join(str(item) for item in strategic.get('limitations', []))) + "</p>") if strategic.get('limitations') else ''}</article>
    </section>"""
    execution_url = str(case.get("glass_hood_url", "")).replace("/glass-hood?", "/foresight?")
    glass = f"<a class='button primary' href='{escape(execution_url)}'>Inspect how FRIDA worked</a>" if execution_url else ""
    back = f"<a class='button secondary return' href='{back_url}'>{back_label}</a>"
    archive = "HISTORICAL ARCHIVE · " if historical else ""
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA — Case</title>
    <style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--orange:#e76d4a;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.eyebrow,.tag{{font:700 12px Arial,sans-serif;letter-spacing:.11em;color:var(--teal)}}h1{{font-size:clamp(40px,6vw,64px);line-height:1.05;margin:8px 0 16px}}.hero,.card,.so-what article{{border:1px solid var(--line);border-radius:16px;padding:26px;background:#fff}}.hero{{background:var(--ink);color:#fff}}.so-what{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px}}.so-what article{{border-top:5px solid var(--teal);font-size:16px}}.so-what p{{margin:5px 0}}.limits-note{{color:#516273;font:13px Arial,sans-serif}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}}h2{{margin:0 0 8px;font-size:25px}}.status{{border-left:6px solid var(--orange)}}.case-top,.case-bottom{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}.case-top{{margin-bottom:18px}}.case-bottom{{margin-top:22px}}.button{{display:inline-block;padding:11px 15px;border-radius:9px;text-decoration:none;font:bold 13px Arial,sans-serif}}.button.primary{{background:var(--ink);color:#fff}}.button.secondary{{background:#fff;border:1px solid var(--line);color:var(--ink)}}.return{{box-shadow:0 1px 0 rgba(16,36,58,.08)}}small{{color:#516273}}@media(max-width:650px){{.grid,.so-what{{grid-template-columns:1fr}}}}</style>
    <main><nav class='case-top' aria-label='Return navigation'>{back}</nav><p class='eyebrow'>FRIDA · {archive}GOVERNED CASE PRESENTATION</p><section class='hero'><p class='tag'>{archive}{escape(str(case['label']))}</p><h1>{escape(str(case['title']))}</h1><p>{escape(str(case['source']))}</p><small>Case ID: {escape(str(case['case_id']))} · Execution: {escape(str(case['execution_id']))}</small></section>{so_what}<div class='grid'><section class='card'><p class='tag'>FRIDA ATTENTION</p><h2>{escape(str(case['attention']))}</h2><p>{escape(str(case['question']))}</p><p><small>{specialists}</small></p></section><section class='card status'><p class='tag'>GOVERNED RESULT</p><h2>{escape(str(case['disposition']))}</h2><p>Challenger: {escape(str(case['challenger']))} · Interpretation: {escape(str(case['interpretation']))}</p></section><section class='card'><p class='tag'>EVIDENCE</p><ul>{evidence}</ul></section><section class='card'><p class='tag'>LIMITS</p><ul>{limits}</ul></section></div><nav class='case-bottom' aria-label='Case actions'>{glass}{back}</nav></main></html>"""


def render_case_history_html(cases: list[dict[str, Any]]) -> str:
    cards="".join(f"<article><p class='tag'>{escape(str(case['label']))}</p><h2>{escape(str(case['title']))}</h2><p>{escape(str(case['source']))}</p><p><b>{escape(str(case['disposition']))}</b></p><a href='/case?case_id={escape(str(case['case_id']))}&amp;from=history'>Open governed case</a></article>" for case in cases) or "<article><h2>No persisted cases</h2><p>FRIDA does not fabricate records.</p></article>"
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA — History</title><style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.eyebrow,.tag{{font:700 12px Arial;letter-spacing:.11em;color:var(--teal)}}h1{{font-size:56px;margin:8px 0}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}article{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:23px}}h2{{margin:7px 0;font-size:26px}}a{{color:var(--ink);font-weight:bold}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style><main><p class='eyebrow'>PERSISTED CASES & EXECUTIONS</p><h1>History</h1><p>Every entry is derived from retained case, evidence and execution artifacts. No records are fabricated.</p><section class='grid'>{cards}</section></main></html>"""

def render_history_html(cycles: list[dict[str, Any]] | None = None, current: dict[str, Any] | None = None) -> str:
    cycle_note = f"{len(cycles)} recent live observation cycle(s) are retained with their event trace." if cycles else "No live observation cycles have been retained yet."
    selected=(current or {}).get("selected") or {"measure":"Governed strategic condition","geography":"selected governed geography","limitation":"Evidence, assumptions and limitations remain inspectable."}
    governance=(current or {}).get("governance", {})
    status=governance.get("status", "RESTRICTED")
    return """<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA — History</title>
    <style>:root{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--orange:#e76d4a;--line:#d8d0c3}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 Georgia,serif}main{max-width:1000px;margin:auto;padding:40px 24px 76px}.eyebrow{font:700 12px Arial,sans-serif;letter-spacing:.11em;color:var(--teal)}h1{margin:8px 0 10px;font-size:clamp(38px,6vw,64px);line-height:1.06}.intro{max-width:650px;font-size:21px}.timeline{position:relative;margin-top:32px;padding-left:34px}.timeline:before{content:'';position:absolute;top:8px;bottom:8px;left:8px;width:2px;background:#d8d0c3}.case{position:relative;padding:26px;border:1px solid var(--line);border-radius:16px;background:#fff}.case:before{content:'';position:absolute;left:-34px;top:30px;width:14px;height:14px;border-radius:50%;background:var(--teal);border:4px solid var(--paper)}.tag{font:700 12px Arial,sans-serif;letter-spacing:.1em;color:var(--teal)}h2{margin:8px 0;font-size:28px}.status{display:inline-block;margin-top:8px;padding:5px 9px;border-radius:99px;background:#fff1ed;color:#8d3b27;font:bold 11px Arial,sans-serif;letter-spacing:.07em}.meta{color:#516273}.button{display:inline-block;margin-top:14px;border-radius:9px;padding:11px 15px;background:var(--ink);color:#fff;text-decoration:none;font:bold 13px Arial,sans-serif}</style>
    <main><p class='eyebrow'>PERSISTED OBSERVATIONS</p><h1>History</h1><p class='intro'>A truthful record of what FRIDA has actually retained. No observations are fabricated for this view.</p><section class='timeline'><article class='case'><p class='tag'>CURRENT GOVERNED CASE</p><h2>""" + escape(str(selected["measure"])) + " · " + escape(str(selected["geography"])) + """</h2><p class='meta'>One persisted governed case is available for review.</p><span class='status'>""" + escape(str(status)) + """ — GOVERNED</span><p>""" + escape(str(selected["limitation"])) + """</p><p class='meta'>""" + escape(cycle_note) + """</p><a class='button' href='/'>Open FRIDA in Action</a></article></section></main></html>"""

def render_glass_hood(cycles: list[dict[str, Any]]) -> str:
    if not cycles:
        rows = "<p class='glass-empty'>No live cycle has run yet.</p>"
    else:
        rows = "".join(
            f"<div class='glass-cycle'><p class='glass-cycle-id'>{escape(str(c['cycle_id']))} · {escape(str(c['status']))}</p>" +
            "".join(f"<div class='glass-row'><time>{escape(str(e['occurred_at']))[-14:-6]}</time><b>{escape(str(e['event_type']).replace('.', ' ').upper())}</b><span>{escape(str(e['message']))}</span></div>" for e in c['events']) +
            "</div>" for c in reversed(cycles)
        )
    return f"<section class='glass-hood'><p class='label'>LIVE OBSERVATION CYCLE</p><h2>Under the hood</h2><p>FRIDA shows the governed work she actually performed. No candidate means no model dispatch.</p><div class='glass-events'>{rows}</div></section>"


def render_lead_glass_hood_html(view: dict[str, Any]) -> str:
    """Executive-grade, read-only projection of the verified Lead execution."""
    rows = "".join(
        f"<article class='lead-row actor-{escape(row['actor']['label'].lower().replace(' ', '-'))}'><div class='actor'><b>{escape(row['actor']['icon'])}</b><span>{escape(row['actor']['label'])}</span><time>{escape(row['at'][-14:-6])}</time></div><h3>{escape(row['action'])}</h3><p class='decision'>{escape(row['decision'])}</p><p>{escape(row['detail'])}</p>{('<p class=refs>Evidence: ' + escape(', '.join(row['evidence_ids'])) + '</p>') if row['evidence_ids'] else ''}</article>"
        for row in view['rows']
    )
    stages = "".join(f"<li><b>{escape(item['stage'])}</b><span>{item['total']:,} tokens · {item['latency_ms']:,} ms</span></li>" for item in view['telemetry'])
    catalogue = "".join(f"<li><b>{escape(item['name'].replace('_', ' ').title())}</b><span>{escape(item['role'])}</span></li>" for item in view['catalogue'])
    correction = "" if not view.get('audit_correction') else "<details class='audit'><summary>Audit correction retained</summary><p>A later failure marker was superseded append-only because the persisted ledger proves this execution completed. No record was deleted.</p></details>"
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA in Action — Under the Hood</title>
    <style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--orange:#e76d4a;--line:#d8d0c3;--purple:#665182}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.55 Georgia,serif}}main{{max-width:1040px;margin:auto;padding:42px 24px 80px}}.page-top{{display:flex;align-items:center;justify-content:space-between;gap:18px}}.eyebrow,.actor,.decision,.execution-label{{font:700 12px Arial,sans-serif;letter-spacing:.09em;text-transform:uppercase}}.eyebrow,.execution-label{{color:var(--teal)}}.execution-label{{margin:0 0 6px}}.back{{color:var(--ink);font:700 13px Arial,sans-serif;text-decoration:none}}.back:hover{{color:var(--teal)}}h1{{font-size:clamp(40px,6vw,68px);line-height:1.04;margin:6px 0 16px}}.lead{{max-width:760px;font-size:21px}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:26px 0}}.metric,.lead-row,.panel{{border:1px solid var(--line);border-radius:15px;background:#fff;padding:20px}}.metric b{{display:block;font:700 25px Arial;color:var(--teal)}}.metric span,.refs,.audit{{color:#516273;font:13px Arial}}.sequence{{display:grid;gap:12px}}.lead-row{{border-left:6px solid var(--teal)}}.lead-row.actor-frida{{border-left-color:var(--purple)}}.lead-row.actor-independent-challenger{{border-left-color:var(--orange)}}.lead-row.actor-governance{{border-left-color:#b18826}}.actor{{display:flex;align-items:center;gap:8px;color:#516273}}.actor b{{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#eef3f0;color:var(--teal);font-size:16px}}.actor time{{margin-left:auto;font:12px Arial;color:#71808c}}h3{{margin:12px 0 2px;font-size:22px}}.decision{{margin:0;color:var(--teal)}}.refs{{margin-bottom:0}}.bottom{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:26px}}.panel h2{{margin-top:0}}.panel ul{{padding-left:18px}}.panel li{{padding:8px 0;border-bottom:1px solid #eee;list-style:none}}.panel li span{{display:block;color:#516273;font-size:14px}}.audit{{margin-top:18px;padding:14px;background:#fff;border:1px solid var(--line);border-radius:12px}}summary{{cursor:pointer;font-weight:bold}}@media(max-width:700px){{.summary,.bottom{{grid-template-columns:1fr 1fr}}}}@media(max-width:450px){{.summary,.bottom{{grid-template-columns:1fr}}}}</style>
    <main><div class='page-top'><p class='eyebrow'>FRIDA · MUNICIPAL STRATEGIC INTELLIGENCE</p><a class='back' href='/'>← BACK TO FRIDA</a></div><p class='execution-label'>UNDER THE HOOD · VERIFIED EXECUTION</p><h1>How FRIDA worked.</h1><p class='lead'>The technical execution view: governed decisions are visible; private model reasoning is not.</p><p style='padding:13px 16px;border-left:5px solid #147b79;background:#edf5f3;border-radius:10px;font:14px Arial,sans-serif'><b>ACCELERATED HISTORICAL REPLAY</b><br>FRIDA moves through approved historical evidence faster than production. Activity shown here was actually executed.</p><section class='summary'><div class='metric'><b>{len(view['telemetry'])}</b><span>model completions</span></div><div class='metric'><b>{view['totals']['total']:,}</b><span>total tokens</span></div><div class='metric'><b>{view['totals']['latency_ms']:,} ms</b><span>cumulative model latency</span></div><div class='metric'><b>0</b><span>retries</span></div></section><section id='live-events' data-event-count='{view['event_count']}' style='height:540px;overflow-y:auto;padding-right:8px;border-top:1px solid #d8d0c3;border-bottom:1px solid #d8d0c3' aria-label='Verified execution events'><div class='sequence' style='padding:12px 0'>{rows}</div></section><div class='bottom'><section class='panel'><h2>Runtime telemetry</h2><ul>{stages}</ul></section><section class='panel'><h2>Logical agent catalogue</h2><ul>{catalogue}</ul></section></div>{correction}<nav class='under-hood-actions'><a class='back' href='/technical-record?execution_id={escape(view['execution_id'])}'>VIEW RAW GOVERNED RECORD</a><a class='back' href='/'>← BACK TO FRIDA</a></nav></main><style>.back{{display:inline-block;background:#fff;border:1px solid #d8d0c3;border-radius:9px;padding:10px 14px}}.under-hood-actions{{display:flex;gap:10px;flex-wrap:wrap;margin:28px 0 0}}</style><script>setInterval(async()=>{{try{{const r=await fetch('/api/v1/live-engine/current');if(!r.ok)return;const v=await r.json();const p=document.getElementById('live-events');if(p&&v.event_count!==undefined&&Number(p.dataset.eventCount)!==v.event_count)location.reload();}}catch(_e){{}}}},3000);</script></html>"""


def render_accelerated_replay_html(replay: dict[str, Any]) -> str:
    rows="".join(f"<div class='replay-row'><time>{escape(str(event['occurred_at']))}</time><b>{escape(str(event['event_type']).upper())}</b><span>{escape(str(event['message']))}</span></div>" for event in replay.get("events",[]))
    snapshots="".join(f"<li><b>Historical evidence: {escape(str(item['source_date']))}</b> · replay insertion: {escape(str(item['inserted_at']))} · {escape(str(item['state']))}</li>" for item in replay.get("snapshots",[]))
    return f"""<main><div class='page-top'><p class='eyebrow'>FRIDA · MUNICIPAL STRATEGIC INTELLIGENCE</p><a class='back' href='/'>← BACK TO FRIDA</a></div><p class='execution-label'>UNDER THE HOOD · HISTORICAL REPLAY</p><h1>FRIDA is reviewing approved historical evidence.</h1><p class='lead'>Historical evidence time and replay execution time remain distinct. Public viewers observe only.</p><section class='panel'><h2>Replay {escape(str(replay['replay_id']))}</h2><p>Status: <b>{escape(str(replay['status']))}</b></p><ul>{snapshots}</ul></section><section id='replay-events' data-event-count='{len(replay.get('events',[]))}' style='height:540px;overflow-y:auto;padding-right:8px;border-top:1px solid #d8d0c3;border-bottom:1px solid #d8d0c3' aria-label='Accelerated historical replay events'><div class='sequence'>{rows}</div></section></main><style>.back{{display:inline-block;background:#fff;border:1px solid #d8d0c3;border-radius:9px;padding:10px 14px;color:#10243a;font:700 13px Arial,sans-serif;text-decoration:none}}.replay-row{{display:grid;grid-template-columns:190px 170px 1fr;gap:12px;padding:11px 0;border-bottom:1px solid #d8d0c3;font:14px Arial,sans-serif}}.replay-row time{{color:#516273}}.replay-row b{{color:#147b79;font-size:11px;letter-spacing:.05em}}</style><script>setInterval(async()=>{{try{{const r=await fetch('/api/v1/replay/status');if(!r.ok)return;const v=await r.json();const p=document.getElementById('replay-events');if(p&&v.events&&Number(p.dataset.eventCount)!==v.events.length)location.reload();}}catch(_e){{}}}},2500);</script>"""

def render_action_html(view: dict[str, Any], cycles: list[dict[str, Any]] | None = None) -> str:
    """Polished executive shell; legacy body remains projection-derived."""
    page=_render_action_legacy(view)
    selected=view.get("selected", {})
    metric=f"{selected.get('value', '—')} {selected.get('unit', '')}".strip()
    page=page.replace("<nav><b>FRIDA in Action</b> · <a href='/foresight'>FRIDA Explained</a><small> — the same governed intelligence, opened for inspection</small></nav>", "")
    page=page.replace("<p class='number'>−65.556761 hm³/year</p><p>Official annual availability · Valle de Querétaro aquifer</p>",f"<p class='number'>{escape(metric)}</p><p>{escape(selected.get('measure', 'Observed condition'))} · {escape(selected.get('geography', 'selected governed geography'))}</p>")
    page=page.replace("A governed water-resilience condition now merits strategic review.", "A governed strategic condition now merits review.")
    page=page.replace("The current aquifer-level condition is a strategic planning constraint. It is observed evidence, not a prediction about future supply.", escape(selected.get("limitation", "This is observed evidence with governed limitations; it is not a prediction.")))
    page=page.replace("WHAT I AM WATCHING","WHAT I'M WATCHING NEXT").replace("CURRENT AUTHORITY","WHAT REQUIRES ATTENTION")
    page=page.replace("href='/foresight#inspect'>Why is this restricted?","href='/restricted'>Why is this restricted?").replace("href='/foresight'>Inspect evidence & governance","href='/evidence'>Inspect evidence & governance")
    page=page.replace("WHAT A DECISION-MAKER SHOULD UNDERSTAND NEXT","WHAT I RECOMMEND REVIEWING NEXT").replace("Review resilience options without pretending certainty.","Strategic options under current evidence limits.").replace("additional assumed pressure.", "a declared strategic variation.").replace("a bounded resilience review.", "a bounded strategic review.").replace("population context into water demand", "context into unsupported causal claims")
    page=page.replace("</style>", ".glass-hood{margin-top:18px}.glass-events{margin-top:15px;border-top:1px solid var(--line)}.glass-cycle{padding:12px 0;border-bottom:1px solid var(--line)}.glass-cycle-id{margin:0 0 8px;font:700 11px Arial;letter-spacing:.07em;color:#516273}.glass-row{display:grid;grid-template-columns:72px 166px 1fr;gap:8px;padding:7px 0;font:13px Arial}.glass-row time{color:#516273}.glass-row b{color:var(--teal);font-size:11px;letter-spacing:.05em}.glass-empty{color:#516273}</style>", 1)
    live_top = "<section class='live-invite top'><p class='label'>LIVE DEMO</p><h2>WATCH FRIDA WORK — LIVE</h2><p>See FRIDA and her specialists work as it happens.</p><a class='button' href='/glass-hood'>WATCH FRIDA WORK — LIVE</a></section>"
    lead_link = "<section class='live-invite bottom'><p class='label'>VERIFIED LEAD-AGENT EXECUTION</p><h2>WATCH FRIDA WORK — LIVE</h2><p>See FRIDA and her specialists work as it happens.</p><a class='button' href='/glass-hood'>WATCH FRIDA WORK — LIVE</a></section>"
    page=page.replace("</section><div class='grid'>", "</section>" + live_top + "<div class='grid'>", 1)
    page=page.replace("</style>", ".live-invite{margin-top:16px;background:#fff;border:1px solid var(--line);border-radius:14px;padding:22px}.live-invite.top{border-left:6px solid var(--teal)}.live-invite h2{margin-bottom:6px}</style>", 1)
    return page.replace("</main></html>", render_glass_hood(cycles or []) + lead_link + "</main></html>")


def render_wow_action_html(cases: list[dict[str, Any]], replay: dict[str, Any] | None, verified_execution_id: str | None = None, advisories: list[dict[str, Any]] | None = None) -> str:
    """Municipal projection of persisted work only; technical detail stays in Glass Hood."""
    """
    current=cases[0] if cases else None
    if current:
        status=escape(str(current.get("disposition", "GOVERNED")))
        hero=f"<p class='eyebrow'>MOST RECENT INTERESTING ITEM</p><h1>{escape(str(current['title']))}</h1><p>{escape(str(current['source']))}</p><p class='status'>{status}</p><a class='button' href='/case?case_id={escape(str(current['case_id']))}'>Understand this case</a>"
    else:
        hero="<p class='eyebrow'>MOST RECENT INTERESTING ITEM</p><h1>FRIDA is watching the city.</h1><p>No persisted item currently warrants executive action.</p>"
    browse="".join(f"<a class='item-nav' href='/case?case_id={escape(str(item['case_id']))}'>{escape(str(item['title']))}<small>{escape(str(item.get('disposition','GOVERNED')))}</small></a>" for item in cases) or "<p>No additional persisted items.</p>"
    event_map={
        'replay.started':'New municipal evidence received','observe.source_examined':'Approved historical evidence examined','signal.none':'Baseline retained — no eligible change','signal.detected':'Change detected','frida.attention_reused':'FRIDA reused a governed attention decision','frida.attention_completed':'FRIDA assessing significance','replay.completed':'Investigation and governance completed','replay.stopped':'Cycle stopped at a governed boundary',
    }
    rows=[]
    activity_kind={'replay.started':'OBSERVING','observe.source_examined':'OBSERVE','signal.none':'OBSERVE','signal.detected':'NOTICE','frida.attention_reused':'FRIDA','frida.attention_completed':'FRIDA','replay.completed':'RESULT','replay.stopped':'STOPPED'}
    for event in (replay or {}).get('events',[]):
        label=event_map.get(str(event['event_type']), 'Governed activity recorded')
        href=(f"/case?case_id={escape(str(replay['snapshots'][1].get('case_id') or ''))}" if replay and len(replay.get('snapshots',[]))>1 and replay['snapshots'][1].get('case_id') else f"/glass-hood?replay_id={escape(str(replay.get('replay_id','')))}")
        rows.append(f"<a class='activity-row' href='{href}'><time>{escape(str(event['occurred_at']))[-14:-6]}</time><b>{activity_kind.get(str(event['event_type']),'ACTIVITY')}</b><span>{escape(label)}</span></a>")
    activity=''.join(rows) or "<p>FRIDA has no persisted cycle events to display.</p>"
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>FRIDA in Action</title><style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.55 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.eyebrow{{font:700 12px Arial;letter-spacing:.12em;color:var(--teal)}}.hero{{background:var(--ink);color:#fff;border-radius:22px;padding:34px}}h1{{font-size:clamp(40px,6vw,68px);line-height:1.04;margin:8px 0 14px}}.status{{font:bold 20px Arial;color:#f3c66f}}.button{{display:inline-block;background:#fff;color:var(--ink);padding:12px 16px;border-radius:9px;text-decoration:none;font:bold 13px Arial}}h2{{margin:30px 0 10px}}.items{{display:flex;gap:10px;overflow-x:auto}}.item-nav{{min-width:220px;padding:14px;background:#fff;border:1px solid var(--line);border-radius:12px;color:var(--ink);text-decoration:none;font-weight:bold}}.item-nav small{{display:block;margin-top:5px;color:var(--teal);font:11px Arial}}.activity{{height:410px;overflow-y:auto;background:#fff;border:1px solid var(--line);border-radius:14px;padding:8px 18px}}.activity-row{{display:grid;grid-template-columns:78px 180px 1fr;gap:10px;padding:12px 0;border-bottom:1px solid var(--line);text-decoration:none;color:var(--ink);font:14px Arial}}.activity-row time{{color:#516273}}.activity-row b{{font-size:11px;color:var(--teal);letter-spacing:.05em}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.metrics article{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px}}.metrics b{{display:block;font:700 24px Arial;color:var(--teal)}}@media(max-width:650px){{.metrics{{grid-template-columns:1fr}}.activity-row{{grid-template-columns:1fr}}}}</style><main><section class="hero">{hero}</section><h2>Recent governed items</h2><nav class="items">{browse}</nav><h2>City activity — live window</h2><section class="activity" id="city-activity" data-event-count="{len((replay or {{}}).get('events',[]))}">{activity}</section><section class="metrics"><article><b>{len(cases)}</b><span>persisted strategic items</span></article><article><b id="cycle-status">{escape(str((replay or {{}}).get('status','NO CYCLE'))}</b><span>latest observation cycle</span></article><article><b>0</b><span>fabricated records</span></article></section></main><script>setInterval(async()=>{{try{{const r=await fetch('/api/v1/replay/status');if(!r.ok)return;const v=await r.json(),box=document.getElementById('city-activity'),dot=document.getElementById('frida-heartbeat'),status=document.getElementById('cycle-status');if(!box||!v.events)return;const count=v.events.length;if(status)status.textContent=v.status||'NO CYCLE';if(dot)dot.classList.toggle('active',v.status==='RUNNING');if(Number(box.dataset.eventCount)===count)return;box.dataset.eventCount=count;box.replaceChildren();v.events.forEach(e=>{{const row=document.createElement('a'),time=document.createElement('time'),kind=document.createElement('b'),text=document.createElement('span');row.className='activity-row';row.href='/glass-hood?replay_id='+encodeURIComponent(v.replay_id||'');time.textContent=String(e.occurred_at||'').slice(-14,-6);kind.textContent={{'replay.started':'OBSERVING','observe.source_examined':'OBSERVE','signal.none':'OBSERVE','signal.detected':'NOTICE','frida.attention_reused':'FRIDA','frida.attention_completed':'FRIDA','replay.completed':'RESULT','replay.stopped':'STOPPED'}}[e.event_type]||'ACTIVITY';text.textContent={{'replay.started':'New municipal evidence received','observe.source_examined':'Approved historical evidence examined','signal.none':'Baseline retained — no eligible change','signal.detected':'Change detected','frida.attention_reused':'FRIDA reused a governed attention decision','frida.attention_completed':'FRIDA assessing significance','replay.completed':'Investigation and governance completed','replay.stopped':'Cycle stopped at a governed boundary'}}[e.event_type]||'Governed activity recorded';row.append(time,kind,text);box.append(row)}});if(dot){{dot.classList.add('active','pulse');setTimeout(()=>dot.classList.remove('pulse'),1000)}}}}catch(_e){{}}}},5000);</script></html>'''


    """


def render_wow_action_html(cases: list[dict[str, Any]], replay: dict[str, Any] | None, verified_execution_id: str | None = None, advisories: list[dict[str, Any]] | None = None) -> str:
    """Municipal projection with a stable shell and live content-only refresh."""
    def executive_status(item: dict[str, Any]) -> tuple[str, str]:
        """A presentation-only projection of already governed records."""
        attention = str(item.get("attention", "")).upper()
        disposition = str(item.get("disposition", "")).upper()
        if attention == "INVESTIGATE" or disposition in {"ACTION_REQUIRED", "ESCALATE"}:
            return "RED", "Strategic attention recommended"
        if attention == "WATCH" or disposition in {"EVIDENCE_INSUFFICIENT", "RESTRICTED", "KEEP_WATCHING"}:
            return "YELLOW", "Continued attention warranted"
        return "GREEN", "No strategic action recommended"

    ranked = sorted(cases, key=lambda item: {"RED": 0, "YELLOW": 1, "GREEN": 2}[executive_status(item)[0]])
    current = ranked[0] if ranked else None
    advisory = next((item for item in advisories or [] if str(item.get("result", {}).get("strategic_interest")) == "POSSIBLE"), None)
    if current:
        flag, flag_label = executive_status(current)
        hero = (f"<p class='eyebrow'>MOST RECENT INTERESTING ITEM</p><h1>{escape(str(current['title']))}</h1>"
                f"<p>{escape(str(current['source']))}</p><p class='status status-{flag.lower()}'><span class='status-flag'>⚑</span> {flag} FLAG · {escape(flag_label)}</p>"
                f"<a class='button' href='/case?case_id={escape(str(current['case_id']))}'>Understand this case</a>")
    elif advisory:
        appraisal = advisory["result"]
        hero = ("<p class='eyebrow'>ADVISORY STRATEGIC HYPOTHESIS</p><h1>FRIDA found a question worth watching.</h1>"
                "<p class='status status-yellow'><span class='status-flag'>⚑</span> YELLOW FLAG · Advisory, not canonical Attention</p>"
                f"<p>{escape(str(appraisal.get('strategic_question', 'A governed strategic question is retained.')))}</p>"
                f"<a class='button' href='/advisory?appraisal_id={escape(str(advisory['record_id']))}'>Understand this advisory</a>")
    else:
        hero = "<p class='eyebrow'>LATEST OBSERVATION</p><h1>FRIDA is watching the city.</h1><p class='status status-green'><span class='status-flag'>⚑</span> GREEN FLAG · No strategic concern detected at this time.</p><p>FRIDA continues observing London; a routine observation is not a Case.</p>"
    if verified_execution_id:
        hero += (f"<div class='judge-path'><a class='button' href='/foresight?execution_id={escape(verified_execution_id)}'>"
                 "Inspect how FRIDA worked</a></div>")
    elif not current:
        hero += ("<div class='judge-path'><a class='button' href='/foresight'>"
                 "See how FRIDA is observing</a><p class='tour-note'>No London investigation is available yet."
                 " FRIDA is currently observing London.</p></div>")
    advisory_items = "".join(
        f"<a class='item-nav' href='/advisory?appraisal_id={escape(str(item['record_id']))}'><span class='item-flag item-yellow'>⚑ YELLOW FLAG</span>{escape(str(item['result'].get('strategic_question', 'Strategic advisory')))}<small>Advisory hypothesis · not canonical Attention</small></a>"
        for item in advisories or [] if str(item.get("result", {}).get("strategic_interest")) == "POSSIBLE"
    )
    items = advisory_items + "".join(f"<a class='item-nav' href='/case?case_id={escape(str(item['case_id']))}'><span class='item-flag item-{executive_status(item)[0].lower()}'>⚑ {executive_status(item)[0]} FLAG</span>{escape(str(item['title']))}<small>{escape(executive_status(item)[1])}</small></a>" for item in ranked) or "<p>No current London strategic attention item exists.</p>"
    event_labels = {'replay.started': ('OBSERVING', 'New municipal evidence received'), 'observe.source_examined': ('OBSERVE', 'Approved historical evidence examined'), 'signal.none': ('OBSERVE', 'Baseline retained — no eligible change'), 'signal.detected': ('NOTICE', 'Change detected'), 'frida.attention_reused': ('FRIDA', 'FRIDA reused a governed attention decision'), 'frida.attention_completed': ('FRIDA', 'FRIDA assessing significance'), 'replay.completed': ('RESULT', 'Investigation and governance completed'), 'replay.stopped': ('STOPPED', 'Cycle stopped at a governed boundary')}
    # Current activity is loaded from the active assignment's observation
    # cycles by the shell.  A historical replay must never become the default
    # live-city narrative merely because it happens to be the latest replay.
    events: list[dict[str, Any]] = []
    rows = "<p class='activity-empty'>Loading current governed observation activity…</p>"
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA in Action</title><style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.55 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.product-identity,.eyebrow{{font:700 12px Arial;letter-spacing:.12em;color:var(--teal)}}.product-identity{{margin:0 0 16px}}.hero{{background:var(--ink);color:#fff;border-radius:22px;padding:34px}}h1{{font-size:clamp(40px,6vw,68px);line-height:1.04;margin:8px 0 14px}}.status{{font:bold 16px Arial}}.status-flag{{font-size:23px;vertical-align:-2px}}.status-green,.item-green{{color:#5bc792}}.status-yellow,.item-yellow{{color:#f3c66f}}.status-red,.item-red{{color:#ef806a}}.button{{display:inline-block;background:#fff;color:var(--ink);padding:12px 16px;border-radius:9px;text-decoration:none;font:bold 13px Arial}}.audit-button{{background:#10243a;color:#fff}}.judge-path{{margin-top:22px;padding-top:16px;border-top:1px solid rgba(255,255,255,.24)}}.tour-note{{margin:10px 0 0;color:#e5f0ef;font:14px Arial}}h2{{margin:30px 0 10px}}.section-note{{margin:-4px 0 10px;color:#516273;font:13px Arial}}.items{{display:flex;gap:10px;overflow-x:auto}}.item-nav{{min-width:220px;padding:14px;background:#fff;border:1px solid var(--line);border-radius:12px;color:var(--ink);text-decoration:none;font-weight:bold}}.item-flag{{display:block;font:700 11px Arial;letter-spacing:.06em;margin-bottom:6px}}.item-nav small{{display:block;margin-top:5px;color:#516273;font:11px Arial}}.activity{{height:410px;overflow-y:auto;background:#fff;border:1px solid var(--line);border-radius:14px;padding:8px 18px}}.activity-row{{display:grid;grid-template-columns:132px 150px 1fr;gap:10px;padding:12px 0;border-bottom:1px solid var(--line);text-decoration:none;color:var(--ink);font:14px Arial}}.activity-row time{{color:#516273}}.activity-row b{{font-size:11px;color:var(--teal);letter-spacing:.05em}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.metrics article{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px}}.metrics b{{display:block;font:700 24px Arial;color:var(--teal)}}@media(max-width:650px){{.metrics{{grid-template-columns:1fr}}.activity-row{{grid-template-columns:1fr}}}}</style><main><p class='product-identity'>FRIDA · STRATEGIC URBAN INTELLIGENCE</p><section class='hero'>{hero}</section><h2>FRIDA’s attention</h2><p class='section-note'>Strategic Yellow/Watch-type and Red items only; priority first, then recency.</p><nav class='items'>{items}</nav><h2 id='city-activity-heading'>All observation activity</h2><p class='section-note'>Current official observation activity. Recent routine / Green activity is transparent audit access, not the attention queue.</p><section class='activity' id='city-activity' data-event-count='0'>{rows}</section><p><a class='button audit-button' href='/history'>VIEW ALL OBSERVATION ACTIVITY</a></p><section id='observation-pulse' aria-live='polite'><b>OBSERVATION PULSE</b><span>Loading current official observation status…</span></section><section class='metrics'><article><b>{len(cases) + (1 if advisory else 0)}</b><span>current strategic items</span></article><article><b id='cycle-status'>CURRENT</b><span>active observation context</span></article><article><b>0</b><span>fabricated records</span></article></section></main></html>"""


def _assignment_name(assignment: dict[str, Any]) -> str:
    return f"{assignment.get('city_name', 'Active city')}, {assignment.get('country_name', '')}".rstrip(", ")


def render_active_assignment_explained_html(assignment: dict[str, Any], control: dict[str, Any], advisories: list[dict[str, Any]] | None = None) -> str:
    """Current-city Judge view.  It never falls back to archived execution data."""
    city = escape(_assignment_name(assignment))
    state = escape(str(control.get("state", "STOPPED")).replace("_", " "))
    health = escape(str(control.get("source_health", "UNKNOWN")).replace("_", " "))
    advisory = next((item for item in (advisories or []) if str(item.get("result", {}).get("strategic_interest")) == "POSSIBLE"), None)
    appraisal = ("<section class='grid'><article><b>CURRENT ADVISORY APPRAISAL</b>"
                 f"<p>POSSIBLE / {escape(str(advisory['result'].get('opportunity_family', 'UNKNOWN')).replace('_', ' '))}</p>"
                 f"<p><a class='assignment-action' href='/advisory?appraisal_id={escape(str(advisory['record_id']))}'>INSPECT ADVISORY →</a></p>"
                 "<p>It is a persisted advisory hypothesis, not canonical Attention, a Signal, Candidate or Case.</p></article></section>") if advisory else ""
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA Explained — Current assignment</title>
    <style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.eyebrow{{font:700 12px Arial;letter-spacing:.12em;color:var(--teal)}}.hero{{background:var(--ink);color:#fff;border-radius:22px;padding:34px}}h1{{font-size:clamp(40px,6vw,64px);line-height:1.04;margin:8px 0}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:16px}}article{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:20px}}.active-assignment b{{color:var(--teal)}}.active-assignment .assignment-action{{display:inline-block;margin-top:20px;background:var(--ink);color:#fff;border-radius:9px;padding:11px 15px;text-decoration:none;font:bold 13px Arial}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style>
    <main class='active-assignment'><p class='eyebrow'>FRIDA · STRATEGIC URBAN INTELLIGENCE</p><section class='hero'><p class='eyebrow'>CURRENT ASSIGNMENT · LIVE OBSERVATION</p><h1>FRIDA is observing {city}.</h1><p>This view reflects the active London source fabric, not a historical case or replay.</p></section><section class='grid'><article><b>LIVE STATUS</b><p>{state}</p></article><article><b>SOURCE HEALTH</b><p>{health}</p></article><article><b>GOVERNANCE</b><p>Routine source activity cannot create a Signal or strategic conclusion on its own.</p></article></section>{appraisal}<h2>How to read the activity</h2><p>FRIDA retains attributable source observations, compares normalized operational state and keeps ordinary change separate from strategic attention. No current London case is shown until the governed path actually creates one.</p><a class='assignment-action' href='/glass-hood'>OPEN CURRENT ENGINE VIEW →</a></main></html>"""


def render_active_assignment_history_html(assignment: dict[str, Any], cycles: list[dict[str, Any]]) -> str:
    """Current assignment history, deliberately separate from archived Case records."""
    city = escape(_assignment_name(assignment))
    rows = "".join(
        f"<article><p class='tag'>{escape(str(c.get('status', 'RECORDED')).replace('_', ' '))}</p><h2>{escape(str(c.get('started_at', '')))}</h2><p>{escape(str(c.get('source_count', 0)))} official source(s) examined. The event trace is available under the hood.</p><a href='/glass-hood'>Inspect this active context →</a></article>"
        for c in cycles
    ) or "<article><h2>No London observation cycle has been retained yet.</h2><p>FRIDA does not fabricate activity.</p></article>"
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA — Current History</title><style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.eyebrow,.tag{{font:700 12px Arial;letter-spacing:.11em;color:var(--teal)}}h1{{font-size:clamp(40px,6vw,64px);margin:8px 0}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}article{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:22px}}h2{{margin:6px 0;font-size:24px}}.active-history a{{color:var(--ink);font-weight:bold}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style><main class='active-history'><p class='eyebrow'>CURRENT ASSIGNMENT · {city.upper()}</p><h1>Live observation history</h1><p>Only the active assignment appears here.</p><section class='grid'>{rows}</section></main></html>"""


def render_active_observation_hood_html(assignment: dict[str, Any], cycles: list[dict[str, Any]]) -> str:
    city = escape(_assignment_name(assignment))
    rows = "".join(
        f"<article><b>{escape(str(event.get('event_type', 'activity')).replace('.', ' ').upper())}</b><time>{escape(str(event.get('occurred_at', '')))}</time><p>{escape(str(event.get('message', 'Governed observation activity recorded.')))}</p></article>"
        for cycle in cycles for event in cycle.get("events", [])
    ) or "<article><p>No current active-assignment events have been retained.</p></article>"
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA — Engine View</title><style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.top{{display:flex;justify-content:space-between;align-items:center;gap:12px}}.eyebrow{{font:700 12px Arial;letter-spacing:.12em;color:var(--teal)}}h1{{font-size:clamp(40px,6vw,64px);margin:8px 0}}article{{padding:16px 0;border-bottom:1px solid var(--line)}}article b{{color:var(--teal);font:700 11px Arial;letter-spacing:.08em}}time{{display:block;color:#516273;font:12px Arial;margin-top:4px}}.active-hood .back-to-frida{{display:inline-block;background:#fff;border:1px solid var(--line);border-radius:9px;padding:11px 15px;color:var(--ink);text-decoration:none;font:bold 13px Arial}}</style><main class='active-hood'><div class='top'><p class='eyebrow'>UNDER THE HOOD · CURRENT ASSIGNMENT</p><a class='back-to-frida' href='/'>← BACK TO FRIDA</a></div><h1>How FRIDA is observing {city}.</h1><p>These are real active-assignment observation events. They are not a historical semantic execution or a strategic finding.</p><section>{rows}</section></main></html>"""


def render_execution_explained_html(view: dict[str, Any]) -> str:
    """Judge disclosure for the same persisted execution, without model reasoning."""
    rows="".join(f"<article><b>{escape(row['actor']['label'])}</b><p>{escape(row['action'])} · <strong>{escape(row['decision'])}</strong></p><p>{escape(row['detail'])}</p></article>" for row in view['rows'])
    return f"""<!doctype html><title>FRIDA Explained — Execution</title><style>:root{{--ink:#10243a;--paper:#f7f3eb;--teal:#147b79;--line:#d8d0c3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.55 Georgia,serif}}main{{max-width:1000px;margin:auto;padding:36px 24px 76px}}.eyebrow{{font:700 12px Arial;letter-spacing:.12em;color:var(--teal)}}.hero{{background:var(--ink);color:#fff;border-radius:22px;padding:32px}}h1{{font-size:clamp(40px,6vw,64px);line-height:1.04}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}}.grid article,article{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px}}.button{{display:inline-block;background:var(--ink);color:#fff;padding:12px 16px;border-radius:9px;text-decoration:none;font:bold 13px Arial}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style><main><p class='eyebrow'>FRIDA · MUNICIPAL STRATEGIC INTELLIGENCE</p><section class='hero'><p class='eyebrow'>SAME EXECUTION · TECHNICAL DISCLOSURE</p><h1>How FRIDA reached the governed result.</h1><p>Execution {escape(view['execution_id'])}. Decisions and evidence references are inspectable; private model reasoning is not.</p></section><section class='grid'><article><b>FRIDA Attention</b><p>{escape(str(view.get('attention') or 'GOVERNED'))}</p></article><article><b>Independent Challenger</b><p>{escape(next((row['decision'] for row in view['rows'] if row['actor']['label']=='INDEPENDENT CHALLENGER'),'NOT REACHED'))}</p></article><article><b>Governance</b><p>{escape(str(view.get('disposition') or 'NOT ISSUED'))}</p></article></section><h2>Same journey, expanded</h2>{rows}<p><a class='button' href='/glass-hood?execution_id={escape(view['execution_id'])}'>Detailed technical execution →</a></p></main>"""
