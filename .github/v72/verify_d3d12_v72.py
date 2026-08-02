from pathlib import Path
source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')
required = [
    'D3DMetal RTX post-feedback lighting chain v72: ACTIVE',
    'source=v70-feedback-nonfeedback-outputs',
    'root0-offsets14,15',
    'max-depth=5',
    'POST_FEEDBACK_CHAIN_SEED',
    'POST_FEEDBACK_CHAIN_PASS',
    'POST_FEEDBACK_INPUT',
    'POST_FEEDBACK_OUTPUT',
    'POST_FEEDBACK_CHAIN_RESULT',
    'seed_offsets=14,15',
    'feedback_clearing=disabled',
    'v72_observe_post_feedback_event',
    'commands_modified=0',
]
missing = [m for m in required if m not in text]
if missing:
    raise SystemExit('ERROR: missing V72 source markers: ' + ', '.join(missing))
forbidden = [
    'D3DMetal RTX temporal feedback reset visual candidate v71: ACTIVE',
    'functional FP32 forced-miss control v52: ACTIVE',
    'ray-hit output pattern control v53: ACTIVE',
]
remaining = [m for m in forbidden if m in text]
if remaining:
    raise SystemExit('ERROR: forbidden active markers remain: ' + ', '.join(remaining))
start = text.find('void STDMETHODCALLTYPE v66_trace_dispatch(')
end = text.find('void STDMETHODCALLTYPE v66_trace_set_pipeline_state(', start)
if min(start, end) < 0:
    raise SystemExit('ERROR: dispatch hook range missing')
hook = text[start:end]
if 'v71_reset_history_feedback_before_dispatch(' in hook:
    raise SystemExit('ERROR: V71 clear call remains active in dispatch hook')
if hook.find('s_v66_original_dispatch(') > hook.find('v72_observe_post_feedback_event('):
    raise SystemExit('ERROR: V72 observation must run after the original dispatch')
if 'state.pipeline_state == seed_pipeline' not in text:
    raise SystemExit('ERROR: seed-pipeline skip is missing')
if 'v72_input_contains_resource(inputs, output.resource_id)' not in text:
    raise SystemExit('ERROR: in-place feedback exclusion is missing')
Path('v72-source-verification.txt').write_text(
    '\n'.join([
        'V72_SOURCE_VERIFICATION_OK',
        'SOURCE=V70_FEEDBACK_NONFEEDBACK_OUTPUTS',
        'SEED_DESCRIPTOR_OFFSETS=14,15',
        'MAX_DEPTH=5',
        'V71_FEEDBACK_CLEARING=DISABLED',
        'SEED_PIPELINE_SKIPPED=YES',
        'INPLACE_FEEDBACK_EXCLUDED_FROM_FRONTIER=YES',
        'GPU_READBACK=DISABLED',
        'RESOURCE_COPIES=DISABLED',
        'RESOURCE_BARRIERS=DISABLED',
        'COMMANDS_MODIFIED=NO',
        'RESULT=PASS',
    ]) + '\n', encoding='ascii')
print('V72_SOURCE_VERIFICATION_OK')
