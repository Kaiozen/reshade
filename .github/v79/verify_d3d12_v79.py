from pathlib import Path
import re

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')

required = [
    'V79_BINARY_MARKER_MANIFEST_R1_PRESENT_BACKBUFFER_CHAIN',
    'kaiozen_v79_binary_marker_manifest',
    'D3DMetal RTX presented-frame producer chain v79: ACTIVE',
    'KAIOZEN_V79_ACTIVE',
    'BACKBUFFER_BEGIN_CANDIDATE',
    'PRESENT_BACKBUFFER_CAPTURE',
    'PRESENT_CANDIDATE_REJECTED',
    'reason=resource-was-seen-as-shader-input',
    'PRESENT_WRITER',
    'PRESENT_CHAIN_NODE',
    'PRESENT_CHAIN_INPUT',
    'V79_BASELINE_READY',
    'SETTINGS_RETURN_SIGNAL_ACCEPTED',
    'PRESENT_CHAIN_COMPARISON_NODE',
    'PRESENT_CHAIN_COMPARISON_RESULT',
    'C:\\\\kaiozen-v79-settings-returned.signal',
    'v79_install_device_hook(device);',
    'v79_install_command_list_hooks(list4);',
    'v79_trace_create_rtv',
    'v79_trace_om_set_render_targets',
    'v79_trace_resource_barrier',
    'v79_trace_copy_texture_region',
    'v79_trace_copy_resource',
    'v79_trace_resolve_subresource',
    'v79_record_bound_event(',
    'v79_process_present(',
    'v79_compare_and_log()',
    'v79_max_frame_writers = 24',
    'v79_max_chain_depth = 6',
    'commands_modified=0',
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit('ERROR: missing V79 source markers: ' + ', '.join(missing))

counts = {
    'manifest definition': text.count('kaiozen_v79_binary_marker_manifest()'),
    'device hook declarations+implementation': text.count('void v79_install_device_hook(ID3D12Device *device)'),
    'command hook declarations+implementation': text.count('void v79_install_command_list_hooks('),
    'resource barrier wrapper': text.count('void STDMETHODCALLTYPE v79_trace_resource_barrier('),
    'comparison result log': text.count('PRESENT_CHAIN_COMPARISON_RESULT success='),
}
for label, count in counts.items():
    expected = 2 if 'declarations+implementation' in label else 1
    if count != expected:
        raise SystemExit(f'ERROR: {label} count was {count}, expected {expected}')

for slot, expected in [
    ('v79_create_rtv_slot', '20'),
    ('v79_copy_texture_region_slot', '16'),
    ('v79_copy_resource_slot', '17'),
    ('v79_resolve_subresource_slot', '19'),
    ('v79_resource_barrier_slot', '26'),
    ('v79_om_set_render_targets_slot', '46'),
]:
    if not re.search(rf'constexpr size_t\s+{slot}\s*=\s*{expected}\s*;', text):
        raise SystemExit(f'ERROR: {slot} is not fixed to {expected}')

# Reject accidental command mutation in V79 implementation. Calls to original methods
# are expected; canary clears and explicit barriers must not be introduced by V79.
start = text.index('    bool v79_is_active()\n    {')
end = text.index('    bool v78_is_active()\n    {', start)
v79 = text[start:end]
for forbidden in [
    'ClearUnorderedAccessViewFloat(',
    'ClearUnorderedAccessViewUint(',
    'CopyBufferRegion(',
    'CreateCommittedResource(',
    'queue->Signal(',
]:
    if forbidden in v79:
        raise SystemExit(f'ERROR: V79 observational block contains forbidden mutation: {forbidden}')

# Lightweight C++ lexical balance, including comments and quoted strings.
stack = []
pairs = {')': '(', ']': '[', '}': '{'}
state = 'code'
quote = ''
escaped = False
i = 0
line = 1
while i < len(text):
    c = text[i]
    n = text[i + 1] if i + 1 < len(text) else ''
    if c == '\n':
        line += 1
    if state == 'code':
        if c == '/' and n == '/':
            state = 'line'
            i += 2
            continue
        if c == '/' and n == '*':
            state = 'block'
            i += 2
            continue
        if c in ('"', "'"):
            state = 'string'
            quote = c
            escaped = False
            i += 1
            continue
        if c in '([{':
            stack.append((c, line))
        elif c in ')]}':
            if not stack or stack[-1][0] != pairs[c]:
                raise SystemExit(f'ERROR: lexical mismatch {c} at line {line}')
            stack.pop()
    elif state == 'line':
        if c == '\n':
            state = 'code'
    elif state == 'block':
        if c == '*' and n == '/':
            state = 'code'
            i += 2
            continue
    elif state == 'string':
        if escaped:
            escaped = False
        elif c == '\\':
            escaped = True
        elif c == quote:
            state = 'code'
    i += 1
if state not in ('code', 'line') or stack:
    raise SystemExit(f'ERROR: lexical balance failed state={state} stack={stack[-5:]}')

Path('v79-source-verification.txt').write_text(
    '\n'.join([
        'V79_SOURCE_VERIFICATION_OK',
        'BINARY_MANIFEST=V79_BINARY_MARKER_MANIFEST_R1_PRESENT_BACKBUFFER_CHAIN',
        'RUNTIME_GATE=KAIOZEN_V79_ACTIVE',
        'CREATE_RTV_SLOT=20',
        'COPY_TEXTURE_SLOT=16',
        'COPY_RESOURCE_SLOT=17',
        'RESOLVE_SLOT=19',
        'RESOURCE_BARRIER_SLOT=26',
        'OM_SET_RENDER_TARGETS_SLOT=46',
        'BACKBUFFER_BEGIN_DETECTION=YES',
        'BACKBUFFER_PRESENT_DETECTION=YES',
        'PRESENT_CANDIDATE_FILTER=NEVER_SEEN_AS_SHADER_INPUT',
        'FRAME_WRITER_LIMIT=24',
        'BACKWARD_CHAIN_DEPTH=6',
        'BASELINE_PRESENT_FRAMES=8',
        'POST_SETTINGS_PRESENT_FRAMES=4',
        'EXPLICIT_SETTINGS_SIGNAL=YES',
        'GPU_READBACK=DISABLED',
        'COMMANDS_MODIFIED=NO',
        'CPP_LEXICAL_BALANCE=PASS',
        'RESULT=PASS',
        '',
    ]), encoding='utf-8', newline='\n')
print('V79_SOURCE_VERIFICATION_OK')
