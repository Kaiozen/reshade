from pathlib import Path
import re

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")
text = source.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: {label} anchor count was {count}, expected 1")
    text = text.replace(old, new, 1)


manifest_anchor = r'''extern "C" __declspec(dllexport) const char *kaiozen_v79_r4_binary_marker_manifest()
{
    static const char manifest[] =
        "V79_R4_BINARY_MARKER_MANIFEST_R4_SUBMITTED_COMMAND_LIST_BOUNDARY\n"
        "D3DMetal RTX presented-frame producer chain v79 R4: ACTIVE\n"
        "SUBMITTED_RING_COMMAND_LIST\n"
        "SUBMITTED_RING_FRAME\n"
        "STATIC_COMMAND_LIST_WRITER_RECOVERY\n"
        "frame-boundary=submitted-command-list-replay\n"
        "recording-time-event-capture=enabled\n"
        "commands_modified=0\n";
    return manifest;
}

namespace
'''
manifest_block = manifest_anchor[:-len("namespace\n")] + r'''extern "C" __declspec(dllexport) const char *kaiozen_v79_r5_binary_marker_manifest()
{
    static const char manifest[] =
        "V79_R5_BINARY_MARKER_MANIFEST_R5_EXECUTE_BUNDLE_GRAPH\n"
        "D3DMetal RTX presented-frame producer chain v79 R5: ACTIVE\n"
        "EXECUTE_BUNDLE_EDGE\n"
        "COMMAND_LIST_RESET_GENERATION\n"
        "BUNDLE_GRAPH_RESOLUTION\n"
        "BUNDLE_RING_FRAME\n"
        "frame-boundary=recursive-submitted-bundle-graph\n"
        "commands_modified=0\n";
    return manifest;
}

namespace
'''
replace_once(manifest_anchor, manifest_block, "V79 R5 exported manifest")


state_anchor = r'''    static constexpr uint64_t v79_r4_max_recorded_events = 12000;
'''
state_block = state_anchor + r'''

    struct v79_r5_command_key
    {
        void *identity = nullptr;
        uint64_t generation = 0;
    };

    struct v79_r5_recorded_operation
    {
        uint32_t kind = 0; // 1 = RTV resource, 2 = ExecuteBundle child.
        uint64_t resource_id = 0;
        void *child_identity = nullptr;
        uint64_t child_generation = 0;
    };

    using v79_r5_reset_fn = HRESULT (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, ID3D12CommandAllocator *,
        ID3D12PipelineState *);
    using v79_r5_execute_bundle_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList *, ID3D12GraphicsCommandList *);

    static std::mutex s_v79_r5_hook_mutex;
    static std::unordered_map<void **, v79_r5_reset_fn>
        s_v79_r5_reset_original_by_vtable;
    static std::unordered_map<void **, v79_r5_execute_bundle_fn>
        s_v79_r5_execute_bundle_original_by_vtable;
    static v79_r5_reset_fn s_v79_r5_reset_fallback = nullptr;
    static v79_r5_execute_bundle_fn s_v79_r5_execute_bundle_fallback = nullptr;

    static std::unordered_map<void *, uint64_t>
        s_v79_r5_generation_by_identity;
    static std::unordered_map<
        void *,
        std::unordered_map<uint64_t, std::vector<v79_r5_recorded_operation>>>
        s_v79_r5_operations_by_identity;

    static std::atomic<uint64_t> s_v79_r5_hook_install_attempt_count = 0;
    static std::atomic<uint64_t> s_v79_r5_hook_install_success_count = 0;
    static std::atomic<uint64_t> s_v79_r5_hook_install_failure_count = 0;
    static std::atomic<uint64_t> s_v79_r5_reset_count = 0;
    static std::atomic<uint64_t> s_v79_r5_bundle_edge_count = 0;
    static std::atomic<uint64_t> s_v79_r5_recorded_operation_count = 0;
    static std::atomic<uint64_t> s_v79_r5_queue_submit_call_count = 0;
    static std::atomic<uint64_t> s_v79_r5_queue_submit_list_count = 0;
    static std::atomic<uint64_t> s_v79_r5_post_strict_submit_call_count = 0;
    static std::atomic<uint64_t> s_v79_r5_post_strict_submit_list_count = 0;
    static std::atomic<uint64_t> s_v79_r5_resolution_hit_count = 0;
    static std::atomic<uint64_t> s_v79_r5_resolution_miss_count = 0;
    static std::atomic<uint64_t> s_v79_r5_post_strict_resolution_hit_count = 0;
    static std::atomic<uint64_t> s_v79_r5_post_strict_resolution_miss_count = 0;
    static std::atomic<uint64_t> s_v79_r5_resolution_ambiguous_count = 0;
    static std::atomic<uint64_t> s_v79_r5_bundle_edges_followed_count = 0;
    static std::atomic<uint64_t> s_v79_r5_bundle_ring_frame_count = 0;
    static uint64_t s_v79_r5_last_resolved_resource = 0;
    static constexpr uint64_t v79_r5_max_recorded_operations = 12000;
    static constexpr uint32_t v79_r5_max_bundle_depth = 8;
'''
replace_once(state_anchor, state_block, "V79 R5 state")


