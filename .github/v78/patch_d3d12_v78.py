from pathlib import Path

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'ERROR: {label} anchor count was {count}, expected 1')
    text = text.replace(old, new, 1)


manifest_anchor = r'''extern "C" __declspec(dllexport) const char *kaiozen_v77_binary_marker_manifest()
{
    static const char manifest[] =
        "V77_BINARY_MARKER_MANIFEST_R1_SETTINGS_RESUME_DIFFERENTIAL\n"
        "D3DMetal RTX settings-resume resource differential v77: ACTIVE\n"
        "KAIOZEN_V77_ACTIVE\n"
        "V77_BASELINE_READY\n"
        "SETTINGS_SIGNAL_ACCEPTED\n"
        "DIFFERENTIAL_CANDIDATE\n"
        "DIFFERENTIAL_RESULT\n"
        "signal-file=C:/kaiozen-v77-settings-returned.signal\n"
        "trigger=radial-settings-return-to-world\n"
        "commands_modified=0\n";
    return manifest;
}

namespace
'''
manifest_block = manifest_anchor[:-len('namespace\n')] + r'''extern "C" __declspec(dllexport) const char *kaiozen_v78_binary_marker_manifest()
{
    static const char manifest[] =
        "V78_BINARY_MARKER_MANIFEST_R1_RESUME_HISTORY_PAIR_CANARY\n"
        "D3DMetal RTX resume-history candidate pair canary v78: ACTIVE\n"
        "KAIOZEN_V78_ACTIVE\n"
        "V78_CANDIDATE_PAIR_SIGNATURE_MATCH\n"
        "V78_CANDIDATE_PAIR_CAPTURE_RECORDED\n"
        "V78_CANDIDATE_PAIR_CANARY_PASS\n"
        "groups=173,444,1\n"
        "targets=root0-offsets4,5\n"
        "control=root0-offset7\n"
        "patterns=magenta|cyan\n"
        "queue-fenced-readback=required\n"
        "commands_modified=1\n";
    return manifest;
}

namespace
'''
replace_once(manifest_anchor, manifest_block, 'V78 exported binary marker manifest')

state_anchor = '''    static constexpr size_t v77_max_slots_per_phase = 4096;\n'''
state_block = state_anchor + r'''

    static std::once_flag s_v78_active_once;
    static std::atomic<bool> s_v78_active = false;
    static std::atomic<uint64_t> s_v78_target_signature_count = 0;
    static std::atomic<uint64_t> s_v78_canary_pass_count = 0;
    static std::atomic<uint64_t> s_v78_clear_failure_count = 0;
    static std::atomic<uint64_t> s_v78_last_logged_pass = 0;
'''
replace_once(state_anchor, state_block, 'V78 state')

proto_anchor = '''    bool v77_is_active();\n    void v77_observe_event(\n        ID3D12GraphicsCommandList *command_list,\n        const char *kind,\n        bool graphics);\n\n\t// V33 and V36 define these helpers later in the same namespace. V54 is\n'''
proto_block = '''    bool v77_is_active();\n    void v77_observe_event(\n        ID3D12GraphicsCommandList *command_list,\n        const char *kind,\n        bool graphics);\n    bool v78_is_active();\n    bool v78_apply_candidate_pair_after_dispatch(\n        ID3D12GraphicsCommandList *command_list,\n        UINT group_x, UINT group_y, UINT group_z);\n\n\t// V33 and V36 define these helpers later in the same namespace. V54 is\n'''
replace_once(proto_anchor, proto_block, 'V78 prototypes')

active_anchor = r'''                (void)v77_is_active();
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX settings-resume resource differential v77: ACTIVE runtime-gate=KAIOZEN_V77_ACTIVE trigger=radial-settings-return-to-world signal-file=C:/kaiozen-v77-settings-returned.signal phases=world-baseline,post-settings-resume events-per-phase=120 descriptor-scan-limit=96 textures-only=1 physical-resource-differential=1 feedback-ranking=1 readback=disabled resource-copies=disabled resource-barriers=disabled commands_modified=0.");
'''
active_block = active_anchor + r'''                (void)v78_is_active();
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX resume-history candidate pair canary v78: ACTIVE runtime-gates=KAIOZEN_V78_ACTIVE+KAIOZEN_V76_ACTIVE source=v77-collapsed-resource-families target-pass=depth2-direct-compute groups=173,444,1 targets=root0-offsets4,5 control=root0-offset7 format=10 dimensions=2760x1776 patterns=magenta|cyan one-shot-before-after-readback=enabled persistent-canary-clears=enabled strict-lineage-gate=enabled queue-fenced-readback=required v76-first-consumer-target=disabled commands_modified=1.");
'''
replace_once(active_anchor, active_block, 'V78 active marker')

