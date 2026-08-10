from pathlib import Path
import sys, re, hashlib

build = Path(sys.argv[1])
out = Path(sys.argv[2])
manifest = Path(sys.argv[3])

# RenoDX emits one of:
#   0x12345678.cso       for version-specific HLSL (SM6 etc.)
#   0x12345678_dx11.cso  for 5_x D3D11
#   0x12345678_dx12.cso  for 5_x D3D12
# We are a D3D12-only transplant, so use generic CSO when present, otherwise
# explicitly use the _dx12 variant. Never use _dx11.
embed_dirs = [d for d in build.rglob('embed') if d.is_dir() and d.parent.name == 'zenless-zone-zero.include']
if len(embed_dirs) != 1:
    raise SystemExit(f'ZZZ_EMBED_DIRECTORY_COUNT={len(embed_dirs)}')
embed = embed_dirs[0]
print(f'V24HDR_ZZZ_EMBED_DIR={embed}')
all_cso = sorted(embed.glob('*.cso'))
by_crc = {}
source_kind = {}
for p in all_cso:
    m = re.fullmatch(r'(0x[0-9A-Fa-f]{8})(?:_(dx11|dx12))?\.cso', p.name)
    if not m:
        continue
    crc = int(m.group(1), 16)
    suffix = m.group(2)
    if suffix == 'dx11':
        continue
    priority = 2 if suffix == 'dx12' else 1
    old = by_crc.get(crc)
    if old is None or priority > old[0]:
        by_crc[crc] = (priority, p)
        source_kind[crc] = 'DX12_SM5X' if suffix == 'dx12' else 'GENERIC_DX12'
    elif priority == old[0] and old[1].resolve() != p.resolve():
        raise SystemExit(f'DUPLICATE_SHADER_CRC_SAME_PRIORITY=0x{crc:08X} old={old[1]} new={p}')

if len(by_crc) < 40:
    raise SystemExit(f'V24HDR_SHADER_COUNT_TOO_LOW={len(by_crc)}')

entries = []
chunks = []
manifest_lines = []
for crc in sorted(by_crc):
    p = by_crc[crc][1]
    data = p.read_bytes()
    if len(data) < 64:
        raise SystemExit(f'SHADER_TOO_SMALL={p}')
    # These string checks are supplementary. The authoritative gate is the
    # source bake check before compilation.
    if b'injected_buffer' in data or b'space50' in data:
        raise SystemExit(f'INJECTION_BINDING_SURVIVED={p.name}')
    name = f'v24hdr_shader_{crc:08X}'
    body = []
    for off in range(0, len(data), 20):
        body.append('    ' + ','.join(f'0x{x:02X}' for x in data[off:off + 20]) + ',')
    chunks.append(
        f'alignas(16) static const uint8_t {name}[] = {{\n' +
        '\n'.join(body) + '\n};\n'
    )
    entries.append((crc, name, len(data)))
    manifest_lines.append(
        f'0x{crc:08X} kind={source_kind[crc]} source={p.name} size={len(data)} '
        f'sha256={hashlib.sha256(data).hexdigest()}'
    )

header = '''#pragma once
#include <cstdint>
#include <cstddef>
struct v24hdr_shader_blob { uint32_t crc32; const uint8_t *data; size_t size; };
'''
header += '\n'.join(chunks)
header += '\nstatic const v24hdr_shader_blob g_v24hdr_shaders[] = {\n'
header += ''.join(f'    {{0x{c:08X}u, {n}, {z}u}},\n' for c, n, z in entries)
header += '};\n'
header += 'static constexpr size_t g_v24hdr_shader_count = sizeof(g_v24hdr_shaders) / sizeof(g_v24hdr_shaders[0]);\n'

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(header, encoding='utf-8', newline='\n')
manifest.write_text(
    '\n'.join([
        f'V24HDR_SHADER_COUNT={len(entries)}',
        'RENODX_COMMIT=ddd6d593ed70eb1a2357ae79e4142c3877f9243e',
        'TARGET_API=D3D12',
        f'ZZZ_EMBED_DIRECTORY={embed}',
        'DX11_SHADER_VARIANTS=EXCLUDED',
        'DX12_SM5X_VARIANTS=PREFERRED',
        'INJECTION_BUFFER=ABSENT',
        'B13_SPACE50=ABSENT',
    ] + manifest_lines) + '\n',
    encoding='utf-8',
    newline='\n',
)
print(f'V24HDR_SHADER_COUNT={len(entries)}')
print('V24HDR_DX11_VARIANTS_EXCLUDED=PASS')
print('V24HDR_DX12_SM5X_SELECTION=PASS')
print('V24HDR_SHADER_HEADER_GENERATION=PASS')