forward_anchor = r'''    void v79_r4_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists);

	void v38_install_execute_command_lists_hook(ID3D12CommandQueue *queue);
'''
forward_block = r'''    void v79_r4_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists);

    void v79_r5_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists);

	void v38_install_execute_command_lists_hook(ID3D12CommandQueue *queue);
'''
replace_once(forward_anchor, forward_block, "V79 R5 execute-list forward declaration")


execute_call_anchor = r'''        v76_on_execute_command_lists(queue, count, command_lists);
        v79_r4_on_execute_command_lists(queue, count, command_lists);

'''
execute_call_block = r'''        v76_on_execute_command_lists(queue, count, command_lists);
        v79_r4_on_execute_command_lists(queue, count, command_lists);
        v79_r5_on_execute_command_lists(queue, count, command_lists);

'''
replace_once(execute_call_anchor, execute_call_block, "V79 R5 execute-list callback")


# V33 already sees every native command list immediately after CreateCommandList or
# CreateCommandList1 succeeds. Bootstrap the R5 Reset/ExecuteBundle hooks there,
# rather than waiting for a later OMSetRenderTargets call that may occur after an
# ExecuteBundle edge has already been recorded.
v33_marker = "D3DMetal RTX execution trace v33: COMMAND_LIST_HOOKS installed="
v33_marker_pos = text.find(v33_marker)
if v33_marker_pos < 0:
    raise SystemExit("ERROR: V33 command-list hook marker is missing")
v33_prefix = text[:v33_marker_pos]
v33_candidates = list(re.finditer(
    r"(?:void|bool)\s+(v33_[A-Za-z0-9_]*command_list[A-Za-z0-9_]*)\s*"
    r"\(\s*ID3D12GraphicsCommandList(?:[1-9])?\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\{",
    v33_prefix,
))
if not v33_candidates:
    raise SystemExit("ERROR: could not locate the V33 command-list hook installer")
v33_match = v33_candidates[-1]
v33_parameter = v33_match.group(2)
v33_function_start = v33_match.start()
v33_body_open = v33_match.end()
v33_forward = (
    "    void v79_r5_install_command_list_hooks(\n"
    "        ID3D12GraphicsCommandList *command_list);\n\n"
)
text = (
    text[:v33_function_start] + v33_forward +
    text[v33_function_start:]
)
v33_body_open += len(v33_forward)
v33_bootstrap = (
    "\n        // V79_R5_EARLY_COMMAND_LIST_BOOTSTRAP\n"
    "        v79_r5_install_command_list_hooks(\n"
    "            reinterpret_cast<ID3D12GraphicsCommandList *>("
    + v33_parameter + "));"
)
text = text[:v33_body_open] + v33_bootstrap + text[v33_body_open:]


