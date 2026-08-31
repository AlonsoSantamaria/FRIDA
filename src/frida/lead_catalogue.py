"""Truthful local logical catalogue for the revised FRIDA Lead architecture."""
AGENT_CATALOGUE={
 "frida_lead":{"role":"semantic attention, planning, review and interpretation","tools":[],"call_limit":3},
 "economic_directory_change":{"role":"conservative DENUE edition interpretation","tools":[],"call_limit":2},
 "urban_development_status":{"role":"conservative Semaforo status interpretation","tools":[],"call_limit":2},
 "independent_challenger":{"role":"independent challenge","tools":[],"call_limit":1},
}
ALLOWED_SPECIALISTS=frozenset({"economic_directory_change","urban_development_status"})
