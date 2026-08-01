from pathlib import Path
import argparse
import hashlib

parser = argparse.ArgumentParser()
parser.add_argument('--ir-dir', required=True)
parser.add_argument('--report', required=True)
args = parser.parse_args()

ir_dir = Path(args.ir_dir)
report = Path(args.report)
modules = [
    ir_dir / 'execute-trace-fp32.ll',
    ir_dir / 'execute-plus-miss-fp32.ll',
]
needle = 'i32 %400, i32 %399, i32 0, i32 1, i32 0'
replacement = 'i32 %400, i32 0, i32 0, i32 1, i32 0'
lines = [
    'V52_FUNCTIONAL_FP32_FORCED_MISS_IR_PATCH_OK',
    'BASE_MODULE=REAL_V30_FP32_EXECUTETRACE',
    'TRACE_RAY_EXECUTION=ENABLED',
    'RAYGEN_MATH=ENABLED',
    'OUTPUT_UAV_STORES=ENABLED',
    'INSTANCE_INCLUSION_MASK=0',
    'HIT_SHADER_EXECUTION=DISABLED_BY_MASK',
]
for path in modules:
    if not path.is_file():
        raise RuntimeError(f'Missing V30 IR module: {path}')
    text = path.read_text(encoding='utf-8')
    if text.count(needle) != 1:
        raise RuntimeError(f'{path.name}: expected one TraceRay argument sequence, found {text.count(needle)}')
    if text.count('dx.op.traceRay.struct.RayIntersection_RT') < 2:
        raise RuntimeError(f'{path.name}: real TraceRay declaration/call is missing')
    if text.count('dx.op.rawBufferStore.i32') < 4:
        raise RuntimeError(f'{path.name}: real output UAV stores are missing')
    if 'define void @"\\01?ExecuteTrace@@YAXXZ"()' not in text:
        raise RuntimeError(f'{path.name}: ExecuteTrace definition is missing')
    if 'fmul fast double' in text or 'fptrunc double' in text or 'to double' in text:
        raise RuntimeError(f'{path.name}: FP64 instructions unexpectedly remain')
    original_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    patched = text.replace(needle, replacement, 1)
    trace_lines = [line for line in patched.splitlines() if 'call void @dx.op.traceRay.struct.RayIntersection_RT' in line]
    if len(trace_lines) != 1:
        raise RuntimeError(f'{path.name}: expected one TraceRay call, found {len(trace_lines)}')
    if replacement not in trace_lines[0] or 'i32 %399' in trace_lines[0]:
        raise RuntimeError(f'{path.name}: forced-miss TraceRay call was not produced')
    path.write_text(patched, encoding='utf-8', newline='\n')
    patched_hash = hashlib.sha256(patched.encode('utf-8')).hexdigest()
    lines.append(f'MODULE={path.name} ORIGINAL_SHA256={original_hash} PATCHED_SHA256={patched_hash} TRACE_CALLS=1 OUTPUT_STORE_CALLS=3')
lines.append('RESULT=PASS')
report.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
print(report.read_text(encoding='utf-8'))
