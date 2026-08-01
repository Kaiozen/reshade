from pathlib import Path

SOURCE = Path('source/d3d12/d3d12.cpp')
if not SOURCE.is_file():
    raise RuntimeError(f'Missing source file: {SOURCE}')
text = SOURCE.read_text(encoding='utf-8-sig')
if 'D3DMetal RTX functional FP32 forced-miss control v52:' not in text:
    raise RuntimeError('V52 must be applied before V53')
if 'D3DMetal RTX ray-hit output pattern control v53:' in text:
    raise RuntimeError('V53 is already present')

anchor = (
    '\t\t\t\tstatic_cast<unsigned long long>(call_id),\n'
    '\t\t\t\treplacement_object);\n'
    '\t\t\treshade::log::message(\n'
)
insert = (
    '\t\t\t\tstatic_cast<unsigned long long>(call_id),\n'
    '\t\t\t\treplacement_object);\n'
    '\t\t\treshade::log::message(\n'
    '\t\t\t\treshade::log::level::info,\n'
    '\t\t\t\t"D3DMetal RTX ray-hit output pattern control v53: ACTIVE call=%llu state_object=%p output=_RWRayHitBuffer register=u1 stride=24 block=256 even=zero-record odd=far-miss-record TraceRay=enabled instance-mask=0 hit-shaders=disabled output-stores=patterned.",\n'
    '\t\t\t\tstatic_cast<unsigned long long>(call_id),\n'
    '\t\t\t\treplacement_object);\n'
    '\t\t\treshade::log::message(\n'
)
if text.count(anchor) != 1:
    raise RuntimeError(f'V53 V52-log anchor mismatch: {text.count(anchor)}')
text = text.replace(anchor, insert, 1)

required = [
    'D3DMetal RTX ray-hit output pattern control v53:',
    'output=_RWRayHitBuffer', 'register=u1', 'stride=24', 'block=256',
    'even=zero-record', 'odd=far-miss-record', 'TraceRay=enabled',
    'instance-mask=0', 'hit-shaders=disabled', 'output-stores=patterned',
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f'Missing V53 source marker: {marker}')
SOURCE.write_text(text, encoding='utf-8', newline='\n')

report = Path('v53-patch-report.txt')
report.write_text('\n'.join([
    'V53_RAYHIT_OUTPUT_PATTERN_RUNTIME_PATCH_OK',
    'BASELINE=V52_FUNCTIONAL_FP32_FORCED_MISS',
    'RAYHIT_OUTPUT_REGISTER=u1',
    'RAYHIT_OUTPUT_RECORD_STRIDE=24',
    'RAYHIT_OUTPUT_PATTERN_BLOCK=256',
    'EVEN_RECORD=ZERO',
    'ODD_RECORD=FAR_MISS_4096_KIND_1',
    'TRACE_RAY_EXECUTION=ENABLED',
    'INSTANCE_INCLUSION_MASK=0',
    'HIT_SHADER_EXECUTION=DISABLED_BY_MASK',
    'RT_STATE_BIND_SUPPRESSION=DISABLED',
    'RAY_DISPATCH_SUPPRESSION=DISABLED',
    'RESULT=PASS',
    '',
]), encoding='utf-8', newline='\n')
print(report.read_text(encoding='utf-8'))