# Reuse V76's proven queue-fenced readback machinery, but prevent its old
# first-consumer target from claiming the one-shot capture while V78 is active.
v76_gate_anchor = '''    bool v76_apply_canary_after_dispatch(\n        ID3D12GraphicsCommandList *command_list,\n        UINT max_command_count)\n    {\n        if (!v76_is_active() || command_list == nullptr || max_command_count == 0 ||\n'''
v76_gate_block = '''    bool v76_apply_canary_after_dispatch(\n        ID3D12GraphicsCommandList *command_list,\n        UINT max_command_count)\n    {\n        if (v78_is_active())\n            return false;\n        if (!v76_is_active() || command_list == nullptr || max_command_count == 0 ||\n'''
replace_once(v76_gate_anchor, v76_gate_block, 'Disable old V76 target during V78')

dispatch_anchor = '''        v74_apply_variant_b_after_dispatch(\n            command_list, group_x, group_y, group_z);\n'''
dispatch_block = dispatch_anchor + '''        v78_apply_candidate_pair_after_dispatch(\n            command_list, group_x, group_y, group_z);\n'''
replace_once(dispatch_anchor, dispatch_block, 'V78 direct dispatch mutation')

impl_anchor = '''    void STDMETHODCALLTYPE v66_trace_dispatch(\n'''
impl = r'''    bool v78_is_active()
    {
        std::call_once(
            s_v78_active_once,
            []()
            {
                char value[16] = {};
                const DWORD length = GetEnvironmentVariableA(
                    "KAIOZEN_V78_ACTIVE", value,
                    static_cast<DWORD>(sizeof(value)));
                const bool active = length != 0 && length < sizeof(value) &&
                    (value[0] == '1' || value[0] == 'Y' || value[0] == 'y' ||
                     value[0] == 'T' || value[0] == 't');
                s_v78_active.store(active, std::memory_order_release);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX resume-history candidate pair canary v78: RUNTIME_GATE active=%u environment=%s selection_timing=dll-startup v76-readback-backend-required=1 commands_modified=%u.",
                    active ? 1u : 0u,
                    length != 0 ? value : "unset",
                    active ? 1u : 0u);
            });
        return s_v78_active.load(std::memory_order_acquire);
    }

    bool v78_apply_candidate_pair_after_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x, UINT group_y, UINT group_z)
    {
        if (!v78_is_active() || !v76_is_active() || command_list == nullptr ||
            group_x != 173 || group_y != 444 || group_z != 1 ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire) ||
            !s_v66_world_consumer_found.load(std::memory_order_acquire) ||
            !s_v61_rewritten_steady_state_seen.load(std::memory_order_acquire))
            return false;

        v66_command_binding_state state = {};
        if (!v74_get_binding_state(command_list, state))
            return false;

        v71_resolved_uav candidate_a = {};
        v71_resolved_uav candidate_b = {};
        v71_resolved_uav control = {};
        const bool signature =
            v74_resolve_compute_table_descriptor(state, 0, 4, 3, candidate_a) &&
            v74_resolve_compute_table_descriptor(state, 0, 5, 3, candidate_b) &&
            v74_resolve_compute_table_descriptor(state, 0, 7, 3, control) &&
            v74_resolved_format(candidate_a) == 10 &&
            v74_resolved_format(candidate_b) == 10 &&
            v74_resolved_format(control) == 10 &&
            candidate_a.resource.dimension == 3 &&
            candidate_b.resource.dimension == 3 &&
            control.resource.dimension == 3 &&
            candidate_a.resource.width == 2760 && candidate_a.resource.height == 1776 &&
            candidate_b.resource.width == 2760 && candidate_b.resource.height == 1776 &&
            control.resource.width == 2760 && control.resource.height == 1776 &&
            !v74_same_resource(candidate_a, candidate_b) &&
            !v74_same_resource(candidate_a, control) &&
            !v74_same_resource(candidate_b, control);
        if (!signature)
            return false;

        const uint64_t target_index =
            s_v78_target_signature_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        if (target_index == 1)
        {
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX resume-history candidate pair canary v78: V78_CANDIDATE_PAIR_SIGNATURE_MATCH target_index=1 pipeline_state=%p groups=173,444,1 candidate_a=root0-offset4 candidate_a_resource_id=%llu candidate_b=root0-offset5 candidate_b_resource_id=%llu control=root0-offset7 control_resource_id=%llu format=10 dimensions=2760x1776 strict_rewritten_proof=1 timing=after-target-dispatch commands_modified=0.",
                state.pipeline_state,
                static_cast<unsigned long long>(candidate_a.resource.resource_id),
                static_cast<unsigned long long>(candidate_b.resource.resource_id),
                static_cast<unsigned long long>(control.resource.resource_id));
        }

        bool applied = false;
        bool expected = false;
        if (s_v76_capture_claimed.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
        {
            applied = v76_record_before_after_capture(
                command_list, candidate_a, candidate_b,
                state.pipeline_state, 0);
            if (!applied)
                s_v76_capture_claimed.store(false, std::memory_order_release);
            else
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX resume-history candidate pair canary v78: V78_CANDIDATE_PAIR_CAPTURE_RECORDED candidate_a_resource_id=%llu candidate_b_resource_id=%llu control_resource_id=%llu patterns=magenta|cyan readback_backend=v76-queue-fenced commands_modified=1.",
                    static_cast<unsigned long long>(candidate_a.resource.resource_id),
                    static_cast<unsigned long long>(candidate_b.resource.resource_id),
                    static_cast<unsigned long long>(control.resource.resource_id));
        }
        else if (!s_v76_readback_failed.load(std::memory_order_acquire))
        {
            const FLOAT pattern_a[4] = { 1.0f, 0.0f, 1.0f, 1.0f };
            const FLOAT pattern_b[4] = { 0.0f, 1.0f, 1.0f, 1.0f };
            const bool clear_a =
                v76_clear_with_pattern(command_list, candidate_a, pattern_a);
            const bool clear_b =
                v76_clear_with_pattern(command_list, candidate_b, pattern_b);
            applied = clear_a && clear_b;
            if (!applied)
            {
                const uint64_t failure =
                    s_v78_clear_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
                reshade::log::message(
                    reshade::log::level::warning,
                    "D3DMetal RTX resume-history candidate pair canary v78: V78_CANDIDATE_PAIR_CLEAR_FAILURE failure_index=%llu clear_a=%u clear_b=%u commands_modified=1.",
                    static_cast<unsigned long long>(failure),
                    clear_a ? 1u : 0u,
                    clear_b ? 1u : 0u);
            }
        }

        if (!applied)
            return false;

        const uint64_t pass_index =
            s_v78_canary_pass_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        const uint64_t last =
            s_v78_last_logged_pass.load(std::memory_order_acquire);
        if (pass_index == 1 || pass_index == 8 || pass_index == 64 ||
            pass_index >= last + 300)
        {
            s_v78_last_logged_pass.store(pass_index, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX resume-history candidate pair canary v78: V78_CANDIDATE_PAIR_CANARY_PASS pass_index=%llu pipeline_state=%p groups=173,444,1 candidate_a_resource_id=%llu candidate_b_resource_id=%llu control_resource_id=%llu pattern_a=1,0,1,1 pattern_b=0,1,1,1 strict_rewritten_proof=1 timing=after-target-dispatch uav_barriers=4 commands_modified=1.",
                static_cast<unsigned long long>(pass_index),
                state.pipeline_state,
                static_cast<unsigned long long>(candidate_a.resource.resource_id),
                static_cast<unsigned long long>(candidate_b.resource.resource_id),
                static_cast<unsigned long long>(control.resource.resource_id));
        }
        return true;
    }

'''
replace_once(impl_anchor, impl + impl_anchor, 'V78 implementation')

