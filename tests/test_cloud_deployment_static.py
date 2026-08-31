"""Static safeguards for the approved Cloud SQL / Cloud Run boundary."""
from pathlib import Path
import unittest

from frida.postgres_migrate import FORESIGHT_EXECUTION, SOURCE_STATE, WP01_EXECUTION, import_london_intelligence


class CloudDeploymentStaticTests(unittest.TestCase):
    def test_tracked_postgres_schema_preserves_governed_artifact_tables(self):
        schema = (Path(__file__).parents[1] / "migrations" / "001_frida_postgres.sql").read_text(encoding="utf-8")
        for table in ("observations", "candidate_signals", "execution_attempts", "execution_events", "foresight_source_states", "foresight_executions", "foresight_execution_events", "observation_cycles", "observation_cycle_events"):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)
        self.assertIn("schema_migrations", schema)

    def test_accelerated_replay_schema_is_append_only_and_separate_from_world_observations(self):
        schema = (Path(__file__).parents[1] / "migrations" / "002_accelerated_historical_replay.sql").read_text(encoding="utf-8")
        for table in ("accelerated_replays", "accelerated_replay_snapshots", "accelerated_replay_events"):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)
        self.assertIn("accelerated_replays_one_active_idx", schema)

    def test_observation_control_schema_is_durable_and_source_independent(self):
        schema = (Path(__file__).parents[1] / "migrations" / "004_autonomous_observation_control.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS observation_control", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS observation_control_events", schema)
        self.assertIn("INSERT INTO observation_control", schema)

    def test_taipei_fabric_is_append_only_and_private_before_any_signal(self):
        schema = (Path(__file__).parents[1] / "migrations" / "006_taipei_observation_fabric.sql").read_text(encoding="utf-8")
        staging = (Path(__file__).parents[1] / "src" / "frida" / "staging.py").read_text(encoding="utf-8")
        self.assertIn("source_fabric_observations", schema)
        self.assertIn("/api/v1/probe/taipei-fabric", staging)
        self.assertIn('"model_calls": 0', staging)

    def test_temporal_pattern_memory_is_append_only_and_not_an_eligibility_engine(self):
        schema = (Path(__file__).parents[1] / "migrations" / "007_temporal_pattern_memory.sql").read_text(encoding="utf-8")
        memory = (Path(__file__).parents[1] / "src" / "frida" / "temporal_pattern_memory.py").read_text(encoding="utf-8")
        self.assertIn("temporal_pattern_assessments", schema)
        self.assertIn("never creates a Signal", memory)
        self.assertIn("CROSS_SOURCE_PATTERN", memory)

    def test_cloud_pattern_persistence_uses_the_execution_owned_connection(self):
        store = (Path(__file__).parents[1] / "src" / "frida" / "postgres_store.py").read_text(encoding="utf-8")
        method = store.split("    def append_temporal_pattern_assessment", 1)[1].split("    def create_operator_access_link", 1)[0]
        self.assertIn("self.connection.cursor()", method)
        self.assertNotIn("self._connect()", method)

    def test_cloud_store_can_persist_governed_observation_cycles(self):
        store = (Path(__file__).parents[1] / "src" / "frida" / "postgres_store.py").read_text(encoding="utf-8")
        for method in ("create_observation_cycle", "append_observation_cycle_event", "complete_observation_cycle"):
            self.assertIn("def " + method, store)

    def test_private_operator_bootstrap_is_short_lived_and_does_not_expose_the_secret(self):
        schema = (Path(__file__).parents[1] / "migrations" / "005_operator_access_links.sql").read_text(encoding="utf-8")
        launcher = (Path(__file__).parents[1] / "scripts" / "open-frida-operator.ps1").read_text(encoding="utf-8")
        staging = (Path(__file__).parents[1] / "src" / "frida" / "staging.py").read_text(encoding="utf-8")
        self.assertIn("operator_access_links", schema)
        self.assertIn("/api/v1/operator/access-link", staging)
        self.assertIn("/private-access", staging)
        self.assertIn("/control", staging)
        self.assertIn("Remove-Variable operatorToken", launcher)
        self.assertNotIn("Bearer frida-staging-token", launcher)

    def test_canonical_import_is_explicit_not_a_development_database_clone(self):
        self.assertTrue(WP01_EXECUTION.startswith("exec-controlled-replay-"))
        self.assertTrue(FORESIGHT_EXECUTION.startswith("foresight-verify-"))
        self.assertEqual(SOURCE_STATE, "foresight-source-state-wr-2201-v1-2026-08-25")

    def test_cloud_build_keeps_local_data_and_credentials_out_of_upload(self):
        ignored = (Path(__file__).parents[1] / ".gcloudignore").read_text(encoding="utf-8")
        for entry in (".gcloud-gate4b/", "data/*.sqlite3", "data/checkpoints/"):
            self.assertIn(entry, ignored)
        self.assertIn("!data/frida-final-london-appraisal.sqlite3", ignored)

    def test_procfile_uses_the_governed_staging_surface(self):
        procfile = (Path(__file__).parents[1] / "Procfile").read_text(encoding="utf-8")
        self.assertEqual(procfile.strip(), "web: python -m frida.staging")

    def test_cloud_image_includes_the_canonical_frida_identity_asset(self):
        dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")
        package_config = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("COPY src ./src", dockerfile)
        self.assertIn('frida = ["assets/*.png", "assets/*.jpg", "assets/*.svg"]', package_config)
        self.assertTrue((Path(__file__).parents[1] / "src" / "frida" / "assets" / "Frida-logo.png").is_file())
        self.assertTrue((Path(__file__).parents[1] / "src" / "frida" / "assets" / "taipei-city-government-logo.jpg").is_file())
        self.assertTrue((Path(__file__).parents[1] / "src" / "frida" / "assets" / "london-city-coat-of-arms.svg").is_file())

    def test_cloud_image_includes_tracked_schema_migrations(self):
        dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")
        dockerignore = (Path(__file__).parents[1] / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("COPY migrations ./migrations", dockerfile)
        self.assertIn("COPY data/frida-final-london-appraisal.sqlite3 /app/seed/frida-final-london-appraisal.sqlite3", dockerfile)
        self.assertIn("!data/frida-final-london-appraisal.sqlite3", dockerignore)

    def test_london_intelligence_seed_is_explicit_and_idempotent(self):
        staging = (Path(__file__).parents[1] / "src" / "frida" / "staging.py").read_text(encoding="utf-8")
        self.assertTrue(callable(import_london_intelligence))
        self.assertIn("import_london_intelligence(database_url", staging)
        self.assertIn("/app/seed/frida-final-london-appraisal.sqlite3", staging)

    def test_cloud_image_installs_the_approved_native_google_runtime(self):
        dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn('pip install --no-cache-dir ".[google-runtime]"', dockerfile)

    def test_cloud_run_uses_a_secret_component_not_a_committed_database_url(self):
        staging = (Path(__file__).parents[1] / "src" / "frida" / "staging.py").read_text(encoding="utf-8")
        self.assertIn("FRIDA_CLOUDSQL_INSTANCE", staging)
        self.assertIn("FRIDA_DATABASE_PASSWORD", staging)
        self.assertIn("/cloudsql/", staging)

    def test_public_judge_paths_remain_read_only_and_include_glass_hood(self):
        staging = (Path(__file__).parents[1] / "src" / "frida" / "staging.py").read_text(encoding="utf-8")
        self.assertIn('"/glass-hood"', staging)
        self.assertIn('"/technical-record"', staging)
        self.assertIn('"/glass-hood", "/technical-record"', staging)
        self.assertIn('"/api/v1/live-engine/current"', staging)
        self.assertIn('"cloud judge surface is read-only"', staging)
        self.assertIn('"/api/v1/replay/status"', staging)
        self.assertIn('self.path == "/api/v1/replay/start"', staging)
        self.assertIn('FRIDA_REPLAY_RUNTIME_ENABLED', staging)
        self.assertIn('self.path == "/api/v1/replay/run"', staging)
        self.assertIn('self.path == "/api/v1/replay/stop"', staging)
        self.assertIn('self.path == "/api/v1/replay/start-live-deterministic"', staging)
        self.assertIn('"/api/v1/observation/status"', staging)
        self.assertIn('"/api/v1/observation/recent"', staging)
        self.assertIn('"/assets/taipei-city-government-logo.jpg"', staging)
        self.assertIn('"/assets/london-city-coat-of-arms.svg"', staging)
        self.assertIn('self.path.startswith("/api/v1/observation/")', staging)
        self.assertIn('render_operator_html', staging)
        self.assertIn('apply_schema(database_url)', staging)
        self.assertIn('"/api/v1/probe/london-tfl"', staging)


if __name__ == "__main__":
    unittest.main()
