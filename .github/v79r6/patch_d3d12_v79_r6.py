from pathlib import Path
import re
import traceback

source = Path("source/d3d12/d3d12.cpp")
diagnostic_path = Path("v79-r6-patcher-diagnostics.txt")
diagnostics = [
    "V79_R6_PATCHER_DIAGNOSTICS",
    "ANCHOR_MODE=MARKER_DRIVEN_REGEX",
    "EXPERIMENT=TRIPLET_TOUCH_COMMAND_STREAM_CENSUS",
]

def save_diagnostics():
    diagnostic_path.write_text("\n".join(diagnostics) + "\n", encoding="utf-8")

def note(stage, detail="PASS"):
    line = f"PATCH_STAGE={stage} {detail}"
    diagnostics.append(line)
    print(line, flush=True)
    save_diagnostics()

def fail(stage, detail):
    line = f"V79_R6_PATCHER_ERROR stage={stage} detail={detail}"
    diagnostics.append(line)
    print(line, flush=True)
    save_diagnostics()
    raise SystemExit(1)

def unique_regex(pattern, stage, flags=re.M | re.S):
    matches = list(re.finditer(pattern, text, flags))
    if len(matches) != 1:
        fail(stage, f"regex_match_count={len(matches)} pattern={pattern!r}")
    return matches[0]

def matching_brace(open_index, stage):
    depth = 0
    in_string = False
    quote = ""
    escape = False
    i = open_index
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_string = True
            quote = ch
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    fail(stage, "matching_closing_brace_not_found")

if not source.is_file():
    fail("source", "source/d3d12/d3d12.cpp_is_missing")
text = source.read_text(encoding="utf-8")
if "kaiozen_v79_r6_binary_marker_manifest" in text:
    fail("preflight", "source_already_contains_v79_r6")
for marker in [
    "kaiozen_v79_r5_binary_marker_manifest",
    "V79_R5_HOTFIX2_MARKER_DRIVEN_PATCHER",
    "v79_r5_current_generation",
    "v79_trace_copy_texture_region",
    "v79_trace_copy_resource",
    "v79_trace_resolve_subresource",
    "v79_trace_resource_barrier",
    "v79_resolve_rtv_handle",
]:
    if marker not in text:
        fail("preflight", f"missing_r5_marker={marker}")
note("preflight")