helper_anchor = r'''    void v79_r4_recover_locked_writer_metadata()
'''
helper_block = r'''    uint64_t v79_r5_current_generation(void *identity)
    {
        if (identity == nullptr)
            return 0;
        std::lock_guard<std::mutex> lock(s_v79_mutex);
        return s_v79_r5_generation_by_identity[identity];
    }

    bool v79_r5_key_seen(
        const std::vector<v79_r5_command_key> &visited,
        void *identity,
        uint64_t generation)
    {
        return std::find_if(
            visited.begin(), visited.end(),
            [identity, generation](const v79_r5_command_key &key)
            {
                return key.identity == identity &&
                    key.generation == generation;
            }) != visited.end();
    }

    v79_r5_reset_fn v79_r5_lookup_reset_original(
        ID3D12GraphicsCommandList *command_list)
    {
        if (command_list == nullptr)
            return nullptr;
        void **vtable = *reinterpret_cast<void ***>(command_list);
        std::lock_guard<std::mutex> lock(s_v79_r5_hook_mutex);
        const auto found = s_v79_r5_reset_original_by_vtable.find(vtable);
        return found != s_v79_r5_reset_original_by_vtable.end() ?
            found->second : s_v79_r5_reset_fallback;
    }

    v79_r5_execute_bundle_fn v79_r5_lookup_execute_bundle_original(
        ID3D12GraphicsCommandList *command_list)
    {
        if (command_list == nullptr)
            return nullptr;
        void **vtable = *reinterpret_cast<void ***>(command_list);
        std::lock_guard<std::mutex> lock(s_v79_r5_hook_mutex);
        const auto found =
            s_v79_r5_execute_bundle_original_by_vtable.find(vtable);
        return found != s_v79_r5_execute_bundle_original_by_vtable.end() ?
            found->second : s_v79_r5_execute_bundle_fallback;
    }

    HRESULT STDMETHODCALLTYPE v79_r5_trace_reset(
        ID3D12GraphicsCommandList *command_list,
        ID3D12CommandAllocator *allocator,
        ID3D12PipelineState *initial_state);

    void STDMETHODCALLTYPE v79_r5_trace_execute_bundle(
        ID3D12GraphicsCommandList *command_list,
        ID3D12GraphicsCommandList *bundle);

    void v79_r5_install_command_list_hooks(
        ID3D12GraphicsCommandList *command_list)
    {
        if (!v79_is_active() || command_list == nullptr)
            return;

        s_v79_r5_hook_install_attempt_count.fetch_add(
            1, std::memory_order_acq_rel);
        void **vtable = *reinterpret_cast<void ***>(command_list);
        if (vtable == nullptr)
            return;

        bool reset_installed = false;
        bool bundle_installed = false;
        bool failed = false;
        {
            std::lock_guard<std::mutex> lock(s_v79_r5_hook_mutex);
            reset_installed =
                s_v79_r5_reset_original_by_vtable.find(vtable) !=
                s_v79_r5_reset_original_by_vtable.end();
            bundle_installed =
                s_v79_r5_execute_bundle_original_by_vtable.find(vtable) !=
                s_v79_r5_execute_bundle_original_by_vtable.end();
            if (reset_installed && bundle_installed)
                return;

            if (!reset_installed)
            {
                void **slot = vtable + 10;
                DWORD old_protection = 0;
                if (!VirtualProtect(
                        slot, sizeof(void *), PAGE_EXECUTE_READWRITE,
                        &old_protection))
                {
                    failed = true;
                }
                else
                {
                    void *original = InterlockedExchangePointer(
                        reinterpret_cast<PVOID volatile *>(slot),
                        reinterpret_cast<void *>(&v79_r5_trace_reset));
                    DWORD ignored = 0;
                    VirtualProtect(
                        slot, sizeof(void *), old_protection, &ignored);
                    if (original != nullptr &&
                        original != reinterpret_cast<void *>(
                            &v79_r5_trace_reset))
                    {
                        const auto typed = reinterpret_cast<v79_r5_reset_fn>(
                            original);
                        s_v79_r5_reset_original_by_vtable[vtable] = typed;
                        if (s_v79_r5_reset_fallback == nullptr)
                            s_v79_r5_reset_fallback = typed;
                        reset_installed = true;
                    }
                    else if (original == reinterpret_cast<void *>(
                                 &v79_r5_trace_reset) &&
                             s_v79_r5_reset_fallback != nullptr)
                    {
                        s_v79_r5_reset_original_by_vtable[vtable] =
                            s_v79_r5_reset_fallback;
                        reset_installed = true;
                    }
                    else
                    {
                        failed = true;
                    }
                }
            }

            if (!bundle_installed)
            {
                void **slot = vtable + 27;
                DWORD old_protection = 0;
                if (!VirtualProtect(
                        slot, sizeof(void *), PAGE_EXECUTE_READWRITE,
                        &old_protection))
                {
                    failed = true;
                }
                else
                {
                    void *original = InterlockedExchangePointer(
                        reinterpret_cast<PVOID volatile *>(slot),
                        reinterpret_cast<void *>(
                            &v79_r5_trace_execute_bundle));
                    DWORD ignored = 0;
                    VirtualProtect(
                        slot, sizeof(void *), old_protection, &ignored);
                    if (original != nullptr &&
                        original != reinterpret_cast<void *>(
                            &v79_r5_trace_execute_bundle))
                    {
                        const auto typed =
                            reinterpret_cast<v79_r5_execute_bundle_fn>(
                                original);
                        s_v79_r5_execute_bundle_original_by_vtable[vtable] =
                            typed;
                        if (s_v79_r5_execute_bundle_fallback == nullptr)
                            s_v79_r5_execute_bundle_fallback = typed;
                        bundle_installed = true;
                    }
                    else if (original == reinterpret_cast<void *>(
                                 &v79_r5_trace_execute_bundle) &&
                             s_v79_r5_execute_bundle_fallback != nullptr)
                    {
                        s_v79_r5_execute_bundle_original_by_vtable[vtable] =
                            s_v79_r5_execute_bundle_fallback;
                        bundle_installed = true;
                    }
                    else
                    {
                        failed = true;
                    }
                }
            }
        }

        if (reset_installed && bundle_installed)
        {
            const uint64_t success =
                s_v79_r5_hook_install_success_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            if (success <= 8)
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R5: COMMAND_LIST_HOOKS installed=1 success=%llu command_list=%p vtable=%p reset_slot=10 execute_bundle_slot=27 commands_modified=0.",
                    static_cast<unsigned long long>(success), command_list,
                    vtable);
        }
        else if (failed)
        {
            const uint64_t failures =
                s_v79_r5_hook_install_failure_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            if (failures <= 8)
                reshade::log::message(
                    reshade::log::level::warning,
                    "D3DMetal RTX presented-frame producer chain v79 R5: COMMAND_LIST_HOOKS installed=0 failure=%llu command_list=%p vtable=%p reset_installed=%u execute_bundle_installed=%u commands_modified=0.",
                    static_cast<unsigned long long>(failures), command_list,
                    vtable, reset_installed ? 1u : 0u,
                    bundle_installed ? 1u : 0u);
        }
    }

    void v79_r5_record_rtv_event(
        ID3D12GraphicsCommandList *command_list,
        const std::vector<uint64_t> &resources)
    {
        if (!v79_is_active() || command_list == nullptr || resources.empty())
            return;
        void *const identity = v33_identity_pointer(
            reinterpret_cast<IUnknown *>(command_list));
        if (identity == nullptr)
            return;

        std::lock_guard<std::mutex> lock(s_v79_mutex);
        const uint64_t generation =
            s_v79_r5_generation_by_identity[identity];
        auto &operations =
            s_v79_r5_operations_by_identity[identity][generation];
        for (const uint64_t resource_id : resources)
        {
            if (resource_id == 0 ||
                s_v79_r5_recorded_operation_count.load(
                    std::memory_order_acquire) >=
                    v79_r5_max_recorded_operations)
                break;
            if (!operations.empty() && operations.back().kind == 1 &&
                operations.back().resource_id == resource_id)
                continue;
            v79_r5_recorded_operation operation = {};
            operation.kind = 1;
            operation.resource_id = resource_id;
            operations.push_back(operation);
            s_v79_r5_recorded_operation_count.fetch_add(
                1, std::memory_order_acq_rel);
        }
    }

    void v79_r5_on_reset(ID3D12GraphicsCommandList *command_list)
    {
        if (!v79_is_active() || command_list == nullptr)
            return;
        void *const identity = v33_identity_pointer(
            reinterpret_cast<IUnknown *>(command_list));
        if (identity == nullptr)
            return;

        uint64_t generation = 0;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            generation = ++s_v79_r5_generation_by_identity[identity];
            s_v79_r5_operations_by_identity[identity][generation].clear();
        }
        const uint64_t reset = s_v79_r5_reset_count.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        if (reset <= 16 || reset % 128 == 0)
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R5: COMMAND_LIST_RESET_GENERATION reset=%llu command_list=%p identity=%p generation=%llu commands_modified=0.",
                static_cast<unsigned long long>(reset), command_list,
                identity, static_cast<unsigned long long>(generation));
    }

    void v79_r5_on_execute_bundle(
        ID3D12GraphicsCommandList *command_list,
        ID3D12GraphicsCommandList *bundle)
    {
        if (!v79_is_active() || command_list == nullptr || bundle == nullptr)
            return;
        v79_r5_install_command_list_hooks(command_list);
        v79_r5_install_command_list_hooks(bundle);

        void *const parent_identity = v33_identity_pointer(
            reinterpret_cast<IUnknown *>(command_list));
        void *const child_identity = v33_identity_pointer(
            reinterpret_cast<IUnknown *>(bundle));
        if (parent_identity == nullptr || child_identity == nullptr)
            return;

        uint64_t parent_generation = 0;
        uint64_t child_generation = 0;
        bool recorded = false;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            parent_generation =
                s_v79_r5_generation_by_identity[parent_identity];
            child_generation =
                s_v79_r5_generation_by_identity[child_identity];
            if (s_v79_r5_recorded_operation_count.load(
                    std::memory_order_acquire) <
                v79_r5_max_recorded_operations)
            {
                auto &operations =
                    s_v79_r5_operations_by_identity[parent_identity]
                                                     [parent_generation];
                v79_r5_recorded_operation operation = {};
                operation.kind = 2;
                operation.child_identity = child_identity;
                operation.child_generation = child_generation;
                operations.push_back(operation);
                s_v79_r5_recorded_operation_count.fetch_add(
                    1, std::memory_order_acq_rel);
                recorded = true;
            }
        }

        if (recorded)
        {
            const uint64_t edge = s_v79_r5_bundle_edge_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
            if (edge <= 32 || edge % 128 == 0)
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R5: EXECUTE_BUNDLE_EDGE edge=%llu parent=%p parent_identity=%p parent_generation=%llu child=%p child_identity=%p child_generation=%llu operation_count=%llu commands_modified=0.",
                    static_cast<unsigned long long>(edge), command_list,
                    parent_identity,
                    static_cast<unsigned long long>(parent_generation),
                    bundle, child_identity,
                    static_cast<unsigned long long>(child_generation),
                    static_cast<unsigned long long>(
                        s_v79_r5_recorded_operation_count.load(
                            std::memory_order_acquire)));
        }
    }

    HRESULT STDMETHODCALLTYPE v79_r5_trace_reset(
        ID3D12GraphicsCommandList *command_list,
        ID3D12CommandAllocator *allocator,
        ID3D12PipelineState *initial_state)
    {
        const v79_r5_reset_fn original =
            v79_r5_lookup_reset_original(command_list);
        if (original == nullptr)
        {
            reshade::log::message(
                reshade::log::level::error,
                "D3DMetal RTX presented-frame producer chain v79 R5: RESET_FORWARD_FAILURE command_list=%p reason=original-not-found commands_modified=0.",
                command_list);
            return E_FAIL;
        }
        const HRESULT result = original(
            command_list, allocator, initial_state);
        if (SUCCEEDED(result))
            v79_r5_on_reset(command_list);
        return result;
    }

    void STDMETHODCALLTYPE v79_r5_trace_execute_bundle(
        ID3D12GraphicsCommandList *command_list,
        ID3D12GraphicsCommandList *bundle)
    {
        v79_r5_on_execute_bundle(command_list, bundle);
        const v79_r5_execute_bundle_fn original =
            v79_r5_lookup_execute_bundle_original(command_list);
        if (original == nullptr)
        {
            reshade::log::message(
                reshade::log::level::error,
                "D3DMetal RTX presented-frame producer chain v79 R5: EXECUTE_BUNDLE_FORWARD_FAILURE command_list=%p bundle=%p reason=original-not-found commands_modified=0.",
                command_list, bundle);
            return;
        }
        original(command_list, bundle);
    }

    void v79_r5_collect_locked_resources(
        void *identity,
        uint64_t generation,
        uint32_t depth,
        std::vector<v79_r5_command_key> &visited,
        std::vector<uint64_t> &resources,
        uint64_t &bundle_edges_followed)
    {
        if (identity == nullptr || depth > v79_r5_max_bundle_depth ||
            v79_r5_key_seen(visited, identity, generation))
            return;
        visited.push_back({ identity, generation });

        std::vector<v79_r5_recorded_operation> operations;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            const auto identity_found =
                s_v79_r5_operations_by_identity.find(identity);
            if (identity_found == s_v79_r5_operations_by_identity.end())
                return;
            const auto generation_found =
                identity_found->second.find(generation);
            if (generation_found == identity_found->second.end())
                return;
            operations = generation_found->second;
        }

        for (const v79_r5_recorded_operation &operation : operations)
        {
            if (operation.kind == 1 && operation.resource_id != 0)
            {
                bool locked_resource = false;
                {
                    std::lock_guard<std::mutex> lock(s_v79_mutex);
                    const auto found = s_v79_r3_locked_resources.find(
                        operation.resource_id);
                    locked_resource =
                        found != s_v79_r3_locked_resources.end() &&
                        found->second;
                }
                if (locked_resource &&
                    (resources.empty() ||
                     resources.back() != operation.resource_id))
                    resources.push_back(operation.resource_id);
            }
            else if (operation.kind == 2 &&
                     operation.child_identity != nullptr)
            {
                ++bundle_edges_followed;
                v79_r5_collect_locked_resources(
                    operation.child_identity,
                    operation.child_generation,
                    depth + 1, visited, resources,
                    bundle_edges_followed);
            }
        }
    }

    void v79_r5_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists)
    {
        (void)queue;
        if (!v79_is_active() || command_lists == nullptr ||
            !s_v79_r3_triplet_locked.load(std::memory_order_acquire) ||
            s_v79_result_ready.load(std::memory_order_acquire))
            return;

        const bool strict = s_v61_rewritten_steady_state_seen.load(
            std::memory_order_acquire);
        const uint64_t submit_call =
            s_v79_r5_queue_submit_call_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
        s_v79_r5_queue_submit_list_count.fetch_add(
            count, std::memory_order_acq_rel);
        uint64_t post_strict_submit_call =
            s_v79_r5_post_strict_submit_call_count.load(
                std::memory_order_acquire);
        uint64_t post_strict_submit_lists =
            s_v79_r5_post_strict_submit_list_count.load(
                std::memory_order_acquire);
        if (strict)
        {
            post_strict_submit_call =
                s_v79_r5_post_strict_submit_call_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            post_strict_submit_lists =
                s_v79_r5_post_strict_submit_list_count.fetch_add(
                    count, std::memory_order_acq_rel) + count;
        }

        std::vector<uint64_t> submitted_resources;
        uint64_t edges_followed = 0;
        uint64_t resolved_lists = 0;
        for (UINT index = 0; index < count; ++index)
        {
            ID3D12CommandList *list = nullptr;
            if (!safe_copy_from_process(
                    command_lists + index, &list, sizeof(list)) ||
                list == nullptr)
                continue;

            ID3D12GraphicsCommandList *graphics_list =
                reinterpret_cast<ID3D12GraphicsCommandList *>(list);
            v79_r5_install_command_list_hooks(graphics_list);
            void *const identity = v33_identity_pointer(
                reinterpret_cast<IUnknown *>(list));
            if (identity == nullptr)
                continue;
            const uint64_t generation =
                v79_r5_current_generation(identity);
            std::vector<v79_r5_command_key> visited;
            std::vector<uint64_t> resolved;
            uint64_t list_edges = 0;
            v79_r5_collect_locked_resources(
                identity, generation, 0, visited, resolved, list_edges);
            edges_followed += list_edges;
            if (!resolved.empty())
                ++resolved_lists;
            for (const uint64_t resource_id : resolved)
            {
                if (submitted_resources.empty() ||
                    submitted_resources.back() != resource_id)
                    submitted_resources.push_back(resource_id);
            }
        }
        s_v79_r5_bundle_edges_followed_count.fetch_add(
            edges_followed, std::memory_order_acq_rel);

        if (submit_call <= 16 || submit_call % 120 == 0 ||
            (strict && post_strict_submit_call == 1))
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R5: QUEUE_SUBMIT submit_call=%llu command_list_count=%u raw_submit_calls=%llu raw_submit_lists=%llu post_strict_submit_calls=%llu post_strict_submit_lists=%llu resolved_lists=%llu bundle_edges_followed=%llu recorded_bundle_edges=%llu reset_generations=%llu hook_successes=%llu strict_rewritten_proof=%u commands_modified=0.",
                static_cast<unsigned long long>(submit_call), count,
                static_cast<unsigned long long>(
                    s_v79_r5_queue_submit_call_count.load(
                        std::memory_order_acquire)),
                static_cast<unsigned long long>(
                    s_v79_r5_queue_submit_list_count.load(
                        std::memory_order_acquire)),
                static_cast<unsigned long long>(
                    s_v79_r5_post_strict_submit_call_count.load(
                        std::memory_order_acquire)),
                static_cast<unsigned long long>(
                    s_v79_r5_post_strict_submit_list_count.load(
                        std::memory_order_acquire)),
                static_cast<unsigned long long>(resolved_lists),
                static_cast<unsigned long long>(edges_followed),
                static_cast<unsigned long long>(
                    s_v79_r5_bundle_edge_count.load(
                        std::memory_order_acquire)),
                static_cast<unsigned long long>(
                    s_v79_r5_reset_count.load(
                        std::memory_order_acquire)),
                static_cast<unsigned long long>(
                    s_v79_r5_hook_install_success_count.load(
                        std::memory_order_acquire)),
                strict ? 1u : 0u);

        if (submitted_resources.empty())
        {
            const uint64_t miss =
                s_v79_r5_resolution_miss_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            uint64_t post_strict_miss =
                s_v79_r5_post_strict_resolution_miss_count.load(
                    std::memory_order_acquire);
            if (strict)
                post_strict_miss =
                    s_v79_r5_post_strict_resolution_miss_count.fetch_add(
                        1, std::memory_order_acq_rel) + 1;
            if (miss <= 16 || miss % 120 == 0 ||
                (strict && post_strict_miss == 1))
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R5: BUNDLE_GRAPH_RESOLUTION hit=0 miss=%llu post_strict_resolution_misses=%llu submit_call=%llu command_list_count=%u bundle_edges_followed=%llu reason=no-recursive-path-to-frozen-triplet strict_rewritten_proof=%u commands_modified=0.",
                    static_cast<unsigned long long>(miss),
                    static_cast<unsigned long long>(
                        s_v79_r5_post_strict_resolution_miss_count.load(
                            std::memory_order_acquire)),
                    static_cast<unsigned long long>(submit_call), count,
                    static_cast<unsigned long long>(edges_followed),
                    strict ? 1u : 0u);
            return;
        }

        const uint64_t hit = s_v79_r5_resolution_hit_count.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        uint64_t post_strict_hit =
            s_v79_r5_post_strict_resolution_hit_count.load(
                std::memory_order_acquire);
        if (strict)
            post_strict_hit =
                s_v79_r5_post_strict_resolution_hit_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
        std::vector<uint64_t> distinct;
        for (const uint64_t resource_id : submitted_resources)
            if (std::find(distinct.begin(), distinct.end(), resource_id) ==
                distinct.end())
                distinct.push_back(resource_id);
        const bool ambiguous = distinct.size() > 1;
        if (ambiguous)
            s_v79_r5_resolution_ambiguous_count.fetch_add(
                1, std::memory_order_acq_rel);

        if (hit <= 32 || hit % 120 == 0 ||
            (strict && post_strict_hit == 1))
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R5: BUNDLE_GRAPH_RESOLUTION hit=1 resolution_hit=%llu post_strict_resolution_hits=%llu submit_call=%llu command_list_count=%u resolved_lists=%llu resolved_resource_events=%zu distinct_triplet_resources=%zu bundle_edges_followed=%llu ambiguous_submission=%u strict_rewritten_proof=%u commands_modified=0.",
                static_cast<unsigned long long>(hit),
                static_cast<unsigned long long>(
                    s_v79_r5_post_strict_resolution_hit_count.load(
                        std::memory_order_acquire)),
                static_cast<unsigned long long>(submit_call), count,
                static_cast<unsigned long long>(resolved_lists),
                submitted_resources.size(), distinct.size(),
                static_cast<unsigned long long>(edges_followed),
                ambiguous ? 1u : 0u, strict ? 1u : 0u);

        for (const uint64_t current : submitted_resources)
        {
            uint64_t previous = 0;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                previous = s_v79_r5_last_resolved_resource;
                s_v79_r5_last_resolved_resource = current;
            }
            if (!strict || previous == 0 || previous == current)
                continue;

            v55_resource_info previous_info = {};
            if (!v55_get_resource(previous, previous_info) ||
                previous_info.resource == nullptr)
                continue;

            const uint64_t frame =
                s_v79_r5_bundle_ring_frame_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            if (frame <= 24 || frame % 120 == 0)
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R5: BUNDLE_RING_FRAME frame=%llu completed_resource_id=%llu next_resource_id=%llu format=%u dimensions=%llux%u boundary=recursive-submitted-bundle-graph bundle_edges_followed=%llu ambiguous_submission=%u commands_modified=0.",
                    static_cast<unsigned long long>(frame),
                    static_cast<unsigned long long>(previous),
                    static_cast<unsigned long long>(current),
                    previous_info.format,
                    static_cast<unsigned long long>(previous_info.width),
                    previous_info.height,
                    static_cast<unsigned long long>(edges_followed),
                    ambiguous ? 1u : 0u);
            v79_process_present(previous_info.resource);
        }
    }

    void v79_r4_recover_locked_writer_metadata()
'''
replace_once(helper_anchor, helper_block, "V79 R5 bundle graph helpers")


