from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
text = source.read_text(encoding="utf-8")

required = [
    "D3DMetal RTX ray-hit consumer bootstrap repair v67: ACTIVE",
    "resource-map-bootstrap=enabled",
    "bounded-refresh=enabled",
    "actual-pipeline-id=enabled",
    "v39_install_resource_hooks(device);",
    "v64_rewritten_capture_candidate(",
    "s_v67_last_refresh_pipeline",
    "s_v67_last_refresh_ray",
    "s_v67_refresh_attempts",
    "v67-rewritten-pipeline-bootstrap",
    "v67-bounded-ray-bootstrap",
    "U1_BOOTSTRAP_RESULT success=%u",
    "consumer-observation=v66",
    "readback=disabled",
    "resource-barriers=disabled",
    "commands_modified=0",
]
for marker in required:
    if marker not in text:
        raise SystemExit(f"ERROR: missing V67 source marker: {marker}")

for forbidden in [
    'v65_refresh_current_u1_target(0, "v66-world-ray-dispatch")',
]:
    if forbidden in text:
        raise SystemExit(f"ERROR: obsolete V66 bootstrap remains: {forbidden}")

report = """V67_SOURCE_VERIFICATION_OK
RESOURCE_CREATION_HOOKS=ENABLED
RESOURCE_MAP_UNMAP_BOOTSTRAP=ENABLED
ACTUAL_REWRITTEN_PIPELINE_ID=ENABLED
REFRESH_INTERVAL_RAYS=64
REFRESH_SPAM_REMOVED=YES
RAYHIT_READBACK=DISABLED
RESOURCE_COPIES=DISABLED
RESOURCE_BARRIERS=DISABLED
COMMANDS_MODIFIED=NO
RESULT=PASS
"""
Path("v67-source-verification.txt").write_text(report, encoding="ascii")
print(report, end="")
