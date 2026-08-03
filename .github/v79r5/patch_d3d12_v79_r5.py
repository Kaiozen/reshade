from pathlib import Path
import re
import traceback

source = Path("source/d3d12/d3d12.cpp")
diagnostic_path = Path("v79-r5-patcher-diagnostics.txt")
diagnostics = [
    "V79_R5_HOTFIX2_PATCHER_DIAGNOSTICS",
    "ANCHOR_MODE=MARKER_DRIVEN_REGEX",
    "WHITESPACE_TOLERANCE=ENABLED",
    "OPTIONAL_STATIC_TOLERANCE=ENABLED",
]

def save_diagnostics():
    diagnostic_path.write_text("\n".join(diagnostics) + "\n", encoding="utf-8")

def note(stage, detail="PASS"):
    line = f"PATCH_STAGE={stage} {detail}"
    diagnostics.append(line)
    print(line, flush=True)
    save_diagnostics()

def fail(stage, detail):
    line = f"V79_R5_PATCHER_ERROR stage={stage} detail={detail}"
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
    string_char = ""
    escape = False
    i = open_index
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == string_char:
                in_string = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_string = True
            string_char = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    fail(stage, "matching_closing_brace_not_found")

if not source.is_file():
    fail("source", "source/d3d12/d3d12.cpp_is_missing")

text = source.read_text(encoding="utf-8")
if "kaiozen_v79_r5_binary_marker_manifest" in text:
    fail("preflight", "source_already_contains_v79_r5")
for marker in [
    "kaiozen_v79_r4_binary_marker_manifest",
    "v79_r4_on_execute_command_lists",
    "v79_r4_recover_locked_writer_metadata",
    "v79_r3_observe_rtv_sequence",
    "D3DMetal RTX presented-frame producer chain v79 R4: ACTIVE",
]:
    if marker not in text:
        fail("preflight", f"missing_r4_marker={marker}")
note("preflight")

