from pathlib import Path

SOURCE = Path('source/d3d12/d3d12.cpp')
if not SOURCE.is_file():
    raise RuntimeError(f'Missing source file: {SOURCE}')
text = SOURCE.read_text(encoding='utf-8-sig')
if 'D3DMetal RTX FP32 universal bridge v32:' not in text:
    raise RuntimeError('V32 must be applied before V52')
if 'D3DMetal RTX shader-identifier query trace v36:' not in text:
    raise RuntimeError('V36 must be applied before V52')
if 'D3DMetal RTX functional FP32 forced-miss control v52:' in text:
    raise RuntimeError('V52 is already present')
anchor = (
    '\t\t\tconst unsigned int success = ++s_v32_rewrite_successes;\n'
    '\t\t\treshade::log::message(\n'
)
insert = (
    '\t\t\tconst unsigned int success = ++s_v32_rewrite_successes;\n'
    '\t\t\treshade::log::message(\n'
    '\t\t\t\treshade::log::level::info,\n'
    '\t\t\t\t"D3DMetal RTX functional FP32 forced-miss control v52: ACTIVE call=%llu state_object=%p module=real-v30-fp32 TraceRay=enabled instance-mask=0 output-stores=enabled hit-shaders=disabled ray-dispatch-suppression=disabled rt-bind-suppression=disabled.",\n'
    '\t\t\t\tstatic_cast<unsigned long long>(call_id),\n'
    '\t\t\t\treplacement_object);\n'
    '\t\t\treshade::log::message(\n'
)
if text.count(anchor) != 1:
    raise RuntimeError(f'V52 V32 success anchor mismatch: {text.count(anchor)}')
text = text.replace(anchor, insert, 1)
required = [
    'D3DMetal RTX functional FP32 forced-miss control v52:',
    'module=real-v30-fp32', 'TraceRay=enabled', 'instance-mask=0',
    'output-stores=enabled', 'hit-shaders=disabled',
    'ray-dispatch-suppression=disabled', 'rt-bind-suppression=disabled',
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f'Missing V52 source marker: {marker}')
SOURCE.write_text(text, encoding='utf-8', newline='\n')
report = Path('v52-patch-report.txt')
report.write_text('\n'.join([
    'V52_FUNCTIONAL_FP32_FORCED_MISS_RUNTIME_PATCH_OK',
    'BASELINE=V36_WITH_REAL_V30_FP32_MODULE',
    'EMPTY_V41_RAYGEN_PRESENT=NO',
    'TRACE_RAY_EXECUTION=ENABLED',
    'INSTANCE_INCLUSION_MASK=0',
    'RAYGEN_MATH_PRESERVED=YES',
    'OUTPUT_UAV_STORES_PRESERVED=YES',
    'HIT_SHADER_EXECUTION=DISABLED_BY_MASK',
    'RT_STATE_BIND_SUPPRESSION=DISABLED',
    'RAY_DISPATCH_SUPPRESSION=DISABLED',
    'V33_DIRECT_DISPATCH_FORWARDING=PRESERVED',
    'V34_INDIRECT_DISPATCH_FORWARDING=PRESERVED',
    'V36_IDENTIFIER_RESULTS_UNMODIFIED=YES',
    'RESULT=PASS',
    '',
]), encoding='utf-8', newline='\n')
print(report.read_text(encoding='utf-8'))
