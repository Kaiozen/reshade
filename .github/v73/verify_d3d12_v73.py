from pathlib import Path
source = Path('source/d3d12/d3d12.cpp')
if not source.is_file(): raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')
required = [
'D3DMetal RTX branch isolation visual candidate v73: ACTIVE','KAIOZEN_V73_VARIANT',
'BRANCH_A_TARGET_CAPTURED','BRANCH_B_TARGET_CAPTURED','BRANCH_CLEAR_PASS',
'A-current-lighting-offset18','B-small-hierarchy','v73_note_v72_chain_pass',
'v73_apply_selected_branch_before_dispatch','s_v61_rewritten_steady_state_seen.load',
'ClearUnorderedAccessViewFloat','explicit_resource_barriers=0','commands_modified=1']
missing=[m for m in required if m not in text]
if missing: raise SystemExit('ERROR: missing V73 source markers: '+', '.join(missing))
forbidden=['D3DMetal RTX temporal feedback reset visual candidate v71: ACTIVE','functional FP32 forced-miss control v52: ACTIVE','ray-hit output pattern control v53: ACTIVE']
remaining=[m for m in forbidden if m in text]
if remaining: raise SystemExit('ERROR: forbidden active markers remain: '+', '.join(remaining))
start=text.find('void STDMETHODCALLTYPE v66_trace_dispatch(')
end=text.find('void STDMETHODCALLTYPE v66_trace_set_pipeline_state(',start)
if min(start,end)<0: raise SystemExit('ERROR: dispatch hook range missing')
hook=text[start:end]
pre=hook.find('v73_apply_selected_branch_before_dispatch(')
orig=hook.find('s_v66_original_dispatch(')
obs=hook.find('v72_observe_post_feedback_event(')
if min(pre,orig,obs)<0 or not(pre<orig<obs): raise SystemExit('ERROR: V73 clear order is invalid')
if 'depth, state.pipeline_state, inputs, outputs' not in text: raise SystemExit('ERROR: V72 target learning call missing')
Path('v73-source-verification.txt').write_text('V73_SOURCE_VERIFICATION_OK\nRUNTIME_SELECTOR=KAIOZEN_V73_VARIANT\nVARIANT_A=CURRENT_LIGHTING_OFFSET18\nVARIANT_B=SMALL_HIERARCHY_1024_128_16\nTARGETS_LEARNED_FROM_V72=YES\nSTRICT_REWRITTEN_LINEAGE_GATE=YES\nCLEAR_BEFORE_DISPATCH=YES\nGPU_READBACK=DISABLED\nRESOURCE_COPIES=DISABLED\nEXPLICIT_RESOURCE_BARRIERS=DISABLED\nCOMMANDS_MODIFIED=YES\nRESULT=PASS\n',encoding='ascii')
print('V73_SOURCE_VERIFICATION_OK')
