from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")
text = source.read_text(encoding="utf-8")
required = [
    "D3DMetal RTX downstream lighting dependency chain v70: ACTIVE",
    "source=first-rayhit-consumer",
    "max-depth=3",
    "stop-on-feedback=enabled",
    "phases=world,manual-post-menu",
    "logical-slot-comparison=enabled",
    "physical-resource-persistence=diagnostic-only",
    "struct v70_input_reference",
    "struct v70_chain_pass_signature",
    "struct v70_chain_phase_state",
    "v70_scan_chain_bindings(",
    "v70_seed_chain(",
    "v70_observe_chain_event(",
    "CHAIN_SEED phase=",
    "CHAIN_PASS phase=",
    "CHAIN_INPUT phase=",
    "CHAIN_OUTPUT phase=",
    "WORLD_CHAIN_COMPLETE",
    "POST_MENU_CHAIN_COMPLETE",
    "CHAIN_COMPARISON depth=",
    "DOWNSTREAM_CHAIN_RESULT success=1",
    "stop_on_feedback=1",
    "readback=disabled",
    "resource-copies=disabled",
    "resource-barriers=disabled",
    "commands_modified=0",
]
missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit("ERROR: V70 missing source markers: " + ", ".join(missing))
counts = {
    "ACTIVE": text.count("downstream lighting dependency chain v70: ACTIVE"),
    "SEED": text.count("CHAIN_SEED phase="),
    "PASS": text.count("CHAIN_PASS phase="),
    "RESULT": text.count("DOWNSTREAM_CHAIN_RESULT success=1"),
    "DIRECT_CALL": text.count('command_list, "direct-compute", false'),
    "INDIRECT_CALL": text.count('command_list,\n                "execute-indirect-compute",\n                false'),
    "DRAW_CALLS": text.count('command_list, "draw-'),
}
for label, count in counts.items():
    if count < 1:
        raise SystemExit(f"ERROR: V70 structural check failed: {label}={count}")
for forbidden in [
    "V70_COMMAND_MODIFICATION=YES",
    "V70_RESOURCE_BARRIER=ENABLED",
    "V70_READBACK=ENABLED",
]:
    if forbidden in text:
        raise SystemExit(f"ERROR: V70 forbidden source marker present: {forbidden}")
report = [
    "V70_SOURCE_VERIFICATION_OK",
    f"ACTIVE_MARKER_COUNT={counts['ACTIVE']}",
    f"CHAIN_SEED_MARKER_COUNT={counts['SEED']}",
    f"CHAIN_PASS_MARKER_COUNT={counts['PASS']}",
    f"CHAIN_RESULT_MARKER_COUNT={counts['RESULT']}",
    "WORLD_CHAIN=ENABLED",
    "POST_MENU_CHAIN=ENABLED",
    "MAX_CHAIN_DEPTH=3",
    "STOP_ON_FEEDBACK=ENABLED",
    "LOGICAL_SLOT_COMPARISON=ENABLED",
    "PHYSICAL_RESOURCE_PERSISTENCE=DIAGNOSTIC_ONLY",
    "RAYHIT_READBACK=DISABLED",
    "RESOURCE_COPIES=DISABLED",
    "RESOURCE_BARRIERS=DISABLED",
    "COMMANDS_MODIFIED=NO",
    "RESULT=PASS",
]
Path("v70-source-verification.txt").write_text("\n".join(report) + "\n", encoding="ascii")
print("V70_SOURCE_VERIFICATION_OK")
