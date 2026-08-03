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


manifest_anchor = r'''extern "C" __declspec(dllexport) const char *kaiozen_v78_binary_marker_manifest()
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
manifest_block = manifest_anchor[:-len('namespace\n')] + r'''extern "C" __declspec(dllexport) const char *kaiozen_v79_binary_marker_manifest()
{
    static const char manifest[] =
        "V79_BINARY_MARKER_MANIFEST_R1_PRESENT_BACKBUFFER_CHAIN\n"
        "D3DMetal RTX presented-frame producer chain v79: ACTIVE\n"
        "KAIOZEN_V79_ACTIVE\n"
        "BACKBUFFER_BEGIN_CANDIDATE\n"
        "PRESENT_BACKBUFFER_CAPTURE\n"
        "PRESENT_CANDIDATE_REJECTED\n"
        "PRESENT_WRITER\n"
        "PRESENT_CHAIN_NODE\n"
        "V79_BASELINE_READY\n"
        "SETTINGS_RETURN_SIGNAL_ACCEPTED\n"
        "PRESENT_CHAIN_COMPARISON_RESULT\n"
        "signal-file=C:/kaiozen-v79-settings-returned.signal\n"
        "trigger=radial-settings-return-to-world\n"
        "commands_modified=0\n";
    return manifest;
}

namespace
'''
replace_once(manifest_anchor, manifest_block, 'V79 exported binary marker manifest')

# Add method types, slots and original function pointers beside the V66 command-list declarations.
type_anchor = '''    constexpr size_t v66_set_graphics_root_uav_slot = 42;\n\n'''
type_block = type_anchor + r'''    using v79_create_rtv_fn = void (STDMETHODCALLTYPE *)(
        ID3D12Device *, ID3D12Resource *,
        const D3D12_RENDER_TARGET_VIEW_DESC *,
        D3D12_CPU_DESCRIPTOR_HANDLE);
    using v79_resource_barrier_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, UINT,
        const D3D12_RESOURCE_BARRIER *);
    using v79_copy_texture_region_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *,
        const D3D12_TEXTURE_COPY_LOCATION *, UINT, UINT, UINT,
        const D3D12_TEXTURE_COPY_LOCATION *, const D3D12_BOX *);
    using v79_copy_resource_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, ID3D12Resource *, ID3D12Resource *);
    using v79_resolve_subresource_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, ID3D12Resource *, UINT,
        ID3D12Resource *, UINT, DXGI_FORMAT);
    using v79_om_set_render_targets_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, UINT,
        const D3D12_CPU_DESCRIPTOR_HANDLE *, BOOL,
        const D3D12_CPU_DESCRIPTOR_HANDLE *);

    constexpr size_t v79_create_rtv_slot = 20;
    constexpr size_t v79_copy_texture_region_slot = 16;
    constexpr size_t v79_copy_resource_slot = 17;
    constexpr size_t v79_resolve_subresource_slot = 19;
    constexpr size_t v79_resource_barrier_slot = 26;
    constexpr size_t v79_om_set_render_targets_slot = 46;

'''
replace_once(type_anchor, type_block, 'V79 function types and slots')

pointer_anchor = '''    static v66_set_root_gpu_va_fn s_v66_original_graphics_uav = nullptr;\n'''
# The actual source uses a different variable name, so anchor on the final exact line instead.
if pointer_anchor not in text:
    pointer_anchor = '''    static v66_set_root_gpu_va_fn s_v66_original_set_graphics_root_uav = nullptr;\n'''
pointer_block = pointer_anchor + r'''    static v79_create_rtv_fn s_v79_original_create_rtv = nullptr;
    static v79_resource_barrier_fn s_v79_original_resource_barrier = nullptr;
    static v79_copy_texture_region_fn s_v79_original_copy_texture_region = nullptr;
    static v79_copy_resource_fn s_v79_original_copy_resource = nullptr;
    static v79_resolve_subresource_fn s_v79_original_resolve_subresource = nullptr;
    static v79_om_set_render_targets_fn s_v79_original_om_set_render_targets = nullptr;
'''
replace_once(pointer_anchor, pointer_block, 'V79 original function pointers')

state_anchor = '''    static std::atomic<uint64_t> s_v78_last_logged_pass = 0;\n'''
state_block = state_anchor + r'''

    struct v79_event_record
    {
        uint64_t index = 0;
        uintptr_t pipeline = 0;
        unsigned int kind = 0;
        bool graphics = false;
        UINT group_x = 0;
        UINT group_y = 0;
        UINT group_z = 0;
        std::vector<v70_input_reference> inputs;
        std::vector<v66_output_candidate> outputs;
    };

    struct v79_present_capture
    {
        bool valid = false;
        uint64_t present_resource_id = 0;
        unsigned int format = 0;
        UINT64 width = 0;
        UINT height = 0;
        std::vector<v79_event_record> writers;
        std::vector<v79_event_record> chain;
    };

    static std::once_flag s_v79_active_once;
    static std::atomic<bool> s_v79_active = false;
    static std::once_flag s_v79_device_hook_once;
    static std::once_flag s_v79_command_hook_once;
    static std::atomic<bool> s_v79_rtv_hook_installed = false;
    static std::atomic<bool> s_v79_command_hooks_installed = false;
    static std::atomic<bool> s_v79_baseline_ready = false;
    static std::atomic<bool> s_v79_manual_signal_accepted = false;
    static std::atomic<bool> s_v79_post_phase = false;
    static std::atomic<bool> s_v79_result_ready = false;
    static std::atomic<uint64_t> s_v79_event_count = 0;
    static std::atomic<uint64_t> s_v79_begin_candidate_count = 0;
    static std::atomic<uint64_t> s_v79_present_capture_count = 0;
    static std::atomic<uint64_t> s_v79_baseline_present_count = 0;
    static std::atomic<uint64_t> s_v79_post_present_count = 0;
    static std::atomic<uint64_t> s_v79_signal_checks = 0;
    static std::atomic<uint64_t> s_v79_last_signal_check_tick_ms = 0;
    static std::mutex s_v79_mutex;
    static std::unordered_map<SIZE_T, uint64_t> s_v79_rtv_resources;
    static std::unordered_map<ID3D12GraphicsCommandList *, std::vector<uint64_t>>
        s_v79_current_rtvs;
    static std::unordered_map<uint64_t, bool> s_v79_active_backbuffers;
    static std::unordered_map<uint64_t, bool> s_v79_seen_as_input;
    static std::atomic<uint64_t> s_v79_rejected_input_candidates = 0;
    static std::unordered_map<uint64_t, std::vector<v79_event_record>>
        s_v79_frame_writers;
    static std::unordered_map<uint64_t, v79_event_record> s_v79_last_writer;
    static v79_present_capture s_v79_baseline_capture;
    static v79_present_capture s_v79_post_capture;
    static constexpr size_t v79_max_inputs = 48;
    static constexpr size_t v79_max_outputs = 16;
    static constexpr size_t v79_max_frame_writers = 24;
    static constexpr size_t v79_max_chain_depth = 6;
