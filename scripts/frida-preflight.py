"""Model-free canonical FRIDA runtime preflight."""
from __future__ import annotations

import json

from frida.runtime_bootstrap import preflight


if __name__ == "__main__":
    value = preflight()
    print(json.dumps({"state": value.state, "project": value.project, "checks": value.checks}, sort_keys=True))
