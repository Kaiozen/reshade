from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
for required in (
    "D3DMetal RTX execution trace v33:",
    "D3DMetal RTX indirect execution trace v34:",
    "D3DMetal RTX RT-state bind suppression control v45:",
):
    if required not in text:
        raise RuntimeError(f"V46 prerequisite is missing: {required}")
if "D3DMetal RTX non-RT PSO census v46:" in text:
    raise RuntimeError("V46 is already present")

def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)

globals_anchor = "\tstatic std::once_flag s_v45_active_log_once;\n"
if text.count(globals_anchor) != 1:
    raise RuntimeError(f"V46 globals anchor mismatch: {text.count(globals_anchor)}")

helper_anchor = "\tvoid v33_install_command_list_method_hooks(IUnknown *command_list)\n"
if text.count(helper_anchor) != 1:
    raise RuntimeError(f"V46 helper anchor mismatch: {text.count(helper_anchor)}")

helper = """
\tusing v46_reset_fn = HRESULT (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList *,
\t\tID3D12CommandAllocator *,
\t\tID3D12PipelineState *);
\tusing v46_draw_instanced_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList *, UINT, UINT, UINT, UINT);
\tusing v46_draw_indexed_instanced_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList *, UINT, UINT, UINT, INT, UINT);
\tusing v46_dispatch_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList *, UINT, UINT, UINT);
\tusing v46_set_pipeline_state_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList *, ID3D12PipelineState *);
\tusing v46_create_graphics_pso_fn = HRESULT (STDMETHODCALLTYPE *)(
\t\tID3D12Device *,
\t\tconst D3D12_GRAPHICS_PIPELINE_STATE_DESC *,
\t\tREFIID,
\t\tvoid **);
\tusing v46_create_compute_pso_fn = HRESULT (STDMETHODCALLTYPE *)(
\t\tID3D12Device *,
\t\tconst D3D12_COMPUTE_PIPELINE_STATE_DESC *,
\t\tREFIID,
\t\tvoid **);

\tconstexpr size_t v46_reset_slot = 10;
\tconstexpr size_t v46_draw_instanced_slot = 12;
\tconstexpr size_t v46_draw_indexed_instanced_slot = 13;
\tconstexpr size_t v46_dispatch_slot = 14;
\tconstexpr size_t v46_set_pipeline_state_slot = 25;
\tconstexpr size_t v46_create_graphics_pso_slot = 10;
\tconstexpr size_t v46_create_compute_pso_slot = 11;

\tstatic v46_reset_fn s_v46_original_reset = nullptr;
\tstatic v46_draw_instanced_fn s_v46_original_draw_instanced = nullptr;
\tstatic v46_draw_indexed_instanced_fn
\t\ts_v46_original_draw_indexed_instanced = nullptr;
\tstatic v46_dispatch_fn s_v46_original_dispatch = nullptr;
\tstatic v46_set_pipeline_state_fn
\t\ts_v46_original_set_pipeline_state = nullptr;
\tstatic v46_create_graphics_pso_fn
\t\ts_v46_original_create_graphics_pso = nullptr;
\tstatic v46_create_compute_pso_fn
\t\ts_v46_original_create_compute_pso = nullptr;

\tstruct v46_pso_metadata
\t{
\t\tunsigned int kind = 0; // 0=unknown, 1=graphics, 2=compute
\t\tuint64_t shader_hash = 0;
\t\tuint64_t vs_hash = 0;
\t\tuint64_t ps_hash = 0;
\t\tuint64_t cs_hash = 0;
\t};

\tstruct v46_pso_info
\t{
\t\tuint64_t pso_id = 0;
\t\tvoid *identity = nullptr;
\t\tv46_pso_metadata metadata = {};
\t\tuint64_t pre_binds = 0;
\t\tuint64_t post_binds = 0;
\t\tuint64_t pre_dispatch = 0;
\t\tuint64_t post_dispatch = 0;
\t\tuint64_t pre_draw = 0;
\t\tuint64_t post_draw = 0;
\t\tuint64_t pre_draw_indexed = 0;
\t\tuint64_t post_draw_indexed = 0;
\t\tuint64_t pre_indirect_dispatch = 0;
\t\tuint64_t post_indirect_dispatch = 0;
\t\tuint64_t pre_indirect_draw = 0;
\t\tuint64_t post_indirect_draw = 0;
\t\tuint64_t pre_indirect_draw_indexed = 0;
\t\tuint64_t post_indirect_draw_indexed = 0;
\t\tuint64_t pre_indirect_mesh = 0;
\t\tuint64_t post_indirect_mesh = 0;
\t};

\tstatic std::once_flag s_v46_command_hook_once;
\tstatic std::once_flag s_v46_device_hook_once;
\tstatic std::once_flag s_v46_active_log_once;
\tstatic std::mutex s_v46_mutex;
\tstatic std::unordered_map<void *, v46_pso_metadata>
\t\ts_v46_metadata_by_identity;
\tstatic std::unordered_map<void *, uint64_t>
\t\ts_v46_ids_by_identity;
\tstatic std::unordered_map<uint64_t, v46_pso_info>
\t\ts_v46_infos;
\tstatic std::unordered_map<ID3D12GraphicsCommandList *, uint64_t>
\t\ts_v46_bound_pso_ids;
\tstatic std::atomic<uint64_t> s_v46_next_pso_id = 0;
\tstatic std::atomic<uint64_t> s_v46_post_command_total = 0;

\tconst char *v46_kind_name(unsigned int kind)
\t{
\t\tswitch (kind)
\t\t{
\t\tcase 1: return "graphics";
\t\tcase 2: return "compute";
\t\tdefault: return "unknown";
\t\t}
\t}

\tbool v46_post_phase()
\t{
\t\treturn s_v45_suppressed_state_binds.load(
\t\t\tstd::memory_order_relaxed) != 0;
\t}

\tuint64_t v46_mix_hash(uint64_t hash, uint64_t value)
\t{
\t\tfor (unsigned int index = 0; index < 8; ++index)
\t\t{
\t\t\thash ^= static_cast<unsigned char>(
\t\t\t\t(value >> (index * 8)) & 0xFFull);
\t\t\thash *= 1099511628211ull;
\t\t}
\t\treturn hash;
\t}

\tuint64_t v46_hash_shader(const D3D12_SHADER_BYTECODE &bytecode)
\t{
\t\tif (bytecode.pShaderBytecode == nullptr ||
\t\t\tbytecode.BytecodeLength == 0)
\t\t\treturn 0;

\t\tuint64_t hash = 1469598103934665603ull;
\t\tconst auto *bytes = static_cast<const unsigned char *>(
\t\t\tbytecode.pShaderBytecode);
\t\tSIZE_T offset = 0;
\t\tunsigned char buffer[4096] = {};
\t\twhile (offset < bytecode.BytecodeLength)
\t\t{
\t\t\tconst SIZE_T remaining =
\t\t\t\tbytecode.BytecodeLength - offset;
\t\t\tconst SIZE_T amount =
\t\t\t\tremaining < sizeof(buffer) ? remaining : sizeof(buffer);
\t\t\tif (!safe_copy_from_process(
\t\t\t\t\tbytes + offset, buffer, amount))
\t\t\t\treturn 0;
\t\t\tfor (SIZE_T index = 0; index < amount; ++index)
\t\t\t{
\t\t\t\thash ^= buffer[index];
\t\t\t\thash *= 1099511628211ull;
\t\t\t}
\t\t\toffset += amount;
\t\t}
\t\treturn hash;
\t}

\tvoid v46_store_created_metadata(
\t\tID3D12PipelineState *pipeline_state,
\t\tconst v46_pso_metadata &metadata)
\t{
\t\tif (pipeline_state == nullptr)
\t\t\treturn;
\t\tvoid *const identity = v33_identity_pointer(
\t\t\treinterpret_cast<IUnknown *>(pipeline_state));
\t\tif (identity == nullptr)
\t\t\treturn;
\t\t{
\t\t\tstd::lock_guard<std::mutex> lock(s_v46_mutex);
\t\t\ts_v46_metadata_by_identity[identity] = metadata;
\t\t}
\t\treshade::log::message(
\t\t\treshade::log::level::info,
\t\t\t"D3DMetal RTX non-RT PSO census v46: PSO_CREATE kind=%s pipeline_state=%p identity=%p shader_hash=0x%llX vs_hash=0x%llX ps_hash=0x%llX cs_hash=0x%llX.",
\t\t\tv46_kind_name(metadata.kind),
\t\t\tpipeline_state,
\t\t\tidentity,
\t\t\tstatic_cast<unsigned long long>(metadata.shader_hash),
\t\t\tstatic_cast<unsigned long long>(metadata.vs_hash),
\t\t\tstatic_cast<unsigned long long>(metadata.ps_hash),
\t\t\tstatic_cast<unsigned long long>(metadata.cs_hash));
\t}

\tHRESULT STDMETHODCALLTYPE v46_trace_create_graphics_pso(
\t\tID3D12Device *device,
\t\tconst D3D12_GRAPHICS_PIPELINE_STATE_DESC *desc,
\t\tREFIID riid,
\t\tvoid **pipeline_state)
\t{
\t\tif (s_v46_original_create_graphics_pso == nullptr)
\t\t\treturn E_FAIL;

\t\tD3D12_GRAPHICS_PIPELINE_STATE_DESC snapshot = {};
\t\tconst bool readable =
\t\t\tdesc != nullptr &&
\t\t\tsafe_copy_from_process(desc, &snapshot, sizeof(snapshot));
\t\tconst HRESULT result = s_v46_original_create_graphics_pso(
\t\t\tdevice, desc, riid, pipeline_state);

\t\tvoid *created = nullptr;
\t\tif (pipeline_state != nullptr)
\t\t\tsafe_copy_from_process(
\t\t\t\tpipeline_state, &created, sizeof(created));
\t\tif (SUCCEEDED(result) && created != nullptr && readable)
\t\t{
\t\t\tv46_pso_metadata metadata = {};
\t\t\tmetadata.kind = 1;
\t\t\tmetadata.vs_hash = v46_hash_shader(snapshot.VS);
\t\t\tmetadata.ps_hash = v46_hash_shader(snapshot.PS);
\t\t\tmetadata.shader_hash = 1469598103934665603ull;
\t\t\tmetadata.shader_hash = v46_mix_hash(
\t\t\t\tmetadata.shader_hash, metadata.vs_hash);
\t\t\tmetadata.shader_hash = v46_mix_hash(
\t\t\t\tmetadata.shader_hash, metadata.ps_hash);
\t\t\tmetadata.shader_hash = v46_mix_hash(
\t\t\t\tmetadata.shader_hash, v46_hash_shader(snapshot.DS));
\t\t\tmetadata.shader_hash = v46_mix_hash(
\t\t\t\tmetadata.shader_hash, v46_hash_shader(snapshot.HS));
\t\t\tmetadata.shader_hash = v46_mix_hash(
\t\t\t\tmetadata.shader_hash, v46_hash_shader(snapshot.GS));
\t\t\tv46_store_created_metadata(
\t\t\t\treinterpret_cast<ID3D12PipelineState *>(created),
\t\t\t\tmetadata);
\t\t}
\t\treturn result;
\t}

\tHRESULT STDMETHODCALLTYPE v46_trace_create_compute_pso(
\t\tID3D12Device *device,
\t\tconst D3D12_COMPUTE_PIPELINE_STATE_DESC *desc,
\t\tREFIID riid,
\t\tvoid **pipeline_state)
\t{
\t\tif (s_v46_original_create_compute_pso == nullptr)
\t\t\treturn E_FAIL;

\t\tD3D12_COMPUTE_PIPELINE_STATE_DESC snapshot = {};
\t\tconst bool readable =
\t\t\tdesc != nullptr &&
\t\t\tsafe_copy_from_process(desc, &snapshot, sizeof(snapshot));
\t\tconst HRESULT result = s_v46_original_create_compute_pso(
\t\t\tdevice, desc, riid, pipeline_state);

\t\tvoid *created = nullptr;
\t\tif (pipeline_state != nullptr)
\t\t\tsafe_copy_from_process(
\t\t\t\tpipeline_state, &created, sizeof(created));
\t\tif (SUCCEEDED(result) && created != nullptr && readable)
\t\t{
\t\t\tv46_pso_metadata metadata = {};
\t\t\tmetadata.kind = 2;
\t\t\tmetadata.cs_hash = v46_hash_shader(snapshot.CS);
\t\t\tmetadata.shader_hash = metadata.cs_hash;
\t\t\tv46_store_created_metadata(
\t\t\t\treinterpret_cast<ID3D12PipelineState *>(created),
\t\t\t\tmetadata);
\t\t}
\t\treturn result;
\t}

\tvoid v46_install_pso_creation_hooks(ID3D12Device *device)
\t{
\t\tif (device == nullptr)
\t\t\treturn;
\t\tstd::call_once(
\t\t\ts_v46_device_hook_once,
\t\t\t[device]()
\t\t\t{
\t\t\t\tvoid **const vtable =
\t\t\t\t\t*reinterpret_cast<void ***>(device);
\t\t\t\ts_v46_original_create_graphics_pso =
\t\t\t\t\treinterpret_cast<v46_create_graphics_pso_fn>(
\t\t\t\t\t\tvtable[v46_create_graphics_pso_slot]);
\t\t\t\ts_v46_original_create_compute_pso =
\t\t\t\t\treinterpret_cast<v46_create_compute_pso_fn>(
\t\t\t\t\t\tvtable[v46_create_compute_pso_slot]);

\t\t\t\tDWORD old_protect = 0;
\t\t\t\tif (!VirtualProtect(
\t\t\t\t\t\t&vtable[v46_create_graphics_pso_slot],
\t\t\t\t\t\tsizeof(void *) * 2,
\t\t\t\t\t\tPAGE_EXECUTE_READWRITE,
\t\t\t\t\t\t&old_protect))
\t\t\t\t{
\t\t\t\t\treshade::log::message(
\t\t\t\t\t\treshade::log::level::warning,
\t\t\t\t\t\t"D3DMetal RTX non-RT PSO census v46: DEVICE_PSO_HOOKS installed=0 error=%lu.",
\t\t\t\t\t\tGetLastError());
\t\t\t\t\treturn;
\t\t\t\t}

\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t&vtable[v46_create_graphics_pso_slot]),
\t\t\t\t\treinterpret_cast<PVOID>(
\t\t\t\t\t\t&v46_trace_create_graphics_pso));
\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t&vtable[v46_create_compute_pso_slot]),
\t\t\t\t\treinterpret_cast<PVOID>(
\t\t\t\t\t\t&v46_trace_create_compute_pso));

\t\t\t\tDWORD ignored = 0;
\t\t\t\tVirtualProtect(
\t\t\t\t\t&vtable[v46_create_graphics_pso_slot],
\t\t\t\t\tsizeof(void *) * 2,
\t\t\t\t\told_protect,
\t\t\t\t\t&ignored);
\t\t\t\tFlushInstructionCache(
\t\t\t\t\tGetCurrentProcess(),
\t\t\t\t\t&vtable[v46_create_graphics_pso_slot],
\t\t\t\t\tsizeof(void *) * 2);

\t\t\t\tconst bool verified =
\t\t\t\t\tvtable[v46_create_graphics_pso_slot] ==
\t\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t\t&v46_trace_create_graphics_pso) &&
\t\t\t\t\tvtable[v46_create_compute_pso_slot] ==
\t\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t\t&v46_trace_create_compute_pso);
\t\t\t\treshade::log::message(
\t\t\t\t\tverified ?
\t\t\t\t\t\treshade::log::level::info :
\t\t\t\t\t\treshade::log::level::warning,
\t\t\t\t\t"D3DMetal RTX non-RT PSO census v46: DEVICE_PSO_HOOKS installed=%u graphics_slot=%zu compute_slot=%zu.",
\t\t\t\t\tverified ? 1u : 0u,
\t\t\t\t\tv46_create_graphics_pso_slot,
\t\t\t\t\tv46_create_compute_pso_slot);
\t\t\t});
\t}

\tuint64_t v46_register_pso(ID3D12PipelineState *pipeline_state)
\t{
\t\tif (pipeline_state == nullptr)
\t\t\treturn 0;
\t\tvoid *const identity = v33_identity_pointer(
\t\t\treinterpret_cast<IUnknown *>(pipeline_state));
\t\tif (identity == nullptr)
\t\t\treturn 0;

\t\tuint64_t pso_id = 0;
\t\tbool created = false;
\t\tv46_pso_info snapshot = {};
\t\t{
\t\t\tstd::lock_guard<std::mutex> lock(s_v46_mutex);
\t\t\tconst auto found = s_v46_ids_by_identity.find(identity);
\t\t\tif (found != s_v46_ids_by_identity.end())
\t\t\t{
\t\t\t\tpso_id = found->second;
\t\t\t}
\t\t\telse
\t\t\t{
\t\t\t\tpso_id = ++s_v46_next_pso_id;
\t\t\t\tv46_pso_info info = {};
\t\t\t\tinfo.pso_id = pso_id;
\t\t\t\tinfo.identity = identity;
\t\t\t\tconst auto meta =
\t\t\t\t\ts_v46_metadata_by_identity.find(identity);
\t\t\t\tif (meta != s_v46_metadata_by_identity.end())
\t\t\t\t\tinfo.metadata = meta->second;
\t\t\t\ts_v46_ids_by_identity[identity] = pso_id;
\t\t\t\ts_v46_infos[pso_id] = info;
\t\t\t\tsnapshot = info;
\t\t\t\tcreated = true;
\t\t\t}
\t\t}
\t\tif (created)
\t\t{
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::info,
\t\t\t\t"D3DMetal RTX non-RT PSO census v46: PSO_REGISTER pso_id=%llu pipeline_state=%p identity=%p kind=%s shader_hash=0x%llX vs_hash=0x%llX ps_hash=0x%llX cs_hash=0x%llX.",
\t\t\t\tstatic_cast<unsigned long long>(pso_id),
\t\t\t\tpipeline_state,
\t\t\t\tidentity,
\t\t\t\tv46_kind_name(snapshot.metadata.kind),
\t\t\t\tstatic_cast<unsigned long long>(
\t\t\t\t\tsnapshot.metadata.shader_hash),
\t\t\t\tstatic_cast<unsigned long long>(
\t\t\t\t\tsnapshot.metadata.vs_hash),
\t\t\t\tstatic_cast<unsigned long long>(
\t\t\t\t\tsnapshot.metadata.ps_hash),
\t\t\t\tstatic_cast<unsigned long long>(
\t\t\t\t\tsnapshot.metadata.cs_hash));
\t\t}
\t\treturn pso_id;
\t}

\tuint64_t v46_post_total(const v46_pso_info &info)
\t{
\t\treturn
\t\t\tinfo.post_dispatch +
\t\t\tinfo.post_draw +
\t\t\tinfo.post_draw_indexed +
\t\t\tinfo.post_indirect_dispatch +
\t\t\tinfo.post_indirect_draw +
\t\t\tinfo.post_indirect_draw_indexed +
\t\t\tinfo.post_indirect_mesh;
\t}

\tvoid v46_log_snapshot(
\t\tconst v46_pso_info &info,
\t\tconst char *trigger)
\t{
\t\treshade::log::message(
\t\t\treshade::log::level::info,
\t\t\t"D3DMetal RTX non-RT PSO census v46: PSO_SNAPSHOT pso_id=%llu kind=%s shader_hash=0x%llX vs_hash=0x%llX ps_hash=0x%llX cs_hash=0x%llX pre_binds=%llu post_binds=%llu pre_dispatch=%llu post_dispatch=%llu pre_draw=%llu post_draw=%llu pre_draw_indexed=%llu post_draw_indexed=%llu pre_indirect_dispatch=%llu post_indirect_dispatch=%llu pre_indirect_draw=%llu post_indirect_draw=%llu pre_indirect_draw_indexed=%llu post_indirect_draw_indexed=%llu pre_indirect_mesh=%llu post_indirect_mesh=%llu post_total=%llu trigger=%s.",
\t\t\tstatic_cast<unsigned long long>(info.pso_id),
\t\t\tv46_kind_name(info.metadata.kind),
\t\t\tstatic_cast<unsigned long long>(info.metadata.shader_hash),
\t\t\tstatic_cast<unsigned long long>(info.metadata.vs_hash),
\t\t\tstatic_cast<unsigned long long>(info.metadata.ps_hash),
\t\t\tstatic_cast<unsigned long long>(info.metadata.cs_hash),
\t\t\tstatic_cast<unsigned long long>(info.pre_binds),
\t\t\tstatic_cast<unsigned long long>(info.post_binds),
\t\t\tstatic_cast<unsigned long long>(info.pre_dispatch),
\t\t\tstatic_cast<unsigned long long>(info.post_dispatch),
\t\t\tstatic_cast<unsigned long long>(info.pre_draw),
\t\t\tstatic_cast<unsigned long long>(info.post_draw),
\t\t\tstatic_cast<unsigned long long>(info.pre_draw_indexed),
\t\t\tstatic_cast<unsigned long long>(info.post_draw_indexed),
\t\t\tstatic_cast<unsigned long long>(info.pre_indirect_dispatch),
\t\t\tstatic_cast<unsigned long long>(info.post_indirect_dispatch),
\t\t\tstatic_cast<unsigned long long>(info.pre_indirect_draw),
\t\t\tstatic_cast<unsigned long long>(info.post_indirect_draw),
\t\t\tstatic_cast<unsigned long long>(
\t\t\t\tinfo.pre_indirect_draw_indexed),
\t\t\tstatic_cast<unsigned long long>(
\t\t\t\tinfo.post_indirect_draw_indexed),
\t\t\tstatic_cast<unsigned long long>(info.pre_indirect_mesh),
\t\t\tstatic_cast<unsigned long long>(info.post_indirect_mesh),
\t\t\tstatic_cast<unsigned long long>(v46_post_total(info)),
\t\t\ttrigger);
\t}

\tvoid v46_bind_pso(
\t\tID3D12GraphicsCommandList *command_list,
\t\tID3D12PipelineState *pipeline_state,
\t\tconst char *trigger)
\t{
\t\tif (command_list == nullptr)
\t\t\treturn;
\t\tconst uint64_t pso_id = v46_register_pso(pipeline_state);
\t\tv46_pso_info snapshot = {};
\t\tbool should_log = false;
\t\t{
\t\t\tstd::lock_guard<std::mutex> lock(s_v46_mutex);
\t\t\tif (pso_id == 0)
\t\t\t{
\t\t\t\ts_v46_bound_pso_ids.erase(command_list);
\t\t\t\treturn;
\t\t\t}
\t\t\ts_v46_bound_pso_ids[command_list] = pso_id;
\t\t\tauto &info = s_v46_infos[pso_id];
\t\t\tif (v46_post_phase())
\t\t\t\t++info.post_binds;
\t\t\telse
\t\t\t\t++info.pre_binds;
\t\t\tsnapshot = info;
\t\t\tshould_log =
\t\t\t\tinfo.post_binds <= 4 ||
\t\t\t\t(info.post_binds % 240ull) == 0;
\t\t}
\t\tif (should_log)
\t\t\tv46_log_snapshot(snapshot, trigger);
\t}

\tuint64_t v46_lookup_bound_pso(
\t\tID3D12GraphicsCommandList *command_list)
\t{
\t\tif (command_list == nullptr)
\t\t\treturn 0;
\t\tstd::lock_guard<std::mutex> lock(s_v46_mutex);
\t\tconst auto found = s_v46_bound_pso_ids.find(command_list);
\t\treturn found != s_v46_bound_pso_ids.end() ?
\t\t\tfound->second : 0;
\t}

\tvoid v46_record_command(
\t\tID3D12GraphicsCommandList *command_list,
\t\tunsigned int kind,
\t\tuint64_t count,
\t\tconst char *trigger)
\t{
\t\tconst bool post = v46_post_phase();
\t\tif (post)
\t\t{
\t\t\tstd::call_once(
\t\t\t\ts_v46_active_log_once,
\t\t\t\t[]()
\t\t\t\t{
\t\t\t\t\treshade::log::message(
\t\t\t\t\t\treshade::log::level::info,
\t\t\t\t\t\t"D3DMetal RTX non-RT PSO census v46: ACTIVE phase-anchor=first-suppressed-rt-bind pso-creation-hashes=1 direct-dispatch-draw=1 indirect-dispatch-draw-mesh=1 behavior-modified=0.");
\t\t\t\t});
\t\t}

\t\tconst uint64_t pso_id =
\t\t\tv46_lookup_bound_pso(command_list);
\t\tif (pso_id == 0)
\t\t\treturn;

\t\tv46_pso_info snapshot = {};
\t\tuint64_t post_total = 0;
\t\tbool should_log = false;
\t\t{
\t\t\tstd::lock_guard<std::mutex> lock(s_v46_mutex);
\t\t\tauto found = s_v46_infos.find(pso_id);
\t\t\tif (found == s_v46_infos.end())
\t\t\t\treturn;
\t\t\tauto &info = found->second;
\t\t\tswitch (kind)
\t\t\t{
\t\t\tcase 1:
\t\t\t\t(post ? info.post_dispatch : info.pre_dispatch) += count;
\t\t\t\tbreak;
\t\t\tcase 2:
\t\t\t\t(post ? info.post_draw : info.pre_draw) += count;
\t\t\t\tbreak;
\t\t\tcase 3:
\t\t\t\t(post ? info.post_draw_indexed : info.pre_draw_indexed) += count;
\t\t\t\tbreak;
\t\t\tcase 4:
\t\t\t\t(post ? info.post_indirect_dispatch : info.pre_indirect_dispatch) += count;
\t\t\t\tbreak;
\t\t\tcase 5:
\t\t\t\t(post ? info.post_indirect_draw : info.pre_indirect_draw) += count;
\t\t\t\tbreak;
\t\t\tcase 6:
\t\t\t\t(post ? info.post_indirect_draw_indexed : info.pre_indirect_draw_indexed) += count;
\t\t\t\tbreak;
\t\t\tcase 7:
\t\t\t\t(post ? info.post_indirect_mesh : info.pre_indirect_mesh) += count;
\t\t\t\tbreak;
\t\t\tdefault:
\t\t\t\treturn;
\t\t\t}
\t\t\tsnapshot = info;
\t\t\tpost_total = v46_post_total(info);
\t\t\tshould_log =
\t\t\t\tpost &&
\t\t\t\t(post_total <= 8 ||
\t\t\t\t (post_total % 120ull) < count);
\t\t}
\t\tif (post)
\t\t\ts_v46_post_command_total += count;
\t\tif (should_log)
\t\t\tv46_log_snapshot(snapshot, trigger);
\t}

\tHRESULT STDMETHODCALLTYPE v46_trace_reset(
\t\tID3D12GraphicsCommandList *command_list,
\t\tID3D12CommandAllocator *allocator,
\t\tID3D12PipelineState *initial_state)
\t{
\t\tif (s_v46_original_reset == nullptr)
\t\t\treturn E_FAIL;
\t\tconst HRESULT result = s_v46_original_reset(
\t\t\tcommand_list, allocator, initial_state);
\t\tif (SUCCEEDED(result))
\t\t\tv46_bind_pso(command_list, initial_state, "reset");
\t\treturn result;
\t}

\tvoid STDMETHODCALLTYPE v46_trace_set_pipeline_state(
\t\tID3D12GraphicsCommandList *command_list,
\t\tID3D12PipelineState *pipeline_state)
\t{
\t\tv46_bind_pso(command_list, pipeline_state, "set-pso");
\t\tif (s_v46_original_set_pipeline_state != nullptr)
\t\t\ts_v46_original_set_pipeline_state(
\t\t\t\tcommand_list, pipeline_state);
\t}

\tvoid STDMETHODCALLTYPE v46_trace_dispatch(
\t\tID3D12GraphicsCommandList *command_list,
\t\tUINT x, UINT y, UINT z)
\t{
\t\tv46_record_command(command_list, 1, 1, "dispatch");
\t\tif (s_v46_original_dispatch != nullptr)
\t\t\ts_v46_original_dispatch(command_list, x, y, z);
\t}

\tvoid STDMETHODCALLTYPE v46_trace_draw_instanced(
\t\tID3D12GraphicsCommandList *command_list,
\t\tUINT vertex_count,
\t\tUINT instance_count,
\t\tUINT start_vertex,
\t\tUINT start_instance)
\t{
\t\tv46_record_command(command_list, 2, 1, "draw");
\t\tif (s_v46_original_draw_instanced != nullptr)
\t\t\ts_v46_original_draw_instanced(
\t\t\t\tcommand_list,
\t\t\t\tvertex_count,
\t\t\t\tinstance_count,
\t\t\t\tstart_vertex,
\t\t\t\tstart_instance);
\t}

\tvoid STDMETHODCALLTYPE v46_trace_draw_indexed_instanced(
\t\tID3D12GraphicsCommandList *command_list,
\t\tUINT index_count,
\t\tUINT instance_count,
\t\tUINT start_index,
\t\tINT base_vertex,
\t\tUINT start_instance)
\t{
\t\tv46_record_command(command_list, 3, 1, "draw-indexed");
\t\tif (s_v46_original_draw_indexed_instanced != nullptr)
\t\t\ts_v46_original_draw_indexed_instanced(
\t\t\t\tcommand_list,
\t\t\t\tindex_count,
\t\t\t\tinstance_count,
\t\t\t\tstart_index,
\t\t\t\tbase_vertex,
\t\t\t\tstart_instance);
\t}

\tvoid v46_install_nonrt_command_hooks(IUnknown *command_list)
\t{
\t\tif (command_list == nullptr)
\t\t\treturn;
\t\tstd::call_once(
\t\t\ts_v46_command_hook_once,
\t\t\t[command_list]()
\t\t\t{
\t\t\t\tID3D12GraphicsCommandList *list = nullptr;
\t\t\t\tconst HRESULT query_hr = command_list->QueryInterface(
\t\t\t\t\t__uuidof(ID3D12GraphicsCommandList),
\t\t\t\t\treinterpret_cast<void **>(&list));
\t\t\t\tif (FAILED(query_hr) || list == nullptr)
\t\t\t\t{
\t\t\t\t\treshade::log::message(
\t\t\t\t\t\treshade::log::level::warning,
\t\t\t\t\t\t"D3DMetal RTX non-RT PSO census v46: COMMAND_HOOKS installed=0 query_raw=0x%08X.",
\t\t\t\t\t\tstatic_cast<uint32_t>(query_hr));
\t\t\t\t\treturn;
\t\t\t\t}

\t\t\t\tvoid **const vtable =
\t\t\t\t\t*reinterpret_cast<void ***>(list);
\t\t\t\ts_v46_original_reset =
\t\t\t\t\treinterpret_cast<v46_reset_fn>(
\t\t\t\t\t\tvtable[v46_reset_slot]);
\t\t\t\ts_v46_original_draw_instanced =
\t\t\t\t\treinterpret_cast<v46_draw_instanced_fn>(
\t\t\t\t\t\tvtable[v46_draw_instanced_slot]);
\t\t\t\ts_v46_original_draw_indexed_instanced =
\t\t\t\t\treinterpret_cast<v46_draw_indexed_instanced_fn>(
\t\t\t\t\t\tvtable[v46_draw_indexed_instanced_slot]);
\t\t\t\ts_v46_original_dispatch =
\t\t\t\t\treinterpret_cast<v46_dispatch_fn>(
\t\t\t\t\t\tvtable[v46_dispatch_slot]);
\t\t\t\ts_v46_original_set_pipeline_state =
\t\t\t\t\treinterpret_cast<v46_set_pipeline_state_fn>(
\t\t\t\t\t\tvtable[v46_set_pipeline_state_slot]);

\t\t\t\tDWORD old_protect = 0;
\t\t\t\tif (!VirtualProtect(
\t\t\t\t\t\t&vtable[v46_reset_slot],
\t\t\t\t\t\tsizeof(void *) *
\t\t\t\t\t\t\t(v46_set_pipeline_state_slot -
\t\t\t\t\t\t\t v46_reset_slot + 1),
\t\t\t\t\t\tPAGE_EXECUTE_READWRITE,
\t\t\t\t\t\t&old_protect))
\t\t\t\t{
\t\t\t\t\treshade::log::message(
\t\t\t\t\t\treshade::log::level::warning,
\t\t\t\t\t\t"D3DMetal RTX non-RT PSO census v46: COMMAND_HOOKS installed=0 error=%lu.",
\t\t\t\t\t\tGetLastError());
\t\t\t\t\tlist->Release();
\t\t\t\t\treturn;
\t\t\t\t}

\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t&vtable[v46_reset_slot]),
\t\t\t\t\treinterpret_cast<PVOID>(&v46_trace_reset));
\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t&vtable[v46_draw_instanced_slot]),
\t\t\t\t\treinterpret_cast<PVOID>(
\t\t\t\t\t\t&v46_trace_draw_instanced));
\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t&vtable[v46_draw_indexed_instanced_slot]),
\t\t\t\t\treinterpret_cast<PVOID>(
\t\t\t\t\t\t&v46_trace_draw_indexed_instanced));
\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t&vtable[v46_dispatch_slot]),
\t\t\t\t\treinterpret_cast<PVOID>(&v46_trace_dispatch));
\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t&vtable[v46_set_pipeline_state_slot]),
\t\t\t\t\treinterpret_cast<PVOID>(
\t\t\t\t\t\t&v46_trace_set_pipeline_state));

\t\t\t\tDWORD ignored = 0;
\t\t\t\tVirtualProtect(
\t\t\t\t\t&vtable[v46_reset_slot],
\t\t\t\t\tsizeof(void *) *
\t\t\t\t\t\t(v46_set_pipeline_state_slot -
\t\t\t\t\t\t v46_reset_slot + 1),
\t\t\t\t\told_protect,
\t\t\t\t\t&ignored);
\t\t\t\tFlushInstructionCache(
\t\t\t\t\tGetCurrentProcess(),
\t\t\t\t\t&vtable[v46_reset_slot],
\t\t\t\t\tsizeof(void *) *
\t\t\t\t\t\t(v46_set_pipeline_state_slot -
\t\t\t\t\t\t v46_reset_slot + 1));

\t\t\t\tconst bool verified =
\t\t\t\t\tvtable[v46_reset_slot] ==
\t\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t\t&v46_trace_reset) &&
\t\t\t\t\tvtable[v46_draw_instanced_slot] ==
\t\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t\t&v46_trace_draw_instanced) &&
\t\t\t\t\tvtable[v46_draw_indexed_instanced_slot] ==
\t\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t\t&v46_trace_draw_indexed_instanced) &&
\t\t\t\t\tvtable[v46_dispatch_slot] ==
\t\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t\t&v46_trace_dispatch) &&
\t\t\t\t\tvtable[v46_set_pipeline_state_slot] ==
\t\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t\t&v46_trace_set_pipeline_state);
\t\t\t\treshade::log::message(
\t\t\t\t\tverified ?
\t\t\t\t\t\treshade::log::level::info :
\t\t\t\t\t\treshade::log::level::warning,
\t\t\t\t\t"D3DMetal RTX non-RT PSO census v46: COMMAND_HOOKS installed=%u reset_slot=%zu draw_slot=%zu draw_indexed_slot=%zu dispatch_slot=%zu set_pso_slot=%zu.",
\t\t\t\t\tverified ? 1u : 0u,
\t\t\t\t\tv46_reset_slot,
\t\t\t\t\tv46_draw_instanced_slot,
\t\t\t\t\tv46_draw_indexed_instanced_slot,
\t\t\t\t\tv46_dispatch_slot,
\t\t\t\t\tv46_set_pipeline_state_slot);
\t\t\t\tlist->Release();
\t\t\t});
\t}

\tvoid v46_record_nonray_indirect(
\t\tID3D12GraphicsCommandList *command_list,
\t\tuint64_t type_mask,
\t\tUINT max_command_count)
\t{
\t\tconst uint64_t count =
\t\t\tmax_command_count == 0 ? 1ull :
\t\t\tstatic_cast<uint64_t>(max_command_count);
\t\tif ((type_mask & 0x4ull) != 0)
\t\t\tv46_record_command(
\t\t\t\tcommand_list, 4, count, "indirect-dispatch");
\t\tif ((type_mask & 0x1ull) != 0)
\t\t\tv46_record_command(
\t\t\t\tcommand_list, 5, count, "indirect-draw");
\t\tif ((type_mask & 0x2ull) != 0)
\t\t\tv46_record_command(
\t\t\t\tcommand_list, 6, count, "indirect-draw-indexed");
\t\tif ((type_mask & 0x400ull) != 0)
\t\t\tv46_record_command(
\t\t\t\tcommand_list, 7, count, "indirect-mesh");
\t}
"""

