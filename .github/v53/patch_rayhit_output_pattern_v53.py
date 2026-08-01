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

insert_anchor = '  %413 = call %dx.types.Handle @"dx.op.createHandleForLib.class.RWStructuredBuffer<RayIntersection_Data>"(i32 160, %"class.RWStructuredBuffer<RayIntersection_Data>" %9)  ; CreateHandleForLib(Resource)\n'
insert_block = (
    '  %v53_block = lshr i32 %19, 8\n'
    '  %v53_parity = and i32 %v53_block, 1\n'
    '  %v53_odd = icmp ne i32 %v53_parity, 0\n'
    '  %v53_distance = select i1 %v53_odd, i32 1166016512, i32 0\n'
    '  %v53_kind = select i1 %v53_odd, i32 1, i32 0\n'
    + insert_anchor
)

store0_old = '  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %413, i32 %19, i32 0, i32 %407, i32 %408, i32 %409, i32 %410, i8 15, i32 4)  ; RawBufferStore(uav,index,elementOffset,value0,value1,value2,value3,mask,alignment)\n'
store0_new = '  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %413, i32 %19, i32 0, i32 %v53_distance, i32 0, i32 %v53_kind, i32 0, i8 15, i32 4)  ; RawBufferStore(uav,index,elementOffset,value0,value1,value2,value3,mask,alignment)\n'
store1_old = '  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %413, i32 %19, i32 16, i32 %411, i32 undef, i32 undef, i32 undef, i8 1, i32 4)  ; RawBufferStore(uav,index,elementOffset,value0,value1,value2,value3,mask,alignment)\n'
store1_new = '  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %413, i32 %19, i32 16, i32 0, i32 undef, i32 undef, i32 undef, i8 1, i32 4)  ; RawBufferStore(uav,index,elementOffset,value0,value1,value2,value3,mask,alignment)\n'
store2_old = '  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %413, i32 %19, i32 20, i32 %412, i32 undef, i32 undef, i32 undef, i8 1, i32 4)  ; RawBufferStore(uav,index,elementOffset,value0,value1,value2,value3,mask,alignment)\n'
store2_new = '  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %413, i32 %19, i32 20, i32 0, i32 undef, i32 undef, i32 undef, i8 1, i32 4)  ; RawBufferStore(uav,index,elementOffset,value0,value1,value2,value3,mask,alignment)\n'

lines = [
    'V53_RAYHIT_OUTPUT_PATTERN_IR_PATCH_OK',
    'BASELINE=V52_REAL_FP32_FORCED_MISS',
    'TRACE_RAY_EXECUTION=ENABLED',
    'INSTANCE_INCLUSION_MASK=0',
    'OUTPUT_BUFFER=_RWRayHitBuffer_REGISTER_U1',
    'OUTPUT_RECORD_STRIDE=24',
    'PATTERN_BLOCK_SIZE=256_RAYS',
    'EVEN_RECORD=distance_bits_0_kind_0_rest_0',
    'ODD_RECORD=distance_bits_0x45800000_kind_1_rest_0',
    'ORIGINAL_RAYGEN_BOUNDS_CHECKS=PRESERVED',
]

for path in modules:
    if not path.is_file():
        raise RuntimeError(f'Missing V52 IR module: {path}')
    text = path.read_text(encoding='utf-8')
    if 'i32 %400, i32 0, i32 0, i32 1, i32 0' not in text:
        raise RuntimeError(f'{path.name}: V52 forced-miss TraceRay mask is missing')
    if text.count(insert_anchor) != 1:
        raise RuntimeError(f'{path.name}: output-handle anchor count={text.count(insert_anchor)}')
    for old, label in [(store0_old, 'store0'), (store1_old, 'store1'), (store2_old, 'store2')]:
        if text.count(old) != 1:
            raise RuntimeError(f'{path.name}: {label} count={text.count(old)}')
    if '%v53_block' in text:
        raise RuntimeError(f'{path.name}: V53 is already applied')

    original_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    patched = text.replace(insert_anchor, insert_block, 1)
    patched = patched.replace(store0_old, store0_new, 1)
    patched = patched.replace(store1_old, store1_new, 1)
    patched = patched.replace(store2_old, store2_new, 1)

    required = [
        '%v53_block = lshr i32 %19, 8',
        '%v53_parity = and i32 %v53_block, 1',
        '%v53_odd = icmp ne i32 %v53_parity, 0',
        '%v53_distance = select i1 %v53_odd, i32 1166016512, i32 0',
        '%v53_kind = select i1 %v53_odd, i32 1, i32 0',
        'i32 %v53_distance, i32 0, i32 %v53_kind, i32 0',
    ]
    for marker in required:
        if marker not in patched:
            raise RuntimeError(f'{path.name}: missing patched marker: {marker}')
    for stale in [
        'i32 %407, i32 %408, i32 %409, i32 %410',
        'i32 16, i32 %411',
        'i32 20, i32 %412',
    ]:
        if stale in patched:
            raise RuntimeError(f'{path.name}: original output value remains: {stale}')

    trace_calls = [line for line in patched.splitlines() if 'call void @dx.op.traceRay.struct.RayIntersection_RT' in line]
    if len(trace_calls) != 1 or 'i32 %400, i32 0, i32 0, i32 1, i32 0' not in trace_calls[0]:
        raise RuntimeError(f'{path.name}: forced-miss TraceRay call changed unexpectedly')
    if patched.count('call void @dx.op.rawBufferStore.i32') != 3:
        raise RuntimeError(f'{path.name}: expected three ExecuteTrace output stores')

    path.write_text(patched, encoding='utf-8', newline='\n')
    patched_hash = hashlib.sha256(patched.encode('utf-8')).hexdigest()
    lines.append(f'MODULE={path.name} ORIGINAL_SHA256={original_hash} PATCHED_SHA256={patched_hash} TRACE_CALLS=1 OUTPUT_STORE_CALLS=3')

lines += ['RESULT=PASS', '']
report.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
print(report.read_text(encoding='utf-8'))
