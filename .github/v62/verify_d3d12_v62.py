from pathlib import Path

source = Path('source/d3d12/d3d12.cpp').read_text(encoding='utf-8')
report = Path('v62-patch-report.txt').read_text(encoding='utf-8')

required_source = [
    'D3DMetal RTX ray-hit output forensics v62: FORENSIC_HOOKS_ENABLED',
    'D3DMetal RTX ray-hit output forensics v62: U1_TARGET_READY',
    'D3DMetal RTX ray-hit output forensics v62: U1_CAPTURE_RECORDED',
    'D3DMetal RTX ray-hit output forensics v62: U1_QUEUE_SUBMITTED',
    'D3DMetal RTX ray-hit output forensics v62: U1_RECORD',
    'D3DMetal RTX ray-hit output forensics v62: U1_BLOCK_SUMMARY',
    'D3DMetal RTX ray-hit output forensics v62: U1_READBACK_RESULT',
    'v61_rewritten_steady_state_candidate',
    'v62_try_capture_u1_output',
    'v62_on_execute_command_lists',
    'v38_install_create_command_queue_hook(device)',
    'v39_install_resource_hooks(device)',
    'v55_install_descriptor_hooks(device)',
    'v57_install_resource_map_hook(resource)',
    'v59_install_resource_unmap_hook(resource)',
    's_v59_high_frequency_tracking_enabled = true',
    'commands_modified=copy-after-dispatch-restored-uav-state',
]
for marker in required_source:
    if marker not in source:
        raise RuntimeError(f'Missing V62 source marker: {marker}')

for forbidden in [
    'v58_install_gpu_va_hook(resource);',
    'v57_trace_copy_buffer_region));',
]:
    if forbidden in source:
        raise RuntimeError(f'Forbidden high-frequency V62 path is active: {forbidden}')

required_report = [
    'V62_RAYHIT_OUTPUT_FORENSICS_PATCH_OK',
    'STRICT_REWRITTEN_PIPELINE_REQUIRED=YES',
    'U1_TOTAL_SAMPLED_RECORDS=1280',
    'U1_COPY_OCCURS=AFTER_GENUINE_REWRITTEN_DISPATCH',
    'RESULT=PASS',
]
for marker in required_report:
    if marker not in report:
        raise RuntimeError(f'Missing V62 report marker: {marker}')

print('V62_SOURCE_VERIFICATION_OK')
print('STRICT_REWRITTEN_PIPELINE_REQUIRED=YES')
print('U1_OUTPUT_FORENSICS=ENABLED')
print('U1_SAMPLED_RECORDS=1280')
print('RESULT=PASS')