text = text.replace(globals_anchor, globals_anchor + helper + "\n", 1)

create_call = (
    "\t\t\tv33_install_command_list_method_hooks(\n"
    "\t\t\t\treinterpret_cast<IUnknown *>(created));\n"
)
count = text.count(create_call)
if count != 2:
    raise RuntimeError(
        f"V46 command-list creation anchor mismatch: {count}")
create_replacement = (
    create_call +
    "\t\t\tv46_install_nonrt_command_hooks(\n"
    "\t\t\t\treinterpret_cast<IUnknown *>(created));\n"
)
text = text.replace(create_call, create_replacement)

device_anchor = (
    "\t\tif (device == nullptr)\n"
    "\t\t\treturn;\n\n"
    "\t\tv34_install_create_command_signature_hook(device);\n"
)
device_replacement = (
    "\t\tif (device == nullptr)\n"
    "\t\t\treturn;\n\n"
    "\t\tv46_install_pso_creation_hooks(device);\n"
    "\t\tv34_install_create_command_signature_hook(device);\n"
)
text = replace_once(
    text, device_anchor, device_replacement,
    "V46 device PSO hook installation")

indirect_anchor = (
    "\t\tconst bool dispatch_rays =\n"
    "\t\t\ttracked_signature && signature_info.dispatch_rays;\n\n"
    "\t\tuint64_t state_call = 0;\n"
)
indirect_replacement = (
    "\t\tconst bool dispatch_rays =\n"
    "\t\t\ttracked_signature && signature_info.dispatch_rays;\n"
    "\t\tif (tracked_signature && !dispatch_rays)\n"
    "\t\t\tv46_record_nonray_indirect(\n"
    "\t\t\t\tcommand_list,\n"
    "\t\t\t\tsignature_info.type_mask,\n"
    "\t\t\t\tmax_command_count);\n\n"
    "\t\tuint64_t state_call = 0;\n"
)
text = replace_once(
    text, indirect_anchor, indirect_replacement,
    "V46 non-ray ExecuteIndirect census")

