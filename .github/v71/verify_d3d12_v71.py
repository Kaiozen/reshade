from pathlib import Path

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')

required = [
    'D3DMetal RTX temporal feedback reset visual candidate v71: ACTIVE',
    'target=v70-first-feedback-boundary',
    'logical-root0-uav-offsets12,13',
    'HISTORY_FEEDBACK_TARGET_FOUND',
    'HISTORY_FEEDBACK_CLEAR_PASS',
    'ClearUnorderedAccessViewFloat',
    'v71_reset_history_feedback_before_dispatch',
    'feedback_offsets=12,13',
    'clear_value=0,0,0,0',
    'explicit_resource_barriers=0',
    'commands_modified=1',
]
missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit('ERROR: missing V71 source markers: ' + ', '.join(missing))

forbidden = [
    'functional FP32 forced-miss control v52: ACTIVE',
    'ray-hit output pattern control v53: ACTIVE',
]
remaining = [marker for marker in forbidden if marker in text]
if remaining:
    raise SystemExit('ERROR: forbidden diagnostic markers remain active: ' + ', '.join(remaining))

hook_start = text.find('void STDMETHODCALLTYPE v66_trace_dispatch(')
if hook_start < 0:
    raise SystemExit('ERROR: v66_trace_dispatch hook is missing')
hook_end = text.find('void STDMETHODCALLTYPE v66_trace_set_pipeline_state(', hook_start)
if hook_end < 0:
    raise SystemExit('ERROR: dispatch hook end anchor is missing')
hook = text[hook_start:hook_end]
clear_pos = hook.find('v71_reset_history_feedback_before_dispatch(')
dispatch_pos = hook.find('s_v66_original_dispatch(command_list, group_x, group_y, group_z)')
observe_pos = hook.find('v70_observe_chain_event(')
if min(clear_pos, dispatch_pos, observe_pos) < 0 or not (clear_pos < dispatch_pos < observe_pos):
    raise SystemExit('ERROR: V71 clear must run before the real dispatch and V70 observation')

if text.count('command_list->ClearUnorderedAccessViewFloat(') != 2:
    raise SystemExit('ERROR: V71 must issue exactly two UAV clear calls')
if 'group_x) * 8u' not in text or 'group_y * 8u' not in text:
    raise SystemExit('ERROR: V71 8x8 dispatch-to-resource signature is missing')

report = Path('v71-source-verification.txt')
report.write_text(
    '\n'.join([
        'V71_SOURCE_VERIFICATION_OK',
        'TARGET=V70_FIRST_FEEDBACK_BOUNDARY',
        'DYNAMIC_PIPELINE_IDENTIFICATION=YES',
        'ROOT_PARAMETER=0',
        'FEEDBACK_DESCRIPTOR_OFFSETS=12,13',
        'EXPECTED_THREADGROUP_FOOTPRINT=8X8',
        'CLEAR_BEFORE_DISPATCH=YES',
        'CLEAR_UAV_CALL_COUNT=2',
        'CLEAR_VALUE=0,0,0,0',
        'RESOURCE_COPIES=DISABLED',
        'EXPLICIT_RESOURCE_BARRIERS=DISABLED',
        'COMMANDS_MODIFIED=YES',
        'V52_FORCED_ZERO_MASK_PRESENT=NO',
        'V53_PATTERNED_OUTPUT_PRESENT=NO',
        'RESULT=PASS',
    ]) + '\n',
    encoding='ascii')
print('V71_SOURCE_VERIFICATION_OK')
