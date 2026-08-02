from pathlib import Path
source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')
required = [
    'D3DMetal RTX definitive branch isolation v74: ACTIVE',
    'KAIOZEN_V74_VARIANT',
    'selection_timing=dll-startup',
    'BRANCH_A_SIGNATURE_MATCH',
    'BRANCH_B_SIGNATURE_MATCH',
    'BRANCH_CLEAR_PASS variant=',
    'A-fullres-offset18',
    'B-768x32-hierarchy',
    'group_x != 345 || group_y != 222',
    'group_x != 87 || group_y != 56',
    'target18.resource.width == 2760',
    'target6.resource.width == 768',
    'target6.resource.height == 32',
    'v74_same_resource(target18, alias2)',
    'D3D12_RESOURCE_BARRIER_TYPE_UAV',
    'v74_apply_variant_a_before_dispatch',
    'v74_apply_variant_b_after_dispatch',
    's_v62_u1_target_ready.load',
    's_v66_world_consumer_found.load',
    'commands_modified=1'
]
missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit('ERROR: missing V74 source markers: ' + ', '.join(missing))

start = text.find('void STDMETHODCALLTYPE v66_trace_dispatch(')
end = text.find('void STDMETHODCALLTYPE v66_trace_set_pipeline_state(', start)
if min(start, end) < 0:
    raise SystemExit('ERROR: V74 dispatch hook range missing')
hook = text[start:end]
pre = hook.find('v74_apply_variant_a_before_dispatch(')
orig = hook.find('s_v66_original_dispatch(')
post = hook.find('v74_apply_variant_b_after_dispatch(')
observe = hook.find('v72_observe_post_feedback_event(')
if min(pre, orig, post, observe) < 0 or not (pre < orig < post < observe):
    raise SystemExit('ERROR: V74 dispatch ordering is invalid')
if 'v73_apply_selected_branch_before_dispatch(' in hook:
    raise SystemExit('ERROR: obsolete V73 clear call remains active in dispatch hook')

active_pos = text.find('D3DMetal RTX definitive branch isolation v74: ACTIVE')
select_call = text.rfind('(void)v74_get_selected_variant();', 0, active_pos)
if select_call < 0:
    raise SystemExit('ERROR: V74 selector is not read during startup logging')

clear_start = text.find('bool v74_clear_with_uav_barriers(')
clear_end = text.find('void v74_log_clear_pass(', clear_start)
clear_body = text[clear_start:clear_end]
if clear_body.count('command_list->ResourceBarrier(1, &barrier);') != 2:
    raise SystemExit('ERROR: V74 does not issue exactly two UAV barriers per clear')
if clear_body.count('ClearUnorderedAccessViewFloat(') != 1:
    raise SystemExit('ERROR: V74 clear helper count is invalid')

Path('v74-source-verification.txt').write_text(
    'V74_SOURCE_VERIFICATION_OK\n'
    'SELECTOR_READ_AT_DLL_STARTUP=YES\n'
    'VARIANT_A_EXACT_SIGNATURE=YES\n'
    'VARIANT_A_CLEAR_BEFORE_DISPATCH=YES\n'
    'VARIANT_B_EXACT_768x32_SIGNATURE=YES\n'
    'VARIANT_B_CLEAR_AFTER_PRODUCER=YES\n'
    'OBSOLETE_V73_CLEAR_CALL_ACTIVE=NO\n'
    'UAV_BARRIERS_PER_CLEAR=2\n'
    'RUNNER_MUST_REQUIRE_CLEAR_LOG=YES\n'
    'GPU_READBACK=DISABLED\n'
    'RESOURCE_COPIES=DISABLED\n'
    'COMMANDS_MODIFIED=YES\n'
    'RESULT=PASS\n',
    encoding='ascii')
print('V74_SOURCE_VERIFICATION_OK')
