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

# V74 must be dormant by default inside the V75 artifact. Its old default-A
# behavior would otherwise modify a second branch during this supposedly
# single-variable test.
v74_selector_old = '''    int v74_get_selected_variant()
    {
        std::call_once(
            s_v74_variant_once,
            []()
            {
                char value[16] = {};
                const DWORD length = GetEnvironmentVariableA(
                    "KAIOZEN_V74_VARIANT", value,
                    static_cast<DWORD>(sizeof(value)));
                int selected = 1;
                if (length != 0 && length < sizeof(value) &&
                    (value[0] == 'B' || value[0] == 'b' || value[0] == '2'))
                    selected = 2;
                s_v74_selected_variant.store(selected, std::memory_order_release);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX definitive branch isolation v74: VARIANT_SELECTED variant=%s environment=%s selection_timing=dll-startup commands_modified=1.",
                    selected == 2 ? "B-768x32-hierarchy" : "A-fullres-offset18",
                    length != 0 ? value : "default-A");
            });
        return s_v74_selected_variant.load(std::memory_order_acquire);
    }
'''
v74_selector_new = v74_selector_old.replace(
    '                int selected = 1;\n',
    '                int selected = 0;\n').replace(
    '                    selected == 2 ? "B-768x32-hierarchy" : "A-fullres-offset18",\n',
    '                    selected == 2 ? "B-768x32-hierarchy" : (selected == 1 ? "A-fullres-offset18" : "disabled-by-v75"),\n').replace(
    '                    length != 0 ? value : "default-A");\n',
    '                    length != 0 ? value : "disabled-by-v75");\n')
replace_once(v74_selector_old, v74_selector_new, 'V74 default selector disable')

state_old = '''    static std::atomic<uint64_t> s_v74_last_logged_b = 0;\n'''
state_new = state_old + '''    static std::once_flag s_v75_active_once;
    static std::atomic<bool> s_v75_active = false;
    static std::atomic<uint64_t> s_v75_target_signature_count = 0;
    static std::atomic<uint64_t> s_v75_output_pair_clear_count = 0;
    static std::atomic<uint64_t> s_v75_clear_failure_count = 0;
    static std::atomic<uint64_t> s_v75_last_logged_pass = 0;
'''
replace_once(state_old, state_new, 'V75 state')

proto_old = '''    bool v74_apply_variant_b_after_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x,
        UINT group_y,
        UINT group_z);
'''
proto_new = proto_old + '''    bool v75_is_active();
    bool v75_clear_first_consumer_outputs_after_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT max_command_count);
'''
replace_once(proto_old, proto_new, 'V75 prototypes')

active_old = '''\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX definitive branch isolation v74: ACTIVE runtime-selector=KAIOZEN_V74_VARIANT variants=A-exact-fullres-offset18-before-dispatch,B-exact-768x32-offset6-after-producer selector-read-at-startup=1 gate=u1-plus-world-consumer exact-signatures=enabled uav-barriers=before-and-after-clear visual-timer-requires-clear=1 commands_modified=1.");
'''
active_new = active_old + '''                (void)v75_is_active();
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX first ray-hit consumer output knockout v75: ACTIVE runtime-gate=KAIOZEN_V75_ACTIVE exact-consumer-signature=u1-root0-offset17-srv outputs=root0-offsets35,36 post-execute-indirect-clear=enabled output-pair-clear=enabled v74-default-selector=disabled uav-barriers-per-resource=2 visual-timer-requires-clear=1 commands_modified=1.");
'''
replace_once(active_old, active_new, 'V75 active marker')

