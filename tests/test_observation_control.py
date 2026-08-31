from __future__ import annotations

from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from time import sleep
import json
import unittest
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from frida.observation_control import AutonomousObservationController, validate_cadence
from frida.staging import StagingService, build_handler


class EmptyAuthorizedProvider:
    def snapshots(self):
        return ()


class FailingAuthorizedProvider:
    def snapshots(self):
        raise OSError("source unavailable")


class ObservationControlTests(unittest.TestCase):
    def service(self, directory: str, provider=None) -> StagingService:
        return StagingService(str(Path(directory) / "frida.sqlite3"), source_provider=provider)

    def wait_for_cycle(self, service: StagingService) -> None:
        for _ in range(80):
            cycles=service.store.recent_observation_cycles(1)
            if cycles and cycles[0]["status"] != "RUNNING": return
            sleep(.05)
        self.fail("scheduler did not execute a claimed observation cycle")

    def test_start_runs_a_source_independent_deterministic_cycle_without_semantic_dispatch(self):
        with TemporaryDirectory() as directory:
            service=self.service(directory, EmptyAuthorizedProvider())
            try:
                current=service.start_observation(60)
                self.assertEqual(current["state"], "RUNNING")
                self.wait_for_cycle(service)
                cycle=service.store.recent_observation_cycles(1)[0]
                self.assertEqual(cycle["semantic_call_count"], 0)
                self.assertEqual(cycle["status"], "COMPLETED_NO_DISPATCH")
                for _ in range(40):
                    status=service.observation_status()
                    if status["source_health"] == "HEALTHY": break
                    sleep(.025)
                self.assertEqual(status["source_health"], "HEALTHY")
                self.assertFalse(status["cycle_active"])
            finally: service.close()

    def test_pause_resume_stop_and_cadence_are_persisted_and_bounded(self):
        with TemporaryDirectory() as directory:
            service=self.service(directory)
            try:
                status=service.start_observation(60)
                self.assertEqual(status["source_health"], "NO_AUTHORIZED_SOURCE_CONFIGURED")
                self.assertEqual(service.pause_observation()["state"], "PAUSED")
                self.assertEqual(service.resume_observation()["state"], "RUNNING")
                self.assertEqual(service.stop_observation()["state"], "STOPPED")
                with self.assertRaises(ValueError): service.start_observation(59)
                with self.assertRaises(ValueError): validate_cadence(True)
                self.assertEqual(service.store.recent_observation_cycles(), [])
            finally: service.close()

    def test_source_failure_pauses_without_retry_or_semantic_dispatch(self):
        with TemporaryDirectory() as directory:
            service=self.service(directory, FailingAuthorizedProvider())
            try:
                service.start_observation(60)
                for _ in range(80):
                    status=service.observation_status()
                    if status["state"] == "PAUSED": break
                    sleep(.05)
                self.assertEqual(status["state"], "PAUSED")
                self.assertEqual(status["source_health"], "ERROR")
                self.assertEqual(status["last_error_class"], "OSError")
                self.assertEqual(service.store.recent_observation_cycles(), [])
            finally: service.close()

    def test_only_one_controller_claims_one_due_cycle(self):
        with TemporaryDirectory() as directory:
            service=self.service(directory)
            second=AutonomousObservationController(service.store, lambda provider: __import__('frida.live_observation', fromlist=['LiveObservationCycle']).LiveObservationCycle(service, provider), EmptyAuthorizedProvider(), poll_seconds=.005)
            service.observation_control.close()
            service.observation_control=AutonomousObservationController(service.store, lambda provider: __import__('frida.live_observation', fromlist=['LiveObservationCycle']).LiveObservationCycle(service, provider), EmptyAuthorizedProvider(), poll_seconds=.005)
            service.observation_control.start_worker(); second.start_worker()
            try:
                service.start_observation(60); self.wait_for_cycle(service); sleep(.08)
                self.assertEqual(len(service.store.recent_observation_cycles()), 1)
            finally:
                second.close(); service.close()

    def test_private_operator_can_mutate_with_session_but_public_cannot(self):
        with TemporaryDirectory() as directory:
            service=self.service(directory)
            server=ThreadingHTTPServer(("127.0.0.1",0),build_handler(service,"test-token",public_readonly=True)); thread=Thread(target=server.serve_forever,daemon=True); thread.start()
            endpoint=f"http://127.0.0.1:{server.server_port}"
            try:
                with self.assertRaises(HTTPError) as blocked: urlopen(Request(endpoint+"/api/v1/observation/start",method="POST",data=b"{}",headers={"Content-Type":"application/json"}))
                self.assertEqual(blocked.exception.code,401); blocked.exception.close()
                operator=urlopen(Request(endpoint+"/operator",headers={"Authorization":"Bearer test-token"}))
                cookie=operator.headers["Set-Cookie"]; page=operator.read().decode(); operator.close()
                self.assertIn("Observation control",page); self.assertNotIn("test-token",page)
                request=Request(endpoint+"/api/v1/observation/start",method="POST",data=json.dumps({"cadence_seconds":60}).encode(),headers={"Content-Type":"application/json","Cookie":cookie})
                self.assertEqual(urlopen(request).status,200)
                public=json.loads(urlopen(endpoint+"/api/v1/observation/status").read())
                self.assertEqual(public["state"],"RUNNING")
            finally:
                server.shutdown();server.server_close();service.close()

    def test_private_access_link_is_single_use_and_bootstraps_control_session(self):
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, message, headers, newurl):
                return None
        with TemporaryDirectory() as directory:
            service=self.service(directory)
            server=ThreadingHTTPServer(("127.0.0.1",0),build_handler(service,"test-token",public_readonly=True)); thread=Thread(target=server.serve_forever,daemon=True); thread.start()
            endpoint=f"http://127.0.0.1:{server.server_port}"
            try:
                with self.assertRaises(HTTPError) as public:
                    urlopen(endpoint+"/api/v1/operator/access-link")
                self.assertEqual(public.exception.code,401); public.exception.close()
                access=json.loads(urlopen(Request(endpoint+"/api/v1/operator/access-link",headers={"Authorization":"Bearer test-token"})).read())
                self.assertEqual(access["expires_in_seconds"],120)
                self.assertTrue(access["access_path"].startswith("/private-access?code="))
                opener=build_opener(NoRedirect())
                with self.assertRaises(HTTPError) as redirect:
                    opener.open(endpoint+access["access_path"])
                self.assertEqual(redirect.exception.code,303)
                cookie=redirect.exception.headers["Set-Cookie"]
                self.assertEqual(redirect.exception.headers["Location"],"/control")
                redirect.exception.close()
                page=urlopen(Request(endpoint+"/control",headers={"Cookie":cookie})).read().decode()
                self.assertIn("Observation control",page)
                with self.assertRaises(HTTPError) as reused:
                    opener.open(endpoint+access["access_path"])
                self.assertEqual(reused.exception.code,401); reused.exception.close()
            finally:
                server.shutdown();server.server_close();service.close()
