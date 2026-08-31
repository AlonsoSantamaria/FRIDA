"""Canonical non-secret local runtime bootstrap and model-free preflight."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT="project-b241d3e1-4c3d-4801-9c6"; LOCATION="global"
ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT.parent / "frida.gcloud-gate4b"

@dataclass(frozen=True, slots=True)
class Preflight:
    state:str; project:str|None; checks:dict[str,bool]

def environment() -> dict[str,str]:
    return {"CLOUDSDK_CONFIG":str(CONFIG),"GOOGLE_CLOUD_PROJECT":PROJECT,"GOOGLE_GENAI_USE_VERTEXAI":"TRUE","GOOGLE_CLOUD_LOCATION":LOCATION}

def apply() -> dict[str,str]:
    values=environment(); os.environ.update(values); return values

def preflight() -> Preflight:
    values=apply(); checks={"venv":Path(os.sys.executable).name.lower().startswith("python"),"cloudsdk_config":Path(values["CLOUDSDK_CONFIG"]).is_dir(),"vertex":values["GOOGLE_GENAI_USE_VERTEXAI"]=="TRUE","global":values["GOOGLE_CLOUD_LOCATION"]==LOCATION}
    if not checks["cloudsdk_config"]: return Preflight("AUTH_CONTEXT_UNAVAILABLE",None,checks|{"adc":False,"project":False})
    try:
        import google.auth
        _,project=google.auth.default()
        checks["adc"]=True; checks["project"]=project==PROJECT
        return Preflight("READY" if all(checks.values()) else "AUTH_CONTEXT_UNAVAILABLE",project,checks)
    except Exception:
        return Preflight("AUTH_CONTEXT_UNAVAILABLE",None,checks|{"adc":False,"project":False})
