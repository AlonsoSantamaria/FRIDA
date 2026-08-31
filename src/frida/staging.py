"""Restricted technical-staging HTTP surface for the deterministic FRIDA core."""
from __future__ import annotations

import json
import os
import hmac
import hashlib
import secrets
import time
from urllib.parse import quote
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .domain import EvidenceClass
from .observation import DenueObserver, ObservationAuditEvent, ReplaySnapshot, SemaforoObserver, validate_and_prepare
from .persistence import StagingStore
from .postgres_store import PostgresStore
from .case_spine import CaseSpine
from .demo_view import render_html, render_foresight_html, render_action_html, render_wow_action_html, render_execution_explained_html, render_lead_glass_hood_html, render_accelerated_replay_html, render_enduser_explanation, render_history_html, render_case_presentation_html, render_case_history_html, render_active_assignment_explained_html, render_active_assignment_history_html, render_active_observation_hood_html, foresight_projection, render_shell
from .lead_projection import current_lead_projection, raw_governed_record_projection
from .case_presentation import case_index, select_case
from .accelerated_replay import AcceleratedHistoricalReplay
from .smn_probe import probe_queretaro_forecast, SMNProbeError
from .tfl_probe import probe_victoria_line
from .golden_path import wp01_current_evidence
from .live_observation import LiveObservationCycle
from .observation_control import AutonomousObservationController, DEFAULT_CADENCE_SECONDS
from .taipei_observation import TaipeiObservationFabricProvider, classify_state
from .london_observation import LondonObservationFabricProvider
from .city_assignment import LONDON_ASSIGNMENT_ID, public_identity
from .london_time_travel import LondonTimeTravel
from .temporal_pattern_memory import assess
from .first_appraisal import FirstAppraisalBlocked, FirstAppraisalService
from .advisory_projection import render_advisory_html, render_advisory_raw_html, select_advisory
from .briefing_projection import render_briefings_html, render_brief_html
from .strategic_briefing import HISTORICAL_BRIEF_CUTOFFS, StrategicBriefingService
from .operator_view import render_operator_html
from .postgres_migrate import apply_schema, import_london_intelligence


