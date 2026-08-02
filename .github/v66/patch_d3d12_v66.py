from __future__ import annotations

from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
REPORT = Path("v66-patch-report.txt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


text = SOURCE.read_text(encoding="utf-8")
if "D3DMetal RTX ray-hit consumer and lighting-history discovery v66" in text:
    raise RuntimeError("V66 patch appears to be applied already")
if "D3DMetal RTX u1 target rollover v65" not in text:
    raise RuntimeError("V65 baseline marker is missing")
if "D3DMetal RTX AddToStateObject lineage bridge v61" not in text:
    raise RuntimeError("V61 strict lineage marker is missing")

text = replace_once(
    text,
    '''    // D3DMetal RTX u1 target rollover v65.
    // Refreshes the local-root u1 descriptor after a rewritten pipeline change,
    // rejects stale target generations, and captures the post-menu resource
    // shortly after rollover instead of waiting on the old V64 1400-ray target.
''',
    '''    // D3DMetal RTX u1 target rollover v65.
    // Refreshes the local-root u1 descriptor after a rewritten pipeline change,
    // rejects stale target generations, and captures the post-menu resource
    // shortly after rollover instead of waiting on the old V64 1400-ray target.

    // D3DMetal RTX ray-hit consumer and lighting-history discovery v66.
    // Observes root bindings after genuine rewritten ray dispatches, identifies
    // the first compute pass that reads _RWRayHitBuffer, records its output UAVs,
    // and compares them after the normal 3D character-menu pause and resume.
    // V66 records commands unchanged and performs no resource copies or barriers.
''',
    "add V66 source marker",
)

text = replace_once(
    text,
    '''\tusing v33_dispatch_rays_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList4 *,
\t\tconst D3D12_DISPATCH_RAYS_DESC *);

\tusing v61_add_to_state_object_fn = HRESULT (STDMETHODCALLTYPE *)(
''',
    '''\tusing v33_dispatch_rays_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList4 *,
\t\tconst D3D12_DISPATCH_RAYS_DESC *);

    using v66_draw_instanced_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, UINT, UINT, UINT, UINT);
    using v66_draw_indexed_instanced_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, UINT, UINT, UINT, INT, UINT);
    using v66_dispatch_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, UINT, UINT, UINT);
    using v66_set_pipeline_state_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, ID3D12PipelineState *);
    using v66_set_root_signature_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, ID3D12RootSignature *);
    using v66_set_root_descriptor_table_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, UINT, D3D12_GPU_DESCRIPTOR_HANDLE);
    using v66_set_root_gpu_va_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, UINT, D3D12_GPU_VIRTUAL_ADDRESS);

\tusing v61_add_to_state_object_fn = HRESULT (STDMETHODCALLTYPE *)(
''',
    "add V66 command-list function types",
)

text = replace_once(
    text,
    '''\tconstexpr size_t v33_create_command_list_slot = 12;
\tconstexpr size_t v33_create_command_list1_slot = 51;
\tconstexpr size_t v33_set_pipeline_state1_slot = 75;
\tconstexpr size_t v33_dispatch_rays_slot = 76;
\tconstexpr size_t v61_add_to_state_object_slot = 66;
''',
    '''\tconstexpr size_t v33_create_command_list_slot = 12;
\tconstexpr size_t v33_create_command_list1_slot = 51;
\tconstexpr size_t v33_set_pipeline_state1_slot = 75;
\tconstexpr size_t v33_dispatch_rays_slot = 76;
\tconstexpr size_t v61_add_to_state_object_slot = 66;

    constexpr size_t v66_draw_instanced_slot = 12;
    constexpr size_t v66_draw_indexed_instanced_slot = 13;
    constexpr size_t v66_dispatch_slot = 14;
    constexpr size_t v66_set_pipeline_state_slot = 25;
    constexpr size_t v66_set_compute_root_signature_slot = 29;
    constexpr size_t v66_set_graphics_root_signature_slot = 30;
    constexpr size_t v66_set_compute_root_descriptor_table_slot = 31;
    constexpr size_t v66_set_graphics_root_descriptor_table_slot = 32;
    constexpr size_t v66_set_compute_root_srv_slot = 39;
    constexpr size_t v66_set_graphics_root_srv_slot = 40;
    constexpr size_t v66_set_compute_root_uav_slot = 41;
    constexpr size_t v66_set_graphics_root_uav_slot = 42;
''',
    "add V66 vtable slots",
)

text = replace_once(
    text,
    '''\tstatic v33_set_pipeline_state1_fn s_v33_original_set_pipeline_state1 = nullptr;
\tstatic v33_dispatch_rays_fn s_v33_original_dispatch_rays = nullptr;
\tstatic v61_add_to_state_object_fn s_v61_original_add_to_state_object = nullptr;
''',
    '''\tstatic v33_set_pipeline_state1_fn s_v33_original_set_pipeline_state1 = nullptr;
\tstatic v33_dispatch_rays_fn s_v33_original_dispatch_rays = nullptr;
\tstatic v61_add_to_state_object_fn s_v61_original_add_to_state_object = nullptr;

    static v66_draw_instanced_fn s_v66_original_draw_instanced = nullptr;
    static v66_draw_indexed_instanced_fn s_v66_original_draw_indexed_instanced = nullptr;
    static v66_dispatch_fn s_v66_original_dispatch = nullptr;
    static v66_set_pipeline_state_fn s_v66_original_set_pipeline_state = nullptr;
    static v66_set_root_signature_fn s_v66_original_set_compute_root_signature = nullptr;
    static v66_set_root_signature_fn s_v66_original_set_graphics_root_signature = nullptr;
    static v66_set_root_descriptor_table_fn s_v66_original_set_compute_root_descriptor_table = nullptr;
    static v66_set_root_descriptor_table_fn s_v66_original_set_graphics_root_descriptor_table = nullptr;
    static v66_set_root_gpu_va_fn s_v66_original_set_compute_root_srv = nullptr;
    static v66_set_root_gpu_va_fn s_v66_original_set_graphics_root_srv = nullptr;
    static v66_set_root_gpu_va_fn s_v66_original_set_compute_root_uav = nullptr;
    static v66_set_root_gpu_va_fn s_v66_original_set_graphics_root_uav = nullptr;
''',
    "add V66 original method pointers",
)

state_anchor = '''\tstatic std::atomic<uint64_t> s_v33_dispatch_total = 0;
\tstatic std::atomic<uint64_t> s_v33_dispatch_rewritten = 0;
'''
state_code = '''\tstatic std::atomic<uint64_t> s_v33_dispatch_total = 0;
\tstatic std::atomic<uint64_t> s_v33_dispatch_rewritten = 0;

    struct v66_command_binding_state
    {
        ID3D12PipelineState *pipeline_state = nullptr;
        std::unordered_map<UINT, UINT64> compute_tables;
        std::unordered_map<UINT, UINT64> graphics_tables;
        std::unordered_map<UINT, UINT64> compute_srvs;
        std::unordered_map<UINT, UINT64> graphics_srvs;
        std::unordered_map<UINT, UINT64> compute_uavs;
        std::unordered_map<UINT, UINT64> graphics_uavs;
    };

    struct v66_output_candidate
    {
        uint64_t resource_id = 0;
        unsigned int format = 0;
        unsigned int dimension = 0;
        UINT64 width = 0;
        UINT height = 0;
        unsigned int flags = 0;
        unsigned int binding_kind = 0; // 1=table UAV, 2=direct root UAV
        UINT root_parameter = 0;
        UINT descriptor_offset = 0;
    };

    static std::once_flag s_v66_command_hook_once;
    static std::atomic<bool> s_v66_command_hooks_installed = false;
    static std::mutex s_v66_binding_state_mutex;
    static std::unordered_map<ID3D12GraphicsCommandList *, v66_command_binding_state>
        s_v66_binding_states;
    static std::mutex s_v66_result_mutex;
    static std::vector<uint64_t> s_v66_world_output_ids;
    static void *s_v66_world_pipeline_state = nullptr;
    static std::atomic<uint64_t> s_v66_ray_epoch = 0;
    static std::atomic<uint64_t> s_v66_last_ray_tick_ms = 0;
    static std::atomic<void *> s_v66_last_ray_command_list = nullptr;
    static std::atomic<uint64_t> s_v66_direct_compute_dispatches = 0;
    static std::atomic<uint64_t> s_v66_indirect_compute_dispatches = 0;
    static std::atomic<uint64_t> s_v66_graphics_draws = 0;
    static std::atomic<uint64_t> s_v66_binding_scans = 0;
    static std::atomic<uint64_t> s_v66_u1_reference_candidates = 0;
    static std::atomic<uint64_t> s_v66_output_candidates = 0;
    static std::atomic<bool> s_v66_world_consumer_found = false;
    static std::atomic<bool> s_v66_menu_prompt_ready = false;
    static std::atomic<bool> s_v66_post_menu_phase = false;
    static std::atomic<uint64_t> s_v66_menu_gap_count = 0;
    static std::atomic<bool> s_v66_post_menu_consumer_found = false;

    bool v65_refresh_current_u1_target(uint64_t pipeline_id, const char *reason);
    void v66_note_rewritten_ray_dispatch(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        uint64_t state_call,
        uint64_t ray_index);
    void v66_observe_consumer_dispatch(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        UINT group_x,
        UINT group_y,
        UINT group_z);
'''
text = replace_once(text, state_anchor, state_code, "add V66 state and declarations")

text = replace_once(
    text,
    '''\t\tif (s_v33_original_dispatch_rays != nullptr)
\t\t\ts_v33_original_dispatch_rays(command_list, desc);
\t}
''',
    '''\t\tif (s_v33_original_dispatch_rays != nullptr)
\t\t\ts_v33_original_dispatch_rays(command_list, desc);

        if (rewritten)
            v66_note_rewritten_ray_dispatch(
                reinterpret_cast<ID3D12GraphicsCommandList *>(command_list),
                "direct-dispatch-rays",
                state_call,
                rewritten_index);
\t}
''',
    "observe direct rewritten ray dispatches",
)

text = replace_once(
    text,
    '''\tstruct v34_signature_info
\t{
\t\tbool dispatch_rays = false;
\t\tUINT num_arguments = 0;
''',
    '''\tstruct v34_signature_info
\t{
\t\tbool dispatch_rays = false;
        bool dispatch_compute = false;
\t\tUINT num_arguments = 0;
''',
    "track indirect compute signatures",
)

text = replace_once(
    text,
    '''\t\t\tif (argument.Type ==
\t\t\t\tD3D12_INDIRECT_ARGUMENT_TYPE_DISPATCH_RAYS)
\t\t\t\tinfo.dispatch_rays = true;
''',
    '''\t\t\tif (argument.Type ==
\t\t\t\tD3D12_INDIRECT_ARGUMENT_TYPE_DISPATCH_RAYS)
\t\t\t\tinfo.dispatch_rays = true;
            if (argument.Type ==
                D3D12_INDIRECT_ARGUMENT_TYPE_DISPATCH)
                info.dispatch_compute = true;
''',
    "detect indirect compute dispatch signatures",
)

# Install the full V66 observer before the existing V33 two-slot hook.
text = replace_once(
    text,
    '''\t\tv34_install_execute_indirect_hook(list4);

\t\tvoid **const vtable =
''',
    '''\t\tv34_install_execute_indirect_hook(list4);
        v66_install_command_list_consumer_hooks(list4);

\t\tvoid **const vtable =
''',
    "install V66 command-list hooks",
)

# Forward declaration for the installer is placed with the other V66 declarations.
text = replace_once(
    text,
    '''    void v66_observe_consumer_dispatch(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        UINT group_x,
        UINT group_y,
        UINT group_z);
''',
    '''    void v66_observe_consumer_dispatch(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        UINT group_x,
        UINT group_y,
        UINT group_z);
    void v66_install_command_list_consumer_hooks(
        ID3D12GraphicsCommandList4 *command_list);
''',
    "declare V66 installer",
)

v66_impl_anchor = '''\tvoid v33_install_command_list_method_hooks(IUnknown *command_list)
\t{
'''
v66_impl = r'''
    bool v66_contains_id(const std::vector<uint64_t> &ids, uint64_t value)
    {
        return value != 0 &&
            std::find(ids.begin(), ids.end(), value) != ids.end();
    }

    void v66_add_output_candidate(
        std::vector<v66_output_candidate> &outputs,
        const v55_descriptor_info &descriptor,
        const v55_resource_info &resource,
        unsigned int binding_kind,
        UINT root_parameter,
        UINT descriptor_offset)
    {
        if (descriptor.kind != 3 || resource.resource_id == 0)
            return;
        for (const auto &existing : outputs)
            if (existing.resource_id == resource.resource_id)
                return;
        if (outputs.size() >= 24)
            return;
        v66_output_candidate output = {};
        output.resource_id = resource.resource_id;
        output.format = descriptor.format != 0 ? descriptor.format : resource.format;
        output.dimension = resource.dimension;
        output.width = resource.width;
        output.height = resource.height;
        output.flags = resource.flags;
        output.binding_kind = binding_kind;
        output.root_parameter = root_parameter;
        output.descriptor_offset = descriptor_offset;
        outputs.push_back(output);
    }

    bool v66_find_resource_by_gpu_va(
        UINT64 gpu_va,
        v55_resource_info &resource)
    {
        resource = {};
        if (gpu_va == 0)
            return false;
        std::lock_guard<std::mutex> lock(s_v55_mutex);
        for (const auto &entry : s_v55_resources)
        {
            const auto &candidate = entry.second;
            if (candidate.gpu_va == 0 || candidate.width == 0 ||
                gpu_va < candidate.gpu_va ||
                gpu_va >= candidate.gpu_va + candidate.width)
                continue;
            resource = candidate;
            return true;
        }
        return false;
    }

    bool v66_scan_bound_tables(
        const v66_command_binding_state &state,
        bool graphics,
        ID3D12Resource *u1_resource,
        uint64_t &u1_resource_id,
        const char *&u1_binding,
        UINT &u1_root_parameter,
        UINT &u1_descriptor_offset,
        std::vector<v66_output_candidate> &outputs)
    {
        const auto &tables = graphics ? state.graphics_tables : state.compute_tables;
        bool references_u1 = false;
        for (const auto &table : tables)
        {
            v55_heap_info heap = {};
            UINT base_index = 0;
            if (!v55_find_heap_by_gpu(table.second, heap, base_index))
                continue;

            const UINT remaining = heap.count > base_index ? heap.count - base_index : 0;
            const UINT inspect = remaining < 96u ? remaining : 96u;
            for (UINT offset = 0; offset < inspect; ++offset)
            {
                const UINT64 handle = heap.gpu_start +
                    static_cast<UINT64>(base_index + offset) * heap.increment;
                v55_heap_info resolved_heap = {};
                UINT descriptor_index = 0;
                v55_descriptor_info descriptor = {};
                v55_resource_info resource = {};
                if (!v55_resolve_gpu_descriptor(
                        handle, resolved_heap, descriptor_index,
                        descriptor, resource))
                    continue;

                if (resource.resource == u1_resource)
                {
                    references_u1 = true;
                    u1_resource_id = resource.resource_id;
                    u1_binding = descriptor.kind == 3 ? "table-uav" : "table-srv";
                    u1_root_parameter = table.first;
                    u1_descriptor_offset = offset;
                    continue;
                }

                v66_add_output_candidate(
                    outputs, descriptor, resource, 1,
                    table.first, offset);
            }
        }

        const auto &srvs = graphics ? state.graphics_srvs : state.compute_srvs;
        const auto &uavs = graphics ? state.graphics_uavs : state.compute_uavs;
        for (const auto &binding : srvs)
        {
            v55_resource_info resource = {};
            if (!v66_find_resource_by_gpu_va(binding.second, resource))
                continue;
            if (resource.resource == u1_resource)
            {
                references_u1 = true;
                u1_resource_id = resource.resource_id;
                u1_binding = "direct-root-srv";
                u1_root_parameter = binding.first;
                u1_descriptor_offset = 0;
            }
        }
        for (const auto &binding : uavs)
        {
            v55_resource_info resource = {};
            if (!v66_find_resource_by_gpu_va(binding.second, resource))
                continue;
            if (resource.resource == u1_resource)
            {
                references_u1 = true;
                u1_resource_id = resource.resource_id;
                u1_binding = "direct-root-uav";
                u1_root_parameter = binding.first;
                u1_descriptor_offset = 0;
            }
            else
            {
                v55_descriptor_info descriptor = {};
                descriptor.kind = 3;
                descriptor.format = resource.format;
                v66_add_output_candidate(
                    outputs, descriptor, resource, 2,
                    binding.first, 0);
            }
        }
        return references_u1;
    }

    void v66_log_outputs(
        const char *phase,
        const char *kind,
        uint64_t dispatch_index,
        const std::vector<v66_output_candidate> &outputs)
    {
        for (UINT index = 0; index < outputs.size(); ++index)
        {
            const auto &output = outputs[index];
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: CONSUMER_OUTPUT phase=%s dispatch_kind=%s dispatch_index=%llu output_index=%u resource_id=%llu format=%u dimension=%u width=%llu height=%u flags=0x%X binding_kind=%s root_parameter=%u descriptor_offset=%u.",
                phase,
                kind,
                static_cast<unsigned long long>(dispatch_index),
                index,
                static_cast<unsigned long long>(output.resource_id),
                output.format,
                output.dimension,
                static_cast<unsigned long long>(output.width),
                output.height,
                output.flags,
                output.binding_kind == 2 ? "direct-root-uav" : "table-uav",
                output.root_parameter,
                output.descriptor_offset);
        }
    }

    void v66_note_rewritten_ray_dispatch(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        uint64_t state_call,
        uint64_t ray_index)
    {
        const uint64_t now = GetTickCount64();
        const uint64_t previous_tick = s_v66_last_ray_tick_ms.exchange(
            now, std::memory_order_acq_rel);
        const uint64_t epoch = s_v66_ray_epoch.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        s_v66_last_ray_command_list.store(command_list, std::memory_order_release);

        if (!s_v62_u1_target_ready.load(std::memory_order_acquire) &&
            ray_index >= 32)
            v65_refresh_current_u1_target(0, "v66-world-ray-dispatch");

        if (s_v66_world_consumer_found.load(std::memory_order_acquire) &&
            !s_v66_post_menu_phase.load(std::memory_order_acquire) &&
            previous_tick != 0 && now > previous_tick &&
            now - previous_tick >= 3000)
        {
            bool expected = false;
            if (s_v66_post_menu_phase.compare_exchange_strong(
                    expected, true, std::memory_order_acq_rel))
            {
                const uint64_t gap_index = s_v66_menu_gap_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: MENU_TRANSITION_RESUME gap_index=%llu gap_ms=%llu ray_epoch=%llu dispatch_kind=%s state_call=%llu ray_index=%llu.",
                    static_cast<unsigned long long>(gap_index),
                    static_cast<unsigned long long>(now - previous_tick),
                    static_cast<unsigned long long>(epoch),
                    kind != nullptr ? kind : "unknown",
                    static_cast<unsigned long long>(state_call),
                    static_cast<unsigned long long>(ray_index));
            }
        }
    }

    void v66_observe_consumer_dispatch(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        UINT group_x,
        UINT group_y,
        UINT group_z)
    {
        if (command_list == nullptr ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire) ||
            s_v66_ray_epoch.load(std::memory_order_acquire) == 0)
            return;

        const uint64_t dispatch_index =
            strcmp(kind, "execute-indirect-compute") == 0 ?
                s_v66_indirect_compute_dispatches.fetch_add(
                    1, std::memory_order_acq_rel) + 1 :
                s_v66_direct_compute_dispatches.fetch_add(
                    1, std::memory_order_acq_rel) + 1;

        v66_command_binding_state state = {};
        {
            std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
            const auto found = s_v66_binding_states.find(command_list);
            if (found == s_v66_binding_states.end())
                return;
            state = found->second;
        }

        ID3D12Resource *u1_resource = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            u1_resource = s_v62_u1_resource;
        }
        if (u1_resource == nullptr)
            return;

        ++s_v66_binding_scans;
        uint64_t u1_resource_id = 0;
        const char *u1_binding = "none";
        UINT u1_root_parameter = 0;
        UINT u1_descriptor_offset = 0;
        std::vector<v66_output_candidate> outputs;
        const bool references_u1 = v66_scan_bound_tables(
            state, false, u1_resource, u1_resource_id,
            u1_binding, u1_root_parameter,
            u1_descriptor_offset, outputs);
        if (!references_u1)
            return;

        ++s_v66_u1_reference_candidates;
        s_v66_output_candidates.fetch_add(
            static_cast<uint64_t>(outputs.size()),
            std::memory_order_acq_rel);

        const bool post_menu =
            s_v66_post_menu_phase.load(std::memory_order_acquire);
        if (!post_menu)
        {
            if (outputs.empty())
            {
                const uint64_t candidate_index =
                    s_v66_u1_reference_candidates.load(
                        std::memory_order_acquire);
                if (candidate_index <= 8)
                {
                    reshade::log::message(
                        reshade::log::level::info,
                        "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: CONSUMER_CANDIDATE phase=world dispatch_kind=%s dispatch_index=%llu pipeline_state=%p u1_resource_id=%llu u1_binding=%s root_parameter=%u descriptor_offset=%u output_count=0 groups=%u,%u,%u commands_modified=0.",
                        kind,
                        static_cast<unsigned long long>(dispatch_index),
                        state.pipeline_state,
                        static_cast<unsigned long long>(u1_resource_id),
                        u1_binding,
                        u1_root_parameter,
                        u1_descriptor_offset,
                        group_x, group_y, group_z);
                }
                return;
            }

            bool expected = false;
            if (!s_v66_world_consumer_found.compare_exchange_strong(
                    expected, true, std::memory_order_acq_rel))
                return;

            {
                std::lock_guard<std::mutex> lock(s_v66_result_mutex);
                s_v66_world_output_ids.clear();
                for (const auto &output : outputs)
                    s_v66_world_output_ids.push_back(output.resource_id);
                s_v66_world_pipeline_state = state.pipeline_state;
            }
            s_v66_menu_prompt_ready.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: WORLD_CONSUMER_FOUND dispatch_kind=%s dispatch_index=%llu ray_epoch=%llu same_command_list_as_last_ray=%u pipeline_state=%p u1_resource_id=%llu u1_binding=%s root_parameter=%u descriptor_offset=%u output_count=%zu groups=%u,%u,%u commands_modified=0.",
                kind,
                static_cast<unsigned long long>(dispatch_index),
                static_cast<unsigned long long>(
                    s_v66_ray_epoch.load(std::memory_order_acquire)),
                s_v66_last_ray_command_list.load(std::memory_order_acquire) ==
                    command_list ? 1u : 0u,
                state.pipeline_state,
                static_cast<unsigned long long>(u1_resource_id),
                u1_binding,
                u1_root_parameter,
                u1_descriptor_offset,
                outputs.size(),
                group_x, group_y, group_z);
            v66_log_outputs("world", kind, dispatch_index, outputs);
            return;
        }

        if (outputs.empty())
            return;
        bool expected = false;
        if (!s_v66_post_menu_consumer_found.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
            return;

        uint64_t persistent_outputs = 0;
        bool same_pipeline_state = false;
        {
            std::lock_guard<std::mutex> lock(s_v66_result_mutex);
            for (const auto &output : outputs)
                if (v66_contains_id(s_v66_world_output_ids, output.resource_id))
                    ++persistent_outputs;
            same_pipeline_state =
                s_v66_world_pipeline_state == state.pipeline_state;
        }

        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: POST_MENU_CONSUMER_RESULT success=1 dispatch_kind=%s dispatch_index=%llu ray_epoch=%llu pipeline_state=%p same_pipeline_state=%u u1_resource_id=%llu u1_binding=%s root_parameter=%u descriptor_offset=%u output_count=%zu persistent_output_count=%llu groups=%u,%u,%u commands_modified=0.",
            kind,
            static_cast<unsigned long long>(dispatch_index),
            static_cast<unsigned long long>(
                s_v66_ray_epoch.load(std::memory_order_acquire)),
            state.pipeline_state,
            same_pipeline_state ? 1u : 0u,
            static_cast<unsigned long long>(u1_resource_id),
            u1_binding,
            u1_root_parameter,
            u1_descriptor_offset,
            outputs.size(),
            static_cast<unsigned long long>(persistent_outputs),
            group_x, group_y, group_z);
        v66_log_outputs("post-menu", kind, dispatch_index, outputs);
    }

    void v66_observe_graphics_draw(
        ID3D12GraphicsCommandList *command_list,
        const char *kind)
    {
        if (command_list == nullptr ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire) ||
            s_v66_world_consumer_found.load(std::memory_order_acquire))
            return;
        const uint64_t draw_index = s_v66_graphics_draws.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        v66_command_binding_state state = {};
        {
            std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
            const auto found = s_v66_binding_states.find(command_list);
            if (found == s_v66_binding_states.end())
                return;
            state = found->second;
        }
        ID3D12Resource *u1_resource = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            u1_resource = s_v62_u1_resource;
        }
        uint64_t u1_resource_id = 0;
        const char *u1_binding = "none";
        UINT root_parameter = 0;
        UINT descriptor_offset = 0;
        std::vector<v66_output_candidate> outputs;
        if (u1_resource != nullptr && v66_scan_bound_tables(
                state, true, u1_resource, u1_resource_id,
                u1_binding, root_parameter, descriptor_offset, outputs) &&
            draw_index <= 8)
        {
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: GRAPHICS_CONSUMER_CANDIDATE draw_kind=%s draw_index=%llu pipeline_state=%p u1_resource_id=%llu u1_binding=%s root_parameter=%u descriptor_offset=%u output_uav_count=%zu commands_modified=0.",
                kind,
                static_cast<unsigned long long>(draw_index),
                state.pipeline_state,
                static_cast<unsigned long long>(u1_resource_id),
                u1_binding,
                root_parameter,
                descriptor_offset,
                outputs.size());
        }
    }

    void STDMETHODCALLTYPE v66_trace_draw_instanced(
        ID3D12GraphicsCommandList *command_list,
        UINT vertex_count, UINT instance_count,
        UINT start_vertex, UINT start_instance)
    {
        if (s_v66_original_draw_instanced != nullptr)
            s_v66_original_draw_instanced(
                command_list, vertex_count, instance_count,
                start_vertex, start_instance);
        v66_observe_graphics_draw(command_list, "draw-instanced");
    }

    void STDMETHODCALLTYPE v66_trace_draw_indexed_instanced(
        ID3D12GraphicsCommandList *command_list,
        UINT index_count, UINT instance_count,
        UINT start_index, INT base_vertex, UINT start_instance)
    {
        if (s_v66_original_draw_indexed_instanced != nullptr)
            s_v66_original_draw_indexed_instanced(
                command_list, index_count, instance_count,
                start_index, base_vertex, start_instance);
        v66_observe_graphics_draw(command_list, "draw-indexed-instanced");
    }

    void STDMETHODCALLTYPE v66_trace_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT group_x, UINT group_y, UINT group_z)
    {
        if (s_v66_original_dispatch != nullptr)
            s_v66_original_dispatch(command_list, group_x, group_y, group_z);
        v66_observe_consumer_dispatch(
            command_list, "direct-compute", group_x, group_y, group_z);
    }

    void STDMETHODCALLTYPE v66_trace_set_pipeline_state(
        ID3D12GraphicsCommandList *command_list,
        ID3D12PipelineState *pipeline_state)
    {
        if (s_v66_original_set_pipeline_state != nullptr)
            s_v66_original_set_pipeline_state(command_list, pipeline_state);
        std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
        s_v66_binding_states[command_list].pipeline_state = pipeline_state;
    }

    void v66_clear_root_bindings(
        ID3D12GraphicsCommandList *command_list,
        bool graphics)
    {
        std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
        auto &state = s_v66_binding_states[command_list];
        if (graphics)
        {
            state.graphics_tables.clear();
            state.graphics_srvs.clear();
            state.graphics_uavs.clear();
        }
        else
        {
            state.compute_tables.clear();
            state.compute_srvs.clear();
            state.compute_uavs.clear();
        }
    }

    void STDMETHODCALLTYPE v66_trace_set_compute_root_signature(
        ID3D12GraphicsCommandList *command_list,
        ID3D12RootSignature *root_signature)
    {
        if (s_v66_original_set_compute_root_signature != nullptr)
            s_v66_original_set_compute_root_signature(command_list, root_signature);
        v66_clear_root_bindings(command_list, false);
    }

    void STDMETHODCALLTYPE v66_trace_set_graphics_root_signature(
        ID3D12GraphicsCommandList *command_list,
        ID3D12RootSignature *root_signature)
    {
        if (s_v66_original_set_graphics_root_signature != nullptr)
            s_v66_original_set_graphics_root_signature(command_list, root_signature);
        v66_clear_root_bindings(command_list, true);
    }

    void STDMETHODCALLTYPE v66_trace_set_compute_root_descriptor_table(
        ID3D12GraphicsCommandList *command_list,
        UINT root_parameter,
        D3D12_GPU_DESCRIPTOR_HANDLE handle)
    {
        if (s_v66_original_set_compute_root_descriptor_table != nullptr)
            s_v66_original_set_compute_root_descriptor_table(
                command_list, root_parameter, handle);
        std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
        s_v66_binding_states[command_list].compute_tables[root_parameter] = handle.ptr;
    }

    void STDMETHODCALLTYPE v66_trace_set_graphics_root_descriptor_table(
        ID3D12GraphicsCommandList *command_list,
        UINT root_parameter,
        D3D12_GPU_DESCRIPTOR_HANDLE handle)
    {
        if (s_v66_original_set_graphics_root_descriptor_table != nullptr)
            s_v66_original_set_graphics_root_descriptor_table(
                command_list, root_parameter, handle);
        std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
        s_v66_binding_states[command_list].graphics_tables[root_parameter] = handle.ptr;
    }

    void v66_store_root_gpu_va(
        ID3D12GraphicsCommandList *command_list,
        UINT root_parameter,
        UINT64 gpu_va,
        bool graphics,
        bool uav)
    {
        std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
        auto &state = s_v66_binding_states[command_list];
        auto &bindings = graphics ?
            (uav ? state.graphics_uavs : state.graphics_srvs) :
            (uav ? state.compute_uavs : state.compute_srvs);
        bindings[root_parameter] = gpu_va;
    }

    void STDMETHODCALLTYPE v66_trace_set_compute_root_srv(
        ID3D12GraphicsCommandList *command_list,
        UINT root_parameter, D3D12_GPU_VIRTUAL_ADDRESS gpu_va)
    {
        if (s_v66_original_set_compute_root_srv != nullptr)
            s_v66_original_set_compute_root_srv(command_list, root_parameter, gpu_va);
        v66_store_root_gpu_va(command_list, root_parameter, gpu_va, false, false);
    }

    void STDMETHODCALLTYPE v66_trace_set_graphics_root_srv(
        ID3D12GraphicsCommandList *command_list,
        UINT root_parameter, D3D12_GPU_VIRTUAL_ADDRESS gpu_va)
    {
        if (s_v66_original_set_graphics_root_srv != nullptr)
            s_v66_original_set_graphics_root_srv(command_list, root_parameter, gpu_va);
        v66_store_root_gpu_va(command_list, root_parameter, gpu_va, true, false);
    }

    void STDMETHODCALLTYPE v66_trace_set_compute_root_uav(
        ID3D12GraphicsCommandList *command_list,
        UINT root_parameter, D3D12_GPU_VIRTUAL_ADDRESS gpu_va)
    {
        if (s_v66_original_set_compute_root_uav != nullptr)
            s_v66_original_set_compute_root_uav(command_list, root_parameter, gpu_va);
        v66_store_root_gpu_va(command_list, root_parameter, gpu_va, false, true);
    }

    void STDMETHODCALLTYPE v66_trace_set_graphics_root_uav(
        ID3D12GraphicsCommandList *command_list,
        UINT root_parameter, D3D12_GPU_VIRTUAL_ADDRESS gpu_va)
    {
        if (s_v66_original_set_graphics_root_uav != nullptr)
            s_v66_original_set_graphics_root_uav(command_list, root_parameter, gpu_va);
        v66_store_root_gpu_va(command_list, root_parameter, gpu_va, true, true);
    }

    void v66_install_command_list_consumer_hooks(
        ID3D12GraphicsCommandList4 *command_list)
    {
        if (command_list == nullptr)
            return;
        std::call_once(
            s_v66_command_hook_once,
            [command_list]()
            {
                void **const vtable = *reinterpret_cast<void ***>(command_list);
                s_v66_original_draw_instanced = reinterpret_cast<v66_draw_instanced_fn>(vtable[v66_draw_instanced_slot]);
                s_v66_original_draw_indexed_instanced = reinterpret_cast<v66_draw_indexed_instanced_fn>(vtable[v66_draw_indexed_instanced_slot]);
                s_v66_original_dispatch = reinterpret_cast<v66_dispatch_fn>(vtable[v66_dispatch_slot]);
                s_v66_original_set_pipeline_state = reinterpret_cast<v66_set_pipeline_state_fn>(vtable[v66_set_pipeline_state_slot]);
                s_v66_original_set_compute_root_signature = reinterpret_cast<v66_set_root_signature_fn>(vtable[v66_set_compute_root_signature_slot]);
                s_v66_original_set_graphics_root_signature = reinterpret_cast<v66_set_root_signature_fn>(vtable[v66_set_graphics_root_signature_slot]);
                s_v66_original_set_compute_root_descriptor_table = reinterpret_cast<v66_set_root_descriptor_table_fn>(vtable[v66_set_compute_root_descriptor_table_slot]);
                s_v66_original_set_graphics_root_descriptor_table = reinterpret_cast<v66_set_root_descriptor_table_fn>(vtable[v66_set_graphics_root_descriptor_table_slot]);
                s_v66_original_set_compute_root_srv = reinterpret_cast<v66_set_root_gpu_va_fn>(vtable[v66_set_compute_root_srv_slot]);
                s_v66_original_set_graphics_root_srv = reinterpret_cast<v66_set_root_gpu_va_fn>(vtable[v66_set_graphics_root_srv_slot]);
                s_v66_original_set_compute_root_uav = reinterpret_cast<v66_set_root_gpu_va_fn>(vtable[v66_set_compute_root_uav_slot]);
                s_v66_original_set_graphics_root_uav = reinterpret_cast<v66_set_root_gpu_va_fn>(vtable[v66_set_graphics_root_uav_slot]);

                struct patch_entry { size_t slot; void *replacement; };
                const patch_entry patches[] = {
                    { v66_draw_instanced_slot, reinterpret_cast<void *>(&v66_trace_draw_instanced) },
                    { v66_draw_indexed_instanced_slot, reinterpret_cast<void *>(&v66_trace_draw_indexed_instanced) },
                    { v66_dispatch_slot, reinterpret_cast<void *>(&v66_trace_dispatch) },
                    { v66_set_pipeline_state_slot, reinterpret_cast<void *>(&v66_trace_set_pipeline_state) },
                    { v66_set_compute_root_signature_slot, reinterpret_cast<void *>(&v66_trace_set_compute_root_signature) },
                    { v66_set_graphics_root_signature_slot, reinterpret_cast<void *>(&v66_trace_set_graphics_root_signature) },
                    { v66_set_compute_root_descriptor_table_slot, reinterpret_cast<void *>(&v66_trace_set_compute_root_descriptor_table) },
                    { v66_set_graphics_root_descriptor_table_slot, reinterpret_cast<void *>(&v66_trace_set_graphics_root_descriptor_table) },
                    { v66_set_compute_root_srv_slot, reinterpret_cast<void *>(&v66_trace_set_compute_root_srv) },
                    { v66_set_graphics_root_srv_slot, reinterpret_cast<void *>(&v66_trace_set_graphics_root_srv) },
                    { v66_set_compute_root_uav_slot, reinterpret_cast<void *>(&v66_trace_set_compute_root_uav) },
                    { v66_set_graphics_root_uav_slot, reinterpret_cast<void *>(&v66_trace_set_graphics_root_uav) },
                };

                bool installed = true;
                for (const auto &patch : patches)
                {
                    DWORD old_protect = 0;
                    if (!VirtualProtect(
                            &vtable[patch.slot], sizeof(void *),
                            PAGE_EXECUTE_READWRITE, &old_protect))
                    {
                        installed = false;
                        continue;
                    }
                    InterlockedExchangePointer(
                        reinterpret_cast<PVOID volatile *>(&vtable[patch.slot]),
                        patch.replacement);
                    DWORD ignored = 0;
                    VirtualProtect(
                        &vtable[patch.slot], sizeof(void *),
                        old_protect, &ignored);
                    FlushInstructionCache(
                        GetCurrentProcess(), &vtable[patch.slot], sizeof(void *));
                    installed = installed && vtable[patch.slot] == patch.replacement;
                }

                s_v66_command_hooks_installed.store(
                    installed, std::memory_order_release);
                reshade::log::message(
                    installed ? reshade::log::level::info :
                                reshade::log::level::warning,
                    "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: COMMAND_LIST_CONSUMER_HOOKS installed=%u draw_slots=12,13 dispatch_slot=14 pso_slot=25 root_signature_slots=29,30 table_slots=31,32 direct_srv_slots=39,40 direct_uav_slots=41,42 commands_modified=0.",
                    installed ? 1u : 0u);
            });
    }

'''
text = replace_once(text, v66_impl_anchor, v66_impl + v66_impl_anchor, "add V66 consumer observer")

# ExecuteIndirect: treat ordinary DISPATCH signatures as compute consumers.
text = replace_once(
    text,
    '''\t\tconst bool dispatch_rays =
\t\t\ttracked_signature && signature_info.dispatch_rays;
''',
    '''\t\tconst bool dispatch_rays =
\t\t\ttracked_signature && signature_info.dispatch_rays;
        const bool dispatch_compute =
            tracked_signature && signature_info.dispatch_compute &&
            !signature_info.dispatch_rays;
''',
    "classify indirect compute dispatch",
)

old_after_indirect = '''\t\tif (s_v34_original_execute_indirect != nullptr)
\t\t\ts_v34_original_execute_indirect(
\t\t\t\tcommand_list,
\t\t\t\tcommand_signature,
\t\t\t\tmax_command_count,
\t\t\t\targument_buffer,
\t\t\t\targument_buffer_offset,
\t\t\t\tcount_buffer,
\t\t\t\tcount_buffer_offset);

\t\t// V65 captures the initial world target twice, then refreshes and
\t\t// samples the current u1 target after the first rewritten pipeline
\t\t// rollover (normally caused by the controlled menu transition).
\t\tif (dispatch_rays && rewritten)
\t\t\tv64_try_capture_timeline(command_list);
'''
new_after_indirect = '''\t\tif (s_v34_original_execute_indirect != nullptr)
\t\t\ts_v34_original_execute_indirect(
\t\t\t\tcommand_list,
\t\t\t\tcommand_signature,
\t\t\t\tmax_command_count,
\t\t\t\targument_buffer,
\t\t\t\targument_buffer_offset,
\t\t\t\tcount_buffer,
\t\t\t\tcount_buffer_offset);

        if (dispatch_rays && rewritten)
            v66_note_rewritten_ray_dispatch(
                command_list,
                "execute-indirect-dispatch-rays",
                state_call,
                rewritten_ray_index);
        else if (dispatch_compute)
            v66_observe_consumer_dispatch(
                command_list,
                "execute-indirect-compute",
                max_command_count, 0, 0);
'''
text = replace_once(text, old_after_indirect, new_after_indirect, "replace V65 copies with V66 observation")

# Replace the V65 active mode with V66 and stop installing readback/queue hooks.
old_mode = '''\t\tstatic std::once_flag v64_temporal_mode_once;
\t\tstd::call_once(
\t\t\tv64_temporal_mode_once,
\t\t\t[device]()
\t\t\t{
\t\t\t\tv38_install_create_command_queue_hook(device);
\t\t\t\tv39_install_resource_hooks(device);
\t\t\t\tv55_install_descriptor_hooks(device);
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
\t\t\t\t\t"D3DMetal RTX u1 target rollover v65: ACTIVE stages=3 initial-thresholds=96,512 rollover-threshold=64 records-per-stage=1280 strict-lineage=v61 normalization=v63-fdiv stale-target-rejection=enabled commands_modified=current-target-copy-only.");
\t\t\t});
'''
new_mode = '''\t\tstatic std::once_flag v66_consumer_mode_once;
\t\tstd::call_once(
\t\t\tv66_consumer_mode_once,
\t\t\t[device]()
\t\t\t{
\t\t\t\tv55_install_descriptor_hooks(device);
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: ACTIVE strict-lineage=v61 normalization=v63-fdiv descriptor-binding-observation=enabled normal-menu-gap-threshold-ms=3000 descriptor-scan-limit=96 resource-readback=disabled resource-barriers=disabled commands_modified=0.");
\t\t\t});
'''
text = replace_once(text, old_mode, new_mode, "activate V66 without readback hooks")

SOURCE.write_text(text, encoding="utf-8", newline="\n")
REPORT.write_text(
    "\n".join([
        "V66_RAYHIT_CONSUMER_HISTORY_DISCOVERY_PATCH_OK",
        "BASELINE=V65_U1_TARGET_ROLLOVER",
        "STRICT_REWRITTEN_LINEAGE=V61",
        "NORMALIZATION=V63_STRICT_FP32_DIVISION",
        "RAYHIT_READBACK=DISABLED",
        "RESOURCE_BARRIERS=DISABLED",
        "COMMAND_LIST_BINDING_OBSERVATION=ENABLED",
        "DIRECT_COMPUTE_DISPATCH=ENABLED",
        "INDIRECT_COMPUTE_DISPATCH=ENABLED",
        "GRAPHICS_CONSUMER_CANDIDATES=ENABLED",
        "NORMAL_3D_MENU_GAP_THRESHOLD_MS=3000",
        "DESCRIPTOR_SCAN_LIMIT=96",
        "COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)
print("V66_RAYHIT_CONSUMER_HISTORY_DISCOVERY_PATCH_OK")