om_tail_anchor = r'''        v79_r3_observe_rtv_sequence(resources);
        v79_r4_recover_locked_writer_metadata();
'''
om_tail_block = r'''        v79_r5_install_command_list_hooks(command_list);
        v79_r5_record_rtv_event(command_list, resources);
        v79_r3_observe_rtv_sequence(resources);
        v79_r4_recover_locked_writer_metadata();
'''
replace_once(om_tail_anchor, om_tail_block, "V79 R5 RTV operation stream")


active_log_anchor = r'''                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R4: ACTIVE frozen-triplet-source=recording-time-OMSetRenderTargets frame-boundary=submitted-command-list-replay command-list-identity-map=enabled static-command-list-writer-recovery=enabled recording-time-event-capture=enabled strict-lineage-required-for-present-capture=1 GPU-readback=disabled injected-copies=disabled injected-barriers=disabled commands_modified=0.");'''
active_log_block = active_log_anchor + r'''
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R5: ACTIVE frozen-triplet-source=R3 recording-time-OMSetRenderTargets frame-boundary=recursive-submitted-bundle-graph execute-bundle-slot=27 reset-slot=10 generation-tracking=enabled ordered-operation-stream=enabled max-bundle-depth=8 raw-post-strict-submission-counters=enabled static-command-list-writer-recovery=R4 strict-lineage-required-for-present-capture=1 GPU-readback=disabled injected-copies=disabled injected-barriers=disabled commands_modified=0.");'''
replace_once(active_log_anchor, active_log_block, "V79 R5 active log")


