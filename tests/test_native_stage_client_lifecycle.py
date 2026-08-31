import os
import unittest
from unittest.mock import patch

from frida.native_stage_runtime import NativeStageError, NativeStages


class _Usage:
    def model_dump(self, **_kwargs):
        return {}


class _Candidate:
    finish_reason = "STOP"


class _Response:
    candidates = [_Candidate()]
    usage_metadata = _Usage()
    parsed = {"ok": True}


class _Models:
    def __init__(self, client):
        self.client = client

    def generate_content(self, **_kwargs):
        if self.client.closed:
            raise AssertionError("request used a closed client")
        self.client.calls += 1
        return _Response()


class _Client:
    def __init__(self):
        self.closed = False
        self.calls = 0
        self.close_calls = 0
        self.models = _Models(self)

    def close(self):
        self.closed = True
        self.close_calls += 1


class NativeClientLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
            "GOOGLE_CLOUD_LOCATION": "global",
            "GOOGLE_CLOUD_PROJECT": "project-b241d3e1-4c3d-4801-9c6",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_client_is_reused_open_for_three_stages_then_closed_once(self):
        client = _Client()
        stages = NativeStages(client=client)
        for stage in ("Semantic Triage", "Investigation", "Independent Challenger"):
            value, _meta = stages._invoke(stage, object, "p", {},
                                          lambda _parsed, _allowed: stage, set())
            self.assertEqual(value, stage)
        self.assertFalse(client.closed)
        self.assertEqual(client.calls, 3)
        stages.close()
        stages.close()
        self.assertTrue(client.closed)
        self.assertEqual(client.close_calls, 1)

    def test_closed_execution_cannot_issue_another_stage_call(self):
        client = _Client()
        stages = NativeStages(client=client)
        stages.close()
        with self.assertRaises(NativeStageError) as error:
            stages._get_client()
        self.assertEqual(error.exception.code, "CLIENT_LIFECYCLE_CLOSED")
        self.assertEqual(client.calls, 0)

    def test_factory_creates_one_client_for_multiple_stage_lookups(self):
        clients = []
        def factory():
            client = _Client()
            clients.append(client)
            return client
        stages = NativeStages(client_factory=factory)
        self.assertIs(stages._get_client(), stages._get_client())
        self.assertEqual(len(clients), 1)
        stages.close()
        self.assertTrue(clients[0].closed)