'''
replace_once(state_anchor, state_block, 'V79 state')

proto_anchor = '''    bool v78_apply_candidate_pair_after_dispatch(\n        ID3D12GraphicsCommandList *command_list,\n        UINT group_x, UINT group_y, UINT group_z);\n\n\t// V33 and V36 define these helpers later in the same namespace. V54 is\n'''
proto_block = '''    bool v78_apply_candidate_pair_after_dispatch(\n        ID3D12GraphicsCommandList *command_list,\n        UINT group_x, UINT group_y, UINT group_z);\n    bool v79_is_active();\n    void v79_install_device_hook(ID3D12Device *device);\n    void v79_install_command_list_hooks(ID3D12GraphicsCommandList4 *command_list);\n    void v79_record_bound_event(\n        ID3D12GraphicsCommandList *command_list,\n        const char *kind, bool graphics,\n        UINT group_x, UINT group_y, UINT group_z);\n\n\t// V33 and V36 define these helpers later in the same namespace. V54 is\n'''
replace_once(proto_anchor, proto_block, 'V79 prototypes')

# Install RTV tracking with the other device-side bootstrap hooks.
device_install_anchor = '''                v39_install_resource_hooks(device);\n\t\t\t\tv55_install_descriptor_hooks(device);\n'''
device_install_block = device_install_anchor + '''                v79_install_device_hook(device);\n'''
replace_once(device_install_anchor, device_install_block, 'V79 device hook bootstrap')

# Install the new command-list hooks after the existing shared command-list hooks.
command_install_anchor = '''\t\tv34_install_execute_indirect_hook(list4);\n        v66_install_command_list_consumer_hooks(list4);\n'''
command_install_block = command_install_anchor + '''        v79_install_command_list_hooks(list4);\n'''
replace_once(command_install_anchor, command_install_block, 'V79 command-list hook bootstrap')

# Record direct dispatches and draws after the original command has been emitted.
dispatch_event_anchor = '''        v77_observe_event(\n            command_list, "direct-compute", false);\n'''
dispatch_event_block = dispatch_event_anchor + '''        v79_record_bound_event(\n            command_list, "direct-compute", false,\n            group_x, group_y, group_z);\n'''
replace_once(dispatch_event_anchor, dispatch_event_block, 'V79 direct dispatch event')

draw_event_anchor = '''        v77_observe_event(\n            command_list, "draw-instanced", true);\n'''
draw_event_block = draw_event_anchor + '''        v79_record_bound_event(\n            command_list, "draw-instanced", true,\n            vertex_count, instance_count, 0);\n'''
replace_once(draw_event_anchor, draw_event_block, 'V79 draw-instanced event')

draw_index_event_anchor = '''        v77_observe_event(\n            command_list, "draw-indexed-instanced", true);\n'''
draw_index_event_block = draw_index_event_anchor + '''        v79_record_bound_event(\n            command_list, "draw-indexed-instanced", true,\n            index_count, instance_count, 0);\n'''
replace_once(draw_index_event_anchor, draw_index_event_block, 'V79 draw-indexed event')

indirect_event_anchor = '''            v77_observe_event(\n                command_list,\n                "execute-indirect-compute",\n                false);\n'''
indirect_event_block = indirect_event_anchor + '''            v79_record_bound_event(\n                command_list,\n                "execute-indirect-compute",\n                false, max_command_count, 0, 0);\n'''
replace_once(indirect_event_anchor, indirect_event_block, 'V79 indirect compute event')

# Emit the V79 activation marker beside the latest runtime markers.
active_anchor = r'''                (void)v78_is_active();
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX resume-history candidate pair canary v78: ACTIVE runtime-gates=KAIOZEN_V78_ACTIVE+KAIOZEN_V76_ACTIVE source=v77-collapsed-resource-families target-pass=depth2-direct-compute groups=173,444,1 targets=root0-offsets4,5 control=root0-offset7 format=10 dimensions=2760x1776 patterns=magenta|cyan one-shot-before-after-readback=enabled persistent-canary-clears=enabled strict-lineage-gate=enabled queue-fenced-readback=required v76-first-consumer-target=disabled commands_modified=1.");
'''
active_block = active_anchor + r'''                (void)v79_is_active();
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79: ACTIVE runtime-gate=KAIOZEN_V79_ACTIVE backbuffer-detection=present-like-common-to-output+output-to-common rtv-tracking=enabled copy-resolve-tracking=enabled present-frame-writers=24 backward-depth=6 baseline-present-frames=8 post-settings-present-frames=4 signal-file=C:/kaiozen-v79-settings-returned.signal commands_modified=0.");
'''
replace_once(active_anchor, active_block, 'V79 active marker')