required_markers = [
    "D3DMetal RTX non-RT PSO census v46: ACTIVE",
    "PSO_CREATE kind=",
    "PSO_REGISTER pso_id=",
    "PSO_SNAPSHOT pso_id=",
    "DEVICE_PSO_HOOKS installed=",
    "COMMAND_HOOKS installed=",
    "phase-anchor=first-suppressed-rt-bind",
    "indirect-dispatch-draw-mesh=1",
    "behavior-modified=0",
    "v46_install_pso_creation_hooks(device);",
    "v46_install_nonrt_command_hooks(",
    "v46_record_nonray_indirect(",
]
for marker in required_markers:
    if marker not in text:
        raise RuntimeError(f"Missing V46 source marker: {marker}")

for forbidden in (
    "\\tusing v46_reset_fn",
    "\\tstatic std::once_flag s_v46_command_hook_once",
    "\\tvoid v46_record_nonray_indirect",
):
    if forbidden in text:
        raise RuntimeError(
            f"V46 emitted a literal tab escape into C++ source: {forbidden}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v46-patch-report.txt")
report.write_text("\n".join([
    "V46_NONRT_PSO_CENSUS_PATCH_OK",
    "V45_RT_BIND_AND_RAY_DISPATCH_SUPPRESSION_PRESERVED=YES",
    "CREATE_GRAPHICS_PIPELINE_STATE_SLOT=10",
    "CREATE_COMPUTE_PIPELINE_STATE_SLOT=11",
    "RESET_SLOT=10",
    "DRAW_INSTANCED_SLOT=12",
    "DRAW_INDEXED_INSTANCED_SLOT=13",
    "DIRECT_DISPATCH_SLOT=14",
    "SET_PIPELINE_STATE_SLOT=25",
    "PSO_SHADER_BYTECODE_HASHING=ENABLED",
    "DIRECT_DISPATCH_CENSUS=ENABLED",
    "DIRECT_DRAW_CENSUS=ENABLED",
    "NONRAY_EXECUTE_INDIRECT_CENSUS=ENABLED",
    "RTX_PHASE_ANCHOR=FIRST_SUPPRESSED_RT_BIND",
    "GRAPHICS_AND_COMPUTE_COMMANDS_UNMODIFIED=YES",
    "NONRAY_EXECUTE_INDIRECT_UNMODIFIED=YES",
    "LITERAL_TAB_ESCAPES_IN_CPP=NO",
    "RESULT=PASS",
    "",
]), encoding="utf-8", newline="\n")
print(report.read_text(encoding="utf-8"))
