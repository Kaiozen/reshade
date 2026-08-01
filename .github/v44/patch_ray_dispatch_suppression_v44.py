from pathlib import Path

SOURCE = Path('source/d3d12/d3d12.cpp')
if not SOURCE.is_file():
    raise RuntimeError(f'Missing source file: {SOURCE}')

text = SOURCE.read_text(encoding='utf-8-sig')
if 'D3DMetal RTX no-output raygen control v41:' not in text:
    raise RuntimeError('V41 must be applied before V44')
if 'D3DMetal RTX no-output inheritance census v43:' not in text:
    raise RuntimeError('V43 must be applied before V44')
if 'D3DMetal RTX ray-dispatch suppression control v44:' in text:
    raise RuntimeError('V44 is already present')

globals_anchor = '\tstatic std::atomic<uint64_t> s_v43_total_indirect_rays = 0;\n'
if text.count(globals_anchor) != 1:
    raise RuntimeError(f'V44 globals anchor mismatch: {text.count(globals_anchor)}')

globals_insert = r'''
\tstatic std::atomic<uint64_t> s_v44_suppressed_direct_rays = 0;
\tstatic std::atomic<uint64_t> s_v44_suppressed_indirect_rays = 0;
\tstatic std::once_flag s_v44_active_log_once;
'''
text = text.replace(globals_anchor, globals_anchor + globals_insert, 1)

direct_anchor = (
    '\t\tif (s_v33_original_dispatch_rays != nullptr)\n'
    '\t\t\ts_v33_original_dispatch_rays(command_list, desc);\n'
    '\t}\n'
)
if text.count(direct_anchor) != 1:
    raise RuntimeError(f'V44 direct DispatchRays anchor mismatch: {text.count(direct_anchor)}')

direct_replacement = r'''\t\tstd::call_once(
\t\t\ts_v44_active_log_once,
\t\t\t[]()
\t\t\t{
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
\t\t\t\t\t"D3DMetal RTX ray-dispatch suppression control v44: ACTIVE direct-dispatch-rays-suppressed=1 indirect-dispatch-rays-suppressed=1 non-ray-indirect-commands-preserved=1.");
\t\t\t});

\t\tconst uint64_t v44_suppressed_direct_index =
\t\t\t++s_v44_suppressed_direct_rays;
\t\treshade::log::message(
\t\t\treshade::log::level::info,
\t\t\t"D3DMetal RTX ray-dispatch suppression control v44: SUPPRESS_DIRECT suppressed_direct_index=%llu command_list=%p desc=%p.",
\t\t\tstatic_cast<unsigned long long>(v44_suppressed_direct_index),
\t\t\tcommand_list,
\t\t\tdesc);
\t\treturn;
\t}
'''
text = text.replace(direct_anchor, direct_replacement, 1)

indirect_anchor = (
    '\t\tif (s_v34_original_execute_indirect != nullptr)\n'
    '\t\t\ts_v34_original_execute_indirect(\n'
    '\t\t\t\tcommand_list,\n'
    '\t\t\t\tcommand_signature,\n'
    '\t\t\t\tmax_command_count,\n'
    '\t\t\t\targument_buffer,\n'
    '\t\t\t\targument_buffer_offset,\n'
    '\t\t\t\tcount_buffer,\n'
    '\t\t\t\tcount_buffer_offset);\n'
    '\t}\n'
)
if text.count(indirect_anchor) != 1:
    raise RuntimeError(f'V44 ExecuteIndirect anchor mismatch: {text.count(indirect_anchor)}')

indirect_replacement = r'''\t\tif (dispatch_rays)
\t\t{
\t\t\tstd::call_once(
\t\t\t\ts_v44_active_log_once,
\t\t\t\t[]()
\t\t\t\t{
\t\t\t\t\treshade::log::message(
\t\t\t\t\t\treshade::log::level::info,
\t\t\t\t\t\t"D3DMetal RTX ray-dispatch suppression control v44: ACTIVE direct-dispatch-rays-suppressed=1 indirect-dispatch-rays-suppressed=1 non-ray-indirect-commands-preserved=1.");
\t\t\t\t});

\t\t\tconst uint64_t v44_suppressed_indirect_index =
\t\t\t\t++s_v44_suppressed_indirect_rays;
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::info,
\t\t\t\t"D3DMetal RTX ray-dispatch suppression control v44: SUPPRESS_INDIRECT suppressed_indirect_index=%llu command_list=%p signature=%p max_count=%u argument_buffer=%p argument_offset=%llu count_buffer=%p count_offset=%llu.",
\t\t\t\tstatic_cast<unsigned long long>(v44_suppressed_indirect_index),
\t\t\t\tcommand_list,
\t\t\t\tcommand_signature,
\t\t\t\tmax_command_count,
\t\t\t\targument_buffer,
\t\t\t\tstatic_cast<unsigned long long>(argument_buffer_offset),
\t\t\t\tcount_buffer,
\t\t\t\tstatic_cast<unsigned long long>(count_buffer_offset));
\t\t\treturn;
\t\t}

\t\tif (s_v34_original_execute_indirect != nullptr)
\t\t\ts_v34_original_execute_indirect(
\t\t\t\tcommand_list,
\t\t\t\tcommand_signature,
\t\t\t\tmax_command_count,
\t\t\t\targument_buffer,
\t\t\t\targument_buffer_offset,
\t\t\t\tcount_buffer,
\t\t\t\tcount_buffer_offset);
\t}
'''
text = text.replace(indirect_anchor, indirect_replacement, 1)

for marker in [
    'D3DMetal RTX ray-dispatch suppression control v44: ACTIVE',
    'SUPPRESS_DIRECT suppressed_direct_index=',
    'SUPPRESS_INDIRECT suppressed_indirect_index=',
    'direct-dispatch-rays-suppressed=1',
    'indirect-dispatch-rays-suppressed=1',
    'non-ray-indirect-commands-preserved=1',
]:
    if marker not in text:
        raise RuntimeError(f'Missing V44 source marker: {marker}')

if text.count('s_v34_original_execute_indirect(') != 1:
    raise RuntimeError('V44 expected one remaining original ExecuteIndirect call for non-ray commands')

SOURCE.write_text(text, encoding='utf-8', newline='\n')

report = Path('v44-patch-report.txt')
report.write_text('\n'.join([
    'V44_RAY_DISPATCH_SUPPRESSION_CONTROL_PATCH_OK',
    'V41_MINIMAL_NO_OUTPUT_RAYGEN_PRESERVED=YES',
    'V43_INHERITANCE_CENSUS_PRESERVED=YES',
    'DIRECT_DISPATCH_RAYS_SUPPRESSED=YES',
    'INDIRECT_DISPATCH_RAYS_SUPPRESSED=YES',
    'NON_RAY_EXECUTE_INDIRECT_PRESERVED=YES',
    'SHADER_BYTES_MODIFIED_BY_V44=NO',
    'STATE_OBJECTS_MODIFIED_BY_V44=NO',
    'SHADER_TABLES_MODIFIED_BY_V44=NO',
    'DISPATCH_ARGUMENT_BUFFERS_MODIFIED_BY_V44=NO',
    'CONTROL_FLOW_CHANGE=SKIP_RAY_DISPATCH_COMMAND_RECORDING',
    'RESULT=PASS',
    '',
]), encoding='utf-8', newline='\n')
print(report.read_text(encoding='utf-8'))