impl_anchor = '''    bool v78_is_active()\n'''
impl = r'''    bool v79_is_active()
    {
        std::call_once(
            s_v79_active_once,
            []()
            {
                char value[16] = {};
                const DWORD length = GetEnvironmentVariableA(
                    "KAIOZEN_V79_ACTIVE", value,
                    static_cast<DWORD>(sizeof(value)));
                const bool active = length != 0 && length < sizeof(value) &&
                    (value[0] == '1' || value[0] == 'Y' || value[0] == 'y' ||
                     value[0] == 'T' || value[0] == 't');
                s_v79_active.store(active, std::memory_order_release);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79: RUNTIME_GATE active=%u environment=%s selection_timing=dll-startup commands_modified=0.",
                    active ? 1u : 0u,
                    length != 0 ? value : "unset");
            });
        return s_v79_active.load(std::memory_order_acquire);
    }

    const char *v79_kind_name(unsigned int kind)
    {
        switch (kind)
        {
        case 1: return "direct-compute";
        case 2: return "execute-indirect-compute";
        case 3: return "draw-instanced";
        case 4: return "draw-indexed-instanced";
        case 5: return "copy-texture";
        case 6: return "copy-resource";
        case 7: return "resolve-subresource";
        default: return "unknown";
        }
    }

    unsigned int v79_kind_value(const char *kind)
    {
        if (kind == nullptr) return 0;
        if (std::strcmp(kind, "direct-compute") == 0) return 1;
        if (std::strcmp(kind, "execute-indirect-compute") == 0) return 2;
        if (std::strcmp(kind, "draw-instanced") == 0) return 3;
        if (std::strcmp(kind, "draw-indexed-instanced") == 0) return 4;
        if (std::strcmp(kind, "copy-texture") == 0) return 5;
        if (std::strcmp(kind, "copy-resource") == 0) return 6;
        if (std::strcmp(kind, "resolve-subresource") == 0) return 7;
        return 0;
    }

    void v79_add_input(
        std::vector<v70_input_reference> &inputs,
        uint64_t resource_id, unsigned int descriptor_kind,
        unsigned int binding_kind, UINT root_parameter,
        UINT descriptor_offset)
    {
        if (resource_id == 0)
            return;
        for (const auto &existing : inputs)
            if (existing.resource_id == resource_id &&
                existing.binding_kind == binding_kind &&
                existing.root_parameter == root_parameter &&
                existing.descriptor_offset == descriptor_offset)
                return;
        if (inputs.size() >= v79_max_inputs)
            return;
        v70_input_reference value = {};
        value.resource_id = resource_id;
        value.descriptor_kind = descriptor_kind;
        value.binding_kind = binding_kind;
        value.root_parameter = root_parameter;
        value.descriptor_offset = descriptor_offset;
        inputs.push_back(value);
    }

    void v79_add_output(
        std::vector<v66_output_candidate> &outputs,
        const v55_resource_info &resource,
        unsigned int binding_kind, UINT root_parameter,
        UINT descriptor_offset)
    {
        if (resource.resource_id == 0)
            return;
        for (const auto &existing : outputs)
            if (existing.resource_id == resource.resource_id &&
                existing.binding_kind == binding_kind &&
                existing.root_parameter == root_parameter &&
                existing.descriptor_offset == descriptor_offset)
                return;
        if (outputs.size() >= v79_max_outputs)
            return;
        v66_output_candidate value = {};
        value.resource_id = resource.resource_id;
        value.format = resource.format;
        value.dimension = resource.dimension;
        value.width = resource.width;
        value.height = resource.height;
        value.flags = resource.flags;
        value.binding_kind = binding_kind;
        value.root_parameter = root_parameter;
        value.descriptor_offset = descriptor_offset;
        outputs.push_back(value);
    }

    bool v79_get_resource_info(ID3D12Resource *resource, v55_resource_info &info)
    {
        info = {};
        if (resource == nullptr)
            return false;
        const uint64_t id = v55_register_resource(resource);
        return v55_get_resource(id, info);
    }

    bool v79_is_large_texture(const v55_resource_info &resource)
    {
        return resource.dimension == 3 &&
            resource.width >= 1280 && resource.height >= 720;
    }

    bool v79_resolve_rtv_handle(SIZE_T handle, uint64_t &resource_id)
    {
        resource_id = 0;
        if (handle == 0)
            return false;
        std::lock_guard<std::mutex> lock(s_v79_mutex);
        const auto found = s_v79_rtv_resources.find(handle);
        if (found == s_v79_rtv_resources.end())
            return false;
        resource_id = found->second;
        return resource_id != 0;
    }

    UINT v79_rtv_increment(SIZE_T handle)
    {
        std::lock_guard<std::mutex> lock(s_v55_mutex);
        for (auto it = s_v55_heaps.rbegin(); it != s_v55_heaps.rend(); ++it)
        {
            if (it->type != D3D12_DESCRIPTOR_HEAP_TYPE_RTV ||
                it->increment == 0 || it->count == 0 ||
                handle < it->cpu_start)
                continue;
            const SIZE_T end = it->cpu_start +
                static_cast<SIZE_T>(it->increment) * it->count;
            if (handle < end)
                return it->increment;
        }
        return 0;
    }

    void STDMETHODCALLTYPE v79_trace_create_rtv(
        ID3D12Device *device, ID3D12Resource *resource,
        const D3D12_RENDER_TARGET_VIEW_DESC *desc,
        D3D12_CPU_DESCRIPTOR_HANDLE destination)
    {
        if (s_v79_original_create_rtv != nullptr)
            s_v79_original_create_rtv(device, resource, desc, destination);
        if (!v79_is_active() || destination.ptr == 0)
            return;
        uint64_t resource_id = 0;
        if (resource != nullptr)
            resource_id = v55_register_resource(resource);
        std::lock_guard<std::mutex> lock(s_v79_mutex);
        if (resource_id != 0)
            s_v79_rtv_resources[destination.ptr] = resource_id;
        else
            s_v79_rtv_resources.erase(destination.ptr);
    }

    void v79_install_device_hook(ID3D12Device *device)
    {
        if (device == nullptr)
            return;
        std::call_once(
            s_v79_device_hook_once,
            [device]()
            {
                void **const vtable = *reinterpret_cast<void ***>(device);
                s_v79_original_create_rtv =
                    reinterpret_cast<v79_create_rtv_fn>(
                        vtable[v79_create_rtv_slot]);
                DWORD old_protect = 0;
                bool installed = VirtualProtect(
                    &vtable[v79_create_rtv_slot], sizeof(void *),
                    PAGE_EXECUTE_READWRITE, &old_protect) != FALSE;
                if (installed)
                {
                    InterlockedExchangePointer(
                        reinterpret_cast<PVOID volatile *>(
                            &vtable[v79_create_rtv_slot]),
                        reinterpret_cast<PVOID>(&v79_trace_create_rtv));
                    DWORD ignored = 0;
                    VirtualProtect(
                        &vtable[v79_create_rtv_slot], sizeof(void *),
                        old_protect, &ignored);
                    FlushInstructionCache(
                        GetCurrentProcess(), &vtable[v79_create_rtv_slot],
                        sizeof(void *));
                    installed = vtable[v79_create_rtv_slot] ==
                        reinterpret_cast<void *>(&v79_trace_create_rtv);
                }
                s_v79_rtv_hook_installed.store(
                    installed, std::memory_order_release);
                reshade::log::message(
                    installed ? reshade::log::level::info :
                                reshade::log::level::warning,
                    "D3DMetal RTX presented-frame producer chain v79: RTV_HOOK installed=%u create_rtv_slot=20 commands_modified=0.",
                    installed ? 1u : 0u);
            });
    }

    void STDMETHODCALLTYPE v79_trace_om_set_render_targets(
        ID3D12GraphicsCommandList *command_list,
        UINT render_target_count,
        const D3D12_CPU_DESCRIPTOR_HANDLE *render_targets,
        BOOL single_range,
        const D3D12_CPU_DESCRIPTOR_HANDLE *depth_stencil)
    {
        if (s_v79_original_om_set_render_targets != nullptr)
            s_v79_original_om_set_render_targets(
                command_list, render_target_count, render_targets,
                single_range, depth_stencil);
        if (!v79_is_active() || command_list == nullptr)
            return;

        std::vector<uint64_t> resources;
        D3D12_CPU_DESCRIPTOR_HANDLE first = {};
        if (render_target_count != 0 && render_targets != nullptr)
            safe_copy_from_process(render_targets, &first, sizeof(first));
        const UINT increment = single_range && first.ptr != 0 ?
            v79_rtv_increment(first.ptr) : 0;
        for (UINT index = 0; index < render_target_count; ++index)
        {
            D3D12_CPU_DESCRIPTOR_HANDLE handle = {};
            if (single_range)
            {
                if (first.ptr == 0 || increment == 0)
                    break;
                handle.ptr = first.ptr +
                    static_cast<SIZE_T>(index) * increment;
            }
            else if (!safe_copy_from_process(
                         render_targets + index, &handle, sizeof(handle)))
                continue;
            uint64_t resource_id = 0;
            if (v79_resolve_rtv_handle(handle.ptr, resource_id) &&
                std::find(resources.begin(), resources.end(), resource_id) ==
                    resources.end())
                resources.push_back(resource_id);
        }
        std::lock_guard<std::mutex> lock(s_v79_mutex);
        s_v79_current_rtvs[command_list] = std::move(resources);
    }

    bool v79_collect_bound_resources(
        ID3D12GraphicsCommandList *command_list,
        bool graphics,
        v79_event_record &event)
    {
        v66_command_binding_state state = {};
        {
            std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
            const auto found = s_v66_binding_states.find(command_list);
            if (found == s_v66_binding_states.end())
                return false;
            state = found->second;
        }
        event.pipeline = reinterpret_cast<uintptr_t>(state.pipeline_state);
        const auto &tables = graphics ? state.graphics_tables : state.compute_tables;
        for (const auto &table : tables)
        {
            v55_heap_info heap = {};
            UINT base_index = 0;
            if (!v55_find_heap_by_gpu(table.second, heap, base_index))
                continue;
            const UINT remaining = heap.count > base_index ?
                heap.count - base_index : 0;
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
                        descriptor, resource) || resource.resource_id == 0 ||
                    resource.dimension != 3)
                    continue;
                if (descriptor.kind == 2 || descriptor.kind == 3)
                    v79_add_input(
                        event.inputs, resource.resource_id,
                        descriptor.kind, 1, table.first, offset);
                if (descriptor.kind == 3)
                    v79_add_output(
                        event.outputs, resource, 1,
                        table.first, offset);
            }
        }

        const auto &srvs = graphics ? state.graphics_srvs : state.compute_srvs;
        const auto &uavs = graphics ? state.graphics_uavs : state.compute_uavs;
        for (const auto &binding : srvs)
        {
            v55_resource_info resource = {};
            if (v66_find_resource_by_gpu_va(binding.second, resource) &&
                resource.dimension == 3)
                v79_add_input(
                    event.inputs, resource.resource_id, 2, 2,
                    binding.first, 0);
        }
        for (const auto &binding : uavs)
        {
            v55_resource_info resource = {};
            if (!v66_find_resource_by_gpu_va(binding.second, resource) ||
                resource.dimension != 3)
                continue;
            v79_add_input(
                event.inputs, resource.resource_id, 3, 2,
                binding.first, 0);
            v79_add_output(
                event.outputs, resource, 2, binding.first, 0);
        }

        if (graphics)
        {
            std::vector<uint64_t> rtvs;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                const auto found = s_v79_current_rtvs.find(command_list);
                if (found != s_v79_current_rtvs.end())
                    rtvs = found->second;
            }
            for (UINT index = 0; index < rtvs.size(); ++index)
            {
                v55_resource_info resource = {};
                if (v55_get_resource(rtvs[index], resource))
                    v79_add_output(event.outputs, resource, 3, index, 0);
            }
        }
        return !event.outputs.empty();
    }

    void v79_publish_event(const v79_event_record &event)
    {
        if (event.outputs.empty())
            return;
        std::lock_guard<std::mutex> lock(s_v79_mutex);
        for (const auto &input : event.inputs)
            s_v79_seen_as_input[input.resource_id] = true;
        for (const auto &output : event.outputs)
        {
            s_v79_last_writer[output.resource_id] = event;
            const auto active = s_v79_active_backbuffers.find(output.resource_id);
            if (active == s_v79_active_backbuffers.end() || !active->second)
                continue;
            auto &writers = s_v79_frame_writers[output.resource_id];
            if (writers.size() < v79_max_frame_writers)
                writers.push_back(event);
        }
    }

    void v79_record_bound_event(
        ID3D12GraphicsCommandList *command_list,
        const char *kind, bool graphics,
        UINT group_x, UINT group_y, UINT group_z)
    {
        if (!v79_is_active() || command_list == nullptr ||
            !s_v61_rewritten_steady_state_seen.load(std::memory_order_acquire) ||
            s_v79_result_ready.load(std::memory_order_acquire))
            return;

        if (graphics)
        {
            bool has_large_rtv = false;
            std::vector<uint64_t> rtvs;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                const auto found = s_v79_current_rtvs.find(command_list);
                if (found != s_v79_current_rtvs.end())
                    rtvs = found->second;
            }
            for (const uint64_t id : rtvs)
            {
                v55_resource_info resource = {};
                if (v55_get_resource(id, resource) && v79_is_large_texture(resource))
                {
                    has_large_rtv = true;
                    break;
                }
            }
            if (!has_large_rtv)
                return;
        }

        v79_event_record event = {};
        event.index = s_v79_event_count.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        event.kind = v79_kind_value(kind);
        event.graphics = graphics;
        event.group_x = group_x;
        event.group_y = group_y;
        event.group_z = group_z;
        if (!v79_collect_bound_resources(command_list, graphics, event))
            return;
        v79_publish_event(event);
    }

    void v79_record_copy_event(
        const char *kind, ID3D12Resource *destination,
        ID3D12Resource *source)
    {
        if (!v79_is_active() || destination == nullptr || source == nullptr ||
            !s_v61_rewritten_steady_state_seen.load(std::memory_order_acquire) ||
            s_v79_result_ready.load(std::memory_order_acquire))
            return;
        v55_resource_info destination_info = {};
        v55_resource_info source_info = {};
        if (!v79_get_resource_info(destination, destination_info) ||
            !v79_get_resource_info(source, source_info) ||
            !v79_is_large_texture(destination_info))
            return;
        v79_event_record event = {};
        event.index = s_v79_event_count.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        event.kind = v79_kind_value(kind);
        v79_add_input(event.inputs, source_info.resource_id, 2, 4, 0, 0);
        v79_add_output(event.outputs, destination_info, 4, 0, 0);
        v79_publish_event(event);
    }

    void STDMETHODCALLTYPE v79_trace_copy_texture_region(
        ID3D12GraphicsCommandList *command_list,
        const D3D12_TEXTURE_COPY_LOCATION *destination,
        UINT destination_x, UINT destination_y, UINT destination_z,
        const D3D12_TEXTURE_COPY_LOCATION *source_location,
        const D3D12_BOX *source_box)
    {
        if (s_v79_original_copy_texture_region != nullptr)
            s_v79_original_copy_texture_region(
                command_list, destination, destination_x, destination_y,
                destination_z, source_location, source_box);
        D3D12_TEXTURE_COPY_LOCATION dst = {};
        D3D12_TEXTURE_COPY_LOCATION src = {};
        if (destination != nullptr && source_location != nullptr &&
            safe_copy_from_process(destination, &dst, sizeof(dst)) &&
            safe_copy_from_process(source_location, &src, sizeof(src)))
            v79_record_copy_event("copy-texture", dst.pResource, src.pResource);
    }

    void STDMETHODCALLTYPE v79_trace_copy_resource(
        ID3D12GraphicsCommandList *command_list,
        ID3D12Resource *destination, ID3D12Resource *source_resource)
    {
        if (s_v79_original_copy_resource != nullptr)
            s_v79_original_copy_resource(
                command_list, destination, source_resource);
        v79_record_copy_event("copy-resource", destination, source_resource);
    }

    void STDMETHODCALLTYPE v79_trace_resolve_subresource(
        ID3D12GraphicsCommandList *command_list,
        ID3D12Resource *destination, UINT destination_subresource,
        ID3D12Resource *source_resource, UINT source_subresource,
        DXGI_FORMAT format)
    {
        if (s_v79_original_resolve_subresource != nullptr)
            s_v79_original_resolve_subresource(
                command_list, destination, destination_subresource,
                source_resource, source_subresource, format);
        v79_record_copy_event(
            "resolve-subresource", destination, source_resource);
    }

    int v79_event_score(
        const v79_event_record &event,
        uint64_t target_resource_id,
        UINT64 target_width, UINT target_height)
    {
        int score = 0;
        for (const auto &output : event.outputs)
            if (output.resource_id == target_resource_id)
                score += 200;
        score += static_cast<int>(event.inputs.size()) * 8;
        if (event.kind == 5 || event.kind == 6 || event.kind == 7)
            score += 90;
        if (event.graphics)
            score += 20;
        for (const auto &input : event.inputs)
        {
            v55_resource_info resource = {};
            if (!v55_get_resource(input.resource_id, resource))
                continue;
            if (resource.width == target_width && resource.height == target_height)
                score += 35;
            if (resource.format == 10 || resource.format == 2)
                score += 10;
        }
        return score;
    }

    bool v79_build_capture(
        uint64_t present_resource_id,
        const v55_resource_info &present_resource,
        v79_present_capture &capture)
    {
        capture = {};
        std::vector<v79_event_record> writers;
        std::unordered_map<uint64_t, v79_event_record> writer_snapshot;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            const auto found = s_v79_frame_writers.find(present_resource_id);
            if (found != s_v79_frame_writers.end())
                writers = found->second;
            writer_snapshot = s_v79_last_writer;
        }
        if (writers.empty())
            return false;

        std::sort(
            writers.begin(), writers.end(),
            [present_resource_id, &present_resource](
                const v79_event_record &left,
                const v79_event_record &right)
            {
                return v79_event_score(
                    left, present_resource_id,
                    present_resource.width, present_resource.height) >
                    v79_event_score(
                    right, present_resource_id,
                    present_resource.width, present_resource.height);
            });
        if (writers.size() > 12)
            writers.resize(12);

        capture.valid = true;
        capture.present_resource_id = present_resource_id;
        capture.format = present_resource.format;
        capture.width = present_resource.width;
        capture.height = present_resource.height;
        capture.writers = writers;

        v79_event_record current = writers.front();
        std::vector<uint64_t> visited;
        for (size_t depth = 0; depth < v79_max_chain_depth; ++depth)
        {
            capture.chain.push_back(current);
            uint64_t best_input = 0;
            int best_score = -1;
            for (const auto &input : current.inputs)
            {
                if (std::find(visited.begin(), visited.end(), input.resource_id) !=
                    visited.end())
                    continue;
                const auto producer = writer_snapshot.find(input.resource_id);
                if (producer == writer_snapshot.end() ||
                    producer->second.index >= current.index)
                    continue;
                v55_resource_info resource = {};
                int input_score = 50;
                if (v55_get_resource(input.resource_id, resource))
                {
                    if (resource.width == present_resource.width &&
                        resource.height == present_resource.height)
                        input_score += 100;
                    if (resource.format == 10 || resource.format == 2)
                        input_score += 20;
                }
                input_score += static_cast<int>(
                    producer->second.inputs.size()) * 4;
                if (input_score > best_score)
                {
                    best_score = input_score;
                    best_input = input.resource_id;
                }
            }
            if (best_input == 0)
                break;
            visited.push_back(best_input);
            current = writer_snapshot[best_input];
        }
        return !capture.chain.empty();
    }

    void v79_log_capture(const char *phase, const v79_present_capture &capture)
    {
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX presented-frame producer chain v79: PRESENT_BACKBUFFER_CAPTURE phase=%s present_resource_id=%llu format=%u dimensions=%llux%u writer_count=%zu chain_depth=%zu strict_rewritten_proof=1 commands_modified=0.",
            phase,
            static_cast<unsigned long long>(capture.present_resource_id),
            capture.format,
            static_cast<unsigned long long>(capture.width),
            capture.height,
            capture.writers.size(), capture.chain.size());
        for (size_t index = 0; index < capture.writers.size(); ++index)
        {
            const auto &writer = capture.writers[index];
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79: PRESENT_WRITER phase=%s rank=%zu event_index=%llu event_kind=%s pipeline_state=%p graphics=%u inputs=%zu outputs=%zu groups=%u,%u,%u score=%d commands_modified=0.",
                phase, index + 1,
                static_cast<unsigned long long>(writer.index),
                v79_kind_name(writer.kind),
                reinterpret_cast<void *>(writer.pipeline),
                writer.graphics ? 1u : 0u,
                writer.inputs.size(), writer.outputs.size(),
                writer.group_x, writer.group_y, writer.group_z,
                v79_event_score(
                    writer, capture.present_resource_id,
                    capture.width, capture.height));
        }
        for (size_t depth = 0; depth < capture.chain.size(); ++depth)
        {
            const auto &node = capture.chain[depth];
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79: PRESENT_CHAIN_NODE phase=%s depth=%zu event_index=%llu event_kind=%s pipeline_state=%p graphics=%u input_count=%zu output_count=%zu groups=%u,%u,%u commands_modified=0.",
                phase, depth,
                static_cast<unsigned long long>(node.index),
                v79_kind_name(node.kind),
                reinterpret_cast<void *>(node.pipeline),
                node.graphics ? 1u : 0u,
                node.inputs.size(), node.outputs.size(),
                node.group_x, node.group_y, node.group_z);
            for (size_t input_index = 0;
                 input_index < node.inputs.size() && input_index < 16;
                 ++input_index)
            {
                const auto &input = node.inputs[input_index];
                v55_resource_info resource = {};
                v55_get_resource(input.resource_id, resource);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79: PRESENT_CHAIN_INPUT phase=%s depth=%zu input_index=%zu resource_id=%llu descriptor_kind=%s binding_kind=%u root_parameter=%u descriptor_offset=%u format=%u dimensions=%llux%u flags=0x%X commands_modified=0.",
                    phase, depth, input_index,
                    static_cast<unsigned long long>(input.resource_id),
                    v55_descriptor_kind_name(input.descriptor_kind),
                    input.binding_kind,
                    input.root_parameter,
                    input.descriptor_offset,
                    resource.format,
                    static_cast<unsigned long long>(resource.width),
                    resource.height, resource.flags);
            }
        }
    }

    void v79_check_signal()
    {
        if (!s_v79_baseline_ready.load(std::memory_order_acquire) ||
            s_v79_manual_signal_accepted.load(std::memory_order_acquire))
            return;
        const uint64_t now = GetTickCount64();
        uint64_t previous = s_v79_last_signal_check_tick_ms.load(
            std::memory_order_acquire);
        if (now < previous + 100 ||
            !s_v79_last_signal_check_tick_ms.compare_exchange_strong(
                previous, now, std::memory_order_acq_rel))
            return;
        s_v79_signal_checks.fetch_add(1, std::memory_order_acq_rel);
        const DWORD attributes = GetFileAttributesA(
            "C:\\kaiozen-v79-settings-returned.signal");
        if (attributes == INVALID_FILE_ATTRIBUTES ||
            (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0)
            return;
        bool expected = false;
        if (!s_v79_manual_signal_accepted.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
            return;
        s_v79_post_phase.store(true, std::memory_order_release);
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX presented-frame producer chain v79: SETTINGS_RETURN_SIGNAL_ACCEPTED signal_file=C:/kaiozen-v79-settings-returned.signal trigger=radial-settings-return-to-world next_present_frames=4 commands_modified=0.");
    }

    bool v79_logical_node_match(
        const v79_event_record &left,
        const v79_event_record &right)
    {
        return left.kind == right.kind &&
            left.pipeline == right.pipeline &&
            left.graphics == right.graphics &&
            left.group_x == right.group_x &&
            left.group_y == right.group_y &&
            left.group_z == right.group_z;
    }

    void v79_compare_and_log()
    {
        v79_present_capture baseline;
        v79_present_capture post;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            baseline = s_v79_baseline_capture;
            post = s_v79_post_capture;
        }
        const size_t common_depth =
            baseline.chain.size() < post.chain.size() ?
                baseline.chain.size() : post.chain.size();
        uint64_t logical_matches = 0;
        uint64_t recreated_inputs = 0;
        for (size_t depth = 0; depth < common_depth; ++depth)
        {
            const auto &before = baseline.chain[depth];
            const auto &after = post.chain[depth];
            const bool logical_match = v79_logical_node_match(before, after);
            if (logical_match)
                ++logical_matches;
            for (const auto &before_input : before.inputs)
            {
                bool found_same = false;
                for (const auto &after_input : after.inputs)
                    if (before_input.resource_id == after_input.resource_id)
                    {
                        found_same = true;
                        break;
                    }
                if (!found_same)
                    ++recreated_inputs;
            }
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79: PRESENT_CHAIN_COMPARISON_NODE depth=%zu logical_match=%u baseline_kind=%s post_kind=%s baseline_pipeline=%p post_pipeline=%p baseline_inputs=%zu post_inputs=%zu commands_modified=0.",
                depth, logical_match ? 1u : 0u,
                v79_kind_name(before.kind), v79_kind_name(after.kind),
                reinterpret_cast<void *>(before.pipeline),
                reinterpret_cast<void *>(after.pipeline),
                before.inputs.size(), after.inputs.size());
        }
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX presented-frame producer chain v79: PRESENT_CHAIN_COMPARISON_RESULT success=%u baseline_present_resource_id=%llu post_present_resource_id=%llu baseline_writer_count=%zu post_writer_count=%zu baseline_chain_depth=%zu post_chain_depth=%zu common_depth=%zu logical_node_matches=%llu recreated_input_references=%llu strict_rewritten_proof=1 trigger=radial-settings-return-to-world commands_modified=0.",
            baseline.valid && post.valid ? 1u : 0u,
            static_cast<unsigned long long>(baseline.present_resource_id),
            static_cast<unsigned long long>(post.present_resource_id),
            baseline.writers.size(), post.writers.size(),
            baseline.chain.size(), post.chain.size(), common_depth,
            static_cast<unsigned long long>(logical_matches),
            static_cast<unsigned long long>(recreated_inputs));
        s_v79_result_ready.store(true, std::memory_order_release);
    }

    void v79_process_present(ID3D12Resource *resource)
    {
        if (!v79_is_active() || resource == nullptr ||
            !s_v61_rewritten_steady_state_seen.load(std::memory_order_acquire) ||
            s_v79_result_ready.load(std::memory_order_acquire))
            return;
        v79_check_signal();
        v55_resource_info info = {};
        if (!v79_get_resource_info(resource, info) ||
            !v79_is_large_texture(info) ||
            (info.flags & D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET) == 0)
            return;
        bool seen_as_input = false;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            const auto found = s_v79_seen_as_input.find(info.resource_id);
            seen_as_input = found != s_v79_seen_as_input.end() && found->second;
        }
        if (seen_as_input)
        {
            const uint64_t rejected =
                s_v79_rejected_input_candidates.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            if (rejected <= 8)
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79: PRESENT_CANDIDATE_REJECTED count=%llu resource_id=%llu reason=resource-was-seen-as-shader-input format=%u dimensions=%llux%u commands_modified=0.",
                    static_cast<unsigned long long>(rejected),
                    static_cast<unsigned long long>(info.resource_id),
                    info.format,
                    static_cast<unsigned long long>(info.width), info.height);
            return;
        }

        v79_present_capture capture;
        if (!v79_build_capture(info.resource_id, info, capture))
            return;

        s_v79_present_capture_count.fetch_add(1, std::memory_order_acq_rel);
        const bool post_phase = s_v79_post_phase.load(std::memory_order_acquire);
        if (!post_phase)
        {
            const uint64_t frame = s_v79_baseline_present_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                s_v79_baseline_capture = capture;
            }
            if (frame >= 8)
            {
                bool expected = false;
                if (s_v79_baseline_ready.compare_exchange_strong(
                        expected, true, std::memory_order_acq_rel))
                {
                    v79_log_capture("baseline", capture);
                    reshade::log::message(
                        reshade::log::level::info,
                        "D3DMetal RTX presented-frame producer chain v79: V79_BASELINE_READY present_frames=%llu present_resource_id=%llu writer_count=%zu chain_depth=%zu candidate_filter=never-seen-as-input ready_for_radial_settings=1 commands_modified=0.",
                        static_cast<unsigned long long>(frame),
                        static_cast<unsigned long long>(capture.present_resource_id),
                        capture.writers.size(), capture.chain.size());
                }
            }
        }
        else
        {
            const uint64_t frame = s_v79_post_present_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                s_v79_post_capture = capture;
            }
            if (frame >= 4 &&
                !s_v79_result_ready.load(std::memory_order_acquire))
            {
                v79_log_capture("post-settings", capture);
                v79_compare_and_log();
            }
        }
    }

    void v79_observe_barriers(
        UINT barrier_count, const D3D12_RESOURCE_BARRIER *barriers)
    {
        if (!v79_is_active() || barriers == nullptr || barrier_count == 0)
            return;
        for (UINT index = 0; index < barrier_count; ++index)
        {
            D3D12_RESOURCE_BARRIER barrier = {};
            if (!safe_copy_from_process(barriers + index, &barrier, sizeof(barrier)) ||
                barrier.Type != D3D12_RESOURCE_BARRIER_TYPE_TRANSITION ||
                barrier.Transition.pResource == nullptr)
                continue;
            v55_resource_info resource = {};
            if (!v79_get_resource_info(
                    barrier.Transition.pResource, resource) ||
                !v79_is_large_texture(resource) ||
                (resource.flags & D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET) == 0)
                continue;
            const D3D12_RESOURCE_STATES before = barrier.Transition.StateBefore;
            const D3D12_RESOURCE_STATES after = barrier.Transition.StateAfter;
            const bool begin = before == D3D12_RESOURCE_STATE_PRESENT &&
                ((after & D3D12_RESOURCE_STATE_RENDER_TARGET) != 0 ||
                 (after & D3D12_RESOURCE_STATE_COPY_DEST) != 0 ||
                 (after & D3D12_RESOURCE_STATE_RESOLVE_DEST) != 0);
            const bool present = after == D3D12_RESOURCE_STATE_PRESENT &&
                ((before & D3D12_RESOURCE_STATE_RENDER_TARGET) != 0 ||
                 (before & D3D12_RESOURCE_STATE_COPY_DEST) != 0 ||
                 (before & D3D12_RESOURCE_STATE_RESOLVE_DEST) != 0);
            if (begin)
            {
                const uint64_t count = s_v79_begin_candidate_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
                {
                    std::lock_guard<std::mutex> lock(s_v79_mutex);
                    s_v79_active_backbuffers[resource.resource_id] = true;
                    s_v79_frame_writers[resource.resource_id].clear();
                }
                if (count <= 8)
                    reshade::log::message(
                        reshade::log::level::info,
                        "D3DMetal RTX presented-frame producer chain v79: BACKBUFFER_BEGIN_CANDIDATE count=%llu resource_id=%llu format=%u dimensions=%llux%u before=0x%X after=0x%X commands_modified=0.",
                        static_cast<unsigned long long>(count),
                        static_cast<unsigned long long>(resource.resource_id),
                        resource.format,
                        static_cast<unsigned long long>(resource.width),
                        resource.height,
                        static_cast<unsigned int>(before),
                        static_cast<unsigned int>(after));
            }
            if (present)
            {
                v79_process_present(barrier.Transition.pResource);
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                s_v79_active_backbuffers[resource.resource_id] = false;
            }
        }
    }

    void STDMETHODCALLTYPE v79_trace_resource_barrier(
        ID3D12GraphicsCommandList *command_list,
        UINT barrier_count, const D3D12_RESOURCE_BARRIER *barriers)
    {
        if (s_v79_original_resource_barrier != nullptr)
            s_v79_original_resource_barrier(
                command_list, barrier_count, barriers);
        v79_observe_barriers(barrier_count, barriers);
    }

    void v79_install_command_list_hooks(
        ID3D12GraphicsCommandList4 *command_list)
    {
        if (command_list == nullptr)
            return;
        std::call_once(
            s_v79_command_hook_once,
            [command_list]()
            {
                void **const vtable = *reinterpret_cast<void ***>(command_list);
                s_v79_original_copy_texture_region =
                    reinterpret_cast<v79_copy_texture_region_fn>(
                        vtable[v79_copy_texture_region_slot]);
                s_v79_original_copy_resource =
                    reinterpret_cast<v79_copy_resource_fn>(
                        vtable[v79_copy_resource_slot]);
                s_v79_original_resolve_subresource =
                    reinterpret_cast<v79_resolve_subresource_fn>(
                        vtable[v79_resolve_subresource_slot]);
                s_v79_original_resource_barrier =
                    reinterpret_cast<v79_resource_barrier_fn>(
                        vtable[v79_resource_barrier_slot]);
                s_v79_original_om_set_render_targets =
                    reinterpret_cast<v79_om_set_render_targets_fn>(
                        vtable[v79_om_set_render_targets_slot]);
                struct patch_entry { size_t slot; void *replacement; };
                const patch_entry patches[] = {
                    { v79_copy_texture_region_slot,
                      reinterpret_cast<void *>(&v79_trace_copy_texture_region) },
                    { v79_copy_resource_slot,
                      reinterpret_cast<void *>(&v79_trace_copy_resource) },
                    { v79_resolve_subresource_slot,
                      reinterpret_cast<void *>(&v79_trace_resolve_subresource) },
                    { v79_resource_barrier_slot,
                      reinterpret_cast<void *>(&v79_trace_resource_barrier) },
                    { v79_om_set_render_targets_slot,
                      reinterpret_cast<void *>(&v79_trace_om_set_render_targets) },
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
                        reinterpret_cast<PVOID volatile *>(
                            &vtable[patch.slot]), patch.replacement);
                    DWORD ignored = 0;
                    VirtualProtect(
                        &vtable[patch.slot], sizeof(void *),
                        old_protect, &ignored);
                    FlushInstructionCache(
                        GetCurrentProcess(), &vtable[patch.slot], sizeof(void *));
                    installed = installed &&
                        vtable[patch.slot] == patch.replacement;
                }
                s_v79_command_hooks_installed.store(
                    installed, std::memory_order_release);
                reshade::log::message(
                    installed ? reshade::log::level::info :
                                reshade::log::level::warning,
                    "D3DMetal RTX presented-frame producer chain v79: COMMAND_HOOKS installed=%u copy_texture_slot=16 copy_resource_slot=17 resolve_slot=19 barrier_slot=26 om_rtv_slot=46 commands_modified=0.",
                    installed ? 1u : 0u);
            });
    }

'''
replace_once(impl_anchor, impl + impl_anchor, 'V79 implementation')

