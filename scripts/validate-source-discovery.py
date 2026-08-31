"""Model-free validation of bounded London Source Registry promotion."""
from __future__ import annotations
import json
import tempfile
from pathlib import Path
from frida.persistence import StagingStore
from frida.source_discovery import SourceDiscoveryService

with tempfile.TemporaryDirectory(prefix="frida-source-discovery-") as directory:
    store=StagingStore(Path(directory) / "registry.sqlite3")
    try:
        store.activate_london_assignment()
        first=SourceDiscoveryService(store).discover("LONDON_FINAL_ACTIVE", "planning flood resilience")
        repeated=SourceDiscoveryService(store).discover("LONDON_FINAL_ACTIVE", "planning flood resilience")
        print(json.dumps({"first":first,"repeated":repeated,"registry_entries":store.connection.execute("SELECT COUNT(*) FROM source_registry_entries").fetchone()[0],"events":store.connection.execute("SELECT lifecycle_state,reason FROM source_registry_events ORDER BY event_id").fetchall() and [dict(row) for row in store.connection.execute("SELECT lifecycle_state,reason FROM source_registry_events ORDER BY event_id").fetchall()]},sort_keys=True))
    finally: store.close()
