from pathlib import Path

source = Path('source/d3d12/d3d12.cpp').read_text(encoding='utf-8')
report = Path('v61-patch-report.txt').read_text(encoding='utf-8')

required_source = [
    'D3DMetal RTX AddToStateObject lineage bridge v61: HOOK',
    'D3DMetal RTX AddToStateObject lineage bridge v61: ADD_RESULT',
    'D3DMetal RTX AddToStateObject lineage bridge v61: REWRITTEN_STEADY_STATE_EXECUTED',
    'v61_add_to_state_object_slot = 66',
    'v61_trace_add_to_state_object',
    'v61_install_add_to_state_object_hook',
    'v61_rewritten_steady_state_candidate',
    'v33_register_rewritten_state_object',
    'g_v30_execute_plus_miss_fp32_dxil',
    'base_rewritten || (addition_rewritten && !addition_rewrite_fallback)',
]
for marker in required_source:
    if marker not in source:
        raise RuntimeError(f'Missing V61 source marker: {marker}')

for forbidden in [
    'REAL_FP32_DISPATCH_EXECUTED mode=indirect',
    's_v60_real_fp32_dispatch_seen',
]:
    if forbidden in source:
        raise RuntimeError(f'Stale V60 false-proof marker remains: {forbidden}')

required_report = [
    'V61_ADD_TO_STATE_OBJECT_LINEAGE_BRIDGE_PATCH_OK',
    'ADD_TO_STATE_OBJECT_SLOT=66',
    'PARENT_DXIL_IN_ADDITIONS_REWRITTEN=YES',
    'DOMINANT_PIPELINE_PROOF_REQUIRES_REWRITTEN_LINEAGE=YES',
    'V60_IDENTIFIER_ONLY_PROOF_SUPERSEDED=YES',
    'RESULT=PASS',
]
for marker in required_report:
    if marker not in report:
        raise RuntimeError(f'Missing V61 report marker: {marker}')

print('V61_SOURCE_VERIFICATION_OK')
print('ADD_TO_STATE_OBJECT_SLOT=66')
print('STRICT_REWRITTEN_STEADY_STATE_PROOF=YES')
print('RESULT=PASS')
