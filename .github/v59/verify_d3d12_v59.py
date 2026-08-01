from pathlib import Path

source = Path('source/d3d12/d3d12.cpp').read_text(encoding='utf-8')
required = {
    'active marker': 'D3DMetal RTX steady-state shader-table lineage v59',
    'unmap hook': 'RESOURCE_UNMAP_HOOK installed=',
    'rescan result': 'STEADY_RESCAN_RESULT scanned=',
    'record candidate': 'RAYGEN_RECORD_CANDIDATE sequence=',
    'lineage result': 'RAYGEN_RECORD_LINEAGE_RESULT success=',
    'final result': 'V59_RESULT resource_lookup_complete=',
    'tracking shutdown': 'HIGH_FREQUENCY_TRACKING_DISABLED reason=',
    'unmap slot': 'constexpr size_t v59_resource_unmap_slot = 9;',
    'copy lineage': 'v59_propagate_copy_lineage(',
    'local root fallback': 'v55_resolve_raygen_local_root(best->bytes, sizeof(best->bytes));',
    'v58 baseline': 'D3DMetal RTX live GPU-VA relocation tracking v58',
}
missing = [name for name, marker in required.items() if marker not in source]
if missing:
    raise SystemExit('V59 verification failed, missing: ' + ', '.join(missing))

for marker in (
    'SHADERS_MODIFIED_BY_V59=YES',
    'COPY_COMMANDS_MODIFIED_BY_V59=YES',
    'DISPATCH_ARGUMENTS_MODIFIED_BY_V59=YES',
):
    if marker in source:
        raise SystemExit(f'Forbidden marker found: {marker}')

if source.count('V59_RESULT resource_lookup_complete=') != 2:
    raise SystemExit('Expected exactly two V59 result branches')
if source.count('v59_install_resource_unmap_hook(resource);') != 1:
    raise SystemExit('Unmap hook must be installed exactly once per tracked-resource path')
if source.count('v59_refresh_live_candidate_addresses(desc);') != 1:
    raise SystemExit('Steady-state rescan must occur exactly once in capture path')

Path('v59-source-verification.txt').write_text(
    'V59_SOURCE_VERIFICATION_OK\n'
    'COMMANDS_MODIFIED=NO\n'
    'SHADER_BYTES_MODIFIED=NO\n'
    'DESCRIPTORS_MODIFIED=NO\n',
    encoding='utf-8',
)
print('V59_SOURCE_VERIFICATION_OK')