source.write_text(text, encoding="utf-8")

Path("v79-r5-patch-report.txt").write_text(
    "\n".join([
        "V79_R5_EXECUTE_BUNDLE_GRAPH_PATCH_OK",
        "BINARY_MANIFEST=V79_R5_BINARY_MARKER_MANIFEST_R5_EXECUTE_BUNDLE_GRAPH",
        "TRIPLET_SOURCE=V79_R3_FROZEN_RECORDING_TIME_TRIPLET",
        "STATIC_WRITER_RECOVERY=V79_R4",
        "EXECUTE_BUNDLE_SLOT=27",
        "EARLY_COMMAND_LIST_BOOTSTRAP=V33_CREATE_COMMAND_LIST_PATH",
        "COMMAND_LIST_RESET_SLOT=10",
        "GENERATION_TRACKING=ENABLED",
        "ORDERED_OPERATION_STREAM=RTV_AND_EXECUTE_BUNDLE",
        "FRAME_BOUNDARY=RECURSIVE_SUBMITTED_BUNDLE_GRAPH",
        "MAX_BUNDLE_DEPTH=8",
        "RAW_POST_STRICT_SUBMISSION_COUNTERS=ENABLED",
        "GPU_READBACK=DISABLED",
        "INJECTED_COPIES=DISABLED",
        "INJECTED_BARRIERS=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)

print("V79_R5_EXECUTE_BUNDLE_GRAPH_PATCH_OK")
