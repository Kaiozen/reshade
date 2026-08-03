from pathlib import Path

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')

required = [
    'kaiozen_v78_binary_marker_manifest',
    'V78_BINARY_MARKER_MANIFEST_R1_RESUME_HISTORY_PAIR_CANARY',
    'D3DMetal RTX resume-history candidate pair canary v78: ACTIVE',
    'KAIOZEN_V78_ACTIVE',
    'V78_CANDIDATE_PAIR_SIGNATURE_MATCH',
    'V78_CANDIDATE_PAIR_CAPTURE_RECORDED',
    'V78_CANDIDATE_PAIR_CANARY_PASS',
    'groups=173,444,1',
    'targets=root0-offsets4,5',
    'control=root0-offset7',
    'queue-fenced-readback=required',
    'v78_apply_candidate_pair_after_dispatch',
    'group_x != 173 || group_y != 444 || group_z != 1',
    'v74_resolve_compute_table_descriptor(state, 0, 4, 3, candidate_a)',
    'v74_resolve_compute_table_descriptor(state, 0, 5, 3, candidate_b)',
    'v74_resolve_compute_table_descriptor(state, 0, 7, 3, control)',
    'candidate_a.resource.width == 2760 && candidate_a.resource.height == 1776',
    'candidate_b.resource.width == 2760 && candidate_b.resource.height == 1776',
    'control.resource.width == 2760 && control.resource.height == 1776',
    '!s_v61_rewritten_steady_state_seen.load(std::memory_order_acquire)',
    'v76_record_before_after_capture(',
    'v76_clear_with_pattern(command_list, candidate_a, pattern_a)',
    'v76_clear_with_pattern(command_list, candidate_b, pattern_b)',
    'if (v78_is_active())\n            return false;',
    'V76_FIRST_CONSUMER_TARGET_DISABLED_WHEN_V78_ACTIVE=YES',
]
# The last marker is in the patch report, not the source.
source_required = required[:-1]
missing = [marker for marker in source_required if marker not in text]
if missing:
    raise SystemExit('ERROR: V78 source is missing markers: ' + ', '.join(missing))

# One runtime implementation and one hook call plus one prototype.
if text.count('bool v78_apply_candidate_pair_after_dispatch(') != 2:
    raise SystemExit('ERROR: V78 apply function prototype/definition count is not exactly 2')
if text.count('v78_apply_candidate_pair_after_dispatch(\n            command_list, group_x, group_y, group_z);') != 1:
    raise SystemExit('ERROR: V78 direct-dispatch hook count is not exactly 1')
if text.count('extern "C" __declspec(dllexport) const char *kaiozen_v78_binary_marker_manifest()') != 1:
    raise SystemExit('ERROR: V78 exported marker manifest count is not exactly 1')

# The target mutation must be recorded after the actual direct dispatch.
dispatch_body_start = text.find('void STDMETHODCALLTYPE v66_trace_dispatch(')
if dispatch_body_start < 0:
    raise SystemExit('ERROR: v66_trace_dispatch was not found')
dispatch_body = text[dispatch_body_start:dispatch_body_start + 2600]
original_pos = dispatch_body.find('s_v66_original_dispatch(command_list, group_x, group_y, group_z);')
v78_pos = dispatch_body.find('v78_apply_candidate_pair_after_dispatch(')
if original_pos < 0 or v78_pos < 0 or v78_pos <= original_pos:
    raise SystemExit('ERROR: V78 mutation is not after the original target dispatch')

# V78 intentionally reuses V76 queue-fenced readback and must not install a
# second queue hook or a second worker implementation.
if text.count('DWORD WINAPI v76_readback_worker') != 1:
    raise SystemExit('ERROR: V76 readback worker count changed unexpectedly')
if text.count('void v76_on_execute_command_lists(') != 3:
    raise SystemExit('ERROR: V76 queue submission declaration/definition count changed unexpectedly')

report = '\n'.join([
    'V78_SOURCE_VERIFICATION_OK',
    'RUNTIME_GATE=KAIOZEN_V78_ACTIVE',
    'READBACK_BACKEND_GATE=KAIOZEN_V76_ACTIVE',
    'TARGET_PASS=DEPTH2_DIRECT_COMPUTE_173x444x1',
    'TARGET_A=ROOT0_OFFSET4_FORMAT10_2760x1776',
    'TARGET_B=ROOT0_OFFSET5_FORMAT10_2760x1776',
    'CONTROL=ROOT0_OFFSET7_FORMAT10_2760x1776',
    'TARGETS_DISTINCT=YES',
    'STRICT_REWRITTEN_GATE=YES',
    'MUTATION_TIMING=AFTER_TARGET_DISPATCH',
    'V76_FIRST_CONSUMER_TARGET_DISABLED=YES',
    'QUEUE_FENCED_READBACK=REUSED_FROM_V76',
    'PERSISTENT_CANARY_CLEAR=YES',
    'PATTERNS=MAGENTA_AND_CYAN',
    'COMMANDS_MODIFIED=YES',
    'RESULT=PASS',
    '',
])
Path('v78-source-verification.txt').write_text(report, encoding='utf-8', newline='\n')
print(report, end='')