impl_anchor = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
'''
impl = r'''    bool v75_is_active()
    {
        std::call_once(
            s_v75_active_once,
            []()
            {
                char value[16] = {};
                const DWORD length = GetEnvironmentVariableA(
                    "KAIOZEN_V75_ACTIVE", value,
                    static_cast<DWORD>(sizeof(value)));
                const bool active = length != 0 && length < sizeof(value) &&
                    (value[0] == '1' || value[0] == 'Y' || value[0] == 'y' ||
                     value[0] == 'T' || value[0] == 't');
                s_v75_active.store(active, std::memory_order_release);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX first ray-hit consumer output knockout v75: RUNTIME_GATE active=%u environment=%s selection_timing=dll-startup commands_modified=%u.",
                    active ? 1u : 0u,
                    length != 0 ? value : "unset",
                    active ? 1u : 0u);
            });
        return s_v75_active.load(std::memory_order_acquire);
    }

    bool v75_same_resource_info(
        const v71_resolved_uav &resolved,
        ID3D12Resource *resource)
    {
        return resource != nullptr && resolved.resource.resource == resource;
    }

    bool v75_clear_first_consumer_outputs_after_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT max_command_count)
    {
        if (!v75_is_active() || command_list == nullptr || max_command_count == 0 ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire) ||
            !s_v66_world_consumer_found.load(std::memory_order_acquire))
            return false;

        v66_command_binding_state state = {};
        if (!v74_get_binding_state(command_list, state))
            return false;

        ID3D12Resource *u1_resource = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            u1_resource = s_v62_u1_resource;
        }
        if (u1_resource == nullptr)
            return false;

        v71_resolved_uav u1_srv = {};
        v71_resolved_uav output35 = {};
        v71_resolved_uav output36 = {};
        const bool signature =
            v74_resolve_compute_table_descriptor(state, 0, 17, 2, u1_srv) &&
            v74_resolve_compute_table_descriptor(state, 0, 35, 3, output35) &&
            v74_resolve_compute_table_descriptor(state, 0, 36, 3, output36) &&
            v75_same_resource_info(u1_srv, u1_resource) &&
            v74_resolved_format(output35) == 10 &&
            v74_resolved_format(output36) == 10 &&
            output35.resource.dimension == 3 &&
            output36.resource.dimension == 3 &&
            output35.resource.width == 2760 && output35.resource.height == 1776 &&
            output36.resource.width == 2760 && output36.resource.height == 1776 &&
            !v74_same_resource(output35, output36);
        if (!signature)
            return false;

        const uint64_t target_index =
            s_v75_target_signature_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        if (target_index == 1)
        {
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX first ray-hit consumer output knockout v75: FIRST_CONSUMER_SIGNATURE_MATCH target_index=1 pipeline_state=%p u1_resource_id=%llu u1_binding=root0-offset17-srv output35_resource_id=%llu output36_resource_id=%llu output_format=10 dimensions=2760x1776 timing=after-execute-indirect-compute commands_modified=0.",
                state.pipeline_state,
                static_cast<unsigned long long>(u1_srv.resource.resource_id),
                static_cast<unsigned long long>(output35.resource.resource_id),
                static_cast<unsigned long long>(output36.resource.resource_id));
        }

        const bool clear35 = v74_clear_with_uav_barriers(command_list, output35);
        const bool clear36 = v74_clear_with_uav_barriers(command_list, output36);
        if (!clear35 || !clear36)
        {
            const uint64_t failures =
                s_v75_clear_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX first ray-hit consumer output knockout v75: OUTPUT_PAIR_CLEAR_FAILURE failure_index=%llu clear35=%u clear36=%u commands_modified=1.",
                static_cast<unsigned long long>(failures),
                clear35 ? 1u : 0u,
                clear36 ? 1u : 0u);
            return false;
        }

        const uint64_t pass_index =
            s_v75_output_pair_clear_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        const uint64_t last = s_v75_last_logged_pass.load(std::memory_order_acquire);
        if (pass_index == 1 || pass_index == 8 || pass_index == 64 ||
            pass_index >= last + 300)
        {
            s_v75_last_logged_pass.store(pass_index, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX first ray-hit consumer output knockout v75: OUTPUT_PAIR_CLEAR_PASS pass_index=%llu pipeline_state=%p u1_resource_id=%llu output35_resource_id=%llu output36_resource_id=%llu dimensions=2760x1776 timing=after-execute-indirect-compute uav_barriers=4 clear_value=0,0,0,0 commands_modified=1.",
                static_cast<unsigned long long>(pass_index),
                state.pipeline_state,
                static_cast<unsigned long long>(u1_srv.resource.resource_id),
                static_cast<unsigned long long>(output35.resource.resource_id),
                static_cast<unsigned long long>(output36.resource.resource_id));
        }
        return true;
    }

'''
count = text.count(impl_anchor)
if count != 1:
    raise SystemExit(f'ERROR: V75 implementation anchor count was {count}, expected 1')
text = text.replace(impl_anchor, impl + impl_anchor, 1)

hook_old = '''            v66_observe_consumer_dispatch(
                command_list,
                "execute-indirect-compute",
                max_command_count, 0, 0);
'''
hook_new = hook_old + '''            v75_clear_first_consumer_outputs_after_dispatch(
                command_list,
                max_command_count);
'''
replace_once(hook_old, hook_new, 'V75 execute-indirect hook')

source.write_text(text, encoding='utf-8')
Path('v75-patch-report.txt').write_text(
    'V75_FIRST_CONSUMER_OUTPUT_KNOCKOUT_PATCH_OK\n'
    'RUNTIME_GATE=KAIOZEN_V75_ACTIVE\n'
    'V74_DEFAULT_SELECTOR=DISABLED\n'
    'TARGET=FIRST_EXECUTE_INDIRECT_COMPUTE_CONSUMER_OF_U1\n'
    'U1_BINDING=ROOT0_OFFSET17_SRV\n'
    'OUTPUTS=ROOT0_OFFSETS35_AND36_UAV\n'
    'OUTPUT_FORMAT=10\n'
    'OUTPUT_DIMENSIONS=2760x1776\n'
    'CLEAR_TIMING=AFTER_CONSUMER_EXECUTE_INDIRECT\n'
    'UAV_BARRIERS_TOTAL_PER_PAIR=4\n'
    'VISUAL_TIMER_REQUIRES_CLEAR_LOG=YES\n'
    'GPU_READBACK=DISABLED\n'
    'RESOURCE_COPIES=DISABLED\n'
    'COMMANDS_MODIFIED=YES\n'
    'RESULT=PASS\n',
    encoding='ascii')
print('V75_FIRST_CONSUMER_OUTPUT_KNOCKOUT_PATCH_OK')
