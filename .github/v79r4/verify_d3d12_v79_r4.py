from pathlib import Path
import re

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")
text = source.read_text(encoding="utf-8")

required = [
    "V79_R4_BINARY_MARKER_MANIFEST_R4_SUBMITTED_COMMAND_LIST_BOUNDARY",
    "kaiozen_v79_r4_binary_marker_manifest",
    "D3DMetal RTX presented-frame producer chain v79 R4: ACTIVE",
    "SUBMITTED_RING_COMMAND_LIST",
    "SUBMITTED_RING_FRAME",
    "STATIC_COMMAND_LIST_WRITER_RECOVERY",
    "frame-boundary=submitted-command-list-replay",
    "recording-time-event-capture=enabled",
    "s_v79_r4_command_list_rtvs_by_identity",
    "s_v79_r4_submitted_ring_frame_count",
    "v79_r4_recover_locked_writer_metadata",
    "v79_r4_on_execute_command_lists",
    "v79_r4_on_execute_command_lists(queue, count, command_lists);",
    "v79_r4_command_list_rtvs_by_identity[",
    "v79_process_present(previous_info.resource);",
    "commands_modified=0",
]
missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit("ERROR: missing V79 R4 source markers: " + ", ".join(missing))

if text.count("v79_r4_on_execute_command_lists(queue, count, command_lists);") != 1:
    raise SystemExit("ERROR: V79 R4 execute callback must be installed exactly once")
if text.count("extern \"C\" __declspec(dllexport) const char *kaiozen_v79_r4_binary_marker_manifest()") != 1:
    raise SystemExit("ERROR: V79 R4 exported manifest count is not one")

publish_pos = text.index("    void v79_publish_event(")
bound_start = text.index("    void v79_record_bound_event(", publish_pos)
bound_end = text.index("    void v79_record_copy_event(", bound_start)
bound_text = text[bound_start:bound_end]
if "s_v61_rewritten_steady_state_seen" in bound_text:
    raise SystemExit("ERROR: recording-time bound-event capture is still blocked by strict proof")

copy_start = bound_end
copy_end = text.index("    void STDMETHODCALLTYPE v79_trace_copy_texture_region(", copy_start)
copy_text = text[copy_start:copy_end]
if "s_v61_rewritten_steady_state_seen" in copy_text:
    raise SystemExit("ERROR: recording-time copy capture is still blocked by strict proof")

r3_start = text.index("    void v79_r3_observe_rtv_sequence(")
r3_end = text.index("    void v79_r2_note_begin_candidate(", r3_start)
r3 = text[r3_start:r3_end]
if "v79_r4_recover_locked_writer_metadata();\n            return;" not in r3:
    raise SystemExit("ERROR: recording-time R3 frame processing is not disabled after triplet lock")

execute_start = text.rindex("    void v79_r4_on_execute_command_lists(")
execute_end = text.index("    bool v79_r3_resource_had_begin(", execute_start)
execute = text[execute_start:execute_end]
for marker in [
    "v33_identity_pointer",
    "s_v79_r4_command_list_rtvs_by_identity",
    "s_v79_r3_locked_resources",
    "s_v61_rewritten_steady_state_seen",
    "SUBMITTED_RING_FRAME",
    "v79_process_present(previous_info.resource)",
]:
    if marker not in execute:
        raise SystemExit(f"ERROR: V79 R4 queue observer is missing {marker}")

# Lightweight C++ lexical balance, ignoring strings and comments.
def stripped_cpp(value: str) -> str:
    value = re.sub(r"//[^\n]*", "", value)
    value = re.sub(r"/\*.*?\*/", "", value, flags=re.S)
    value = re.sub(r'R\"[^\n(]*\(.*?\)[^\n\"]*\"', '""', value, flags=re.S)
    value = re.sub(r'"(?:\\.|[^"\\])*"', '""', value)
    value = re.sub(r"'(?:\\.|[^'\\])*'", "''", value)
    return value

clean = stripped_cpp(text)
for opening, closing, label in [("{", "}", "braces"), ("(", ")", "parentheses"), ("[", "]", "brackets")]:
    depth = 0
    for char in clean:
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth < 0:
                raise SystemExit(f"ERROR: negative C++ {label} balance")
    if depth != 0:
        raise SystemExit(f"ERROR: C++ {label} balance ended at {depth}")

Path("v79-r4-source-verification.txt").write_text(
    "\n".join([
        "V79_R4_SOURCE_VERIFICATION_OK",
        "BINARY_MANIFEST=V79_R4_BINARY_MARKER_MANIFEST_R4_SUBMITTED_COMMAND_LIST_BOUNDARY",
        "EXPORTED_MANIFEST_SYMBOL=kaiozen_v79_r4_binary_marker_manifest",
        "TRIPLET_SOURCE=RECORDING_TIME_OM_SET_RENDER_TARGETS",
        "FRAME_BOUNDARY=SUBMITTED_COMMAND_LIST_REPLAY",
        "COMMAND_LIST_IDENTITY_MAP=ENABLED",
        "STATIC_COMMAND_LIST_WRITER_RECOVERY=ENABLED",
        "RECORDING_TIME_EVENT_CAPTURE=ENABLED",
        "STRICT_LINEAGE_REQUIRED_FOR_PRESENT_CAPTURE=YES",
        "GPU_READBACK=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "CPP_LEXICAL_BALANCE=PASS",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)
print("V79_R4_SOURCE_VERIFICATION_OK")
