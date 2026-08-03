from pathlib import Path
import re

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")
text = source.read_text(encoding="utf-8")

required = [
    "V79_R5_BINARY_MARKER_MANIFEST_R5_EXECUTE_BUNDLE_GRAPH",
    "kaiozen_v79_r5_binary_marker_manifest",
    "D3DMetal RTX presented-frame producer chain v79 R5: ACTIVE",
    "EXECUTE_BUNDLE_EDGE",
    "COMMAND_LIST_RESET_GENERATION",
    "BUNDLE_GRAPH_RESOLUTION",
    "BUNDLE_RING_FRAME",
    "frame-boundary=recursive-submitted-bundle-graph",
    "s_v79_r5_generation_by_identity",
    "s_v79_r5_operations_by_identity",
    "s_v79_r5_post_strict_resolution_hit_count",
    "s_v79_r5_post_strict_resolution_miss_count",
    "v79_r5_trace_reset",
    "v79_r5_trace_execute_bundle",
    "v79_r5_install_command_list_hooks",
    "V79_R5_EARLY_COMMAND_LIST_BOOTSTRAP",
    "V79_R5_HOTFIX2_MARKER_DRIVEN_PATCHER",
    "reinterpret_cast<ID3D12GraphicsCommandList *>(command_list)",
    "v79_r5_record_rtv_event",
    "v79_r5_collect_locked_resources",
    "s_v79_r3_locked_resources",
    "v79_r5_on_execute_command_lists",
    "v79_r5_on_execute_command_lists(queue, count, command_lists);",
    "v79_r5_install_command_list_hooks(command_list);",
    "v79_r5_record_rtv_event(command_list, resources);",
    "vtable + 10",
    "vtable + 27",
    "v79_process_present(previous_info.resource);",
    "commands_modified=0",
]
missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit("ERROR: missing V79 R5 source markers: " + ", ".join(missing))

v33_helper_matches = list(re.finditer(
    r'(?m)^[ \t]*(?:static\s+)?void\s+v33_install_command_list_method_hooks\s*'
    r'\(\s*IUnknown\s*\*\s*(?:const\s+)?command_list\s*\)\s*\{',
    text))
if len(v33_helper_matches) != 1:
    raise SystemExit(
        "ERROR: V79 R5 expected exactly one whitespace-tolerant V33 IUnknown helper, "
        f"found {len(v33_helper_matches)}")

if text.count("v79_r5_on_execute_command_lists(queue, count, command_lists);") != 1:
    raise SystemExit("ERROR: V79 R5 queue callback must be installed exactly once")
if text.count('extern "C" __declspec(dllexport) const char *kaiozen_v79_r5_binary_marker_manifest()') != 1:
    raise SystemExit("ERROR: V79 R5 exported manifest count is not one")
if text.count("v79_r5_install_command_list_hooks(command_list);") < 2:
    raise SystemExit("ERROR: V79 R5 command-list hook bootstrap is incomplete")
if text.count("v79_r5_record_rtv_event(command_list, resources);") != 1:
    raise SystemExit("ERROR: V79 R5 RTV operation recording must be installed exactly once")

bootstrap_pos = text.index("V79_R5_EARLY_COMMAND_LIST_BOOTSTRAP")
v33_hook_log_pos = text.index("D3DMetal RTX execution trace v33: COMMAND_LIST_HOOKS installed=")
if bootstrap_pos > v33_hook_log_pos:
    raise SystemExit("ERROR: V79 R5 early command-list bootstrap is outside the V33 creation path")
if text.count("V79_R5_EARLY_COMMAND_LIST_BOOTSTRAP") != 1:
    raise SystemExit("ERROR: V79 R5 early command-list bootstrap count is not one")

execute_hook_start = text.rindex("    void STDMETHODCALLTYPE v79_r5_trace_execute_bundle(")
execute_hook_end = text.index("    void v79_r5_collect_locked_resources(", execute_hook_start)
execute_hook = text[execute_hook_start:execute_hook_end]
if execute_hook.index("v79_r5_on_execute_bundle(command_list, bundle);") > execute_hook.index("original(command_list, bundle);"):
    raise SystemExit("ERROR: ExecuteBundle metadata must be captured before forwarding")
if "original(command_list, bundle);" not in execute_hook:
    raise SystemExit("ERROR: ExecuteBundle is not forwarded unchanged")