class StagingService:
    def __init__(self, database_path: str, foresight_database_path: str = "data/frida-foresight.sqlite3", database_url: str | None = None, source_provider=None):
        self.store = PostgresStore(database_url) if database_url else StagingStore(database_path)
        self.case_spine = CaseSpine(self.store)
        self.foresight_database_path = foresight_database_path
        self.observers = {"DENUE": DenueObserver(), "SEMAFORO": SemaforoObserver()}
        self.replay = AcceleratedHistoricalReplay(self.store, os.environ.get("FRIDA_APPROVED_EVIDENCE_ROOT", "data/source-validation/wp01/denue/raw"))
        # A source is deliberately not selected by the operator.  When Product
        # authorizes one, it is wired here through the existing provider boundary.
        if source_provider is None and os.environ.get("FRIDA_LONDON_FABRIC_ENABLED", "").lower() in {"1", "true", "yes"}:
            source_provider = LondonObservationFabricProvider(
                due_source_ids=lambda: self.store.due_observation_sources(LONDON_ASSIGNMENT_ID, datetime.now(tz=timezone.utc)),
                source_completed=lambda source_id, error: self.store.complete_observation_source(LONDON_ASSIGNMENT_ID, source_id, error),
            )
        if source_provider is None and os.environ.get("FRIDA_TAIPEI_FABRIC_ENABLED", "").lower() in {"1", "true", "yes"}:
            source_provider = TaipeiObservationFabricProvider()
        self.observation_control = AutonomousObservationController(
            self.store, lambda provider: LiveObservationCycle(self, provider), provider=source_provider
        )
        self.observation_control.start_worker()

    def close(self) -> None:
        self.observation_control.close()
        self.store.close()

    def observation_status(self) -> dict[str, object]:
        return {**self.store.observation_control(), "authorized_source_configured": self.observation_control.provider_configured, "active_assignment": self.store.active_assignment()}

    def activate_london_assignment(self) -> dict[str, object]:
        now=datetime.now(tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        queretaro=self.store.create_assignment_archive('archive-queretaro-'+now, 'QUERETARO_HISTORICAL_ARCHIVE')
        taipei=self.store.create_assignment_archive('archive-taipei-'+now, 'TAIPEI_TECHNICAL_ARCHIVE')
        if not self.store.verify_assignment_archive(str(queretaro['archive_id'])):
            raise RuntimeError('Querétaro archive verification failed')
        if not self.store.verify_assignment_archive(str(taipei['archive_id'])):
            raise RuntimeError('Taipei archive verification failed')
        assignment=self.store.activate_london_assignment()
        return {"assignment": assignment, "archives": [queretaro,taipei], "observation_state": self.observation_status()}

    def start_observation(self, cadence_seconds: object = DEFAULT_CADENCE_SECONDS) -> dict[str, object]:
        self.store.start_observation_control(cadence_seconds)
        if not self.observation_control.provider_configured:
            self.store.set_observation_source_health("NO_AUTHORIZED_SOURCE_CONFIGURED")
        return self.observation_status()

    def pause_observation(self) -> dict[str, object]:
        self.store.pause_observation_control(); return self.observation_status()

    def resume_observation(self) -> dict[str, object]:
        self.store.resume_observation_control(); return self.observation_status()

    def stop_observation(self) -> dict[str, object]:
        self.store.stop_observation_control(); return self.observation_status()

    def capture_source_fabric_snapshot(self, snapshot: dict[str, object], previous: dict[str, object] | None) -> dict[str, str]:
        """Persist acquisition before the separate future eligibility/Signal boundary."""
        assignment_id=str((self.store.active_assignment() or {}).get("assignment_id") or "TAIPEI_TECHNICAL_ARCHIVE")
        previous_hash = str(previous["state_fingerprint_sha256"]) if previous else None
        current = type("SourceState", (), {"fingerprint_sha256": snapshot["fingerprint_sha256"]})()
        classification = classify_state(previous_hash, current)
        observation_id = self.store.append_source_fabric_observation(snapshot, classification, assignment_id)
        # Memory can compare compatible persisted sources, but it is strictly
        # informational until a later, separately governed eligibility phase.
        history = self.store.recent_source_fabric_observations_all(assignment_id=assignment_id)
        assessment = assess(history)
        assessment_id = self.store.append_temporal_pattern_assessment(assessment, assignment_id)
        return {"classification": classification, "pattern_assessment_id": assessment_id, "pattern_state": assessment.state, "source_observation_id": observation_id}

    def first_appraise_london_change(self, observation: dict[str, object]) -> tuple[dict[str, object], dict[str, object]] | None:
        """Optional, bounded cognition after factual capture; it never dispatches research."""
        active = self.store.active_assignment() or {}
        assignment_id = str(active.get("assignment_id") or "")
        if assignment_id != LONDON_ASSIGNMENT_ID or os.environ.get("FRIDA_FIRST_APPRAISAL_ENABLED", "").lower() not in {"1", "true", "yes"}:
            return None
        stages = FirstAppraisalService(self.store)
        try:
            return stages.appraise(assignment_id, (observation,))
        finally:
            stages.close()

    def probe_taipei_fabric(self, *, persist_baseline: bool = False) -> list[dict[str, object]]:
        reports=[]
        for source in TaipeiObservationFabricProvider().snapshots():
            snapshot=source.persisted()
            previous=self.store.latest_source_fabric_observation(str(snapshot["source_id"]))
            captured=self.capture_source_fabric_snapshot(snapshot, previous) if persist_baseline else {"classification": classify_state(str(previous["state_fingerprint_sha256"]) if previous else None, source)}
            classification=str(captured["classification"])
            items=snapshot["canonical_state"].get("stations", snapshot["canonical_state"].get("active_works", []))
            reports.append({"source_id":snapshot["source_id"],"source_timestamp":snapshot["source_timestamp"],"retrieved_at":snapshot["retrieved_at"],"state_fingerprint_sha256":snapshot["fingerprint_sha256"],"classification":classification,"station_or_work_count":len(items)})
        return reports

    def start_accelerated_replay(self, authorization_reference: str) -> dict[str, object]:
        """Private control path.  It advances deterministic history only;
        semantic Option 2.5 dispatch remains held until separate clearance."""
        replay_id=self.replay.start(authorization_reference)
        first=self.replay.process_deterministic_snapshot(replay_id, 1)
        second=self.replay.process_deterministic_snapshot(replay_id, 2)
        return {"replay_id":replay_id,"first":first,"current":second,"model_calls":0}

    def start_live_deterministic_replay(self, authorization_reference: str) -> dict[str, object]:
        replay_id = self.replay.start_live_deterministic_progression(authorization_reference)
        return {"replay_id": replay_id, "status": "RUNNING", "model_calls": 0, "progression": "PERSISTED_INCREMENTAL"}

    def start_london_time_travel(self, authorization_reference: str) -> dict[str, object]:
        if str((self.store.active_assignment() or {}).get("assignment_id")) != LONDON_ASSIGNMENT_ID:
            raise RuntimeError("London must be the active assignment")
        replay_id=LondonTimeTravel(self.store).start(authorization_reference)
        return {"replay_id":replay_id,"status":"RUNNING","model_calls":0,"mode":"LONDON_ACCELERATED_HISTORICAL_REPLAY"}

    def create_historical_strategic_brief(self, cutoff: date) -> dict[str, object]:
        """Run one allow-listed, cutoff-enforced historical briefing in Cloud."""
        if cutoff not in HISTORICAL_BRIEF_CUTOFFS:
            raise ValueError("historical briefing cutoff is not approved")
        briefing = StrategicBriefingService(self.store)
        try:
            brief_id, _, brief, meta = briefing.create_historical(cutoff)
            return {"brief_id": brief_id, "historical_as_of": cutoff.isoformat(),
                    "executive_posture": brief["executive_posture"],
                    "semantic_status": brief["semantic_status"], "runtime_meta": meta}
        finally:
            briefing.close()

    def run_accelerated_replay(self, replay_id: str, authorization_reference: str) -> dict[str, object]:
        if os.environ.get("FRIDA_REPLAY_RUNTIME_ENABLED", "").lower() not in {"1","true","yes"}:
            raise RuntimeError("accelerated replay semantic runtime is not authorized")
        return self.replay.run_authorized_semantic_path(replay_id, wp01_current_evidence(datetime.now().astimezone()), authorization_reference)

    def stop_deterministic_replay(self, replay_id: str) -> None:
        self.replay.stop_deterministic_verification(replay_id)

    def ingest(self, payload: dict[str, object]) -> dict[str, object]:
        snapshot = ReplaySnapshot(
            source_id=str(payload["source_id"]), source_reference=str(payload["source_reference"]),
            source_date=datetime.fromisoformat(str(payload["source_date"])), content_hash=str(payload["content_hash"]),
            evidence_class=EvidenceClass(str(payload["evidence_class"])), replay_sequence=int(payload["replay_sequence"]),
            observed_at=datetime.fromisoformat(str(payload["observed_at"])),
        )
        observer = self.observers.get(snapshot.source_id)
        if observer is None:
            raise ValueError("source_id is not an approved staging observer")
        result = self.case_spine.observe(snapshot)
        if result["state"] == "DUPLICATE":
            audit=(ObservationAuditEvent("observation.received", snapshot.source_id, snapshot.content_hash), ObservationAuditEvent("signal.deduplicated", snapshot.source_id, "known_hash"))
            self.store.record_audit(audit)
            return {"signal_id": None, "candidate_signal": None, "attention_state": "NOT_CREATED_DUPLICATE", "audit": [event.event_type for event in audit]}
        audit=(ObservationAuditEvent("observation.received", snapshot.source_id, snapshot.content_hash), ObservationAuditEvent("signal.created", snapshot.source_id, str(result["signal_id"])), ObservationAuditEvent("frida_attention.pending", snapshot.source_id, str(result["state"])))
        self.store.record_audit(audit)
        return {
            "signal_id": result["signal_id"], "candidate_signal": None,
            "attention_state": result["state"],
            "audit": [event.event_type for event in audit],
        }


def build_handler(service: StagingService, token: str, *, public_readonly: bool = False):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: HTTPStatus, body: dict[str, object], headers: dict[str, str] | None = None) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            for key, value in (headers or {}).items(): self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def _html(self, status: HTTPStatus, body: str, headers: dict[str, str] | None = None) -> None:
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            for key, value in (headers or {}).items(): self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, location: str, headers: dict[str, str] | None = None) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items(): self.send_header(key, value)
            self.end_headers()
        def _logo(self) -> None:
            data=(Path(__file__).parent / 'assets' / 'Frida-logo.png').read_bytes(); self.send_response(200); self.send_header('Content-Type','image/png'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

        def _taipei_logo(self) -> None:
            data=(Path(__file__).parent / 'assets' / 'taipei-city-government-logo.jpg').read_bytes(); self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

        def _flower_icon(self) -> None:
            deployed = Path('/app/branding/frida-flower-icon.png')
            local = Path(__file__).parents[2] / 'docs' / 'History docs & images' / 'FRIDA_flower_icon_actual.png'
            data = (deployed if deployed.exists() else local).read_bytes()
            self.send_response(200); self.send_header('Content-Type','image/png'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

        def _london_coat_of_arms(self) -> None:
            data=(Path(__file__).parent / 'assets' / 'london-city-coat-of-arms.svg').read_bytes(); self.send_response(200); self.send_header('Content-Type','image/svg+xml'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

        def _operator_session(self) -> str | None:
            expires = str(int(time.time()) + 1800)
            signature = hmac.new(token.encode(), expires.encode(), hashlib.sha256).hexdigest()
            return f"frida_operator={expires}.{signature}; Max-Age=1800; Path=/; Secure; HttpOnly; SameSite=Strict"

        def _new_operator_access_path(self) -> str:
            code = secrets.token_urlsafe(32)
            digest = hashlib.sha256(code.encode()).hexdigest()
            expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=2)
            service.store.create_operator_access_link(digest, expires_at)
            return "/private-access?code=" + quote(code, safe="")

        def _consume_operator_access_path(self, code: str | None) -> bool:
            if not code or len(code) > 256:
                return False
            digest = hashlib.sha256(code.encode()).hexdigest()
            return service.store.consume_operator_access_link(digest, datetime.now(tz=timezone.utc))

        def _valid_session(self) -> bool:
            cookie = self.headers.get("Cookie", "")
            value = next((part.split("=", 1)[1] for part in cookie.split(";") if part.strip().startswith("frida_operator=")), "")
            if "." not in value: return False
            expires, signature = value.split(".", 1)
            expected = hmac.new(token.encode(), expires.encode(), hashlib.sha256).hexdigest()
            return expires.isdigit() and int(expires) >= int(time.time()) and hmac.compare_digest(signature, expected)

        def _authorized(self) -> bool:
            return self.headers.get("Authorization") == f"Bearer {token}" or self._valid_session()

        def _can_read(self, path: str) -> bool:
            return self._authorized() or (public_readonly and path in {
                "/", "/action", "/foresight", "/history", "/case", "/glass-hood", "/technical-record",
                "/restricted", "/evidence", "/advisory", "/briefings", "/briefing", "/healthz", "/readyz", "/favicon.ico", "/assets/frida-logo.png", "/assets/frida-flower-icon.png", "/assets/taipei-city-government-logo.jpg", "/assets/london-city-coat-of-arms.svg",
                "/api/v1/live-engine/current",
                "/api/v1/replay/status",
                "/api/v1/observation/status",
                "/api/v1/observation/recent",
                "/api/v1/assignment/active",
            })

        def _london_is_active(self) -> bool:
            active = service.store.active_assignment() or {}
            return str(active.get("assignment_id")) == LONDON_ASSIGNMENT_ID

        def _foreign_artifact_unavailable(self) -> None:
            """Fail closed instead of projecting another client's records in London."""
            return self._html(
                HTTPStatus.NOT_FOUND,
                "<main><h1>FRIDA</h1><p>This governed artifact is not available for the London assignment.</p></main>",
                {"Cache-Control": "no-store"},
            )

        def do_GET(self) -> None:
            request=urlparse(self.path); path=request.path; query=parse_qs(request.query)
            if path in {"/healthz", "/readyz"}:
                return self._json(HTTPStatus.OK, {"status": "ok"})
            if path == "/private-access":
                if not self._consume_operator_access_path(query.get("code", [None])[0]):
                    return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"}, {"Cache-Control": "no-store"})
                return self._redirect("/control", {"Set-Cookie": self._operator_session()})
            if not self._can_read(path): return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"})
            if path == '/favicon.ico': return self._flower_icon()
            if path == '/assets/frida-logo.png': return self._logo()
            if path == '/assets/frida-flower-icon.png': return self._flower_icon()
            if path == '/assets/taipei-city-government-logo.jpg': return self._taipei_logo()
            if path == '/assets/london-city-coat-of-arms.svg': return self._london_coat_of_arms()
            if path == "/api/v1/staging/status":
                return self._json(HTTPStatus.OK, service.store.status())
            if path == "/api/v1/replay/status":
                return self._json(HTTPStatus.OK, service.store.accelerated_replay() or {"status":"NO_REPLAY"})
            if path == "/api/v1/observation/status":
                return self._json(HTTPStatus.OK, service.observation_status())
            if path == "/api/v1/observation/recent":
                return self._json(HTTPStatus.OK, service.store.recent_observation_cycles())
            if path == "/api/v1/assignment/active":
                assignment = service.store.active_assignment()
                return self._json(HTTPStatus.OK, {"assignment": {**(assignment or {}), **public_identity(assignment)}})
            if path == "/api/v1/briefings/metadata":
                # Operator-only audit read; public briefing pages remain the
                # editorial projection and never expose runtime metadata.
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error":"restricted"})
                brief_id=query.get("brief_id", [None])[0]
                item=next((x for x in service.store.strategic_briefs() if str(x["brief_id"])==str(brief_id)), None)
                if item is None: return self._json(HTTPStatus.NOT_FOUND, {"error":"not found"})
                audit = {key:item.get(key) for key in ("brief_id", "created_at", "brief_type", "status", "historical_as_of", "evidence_ids", "runtime_meta")}
                return self._json(HTTPStatus.OK, json.loads(json.dumps(audit, default=str)))
            if path in {"/operator", "/control"}:
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"})
                session = {"Set-Cookie": self._operator_session()} if self.headers.get("Authorization") == f"Bearer {token}" else None
                return self._html(HTTPStatus.OK, render_operator_html(service.observation_status()), session)
            if path == "/api/v1/operator/access-link":
                if self.headers.get("Authorization") != f"Bearer {token}":
                    return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"})
                return self._json(HTTPStatus.OK, {"access_path": self._new_operator_access_path(), "expires_in_seconds": 120}, {"Cache-Control": "no-store"})
            if path == "/api/v1/golden-path/latest":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"})
                view = service.store.latest_golden_path_view()
                return self._json(HTTPStatus.OK, view or {"status": "PRE_RUNTIME_READY"})
            if path == "/api/v1/probe/london-tfl":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"})
                try:
                    return self._json(HTTPStatus.OK, probe_victoria_line(os.environ.get("FRIDA_TFL_APP_KEY")))
                except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
                    return self._json(HTTPStatus.BAD_GATEWAY, {"error": type(error).__name__})
            if path == "/golden-path":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"})
                view = service.store.latest_golden_path_view()
                if view is None: return self._html(HTTPStatus.OK, "<main><h1>FRIDA</h1><p>PRE-RUNTIME READY</p></main>")
                return self._html(HTTPStatus.OK, render_html(view))
            if path == "/technical-record":
                execution_id = query.get("execution_id", [None])[0]
                appraisal_id = query.get("appraisal_id", [None])[0]
                if appraisal_id:
                    advisory = select_advisory(service.store.london_advisories(), appraisal_id)
                    if advisory is None: return self._foreign_artifact_unavailable()
                    return self._html(HTTPStatus.OK, render_shell(render_advisory_raw_html(advisory), "explained"))
                if self._london_is_active():
                    return self._foreign_artifact_unavailable()
                view = raw_governed_record_projection(service.store, execution_id) or service.store.latest_golden_path_view()
                if view is None: return self._html(HTTPStatus.OK, "<main><h1>FRIDA</h1><p>RAW GOVERNED RECORD UNAVAILABLE</p></main>")
                return self._html(HTTPStatus.OK, render_shell(render_html(view), "explained"))
            if path == "/glass-hood":
                active = service.store.active_assignment() or {}
                if self._london_is_active() and (query.get("execution_id") or query.get("replay_id")):
                    return self._foreign_artifact_unavailable()
                if not query.get("execution_id") and not query.get("replay_id") and str(active.get("assignment_id")) == LONDON_ASSIGNMENT_ID:
                    return self._html(HTTPStatus.OK, render_shell(render_active_observation_hood_html(active, service.store.recent_observation_cycles()), 'action'))
                replay=service.store.accelerated_replay(query.get("replay_id", [None])[0])
                if replay is not None and (query.get("replay_id") or replay.get("status") in {"RUNNING","PAUSED"}):
                    return self._html(HTTPStatus.OK, render_shell(render_accelerated_replay_html(replay), 'action'))
                view = current_lead_projection(service.store, query.get("execution_id", [None])[0])
                if view is None: return self._html(HTTPStatus.OK, "<main><h1>FRIDA</h1><p>Verified Lead execution unavailable.</p></main>")
                return self._html(HTTPStatus.OK, render_shell(render_lead_glass_hood_html(view), 'action'))
            if path == "/api/v1/live-engine/current":
                return self._json(HTTPStatus.OK, current_lead_projection(service.store) or {"status": "NO_EXECUTION"})
            if path == "/foresight":
                active = service.store.active_assignment() or {}
                if self._london_is_active() and query.get("execution_id"):
                    return self._foreign_artifact_unavailable()
                if not query.get("execution_id") and str(active.get("assignment_id")) == LONDON_ASSIGNMENT_ID:
                    return self._html(HTTPStatus.OK, render_shell(render_active_assignment_explained_html(active, service.observation_status(), service.store.london_advisories()), 'explained'))
                execution=current_lead_projection(service.store, query.get("execution_id", [None])[0])
                if execution is not None:
                    return self._html(HTTPStatus.OK, render_shell(render_execution_explained_html(execution), 'explained'))
                view = foresight_projection(service.store if isinstance(service.store, PostgresStore) else service.foresight_database_path)
                if view is None: return self._html(HTTPStatus.OK, "<main><h1>FRIDA</h1><p>FORESIGHT RUNTIME NOT VERIFIED</p></main>")
                return self._html(HTTPStatus.OK, render_shell(render_foresight_html(view), 'explained'))
            if path == "/advisory":
                if not self._london_is_active(): return self._foreign_artifact_unavailable()
                advisory = select_advisory(service.store.london_advisories(), query.get("appraisal_id", [None])[0])
                if advisory is None: return self._foreign_artifact_unavailable()
                return self._html(HTTPStatus.OK, render_shell(render_advisory_html(advisory), "action"))
            if path == "/briefings":
                if not self._london_is_active(): return self._foreign_artifact_unavailable()
                # Briefings are executive/end-user communication.  Technical
                # inspection begins only after a user explicitly enters a
                # Judge/Under-the-Hood route.
                return self._html(HTTPStatus.OK, render_shell(render_briefings_html(service.store.strategic_briefs()), "action"))
            if path == "/briefing":
                if not self._london_is_active(): return self._foreign_artifact_unavailable()
                brief_id=query.get("brief_id", [None])[0]
                item=next((x for x in service.store.strategic_briefs() if str(x["brief_id"])==str(brief_id)),None)
                if item is None: return self._foreign_artifact_unavailable()
                return self._html(HTTPStatus.OK, render_shell(render_brief_html(item), "action"))
            if path in {"/", "/action"}:
                view = foresight_projection(service.store if isinstance(service.store, PostgresStore) else service.foresight_database_path)
                active = service.store.active_assignment() or {}
                cases = [] if str(active.get("assignment_id")) == LONDON_ASSIGNMENT_ID else case_index(service.store, view)
                # A technical tour cannot borrow a prior client's historical execution.
                verified = None if self._london_is_active() else current_lead_projection(service.store)
                verified_execution_id = str(verified["execution_id"]) if verified else None
                advisories = service.store.london_advisories() if self._london_is_active() else []
                return self._html(HTTPStatus.OK, render_shell(render_wow_action_html(cases, None, verified_execution_id, advisories), 'action'))
            if path in {"/restricted", "/evidence"}:
                active = service.store.active_assignment() or {}
                if str(active.get("assignment_id")) == LONDON_ASSIGNMENT_ID:
                    return self._html(HTTPStatus.OK, render_shell(render_active_assignment_explained_html(active, service.observation_status(), service.store.london_advisories()), 'action'))
                view = foresight_projection(service.store if isinstance(service.store, PostgresStore) else service.foresight_database_path)
                return self._html(HTTPStatus.OK, render_shell(render_enduser_explanation(view, "restricted" if path=="/restricted" else "evidence"), 'action'))
            if path == "/case":
                if self._london_is_active():
                    return self._foreign_artifact_unavailable()
                view = foresight_projection(service.store if isinstance(service.store, PostgresStore) else service.foresight_database_path)
                case=select_case(service.store, view, query.get("case_id", [""])[0])
                if case is None: return self._json(HTTPStatus.NOT_FOUND, {"error": "governed case not found"})
                origin = query.get("from", ["history"])[0]
                if origin not in {"action", "history"}:
                    origin = "history"
                active = service.store.active_assignment() or {}
                historical = str(active.get("assignment_id")) == LONDON_ASSIGNMENT_ID
                return self._html(HTTPStatus.OK, render_shell(render_case_presentation_html(case, origin, historical), origin))
            if path == "/history":
                active = service.store.active_assignment() or {}
                if str(active.get("assignment_id")) == LONDON_ASSIGNMENT_ID and query.get("scope", ["current"])[0] == "current":
                    return self._html(HTTPStatus.OK, render_shell(render_active_assignment_history_html(active, service.store.recent_observation_cycles()), 'history'))
                if self._london_is_active():
                    return self._foreign_artifact_unavailable()
                view = foresight_projection(service.store if isinstance(service.store, PostgresStore) else service.foresight_database_path)
                return self._html(HTTPStatus.OK, render_shell(render_case_history_html(case_index(service.store, view)), 'history'))
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path.startswith("/api/v1/observation/"):
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"})
                try:
                    length=int(self.headers.get("Content-Length","0")); payload=json.loads(self.rfile.read(length) or b"{}")
                    action=self.path.rsplit("/",1)[-1]
                    if action == "start": result=service.start_observation(payload.get("cadence_seconds", DEFAULT_CADENCE_SECONDS))
                    elif action == "pause": result=service.pause_observation()
                    elif action == "resume": result=service.resume_observation()
                    elif action == "stop": result=service.stop_observation()
                    else: return self._json(HTTPStatus.NOT_FOUND, {"error":"not found"})
                    return self._json(HTTPStatus.OK, result)
                except (TypeError, ValueError, json.JSONDecodeError) as error:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            if self.path == "/api/v1/assignment/activate-london":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"})
                try:
                    return self._json(HTTPStatus.OK, service.activate_london_assignment())
                except (RuntimeError, ValueError) as error:
                    return self._json(HTTPStatus.CONFLICT, {"error": type(error).__name__})
            if self.path == "/api/v1/replay/start":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error":"restricted"})
                try:
                    return self._json(HTTPStatus.ACCEPTED, service.start_accelerated_replay("ACCELERATED_HISTORICAL_REPLAY_OPERATOR_START"))
                except ValueError as error:
                    return self._json(HTTPStatus.CONFLICT, {"error":str(error)})
            if self.path == "/api/v1/replay/start-live-deterministic":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error":"restricted"})
                try:
                    return self._json(HTTPStatus.ACCEPTED, service.start_live_deterministic_replay("ACCELERATED_HISTORICAL_REPLAY_LIVE_PROJECTION"))
                except ValueError as error:
                    return self._json(HTTPStatus.CONFLICT, {"error":str(error)})
            if self.path == "/api/v1/replay/start-london-time-travel":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error":"restricted"})
                try:
                    return self._json(HTTPStatus.ACCEPTED, service.start_london_time_travel("LONDON_TIME_TRAVEL_OPERATOR_START"))
                except (RuntimeError, ValueError) as error:
                    return self._json(HTTPStatus.CONFLICT, {"error":type(error).__name__})
            if self.path == "/api/v1/replay/run":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error":"restricted"})
                try:
                    length=int(self.headers.get("Content-Length","0")); payload=json.loads(self.rfile.read(length) or b"{}")
                    return self._json(HTTPStatus.ACCEPTED, service.run_accelerated_replay(str(payload["replay_id"]), "ACCELERATED_HISTORICAL_REPLAY_OPERATOR_RUNTIME"))
                except RuntimeError as error:
                    return self._json(HTTPStatus.CONFLICT, {"error":str(error)})
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error":str(error)})
            if self.path == "/api/v1/replay/stop":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error":"restricted"})
                try:
                    length=int(self.headers.get("Content-Length","0")); payload=json.loads(self.rfile.read(length) or b"{}")
                    service.stop_deterministic_replay(str(payload["replay_id"]))
                    return self._json(HTTPStatus.OK, {"status":"STOPPED", "retry_count":0})
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error":str(error)})
            if self.path == "/api/v1/briefings/create-historical":
                # Private operator-only batch control; public Judge routes stay read-only.
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error":"restricted"})
                try:
                    length=int(self.headers.get("Content-Length","0")); payload=json.loads(self.rfile.read(length) or b"{}")
                    return self._json(HTTPStatus.CREATED, service.create_historical_strategic_brief(date.fromisoformat(str(payload["cutoff"]))))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error":str(error)})
            if self.path == "/api/v1/probe/smn-queretaro":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error":"restricted"})
                try:
                    return self._json(HTTPStatus.OK, probe_queretaro_forecast())
                except SMNProbeError as error:
                    return self._json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})
            if self.path == "/api/v1/probe/taipei-fabric":
                if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error":"restricted"})
                try:
                    return self._json(HTTPStatus.OK, {"sources": service.probe_taipei_fabric(persist_baseline=True), "model_calls": 0})
                except (OSError, ValueError, json.JSONDecodeError) as error:
                    return self._json(HTTPStatus.BAD_GATEWAY, {"error": type(error).__name__})
            if public_readonly: return self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "cloud judge surface is read-only"})
            if self.path != "/api/v1/observations": return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            if not self._authorized(): return self._json(HTTPStatus.UNAUTHORIZED, {"error": "restricted"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                result = service.ingest(json.loads(self.rfile.read(length)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return self._json(HTTPStatus.ACCEPTED, result)

        def log_message(self, format: str, *args: object) -> None:
            return
    return Handler


def main() -> None:
    token = os.environ.get("FRIDA_STAGING_TOKEN")
    if not token:
        raise SystemExit("FRIDA_STAGING_TOKEN must be configured; staging refuses public startup")
    port = int(os.environ.get("PORT", "8080"))
    database_path = os.environ.get("FRIDA_DATABASE_PATH", "/data/frida.sqlite3")
    database_url = os.environ.get("FRIDA_DATABASE_URL")
    # Cloud Run receives the password independently from Secret Manager; build
    # the private Cloud SQL socket endpoint only in process memory.
    if not database_url and os.environ.get("FRIDA_CLOUDSQL_INSTANCE") and os.environ.get("FRIDA_DATABASE_PASSWORD"):
        password = quote(os.environ["FRIDA_DATABASE_PASSWORD"], safe="")
        socket_path = quote(f"/cloudsql/{os.environ['FRIDA_CLOUDSQL_INSTANCE']}", safe="/")
        database_url = f"postgresql://postgres:{password}@/frida?host={socket_path}"
    if not database_url and os.environ.get("FRIDA_JUDGE_PUBLIC", "").lower() in {"1", "true", "yes"}:
        raise SystemExit("FRIDA_DATABASE_URL or managed Cloud SQL configuration is required for public judge startup")
    public_readonly = os.environ.get("FRIDA_JUDGE_PUBLIC", "").lower() in {"1", "true", "yes"}
    # Controlled, idempotent migration of the existing Cloud SQL schema before
    # any worker can read its durable operational state.  No historical row is
    # rewritten and no external migration host is required.
    if public_readonly and database_url:
        apply_schema(database_url)
        import_london_intelligence(database_url, Path("/app/seed/frida-final-london-appraisal.sqlite3"))
    if public_readonly:
        os.environ.setdefault("FRIDA_APPROVED_EVIDENCE_ROOT", "/app/evidence")
    service = StagingService(database_path, database_url=database_url)
    server = ThreadingHTTPServer(("0.0.0.0", port), build_handler(service, token, public_readonly=public_readonly))
    server.serve_forever()


if __name__ == "__main__":
    main()
