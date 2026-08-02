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

state_old = '''    static std::atomic<uint64_t> s_v73_last_logged_pass = 0;\n'''
state_new = state_old + '''    static std::once_flag s_v74_variant_once;
    static std::atomic<int> s_v74_selected_variant = 0;
    static std::atomic<uint64_t> s_v74_variant_a_target_count = 0;
    static std::atomic<uint64_t> s_v74_variant_b_target_count = 0;
    static std::atomic<uint64_t> s_v74_variant_a_clear_pass_count = 0;
    static std::atomic<uint64_t> s_v74_variant_b_clear_pass_count = 0;
    static std::atomic<uint64_t> s_v74_barrier_count = 0;
    static std::atomic<uint64_t> s_v74_cleared_resource_count = 0;
    static std::atomic<uint64_t> s_v74_clear_failure_count = 0;
    static std::atomic<uint64_t> s_v74_last_logged_a = 0;
    static std::atomic<uint64_t> s_v74_last_logged_b = 0;
'''
replace_once(state_old, state_new, 'V74 state')

proto_old = '''    bool v73_apply_selected_branch_before_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x,
        UINT group_y,
        UINT group_z);
'''
proto_new = proto_old + '''    int v74_get_selected_variant();
    bool v74_apply_variant_a_before_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x,
        UINT group_y,
        UINT group_z);
    bool v74_apply_variant_b_after_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x,
        UINT group_y,
        UINT group_z);
'''
replace_once(proto_old, proto_new, 'V74 prototypes')

active_old = '''\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX branch isolation visual candidate v73: ACTIVE runtime-selector=KAIOZEN_V73_VARIANT variants=A-current-lighting-offset18,B-small-hierarchy-1024-128-16 strict-lineage-gate=enabled clear-before-dispatch=enabled explicit-resource-barriers=disabled commands_modified=1.");
'''
active_new = active_old + '''                (void)v74_get_selected_variant();
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX definitive branch isolation v74: ACTIVE runtime-selector=KAIOZEN_V74_VARIANT variants=A-exact-fullres-offset18-before-dispatch,B-exact-768x32-offset6-after-producer selector-read-at-startup=1 gate=u1-plus-world-consumer exact-signatures=enabled uav-barriers=before-and-after-clear visual-timer-requires-clear=1 commands_modified=1.");
'''
replace_once(active_old, active_new, 'V74 active marker')

