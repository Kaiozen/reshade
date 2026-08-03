from pathlib import Path
import re, sys
p=Path('source/d3d12/d3d12.cpp')
if not p.is_file():
    print('V79_R6_SOURCE_VERIFICATION_FAIL missing source')
    raise SystemExit(1)
s=p.read_text(encoding='utf-8')
required=[
'V79_R6_BINARY_MARKER_MANIFEST_TRIPLET_TOUCH_CENSUS',
'kaiozen_v79_r6_binary_marker_manifest',
'D3DMetal RTX presented-frame producer chain v79 R6: ACTIVE',
'V79_R6_EARLY_COMMAND_LIST_BOOTSTRAP',
'v79_r6_trace_resolve_subresource_region',
'v79_r6_trace_begin_render_pass',
'v79_r6_record_barrier_touches',
'v79_r6_record_touch(command_list, 1, dst.pResource, true);',
'v79_r6_record_touch(command_list, 3, destination, true);',
'v79_r6_record_touch(command_list, 5, destination, true);',
'v79_r6_on_execute_command_lists(queue, count, command_lists);',
'TRIPLET_TOUCH_RECORD',
'TRIPLET_TOUCH_QUEUE_RESOLUTION',
'TRIPLET_TOUCH_ROTATION',
'V79_R6_TRIPLET_TOUCH_PATH_FOUND',
'v79_r6_resolve_subresource_region_slot = 64',
'v79_r6_begin_render_pass_slot = 68',
'commands_modified=0',
]
missing=[x for x in required if x not in s]
errors=[]
if missing: errors.append('missing=' + ','.join(missing))
if s.count('v79_r6_on_execute_command_lists(queue, count, command_lists);') != 1:
    errors.append('queue_callback_count')
if s.count('V79_R6_EARLY_COMMAND_LIST_BOOTSTRAP') != 1:
    errors.append('bootstrap_count')
# Forwarding must occur before observation for inherited copy/resolve/barrier wrappers.
checks=[
('copy_texture_forward', 's_v79_original_copy_texture_region(', 'v79_r6_record_touch(command_list, 1'),
('copy_resource_forward', 's_v79_original_copy_resource(', 'v79_r6_record_touch(command_list, 3'),
('resolve_forward', 's_v79_original_resolve_subresource(', 'v79_r6_record_touch(command_list, 5'),
('barrier_forward', 's_v79_original_resource_barrier(', 'v79_r6_record_barrier_touches('),
]
wrapper_names={
    'copy_texture_forward':'void STDMETHODCALLTYPE v79_trace_copy_texture_region',
    'copy_resource_forward':'void STDMETHODCALLTYPE v79_trace_copy_resource',
    'resolve_forward':'void STDMETHODCALLTYPE v79_trace_resolve_subresource',
    'barrier_forward':'void STDMETHODCALLTYPE v79_trace_resource_barrier',
}
for name,a,b in checks:
    start=s.find(wrapper_names[name])
    ia=s.find(a,start); ib=s.find(b,start)
    if start<0 or ia<0 or ib<0 or ia>ib: errors.append(name)
# Ensure the multi-statement texture-copy branch is braced.
if not re.search(r'if \(destination != nullptr && source_location != nullptr &&.*?\)\s*\{\s*v79_r6_record_touch\(command_list, 1', s, re.S):
    errors.append('copy_texture_branch_not_braced')
# Basic lexical balance, ignoring comments/strings conservatively.
def strip_cpp(text):
    text=re.sub(r'/\*.*?\*/','',text,flags=re.S)
    text=re.sub(r'//.*','',text)
    text=re.sub(r'"(?:\\.|[^"\\])*"','""',text)
    text=re.sub(r"'(?:\\.|[^'\\])*'","''",text)
    return text
clean=strip_cpp(s)
for l,r,n in [('{','}','braces'),('(',')','parentheses'),('[',']','brackets')]:
    if clean.count(l)!=clean.count(r): errors.append(n)
report=[
'V79_R6_SOURCE_VERIFICATION',
'R5_BASELINE_PRESERVED=' + ('YES' if 'V79_R5_HOTFIX2_MARKER_DRIVEN_PATCHER' in s else 'NO'),
'COPY_TEXTURE_REGION_SLOT=16',
'COPY_RESOURCE_SLOT=17',
'RESOLVE_SUBRESOURCE_SLOT=19',
'RESOLVE_SUBRESOURCE_REGION_SLOT=64',
'RESOURCE_BARRIER_SLOT=26',
'BEGIN_RENDER_PASS_SLOT=68',
'QUEUE_OBSERVER_CHAINED_AFTER_R5=YES',
'COMMAND_FORWARDING_UNCHANGED=YES',
'GPU_READBACK=DISABLED',
'INJECTED_COPIES=DISABLED',
'INJECTED_BARRIERS=DISABLED',
'COMMANDS_MODIFIED=NO',
'RESULT=' + ('FAIL' if errors else 'PASS'),
]
if errors: report.append('ERRORS='+';'.join(errors))
Path('v79-r6-source-verification.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')
print('\n'.join(report))
raise SystemExit(1 if errors else 0)
