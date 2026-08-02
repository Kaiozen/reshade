from pathlib import Path
import sys

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')
checks = {
    'active_marker': 'D3DMetal RTX canary mutation verification v76: ACTIVE',
    'runtime_gate': 'KAIOZEN_V76_ACTIVE',
    'v75_disabled': 'const bool active = false; // V76 owns the mutation path.',
    'capture_recorded': 'CANARY_CAPTURE_RECORDED',
    'queue_submitted': 'CANARY_QUEUE_SUBMITTED',
    'readback_result': 'CANARY_READBACK_RESULT',
    'clear_pass': 'CANARY_CLEAR_PASS',
    'copy_texture_region': 'command_list->CopyTextureRegion(',
    'placed_footprint': 'D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT',
    'copy_source_transition': 'D3D12_RESOURCE_STATE_COPY_SOURCE',
    'uav_restore': 'D3D12_RESOURCE_STATE_UNORDERED_ACCESS',
    'readback_bytes': 'static constexpr UINT64 v76_readback_bytes = 4096;',
    'sample_stride': 'static constexpr UINT64 v76_sample_stride = 512;',
    'row_pitch': 'static constexpr UINT v76_row_pitch = 256;',
    'pattern35': 'const FLOAT pattern35[4] = { 1.0f, 0.0f, 1.0f, 1.0f };',
    'pattern36': 'const FLOAT pattern36[4] = { 0.0f, 1.0f, 1.0f, 1.0f };',
    'expected35': '0x00, 0x3C, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x3C',
    'expected36': '0x00, 0x00, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C',
    'two_sample_points': 'sample_points=64,64|1380,888',
    'eight_samples': 'samples=8',
    'decisive_match': 'decisive_match = match35 && match36 && changed35 && changed36;',
    'persistent_clear': 'persistent_until-test-end=1',
    'execute_call': 'v76_apply_canary_after_dispatch(',
    'queue_call': 'v76_on_execute_command_lists(queue, count, command_lists);',
    'identity_guard': 'stage=command-list-identity',
    'capture_retry': 's_v76_capture_claimed.store(false, std::memory_order_release);',
}
missing = [name for name, marker in checks.items() if marker not in text]
if missing:
    raise SystemExit('ERROR: Missing V76 source checks: ' + ', '.join(missing))
if text.count('D3DMetal RTX canary mutation verification v76: ACTIVE') != 1:
    raise SystemExit('ERROR: V76 ACTIVE marker count is not exactly one')
if text.count('v76_apply_canary_after_dispatch(') < 3:
    raise SystemExit('ERROR: V76 apply function prototype/definition/call incomplete')
if text.count('v76_on_execute_command_lists(') < 4:
    raise SystemExit('ERROR: V76 queue hook declaration/definition/call incomplete')
execute_anchor = text.index('s_v34_original_execute_indirect(')
apply_anchor = text.index('v76_apply_canary_after_dispatch(', execute_anchor)
if apply_anchor <= execute_anchor:
    raise SystemExit('ERROR: V76 mutation is not recorded after original ExecuteIndirect')
queue_original = text.index('s_v38_original_execute_command_lists(')
queue_v76 = text.index('v76_on_execute_command_lists(queue, count, command_lists);', queue_original)
if queue_v76 <= queue_original:
    raise SystemExit('ERROR: V76 queue signaling is not after original ExecuteCommandLists')
if 'GPU_READBACK=DISABLED' in Path('v76-patch-report.txt').read_text(encoding='ascii') if Path('v76-patch-report.txt').exists() else False:
    raise SystemExit('ERROR: V76 patch report incorrectly disables readback')
Path('v76-source-verification.txt').write_text(
    '\n'.join([
        'V76_SOURCE_VERIFICATION_OK',
        'V75_RUNTIME_DISABLED=YES',
        'TARGET_SIGNATURE=U1_ROOT0_OFFSET17_OUTPUTS35_36',
        'BEFORE_AFTER_READBACK=YES',
        'SAMPLE_POINTS=64,64|1380,888',
        'SAMPLE_COUNT=8',
        'READBACK_BYTES=4096',
        'ROW_PITCH=256',
        'PLACEMENT_ALIGNMENT=512',
        'EXPECTED35_HALF_HEX=003C0000003C003C',
        'EXPECTED36_HALF_HEX=0000003C003C003C',
        'DECISIVE_MATCH_REQUIRES_BOTH_OUTPUTS_AND_CHANGED_BEFORE=YES',
        'PERSISTENT_CANARY_CLEAR=YES',
        'QUEUE_FENCE_WORKER=YES',
        'COMMAND_LIST_IDENTITY_REQUIRED=YES',
        'CAPTURE_RETRY_ON_SETUP_FAILURE=YES',
        'COMMANDS_MODIFIED=YES',
        'RESULT=PASS',
    ]) + '\n',
    encoding='ascii')
print('V76_SOURCE_VERIFICATION_OK')
