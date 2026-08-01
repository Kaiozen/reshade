from pathlib import Path

SOURCE = Path('source/d3d12/d3d12.cpp')
if not SOURCE.is_file():
    raise RuntimeError(f'Missing source file: {SOURCE}')

text = SOURCE.read_text(encoding='utf-8-sig')
if 'D3DMetal RTX no-output raygen control v41:' not in text:
    raise RuntimeError('V41 must be applied before V45')
if 'D3DMetal RTX no-output inheritance census v43:' not in text:
    raise RuntimeError('V43 must be applied before V45')
if 'D3DMetal RTX ray-dispatch suppression control v44:' not in text:
    raise RuntimeError('V44 must be applied before V45')
if 'D3DMetal RTX RT-state bind suppression control v45:' in text:
    raise RuntimeError('V45 is already present')

globals_anchor = '\tstatic std::once_flag s_v44_active_log_once;\n'
if text.count(globals_anchor) != 1:
    raise RuntimeError(f'V45 globals anchor mismatch: {text.count(globals_anchor)}')

globals_insert = '''
\tstatic std::atomic<uint64_t> s_v45_suppressed_state_binds = 0;
\tstatic std::once_flag s_v45_active_log_once;
'''
text = text.replace(globals_anchor, globals_anchor + globals_insert, 1)

bind_anchor = (
    '\t\tif (s_v33_original_set_pipeline_state1 != nullptr)\n'
    '\t\t\ts_v33_original_set_pipeline_state1(command_list, state_object);\n\n'
    '\t\tv43_bind_pipeline(command_list, v43_pipeline_id, state_object);\n'
)
if text.count(bind_anchor) != 1:
    raise RuntimeError(f'V45 SetPipelineState1 anchor mismatch: {text.count(bind_anchor)}')

bind_replacement = '''\t\tstd::call_once(
\t\t\ts_v45_active_log_once,
\t\t\t[]()
\t\t\t{
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
\t\t\t\t\t"D3DMetal RTX RT-state bind suppression control v45: ACTIVE set-pipeline-state1-suppressed=1 ray-dispatch-suppression-v44-preserved=1 non-rt-command-recording-preserved=1.");
\t\t\t});

\t\tconst uint64_t v45_suppressed_bind_index =
\t\t\t++s_v45_suppressed_state_binds;
\t\treshade::log::message(
\t\t\treshade::log::level::info,
\t\t\t"D3DMetal RTX RT-state bind suppression control v45: SUPPRESS_BIND suppressed_bind_index=%llu command_list=%p state_object=%p pipeline_id=%llu rewritten=%u rewritten_state_call=%llu.",
\t\t\tstatic_cast<unsigned long long>(v45_suppressed_bind_index),
\t\t\tcommand_list,
\t\t\tstate_object,
\t\t\tstatic_cast<unsigned long long>(v43_pipeline_id),
\t\t\trewritten ? 1u : 0u,
\t\t\tstatic_cast<unsigned long long>(state_call));

\t\t// Keep V43's attempted-bind census, but do not forward SetPipelineState1
\t\t// to D3DMetal. V44 independently suppresses every ray dispatch.
\t\tv43_bind_pipeline(command_list, v43_pipeline_id, state_object);
'''
text = text.replace(bind_anchor, bind_replacement, 1)

for marker in [
    'D3DMetal RTX RT-state bind suppression control v45: ACTIVE',
    'SUPPRESS_BIND suppressed_bind_index=',
    'set-pipeline-state1-suppressed=1',
    'ray-dispatch-suppression-v44-preserved=1',
    'non-rt-command-recording-preserved=1',
]:
    if marker not in text:
        raise RuntimeError(f'Missing V45 source marker: {marker}')

if 's_v33_original_set_pipeline_state1(command_list, state_object);' in text:
    raise RuntimeError('V45 left a SetPipelineState1 forward call in the hooked path')

# Guard against the literal-tab generator failure seen in the first V44 build.
for forbidden in ('\\tstatic std::atomic', '\\t\\tstd::call_once', '\\t\\tv43_bind_pipeline'):
    if forbidden in text:
        raise RuntimeError(f'V45 emitted a literal tab escape into C++ source: {forbidden}')

SOURCE.write_text(text, encoding='utf-8', newline='\n')

report = Path('v45-patch-report.txt')
report.write_text('\n'.join([
    'V45_RT_STATE_BIND_SUPPRESSION_CONTROL_PATCH_OK',
    'V41_MINIMAL_NO_OUTPUT_RAYGEN_PRESERVED=YES',
    'V43_ATTEMPTED_BIND_CENSUS_PRESERVED=YES',
    'V44_ALL_RAY_DISPATCH_SUPPRESSION_PRESERVED=YES',
    'SET_PIPELINE_STATE1_SUPPRESSED=YES',
    'NON_RT_COMMAND_RECORDING_PRESERVED=YES',
    'STATE_OBJECT_CREATION_PRESERVED=YES',
    'SHADER_IDENTIFIER_QUERIES_PRESERVED=YES',
    'SHADER_TABLES_MODIFIED_BY_V45=NO',
    'DISPATCH_ARGUMENT_BUFFERS_MODIFIED_BY_V45=NO',
    'LITERAL_TAB_ESCAPES_IN_CPP=NO',
    'CONTROL_FLOW_CHANGE=SKIP_RT_STATE_OBJECT_BIND_RECORDING',
    'RESULT=PASS',
    '',
]), encoding='utf-8', newline='\n')
print(report.read_text(encoding='utf-8'))
