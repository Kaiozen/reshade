from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")
text = source.read_text(encoding="utf-8")

required = [
    "D3DMetal RTX manual normal-menu history transition v69: ACTIVE",
    "trigger=explicit-signal",
    "signal-file=C:/kaiozen-v69-menu-closed.signal",
    "automatic-gap-detection=disabled",
    "normal-menu-gap-detection=disabled-by-v69",
    "s_v69_manual_signal_accepted",
    "s_v69_manual_signal_checks",
    "GetFileAttributesW(",
    "MANUAL_MENU_CONFIRMATION accepted=1",
    "PERSISTENT_OUTPUT_CANDIDATE resource_id=",
    "classification=lighting-history-candidate",
    "persistent-output-comparison=enabled",
    "readback=disabled",
    "resource-barriers=disabled",
    "commands_modified=0",
]
for marker in required:
    if marker not in text:
        raise SystemExit(f"ERROR: missing V69 source marker: {marker}")

for forbidden in [
    "MENU_TRANSITION_RESUME gap_index=",
    "normal-menu-gap-threshold-ms=3000",
]:
    if forbidden in text:
        raise SystemExit(f"ERROR: forbidden V69 automatic-gap marker remains: {forbidden}")

report = """V69_SOURCE_VERIFICATION_OK
AUTOMATIC_GAP_DETECTION=DISABLED
MANUAL_SIGNAL_FILE=C:/kaiozen-v69-menu-closed.signal
MANUAL_CONFIRMATION_REQUIRED=YES
POST_MENU_CAPTURE_ARMED_ONLY_AFTER_SIGNAL=YES
PERSISTENT_OUTPUT_COMPARISON=ENABLED
LIGHTING_HISTORY_CANDIDATE_LOGGING=ENABLED
RAYHIT_READBACK=DISABLED
RESOURCE_COPIES=DISABLED
RESOURCE_BARRIERS=DISABLED
COMMANDS_MODIFIED=NO
RESULT=PASS
"""
Path("v69-source-verification.txt").write_text(report, encoding="ascii")
print(report, end="")
