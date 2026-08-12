from pathlib import Path
import sys, re, hashlib, struct, zlib

build = Path(sys.argv[1])
out = Path(sys.argv[2])
manifest = Path(sys.argv[3])

embed_dirs = [d for d in build.rglob('embed') if d.is_dir() and d.parent.name == 'zenless-zone-zero.include']
if len(embed_dirs) != 1:
    raise SystemExit(f'ZZZ_EMBED_DIRECTORY_COUNT={len(embed_dirs)}')
embed = embed_dirs[0]
print(f'V24HDR_ZZZ_EMBED_DIR={embed}')

proxy_vs_path = embed / 'swap_chain_proxy_vertex_shader_dx12.cso'
proxy_ps_path = embed / 'swap_chain_proxy_pixel_shader_dx12.cso'
if not proxy_vs_path.is_file():
    raise SystemExit(f'HOTFIX13_SWAPCHAIN_PROXY_VS_MISSING={proxy_vs_path}')
if not proxy_ps_path.is_file():
    raise SystemExit(f'HOTFIX13_SWAPCHAIN_PROXY_PS_MISSING={proxy_ps_path}')
proxy_vs = proxy_vs_path.read_bytes()
proxy_ps = proxy_ps_path.read_bytes()
if len(proxy_vs) < 64 or len(proxy_ps) < 64:
    raise SystemExit('HOTFIX13_SWAPCHAIN_PROXY_SHADER_TOO_SMALL')

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

def u32(data, off):
    return struct.unpack_from('<I', data, off)[0]

def dxbc_signature_fingerprint(data):
    if len(data) < 32 or data[:4] != b'DXBC':
        return (0, 0, 0, 0, 0)
    total = u32(data, 24)
    count = u32(data, 28)
    if total > len(data) or count > 128 or 32 + count * 4 > len(data):
        return (0, 0, 0, 0, 0)

    in_crc = out_crc = in_size = out_size = 0
    chunk_mask = 0
    for i in range(count):
        off = u32(data, 32 + i * 4)
        if off + 8 > total:
            continue
        tag = data[off:off+4]
        size = u32(data, off + 4)
        if off + 8 + size > total:
            continue
        payload = data[off+8:off+8+size]
        if tag in (b'ISGN', b'ISG1'):
            in_crc = zlib.crc32(payload) & 0xffffffff
            in_size = size
            chunk_mask |= 1
        elif tag in (b'OSGN', b'OSG1', b'OSG5'):
            out_crc = zlib.crc32(payload) & 0xffffffff
            out_size = size
            chunk_mask |= 2

    return (in_crc, out_crc, in_size, out_size, chunk_mask)

entries = []
chunks = []
manifest_lines = []
critical = {
    0x011329C3,0x06D90AA2,0x0A7685EC,0x0BD47EBA,
    0x14317D70,0x1E1BB7CB,0x1E59D729,0x1E69D07D,
    0x21DEC524,0x2862DFB8,0x3978BC7F,0x5DD31DE1,
    0x5DFB8E85,0x617125FB,0x76860566,0x8FF706D2,
    0x92AA9125,0x97A92288,0xA5BD36B0,0xAFC76B07,
    0xCC759B21,0xD09F8758,0xE9DDCE66,0xF432415B,
}
critical_fp_groups = {}

for crc in sorted(by_crc):
    p = by_crc[crc][1]
    data = p.read_bytes()
    if len(data) < 64:
        raise SystemExit(f'SHADER_TOO_SMALL={p}')
    if b'injected_buffer' in data or b'space50' in data:
        raise SystemExit(f'INJECTION_BINDING_SURVIVED={p.name}')

    in_crc, out_crc, in_size, out_size, chunk_mask = dxbc_signature_fingerprint(data)

    name = f'v24hdr_shader_{crc:08X}'
    body = []
    for off in range(0, len(data), 20):
        body.append('    ' + ','.join(f'0x{x:02X}' for x in data[off:off + 20]) + ',')
    chunks.append(
        f'alignas(16) static const uint8_t {name}[] = {{\n' +
        '\n'.join(body) + '\n};\n'
    )
    entries.append((crc, name, len(data), in_crc, out_crc, in_size, out_size, chunk_mask))
    manifest_lines.append(
        f'0x{crc:08X} kind={source_kind[crc]} source={p.name} size={len(data)} '
        f'sha256={hashlib.sha256(data).hexdigest()} '
        f'isig_crc=0x{in_crc:08X} isig_size={in_size} '
        f'osig_crc=0x{out_crc:08X} osig_size={out_size} sigmask={chunk_mask}'
    )
    if crc in critical and in_crc and out_crc:
        key = (len(data), in_crc, in_size, out_crc, out_size)
        critical_fp_groups.setdefault(key, []).append(crc)

unique_critical = sum(1 for v in critical_fp_groups.values() if len(v) == 1)
ambiguous_critical = sum(1 for v in critical_fp_groups.values() if len(v) > 1)

