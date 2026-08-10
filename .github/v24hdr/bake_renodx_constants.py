from pathlib import Path
import sys
import re

p = Path(sys.argv[1])
s = p.read_text(encoding='utf-8-sig')
start = s.find('#ifndef __cplusplus\n')
end = s.find('#define RENODX_RENO_DRT_TONE_MAP_METHOD', start)
if start < 0 or end < 0:
    raise SystemExit('RENODX_BAKE_SHARED_ANCHOR=FAIL')
old = s[start:end]
for x in [
    'cbuffer injected_buffer : register(b13, space50)',
    'cbuffer injected_buffer : register(b13)',
    '#define RENODX_PEAK_NITS',
    '#define RENODX_SWAP_CHAIN_ENCODING',
]:
    if x not in old:
        raise SystemExit('RENODX_BAKE_REQUIRED_MARKER_MISSING=' + x)

new = '''#ifndef __cplusplus
// KAIOZEN D3DMetal native shader transplant: values are baked so replacement
// shaders require no dynamic injection binding and no pipeline-layout mutation.
#define RENODX_TONE_MAP_TYPE                   3.0f
#define RENODX_PEAK_NITS                       1000.0f
#define RENODX_GAME_NITS                       203.0f
#define RENODX_UI_NITS                         203.0f
#define RENODX_GAMMA_CORRECTION                1.0f
#define RENODX_TONE_MAP_HUE_PROCESSOR          0.0f
#define RENODX_TONE_MAP_HUE_CORRECTION         1.0f
#define RENODX_TONE_MAP_HUE_SHIFT              0.5f
#define RENODX_TONE_MAP_EXPOSURE               1.0f
#define RENODX_TONE_MAP_HIGHLIGHTS             1.0f
#define RENODX_TONE_MAP_SHADOWS                1.0f
#define RENODX_TONE_MAP_CONTRAST               1.0f
#define RENODX_TONE_MAP_SATURATION             1.0f
#define RENODX_TONE_MAP_HIGHLIGHT_SATURATION   1.0f
#define RENODX_TONE_MAP_BLOWOUT                0.0f
#define RENODX_TONE_MAP_FLARE                  0.0f
#define RENODX_INTERMEDIATE_ENCODING           renodx::draw::ENCODING_NONE
#define RENODX_SWAP_CHAIN_GAMMA_CORRECTION     RENODX_GAMMA_CORRECTION
#define RENODX_SWAP_CHAIN_CUSTOM_COLOR_SPACE   0.0f
#define RENODX_SWAP_CHAIN_CLAMP_COLOR_SPACE    1.0f
#define RENODX_SWAP_CHAIN_ENCODING             4.0f
#define RENODX_SWAP_CHAIN_ENCODING_COLOR_SPACE 1.0f
'''

s = s[:start] + new + s[end:]
p.write_text(s, encoding='utf-8', newline='\n')

check = p.read_text(encoding='utf-8')
if 'register(b13' in check or 'injectedData.' in check:
    raise SystemExit('RENODX_BAKE_INJECTION_SURVIVED_SHARED=FAIL')

# Fail closed if any ZZZ shader directly accesses the dynamic injection object.
# This proves removing the cbuffer cannot leave an unresolved direct dependency.
game_dir = p.parent
bad = []
for f in game_dir.rglob('*'):
    if not f.is_file() or f.suffix.lower() not in {'.h', '.hlsl'}:
        continue
    text = f.read_text(encoding='utf-8-sig', errors='replace')
    # Scan code, not comments. The transplant removes the dynamic b13 binding
    # entirely and refuses any other live use of descriptor space 50.
    code = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    code = re.sub(r'//[^\r\n]*', '', code)
    if (
        'injectedData.' in code or
        'register(b13' in code or
        re.search(r'register\s*\([^)]*\bspace50\b', code)
    ):
        bad.append(str(f))
if bad:
    raise SystemExit('RENODX_BAKE_DIRECT_INJECTION_DEPENDENCY=FAIL files=' + ';'.join(bad))

print('RENODX_BAKED_CONSTANTS=PASS')
print('RENODX_B13_SPACE50_REMOVED=PASS')
print('RENODX_DIRECT_INJECTION_DEPENDENCY_ABSENT=PASS')
print('RENODX_BAKED_HDR10=PASS')