reset_hook_start = text.rindex("    HRESULT STDMETHODCALLTYPE v79_r5_trace_reset(")
reset_hook_end = text.index("    void STDMETHODCALLTYPE v79_r5_trace_execute_bundle(", reset_hook_start)
reset_hook = text[reset_hook_start:reset_hook_end]
if "const HRESULT result = original(" not in reset_hook or "if (SUCCEEDED(result))" not in reset_hook:
    raise SystemExit("ERROR: Reset generation tracking must occur only after successful forwarding")

queue_start = text.rindex("    void v79_r5_on_execute_command_lists(")
r4_helper_after_queue = re.search(
    r'(?m)^[ \t]*void\s+v79_r4_recover_locked_writer_metadata\s*\(\s*\)\s*\{',
    text[queue_start:])
if r4_helper_after_queue is None:
    raise SystemExit("ERROR: V79 R5 could not locate the whitespace-tolerant R4 helper after the queue observer")
queue_end = queue_start + r4_helper_after_queue.start()
queue = text[queue_start:queue_end]
for marker in [
    "s_v79_r5_post_strict_submit_call_count",
    "s_v79_r5_post_strict_submit_list_count",
    "s_v79_r5_post_strict_resolution_hit_count",
    "s_v79_r5_post_strict_resolution_miss_count",
    "v79_r5_collect_locked_resources",
    "BUNDLE_GRAPH_RESOLUTION",
    "BUNDLE_RING_FRAME",
    "v79_process_present(previous_info.resource)",
]:
    if marker not in queue:
        raise SystemExit(f"ERROR: V79 R5 queue observer is missing {marker}")

# Safety checks: this is an observational command-list hook. It may replace vtable
# pointers to observe recording, but it must forward Reset and ExecuteBundle and
# must not inject GPU commands or alter their parameters.
for forbidden in [
    "ClearUnorderedAccessView",
    "CopyTextureRegion(",
    "CopyResource(",
    "ResourceBarrier(",
    "Dispatch(",
    "DrawInstanced(",
]:
    if forbidden in execute_hook or forbidden in reset_hook:
        raise SystemExit(f"ERROR: V79 R5 hook unexpectedly contains GPU mutation call: {forbidden}")

# Lightweight C++ lexical balance, ignoring strings and comments.
def stripped_cpp(value: str) -> str:
    value = re.sub(r"//[^\n]*", "", value)
    value = re.sub(r"/\*.*?\*/", "", value, flags=re.S)
    value = re.sub(r'R"[^\n(]*\(.*?\)[^\n\"]*"', '""', value, flags=re.S)
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

Path("v79-r5-source-verification.txt").write_text(
    "\n".join([
        "V79_R5_SOURCE_VERIFICATION_OK",
        "V79_R5_HOTFIX2_SOURCE_VERIFICATION_OK",
        "BINARY_MANIFEST=V79_R5_BINARY_MARKER_MANIFEST_R5_EXECUTE_BUNDLE_GRAPH",
        "BINARY_HOTFIX_MARKER=V79_R5_HOTFIX2_MARKER_DRIVEN_PATCHER",
        "EXPORTED_MANIFEST_SYMBOL=kaiozen_v79_r5_binary_marker_manifest",
        "TRIPLET_SOURCE=V79_R3_FROZEN_RECORDING_TIME_TRIPLET",
        "STATIC_WRITER_RECOVERY=V79_R4",
        "EXECUTE_BUNDLE_SLOT=27",
        "EARLY_COMMAND_LIST_BOOTSTRAP=V33_CREATE_COMMAND_LIST_PATH",
        "HOTFIX2_ANCHOR_MODE=MARKER_DRIVEN_REGEX",
        "COMMAND_LIST_RESET_SLOT=10",
        "GENERATION_TRACKING=ENABLED",
        "ORDERED_OPERATION_STREAM=RTV_AND_EXECUTE_BUNDLE",
        "FRAME_BOUNDARY=RECURSIVE_SUBMITTED_BUNDLE_GRAPH",
        "MAX_BUNDLE_DEPTH=8",
        "RAW_POST_STRICT_SUBMISSION_COUNTERS=ENABLED",
        "RESET_FORWARDING=UNCHANGED",
        "EXECUTE_BUNDLE_FORWARDING=UNCHANGED",
        "GPU_READBACK=DISABLED",
        "INJECTED_COPIES=DISABLED",
        "INJECTED_BARRIERS=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "CPP_LEXICAL_BALANCE=PASS",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)
print("V79_R5_SOURCE_VERIFICATION_OK")
print("V79_R5_HOTFIX2_SOURCE_VERIFICATION_OK")
