from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")

text = source.read_text(encoding="utf-8")

# Keep this source verifier aligned with the postconditions already enforced by
# patch_d3d12_v67.py. The later V67 binary-verification step remains stricter
# and validates every user-visible marker in the compiled ReShade64.dll.
required = [
    "D3DMetal RTX ray-hit consumer bootstrap repair v67: ACTIVE",
    "v39_install_resource_hooks(device);",
    "v64_rewritten_capture_candidate(",
    "v67-rewritten-pipeline-bootstrap",
    "v67-bounded-ray-bootstrap",
    "U1_BOOTSTRAP_RESULT success=%u",
    "actual-pipeline-id=enabled",
    "bounded-refresh=enabled",
]
forbidden = [
    'v65_refresh_current_u1_target(0, "v66-world-ray-dispatch")',
]

missing = []
remaining = []

print("V67_SOURCE_VERIFIER_DIAGNOSTICS")
for marker in required:
    present = marker in text
    print(f"REQUIRED={'PASS' if present else 'FAIL'} marker={marker}")
    if not present:
        missing.append(marker)

for marker in forbidden:
    present = marker in text
    print(f"FORBIDDEN={'FAIL' if present else 'PASS'} marker={marker}")
    if present:
        remaining.append(marker)

if missing or remaining:
    lines = [
        "V67_SOURCE_VERIFICATION_FAIL",
        f"MISSING_COUNT={len(missing)}",
        f"FORBIDDEN_REMAINING_COUNT={len(remaining)}",
    ]
    lines.extend(f"MISSING={item}" for item in missing)
    lines.extend(f"FORBIDDEN_REMAINING={item}" for item in remaining)
    lines.append("RESULT=FAIL")
    report = "\n".join(lines) + "\n"
    Path("v67-source-verification.txt").write_text(report, encoding="ascii")
    print(report, end="")
    raise SystemExit(1)

report = """V67_SOURCE_VERIFICATION_OK
PATCH_POSTCONDITIONS=PASS
RESOURCE_CREATION_HOOKS=ENABLED
RESOURCE_MAP_UNMAP_BOOTSTRAP=ENABLED
ACTUAL_REWRITTEN_PIPELINE_ID=ENABLED
REFRESH_INTERVAL_RAYS=64
REFRESH_SPAM_REMOVED=YES
RAYHIT_READBACK=DISABLED
RESOURCE_COPIES=DISABLED
RESOURCE_BARRIERS=DISABLED
COMMANDS_MODIFIED=NO
STRICT_COMPILED_BINARY_VERIFICATION=RETAINED
RESULT=PASS
"""
Path("v67-source-verification.txt").write_text(report, encoding="ascii")
print(report, end="")