impl_anchor = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
'''
impl = r'''    int v74_get_selected_variant()
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

    bool v74_resolve_compute_table_descriptor(
        const v66_command_binding_state &state,
        UINT root_parameter,
        UINT descriptor_offset,
        unsigned int expected_kind,
        v71_resolved_uav &resolved)
    {
        resolved = {};
        const auto table_it = state.compute_tables.find(root_parameter);
        if (table_it == state.compute_tables.end())
            return false;

        v55_heap_info heap = {};
        UINT base_index = 0;
        if (!v55_find_heap_by_gpu(table_it->second, heap, base_index) ||
            heap.increment == 0 || base_index + descriptor_offset >= heap.count)
            return false;

        const UINT descriptor_index = base_index + descriptor_offset;
        const UINT64 gpu_handle = heap.gpu_start +
            static_cast<UINT64>(descriptor_index) * heap.increment;
        v55_heap_info resolved_heap = {};
        UINT resolved_index = 0;
        if (!v55_resolve_gpu_descriptor(
                gpu_handle,
                resolved_heap,
                resolved_index,
                resolved.descriptor,
                resolved.resource) ||
            resolved.descriptor.kind != expected_kind ||
            resolved.resource.resource == nullptr)
            return false;

        resolved.gpu.ptr = gpu_handle;
        resolved.cpu.ptr = resolved_heap.cpu_start +
            static_cast<SIZE_T>(resolved_index) * resolved_heap.increment;
        return resolved.cpu.ptr != 0 && resolved.gpu.ptr != 0;
    }

    unsigned int v74_resolved_format(const v71_resolved_uav &resolved)
    {
        return resolved.descriptor.format != 0 ?
            resolved.descriptor.format : resolved.resource.format;
    }

    bool v74_same_resource(
        const v71_resolved_uav &left,
        const v71_resolved_uav &right)
    {
        if (left.resource.resource_id != 0 && right.resource.resource_id != 0)
            return left.resource.resource_id == right.resource.resource_id;
        return left.resource.resource == right.resource.resource;
    }

    bool v74_clear_with_uav_barriers(
        ID3D12GraphicsCommandList *command_list,
        const v71_resolved_uav &resolved)
    {
        if (command_list == nullptr || resolved.gpu.ptr == 0 ||
            resolved.cpu.ptr == 0 || resolved.resource.resource == nullptr)
            return false;

        D3D12_RESOURCE_BARRIER barrier = {};
        barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
        barrier.Flags = D3D12_RESOURCE_BARRIER_FLAG_NONE;
        barrier.UAV.pResource = resolved.resource.resource;
        command_list->ResourceBarrier(1, &barrier);

        const FLOAT clear_values[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
        command_list->ClearUnorderedAccessViewFloat(
            resolved.gpu,
            resolved.cpu,
            resolved.resource.resource,
            clear_values,
            0,
            nullptr);

        command_list->ResourceBarrier(1, &barrier);
        s_v74_barrier_count.fetch_add(2, std::memory_order_acq_rel);
        s_v74_cleared_resource_count.fetch_add(1, std::memory_order_acq_rel);
        return true;
    }

    void v74_log_clear_pass(
        int variant,
        uint64_t pass_index,
        const v66_command_binding_state &state,
        const v71_resolved_uav &target,
        UINT group_x,
        UINT group_y,
        UINT group_z,
        const char *timing)
    {
        std::atomic<uint64_t> &last_logged =
            variant == 1 ? s_v74_last_logged_a : s_v74_last_logged_b;
        const uint64_t last = last_logged.load(std::memory_order_acquire);
        if (pass_index == 1 || pass_index == 8 || pass_index == 64 ||
            pass_index >= last + 300)
        {
            last_logged.store(pass_index, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX definitive branch isolation v74: BRANCH_CLEAR_PASS variant=%s pass_index=%llu pipeline_state=%p resource_id=%llu format=%u dimensions=%llux%u groups=%u,%u,%u timing=%s uav_barriers=2 clear_value=0,0,0,0 gate=u1-plus-world-consumer commands_modified=1.",
                variant == 2 ? "B-768x32-hierarchy" : "A-fullres-offset18",
                static_cast<unsigned long long>(pass_index),
                state.pipeline_state,
                static_cast<unsigned long long>(target.resource.resource_id),
                v74_resolved_format(target),
                static_cast<unsigned long long>(target.resource.width),
                target.resource.height,
                group_x, group_y, group_z,
                timing);
        }
    }

    bool v74_get_binding_state(
        ID3D12GraphicsCommandList *command_list,
        v66_command_binding_state &state)
    {
        state = {};
        std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
        const auto found = s_v66_binding_states.find(command_list);
        if (found == s_v66_binding_states.end())
            return false;
        state = found->second;
        return state.pipeline_state != nullptr;
    }

    bool v74_apply_variant_a_before_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x,
        UINT group_y,
        UINT group_z)
    {
        if (v74_get_selected_variant() != 1 || command_list == nullptr ||
            group_x != 345 || group_y != 222 || group_z != 1 ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire) ||
            !s_v66_world_consumer_found.load(std::memory_order_acquire))
            return false;

        v66_command_binding_state state = {};
        if (!v74_get_binding_state(command_list, state))
            return false;

        v71_resolved_uav output16 = {};
        v71_resolved_uav output17 = {};
        v71_resolved_uav target18 = {};
        v71_resolved_uav output19 = {};
        v71_resolved_uav alias2 = {};
        const bool signature =
            v74_resolve_compute_table_descriptor(state, 0, 16, 3, output16) &&
            v74_resolve_compute_table_descriptor(state, 0, 17, 3, output17) &&
            v74_resolve_compute_table_descriptor(state, 0, 18, 3, target18) &&
            v74_resolve_compute_table_descriptor(state, 0, 19, 3, output19) &&
            v74_resolve_compute_table_descriptor(state, 2, 2, 3, alias2) &&
            v74_resolved_format(output16) == 10 &&
            v74_resolved_format(output17) == 10 &&
            v74_resolved_format(target18) == 10 &&
            v74_resolved_format(output19) == 24 &&
            output16.resource.dimension == 3 &&
            output17.resource.dimension == 3 &&
            target18.resource.dimension == 3 &&
            output19.resource.dimension == 3 &&
            output16.resource.width == 2760 && output16.resource.height == 1776 &&
            output17.resource.width == 2760 && output17.resource.height == 1776 &&
            target18.resource.width == 2760 && target18.resource.height == 1776 &&
            output19.resource.width == 345 && output19.resource.height == 222 &&
            v74_same_resource(target18, alias2);
        if (!signature)
            return false;

        const uint64_t target_index =
            s_v74_variant_a_target_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        if (target_index == 1)
        {
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX definitive branch isolation v74: BRANCH_A_SIGNATURE_MATCH target_index=1 pipeline_state=%p root0_offsets=16,17,18,19 alias=root2-offset2 target_resource_id=%llu dimensions=2760x1776 groups=345,222,1 timing=before-dispatch commands_modified=0.",
                state.pipeline_state,
                static_cast<unsigned long long>(target18.resource.resource_id));
        }

        if (!v74_clear_with_uav_barriers(command_list, target18))
        {
            const uint64_t failures =
                s_v74_clear_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX definitive branch isolation v74: BRANCH_CLEAR_FAILURE variant=A-fullres-offset18 failure_index=%llu reason=clear-call-rejected commands_modified=0.",
                static_cast<unsigned long long>(failures));
            return false;
        }

        const uint64_t pass_index =
            s_v74_variant_a_clear_pass_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        v74_log_clear_pass(
            1, pass_index, state, target18,
            group_x, group_y, group_z, "before-target-dispatch");
        return true;
    }

    bool v74_apply_variant_b_after_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x,
        UINT group_y,
        UINT group_z)
    {
        if (v74_get_selected_variant() != 2 || command_list == nullptr ||
            group_x != 87 || group_y != 56 || group_z != 1 ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire) ||
            !s_v66_world_consumer_found.load(std::memory_order_acquire))
            return false;

        v66_command_binding_state state = {};
        if (!v74_get_binding_state(command_list, state))
            return false;

        v71_resolved_uav source2 = {};
        v71_resolved_uav target6 = {};
        const bool signature =
            v74_resolve_compute_table_descriptor(state, 0, 2, 2, source2) &&
            v74_resolve_compute_table_descriptor(state, 0, 6, 3, target6) &&
            v74_resolved_format(source2) == 10 &&
            source2.resource.dimension == 3 &&
            source2.resource.width == 2760 && source2.resource.height == 1776 &&
            v74_resolved_format(target6) == 2 &&
            target6.resource.dimension == 4 &&
            target6.resource.width == 768 && target6.resource.height == 32;
        if (!signature)
            return false;

        const uint64_t target_index =
            s_v74_variant_b_target_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        if (target_index == 1)
        {
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX definitive branch isolation v74: BRANCH_B_SIGNATURE_MATCH target_index=1 pipeline_state=%p source=root0-offset2-2760x1776-format10 target=root0-offset6-768x32-format2 target_resource_id=%llu groups=87,56,1 timing=after-producer-dispatch commands_modified=0.",
                state.pipeline_state,
                static_cast<unsigned long long>(target6.resource.resource_id));
        }

        if (!v74_clear_with_uav_barriers(command_list, target6))
        {
            const uint64_t failures =
                s_v74_clear_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX definitive branch isolation v74: BRANCH_CLEAR_FAILURE variant=B-768x32-hierarchy failure_index=%llu reason=clear-call-rejected commands_modified=0.",
                static_cast<unsigned long long>(failures));
            return false;
        }

        const uint64_t pass_index =
            s_v74_variant_b_clear_pass_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        v74_log_clear_pass(
            2, pass_index, state, target6,
            group_x, group_y, group_z, "after-hierarchy-producer-dispatch");
        return true;
    }

