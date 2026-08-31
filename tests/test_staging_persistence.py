from datetime import datetime, timezone
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from frida.staging import StagingService, build_handler
from frida.demo_view import render_foresight_html, render_action_html, render_enduser_explanation, render_history_html, render_shell, render_wow_action_html, render_active_assignment_explained_html, render_active_assignment_history_html, render_active_observation_hood_html, render_case_presentation_html
from frida.live_observation import LiveObservationCycle
from frida.observation_boundary import ObservationTrigger
from frida.advisory_projection import render_advisory_html, render_advisory_raw_html
from frida.briefing_projection import render_briefings_html, render_brief_html


def payload(source_id: str = "DENUE", content_hash: str = "a" * 64) -> dict[str, object]:
    now = datetime(2026, 8, 23, tzinfo=timezone.utc).isoformat()
    return {"source_id": source_id, "source_reference": "official-edition", "source_date": now,
            "content_hash": content_hash, "evidence_class": "REAL", "replay_sequence": 1, "observed_at": now}


class StagingPersistenceTests(unittest.TestCase):
    def test_briefing_pages_use_the_shared_shell_and_visible_return_paths(self):
        item = {
            "brief_id": "brief-1", "created_at": "2026-08-30T00:00:00Z",
            "brief": {"executive_posture": "YELLOW", "executive_summary": "A strategic question.", "semantic_status": "ADVISORY", "why_it_may_matter": "It may matter.", "what_frida_will_watch_next": [], "remaining_uncertainty": [], "evidence_scope_disclosure": "Scoped evidence."},
            "foresight": {"trajectory": "Bounded.", "leading_indicators": []},
            "evidence_ids": [],
        }
        listing = render_shell(render_briefings_html([item]), "action")
        detail = render_shell(render_brief_html(item), "action")
        self.assertIn("frida-shell-wrap", listing)
        self.assertIn("← BACK TO FRIDA", listing)
        self.assertIn("/assets/frida-flower-icon.png", listing)
        self.assertIn("Current authorized evidence window", listing)
        self.assertIn("posture-yellow", listing)
        self.assertIn("⚑</span>YELLOW", listing)
        self.assertIn("<span class='frida-tab active'>FRIDA IN ACTION", listing)
        self.assertIn("href='/foresight'>FRIDA EXPLAINED", listing)
        self.assertIn("frida-shell-wrap", detail)
        self.assertIn("← BRIEFING HISTORY", detail)
        self.assertIn("posture-yellow", detail)
        self.assertIn("<span class='frida-tab active'>FRIDA IN ACTION", detail)
        self.assertLess(listing.index("frida-shell-wrap"), listing.index("<main>"))

    def test_raw_advisory_record_preserves_plain_evidence_with_shared_shell(self):
        advisory = {"record_id": "appraisal-1", "created_at": "2026-08-30T00:00:00Z", "kind": "FIRST_APPRAISAL", "result": {"strategic_interest": "POSSIBLE"}, "bundle": {"evidence": []}}
        page = render_shell(render_advisory_raw_html(advisory), "explained")
        self.assertIn("frida-shell-wrap", page)
        self.assertIn("← BACK TO FRIDA", page)
        self.assertIn("BACK TO ADVISORY", page)
        self.assertIn('&quot;record_id&quot;: &quot;appraisal-1&quot;', page)

    def test_restart_preserves_signal_and_blocks_duplicate_without_creating_candidate(self):
        with TemporaryDirectory() as directory:
            database = str(Path(directory) / "frida.sqlite3")
            first = StagingService(database)
            created = first.ingest(payload())
            first.store.close()
            second = StagingService(database)
            duplicate = second.ingest(payload())
            self.assertEqual(created["attention_state"], "ATTENTION_PENDING")
            self.assertEqual(created["candidate_signal"], None)
            self.assertEqual(duplicate["attention_state"], "NOT_CREATED_DUPLICATE")
            self.assertEqual(second.store.status()["candidate_signals"], 0)
            self.assertGreaterEqual(second.store.status()["audit_events"], 4)
            second.store.close()

    def test_unknown_source_fails_closed(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))
            with self.assertRaisesRegex(ValueError, "approved staging observer"):
                service.ingest(payload("UNAPPROVED"))
            service.store.close()

    def test_golden_path_view_is_durable_and_read_only_retrievable(self):
        with TemporaryDirectory() as directory:
            store = StagingService(str(Path(directory) / "frida.sqlite3")).store
            view = {"run_id": "run-1", "state": "COMPLETED", "audit": [{"at": "2026-08-23T00:00:00+00:00", "stage": "observation.accepted", "detail": "official"}], "disposition": "EVIDENCE_INSUFFICIENT"}
            store.save_golden_path_view(view)
            self.assertEqual(store.latest_golden_path_view()["disposition"], "EVIDENCE_INSUFFICIENT")
            store.close()

    def test_health_is_public_but_staging_status_requires_token(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(service, "test-token"))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            endpoint = f"http://127.0.0.1:{server.server_port}"
            try:
                self.assertEqual(urlopen(endpoint + "/healthz").status, 200)
                with self.assertRaises(HTTPError) as blocked:
                    urlopen(endpoint + "/api/v1/staging/status")
                self.assertEqual(blocked.exception.code, 401)
                blocked.exception.close()
                request = Request(endpoint + "/api/v1/staging/status", headers={"Authorization": "Bearer test-token"})
                self.assertEqual(urlopen(request).status, 200)
            finally:
                server.shutdown()
                server.server_close()
                service.store.close()

    def test_briefing_metadata_is_operator_only(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))
            service.store.append_strategic_brief("brief-audit", "LONDON_FINAL_ACTIVE", "HISTORICAL_TIME_TRAVEL_BRIEF", "VALIDATED", ["e1"], {}, {}, {"retries": 0}, "2018-10-25")
            server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(service, "test-token", public_readonly=True))
            thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            endpoint = f"http://127.0.0.1:{server.server_port}/api/v1/briefings/metadata?brief_id=brief-audit"
            try:
                with self.assertRaises(HTTPError) as blocked:
                    urlopen(endpoint)
                self.assertEqual(blocked.exception.code, 401); blocked.exception.close()
                request = Request(endpoint, headers={"Authorization": "Bearer test-token"})
                payload = json.loads(urlopen(request).read())
                self.assertEqual(payload["brief_id"], "brief-audit")
                self.assertEqual(payload["historical_as_of"], "2018-10-25")
                self.assertEqual(payload["runtime_meta"]["retries"], 0)
            finally:
                server.shutdown(); server.server_close(); service.store.close()

    def test_smn_probe_is_private_and_cannot_create_public_activity(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(service, "test-token", public_readonly=True))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = Request(f"http://127.0.0.1:{server.server_port}/api/v1/probe/smn-queretaro", method="POST")
                with self.assertRaises(HTTPError) as blocked:
                    urlopen(request)
                self.assertEqual(blocked.exception.code, 401)
                blocked.exception.close()
                self.assertEqual(service.store.status()["candidate_signals"], 0)
            finally:
                server.shutdown()
                server.server_close()
                service.store.close()

    def test_foresight_view_explains_governance_without_internal_reasoning(self):
        view={"execution_id":"f","scenario":{},"assessment":{"decision_relevant_differences":["b","s","m"],"limitations":["no numbers"],"evidence_ids":["FW-OBS-001"],"assumption_ids":["ASM-1"]},"challenge":{"reason":"stress needs bounds","required_effect":"define bounds"},"governance":{"qualifications":["q"]}}
        page=render_foresight_html(view)
        for required in ("OBSERVED","ASSUMED","PROJECTED","MATERIAL","RESTRICTED","−65.556761"):
            self.assertIn(required,page)
        self.assertNotIn("chain-of-thought",page)

    def test_action_view_and_judge_view_share_same_governed_projection(self):
        view={"execution_id":"f","scenario":{},"assessment":{"decision_relevant_differences":["b","s","m"],"limitations":["no numbers"],"evidence_ids":["FW-OBS-001"],"assumption_ids":["ASM-1"]},"challenge":{"reason":"stress needs bounds","required_effect":"define bounds"},"governance":{"qualifications":["q"]},"selected":{"value":"12","unit":"units","measure":"selected opportunity","geography":"Test city","as_of":"2026","limitation":"bounded source fact"}}
        action,judge=render_action_html(view),render_foresight_html(view)
        self.assertIn("FRIDA in Action",action); self.assertIn("FRIDA Explained",judge)
        self.assertIn("MATERIAL",judge); self.assertIn("stress needs bounds",action)
        self.assertIn("WATCH FRIDA WORK — LIVE", action)
        self.assertIn("selected opportunity", action); self.assertIn("Test city", judge)

    def test_application_shell_has_stable_accessible_navigation(self):
        page = render_shell("<main><nav>legacy navigation</nav><p>content</p></main>", "action")
        self.assertIn("rel='icon' type='image/png' href='/assets/frida-flower-icon.png'", page)
        self.assertIn("property='og:site_name' content='FRIDA'", page)
        self.assertIn("property='og:image' content='https://frida-zz37olzlja-pv.a.run.app/assets/frida-flower-icon.png'", page)
        self.assertIn("/assets/frida-logo.png", page)
        self.assertIn("href='/' aria-label='Back to FRIDA in Action'", page)
        self.assertIn("<span class='frida-tab active'>FRIDA IN ACTION", page)
        self.assertIn(".frida-tab.active small{color:#e5f0ef}", page)
        self.assertIn("href='/foresight'", page)
        self.assertIn("href='/history'", page)
        self.assertIn(".frida-shell-wrap{width:100%", page)
        self.assertIn("id='frida-heartbeat'", page)
        self.assertIn("frida-idle-tick 5s", page)
        self.assertIn("padding:10px 24px 0 80px", page)
        self.assertIn("STRATEGIC URBAN INTELLIGENCE", page)
        self.assertIn(".frida-heartbeat-row ~ main > .eyebrow{margin:0 0 16px}", page)
        self.assertIn("Click any row for details", page)
        self.assertIn(".activity-row::after", page)
        self.assertIn("/api/v1/assignment/active", page)
        self.assertIn("FRIDA is observing ", page)
        self.assertIn("FRIDA · London build 0.9.0", page)
        self.assertIn("identity_asset_url", page)
        self.assertIn("City of London coat of arms", page)
        self.assertIn("href='/briefings'", page)
        self.assertIn("Latest strategic brief", page)
        self.assertIn("/api/v1/observation/recent", page)
        self.assertLess(page.index("frida-shell-wrap"), page.index("<main>"))

    def test_application_shell_injects_a_favicon_when_a_projection_has_no_head(self):
        page = render_shell("<!doctype html><html lang='en'><meta charset='utf-8'><title>FRIDA in Action</title><main>content</main></html>", "action")
        self.assertIn("<html lang='en'><head><link rel='icon' type='image/png' href='/assets/frida-flower-icon.png'>", page)
        self.assertLess(page.index('<title>FRIDA in Action</title>'), page.index('</head>'))
        self.assertLess(page.index('</head>'), page.index('<main>'))

    def test_application_shell_injects_social_preview_metadata_once(self):
        source = "<!doctype html><html><head><title>FRIDA</title></head><main>content</main></html>"
        page = render_shell(source, "action")
        self.assertEqual(page.count("property='og:site_name'"), 1)
        self.assertIn("FRIDA — Strategic Urban Intelligence", page)

    def test_public_favicon_fallback_is_available(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(service, "test-token", public_readonly=True))
            thread = Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                response = urlopen(f"http://127.0.0.1:{server.server_port}/favicon.ico")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "image/png")
                self.assertGreater(len(response.read()), 0)
            finally:
                server.shutdown(); server.server_close(); service.store.close()

    def test_wow_action_refreshes_activity_without_reloading_the_application_shell(self):
        page = render_wow_action_html([], {"status": "RUNNING", "replay_id": "replay-1", "events": []}, "execution-verified")
        self.assertIn("FRIDA’s attention", page)
        self.assertIn("Current official observation activity.", page)
        self.assertIn("id='observation-pulse'", page)
        self.assertIn("frida-heartbeat", render_shell(page, "action"))
        self.assertNotIn("location.reload()", page)
        shell = render_shell(page, "action")
        self.assertIn("dot.classList.add('active','pulse')", shell)
        self.assertIn("id='live-observation-ticker'", shell)
        self.assertIn("heading.after(tools)", shell)
        self.assertNotIn("<section id='live-observation-ticker'", shell)
        self.assertIn("events.slice(count)", shell)
        self.assertIn("Return to latest activity", shell)
        self.assertIn("activity-arrived", shell)
        self.assertIn("box.prepend(row)", shell)
        self.assertIn("box.scrollTop=0", shell)
        self.assertIn("city-heartbeat", shell)
        self.assertIn("activity-live-tools", shell)
        self.assertIn("No candidate qualified for semantic dispatch.", shell)
        self.assertIn("New autonomous observation cycle started.", shell)
        self.assertIn("Deterministic pattern memory updated", shell)
        self.assertIn("row.href='/glass-hood'", shell)
        self.assertIn("document.getElementById('replay-events')", shell)
        self.assertIn("sequence.append(row)", shell)
        self.assertIn("OBSERVATION PULSE", shell)
        self.assertIn("FRIDA CONTINUES WATCHING", shell)
        self.assertIn("TfL Victoria line", shell)
        self.assertIn("ticker-track", shell)
        self.assertIn("Routine source activity is filtered", shell)
        self.assertNotIn("source-activity-row", shell)
        self.assertIn("FRIDA · STRATEGIC URBAN INTELLIGENCE", page)
        self.assertIn("GREEN FLAG", page)
        self.assertIn("Inspect how FRIDA worked", page)
        self.assertNotIn("JUDGE REVIEW", page)
        self.assertIn("/foresight?execution_id=execution-verified", page)
        self.assertNotIn("historical archive", page.lower())

    def test_london_advisory_tour_preserves_its_non_case_semantics(self):
        advisory = {"record_id": "appraisal-london-1", "created_at": datetime(2026, 8, 30, tzinfo=timezone.utc),
                    "kind": "FIRST_APPRAISAL", "bundle": {"evidence_ids": ["MPS-LAMBETH-202607"]},
                    "result": {"strategic_interest": "POSSIBLE", "opportunity_family": "INTERVENTION_OPPORTUNITY",
                               "strategic_question": "What local context would clarify the opportunity?",
                               "why_it_might_matter": "Aggregate context merits bounded attention.",
                               "evidence_ids_used": ["MPS-LAMBETH-202607"],
                               "missing_evidence": ["Ward-level aggregate context"],
                               "uncertainties": ["No causal claim"],
                               "allowed_context_requests": ["LONDON_PLANNING_SW8"], "research_warranted": True}}
        page = render_advisory_html(advisory)
        raw = render_advisory_raw_html(advisory)
        self.assertIn("YELLOW FLAG · ADVISORY HYPOTHESIS", page)
        self.assertIn("not canonical FRIDA Attention, Signal, Candidate or Case", page)
        self.assertIn("VIEW RAW GOVERNED APPRAISAL RECORD", page)
        self.assertIn("MPS-LAMBETH-202607", raw)
        self.assertNotIn("chain-of-thought", raw)

    def test_current_assignment_views_do_not_fall_back_to_archived_case_copy(self):
        assignment={"assignment_id":"LONDON_FINAL_ACTIVE","city_name":"London","country_name":"United Kingdom"}
        control={"state":"RUNNING","source_health":"HEALTHY"}
        cycle={"cycle_id":"cycle-london","started_at":"2026-08-30T00:00:00+00:00","status":"COMPLETED_NO_DISPATCH","source_count":3,"events":[{"event_type":"observe.source_examined","occurred_at":"2026-08-30T00:00:00+00:00","message":"Official source examined."}]}
        explained=render_active_assignment_explained_html(assignment,control)
        history=render_active_assignment_history_html(assignment,[cycle])
        hood=render_active_observation_hood_html(assignment,[cycle])
        for page in (explained,history,hood):
            self.assertIn("LONDON, UNITED KINGDOM", page.upper())
            self.assertNotIn("Querétaro", page)
            self.assertNotIn("DENUE", page)
            self.assertNotIn("WP01", page)
        self.assertIn("HEALTHY", explained)
        self.assertIn("2026-08-30T00:00:00+00:00", history)
        self.assertIn("OBSERVE", hood)
        self.assertNotIn(".active-assignment a{", explained)
        self.assertIn(".active-assignment .assignment-action", explained)
        self.assertIn("<main class='active-assignment'>", explained)
        self.assertNotIn("/history?scope=archive", explained)
        self.assertIn(".active-history a{", history)
        self.assertNotIn("VIEW VERIFIED HISTORICAL ARCHIVE", history)
        self.assertNotIn("/history?scope=archive", history)
        self.assertIn(".active-hood .back-to-frida", hood)
        self.assertLess(render_shell(explained, "explained").index("frida-shell-wrap"), render_shell(explained, "explained").index("<main class='active-assignment'>"))

    def test_historical_case_keeps_the_full_judge_path_discoverable(self):
        case = {
            "label": "CONTROLLED REPLAY",
            "title": "Verified historical case",
            "source": "Historical real observation",
            "case_id": "case-historical",
            "execution_id": "execution-historical",
            "attention": "INVESTIGATE",
            "question": "What does the governed evidence support?",
            "disposition": "EVIDENCE_INSUFFICIENT",
            "challenger": "ADVISORY",
            "interpretation": "RESTRICTED",
            "glass_hood_url": "/glass-hood?execution_id=execution-historical",
        }
        page = render_case_presentation_html(case, "history", historical=True)
        self.assertIn("Inspect how FRIDA worked", page)
        self.assertIn("/foresight?execution_id=execution-historical", page)
        self.assertIn("href='/history?scope=archive'", page)

    def test_london_routes_default_to_active_assignment_not_archived_projection(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))
            service.activate_london_assignment()
            server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(service, "test-token", public_readonly=True))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            endpoint = f"http://127.0.0.1:{server.server_port}"
            try:
                for path in ("/", "/foresight", "/history", "/glass-hood", "/restricted", "/evidence"):
                    with urlopen(endpoint + path) as response:
                        page = response.read().decode("utf-8")
                    self.assertEqual(response.status, 200)
                    self.assertNotIn("Valle de Querétaro", page)
                    self.assertNotIn("DENUE", page)
                    self.assertNotIn("WP01", page)
                with urlopen(endpoint + "/foresight") as response:
                    self.assertIn("London", response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                service.store.close()

    def test_london_public_routes_fail_closed_for_prior_client_artifacts(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))
            service.activate_london_assignment()
            server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(service, "test-token", public_readonly=True))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            endpoint = f"http://127.0.0.1:{server.server_port}"
            try:
                for path in (
                    "/case?case_id=case-historical-wp01",
                    "/foresight?execution_id=exec-controlled-replay-93a6c7ecb69741c69c18b4bea8c2c1d2",
                    "/glass-hood?execution_id=exec-controlled-replay-93a6c7ecb69741c69c18b4bea8c2c1d2",
                    "/technical-record?execution_id=exec-controlled-replay-93a6c7ecb69741c69c18b4bea8c2c1d2",
                    "/history?scope=archive",
                ):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(endpoint + path)
                    self.assertEqual(error.exception.code, 404)
                    self.assertIn("not available for the London assignment", error.exception.read().decode("utf-8"))
                    error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                service.store.close()

    def test_executive_flags_rank_red_then_yellow_then_green_without_creating_cases(self):
        green = {"case_id": "green", "title": "Green", "source": "official", "attention": "IGNORE"}
        yellow = {"case_id": "yellow", "title": "Yellow", "source": "official", "attention": "WATCH"}
        red = {"case_id": "red", "title": "Red", "source": "official", "attention": "INVESTIGATE"}
        page = render_wow_action_html([green, yellow, red], None)
        self.assertLess(page.index("Red</h1>"), page.index("FRIDA’s attention"))
        self.assertIn("RED FLAG", page)
        self.assertIn("YELLOW FLAG", page)
        self.assertIn("GREEN FLAG", page)
        no_case = render_wow_action_html([], None)
        self.assertIn("GREEN FLAG", no_case)
        self.assertIn("a routine observation is not a Case", no_case)

    def test_supporting_views_are_polished_and_keep_governed_content(self):
        view={"challenge":{"reason":"stress needs bounds"}}
        restricted=render_enduser_explanation(view, "restricted")
        evidence=render_enduser_explanation(view, "evidence")
        history=render_history_html()
        self.assertIn("stress needs bounds", restricted)
        self.assertIn("Open FRIDA Explained", restricted)
        self.assertIn("observed evidence, explicit assumptions", evidence)
        self.assertIn("One persisted governed case is available", history)
        self.assertIn("No observations are fabricated", history)

    def test_live_cycle_records_unchanged_source_without_model_dispatch(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))
            service.ingest(payload())
            outcome = LiveObservationCycle(service).run_once()
            cycles = service.store.recent_observation_cycles()
            self.assertEqual(outcome["candidate_count"], 0)
            self.assertEqual(outcome["semantic_call_count"], 0)
            self.assertEqual(cycles[0]["status"], "COMPLETED_NO_DISPATCH")
            self.assertIn("triage.no_candidate", [event["event_type"] for event in cycles[0]["events"]])
            service.store.close()

    def test_source_fabric_pattern_is_persisted_and_does_not_authorize_dispatch(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))

            class Snapshot:
                def persisted(self):
                    return {
                        "source_id": "TAIPEI_TEST_RAIN",
                        "retrieved_at": "2026-08-29T12:00:00+00:00",
                        "source_timestamp": "2026-08-29T11:55:00+00:00",
                        "source_url": "https://official.example.test/rain",
                        "fingerprint_sha256": "a" * 64,
                        "authority": "Official Taipei test source",
                        "geography": "Taipei City",
                        "adapter_version": "test-v1",
                        "normalization_version": "test-v1",
                        "canonical_state": {"status": "ordinary"},
                    }

            outcome = LiveObservationCycle(service, lambda: (Snapshot(),)).run_once()
            events = service.store.recent_observation_cycles(1)[0]["events"]
            self.assertEqual(outcome["semantic_call_count"], 0)
            self.assertIn("pattern.assessed", [event["event_type"] for event in events])
            pattern = next(event for event in events if event["event_type"] == "pattern.assessed")
            self.assertFalse(pattern["payload"]["authorizes_signal"])
            self.assertTrue(pattern["payload"]["pattern_assessment_id"].startswith("pattern-"))
            service.store.close()

    def test_future_scheduler_boundary_only_supplies_snapshots_to_the_existing_deterministic_cycle(self):
        with TemporaryDirectory() as directory:
            service = StagingService(str(Path(directory) / "frida.sqlite3"))

            class ApprovedProvider:
                def snapshots(self):
                    return (service.store.retained_snapshots())

            trigger = ObservationTrigger(
                lambda provider: LiveObservationCycle(service, provider), ApprovedProvider()
            )
            outcome = trigger.run_once()
            cycle = service.store.recent_observation_cycles(1)[0]
            self.assertEqual(outcome["semantic_call_count"], 0)
            self.assertEqual(cycle["events"][0]["event_type"], "cycle.started")
            self.assertEqual(cycle["events"][-1]["event_type"], "cycle.completed")
            service.store.close()
