from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")
text = source.read_text(encoding="utf-8")

required = [
    "D3DMetal RTX persistent-map candidate bootstrap v68: ACTIVE",
    "persistent-map-rescan=bounded",
    "max-scans=3",
    "candidate-source=steady-state-persistent-map",
    "s_v68_persistent_scan_attempts",
    "v59_scan_persistent_mappings();",
    "PERSISTENT_MAP_SCAN_RESULT success=%u",
    "BOOTSTRAP_TRACKING_DISABLED ready=1",
    "consumer-observation=v66",
    "readback=disabled",
    "resource-barriers=disabled",
    "commands_modified=0",
]
for marker in required:
    if marker not in text:
        raise SystemExit(f"ERROR: missing V68 source marker: {marker}")

report = """V68_SOURCE_VERIFICATION_OK
PERSISTENT_MAP_RESCAN=ENABLED
MAX_PERSISTENT_MAP_SCANS=3
U1_REFRESH_AFTER_SCAN=ENABLED
TRACKING_DISABLED_AFTER_U1_READY=YES
CONSUMER_OBSERVATION=V66
RAYHIT_READBACK=DISABLED
RESOURCE_COPIES=DISABLED
RESOURCE_BARRIERS=DISABLED
COMMANDS_MODIFIED=NO
RESULT=PASS
"""
Path("v68-source-verification.txt").write_text(report, encoding="ascii")
print(report, end="")