try:
    # 1. Insert exported R5 manifest after the complete R4 manifest function.
    match = unique_regex(
        r'extern\s+"C"\s+__declspec\s*\(\s*dllexport\s*\)\s+const\s+char\s*\*\s*'
        r'kaiozen_v79_r4_binary_marker_manifest\s*\(\s*\)\s*\{',
        "manifest")
    open_brace = text.find("{", match.start())
    close_brace = matching_brace(open_brace, "manifest")
    text = text[:close_brace + 1] + "\n\n" + 'extern "C" __declspec(dllexport) const char *kaiozen_v79_r5_binary_marker_manifest()\n{\n    static const char manifest[] =\n        "V79_R5_BINARY_MARKER_MANIFEST_R5_EXECUTE_BUNDLE_GRAPH\\n"\n        "V79_R5_HOTFIX2_MARKER_DRIVEN_PATCHER\\n"\n        "D3DMetal RTX presented-frame producer chain v79 R5: ACTIVE\\n"\n        "EXECUTE_BUNDLE_EDGE\\n"\n        "COMMAND_LIST_RESET_GENERATION\\n"\n        "BUNDLE_GRAPH_RESOLUTION\\n"\n        "BUNDLE_RING_FRAME\\n"\n        "frame-boundary=recursive-submitted-bundle-graph\\n"\n        "commands_modified=0\\n";\n    return manifest;\n}\n' + text[close_brace + 1:]
    note("manifest")

    # 2. Insert state after the R4 event-cap declaration, independent of indentation.
    match = unique_regex(
        r'(?m)^[ \t]*static\s+constexpr\s+uint64_t\s+'
        r'v79_r4_max_recorded_events\s*=\s*12000\s*;',
        "state")
    text = text[:match.end()] + '\n\n    struct v79_r5_command_key\n    {\n        void *identity = nullptr;\n        uint64_t generation = 0;\n    };\n\n    struct v79_r5_recorded_operation\n    {\n        uint32_t kind = 0; // 1 = RTV resource, 2 = ExecuteBundle child.\n        uint64_t resource_id = 0;\n        void *child_identity = nullptr;\n        uint64_t child_generation = 0;\n    };\n\n    using v79_r5_reset_fn = HRESULT (STDMETHODCALLTYPE *)(\n        ID3D12GraphicsCommandList *, ID3D12CommandAllocator *,\n        ID3D12PipelineState *);\n    using v79_r5_execute_bundle_fn = void (STDMETHODCALLTYPE *)(\n        ID3D12GraphicsCommandList *, ID3D12GraphicsCommandList *);\n\n    static std::mutex s_v79_r5_hook_mutex;\n    static std::unordered_map<void **, v79_r5_reset_fn>\n        s_v79_r5_reset_original_by_vtable;\n    static std::unordered_map<void **, v79_r5_execute_bundle_fn>\n        s_v79_r5_execute_bundle_original_by_vtable;\n    static v79_r5_reset_fn s_v79_r5_reset_fallback = nullptr;\n    static v79_r5_execute_bundle_fn s_v79_r5_execute_bundle_fallback = nullptr;\n\n    static std::unordered_map<void *, uint64_t>\n        s_v79_r5_generation_by_identity;\n    static std::unordered_map<\n        void *,\n        std::unordered_map<uint64_t, std::vector<v79_r5_recorded_operation>>>\n        s_v79_r5_operations_by_identity;\n\n    static std::atomic<uint64_t> s_v79_r5_hook_install_attempt_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_hook_install_success_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_hook_install_failure_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_reset_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_bundle_edge_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_recorded_operation_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_queue_submit_call_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_queue_submit_list_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_post_strict_submit_call_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_post_strict_submit_list_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_resolution_hit_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_resolution_miss_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_post_strict_resolution_hit_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_post_strict_resolution_miss_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_resolution_ambiguous_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_bundle_edges_followed_count = 0;\n    static std::atomic<uint64_t> s_v79_r5_bundle_ring_frame_count = 0;\n    static uint64_t s_v79_r5_last_resolved_resource = 0;\n    static constexpr uint64_t v79_r5_max_recorded_operations = 12000;\n    static constexpr uint32_t v79_r5_max_bundle_depth = 8;\n' + text[match.end():]
    note("state")

    # 3. Add R5 queue observer declaration immediately before the established v38 installer declaration.
    v38_decl = unique_regex(
        r'(?m)^(?P<indent>[ \t]*)void\s+v38_install_execute_command_lists_hook\s*'
        r'\(\s*ID3D12CommandQueue\s*\*\s*queue\s*\)\s*;',
        "queue_forward")
    indent = v38_decl.group("indent")
    forward = (
        indent + "void v79_r5_on_execute_command_lists(\n" +
        indent + "    ID3D12CommandQueue *queue,\n" +
        indent + "    UINT count,\n" +
        indent + "    ID3D12CommandList *const *command_lists);\n\n"
    )
    text = text[:v38_decl.start()] + forward + text[v38_decl.start():]
    note("queue_forward")

    # 4. Chain R5 after R4 in the existing ExecuteCommandLists observer.
    call = unique_regex(
        r'(?m)^(?P<indent>[ \t]*)v79_r4_on_execute_command_lists\s*'
        r'\(\s*queue\s*,\s*count\s*,\s*command_lists\s*\)\s*;',
        "queue_callback")
    indent = call.group("indent")
    text = text[:call.end()] + "\n" + indent +         "v79_r5_on_execute_command_lists(queue, count, command_lists);" + text[call.end():]
    note("queue_callback")

    # 5. Bootstrap R5 from the established V33 native command-list creation helper.
    helper = unique_regex(
        r'(?m)^(?P<indent>[ \t]*)(?:static\s+)?void\s+'
        r'v33_install_command_list_method_hooks\s*\(\s*IUnknown\s*\*\s*'
        r'(?:const\s+)?command_list\s*\)\s*\{',
        "v33_bootstrap")
    indent = helper.group("indent")
    forward = (
        indent + "void v79_r5_install_command_list_hooks(\n" +
        indent + "    ID3D12GraphicsCommandList *command_list);\n\n"
    )
    text = text[:helper.start()] + forward + text[helper.start():]
    # Re-find after inserting the declaration.
    helper = unique_regex(
        r'(?m)^(?P<indent>[ \t]*)(?:static\s+)?void\s+'
        r'v33_install_command_list_method_hooks\s*\(\s*IUnknown\s*\*\s*'
        r'(?:const\s+)?command_list\s*\)\s*\{',
        "v33_bootstrap")
    body_open = text.find("{", helper.start(), helper.end())
    indent = helper.group("indent")
    bootstrap = (
        "\n" + indent + "    // V79_R5_EARLY_COMMAND_LIST_BOOTSTRAP\n" +
        indent + "    v79_r5_install_command_list_hooks(\n" +
        indent + "        reinterpret_cast<ID3D12GraphicsCommandList *>(command_list));"
    )
    text = text[:body_open + 1] + bootstrap + text[body_open + 1:]
    note("v33_bootstrap")

    # 6. Insert the R5 implementation immediately before the stable R4 helper definition.
    r4_helper = unique_regex(
        r'(?m)^[ \t]*void\s+v79_r4_recover_locked_writer_metadata\s*'
        r'\(\s*\)\s*\{',
        "r5_helpers")
    text = text[:r4_helper.start()] + '    uint64_t v79_r5_current_generation(void *identity)\n    {\n        if (identity == nullptr)\n            return 0;\n        std::lock_guard<std::mutex> lock(s_v79_mutex);\n        return s_v79_r5_generation_by_identity[identity];\n    }\n\n    bool v79_r5_key_seen(\n        const std::vector<v79_r5_command_key> &visited,\n        void *identity,\n        uint64_t generation)\n    {\n        return std::find_if(\n            visited.begin(), visited.end(),\n            [identity, generation](const v79_r5_command_key &key)\n            {\n                return key.identity == identity &&\n                    key.generation == generation;\n            }) != visited.end();\n    }\n\n    v79_r5_reset_fn v79_r5_lookup_reset_original(\n        ID3D12GraphicsCommandList *command_list)\n    {\n        if (command_list == nullptr)\n            return nullptr;\n        void **vtable = *reinterpret_cast<void ***>(command_list);\n        std::lock_guard<std::mutex> lock(s_v79_r5_hook_mutex);\n        const auto found = s_v79_r5_reset_original_by_vtable.find(vtable);\n        return found != s_v79_r5_reset_original_by_vtable.end() ?\n            found->second : s_v79_r5_reset_fallback;\n    }\n\n    v79_r5_execute_bundle_fn v79_r5_lookup_execute_bundle_original(\n        ID3D12GraphicsCommandList *command_list)\n    {\n        if (command_list == nullptr)\n            return nullptr;\n        void **vtable = *reinterpret_cast<void ***>(command_list);\n        std::lock_guard<std::mutex> lock(s_v79_r5_hook_mutex);\n        const auto found =\n            s_v79_r5_execute_bundle_original_by_vtable.find(vtable);\n        return found != s_v79_r5_execute_bundle_original_by_vtable.end() ?\n            found->second : s_v79_r5_execute_bundle_fallback;\n    }\n\n    HRESULT STDMETHODCALLTYPE v79_r5_trace_reset(\n        ID3D12GraphicsCommandList *command_list,\n        ID3D12CommandAllocator *allocator,\n        ID3D12PipelineState *initial_state);\n\n    void STDMETHODCALLTYPE v79_r5_trace_execute_bundle(\n        ID3D12GraphicsCommandList *command_list,\n        ID3D12GraphicsCommandList *bundle);\n\n    void v79_r5_install_command_list_hooks(\n        ID3D12GraphicsCommandList *command_list)\n    {\n        if (!v79_is_active() || command_list == nullptr)\n            return;\n\n        s_v79_r5_hook_install_attempt_count.fetch_add(\n            1, std::memory_order_acq_rel);\n        void **vtable = *reinterpret_cast<void ***>(command_list);\n        if (vtable == nullptr)\n            return;\n\n        bool reset_installed = false;\n        bool bundle_installed = false;\n        bool failed = false;\n        {\n            std::lock_guard<std::mutex> lock(s_v79_r5_hook_mutex);\n            reset_installed =\n                s_v79_r5_reset_original_by_vtable.find(vtable) !=\n                s_v79_r5_reset_original_by_vtable.end();\n            bundle_installed =\n                s_v79_r5_execute_bundle_original_by_vtable.find(vtable) !=\n                s_v79_r5_execute_bundle_original_by_vtable.end();\n            if (reset_installed && bundle_installed)\n                return;\n\n            if (!reset_installed)\n            {\n                void **slot = vtable + 10;\n                DWORD old_protection = 0;\n                if (!VirtualProtect(\n                        slot, sizeof(void *), PAGE_EXECUTE_READWRITE,\n                        &old_protection))\n                {\n                    failed = true;\n                }\n                else\n                {\n                    void *original = InterlockedExchangePointer(\n                        reinterpret_cast<PVOID volatile *>(slot),\n                        reinterpret_cast<void *>(&v79_r5_trace_reset));\n                    DWORD ignored = 0;\n                    VirtualProtect(\n                        slot, sizeof(void *), old_protection, &ignored);\n                    if (original != nullptr &&\n                        original != reinterpret_cast<void *>(\n                            &v79_r5_trace_reset))\n                    {\n                        const auto typed = reinterpret_cast<v79_r5_reset_fn>(\n                            original);\n                        s_v79_r5_reset_original_by_vtable[vtable] = typed;\n                        if (s_v79_r5_reset_fallback == nullptr)\n                            s_v79_r5_reset_fallback = typed;\n                        reset_installed = true;\n                    }\n                    else if (original == reinterpret_cast<void *>(\n                                 &v79_r5_trace_reset) &&\n                             s_v79_r5_reset_fallback != nullptr)\n                    {\n                        s_v79_r5_reset_original_by_vtable[vtable] =\n                            s_v79_r5_reset_fallback;\n                        reset_installed = true;\n                    }\n                    else\n                    {\n                        failed = true;\n                    }\n                }\n            }\n\n            if (!bundle_installed)\n            {\n                void **slot = vtable + 27;\n                DWORD old_protection = 0;\n                if (!VirtualProtect(\n                        slot, sizeof(void *), PAGE_EXECUTE_READWRITE,\n                        &old_protection))\n                {\n                    failed = true;\n                }\n                else\n                {\n                    void *original = InterlockedExchangePointer(\n                        reinterpret_cast<PVOID volatile *>(slot),\n                        reinterpret_cast<void *>(\n                            &v79_r5_trace_execute_bundle));\n                    DWORD ignored = 0;\n                    VirtualProtect(\n                        slot, sizeof(void *), old_protection, &ignored);\n                    if (original != nullptr &&\n                        original != reinterpret_cast<void *>(\n                            &v79_r5_trace_execute_bundle))\n                    {\n                        const auto typed =\n                            reinterpret_cast<v79_r5_execute_bundle_fn>(\n                                original);\n                        s_v79_r5_execute_bundle_original_by_vtable[vtable] =\n                            typed;\n                        if (s_v79_r5_execute_bundle_fallback == nullptr)\n                            s_v79_r5_execute_bundle_fallback = typed;\n                        bundle_installed = true;\n                    }\n                    else if (original == reinterpret_cast<void *>(\n                                 &v79_r5_trace_execute_bundle) &&\n                             s_v79_r5_execute_bundle_fallback != nullptr)\n                    {\n                        s_v79_r5_execute_bundle_original_by_vtable[vtable] =\n                            s_v79_r5_execute_bundle_fallback;\n                        bundle_installed = true;\n                    }\n                    else\n                    {\n                        failed = true;\n                    }\n                }\n            }\n        }\n\n        if (reset_installed && bundle_installed)\n        {\n            const uint64_t success =\n                s_v79_r5_hook_install_success_count.fetch_add(\n                    1, std::memory_order_acq_rel) + 1;\n            if (success <= 8)\n                reshade::log::message(\n                    reshade::log::level::info,\n                    "D3DMetal RTX presented-frame producer chain v79 R5: COMMAND_LIST_HOOKS installed=1 success=%llu command_list=%p vtable=%p reset_slot=10 execute_bundle_slot=27 commands_modified=0.",\n                    static_cast<unsigned long long>(success), command_list,\n                    vtable);\n        }\n        else if (failed)\n        {\n            const uint64_t failures =\n                s_v79_r5_hook_install_failure_count.fetch_add(\n                    1, std::memory_order_acq_rel) + 1;\n            if (failures <= 8)\n                reshade::log::message(\n                    reshade::log::level::warning,\n                    "D3DMetal RTX presented-frame producer chain v79 R5: COMMAND_LIST_HOOKS installed=0 failure=%llu command_list=%p vtable=%p reset_installed=%u execute_bundle_installed=%u commands_modified=0.",\n                    static_cast<unsigned long long>(failures), command_list,\n                    vtable, reset_installed ? 1u : 0u,\n                    bundle_installed ? 1u : 0u);\n        }\n    }\n\n    void v79_r5_record_rtv_event(\n        ID3D12GraphicsCommandList *command_list,\n        const std::vector<uint64_t> &resources)\n    {\n        if (!v79_is_active() || command_list == nullptr || resources.empty())\n            return;\n        void *const identity = v33_identity_pointer(\n            reinterpret_cast<IUnknown *>(command_list));\n        if (identity == nullptr)\n            return;\n\n        std::lock_guard<std::mutex> lock(s_v79_mutex);\n        const uint64_t generation =\n            s_v79_r5_generation_by_identity[identity];\n        auto &operations =\n            s_v79_r5_operations_by_identity[identity][generation];\n        for (const uint64_t resource_id : resources)\n        {\n            if (resource_id == 0 ||\n                s_v79_r5_recorded_operation_count.load(\n                    std::memory_order_acquire) >=\n                    v79_r5_max_recorded_operations)\n                break;\n            if (!operations.empty() && operations.back().kind == 1 &&\n                operations.back().resource_id == resource_id)\n                continue;\n            v79_r5_recorded_operation operation = {};\n            operation.kind = 1;\n            operation.resource_id = resource_id;\n            operations.push_back(operation);\n            s_v79_r5_recorded_operation_count.fetch_add(\n                1, std::memory_order_acq_rel);\n        }\n    }\n\n    void v79_r5_on_reset(ID3D12GraphicsCommandList *command_list)\n    {\n        if (!v79_is_active() || command_list == nullptr)\n            return;\n        void *const identity = v33_identity_pointer(\n            reinterpret_cast<IUnknown *>(command_list));\n        if (identity == nullptr)\n            return;\n\n        uint64_t generation = 0;\n        {\n            std::lock_guard<std::mutex> lock(s_v79_mutex);\n            generation = ++s_v79_r5_generation_by_identity[identity];\n            s_v79_r5_operations_by_identity[identity][generation].clear();\n        }\n        const uint64_t reset = s_v79_r5_reset_count.fetch_add(\n            1, std::memory_order_acq_rel) + 1;\n        if (reset <= 16 || reset % 128 == 0)\n            reshade::log::message(\n                reshade::log::level::info,\n                "D3DMetal RTX presented-frame producer chain v79 R5: COMMAND_LIST_RESET_GENERATION reset=%llu command_list=%p identity=%p generation=%llu commands_modified=0.",\n                static_cast<unsigned long long>(reset), command_list,\n                identity, static_cast<unsigned long long>(generation));\n    }\n\n    void v79_r5_on_execute_bundle(\n        ID3D12GraphicsCommandList *command_list,\n        ID3D12GraphicsCommandList *bundle)\n    {\n        if (!v79_is_active() || command_list == nullptr || bundle == nullptr)\n            return;\n        v79_r5_install_command_list_hooks(command_list);\n        v79_r5_install_command_list_hooks(bundle);\n\n        void *const parent_identity = v33_identity_pointer(\n            reinterpret_cast<IUnknown *>(command_list));\n        void *const child_identity = v33_identity_pointer(\n            reinterpret_cast<IUnknown *>(bundle));\n        if (parent_identity == nullptr || child_identity == nullptr)\n            return;\n\n        uint64_t parent_generation = 0;\n        uint64_t child_generation = 0;\n        bool recorded = false;\n        {\n            std::lock_guard<std::mutex> lock(s_v79_mutex);\n            parent_generation =\n                s_v79_r5_generation_by_identity[parent_identity];\n            child_generation =\n                s_v79_r5_generation_by_identity[child_identity];\n            if (s_v79_r5_recorded_operation_count.load(\n                    std::memory_order_acquire) <\n                v79_r5_max_recorded_operations)\n            {\n                auto &operations =\n                    s_v79_r5_operations_by_identity[parent_identity]\n                                                     [parent_generation];\n                v79_r5_recorded_operation operation = {};\n                operation.kind = 2;\n                operation.child_identity = child_identity;\n                operation.child_generation = child_generation;\n                operations.push_back(operation);\n                s_v79_r5_recorded_operation_count.fetch_add(\n                    1, std::memory_order_acq_rel);\n                recorded = true;\n            }\n        }\n\n        if (recorded)\n        {\n            const uint64_t edge = s_v79_r5_bundle_edge_count.fetch_add(\n                1, std::memory_order_acq_rel) + 1;\n            if (edge <= 32 || edge % 128 == 0)\n                reshade::log::message(\n                    reshade::log::level::info,\n                    "D3DMetal RTX presented-frame producer chain v79 R5: EXECUTE_BUNDLE_EDGE edge=%llu parent=%p parent_identity=%p parent_generation=%llu child=%p child_identity=%p child_generation=%llu operation_count=%llu commands_modified=0.",\n                    static_cast<unsigned long long>(edge), command_list,\n                    parent_identity,\n                    static_cast<unsigned long long>(parent_generation),\n                    bundle, child_identity,\n                    static_cast<unsigned long long>(child_generation),\n                    static_cast<unsigned long long>(\n                        s_v79_r5_recorded_operation_count.load(\n                            std::memory_order_acquire)));\n        }\n    }\n\n    HRESULT STDMETHODCALLTYPE v79_r5_trace_reset(\n        ID3D12GraphicsCommandList *command_list,\n        ID3D12CommandAllocator *allocator,\n        ID3D12PipelineState *initial_state)\n    {\n        const v79_r5_reset_fn original =\n            v79_r5_lookup_reset_original(command_list);\n        if (original == nullptr)\n        {\n            reshade::log::message(\n                reshade::log::level::error,\n                "D3DMetal RTX presented-frame producer chain v79 R5: RESET_FORWARD_FAILURE command_list=%p reason=original-not-found commands_modified=0.",\n                command_list);\n            return E_FAIL;\n        }\n        const HRESULT result = original(\n            command_list, allocator, initial_state);\n        if (SUCCEEDED(result))\n            v79_r5_on_reset(command_list);\n        return result;\n    }\n\n    void STDMETHODCALLTYPE v79_r5_trace_execute_bundle(\n        ID3D12GraphicsCommandList *command_list,\n        ID3D12GraphicsCommandList *bundle)\n    {\n        v79_r5_on_execute_bundle(command_list, bundle);\n        const v79_r5_execute_bundle_fn original =\n            v79_r5_lookup_execute_bundle_original(command_list);\n        if (original == nullptr)\n        {\n            reshade::log::message(\n                reshade::log::level::error,\n                "D3DMetal RTX presented-frame producer chain v79 R5: EXECUTE_BUNDLE_FORWARD_FAILURE command_list=%p bundle=%p reason=original-not-found commands_modified=0.",\n                command_list, bundle);\n            return;\n        }\n        original(command_list, bundle);\n    }\n\n    void v79_r5_collect_locked_resources(\n        void *identity,\n        uint64_t generation,\n        uint32_t depth,\n        std::vector<v79_r5_command_key> &visited,\n        std::vector<uint64_t> &resources,\n        uint64_t &bundle_edges_followed)\n    {\n        if (identity == nullptr || depth > v79_r5_max_bundle_depth ||\n            v79_r5_key_seen(visited, identity, generation))\n            return;\n        visited.push_back({ identity, generation });\n\n        std::vector<v79_r5_recorded_operation> operations;\n        {\n            std::lock_guard<std::mutex> lock(s_v79_mutex);\n            const auto identity_found =\n                s_v79_r5_operations_by_identity.find(identity);\n            if (identity_found == s_v79_r5_operations_by_identity.end())\n                return;\n            const auto generation_found =\n                identity_found->second.find(generation);\n            if (generation_found == identity_found->second.end())\n                return;\n            operations = generation_found->second;\n        }\n\n        for (const v79_r5_recorded_operation &operation : operations)\n        {\n            if (operation.kind == 1 && operation.resource_id != 0)\n            {\n                bool locked_resource = false;\n                {\n                    std::lock_guard<std::mutex> lock(s_v79_mutex);\n                    const auto found = s_v79_r3_locked_resources.find(\n                        operation.resource_id);\n                    locked_resource =\n                        found != s_v79_r3_locked_resources.end() &&\n                        found->second;\n                }\n                if (locked_resource &&\n                    (resources.empty() ||\n                     resources.back() != operation.resource_id))\n                    resources.push_back(operation.resource_id);\n            }\n            else if (operation.kind == 2 &&\n                     operation.child_identity != nullptr)\n            {\n                ++bundle_edges_followed;\n                v79_r5_collect_locked_resources(\n                    operation.child_identity,\n                    operation.child_generation,\n                    depth + 1, visited, resources,\n                    bundle_edges_followed);\n            }\n        }\n    }\n\n    void v79_r5_on_execute_command_lists(\n        ID3D12CommandQueue *queue,\n        UINT count,\n        ID3D12CommandList *const *command_lists)\n    {\n        (void)queue;\n        if (!v79_is_active() || command_lists == nullptr ||\n            !s_v79_r3_triplet_locked.load(std::memory_order_acquire) ||\n            s_v79_result_ready.load(std::memory_order_acquire))\n            return;\n\n        const bool strict = s_v61_rewritten_steady_state_seen.load(\n            std::memory_order_acquire);\n        const uint64_t submit_call =\n            s_v79_r5_queue_submit_call_count.fetch_add(\n                1, std::memory_order_acq_rel) + 1;\n        s_v79_r5_queue_submit_list_count.fetch_add(\n            count, std::memory_order_acq_rel);\n        uint64_t post_strict_submit_call =\n            s_v79_r5_post_strict_submit_call_count.load(\n                std::memory_order_acquire);\n        uint64_t post_strict_submit_lists =\n            s_v79_r5_post_strict_submit_list_count.load(\n                std::memory_order_acquire);\n        if (strict)\n        {\n            post_strict_submit_call =\n                s_v79_r5_post_strict_submit_call_count.fetch_add(\n                    1, std::memory_order_acq_rel) + 1;\n            post_strict_submit_lists =\n                s_v79_r5_post_strict_submit_list_count.fetch_add(\n                    count, std::memory_order_acq_rel) + count;\n        }\n\n        std::vector<uint64_t> submitted_resources;\n        uint64_t edges_followed = 0;\n        uint64_t resolved_lists = 0;\n        for (UINT index = 0; index < count; ++index)\n        {\n            ID3D12CommandList *list = nullptr;\n            if (!safe_copy_from_process(\n                    command_lists + index, &list, sizeof(list)) ||\n                list == nullptr)\n                continue;\n\n            ID3D12GraphicsCommandList *graphics_list =\n                reinterpret_cast<ID3D12GraphicsCommandList *>(list);\n            v79_r5_install_command_list_hooks(graphics_list);\n            void *const identity = v33_identity_pointer(\n                reinterpret_cast<IUnknown *>(list));\n            if (identity == nullptr)\n                continue;\n            const uint64_t generation =\n                v79_r5_current_generation(identity);\n            std::vector<v79_r5_command_key> visited;\n            std::vector<uint64_t> resolved;\n            uint64_t list_edges = 0;\n            v79_r5_collect_locked_resources(\n                identity, generation, 0, visited, resolved, list_edges);\n            edges_followed += list_edges;\n            if (!resolved.empty())\n                ++resolved_lists;\n            for (const uint64_t resource_id : resolved)\n            {\n                if (submitted_resources.empty() ||\n                    submitted_resources.back() != resource_id)\n                    submitted_resources.push_back(resource_id);\n            }\n        }\n        s_v79_r5_bundle_edges_followed_count.fetch_add(\n            edges_followed, std::memory_order_acq_rel);\n\n        if (submit_call <= 16 || submit_call % 120 == 0 ||\n            (strict && post_strict_submit_call == 1))\n            reshade::log::message(\n                reshade::log::level::info,\n                "D3DMetal RTX presented-frame producer chain v79 R5: QUEUE_SUBMIT submit_call=%llu command_list_count=%u raw_submit_calls=%llu raw_submit_lists=%llu post_strict_submit_calls=%llu post_strict_submit_lists=%llu resolved_lists=%llu bundle_edges_followed=%llu recorded_bundle_edges=%llu reset_generations=%llu hook_successes=%llu strict_rewritten_proof=%u commands_modified=0.",\n                static_cast<unsigned long long>(submit_call), count,\n                static_cast<unsigned long long>(\n                    s_v79_r5_queue_submit_call_count.load(\n                        std::memory_order_acquire)),\n                static_cast<unsigned long long>(\n                    s_v79_r5_queue_submit_list_count.load(\n                        std::memory_order_acquire)),\n                static_cast<unsigned long long>(\n                    s_v79_r5_post_strict_submit_call_count.load(\n                        std::memory_order_acquire)),\n                static_cast<unsigned long long>(\n                    s_v79_r5_post_strict_submit_list_count.load(\n                        std::memory_order_acquire)),\n                static_cast<unsigned long long>(resolved_lists),\n                static_cast<unsigned long long>(edges_followed),\n                static_cast<unsigned long long>(\n                    s_v79_r5_bundle_edge_count.load(\n                        std::memory_order_acquire)),\n                static_cast<unsigned long long>(\n                    s_v79_r5_reset_count.load(\n                        std::memory_order_acquire)),\n                static_cast<unsigned long long>(\n                    s_v79_r5_hook_install_success_count.load(\n                        std::memory_order_acquire)),\n                strict ? 1u : 0u);\n\n        if (submitted_resources.empty())\n        {\n            const uint64_t miss =\n                s_v79_r5_resolution_miss_count.fetch_add(\n                    1, std::memory_order_acq_rel) + 1;\n            uint64_t post_strict_miss =\n                s_v79_r5_post_strict_resolution_miss_count.load(\n                    std::memory_order_acquire);\n            if (strict)\n                post_strict_miss =\n                    s_v79_r5_post_strict_resolution_miss_count.fetch_add(\n                        1, std::memory_order_acq_rel) + 1;\n            if (miss <= 16 || miss % 120 == 0 ||\n                (strict && post_strict_miss == 1))\n                reshade::log::message(\n                    reshade::log::level::info,\n                    "D3DMetal RTX presented-frame producer chain v79 R5: BUNDLE_GRAPH_RESOLUTION hit=0 miss=%llu post_strict_resolution_misses=%llu submit_call=%llu command_list_count=%u bundle_edges_followed=%llu reason=no-recursive-path-to-frozen-triplet strict_rewritten_proof=%u commands_modified=0.",\n                    static_cast<unsigned long long>(miss),\n                    static_cast<unsigned long long>(\n                        s_v79_r5_post_strict_resolution_miss_count.load(\n                            std::memory_order_acquire)),\n                    static_cast<unsigned long long>(submit_call), count,\n                    static_cast<unsigned long long>(edges_followed),\n                    strict ? 1u : 0u);\n            return;\n        }\n\n        const uint64_t hit = s_v79_r5_resolution_hit_count.fetch_add(\n            1, std::memory_order_acq_rel) + 1;\n        uint64_t post_strict_hit =\n            s_v79_r5_post_strict_resolution_hit_count.load(\n                std::memory_order_acquire);\n        if (strict)\n            post_strict_hit =\n                s_v79_r5_post_strict_resolution_hit_count.fetch_add(\n                    1, std::memory_order_acq_rel) + 1;\n        std::vector<uint64_t> distinct;\n        for (const uint64_t resource_id : submitted_resources)\n            if (std::find(distinct.begin(), distinct.end(), resource_id) ==\n                distinct.end())\n                distinct.push_back(resource_id);\n        const bool ambiguous = distinct.size() > 1;\n        if (ambiguous)\n            s_v79_r5_resolution_ambiguous_count.fetch_add(\n                1, std::memory_order_acq_rel);\n\n        if (hit <= 32 || hit % 120 == 0 ||\n            (strict && post_strict_hit == 1))\n            reshade::log::message(\n                reshade::log::level::info,\n                "D3DMetal RTX presented-frame producer chain v79 R5: BUNDLE_GRAPH_RESOLUTION hit=1 resolution_hit=%llu post_strict_resolution_hits=%llu submit_call=%llu command_list_count=%u resolved_lists=%llu resolved_resource_events=%zu distinct_triplet_resources=%zu bundle_edges_followed=%llu ambiguous_submission=%u strict_rewritten_proof=%u commands_modified=0.",\n                static_cast<unsigned long long>(hit),\n                static_cast<unsigned long long>(\n                    s_v79_r5_post_strict_resolution_hit_count.load(\n                        std::memory_order_acquire)),\n                static_cast<unsigned long long>(submit_call), count,\n                static_cast<unsigned long long>(resolved_lists),\n                submitted_resources.size(), distinct.size(),\n                static_cast<unsigned long long>(edges_followed),\n                ambiguous ? 1u : 0u, strict ? 1u : 0u);\n\n        for (const uint64_t current : submitted_resources)\n        {\n            uint64_t previous = 0;\n            {\n                std::lock_guard<std::mutex> lock(s_v79_mutex);\n                previous = s_v79_r5_last_resolved_resource;\n                s_v79_r5_last_resolved_resource = current;\n            }\n            if (!strict || previous == 0 || previous == current)\n                continue;\n\n            v55_resource_info previous_info = {};\n            if (!v55_get_resource(previous, previous_info) ||\n                previous_info.resource == nullptr)\n                continue;\n\n            const uint64_t frame =\n                s_v79_r5_bundle_ring_frame_count.fetch_add(\n                    1, std::memory_order_acq_rel) + 1;\n            if (frame <= 24 || frame % 120 == 0)\n                reshade::log::message(\n                    reshade::log::level::info,\n                    "D3DMetal RTX presented-frame producer chain v79 R5: BUNDLE_RING_FRAME frame=%llu completed_resource_id=%llu next_resource_id=%llu format=%u dimensions=%llux%u boundary=recursive-submitted-bundle-graph bundle_edges_followed=%llu ambiguous_submission=%u commands_modified=0.",\n                    static_cast<unsigned long long>(frame),\n                    static_cast<unsigned long long>(previous),\n                    static_cast<unsigned long long>(current),\n                    previous_info.format,\n                    static_cast<unsigned long long>(previous_info.width),\n                    previous_info.height,\n                    static_cast<unsigned long long>(edges_followed),\n                    ambiguous ? 1u : 0u);\n            v79_process_present(previous_info.resource);\n        }\n    }\n\n' + text[r4_helper.start():]
    note("r5_helpers")

    # 7. Record R5 RTV operations at the established R3/R4 OMSetRenderTargets tail.
    om = unique_regex(
        r'(?m)^(?P<indent>[ \t]*)v79_r3_observe_rtv_sequence\s*'
        r'\(\s*resources\s*\)\s*;\s*\n'
        r'(?P=indent)v79_r4_recover_locked_writer_metadata\s*\(\s*\)\s*;',
        "rtv_stream")
    indent = om.group("indent")
    replacement = (
        indent + "v79_r5_install_command_list_hooks(command_list);\n" +
        indent + "v79_r5_record_rtv_event(command_list, resources);\n" +
        indent + "v79_r3_observe_rtv_sequence(resources);\n" +
        indent + "v79_r4_recover_locked_writer_metadata();"
    )
    text = text[:om.start()] + replacement + text[om.end():]
    note("rtv_stream")

    # 8. Insert the R5 active log after the exact R4 active message statement.
    marker = "D3DMetal RTX presented-frame producer chain v79 R4: ACTIVE"
    positions = [m.start() for m in re.finditer(re.escape(marker), text)]
    # One copy is in the R4 exported manifest and one is the runtime log.
    runtime_positions = [p for p in positions if "frozen-triplet-source=" in text[p:p+700]]
    if len(runtime_positions) != 1:
        fail("active_log", f"runtime_marker_count={len(runtime_positions)}")
    p = runtime_positions[0]
    call_start = text.rfind("reshade::log::message(", max(0, p - 300), p)
    call_end = text.find(");", p)
    if call_start < 0 or call_end < 0:
        fail("active_log", "runtime_log_statement_bounds_not_found")
    call_end += 2
    text = text[:call_end] + '\n                reshade::log::message(\n                    reshade::log::level::info,\n                    "D3DMetal RTX presented-frame producer chain v79 R5: ACTIVE frozen-triplet-source=R3 recording-time-OMSetRenderTargets frame-boundary=recursive-submitted-bundle-graph execute-bundle-slot=27 reset-slot=10 generation-tracking=enabled ordered-operation-stream=enabled max-bundle-depth=8 raw-post-strict-submission-counters=enabled static-command-list-writer-recovery=R4 strict-lineage-required-for-present-capture=1 GPU-readback=disabled injected-copies=disabled injected-barriers=disabled commands_modified=0.");' + text[call_end:]
    note("active_log")

    # Final structural gates before writing.
    required = [
        "V79_R5_BINARY_MARKER_MANIFEST_R5_EXECUTE_BUNDLE_GRAPH",
        "V79_R5_HOTFIX2_MARKER_DRIVEN_PATCHER",
        "V79_R5_EARLY_COMMAND_LIST_BOOTSTRAP",
        "v79_r5_trace_execute_bundle",
        "v79_r5_trace_reset",
        "v79_r5_on_execute_command_lists(queue, count, command_lists);",
        "v79_r5_record_rtv_event(command_list, resources);",
        "BUNDLE_GRAPH_RESOLUTION",
        "BUNDLE_RING_FRAME",
    ]
    missing = [m for m in required if m not in text]
    if missing:
        fail("final_gate", "missing=" + ",".join(missing))
    if text.count("V79_R5_EARLY_COMMAND_LIST_BOOTSTRAP") != 1:
        fail("final_gate", "bootstrap_count_not_one")
    if text.count("v79_r5_on_execute_command_lists(queue, count, command_lists);") != 1:
        fail("final_gate", "queue_callback_count_not_one")

    source.write_text(text, encoding="utf-8")
    note("source_write")

    Path("v79-r5-patch-report.txt").write_text(
        "\n".join([
            "V79_R5_EXECUTE_BUNDLE_GRAPH_PATCH_OK",
            "V79_R5_HOTFIX2_PATCH_OK",
            "BINARY_MANIFEST=V79_R5_BINARY_MARKER_MANIFEST_R5_EXECUTE_BUNDLE_GRAPH",
            "BINARY_HOTFIX_MARKER=V79_R5_HOTFIX2_MARKER_DRIVEN_PATCHER",
            "TRIPLET_SOURCE=V79_R3_FROZEN_RECORDING_TIME_TRIPLET",
            "STATIC_WRITER_RECOVERY=V79_R4",
            "EXECUTE_BUNDLE_SLOT=27",
            "EARLY_COMMAND_LIST_BOOTSTRAP=V33_CREATE_COMMAND_LIST_PATH",
            "HOTFIX2_ANCHOR_MODE=MARKER_DRIVEN_REGEX",
            "WHITESPACE_TOLERANCE=ENABLED",
            "OPTIONAL_STATIC_TOLERANCE=ENABLED",
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
    note("patch_report")
    print("V79_R5_EXECUTE_BUNDLE_GRAPH_PATCH_OK", flush=True)
    print("V79_R5_HOTFIX2_PATCH_OK", flush=True)
except SystemExit:
    raise
except Exception as exc:
    diagnostics.append("TRACEBACK_BEGIN")
    diagnostics.extend(traceback.format_exc().splitlines())
    diagnostics.append("TRACEBACK_END")
    save_diagnostics()
    fail("unexpected_exception", f"{type(exc).__name__}:{exc}")
