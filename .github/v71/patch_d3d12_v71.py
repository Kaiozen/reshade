from pathlib import Path

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')

state_anchor = '''    static std::atomic<bool> s_v70_comparison_complete = false;\n'''
state_add = state_anchor + '''    static std::mutex s_v71_history_mutex;
    static void *s_v71_history_pipeline_state = nullptr;
    static std::atomic<uint64_t> s_v71_target_found_count = 0;
    static std::atomic<uint64_t> s_v71_clear_pass_count = 0;
    static std::atomic<uint64_t> s_v71_clear_resource_count = 0;
    static std::atomic<uint64_t> s_v71_clear_failure_count = 0;
    static std::atomic<uint64_t> s_v71_last_logged_pass = 0;
'''

proto_anchor = '''    void v70_observe_chain_event(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        bool graphics,
        UINT group_x,
        UINT group_y,
        UINT group_z);
'''
proto_add = proto_anchor + '''    bool v71_reset_history_feedback_before_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x,
        UINT group_y,
        UINT group_z);
'''

active_anchor = '''\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX downstream lighting dependency chain v70: ACTIVE source=first-rayhit-consumer max-depth=3 stop-on-feedback=enabled phases=world,manual-post-menu logical-slot-comparison=enabled physical-resource-persistence=diagnostic-only readback=disabled resource-copies=disabled resource-barriers=disabled commands_modified=0.");
'''
active_add = active_anchor + '''\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX temporal feedback reset visual candidate v71: ACTIVE target=v70-first-feedback-boundary identification=logical-root0-uav-offsets12,13 signature=dispatch-8x8 clear=zero-before-dispatch clear-both-feedback-uavs=enabled resource-copies=disabled explicit-resource-barriers=disabled commands_modified=1.");
'''

impl_anchor = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
'''
impl = r'''    struct v71_resolved_uav
    {
        D3D12_GPU_DESCRIPTOR_HANDLE gpu = {};
        D3D12_CPU_DESCRIPTOR_HANDLE cpu = {};
        v55_descriptor_info descriptor = {};
        v55_resource_info resource = {};
    };

    bool v71_resolve_compute_table_uav(
        const v66_command_binding_state &state,
        UINT root_parameter,
        UINT descriptor_offset,
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
            resolved.descriptor.kind != 3 ||
            resolved.resource.resource == nullptr)
            return false;

        resolved.gpu.ptr = gpu_handle;
        resolved.cpu.ptr = resolved_heap.cpu_start +
            static_cast<SIZE_T>(resolved_index) * resolved_heap.increment;
        return resolved.cpu.ptr != 0 && resolved.gpu.ptr != 0;
    }

    bool v71_history_signature_matches(
        const v66_command_binding_state &state,
        UINT group_x,
        UINT group_y,
        UINT group_z,
        v71_resolved_uav &feedback_a,
        v71_resolved_uav &feedback_b,
        v71_resolved_uav &current_output,
        v71_resolved_uav &aux_output)
    {
        if (group_x == 0 || group_y == 0 || group_z != 1 ||
            group_x > 8192 || group_y > 8192)
            return false;
        if (!v71_resolve_compute_table_uav(state, 0, 12, feedback_a) ||
            !v71_resolve_compute_table_uav(state, 0, 13, feedback_b) ||
            !v71_resolve_compute_table_uav(state, 0, 14, current_output) ||
            !v71_resolve_compute_table_uav(state, 0, 15, aux_output))
            return false;

        const UINT64 expected_width = static_cast<UINT64>(group_x) * 8u;
        const UINT expected_height = group_y * 8u;
        const auto same_extent = [expected_width, expected_height](const v55_resource_info &resource)
        {
            return resource.dimension == 3 &&
                resource.width == expected_width &&
                resource.height == expected_height &&
                (resource.flags & 0x4u) != 0;
        };

        if (!same_extent(feedback_a.resource) ||
            !same_extent(feedback_b.resource) ||
            !same_extent(current_output.resource) ||
            !same_extent(aux_output.resource))
            return false;
        if (feedback_a.resource.resource_id == feedback_b.resource.resource_id ||
            feedback_a.resource.resource_id == 0 ||
            feedback_b.resource.resource_id == 0)
            return false;
        if (feedback_a.resource.format != feedback_b.resource.format ||
            feedback_a.resource.format != current_output.resource.format)
            return false;
        if (state.pipeline_state == nullptr ||
            state.pipeline_state == s_v66_world_pipeline_state)
            return false;
        return true;
    }

    bool v71_reset_history_feedback_before_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x,
        UINT group_y,
        UINT group_z)
    {
        if (command_list == nullptr ||
            !s_v66_world_consumer_found.load(std::memory_order_acquire) ||
            s_v62_u1_resource == nullptr)
            return false;

        v66_command_binding_state state = {};
        {
            std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
            const auto found = s_v66_binding_states.find(command_list);
            if (found == s_v66_binding_states.end())
                return false;
            state = found->second;
        }

        void *known_pipeline = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v71_history_mutex);
            known_pipeline = s_v71_history_pipeline_state;
        }
        if (known_pipeline != nullptr && state.pipeline_state != known_pipeline)
            return false;

        v71_resolved_uav feedback_a = {};
        v71_resolved_uav feedback_b = {};
        v71_resolved_uav current_output = {};
        v71_resolved_uav aux_output = {};
        if (!v71_history_signature_matches(
                state, group_x, group_y, group_z,
                feedback_a, feedback_b, current_output, aux_output))
            return false;

        if (known_pipeline == nullptr)
        {
            std::lock_guard<std::mutex> lock(s_v71_history_mutex);
            if (s_v71_history_pipeline_state == nullptr)
            {
                s_v71_history_pipeline_state = state.pipeline_state;
                s_v71_target_found_count.fetch_add(1, std::memory_order_acq_rel);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX temporal feedback reset visual candidate v71: HISTORY_FEEDBACK_TARGET_FOUND pipeline_state=%p groups=%u,%u,%u root_parameter=0 feedback_offsets=12,13 feedback_resources=%llu,%llu current_output_resource=%llu aux_output_resource=%llu format=%u dimensions=%llux%u commands_modified=1.",
                    state.pipeline_state,
                    group_x, group_y, group_z,
                    static_cast<unsigned long long>(feedback_a.resource.resource_id),
                    static_cast<unsigned long long>(feedback_b.resource.resource_id),
                    static_cast<unsigned long long>(current_output.resource.resource_id),
                    static_cast<unsigned long long>(aux_output.resource.resource_id),
                    feedback_a.resource.format,
                    static_cast<unsigned long long>(feedback_a.resource.width),
                    feedback_a.resource.height);
            }
        }

        const FLOAT clear_values[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
        command_list->ClearUnorderedAccessViewFloat(
            feedback_a.gpu,
            feedback_a.cpu,
            feedback_a.resource.resource,
            clear_values,
            0,
            nullptr);
        command_list->ClearUnorderedAccessViewFloat(
            feedback_b.gpu,
            feedback_b.cpu,
            feedback_b.resource.resource,
            clear_values,
            0,
            nullptr);

        const uint64_t pass_index = s_v71_clear_pass_count.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        s_v71_clear_resource_count.fetch_add(2, std::memory_order_acq_rel);
        const uint64_t last_logged = s_v71_last_logged_pass.load(
            std::memory_order_acquire);
        if (pass_index == 1 || pass_index == 8 || pass_index == 64 ||
            pass_index >= last_logged + 300)
        {
            s_v71_last_logged_pass.store(pass_index, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX temporal feedback reset visual candidate v71: HISTORY_FEEDBACK_CLEAR_PASS pass_index=%llu pipeline_state=%p feedback_resources=%llu,%llu clear_value=0,0,0,0 groups=%u,%u,%u explicit_resource_barriers=0 commands_modified=1.",
                static_cast<unsigned long long>(pass_index),
                state.pipeline_state,
                static_cast<unsigned long long>(feedback_a.resource.resource_id),
                static_cast<unsigned long long>(feedback_b.resource.resource_id),
                group_x, group_y, group_z);
        }
        return true;
    }