source.write_text(text, encoding='utf-8', newline='\n')
Path('v78-patch-report.txt').write_text(
    '\n'.join([
        'V78_RESUME_HISTORY_PAIR_CANARY_PATCH_OK',
        'RUNTIME_GATE=KAIOZEN_V78_ACTIVE',
        'READBACK_BACKEND_GATE=KAIOZEN_V76_ACTIVE',
        'TARGET_PASS_GROUPS=173x444x1',
        'TARGET_A=ROOT0_OFFSET4_FORMAT10_2760x1776',
        'TARGET_B=ROOT0_OFFSET5_FORMAT10_2760x1776',
        'CONTROL=ROOT0_OFFSET7_FORMAT10_2760x1776',
        'STRICT_REWRITTEN_GATE=YES',
        'V76_FIRST_CONSUMER_TARGET_DISABLED_WHEN_V78_ACTIVE=YES',
        'PATTERN_A=MAGENTA_1_0_1_1',
        'PATTERN_B=CYAN_0_1_1_1',
        'QUEUE_FENCED_READBACK=REUSED_FROM_V76',
        'PERSISTENT_CANARY_CLEAR=YES',
        'COMMANDS_MODIFIED=YES',
        'RESULT=PASS',
        '',
    ]), encoding='utf-8', newline='\n')
print('V78_RESUME_HISTORY_PAIR_CANARY_PATCH_OK')