def emit_array(name, data):
    body = []
    for off in range(0, len(data), 20):
        body.append('    ' + ','.join(f'0x{x:02X}' for x in data[off:off + 20]) + ',')
    return f'alignas(16) static const uint8_t {name}[] = {{\n' + '\n'.join(body) + '\n};\n'

proxy_arrays = (
    emit_array('g_v24hdr_hotfix12_proxy_vs', proxy_vs) +
    emit_array('g_v24hdr_hotfix12_proxy_ps', proxy_ps) +
    f'static constexpr size_t g_v24hdr_hotfix12_proxy_vs_size = {len(proxy_vs)}u;\n' +
    f'static constexpr size_t g_v24hdr_hotfix12_proxy_ps_size = {len(proxy_ps)}u;\n'
)

header = """#pragma once
#include <cstdint>
#include <cstddef>
struct v24hdr_shader_blob {
    uint32_t crc32;
    const uint8_t *data;
    size_t size;
    uint32_t input_sig_crc32;
    uint32_t output_sig_crc32;
    uint32_t input_sig_size;
    uint32_t output_sig_size;
    uint32_t signature_mask;
};
"""
header += '\n'.join(chunks)
header += '\nstatic const v24hdr_shader_blob g_v24hdr_shaders[] = {\n'
header += ''.join(
    f'    {{0x{c:08X}u, {n}, {z}u, 0x{ic:08X}u, 0x{oc:08X}u, {isz}u, {osz}u, {mask}u}},\n'
    for c, n, z, ic, oc, isz, osz, mask in entries
)
header += '};\n'
header += 'static constexpr size_t g_v24hdr_shader_count = sizeof(g_v24hdr_shaders) / sizeof(g_v24hdr_shaders[0]);\n'

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(header, encoding='utf-8', newline='\n')
proxy_out = out.parent.parent / 'dxgi' / 'v24hdr_swapchain_proxy_shaders.hpp'
proxy_out.parent.mkdir(parents=True, exist_ok=True)
proxy_out.write_text(
    '#pragma once\n#include <cstdint>\n#include <cstddef>\n' + proxy_arrays,
    encoding='utf-8',
    newline='\n',
)
print(f'HOTFIX13_PROXY_HEADER={proxy_out}')
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
        'ADAPTIVE_FINGERPRINTS=DXBC_SIGNATURE_PLUS_EXACT_SIZE',
        f'ADAPTIVE_CRITICAL_UNIQUE_FINGERPRINT_GROUPS={unique_critical}',
        f'ADAPTIVE_CRITICAL_AMBIGUOUS_FINGERPRINT_GROUPS={ambiguous_critical}',
        'HOTFIX13_PROXY_SEPARATE_FROM_UBERPOST=PASS',
        f'HOTFIX13_SWAPCHAIN_PROXY_VS=swap_chain_proxy_vertex_shader_dx12.cso size={len(proxy_vs)} sha256={hashlib.sha256(proxy_vs).hexdigest()}',
        f'HOTFIX13_SWAPCHAIN_PROXY_PS=swap_chain_proxy_pixel_shader_dx12.cso size={len(proxy_ps)} sha256={hashlib.sha256(proxy_ps).hexdigest()}',
        'HOTFIX13_FINAL_ENCODING=HDR10_PQ_BT2020',
        'HOTFIX16_CALIBRATION_PROFILE=MACBOOK_XDR_1000_PEAK_203_PAPER_WHITE',
        'HOTFIX16_RENODX_PEAK_NITS=1000',
        'HOTFIX16_RENODX_GAME_NITS=203',
        'HOTFIX16_RENODX_UI_NITS=203',
        'HOTFIX16_UI_TREATMENT=NOT_INCLUDED',
    ] + manifest_lines) + '\n',
    encoding='utf-8',
    newline='\n',
)
print(f'V24HDR_SHADER_COUNT={len(entries)}')
print(f'V24HDR6_ADAPTIVE_CRITICAL_UNIQUE_FINGERPRINT_GROUPS={unique_critical}')
print(f'V24HDR6_ADAPTIVE_CRITICAL_AMBIGUOUS_FINGERPRINT_GROUPS={ambiguous_critical}')
print('V24HDR6_ADAPTIVE_FINGERPRINT_GENERATION=PASS')
print('V24HDR_DX11_VARIANTS_EXCLUDED=PASS')
print('V24HDR_DX12_SM5X_SELECTION=PASS')
print(f'HOTFIX13_SWAPCHAIN_PROXY_VS_BYTES={len(proxy_vs)}')
print(f'HOTFIX13_SWAPCHAIN_PROXY_PS_BYTES={len(proxy_ps)}')
print('V24HDR13_SEPARATE_SWAPCHAIN_PROXY_EMBED=PASS')
print('V24HDR16_CALIBRATION_MANIFEST=PASS')
print('V24HDR_SHADER_HEADER_GENERATION=PASS')