source.write_text(text, encoding='utf-8', newline='\n')
Path('v79-patch-report.txt').write_text(
    '\n'.join([
        'V79_PRESENT_BACKBUFFER_CHAIN_PATCH_OK',
        'RUNTIME_GATE=KAIOZEN_V79_ACTIVE',
        'BACKBUFFER_DETECTION=PRESENT_LIKE_COMMON_TO_OUTPUT_AND_OUTPUT_TO_COMMON',
        'CREATE_RTV_HOOK=YES',
        'OM_SET_RENDER_TARGETS_HOOK=YES',
        'RESOURCE_BARRIER_HOOK=YES',
        'COPY_TEXTURE_HOOK=YES',
        'COPY_RESOURCE_HOOK=YES',
        'RESOLVE_SUBRESOURCE_HOOK=YES',
        'FRAME_WRITER_LIMIT=24',
        'BACKWARD_CHAIN_DEPTH=6',
        'PRESENT_CANDIDATE_FILTER=NEVER_SEEN_AS_SHADER_INPUT',
        'BASELINE_PRESENT_FRAMES=8',
        'POST_SETTINGS_PRESENT_FRAMES=4',
        'SIGNAL_FILE=C:/kaiozen-v79-settings-returned.signal',
        'TRIGGER=RADIAL_SETTINGS_RETURN_TO_WORLD',
        'GPU_READBACK=DISABLED',
        'COMMANDS_MODIFIED=NO',
        'RESULT=PASS',
        '',
    ]), encoding='utf-8', newline='\n')
print('V79_PRESENT_BACKBUFFER_CHAIN_PATCH_OK')