'''

hook_anchor = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x, UINT group_y, UINT group_z)
    {
        if (s_v66_original_dispatch != nullptr)
            s_v66_original_dispatch(command_list, group_x, group_y, group_z);
        v70_observe_chain_event(
            command_list, "direct-compute", false,
            group_x, group_y, group_z);
        v66_observe_consumer_dispatch(
            command_list, "direct-compute", group_x, group_y, group_z);
    }
'''
hook_repl = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x, UINT group_y, UINT group_z)
    {
        v71_reset_history_feedback_before_dispatch(
            command_list, group_x, group_y, group_z);
        if (s_v66_original_dispatch != nullptr)
            s_v66_original_dispatch(command_list, group_x, group_y, group_z);
        v70_observe_chain_event(
            command_list, "direct-compute", false,
            group_x, group_y, group_z);
        v66_observe_consumer_dispatch(
            command_list, "direct-compute", group_x, group_y, group_z);
    }
'''

if 'D3DMetal RTX temporal feedback reset visual candidate v71: ACTIVE' not in text:
    replacements = [
        ('state', state_anchor, state_add),
        ('prototype', proto_anchor, proto_add),
        ('active marker', active_anchor, active_add),
        ('implementation anchor', impl_anchor, impl + impl_anchor),
        ('dispatch hook', hook_anchor, hook_repl),
    ]
    for label, old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f'ERROR: {label} anchor count {count}, expected 1')
        text = text.replace(old, new, 1)
else:
    print('V71_PATCH_ALREADY_APPLIED=YES')

source.write_text(text, encoding='utf-8')
report = Path('v71-patch-report.txt')
report.write_text(
    '\n'.join([
        'V71_TEMPORAL_FEEDBACK_RESET_PATCH_OK',
        'TARGET=V70_FIRST_STABLE_LOGICAL_FEEDBACK_BOUNDARY',
        'TARGET_IDENTIFICATION=ROOT0_UAV_OFFSETS_12_13_AND_8X8_DISPATCH_SIGNATURE',
        'FEEDBACK_UAVS_CLEARED=2',
        'CLEAR_VALUE=0,0,0,0',
        'CLEAR_TIMING=IMMEDIATELY_BEFORE_TARGET_COMPUTE_DISPATCH',
        'RESOURCE_COPIES=DISABLED',
        'EXPLICIT_RESOURCE_BARRIERS=DISABLED',
        'COMMANDS_MODIFIED=YES',
        'PURPOSE=TARGETED_VISUAL_CONFIRMATION_OF_TEMPORAL_HISTORY_ACCUMULATION',
        'RESULT=PASS',
    ]) + '\n',
    encoding='ascii')
print('V71_TEMPORAL_FEEDBACK_RESET_PATCH_OK')
