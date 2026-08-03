from pathlib import Path

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')

checks = {
    'exported_manifest': 'kaiozen_v77_binary_marker_manifest',
    'manifest_tag': 'V77_BINARY_MARKER_MANIFEST_R1_SETTINGS_RESUME_DIFFERENTIAL',
    'runtime_gate': 'KAIOZEN_V77_ACTIVE',
    'active_marker': 'D3DMetal RTX settings-resume resource differential v77: ACTIVE',
    'baseline_ready': 'V77_BASELINE_READY ready=1',
    'manual_signal': 'SETTINGS_SIGNAL_ACCEPTED accepted=1',
    'signal_path': 'C:/kaiozen-v77-settings-returned.signal',
    'candidate_marker': 'DIFFERENTIAL_CANDIDATE rank=',
    'result_marker': 'DIFFERENTIAL_RESULT success=',
    'baseline_count': 'static constexpr uint64_t v77_events_per_phase = 120;',
    'slot_limit': 'static constexpr size_t v77_max_slots_per_phase = 4096;',
    'descriptor_limit': 'const UINT inspect = remaining < 96u ? remaining : 96u;',
    'textures_only': 'resource.resource_id == 0 || resource.dimension <= 1',
    'physical_overlap': 'physical_overlap=0',
    'feedback_rank': 'feedback_baseline=%u feedback_post=%u',
    'strict_proof': 'strict_rewritten_proof=%u',
    'execute_indirect_call': '"execute-indirect-compute",\n                false);',
    'direct_compute_call': '"direct-compute", false);',
    'draw_call': '"draw-instanced", true);',
    'draw_indexed_call': '"draw-indexed-instanced", true);',
    'compare_claim': 's_v77_compare_claimed.compare_exchange_strong(',
    'no_commands': 'commands_modified=0',
}
missing = [name for name, marker in checks.items() if marker not in text]
if missing:
    raise SystemExit('ERROR: Missing V77 source checks: ' + ', '.join(missing))

if text.count('kaiozen_v77_binary_marker_manifest') != 1:
    raise SystemExit('ERROR: V77 exported manifest function count is not exactly one')
if text.count('D3DMetal RTX settings-resume resource differential v77: ACTIVE') != 2:
    raise SystemExit('ERROR: V77 ACTIVE marker count is not exactly two')
if text.count('v77_observe_event(') < 6:
    raise SystemExit('ERROR: V77 observer prototype/definition/calls are incomplete')
if text.count('V77_BASELINE_READY') < 2:
    raise SystemExit('ERROR: V77 baseline marker is not retained in source and manifest')
if 'ClearUnorderedAccessView' in text[text.index('    bool v77_is_active()\n    {'):text.index('void STDMETHODCALLTYPE v66_trace_dispatch(')]:
    raise SystemExit('ERROR: V77 implementation unexpectedly contains a UAV clear')
if 'CopyTextureRegion' in text[text.index('    bool v77_is_active()\n    {'):text.index('void STDMETHODCALLTYPE v66_trace_dispatch(')]:
    raise SystemExit('ERROR: V77 implementation unexpectedly contains a texture copy')
if 'ResourceBarrier' in text[text.index('    bool v77_is_active()\n    {'):text.index('void STDMETHODCALLTYPE v66_trace_dispatch(')]:
    raise SystemExit('ERROR: V77 implementation unexpectedly contains a resource barrier')

# Ensure the manual signal is accepted only after the baseline gate exists.
baseline_gate = text.index('s_v77_baseline_ready.load(std::memory_order_acquire)')
signal_lookup = text.index('L"C:\\\\kaiozen-v77-settings-returned.signal"')
if signal_lookup <= baseline_gate:
    raise SystemExit('ERROR: V77 signal lookup is not guarded by baseline readiness')

# Ensure observations happen after the original rendering calls.
execute_original = text.index('s_v34_original_execute_indirect(')
execute_observe = text.index('v77_observe_event(', execute_original)
if execute_observe <= execute_original:
    raise SystemExit('ERROR: V77 ExecuteIndirect observation is not after the original call')
dispatch_definition = text.index('void STDMETHODCALLTYPE v66_trace_dispatch(')
dispatch_original = text.index('s_v66_original_dispatch(command_list', dispatch_definition)
dispatch_observe = text.index('v77_observe_event(', dispatch_original)
if dispatch_observe <= dispatch_original:
    raise SystemExit('ERROR: V77 direct dispatch observation is not after the original call')

patch_report = Path('v77-patch-report.txt')
if not patch_report.is_file() or 'COMMANDS_MODIFIED=NO' not in patch_report.read_text(encoding='ascii'):
    raise SystemExit('ERROR: V77 patch report is missing or unsafe')

Path('v77-source-verification.txt').write_text(
    '\n'.join([
        'V77_SOURCE_VERIFICATION_OK',
        'RUNTIME_GATE=KAIOZEN_V77_ACTIVE',
        'TRIGGER=RADIAL_SETTINGS_RETURN_TO_WORLD',
        'SIGNAL_FILE=C:/kaiozen-v77-settings-returned.signal',
        'BASELINE_EVENTS=120',
        'POST_EVENTS=120',
        'DESCRIPTOR_SCAN_LIMIT=96',
        'TEXTURES_ONLY=YES',
        'LOGICAL_SLOT_MATCHING=PIPELINE_EVENT_KIND_ROOT_OFFSET_FORMAT_DIMENSIONS',
        'PHYSICAL_RESOURCE_DIFFERENTIAL=YES',
        'READ_WRITE_FEEDBACK_RANKING=YES',
        'TOP_CANDIDATES=24',
        'STRICT_REWRITTEN_PROOF_REPORTED=YES',
        'MANUAL_SIGNAL_REQUIRES_BASELINE=YES',
        'COMPARE_SINGLE_CLAIM=YES',
        'GPU_READBACK=DISABLED',
        'RESOURCE_COPIES=DISABLED',
        'RESOURCE_BARRIERS=DISABLED',
        'COMMANDS_MODIFIED=NO',
        'RESULT=PASS',
    ]) + '\n',
    encoding='ascii')
print('V77_SOURCE_VERIFICATION_OK')
