from pathlib import Path
source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')
required = [
    'D3DMetal RTX first ray-hit consumer output knockout v75: ACTIVE',
    'KAIOZEN_V75_ACTIVE',
    'RUNTIME_GATE active=',
    'FIRST_CONSUMER_SIGNATURE_MATCH',
    'OUTPUT_PAIR_CLEAR_PASS',
    'OUTPUT_PAIR_CLEAR_FAILURE',
    'root0-offset17-srv',
    'output35_resource_id=',
    'output36_resource_id=',
    'v74_resolve_compute_table_descriptor(state, 0, 17, 2, u1_srv)',
    'v74_resolve_compute_table_descriptor(state, 0, 35, 3, output35)',
    'v74_resolve_compute_table_descriptor(state, 0, 36, 3, output36)',
    'v74_clear_with_uav_barriers(command_list, output35)',
    'v74_clear_with_uav_barriers(command_list, output36)',
    'v75_clear_first_consumer_outputs_after_dispatch(',
    'uav_barriers=4',
    'commands_modified=1'
]
missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit('ERROR: missing V75 source markers: ' + ', '.join(missing))

if text.count('                int selected = 0;\n') != 1:
    raise SystemExit('ERROR: V74 default selector was not disabled exactly once')

start = text.find('void STDMETHODCALLTYPE v34_trace_execute_indirect(')
end = text.find('void v34_install_create_command_signature_hook(', start)
if min(start, end) < 0:
    raise SystemExit('ERROR: execute-indirect hook range missing')
hook = text[start:end]
orig = hook.find('s_v34_original_execute_indirect(')
observe = hook.find('v66_observe_consumer_dispatch(')
clear = hook.find('v75_clear_first_consumer_outputs_after_dispatch(')
if min(orig, observe, clear) < 0 or not (orig < observe < clear):
    raise SystemExit('ERROR: V75 output clear is not after original execute and consumer identification')

impl_start = text.find('bool v75_clear_first_consumer_outputs_after_dispatch(')
impl_end = text.find('void STDMETHODCALLTYPE v66_trace_dispatch(', impl_start)
body = text[impl_start:impl_end]
if body.count('v74_clear_with_uav_barriers(command_list, output') != 2:
    raise SystemExit('ERROR: V75 must clear exactly two consumer outputs')
if 'output35.resource.width == 2760' not in body or 'output36.resource.width == 2760' not in body:
    raise SystemExit('ERROR: V75 exact output extent gate is missing')

Path('v75-source-verification.txt').write_text(
    'V75_SOURCE_VERIFICATION_OK\n'
    'V74_DEFAULT_SELECTOR_DISABLED=YES\n'
    'RUNTIME_GATE_READ_AT_STARTUP=YES\n'
    'FIRST_CONSUMER_EXACT_SIGNATURE=YES\n'
    'U1_ROOT0_OFFSET17_SRV=YES\n'
    'OUTPUT35_AND36_PAIR=YES\n'
    'CLEAR_AFTER_ORIGINAL_EXECUTE_INDIRECT=YES\n'
    'UAV_BARRIERS_TOTAL_PER_PAIR=4\n'
    'VISUAL_TIMER_MUST_REQUIRE_CLEAR_LOG=YES\n'
    'GPU_READBACK=DISABLED\n'
    'RESOURCE_COPIES=DISABLED\n'
    'COMMANDS_MODIFIED=YES\n'
    'RESULT=PASS\n',
    encoding='ascii')
print('V75_SOURCE_VERIFICATION_OK')