'''
count = text.count(impl_anchor)
if count != 1:
    raise SystemExit(f'ERROR: V74 implementation anchor count was {count}, expected 1')
text = text.replace(impl_anchor, impl + impl_anchor, 1)

hook_old = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x, UINT group_y, UINT group_z)
    {
        v73_apply_selected_branch_before_dispatch(
            command_list, group_x, group_y, group_z);
        if (s_v66_original_dispatch != nullptr)
            s_v66_original_dispatch(command_list, group_x, group_y, group_z);
        v72_observe_post_feedback_event(
'''
hook_new = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x, UINT group_y, UINT group_z)
    {
        v74_apply_variant_a_before_dispatch(
            command_list, group_x, group_y, group_z);
        if (s_v66_original_dispatch != nullptr)
            s_v66_original_dispatch(command_list, group_x, group_y, group_z);
        v74_apply_variant_b_after_dispatch(
            command_list, group_x, group_y, group_z);
        v72_observe_post_feedback_event(
'''
replace_once(hook_old, hook_new, 'V74 dispatch hook')

source.write_text(text, encoding='utf-8')
Path('v74-patch-report.txt').write_text(
    'V74_DEFINITIVE_BRANCH_ISOLATION_PATCH_OK\n'
    'RUNTIME_SELECTOR=KAIOZEN_V74_VARIANT\n'
    'SELECTOR_READ_AT_DLL_STARTUP=YES\n'
    'VARIANT_A=EXACT_FULLRES_ROOT0_OFFSET18_BEFORE_DISPATCH\n'
    'VARIANT_A_SIGNATURE=GROUPS_345x222_ROOT0_16_17_18_19_ROOT2_2_ALIAS\n'
    'VARIANT_B=EXACT_768x32_FORMAT2_ROOT0_OFFSET6_AFTER_PRODUCER\n'
    'VARIANT_B_SIGNATURE=GROUPS_87x56_SOURCE_ROOT0_2_TARGET_ROOT0_6\n'
    'GATE=U1_READY_PLUS_WORLD_CONSUMER\n'
    'STRICT_PROOF_REQUIRED_BY_RUNNER=YES\n'
    'UAV_BARRIERS_PER_CLEAR=2\n'
    'VISUAL_TIMER_REQUIRES_CLEAR_LOG=YES\n'
    'GPU_READBACK=DISABLED\n'
    'RESOURCE_COPIES=DISABLED\n'
    'COMMANDS_MODIFIED=YES\n'
    'RESULT=PASS\n',
    encoding='ascii')
print('V74_DEFINITIVE_BRANCH_ISOLATION_PATCH_OK')