try:
    # 1. Exported manifest after R5.
    m = unique_regex(
        r'extern\s+"C"\s+__declspec\s*\(\s*dllexport\s*\)\s+const\s+char\s*\*\s*'
        r'kaiozen_v79_r5_binary_marker_manifest\s*\(\s*\)\s*\{',
        "manifest")
    ob = text.find('{', m.start())
    cb = matching_brace(ob, "manifest")
    manifest = r'''

extern "C" __declspec(dllexport) const char *kaiozen_v79_r6_binary_marker_manifest()
{
    static const char manifest[] =
        "V79_R6_BINARY_MARKER_MANIFEST_TRIPLET_TOUCH_CENSUS\n"
        "D3DMetal RTX presented-frame producer chain v79 R6: ACTIVE\n"
        "TRIPLET_TOUCH_RECORD\n"
        "TRIPLET_TOUCH_QUEUE_RESOLUTION\n"
        "TRIPLET_TOUCH_ROTATION\n"
        "V79_R6_TRIPLET_TOUCH_PATH_FOUND\n"
        "copy-texture=observed\n"
        "copy-resource=observed\n"
        "resolve-subresource=observed\n"
        "resolve-subresource-region=observed\n"
        "legacy-resource-barrier=observed\n"
        "begin-render-pass=observed\n"
        "commands_modified=0\n";
    return manifest;
}
'''
    text = text[:cb+1] + manifest + text[cb+1:]
    note("manifest")

    # 2. State after R5 cap.
    m = unique_regex(
        r'(?m)^[ \t]*static\s+constexpr\s+uint32_t\s+'
        r'v79_r5_max_bundle_depth\s*=\s*8\s*;', "state")
    state = r'''

    struct v79_r6_touch_operation
    {
        uint32_t kind = 0;
        uint64_t resource_id = 0;
        bool write = false;
        uint32_t before_state = 0;
        uint32_t after_state = 0;
    };

    using v79_r6_resolve_region_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList1 *, ID3D12Resource *, UINT, UINT, UINT,
        ID3D12Resource *, UINT, const D3D12_RECT *, DXGI_FORMAT,
        D3D12_RESOLVE_MODE);
    using v79_r6_begin_render_pass_fn = void (STDMETHODCALLTYPE *)(
        ID3D12GraphicsCommandList4 *, UINT,
        const D3D12_RENDER_PASS_RENDER_TARGET_DESC *,
        const D3D12_RENDER_PASS_DEPTH_STENCIL_DESC *,
        D3D12_RENDER_PASS_FLAGS);

    static std::mutex s_v79_r6_hook_mutex;
    static std::unordered_map<void **, v79_r6_resolve_region_fn>
        s_v79_r6_resolve_region_original_by_vtable;
    static std::unordered_map<void **, v79_r6_begin_render_pass_fn>
        s_v79_r6_begin_render_pass_original_by_vtable;
    static v79_r6_resolve_region_fn s_v79_r6_resolve_region_fallback = nullptr;
    static v79_r6_begin_render_pass_fn s_v79_r6_begin_render_pass_fallback = nullptr;
    static std::unordered_map<
        void *,
        std::unordered_map<uint64_t, std::vector<v79_r6_touch_operation>>>
        s_v79_r6_touches_by_identity;
    static std::unordered_map<uint64_t, bool>
        s_v79_r6_post_strict_resources;

    static std::atomic<uint64_t> s_v79_r6_hook_success_count = 0;
    static std::atomic<uint64_t> s_v79_r6_hook_failure_count = 0;
    static std::atomic<uint64_t> s_v79_r6_total_touch_count = 0;
    static std::atomic<uint64_t> s_v79_r6_locked_touch_count = 0;
    static std::atomic<uint64_t> s_v79_r6_copy_texture_count = 0;
    static std::atomic<uint64_t> s_v79_r6_copy_resource_count = 0;
    static std::atomic<uint64_t> s_v79_r6_resolve_count = 0;
    static std::atomic<uint64_t> s_v79_r6_resolve_region_count = 0;
    static std::atomic<uint64_t> s_v79_r6_legacy_barrier_count = 0;
    static std::atomic<uint64_t> s_v79_r6_begin_render_pass_count = 0;
    static std::atomic<uint64_t> s_v79_r6_submit_call_count = 0;
    static std::atomic<uint64_t> s_v79_r6_submit_list_count = 0;
    static std::atomic<uint64_t> s_v79_r6_resolution_hit_count = 0;
    static std::atomic<uint64_t> s_v79_r6_resolution_miss_count = 0;
    static std::atomic<uint64_t> s_v79_r6_post_strict_write_hit_count = 0;
    static std::atomic<uint64_t> s_v79_r6_post_strict_read_hit_count = 0;
    static std::atomic<uint64_t> s_v79_r6_post_strict_miss_count = 0;
    static std::atomic<uint64_t> s_v79_r6_rotation_count = 0;
    static std::atomic<bool> s_v79_r6_path_found = false;
    static uint64_t s_v79_r6_last_write_resource = 0;
    static constexpr uint64_t v79_r6_max_recorded_touches = 200000;
    static constexpr size_t v79_r6_resolve_subresource_region_slot = 64;
    static constexpr size_t v79_r6_begin_render_pass_slot = 68;
'''
    text = text[:m.end()] + state + text[m.end():]
    note("state")

    # 3. Forward declaration and queue callback.
    qdecl = unique_regex(
        r'(?m)^(?P<i>[ \t]*)void\s+v38_install_execute_command_lists_hook\s*'
        r'\(\s*ID3D12CommandQueue\s*\*\s*queue\s*\)\s*;', "queue_forward")
    i = qdecl.group('i')
    fwd = (i + "void v79_r6_on_execute_command_lists(\n" +
           i + "    ID3D12CommandQueue *queue, UINT count,\n" +
           i + "    ID3D12CommandList *const *command_lists);\n\n")
    text = text[:qdecl.start()] + fwd + text[qdecl.start():]
    qcall = unique_regex(
        r'(?m)^(?P<i>[ \t]*)v79_r5_on_execute_command_lists\s*'
        r'\(\s*queue\s*,\s*count\s*,\s*command_lists\s*\)\s*;', "queue_callback")
    i = qcall.group('i')
    text = text[:qcall.end()] + "\n" + i + \
        "v79_r6_on_execute_command_lists(queue, count, command_lists);" + text[qcall.end():]
    note("queue_chain")

    # 4. Early hook bootstrap declaration/call in V33 helper.
    helper = unique_regex(
        r'(?m)^(?P<i>[ \t]*)(?:static\s+)?void\s+'
        r'v33_install_command_list_method_hooks\s*\(\s*IUnknown\s*\*\s*'
        r'(?:const\s+)?command_list\s*\)\s*\{', "v33_helper")
    declaration = "\n\tvoid v79_r6_install_command_list_hooks(\n\t    IUnknown *command_list);\n"
    text = text[:helper.start()] + declaration + text[helper.start():]
    helper = unique_regex(
        r'(?m)^(?P<i>[ \t]*)(?:static\s+)?void\s+'
        r'v33_install_command_list_method_hooks\s*\(\s*IUnknown\s*\*\s*'
        r'(?:const\s+)?command_list\s*\)\s*\{', "v33_helper_after_decl")
    ob = text.find('{', helper.start())
    body = ('\n\t    // V79_R6_EARLY_COMMAND_LIST_BOOTSTRAP\n'
            '\t    v79_r6_install_command_list_hooks(command_list);')
    text = text[:ob+1] + body + text[ob+1:]
    note("v33_bootstrap")

    # 5. R6 helpers immediately before the R5 reset lookup.
    anchor = unique_regex(
        r'(?m)^[ \t]*v79_r5_reset_fn\s+v79_r5_lookup_reset_original\s*\(',
        "helpers_anchor")
    helpers = r'''
    const char *v79_r6_kind_name(uint32_t kind)
    {
        switch (kind)
        {
        case 1: return "copy-texture-destination";
        case 2: return "copy-texture-source";
        case 3: return "copy-resource-destination";
        case 4: return "copy-resource-source";
        case 5: return "resolve-destination";
        case 6: return "resolve-source";
        case 7: return "resolve-region-destination";
        case 8: return "resolve-region-source";
        case 9: return "legacy-resource-barrier";
        case 10: return "begin-render-pass";
        default: return "unknown";
        }
    }

    bool v79_r6_is_locked_resource(uint64_t resource_id)
    {
        std::lock_guard<std::mutex> lock(s_v79_mutex);
        const auto found = s_v79_r3_locked_resources.find(resource_id);
        return found != s_v79_r3_locked_resources.end() && found->second;
    }

    void v79_r6_record_touch(
        ID3D12GraphicsCommandList *command_list,
        uint32_t kind,
        ID3D12Resource *resource,
        bool write,
        uint32_t before_state = 0,
        uint32_t after_state = 0)
    {
        if (!v79_is_active() || command_list == nullptr || resource == nullptr ||
            s_v79_r6_total_touch_count.load(std::memory_order_acquire) >=
                v79_r6_max_recorded_touches)
            return;
        v55_resource_info info = {};
        if (!v79_get_resource_info(resource, info) ||
            !v79_is_large_texture(info) ||
            (info.flags & D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET) == 0)
            return;
        void *const identity = v33_identity_pointer(
            reinterpret_cast<IUnknown *>(command_list));
        if (identity == nullptr)
            return;
        const uint64_t generation = v79_r5_current_generation(identity);
        bool locked = false;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            const auto found = s_v79_r3_locked_resources.find(info.resource_id);
            locked = found != s_v79_r3_locked_resources.end() && found->second;
            auto &ops = s_v79_r6_touches_by_identity[identity][generation];
            if (ops.size() < 2048 &&
                s_v79_r6_total_touch_count.load(std::memory_order_acquire) <
                    v79_r6_max_recorded_touches)
            {
                v79_r6_touch_operation op = {};
                op.kind = kind;
                op.resource_id = info.resource_id;
                op.write = write;
                op.before_state = before_state;
                op.after_state = after_state;
                ops.push_back(op);
                s_v79_r6_total_touch_count.fetch_add(1, std::memory_order_acq_rel);
            }
        }
        if (locked)
            s_v79_r6_locked_touch_count.fetch_add(1, std::memory_order_acq_rel);
        switch (kind)
        {
        case 1: case 2: s_v79_r6_copy_texture_count.fetch_add(1, std::memory_order_acq_rel); break;
        case 3: case 4: s_v79_r6_copy_resource_count.fetch_add(1, std::memory_order_acq_rel); break;
        case 5: case 6: s_v79_r6_resolve_count.fetch_add(1, std::memory_order_acq_rel); break;
        case 7: case 8: s_v79_r6_resolve_region_count.fetch_add(1, std::memory_order_acq_rel); break;
        case 9: s_v79_r6_legacy_barrier_count.fetch_add(1, std::memory_order_acq_rel); break;
        case 10: s_v79_r6_begin_render_pass_count.fetch_add(1, std::memory_order_acq_rel); break;
        }
        const uint64_t total = s_v79_r6_total_touch_count.load(std::memory_order_acquire);
        if ((locked && s_v79_r6_locked_touch_count.load(std::memory_order_acquire) <= 32) ||
            total <= 16 || total % 512 == 0)
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R6: TRIPLET_TOUCH_RECORD total=%llu locked=%u kind=%s write=%u command_list=%p identity=%p generation=%llu resource_id=%llu format=%u dimensions=%llux%u before=0x%X after=0x%X strict_rewritten_proof=%u commands_modified=0.",
                static_cast<unsigned long long>(total), locked ? 1u : 0u,
                v79_r6_kind_name(kind), write ? 1u : 0u, command_list,
                identity, static_cast<unsigned long long>(generation),
                static_cast<unsigned long long>(info.resource_id), info.format,
                static_cast<unsigned long long>(info.width), info.height,
                before_state, after_state,
                s_v61_rewritten_steady_state_seen.load(
                    std::memory_order_acquire) ? 1u : 0u);
    }

    void v79_r6_record_barrier_touches(
        ID3D12GraphicsCommandList *command_list,
        UINT barrier_count,
        const D3D12_RESOURCE_BARRIER *barriers)
    {
        if (command_list == nullptr || barriers == nullptr)
            return;
        for (UINT index = 0; index < barrier_count; ++index)
        {
            D3D12_RESOURCE_BARRIER barrier = {};
            if (!safe_copy_from_process(barriers + index, &barrier, sizeof(barrier)) ||
                barrier.Type != D3D12_RESOURCE_BARRIER_TYPE_TRANSITION ||
                barrier.Transition.pResource == nullptr)
                continue;
            const uint32_t before_state =
                static_cast<uint32_t>(barrier.Transition.StateBefore);
            const uint32_t after_state =
                static_cast<uint32_t>(barrier.Transition.StateAfter);
            const bool write =
                (barrier.Transition.StateAfter &
                 (D3D12_RESOURCE_STATE_RENDER_TARGET |
                  D3D12_RESOURCE_STATE_COPY_DEST |
                  D3D12_RESOURCE_STATE_RESOLVE_DEST |
                  D3D12_RESOURCE_STATE_UNORDERED_ACCESS)) != 0;
            v79_r6_record_touch(
                command_list, 9, barrier.Transition.pResource,
                write, before_state, after_state);
        }
    }

    v79_r6_resolve_region_fn v79_r6_lookup_resolve_region(
        ID3D12GraphicsCommandList1 *command_list)
    {
        if (command_list == nullptr) return nullptr;
        void **vtable = *reinterpret_cast<void ***>(command_list);
        std::lock_guard<std::mutex> lock(s_v79_r6_hook_mutex);
        const auto found = s_v79_r6_resolve_region_original_by_vtable.find(vtable);
        return found != s_v79_r6_resolve_region_original_by_vtable.end() ?
            found->second : s_v79_r6_resolve_region_fallback;
    }

    v79_r6_begin_render_pass_fn v79_r6_lookup_begin_render_pass(
        ID3D12GraphicsCommandList4 *command_list)
    {
        if (command_list == nullptr) return nullptr;
        void **vtable = *reinterpret_cast<void ***>(command_list);
        std::lock_guard<std::mutex> lock(s_v79_r6_hook_mutex);
        const auto found = s_v79_r6_begin_render_pass_original_by_vtable.find(vtable);
        return found != s_v79_r6_begin_render_pass_original_by_vtable.end() ?
            found->second : s_v79_r6_begin_render_pass_fallback;
    }

    void STDMETHODCALLTYPE v79_r6_trace_resolve_subresource_region(
        ID3D12GraphicsCommandList1 *command_list,
        ID3D12Resource *destination, UINT destination_subresource,
        UINT destination_x, UINT destination_y,
        ID3D12Resource *source_resource, UINT source_subresource,
        const D3D12_RECT *source_rect, DXGI_FORMAT format,
        D3D12_RESOLVE_MODE resolve_mode)
    {
        const auto original = v79_r6_lookup_resolve_region(command_list);
        if (original != nullptr)
            original(command_list, destination, destination_subresource,
                destination_x, destination_y, source_resource,
                source_subresource, source_rect, format, resolve_mode);
        v79_r6_record_touch(
            reinterpret_cast<ID3D12GraphicsCommandList *>(command_list),
            7, destination, true);
        v79_r6_record_touch(
            reinterpret_cast<ID3D12GraphicsCommandList *>(command_list),
            8, source_resource, false);
    }

    void STDMETHODCALLTYPE v79_r6_trace_begin_render_pass(
        ID3D12GraphicsCommandList4 *command_list,
        UINT render_target_count,
        const D3D12_RENDER_PASS_RENDER_TARGET_DESC *render_targets,
        const D3D12_RENDER_PASS_DEPTH_STENCIL_DESC *depth_stencil,
        D3D12_RENDER_PASS_FLAGS flags)
    {
        if (render_targets != nullptr)
        {
            for (UINT index = 0; index < render_target_count; ++index)
            {
                D3D12_RENDER_PASS_RENDER_TARGET_DESC desc = {};
                if (!safe_copy_from_process(
                        render_targets + index, &desc, sizeof(desc)))
                    continue;
                uint64_t resource_id = 0;
                if (!v79_resolve_rtv_handle(desc.cpuDescriptor.ptr, resource_id))
                    continue;
                v55_resource_info info = {};
                if (!v55_get_resource(resource_id, info) || info.resource == nullptr)
                    continue;
                v79_r6_record_touch(
                    reinterpret_cast<ID3D12GraphicsCommandList *>(command_list),
                    10, info.resource, true);
            }
        }
        const auto original = v79_r6_lookup_begin_render_pass(command_list);
        if (original != nullptr)
            original(command_list, render_target_count, render_targets,
                depth_stencil, flags);
    }

    void v79_r6_install_command_list_hooks(
        IUnknown *command_list)
    {
        if (!v79_is_active() || command_list == nullptr)
            return;
        ID3D12GraphicsCommandList4 *list4 = nullptr;
        const HRESULT query_hr = command_list->QueryInterface(
            __uuidof(ID3D12GraphicsCommandList4),
            reinterpret_cast<void **>(&list4));
        if (FAILED(query_hr) || list4 == nullptr)
        {
            const uint64_t failure = s_v79_r6_hook_failure_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
            if (failure <= 8)
                reshade::log::message(
                    reshade::log::level::warning,
                    "D3DMetal RTX presented-frame producer chain v79 R6: COMMAND_LIST_HOOKS installed=0 failure=%llu reason=list4-query-failed hr=0x%08X commands_modified=0.",
                    static_cast<unsigned long long>(failure),
                    static_cast<unsigned int>(query_hr));
            return;
        }
        void **vtable = *reinterpret_cast<void ***>(list4);
        if (vtable == nullptr)
        {
            list4->Release();
            return;
        }
        bool resolve_installed = false;
        bool pass_installed = false;
        bool failed = false;
        {
            std::lock_guard<std::mutex> lock(s_v79_r6_hook_mutex);
            resolve_installed =
                s_v79_r6_resolve_region_original_by_vtable.find(vtable) !=
                s_v79_r6_resolve_region_original_by_vtable.end();
            pass_installed =
                s_v79_r6_begin_render_pass_original_by_vtable.find(vtable) !=
                s_v79_r6_begin_render_pass_original_by_vtable.end();
            if (resolve_installed && pass_installed)
            {
                list4->Release();
                return;
            }
            struct item { size_t slot; void *replacement; void **original; };
            void *resolve_original = nullptr;
            void *pass_original = nullptr;
            item items[] = {
                { v79_r6_resolve_subresource_region_slot,
                  reinterpret_cast<void *>(&v79_r6_trace_resolve_subresource_region),
                  &resolve_original },
                { v79_r6_begin_render_pass_slot,
                  reinterpret_cast<void *>(&v79_r6_trace_begin_render_pass),
                  &pass_original },
            };
            for (const item &entry : items)
            {
                if (vtable[entry.slot] == entry.replacement)
                    continue;
                DWORD old_protection = 0;
                if (!VirtualProtect(
                        &vtable[entry.slot], sizeof(void *),
                        PAGE_EXECUTE_READWRITE, &old_protection))
                {
                    failed = true;
                    continue;
                }
                *entry.original = InterlockedExchangePointer(
                    reinterpret_cast<PVOID volatile *>(&vtable[entry.slot]),
                    entry.replacement);
                DWORD ignored = 0;
                VirtualProtect(&vtable[entry.slot], sizeof(void *),
                    old_protection, &ignored);
                FlushInstructionCache(GetCurrentProcess(),
                    &vtable[entry.slot], sizeof(void *));
                if (vtable[entry.slot] != entry.replacement)
                    failed = true;
            }
            if (!resolve_installed && resolve_original != nullptr &&
                resolve_original != reinterpret_cast<void *>(
                    &v79_r6_trace_resolve_subresource_region))
            {
                const auto typed = reinterpret_cast<v79_r6_resolve_region_fn>(
                    resolve_original);
                s_v79_r6_resolve_region_original_by_vtable[vtable] = typed;
                if (s_v79_r6_resolve_region_fallback == nullptr)
                    s_v79_r6_resolve_region_fallback = typed;
                resolve_installed = true;
            }
            if (!pass_installed && pass_original != nullptr &&
                pass_original != reinterpret_cast<void *>(
                    &v79_r6_trace_begin_render_pass))
            {
                const auto typed = reinterpret_cast<v79_r6_begin_render_pass_fn>(
                    pass_original);
                s_v79_r6_begin_render_pass_original_by_vtable[vtable] = typed;
                if (s_v79_r6_begin_render_pass_fallback == nullptr)
                    s_v79_r6_begin_render_pass_fallback = typed;
                pass_installed = true;
            }
        }
        if (resolve_installed && pass_installed && !failed)
        {
            const uint64_t success = s_v79_r6_hook_success_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
            if (success <= 4)
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R6: COMMAND_LIST_HOOKS installed=1 success=%llu resolve_region_slot=64 begin_render_pass_slot=68 commands_modified=0.",
                    static_cast<unsigned long long>(success));
        }
        else if (failed)
        {
            const uint64_t failure = s_v79_r6_hook_failure_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
            if (failure <= 8)
                reshade::log::message(
                    reshade::log::level::warning,
                    "D3DMetal RTX presented-frame producer chain v79 R6: COMMAND_LIST_HOOKS installed=0 failure=%llu resolve_region=%u begin_render_pass=%u commands_modified=0.",
                    static_cast<unsigned long long>(failure),
                    resolve_installed ? 1u : 0u, pass_installed ? 1u : 0u);
        }
        list4->Release();
    }

    void v79_r6_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists)
    {
        (void)queue;
        if (!v79_is_active() || command_lists == nullptr ||
            !s_v79_r3_triplet_locked.load(std::memory_order_acquire))
            return;
        const bool strict = s_v61_rewritten_steady_state_seen.load(
            std::memory_order_acquire);
        const uint64_t submit_call = s_v79_r6_submit_call_count.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        s_v79_r6_submit_list_count.fetch_add(count, std::memory_order_acq_rel);
        std::vector<v79_r6_touch_operation> locked_ops;
        uint64_t resolved_lists = 0;
        for (UINT index = 0; index < count; ++index)
        {
            ID3D12CommandList *list = nullptr;
            if (!safe_copy_from_process(command_lists + index, &list, sizeof(list)) ||
                list == nullptr)
                continue;
            void *const identity = v33_identity_pointer(
                reinterpret_cast<IUnknown *>(list));
            if (identity == nullptr)
                continue;
            const uint64_t generation = v79_r5_current_generation(identity);
            std::vector<v79_r6_touch_operation> operations;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                const auto identity_found = s_v79_r6_touches_by_identity.find(identity);
                if (identity_found != s_v79_r6_touches_by_identity.end())
                {
                    const auto generation_found =
                        identity_found->second.find(generation);
                    if (generation_found != identity_found->second.end())
                        operations = generation_found->second;
                }
            }
            bool list_hit = false;
            for (const auto &operation : operations)
            {
                if (!v79_r6_is_locked_resource(operation.resource_id))
                    continue;
                locked_ops.push_back(operation);
                list_hit = true;
            }
            if (list_hit)
                ++resolved_lists;
        }
        if (locked_ops.empty())
        {
            const uint64_t miss = s_v79_r6_resolution_miss_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
            uint64_t post_miss = s_v79_r6_post_strict_miss_count.load(
                std::memory_order_acquire);
            if (strict)
                post_miss = s_v79_r6_post_strict_miss_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            if (miss <= 16 || miss % 120 == 0 || (strict && post_miss == 1))
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R6: TRIPLET_TOUCH_QUEUE_RESOLUTION hit=0 miss=%llu post_strict_misses=%llu submit_call=%llu command_list_count=%u total_touch_records=%llu locked_touch_records=%llu strict_rewritten_proof=%u commands_modified=0.",
                    static_cast<unsigned long long>(miss),
                    static_cast<unsigned long long>(post_miss),
                    static_cast<unsigned long long>(submit_call), count,
                    static_cast<unsigned long long>(
                        s_v79_r6_total_touch_count.load(std::memory_order_acquire)),
                    static_cast<unsigned long long>(
                        s_v79_r6_locked_touch_count.load(std::memory_order_acquire)),
                    strict ? 1u : 0u);
            return;
        }
        const uint64_t hit = s_v79_r6_resolution_hit_count.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        uint64_t write_hits = 0;
        uint64_t read_hits = 0;
        for (const auto &operation : locked_ops)
        {
            if (operation.write) ++write_hits; else ++read_hits;
            if (strict)
            {
                if (operation.write)
                    s_v79_r6_post_strict_write_hit_count.fetch_add(
                        1, std::memory_order_acq_rel);
                else
                    s_v79_r6_post_strict_read_hit_count.fetch_add(
                        1, std::memory_order_acq_rel);
            }
            if (!strict || !operation.write)
                continue;
            uint64_t previous = 0;
            size_t distinct = 0;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                previous = s_v79_r6_last_write_resource;
                s_v79_r6_last_write_resource = operation.resource_id;
                s_v79_r6_post_strict_resources[operation.resource_id] = true;
                distinct = s_v79_r6_post_strict_resources.size();
            }
            if (previous != 0 && previous != operation.resource_id)
            {
                const uint64_t rotation = s_v79_r6_rotation_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
                if (rotation <= 24 || rotation % 120 == 0)
                    reshade::log::message(
                        reshade::log::level::info,
                        "D3DMetal RTX presented-frame producer chain v79 R6: TRIPLET_TOUCH_ROTATION rotation=%llu completed_resource_id=%llu next_resource_id=%llu distinct_triplet_resources=%zu kind=%s boundary=submitted-direct-command-list-touch strict_rewritten_proof=1 commands_modified=0.",
                        static_cast<unsigned long long>(rotation),
                        static_cast<unsigned long long>(previous),
                        static_cast<unsigned long long>(operation.resource_id),
                        distinct, v79_r6_kind_name(operation.kind));
                if (rotation >= 6 && distinct >= 3)
                {
                    bool expected = false;
                    if (s_v79_r6_path_found.compare_exchange_strong(
                            expected, true, std::memory_order_acq_rel))
                        reshade::log::message(
                            reshade::log::level::info,
                            "D3DMetal RTX presented-frame producer chain v79 R6: V79_R6_TRIPLET_TOUCH_PATH_FOUND success=1 rotations=%llu distinct_triplet_resources=%zu post_strict_write_hits=%llu post_strict_read_hits=%llu frame_boundary=submitted-direct-command-list-touch next_stage=present-chain-capture commands_modified=0.",
                            static_cast<unsigned long long>(rotation), distinct,
                            static_cast<unsigned long long>(
                                s_v79_r6_post_strict_write_hit_count.load(
                                    std::memory_order_acquire)),
                            static_cast<unsigned long long>(
                                s_v79_r6_post_strict_read_hit_count.load(
                                    std::memory_order_acquire)));
                }
            }
        }
        if (hit <= 32 || hit % 120 == 0 ||
            (strict && s_v79_r6_post_strict_write_hit_count.load(
                std::memory_order_acquire) == write_hits))
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R6: TRIPLET_TOUCH_QUEUE_RESOLUTION hit=1 resolution_hit=%llu submit_call=%llu command_list_count=%u resolved_lists=%llu locked_operations=%zu write_operations=%llu read_operations=%llu post_strict_write_hits=%llu post_strict_read_hits=%llu rotations=%llu strict_rewritten_proof=%u commands_modified=0.",
                static_cast<unsigned long long>(hit),
                static_cast<unsigned long long>(submit_call), count,
                static_cast<unsigned long long>(resolved_lists),
                locked_ops.size(),
                static_cast<unsigned long long>(write_hits),
                static_cast<unsigned long long>(read_hits),
                static_cast<unsigned long long>(
                    s_v79_r6_post_strict_write_hit_count.load(
                        std::memory_order_acquire)),
                static_cast<unsigned long long>(
                    s_v79_r6_post_strict_read_hit_count.load(
                        std::memory_order_acquire)),
                static_cast<unsigned long long>(
                    s_v79_r6_rotation_count.load(std::memory_order_acquire)),
                strict ? 1u : 0u);
    }

'''
    text = text[:anchor.start()] + helpers + text[anchor.start():]
    note("helpers")

    # 6. Add recording calls to existing V79 wrappers.
    m = unique_regex(
        r'(?P<i>[ \t]*)if \(destination != nullptr && source_location != nullptr &&\s*'
        r'safe_copy_from_process\(destination, &dst, sizeof\(dst\)\) &&\s*'
        r'safe_copy_from_process\(source_location, &src, sizeof\(src\)\)\)\s*'
        r'v79_record_copy_event\("copy-texture", dst\.pResource, src\.pResource\);',
        "copy_texture")
    i = m.group('i')
    repl = (i + 'if (destination != nullptr && source_location != nullptr &&\n' +
            i + '    safe_copy_from_process(destination, &dst, sizeof(dst)) &&\n' +
            i + '    safe_copy_from_process(source_location, &src, sizeof(src)))\n' +
            i + '{\n' +
            i + '    v79_r6_record_touch(command_list, 1, dst.pResource, true);\n' +
            i + '    v79_r6_record_touch(command_list, 2, src.pResource, false);\n' +
            i + '    v79_record_copy_event("copy-texture", dst.pResource, src.pResource);\n' +
            i + '}')
    text = text[:m.start()] + repl + text[m.end():]

    m = unique_regex(
        r'(?P<i>[ \t]*)v79_record_copy_event\('
        r'"copy-resource",\s*destination,\s*source_resource\);',
        "copy_resource")
    i = m.group('i')
    repl = (i + 'v79_r6_record_touch(command_list, 3, destination, true);\n' +
            i + 'v79_r6_record_touch(command_list, 4, source_resource, false);\n' +
            i + 'v79_record_copy_event("copy-resource", destination, source_resource);')
    text = text[:m.start()] + repl + text[m.end():]

    m = unique_regex(
        r'(?P<i>[ \t]*)v79_record_copy_event\(\s*\n?'
        r'(?P=i)[ \t]*"resolve-subresource",\s*destination,\s*source_resource\);',
        "resolve")
    i = m.group('i')
    repl = (i + 'v79_r6_record_touch(command_list, 5, destination, true);\n' +
            i + 'v79_r6_record_touch(command_list, 6, source_resource, false);\n' +
            i + 'v79_record_copy_event(\n' + i + '    "resolve-subresource", destination, source_resource);')
    text = text[:m.start()] + repl + text[m.end():]

    m = unique_regex(
        r'(?m)^(?P<i>[ \t]*)v79_observe_barriers\('
        r'barrier_count,\s*barriers\)\s*;', "barrier")
    i = m.group('i')
    repl = (i + 'v79_r6_record_barrier_touches(\n' +
            i + '    command_list, barrier_count, barriers);\n' +
            i + 'v79_observe_barriers(barrier_count, barriers);')
    text = text[:m.start()] + repl + text[m.end():]
    note("wrapper_calls")

    # 7. Active runtime log after R5 active log statement.
    marker = "D3DMetal RTX presented-frame producer chain v79 R5: ACTIVE"
    positions = [m.start() for m in re.finditer(re.escape(marker), text)]
    runtime_positions = [p for p in positions if "execute-bundle-slot=27" in text[p:p+900]]
    if len(runtime_positions) != 1:
        fail("active_log", f"runtime_marker_count={len(runtime_positions)}")
    p = runtime_positions[0]
    call_end = text.find(");", p)
    if call_end < 0:
        fail("active_log", "statement_end_not_found")
    call_end += 2
    active = r'''
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R6: ACTIVE frozen-triplet-source=R3 command-generation-source=R5 frame-boundary-candidate=submitted-direct-command-list-touch copy-texture-slot=16 copy-resource-slot=17 resolve-slot=19 resolve-region-slot=64 legacy-barrier-slot=26 begin-render-pass-slot=68 triplet-touch-census=enabled GPU-readback=disabled injected-copies=disabled injected-barriers=disabled commands_modified=0.");'''
    text = text[:call_end] + active + text[call_end:]
    note("active_log")

    required = [
        "V79_R6_BINARY_MARKER_MANIFEST_TRIPLET_TOUCH_CENSUS",
        "V79_R6_EARLY_COMMAND_LIST_BOOTSTRAP",
        "v79_r6_trace_resolve_subresource_region",
        "v79_r6_trace_begin_render_pass",
        "v79_r6_record_barrier_touches",
        "v79_r6_on_execute_command_lists(queue, count, command_lists);",
        "TRIPLET_TOUCH_QUEUE_RESOLUTION",
        "V79_R6_TRIPLET_TOUCH_PATH_FOUND",
    ]
    missing = [x for x in required if x not in text]
    if missing:
        fail("final_gate", "missing=" + ",".join(missing))
    source.write_text(text, encoding="utf-8")
    note("source_write")

    Path("v79-r6-patch-report.txt").write_text("\n".join([
        "V79_R6_TRIPLET_TOUCH_COMMAND_STREAM_PATCH_OK",
        "BINARY_MANIFEST=V79_R6_BINARY_MARKER_MANIFEST_TRIPLET_TOUCH_CENSUS",
        "TRIPLET_SOURCE=V79_R3_FROZEN_RECORDING_TIME_TRIPLET",
        "GENERATION_SOURCE=V79_R5_RESET_GENERATIONS",
        "COPY_TEXTURE_REGION_SLOT=16",
        "COPY_RESOURCE_SLOT=17",
        "RESOLVE_SUBRESOURCE_SLOT=19",
        "RESOLVE_SUBRESOURCE_REGION_SLOT=64",
        "RESOURCE_BARRIER_SLOT=26",
        "BEGIN_RENDER_PASS_SLOT=68",
        "FRAME_BOUNDARY_CANDIDATE=SUBMITTED_DIRECT_COMMAND_LIST_TOUCH_ROTATION",
        "GPU_READBACK=DISABLED",
        "INJECTED_COPIES=DISABLED",
        "INJECTED_BARRIERS=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]), encoding="utf-8")
    note("patch_report")
except SystemExit:
    raise
except Exception as exc:
    fail("exception", f"{type(exc).__name__}:{exc} traceback={traceback.format_exc().replace(chr(10), ' | ')}")
