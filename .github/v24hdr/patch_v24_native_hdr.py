from pathlib import Path


def read(p):
    return Path(p).read_text(encoding='utf-8-sig')


def write(p, s):
    Path(p).write_text(s, encoding='utf-8', newline='\n')


def once(s, old, new, label):
    c = s.count(old)
    if c != 1:
        raise RuntimeError(f'{label}: expected 1, found {c}')
    return s.replace(old, new, 1)


# ======================================================================================
# HOTFIX5 architecture
# - Original native PSOs always go back to the game unchanged.
# - Matching RenoDX PS bytecode is compiled into a second *native* sidecar PSO.
# - Native command lists substitute the sidecar only after HDR presentation is proven active.
# - Stream PSOs (ID3D12Device2::CreatePipelineState) are covered, in addition to legacy graphics PSOs.
# - Pipeline-library loads are covered without wrapping the library object.
# - HDR swapchain conversion is ARMED only after at least one critical UberPost sidecar exists.
# ======================================================================================

sidecar_header = r'''#pragma once

#include "v24hdr_renodx_shaders.hpp"
#include "v24hdr_crc32_hash.hpp"
#include <atomic>
#include <cstdint>
#include <cstring>
#include <cwchar>
#include <mutex>
#include <unordered_map>
#include <unordered_set>
#include <vector>

// KAIOZEN V24 NATIVE HDR STREAM SIDECAR HOTFIX5
// Invariant: every game-visible D3D12 object remains the original native object.
// RenoDX-derived PSOs exist only as private native sidecars and are selected at command recording time.

static bool v24hdr_enabled()
{
    static const bool enabled = []() {
        wchar_t exe[MAX_PATH] = {};
        const DWORD n = GetModuleFileNameW(nullptr, exe, MAX_PATH);
        if (n == 0 || n >= MAX_PATH)
            return false;
        wchar_t *slash = wcsrchr(exe, L'\\');
        if (slash == nullptr)
            return false;
        *(slash + 1) = L'\0';
        wcscat_s(exe, L"KAIOZEN_ZZZ_NATIVE_HDR.ENABLE");
        return GetFileAttributesW(exe) != INVALID_FILE_ATTRIBUTES;
    }();
    return enabled;
}

static const v24hdr_shader_blob *v24hdr_find_shader(uint32_t crc)
{
    for (size_t i = 0; i < g_v24hdr_shader_count; ++i)
        if (g_v24hdr_shaders[i].crc32 == crc)
            return &g_v24hdr_shaders[i];
    return nullptr;
}

static bool v24hdr_is_critical_uberpost_crc(uint32_t crc)
{
    switch (crc)
    {
    case 0x011329C3u: case 0x06D90AA2u: case 0x0A7685ECu: case 0x0BD47EBAu:
    case 0x14317D70u: case 0x1E1BB7CBu: case 0x1E59D729u: case 0x1E69D07Du:
    case 0x21DEC524u: case 0x2862DFB8u: case 0x3978BC7Fu: case 0x5DD31DE1u:
    case 0x5DFB8E85u: case 0x617125FBu: case 0x76860566u: case 0x8FF706D2u:
    case 0x92AA9125u: case 0x97A92288u: case 0xA5BD36B0u: case 0xAFC76B07u:
    case 0xCC759B21u: case 0xD09F8758u: case 0xE9DDCE66u: case 0xF432415Bu:
        return true;
    default:
        return false;
    }
}

static std::atomic<bool> g_v24hdr_hdr_ready{false};
static std::atomic<bool> g_v24hdr_hdr_active{false};
static std::atomic<uint64_t> g_v24hdr_graphics_pso_calls{0};
static std::atomic<uint64_t> g_v24hdr_stream_pso_calls{0};
static std::atomic<uint64_t> g_v24hdr_stream_ps_subobjects{0};
static std::atomic<uint64_t> g_v24hdr_sidecar_candidates{0};
static std::atomic<uint64_t> g_v24hdr_sidecar_successes{0};
static std::atomic<uint64_t> g_v24hdr_sidecar_failures{0};
static std::atomic<uint64_t> g_v24hdr_critical_sidecars{0};
static std::atomic<uint64_t> g_v24hdr_set_pso_substitutions{0};
static std::atomic<uint64_t> g_v24hdr_reset_pso_substitutions{0};
static std::atomic<uint64_t> g_v24hdr_initial_pso_substitutions{0};
static std::atomic<uint64_t> g_v24hdr_command_list_hooks{0};
static std::atomic<uint64_t> g_v24hdr_pipeline_library_creates{0};
static std::atomic<uint64_t> g_v24hdr_pipeline_library_load_graphics{0};
static std::atomic<uint64_t> g_v24hdr_pipeline_library_load_stream{0};
static std::atomic<uint64_t> g_v24hdr_stream_parse_skips{0};
static std::atomic<uint64_t> g_v24hdr_adaptive_matches{0};
static std::atomic<uint64_t> g_v24hdr_adaptive_probes{0};
static std::atomic<uint64_t> g_v24hdr_adaptive_ambiguous{0};

static std::mutex g_v24hdr_sidecar_mutex;
static std::unordered_map<ID3D12PipelineState *, ID3D12PipelineState *> g_v24hdr_sidecars;
static std::unordered_set<uint32_t> g_v24hdr_critical_crc_set;
static std::unordered_set<uint32_t> g_v24hdr_observed_crc_set;
static std::unordered_set<void **> g_v24hdr_command_vtables;
static std::unordered_set<void **> g_v24hdr_library_vtables;

// Cross-translation-unit HDR gate used by DXGI.
bool v24hdr_should_attempt_hdr()
{
    return v24hdr_enabled() && g_v24hdr_hdr_ready.load(std::memory_order_acquire);
}

bool v24hdr_hdr_active()
{
    return v24hdr_enabled() && g_v24hdr_hdr_active.load(std::memory_order_acquire);
}

void v24hdr_set_hdr_active(bool active)
{
    if (!v24hdr_enabled())
        active = false;
    const bool previous = g_v24hdr_hdr_active.exchange(active, std::memory_order_acq_rel);
    if (previous != active)
    {
        reshade::log::message(
            reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: HDR_ACTIVE_%s critical=%llu sidecars=%llu.",
            active ? "ON" : "OFF",
            static_cast<unsigned long long>(g_v24hdr_critical_sidecars.load()),
            static_cast<unsigned long long>(g_v24hdr_sidecar_successes.load()));
    }
}

static ID3D12PipelineState *v24hdr_find_sidecar(ID3D12PipelineState *original)
{
    if (original == nullptr)
        return nullptr;
    std::lock_guard<std::mutex> lock(g_v24hdr_sidecar_mutex);
    const auto it = g_v24hdr_sidecars.find(original);
    return it == g_v24hdr_sidecars.end() ? nullptr : it->second;
}

static void v24hdr_register_sidecar(
    ID3D12PipelineState *original,
    ID3D12PipelineState *replacement,
    uint32_t crc,
    const char *source)
{
    if (original == nullptr || replacement == nullptr)
        return;

    bool inserted = false;
    bool new_critical = false;
    uint64_t critical_count = 0;
    {
        std::lock_guard<std::mutex> lock(g_v24hdr_sidecar_mutex);
        if (g_v24hdr_sidecars.find(original) == g_v24hdr_sidecars.end())
        {
            original->AddRef(); // Deliberately retain original identity to prevent pointer reuse in this one-test build.
            g_v24hdr_sidecars.emplace(original, replacement); // Own replacement's creation reference for process lifetime.
            inserted = true;
            if (v24hdr_is_critical_uberpost_crc(crc) && g_v24hdr_critical_crc_set.insert(crc).second)
            {
                new_critical = true;
                critical_count = ++g_v24hdr_critical_sidecars;
            }
        }
    }

    if (!inserted)
    {
        replacement->Release();
        return;
    }

    const uint64_t total = ++g_v24hdr_sidecar_successes;
    reshade::log::message(
        reshade::log::level::info,
        "KAIOZEN V24 HDR SIDECAR HOTFIX5: SIDECAR_SUCCESS source=%s crc=0x%08X critical=%u total=%llu original=%p sidecar=%p.",
        source, crc, v24hdr_is_critical_uberpost_crc(crc) ? 1u : 0u,
        static_cast<unsigned long long>(total), original, replacement);

    if (new_critical)
    {
        const bool was_ready = g_v24hdr_hdr_ready.exchange(true, std::memory_order_acq_rel);
        reshade::log::message(
            reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: CRITICAL_UBERPOST_SIDECAR crc=0x%08X unique=%llu.",
            crc,
            static_cast<unsigned long long>(critical_count));
        if (!was_ready)
        {
            reshade::log::message(
                reshade::log::level::info,
                "KAIOZEN V24 HDR SIDECAR HOTFIX5: HDR_READY armed=1 reason=critical_uberpost_sidecar crc=0x%08X.",
                crc);
        }
    }
}

static constexpr uint32_t v24hdr_fourcc(char a, char b, char c, char d)
{
    return static_cast<uint32_t>(static_cast<uint8_t>(a)) |
        (static_cast<uint32_t>(static_cast<uint8_t>(b)) << 8) |
        (static_cast<uint32_t>(static_cast<uint8_t>(c)) << 16) |
        (static_cast<uint32_t>(static_cast<uint8_t>(d)) << 24);
}

struct v24hdr_signature_fingerprint
{
    uint32_t input_crc = 0;
    uint32_t output_crc = 0;
    uint32_t input_size = 0;
    uint32_t output_size = 0;
    uint32_t mask = 0;
};

static bool v24hdr_read_u32(const uint8_t *data, size_t size, size_t offset, uint32_t &value)
{
    if (data == nullptr || offset > size || size - offset < sizeof(uint32_t))
        return false;
    std::memcpy(&value, data + offset, sizeof(value));
    return true;
}

static bool v24hdr_signature_fingerprint_of(
    const D3D12_SHADER_BYTECODE &bc,
    v24hdr_signature_fingerprint &fp)
{
    fp = {};
    if (bc.pShaderBytecode == nullptr || bc.BytecodeLength < 32)
        return false;

    const auto *data = static_cast<const uint8_t *>(bc.pShaderBytecode);
    if (std::memcmp(data, "DXBC", 4) != 0)
        return false;

    uint32_t total = 0, count = 0;
    if (!v24hdr_read_u32(data, bc.BytecodeLength, 24, total) ||
        !v24hdr_read_u32(data, bc.BytecodeLength, 28, count))
        return false;
    if (total > bc.BytecodeLength || count > 128 ||
        32ull + static_cast<uint64_t>(count) * 4ull > total)
        return false;

    for (uint32_t i = 0; i < count; ++i)
    {
        uint32_t off = 0;
        if (!v24hdr_read_u32(data, total, 32ull + static_cast<size_t>(i) * 4ull, off))
            continue;
        if (off > total || total - off < 8)
            continue;

        uint32_t tag = 0, part_size = 0;
        if (!v24hdr_read_u32(data, total, off, tag) ||
            !v24hdr_read_u32(data, total, static_cast<size_t>(off) + 4, part_size))
            continue;
        const size_t payload = static_cast<size_t>(off) + 8;
        if (payload > total || part_size > total - payload)
            continue;

        if (tag == v24hdr_fourcc('I','S','G','N') || tag == v24hdr_fourcc('I','S','G','1'))
        {
            fp.input_crc = compute_crc32(data + payload, part_size);
            fp.input_size = part_size;
            fp.mask |= 1u;
        }
        else if (
            tag == v24hdr_fourcc('O','S','G','N') ||
            tag == v24hdr_fourcc('O','S','G','1') ||
            tag == v24hdr_fourcc('O','S','G','5'))
        {
            fp.output_crc = compute_crc32(data + payload, part_size);
            fp.output_size = part_size;
            fp.mask |= 2u;
        }
    }

    return fp.mask == 3u && fp.input_crc != 0 && fp.output_crc != 0;
}

static const v24hdr_shader_blob *v24hdr_find_adaptive_shader(
    const D3D12_SHADER_BYTECODE &bc,
    uint32_t observed_crc)
{
    v24hdr_signature_fingerprint fp = {};
    if (!v24hdr_signature_fingerprint_of(bc, fp))
        return nullptr;

    const v24hdr_shader_blob *candidate = nullptr;
    uint32_t matches = 0;
    uint32_t size_candidates = 0;

    for (size_t i = 0; i < g_v24hdr_shader_count; ++i)
    {
        const auto &shader = g_v24hdr_shaders[i];
        if (!v24hdr_is_critical_uberpost_crc(shader.crc32))
            continue;
        if (shader.size != bc.BytecodeLength)
            continue;

        ++size_candidates;
        if (shader.signature_mask != 3u ||
            shader.input_sig_crc32 != fp.input_crc ||
            shader.output_sig_crc32 != fp.output_crc ||
            shader.input_sig_size != fp.input_size ||
            shader.output_sig_size != fp.output_size)
            continue;

        candidate = &shader;
        ++matches;
    }

    if (size_candidates != 0)
    {
        ++g_v24hdr_adaptive_probes;
        reshade::log::message(
            reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: PS_ADAPTIVE_PROBE observed_crc=0x%08X bytes=%llu size_candidates=%u signature_matches=%u isig=0x%08X/%u osig=0x%08X/%u.",
            observed_crc,
            static_cast<unsigned long long>(bc.BytecodeLength),
            size_candidates,
            matches,
            fp.input_crc,
            fp.input_size,
            fp.output_crc,
            fp.output_size);
    }

    // HOTFIX11: ZZZ 3.1 does not create one immutable UberPost CRC on every
    // world/load path. HOTFIX9 proved 0x4584C304, but HOTFIX10C later observed
    // the same game/world path without that CRC at all. Anchor the current-game
    // UberPost family on the DXBC input/output signature fingerprints measured
    // from the proven HOTFIX9 shader instead of a scene-dependent whole-blob CRC.
    //
    // This remains fail-closed: the signatures must match exactly and native
    // D3D12 PSO creation is still the final compatibility oracle. No successful
    // critical sidecar means HDR_READY remains false and the swapchain stays SDR.
    if (matches == 0 &&
        fp.input_crc == 0x0791E583u && fp.input_size == 352u &&
        fp.output_crc == 0xDB99520Bu && fp.output_size == 148u)
    {
        const auto *v31 = v24hdr_find_shader(0x06D90AA2u);
        if (v31 != nullptr && v24hdr_is_critical_uberpost_crc(v31->crc32))
        {
            ++g_v24hdr_adaptive_matches;
            reshade::log::message(
                reshade::log::level::info,
                "KAIOZEN V24 HDR SIDECAR HOTFIX11: V31_SEMANTIC_MAP observed_crc=0x%08X replacement_crc=0x06D90AA2 observed_bytes=%llu replacement_bytes=%llu isig=0x0791E583/352 osig=0xDB99520B/148 crc_gate=REMOVED compatibility=native_pso_creation_required.",
                observed_crc,
                static_cast<unsigned long long>(bc.BytecodeLength),
                static_cast<unsigned long long>(v31->size));
            return v31;
        }
    }

    if (matches != 1 || candidate == nullptr)
    {
        if (matches > 1)
            ++g_v24hdr_adaptive_ambiguous;
        return nullptr;
    }

    ++g_v24hdr_adaptive_matches;
    reshade::log::message(
        reshade::log::level::info,
        "KAIOZEN V24 HDR SIDECAR HOTFIX5: PS_ADAPTIVE_MATCH observed_crc=0x%08X replacement_crc=0x%08X bytes=%llu isig=0x%08X osig=0x%08X.",
        observed_crc,
        candidate->crc32,
        static_cast<unsigned long long>(bc.BytecodeLength),
        fp.input_crc,
        fp.output_crc);
    return candidate;
}

static bool v24hdr_match_shader_bytecode(
    const D3D12_SHADER_BYTECODE &bc,
    D3D12_SHADER_BYTECODE &replacement_bc,
    uint32_t &crc)
{
    crc = 0;
    if (bc.pShaderBytecode == nullptr || bc.BytecodeLength == 0)
        return false;

    const uint32_t observed_crc =
        compute_crc32(static_cast<const uint8_t *>(bc.pShaderBytecode), bc.BytecodeLength);

    const v24hdr_shader_blob *replacement = v24hdr_find_shader(observed_crc);
    bool adaptive = false;
    if (replacement == nullptr)
    {
        replacement = v24hdr_find_adaptive_shader(bc, observed_crc);
        adaptive = replacement != nullptr;
    }

    bool log_crc = false;
    {
        std::lock_guard<std::mutex> lock(g_v24hdr_sidecar_mutex);
        if (g_v24hdr_observed_crc_set.size() < 512)
            log_crc = g_v24hdr_observed_crc_set.insert(observed_crc).second;
    }
    if (log_crc)
    {
        reshade::log::message(
            reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: PS_CRC_OBSERVED crc=0x%08X matched=%u adaptive=%u bytes=%llu.",
            observed_crc,
            replacement != nullptr ? 1u : 0u,
            adaptive ? 1u : 0u,
            static_cast<unsigned long long>(bc.BytecodeLength));
    }

    if (replacement == nullptr)
    {
        crc = observed_crc;
        return false;
    }

    crc = replacement->crc32;
    replacement_bc.pShaderBytecode = replacement->data;
    replacement_bc.BytecodeLength = replacement->size;
    return true;
}

// Pipeline-state stream layout follows Microsoft's enum+payload pair alignment rule.
template <typename T, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE TypeValue>
struct alignas(void *) v24hdr_stream_subobject
{
    D3D12_PIPELINE_STATE_SUBOBJECT_TYPE type;
    T data;
};

template <typename T, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE TypeValue>
static constexpr size_t v24hdr_stream_size()
{
    return sizeof(v24hdr_stream_subobject<T, TypeValue>);
}

static size_t v24hdr_stream_subobject_size(D3D12_PIPELINE_STATE_SUBOBJECT_TYPE type)
{
    switch (type)
    {
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_ROOT_SIGNATURE: return v24hdr_stream_size<ID3D12RootSignature *, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_ROOT_SIGNATURE>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VS: return v24hdr_stream_size<D3D12_SHADER_BYTECODE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VS>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PS: return v24hdr_stream_size<D3D12_SHADER_BYTECODE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PS>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DS: return v24hdr_stream_size<D3D12_SHADER_BYTECODE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DS>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_HS: return v24hdr_stream_size<D3D12_SHADER_BYTECODE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_HS>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_GS: return v24hdr_stream_size<D3D12_SHADER_BYTECODE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_GS>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CS: return v24hdr_stream_size<D3D12_SHADER_BYTECODE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CS>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_STREAM_OUTPUT: return v24hdr_stream_size<D3D12_STREAM_OUTPUT_DESC, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_STREAM_OUTPUT>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_BLEND: return v24hdr_stream_size<D3D12_BLEND_DESC, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_BLEND>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_SAMPLE_MASK: return v24hdr_stream_size<UINT, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_SAMPLE_MASK>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_RASTERIZER: return v24hdr_stream_size<D3D12_RASTERIZER_DESC, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_RASTERIZER>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL: return v24hdr_stream_size<D3D12_DEPTH_STENCIL_DESC, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_INPUT_LAYOUT: return v24hdr_stream_size<D3D12_INPUT_LAYOUT_DESC, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_INPUT_LAYOUT>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_IB_STRIP_CUT_VALUE: return v24hdr_stream_size<D3D12_INDEX_BUFFER_STRIP_CUT_VALUE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_IB_STRIP_CUT_VALUE>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PRIMITIVE_TOPOLOGY: return v24hdr_stream_size<D3D12_PRIMITIVE_TOPOLOGY_TYPE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PRIMITIVE_TOPOLOGY>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_RENDER_TARGET_FORMATS: return v24hdr_stream_size<D3D12_RT_FORMAT_ARRAY, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_RENDER_TARGET_FORMATS>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL_FORMAT: return v24hdr_stream_size<DXGI_FORMAT, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL_FORMAT>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_SAMPLE_DESC: return v24hdr_stream_size<DXGI_SAMPLE_DESC, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_SAMPLE_DESC>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_NODE_MASK: return v24hdr_stream_size<UINT, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_NODE_MASK>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CACHED_PSO: return v24hdr_stream_size<D3D12_CACHED_PIPELINE_STATE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CACHED_PSO>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_FLAGS: return v24hdr_stream_size<D3D12_PIPELINE_STATE_FLAGS, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_FLAGS>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL1: return v24hdr_stream_size<D3D12_DEPTH_STENCIL_DESC1, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_DEPTH_STENCIL1>();
    case D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VIEW_INSTANCING: return v24hdr_stream_size<D3D12_VIEW_INSTANCING_DESC, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_VIEW_INSTANCING>();
    default: return 0;
    }
}

static bool v24hdr_prepare_stream_sidecar(
    const D3D12_PIPELINE_STATE_STREAM_DESC *source,
    std::vector<uint8_t> &storage,
    D3D12_PIPELINE_STATE_STREAM_DESC &copy_desc,
    uint32_t &matched_crc)
{
    matched_crc = 0;
    if (source == nullptr || source->pPipelineStateSubobjectStream == nullptr || source->SizeInBytes == 0 || source->SizeInBytes > 4 * 1024 * 1024)
        return false;

    storage.resize(source->SizeInBytes);
    std::memcpy(storage.data(), source->pPipelineStateSubobjectStream, source->SizeInBytes);

    bool changed = false;
    size_t offset = 0;
    while (offset < storage.size())
    {
        if (storage.size() - offset < sizeof(D3D12_PIPELINE_STATE_SUBOBJECT_TYPE))
            return false;
        auto *type_ptr = reinterpret_cast<D3D12_PIPELINE_STATE_SUBOBJECT_TYPE *>(storage.data() + offset);
        const D3D12_PIPELINE_STATE_SUBOBJECT_TYPE type = *type_ptr;
        const size_t sub_size = v24hdr_stream_subobject_size(type);
        if (sub_size == 0 || sub_size > storage.size() - offset)
        {
            const uint64_t skips = ++g_v24hdr_stream_parse_skips;
            if (skips <= 64)
                reshade::log::message(reshade::log::level::warning,
                    "KAIOZEN V24 HDR SIDECAR HOTFIX5: STREAM_PARSE_SKIP type=%u offset=%llu total_bytes=%llu.",
                    static_cast<unsigned>(type), static_cast<unsigned long long>(offset), static_cast<unsigned long long>(storage.size()));
            return false;
        }

        if (type == D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PS)
        {
            ++g_v24hdr_stream_ps_subobjects;
            using ps_sub = v24hdr_stream_subobject<D3D12_SHADER_BYTECODE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PS>;
            auto *ps = reinterpret_cast<ps_sub *>(storage.data() + offset);
            D3D12_SHADER_BYTECODE replacement = {};
            uint32_t crc = 0;
            if (v24hdr_match_shader_bytecode(ps->data, replacement, crc))
            {
                ps->data = replacement;
                if (matched_crc == 0)
                    matched_crc = crc;
                changed = true;
            }
        }
        else if (type == D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CACHED_PSO)
        {
            using cached_sub = v24hdr_stream_subobject<D3D12_CACHED_PIPELINE_STATE, D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CACHED_PSO>;
            auto *cached = reinterpret_cast<cached_sub *>(storage.data() + offset);
            cached->data.pCachedBlob = nullptr;
            cached->data.CachedBlobSizeInBytes = 0;
        }

        offset += sub_size;
    }

    if (!changed || offset != storage.size())
        return false;

    copy_desc = *source;
    copy_desc.pPipelineStateSubobjectStream = storage.data();
    return true;
}

static HRESULT STDMETHODCALLTYPE v24hdr_CreateGraphicsPipelineState(
    ID3D12Device *, const D3D12_GRAPHICS_PIPELINE_STATE_DESC *, REFIID, void **);
static HRESULT STDMETHODCALLTYPE v24hdr_CreatePipelineStateStream(
    ID3D12Device2 *, const D3D12_PIPELINE_STATE_STREAM_DESC *, REFIID, void **);
static void STDMETHODCALLTYPE v24hdr_SetPipelineState(
    ID3D12GraphicsCommandList *, ID3D12PipelineState *);

static void v24hdr_try_graphics_sidecar(
    ID3D12Device *device,
    const D3D12_GRAPHICS_PIPELINE_STATE_DESC *desc,
    ID3D12PipelineState *original,
    const char *source)
{
    if (!v24hdr_enabled() || device == nullptr || desc == nullptr || original == nullptr)
        return;

    D3D12_SHADER_BYTECODE replacement_bc = {};
    uint32_t crc = 0;
    if (!v24hdr_match_shader_bytecode(desc->PS, replacement_bc, crc))
        return;

    ++g_v24hdr_sidecar_candidates;
    D3D12_GRAPHICS_PIPELINE_STATE_DESC d = *desc;
    d.PS = replacement_bc;
    d.CachedPSO.pCachedBlob = nullptr;
    d.CachedPSO.CachedBlobSizeInBytes = 0;

    auto trampoline = reshade::hooks::call(
        v24hdr_CreateGraphicsPipelineState,
        reshade::hooks::vtable_from_instance(device) + 10);
    ID3D12PipelineState *replacement = nullptr;
    const HRESULT hr = trampoline(device, &d, IID_PPV_ARGS(&replacement));
    if (FAILED(hr) || replacement == nullptr)
    {
        ++g_v24hdr_sidecar_failures;
        reshade::log::message(reshade::log::level::warning,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: SIDECAR_FAIL source=%s kind=graphics crc=0x%08X hr=0x%08X game_pso_preserved=1.",
            source, crc, static_cast<unsigned>(hr));
        if (replacement != nullptr)
            replacement->Release();
        return;
    }
    v24hdr_register_sidecar(original, replacement, crc, source);
}

static void v24hdr_try_stream_sidecar(
    ID3D12Device2 *device,
    const D3D12_PIPELINE_STATE_STREAM_DESC *desc,
    ID3D12PipelineState *original,
    const char *source)
{
    if (!v24hdr_enabled() || device == nullptr || desc == nullptr || original == nullptr)
        return;

    std::vector<uint8_t> storage;
    D3D12_PIPELINE_STATE_STREAM_DESC copy_desc = {};
    uint32_t crc = 0;
    if (!v24hdr_prepare_stream_sidecar(desc, storage, copy_desc, crc))
        return;

    ++g_v24hdr_sidecar_candidates;
    auto trampoline = reshade::hooks::call(
        v24hdr_CreatePipelineStateStream,
        reshade::hooks::vtable_from_instance(device) + 47);
    ID3D12PipelineState *replacement = nullptr;
    const HRESULT hr = trampoline(device, &copy_desc, IID_PPV_ARGS(&replacement));
    if (FAILED(hr) || replacement == nullptr)
    {
        ++g_v24hdr_sidecar_failures;
        reshade::log::message(reshade::log::level::warning,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: SIDECAR_FAIL source=%s kind=stream crc=0x%08X hr=0x%08X game_pso_preserved=1.",
            source, crc, static_cast<unsigned>(hr));
        if (replacement != nullptr)
            replacement->Release();
        return;
    }
    v24hdr_register_sidecar(original, replacement, crc, source);
}

static ID3D12PipelineState *v24hdr_query_original_pso(void *object)
{
    if (object == nullptr)
        return nullptr;
    ID3D12PipelineState *pso = nullptr;
    reinterpret_cast<IUnknown *>(object)->QueryInterface(IID_PPV_ARGS(&pso));
    return pso;
}

static HRESULT STDMETHODCALLTYPE v24hdr_CreateGraphicsPipelineState(
    ID3D12Device *device,
    const D3D12_GRAPHICS_PIPELINE_STATE_DESC *desc,
    REFIID riid,
    void **ppPipelineState)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_CreateGraphicsPipelineState,
        reshade::hooks::vtable_from_instance(device) + 10);
    const uint64_t call = ++g_v24hdr_graphics_pso_calls;
    const HRESULT hr = trampoline(device, desc, riid, ppPipelineState); // Original first, byte-for-byte unchanged.
    if (SUCCEEDED(hr) && ppPipelineState != nullptr && *ppPipelineState != nullptr && desc != nullptr && v24hdr_enabled())
    {
        ID3D12PipelineState *original = v24hdr_query_original_pso(*ppPipelineState);
        if (original != nullptr)
        {
            v24hdr_try_graphics_sidecar(device, desc, original, "CreateGraphicsPipelineState");
            original->Release();
        }
    }
    if (call <= 16 || (call % 256) == 0)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: GRAPHICS_PSO_CALL total=%llu hr=0x%08X sidecars=%llu.",
            static_cast<unsigned long long>(call), static_cast<unsigned>(hr),
            static_cast<unsigned long long>(g_v24hdr_sidecar_successes.load()));
    return hr;
}

static HRESULT STDMETHODCALLTYPE v24hdr_CreatePipelineStateStream(
    ID3D12Device2 *device,
    const D3D12_PIPELINE_STATE_STREAM_DESC *desc,
    REFIID riid,
    void **ppPipelineState)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_CreatePipelineStateStream,
        reshade::hooks::vtable_from_instance(device) + 47);
    const uint64_t call = ++g_v24hdr_stream_pso_calls;
    const HRESULT hr = trampoline(device, desc, riid, ppPipelineState); // Game always receives original native PSO.
    if (SUCCEEDED(hr) && ppPipelineState != nullptr && *ppPipelineState != nullptr && desc != nullptr && v24hdr_enabled())
    {
        ID3D12PipelineState *original = v24hdr_query_original_pso(*ppPipelineState);
        if (original != nullptr)
        {
            v24hdr_try_stream_sidecar(device, desc, original, "CreatePipelineStateStream");
            original->Release();
        }
    }
    if (call <= 32 || (call % 128) == 0)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: STREAM_PSO_CALL total=%llu stream_ps=%llu sidecars=%llu parse_skips=%llu hr=0x%08X.",
            static_cast<unsigned long long>(call),
            static_cast<unsigned long long>(g_v24hdr_stream_ps_subobjects.load()),
            static_cast<unsigned long long>(g_v24hdr_sidecar_successes.load()),
            static_cast<unsigned long long>(g_v24hdr_stream_parse_skips.load()),
            static_cast<unsigned>(hr));
    return hr;
}

static HRESULT STDMETHODCALLTYPE v24hdr_CommandListReset(
    ID3D12GraphicsCommandList *list,
    ID3D12CommandAllocator *allocator,
    ID3D12PipelineState *initial)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_CommandListReset,
        reshade::hooks::vtable_from_instance(list) + 10);

    // Fail-open invariant: the game-visible Reset call is always executed with the
    // exact original PSO. Only after native Reset succeeds do we bind a private
    // sidecar via SetPipelineState, which has no HRESULT failure path.
    const HRESULT hr = trampoline(list, allocator, initial);
    if (SUCCEEDED(hr) && v24hdr_hdr_active() && initial != nullptr)
    {
        if (ID3D12PipelineState *sidecar = v24hdr_find_sidecar(initial))
        {
            auto set_trampoline = reshade::hooks::call(
                v24hdr_SetPipelineState,
                reshade::hooks::vtable_from_instance(list) + 25);
            set_trampoline(list, sidecar);
            const uint64_t count = ++g_v24hdr_reset_pso_substitutions;
            if (count <= 256)
                reshade::log::message(reshade::log::level::info,
                    "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESET_PSO_SUBSTITUTE total=%llu original=%p sidecar=%p original_reset_hr=0x%08X.",
                    static_cast<unsigned long long>(count), initial, sidecar, static_cast<unsigned>(hr));
        }
    }
    return hr;
}

static void STDMETHODCALLTYPE v24hdr_SetPipelineState(
    ID3D12GraphicsCommandList *list,
    ID3D12PipelineState *pipeline)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_SetPipelineState,
        reshade::hooks::vtable_from_instance(list) + 25);
    ID3D12PipelineState *selected = pipeline;
    if (v24hdr_hdr_active() && pipeline != nullptr)
    {
        if (ID3D12PipelineState *sidecar = v24hdr_find_sidecar(pipeline))
        {
            selected = sidecar;
            const uint64_t count = ++g_v24hdr_set_pso_substitutions;
            if (count <= 1024 || (count % 1024) == 0)
                reshade::log::message(reshade::log::level::info,
                    "KAIOZEN V24 HDR SIDECAR HOTFIX5: PSO_BIND_SUBSTITUTE total=%llu original=%p sidecar=%p.",
                    static_cast<unsigned long long>(count), pipeline, sidecar);
        }
    }
    trampoline(list, selected);
}

static void v24hdr_install_command_list_hooks(IUnknown *object)
{
    if (!v24hdr_enabled() || object == nullptr)
        return;
    ID3D12GraphicsCommandList *list = nullptr;
    if (FAILED(object->QueryInterface(IID_PPV_ARGS(&list))) || list == nullptr)
        return;

    auto *vtable = reshade::hooks::vtable_from_instance(list);
    bool fresh = false;
    {
        std::lock_guard<std::mutex> lock(g_v24hdr_sidecar_mutex);
        fresh = g_v24hdr_command_vtables.insert(vtable).second;
    }
    if (fresh)
    {
        const bool reset = reshade::hooks::install(
            "ID3D12GraphicsCommandList::Reset [V24HDR5]", vtable, 10, &v24hdr_CommandListReset);
        const bool setpso = reshade::hooks::install(
            "ID3D12GraphicsCommandList::SetPipelineState [V24HDR5]", vtable, 25, &v24hdr_SetPipelineState);
        if (reset || setpso)
            ++g_v24hdr_command_list_hooks;
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: COMMAND_LIST_HOOK reset=%u set_pso=%u vtable=%p total=%llu.",
            reset ? 1u : 0u, setpso ? 1u : 0u, vtable,
            static_cast<unsigned long long>(g_v24hdr_command_list_hooks.load()));
    }
    list->Release();
}

static HRESULT STDMETHODCALLTYPE v24hdr_CreateCommandList(
    ID3D12Device *device,
    UINT nodeMask,
    D3D12_COMMAND_LIST_TYPE type,
    ID3D12CommandAllocator *allocator,
    ID3D12PipelineState *initial,
    REFIID riid,
    void **ppCommandList)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_CreateCommandList,
        reshade::hooks::vtable_from_instance(device) + 12);

    // Fail-open invariant: create the native command list with the exact original
    // initial PSO first. Sidecar state is applied only after successful creation.
    const HRESULT hr = trampoline(device, nodeMask, type, allocator, initial, riid, ppCommandList);
    if (SUCCEEDED(hr) && ppCommandList != nullptr && *ppCommandList != nullptr)
    {
        v24hdr_install_command_list_hooks(reinterpret_cast<IUnknown *>(*ppCommandList));
        if (v24hdr_hdr_active() && initial != nullptr)
        {
            if (ID3D12PipelineState *sidecar = v24hdr_find_sidecar(initial))
            {
                ID3D12GraphicsCommandList *list = nullptr;
                if (SUCCEEDED(reinterpret_cast<IUnknown *>(*ppCommandList)->QueryInterface(IID_PPV_ARGS(&list))) && list != nullptr)
                {
                    auto set_trampoline = reshade::hooks::call(
                        v24hdr_SetPipelineState,
                        reshade::hooks::vtable_from_instance(list) + 25);
                    set_trampoline(list, sidecar);
                    ++g_v24hdr_initial_pso_substitutions;
                    list->Release();
                }
            }
        }
    }
    return hr;
}

static HRESULT STDMETHODCALLTYPE v24hdr_CreateCommandList1(
    ID3D12Device4 *device,
    UINT nodeMask,
    D3D12_COMMAND_LIST_TYPE type,
    D3D12_COMMAND_LIST_FLAGS flags,
    REFIID riid,
    void **ppCommandList)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_CreateCommandList1,
        reshade::hooks::vtable_from_instance(device) + 51);
    const HRESULT hr = trampoline(device, nodeMask, type, flags, riid, ppCommandList);
    if (SUCCEEDED(hr) && ppCommandList != nullptr && *ppCommandList != nullptr)
        v24hdr_install_command_list_hooks(reinterpret_cast<IUnknown *>(*ppCommandList));
    return hr;
}

static HRESULT STDMETHODCALLTYPE v24hdr_LoadGraphicsPipeline(
    ID3D12PipelineLibrary *library,
    LPCWSTR name,
    const D3D12_GRAPHICS_PIPELINE_STATE_DESC *desc,
    REFIID riid,
    void **ppPipelineState)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_LoadGraphicsPipeline,
        reshade::hooks::vtable_from_instance(library) + 8);
    const uint64_t load_call = ++g_v24hdr_pipeline_library_load_graphics;
    const HRESULT hr = trampoline(library, name, desc, riid, ppPipelineState);
    if (load_call <= 64)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: PIPELINE_LIBRARY_LOAD_GRAPHICS total=%llu hr=0x%08X.",
            static_cast<unsigned long long>(load_call), static_cast<unsigned>(hr));
    if (SUCCEEDED(hr) && ppPipelineState != nullptr && *ppPipelineState != nullptr && desc != nullptr)
    {
        ID3D12Device *device = nullptr;
        ID3D12PipelineState *original = v24hdr_query_original_pso(*ppPipelineState);
        if (original != nullptr && SUCCEEDED(library->GetDevice(IID_PPV_ARGS(&device))) && device != nullptr)
        {
            v24hdr_try_graphics_sidecar(device, desc, original, "PipelineLibrary.LoadGraphicsPipeline");
            device->Release();
        }
        if (original != nullptr)
            original->Release();
    }
    return hr;
}

static HRESULT STDMETHODCALLTYPE v24hdr_LoadPipeline(
    ID3D12PipelineLibrary1 *library,
    LPCWSTR name,
    const D3D12_PIPELINE_STATE_STREAM_DESC *desc,
    REFIID riid,
    void **ppPipelineState)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_LoadPipeline,
        reshade::hooks::vtable_from_instance(library) + 12);
    const uint64_t load_call = ++g_v24hdr_pipeline_library_load_stream;
    const HRESULT hr = trampoline(library, name, desc, riid, ppPipelineState);
    if (load_call <= 64)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: PIPELINE_LIBRARY_LOAD_STREAM total=%llu hr=0x%08X.",
            static_cast<unsigned long long>(load_call), static_cast<unsigned>(hr));
    if (SUCCEEDED(hr) && ppPipelineState != nullptr && *ppPipelineState != nullptr && desc != nullptr)
    {
        ID3D12Device2 *device2 = nullptr;
        ID3D12PipelineState *original = v24hdr_query_original_pso(*ppPipelineState);
        if (original != nullptr && SUCCEEDED(library->GetDevice(IID_PPV_ARGS(&device2))) && device2 != nullptr)
        {
            v24hdr_try_stream_sidecar(device2, desc, original, "PipelineLibrary1.LoadPipeline");
            device2->Release();
        }
        if (original != nullptr)
            original->Release();
    }
    return hr;
}

static void v24hdr_install_pipeline_library_hooks(IUnknown *object)
{
    if (!v24hdr_enabled() || object == nullptr)
        return;
    ID3D12PipelineLibrary *library = nullptr;
    if (FAILED(object->QueryInterface(IID_PPV_ARGS(&library))) || library == nullptr)
        return;
    auto *vtable = reshade::hooks::vtable_from_instance(library);
    bool fresh = false;
    {
        std::lock_guard<std::mutex> lock(g_v24hdr_sidecar_mutex);
        fresh = g_v24hdr_library_vtables.insert(vtable).second;
    }
    if (fresh)
    {
        const bool load_graphics = reshade::hooks::install(
            "ID3D12PipelineLibrary::LoadGraphicsPipeline [V24HDR5]", vtable, 8, &v24hdr_LoadGraphicsPipeline);
        ID3D12PipelineLibrary1 *library1 = nullptr;
        bool load_stream = false;
        if (SUCCEEDED(library->QueryInterface(IID_PPV_ARGS(&library1))) && library1 != nullptr)
        {
            load_stream = reshade::hooks::install(
                "ID3D12PipelineLibrary1::LoadPipeline [V24HDR5]",
                reshade::hooks::vtable_from_instance(library1), 12, &v24hdr_LoadPipeline);
            library1->Release();
        }
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: PIPELINE_LIBRARY_HOOK load_graphics=%u load_stream=%u vtable=%p.",
            load_graphics ? 1u : 0u, load_stream ? 1u : 0u, vtable);
    }
    library->Release();
}

static HRESULT STDMETHODCALLTYPE v24hdr_CreatePipelineLibrary(
    ID3D12Device1 *device,
    const void *blob,
    SIZE_T length,
    REFIID riid,
    void **ppPipelineLibrary)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_CreatePipelineLibrary,
        reshade::hooks::vtable_from_instance(device) + 44);
    const uint64_t create_call = ++g_v24hdr_pipeline_library_creates;
    const HRESULT hr = trampoline(device, blob, length, riid, ppPipelineLibrary);
    if (create_call <= 16)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: PIPELINE_LIBRARY_CREATE total=%llu bytes=%llu hr=0x%08X.",
            static_cast<unsigned long long>(create_call), static_cast<unsigned long long>(length), static_cast<unsigned>(hr));
    if (SUCCEEDED(hr) && ppPipelineLibrary != nullptr && *ppPipelineLibrary != nullptr)
        v24hdr_install_pipeline_library_hooks(reinterpret_cast<IUnknown *>(*ppPipelineLibrary));
    return hr;
}

static void v24hdr_install_device_hooks(ID3D12Device *device)
{
    if (!v24hdr_enabled() || device == nullptr)
        return;

    auto *base_vtable = reshade::hooks::vtable_from_instance(device);
    const bool graphics = reshade::hooks::install(
        "ID3D12Device::CreateGraphicsPipelineState [V24HDR5]", base_vtable, 10, &v24hdr_CreateGraphicsPipelineState);
    const bool command_list = reshade::hooks::install(
        "ID3D12Device::CreateCommandList [V24HDR5]", base_vtable, 12, &v24hdr_CreateCommandList);

    bool stream = false;
    ID3D12Device2 *device2 = nullptr;
    if (SUCCEEDED(device->QueryInterface(IID_PPV_ARGS(&device2))) && device2 != nullptr)
    {
        stream = reshade::hooks::install(
            "ID3D12Device2::CreatePipelineState [V24HDR5]",
            reshade::hooks::vtable_from_instance(device2), 47, &v24hdr_CreatePipelineStateStream);
        device2->Release();
    }

    bool pipeline_library = false;
    ID3D12Device1 *device1 = nullptr;
    if (SUCCEEDED(device->QueryInterface(IID_PPV_ARGS(&device1))) && device1 != nullptr)
    {
        pipeline_library = reshade::hooks::install(
            "ID3D12Device1::CreatePipelineLibrary [V24HDR5]",
            reshade::hooks::vtable_from_instance(device1), 44, &v24hdr_CreatePipelineLibrary);
        device1->Release();
    }

    bool command_list1 = false;
    ID3D12Device4 *device4 = nullptr;
    if (SUCCEEDED(device->QueryInterface(IID_PPV_ARGS(&device4))) && device4 != nullptr)
    {
        command_list1 = reshade::hooks::install(
            "ID3D12Device4::CreateCommandList1 [V24HDR5]",
            reshade::hooks::vtable_from_instance(device4), 51, &v24hdr_CreateCommandList1);
        device4->Release();
    }

    reshade::log::message(
        reshade::log::level::info,
        "KAIOZEN V24 HDR SIDECAR HOTFIX5: ACTIVE shader_count=%llu native_identity=1 addon_runtime=0 sidecar_psos=1 arm_before_hdr=1 graphics_hook=%u stream_hook=%u library_hook=%u command_list_hook=%u command_list1_hook=%u.",
        static_cast<unsigned long long>(g_v24hdr_shader_count),
        graphics ? 1u : 0u,
        stream ? 1u : 0u,
        pipeline_library ? 1u : 0u,
        command_list ? 1u : 0u,
        command_list1 ? 1u : 0u);
}
'''

# Write helper header first. It is included only by d3d12.cpp, so external HDR gate symbols have one definition.
Path('source/d3d12/v24hdr_sidecar_hotfix5.hpp').write_text(sidecar_header, encoding='utf-8', newline='\n')

# ======================================================================================
# D3D12: include sidecar helper and install native hooks before V24 returns native device.
# ======================================================================================
p = Path('source/d3d12/d3d12.cpp')
s = read(p)
if 'V24 HDR SIDECAR HOTFIX5' in s or 'v24hdr_sidecar_hotfix5.hpp' in s:
    raise RuntimeError('already patched HOTFIX5')
s = once(
    s,
    '#include "addon_manager.hpp"\n',
    '#include "addon_manager.hpp"\n#include "v24hdr_sidecar_hotfix5.hpp"\n',
    'd3d12 HOTFIX5 include',
)
early = (
    '#if RESHADE_ADDON >= 2\n'
    '\t// Balance the temporary add-on-manager reference without constructing a COM proxy.\n'
)
insert = (
    '\t// HOTFIX5: install native PSO/stream/command-list sidecar hooks; game-visible COM identity stays native.\n'
    '\tv24hdr_install_device_hooks(static_cast<ID3D12Device *>(*ppDevice));\n' + early
)
s = once(s, early, insert, 'V24 native early return HOTFIX5 hook')
write(p, s)

# Shared DXGI gate header.
dxgi_gate = r'''#pragma once

// Defined in d3d12.cpp. DXGI is allowed to enter HDR only after a critical native sidecar PSO exists.
extern bool v24hdr_should_attempt_hdr();
extern bool v24hdr_hdr_active();
extern void v24hdr_set_hdr_active(bool active);

static bool v24hdr_is_native_d3d12_queue_hotfix5(IUnknown *object)
{
    if (object == nullptr)
        return false;
    ID3D12CommandQueue *queue = nullptr;
    const HRESULT hr = object->QueryInterface(IID_PPV_ARGS(&queue));
    if (queue != nullptr)
        queue->Release();
    return SUCCEEDED(hr);
}

static bool v24hdr_apply_hdr10_hotfix5(IUnknown *swapchain, const char *phase)
{
    if (swapchain == nullptr)
        return false;
    IDXGISwapChain3 *sc3 = nullptr;
    if (FAILED(swapchain->QueryInterface(IID_PPV_ARGS(&sc3))) || sc3 == nullptr)
        return false;
    UINT support = 0;
    const HRESULT check = sc3->CheckColorSpaceSupport(DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020, &support);
    if (FAILED(check) || (support & DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT) == 0)
    {
        reshade::log::message(reshade::log::level::warning,
            "KAIOZEN V24 HDR SIDECAR HOTFIX5: HDR10_UNSUPPORTED phase=%s check=0x%08X support=0x%X.",
            phase, static_cast<unsigned>(check), support);
        sc3->Release();
        return false;
    }
    const HRESULT set = sc3->SetColorSpace1(DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020);
    reshade::log::message(SUCCEEDED(set) ? reshade::log::level::info : reshade::log::level::warning,
        "KAIOZEN V24 HDR SIDECAR HOTFIX5: HDR10_SET phase=%s check=0x%08X support=0x%X set=0x%08X.",
        phase, static_cast<unsigned>(check), support, static_cast<unsigned>(set));
    sc3->Release();
    return SUCCEEDED(set);
}
'''
Path('source/dxgi/v24hdr_dxgi_gate_hotfix5.hpp').write_text(dxgi_gate, encoding='utf-8', newline='\n')

# ======================================================================================
# DXGI creation: ARM-BEFORE-HDR. No shader readiness = exact coherent R8 SDR.
# If R10 or HDR10 colorspace fails, destroy the experimental swapchain and retry R8.
# ======================================================================================
p = Path('source/dxgi/dxgi.cpp')
s = read(p)
s = once(s, '#include "addon_manager.hpp"\n', '#include "addon_manager.hpp"\n#include "v24hdr_dxgi_gate_hotfix5.hpp"\n', 'dxgi HOTFIX5 include')
fn = 'HRESULT STDMETHODCALLTYPE IDXGIFactory2_CreateSwapChainForHwnd_Impl'
pos = s.find(fn)
if pos < 0:
    raise RuntimeError('CreateSwapChainForHwnd impl missing')
end = s.find('HRESULT STDMETHODCALLTYPE IDXGIFactory2_CreateSwapChainForCoreWindow', pos)
if end < 0:
    raise RuntimeError('CreateSwapChainForHwnd end missing')
chunk = s[pos:end]

# Apply the HDR decision only after V24/ReShade's ordinary descriptor modifications are complete.
old = '\tconst bool modified = dump_and_modify_swapchain_desc(direct3d_version, desc, sync_interval, &fullscreen_desc, hWnd);\n'
new = (
    '\tbool modified = dump_and_modify_swapchain_desc(direct3d_version, desc, sync_interval, &fullscreen_desc, hWnd);\n'
    '\tconst bool v24hdr_candidate = v24hdr_is_native_d3d12_queue_hotfix5(pDevice) && desc.Format == DXGI_FORMAT_R8G8B8A8_UNORM;\n'
    '\tconst DXGI_SWAP_CHAIN_DESC1 v24hdr_sdr_desc = desc;\n'
    '\tconst bool v24hdr_base_modified = modified;\n'
    '\tbool v24hdr_attempt = false;\n'
    '\tif (v24hdr_candidate)\n'
    '\t{\n'
    '\t\tif (v24hdr_should_attempt_hdr())\n'
    '\t\t{\n'
    '\t\t\tdesc.Format = DXGI_FORMAT_R10G10B10A2_UNORM;\n'
    '\t\t\tmodified = true;\n'
    '\t\t\tv24hdr_attempt = true;\n'
    '\t\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR SIDECAR HOTFIX5: SWAPCHAIN_CREATE_ARMED R8_TO_R10.");\n'
    '\t\t}\n'
    '\t\telse\n'
    '\t\t{\n'
    '\t\t\tv24hdr_set_hdr_active(false);\n'
    '\t\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR SIDECAR HOTFIX5: SWAPCHAIN_CREATE_SDR_WAITING_FOR_SHADER_ARM.");\n'
    '\t\t}\n'
    '\t}\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'hwnd modified anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)

old = (
    '\tg_in_dxgi_runtime = true;\n'
    '\tconst HRESULT hr = trampoline(pFactory, pDevice, hWnd, &desc, fullscreen_desc.Windowed ? nullptr : &fullscreen_desc, pRestrictToOutput, ppSwapChain);\n'
    '\tg_in_dxgi_runtime = false;\n'
)
new = (
    '\tg_in_dxgi_runtime = true;\n'
    '\tHRESULT hr = trampoline(pFactory, pDevice, hWnd, &desc, fullscreen_desc.Windowed ? nullptr : &fullscreen_desc, pRestrictToOutput, ppSwapChain);\n'
    '\tg_in_dxgi_runtime = false;\n'
    '\tif (v24hdr_attempt && SUCCEEDED(hr) && ppSwapChain != nullptr && *ppSwapChain != nullptr)\n'
    '\t{\n'
    '\t\tif (v24hdr_apply_hdr10_hotfix5(*ppSwapChain, "create"))\n'
    '\t\t{\n'
    '\t\t\tv24hdr_set_hdr_active(true);\n'
    '\t\t}\n'
    '\t\telse\n'
    '\t\t{\n'
    '\t\t\t(*ppSwapChain)->Release();\n'
    '\t\t\t*ppSwapChain = nullptr;\n'
    '\t\t\tdesc = v24hdr_sdr_desc;\n'
    '\t\t\tmodified = v24hdr_base_modified;\n'
    '\t\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX5: SWAPCHAIN_CREATE_HDR10_ROLLBACK_R8.");\n'
    '\t\t\tg_in_dxgi_runtime = true;\n'
    '\t\t\thr = trampoline(pFactory, pDevice, hWnd, &desc, fullscreen_desc.Windowed ? nullptr : &fullscreen_desc, pRestrictToOutput, ppSwapChain);\n'
    '\t\t\tg_in_dxgi_runtime = false;\n'
    '\t\t\tv24hdr_set_hdr_active(false);\n'
    '\t\t\tv24hdr_attempt = false;\n'
    '\t\t}\n'
    '\t}\n'
    '\telse if (v24hdr_attempt && FAILED(hr))\n'
    '\t{\n'
    '\t\tdesc = v24hdr_sdr_desc;\n'
    '\t\tmodified = v24hdr_base_modified;\n'
    '\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX5: SWAPCHAIN_CREATE_R10_FAIL_ROLLBACK_R8 first_hr=0x%08X.", static_cast<unsigned>(hr));\n'
    '\t\tg_in_dxgi_runtime = true;\n'
    '\t\thr = trampoline(pFactory, pDevice, hWnd, &desc, fullscreen_desc.Windowed ? nullptr : &fullscreen_desc, pRestrictToOutput, ppSwapChain);\n'
    '\t\tg_in_dxgi_runtime = false;\n'
    '\t\tv24hdr_set_hdr_active(false);\n'
    '\t\tv24hdr_attempt = false;\n'
    '\t}\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'hwnd native call anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
s = s[:pos] + chunk + s[end:]
write(p, s)

# ======================================================================================
# DXGI ResizeBuffers/ResizeBuffers1: only convert R8->R10 after HDR_READY.
# A failed colorspace set is treated as a failure and rolled all the way back to R8.
# ======================================================================================
p = Path('source/dxgi/dxgi_swapchain.cpp')
s = read(p)
s = once(s, '#include "runtime_manager.hpp"\n', '#include "runtime_manager.hpp"\n#include "v24hdr_dxgi_gate_hotfix5.hpp"\n', 'swap HOTFIX5 include')

# HOTFIX9: keep HOTFIX7's R8 startup/shader-discovery path. After HDR_READY, try a
# controlled proxy ResizeBuffers at the successful Present boundary. If application
# back-buffer references prevent that transition, nudge the real HWND by one pixel so
# Unity performs its own normal window-resize release/ResizeBuffers/reacquire sequence.
transition_helpers = r'''
static volatile LONG g_v24hdr_hotfix9_transition_state = 0;
static HWND g_v24hdr_hotfix9_nudge_hwnd = nullptr;
static UINT g_v24hdr_hotfix9_saved_client_width = 0;
static UINT g_v24hdr_hotfix9_saved_client_height = 0;
static UINT g_v24hdr_hotfix9_wait_presents = 0;

static bool v24hdr_hotfix9_get_hwnd(IDXGISwapChain *swapchain, HWND *out_hwnd)
{
    if (swapchain == nullptr || out_hwnd == nullptr)
        return false;
    *out_hwnd = nullptr;
    IDXGISwapChain1 *sc1 = nullptr;
    if (FAILED(swapchain->QueryInterface(IID_PPV_ARGS(&sc1))) || sc1 == nullptr)
        return false;
    const HRESULT hr = sc1->GetHwnd(out_hwnd);
    sc1->Release();
    return SUCCEEDED(hr) && *out_hwnd != nullptr;
}

static bool v24hdr_hotfix9_post_wm_size(IDXGISwapChain *swapchain, bool second)
{
    HWND hwnd = nullptr;
    if (!v24hdr_hotfix9_get_hwnd(swapchain, &hwnd))
    {
        reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: WINDOW_NUDGE_NO_HWND.");
        return false;
    }

    RECT client = {};
    if (!GetClientRect(hwnd, &client))
    {
        reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: WINDOW_NUDGE_GETCLIENT_FAIL err=%lu.", GetLastError());
        return false;
    }

    const UINT client_w = static_cast<UINT>(client.right > client.left ? client.right - client.left : 0);
    const UINT client_h = static_cast<UINT>(client.bottom > client.top ? client.bottom - client.top : 0);
    if (client_w == 0 || client_h == 0)
    {
        reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: WINDOW_NUDGE_ZERO_CLIENT width=%u height=%u.", client_w, client_h);
        return false;
    }

    if (!second || g_v24hdr_hotfix9_saved_client_width == 0 || g_v24hdr_hotfix9_saved_client_height == 0)
    {
        g_v24hdr_hotfix9_nudge_hwnd = hwnd;
        g_v24hdr_hotfix9_saved_client_width = client_w;
        g_v24hdr_hotfix9_saved_client_height = client_h;
    }

    const UINT base_w = g_v24hdr_hotfix9_saved_client_width;
    const UINT base_h = g_v24hdr_hotfix9_saved_client_height;
    const UINT nudged_w = second ? base_w : (base_w > 4 ? base_w - 1 : base_w + 1);
    const UINT nudged_h = second ? (base_h > 4 ? base_h - 1 : base_h + 1) : base_h;

    SetLastError(0);
    const BOOL queued = PostMessageW(hwnd, WM_SIZE, SIZE_RESTORED, MAKELPARAM(nudged_w, nudged_h));
    const DWORD err = queued ? 0 : GetLastError();
    reshade::log::message(
        queued ? reshade::log::level::info : reshade::log::level::warning,
        second ? "KAIOZEN V24 HDR SIDECAR HOTFIX9: WINDOW_NUDGE_SECOND queued=%u width=%u height=%u err=%lu." :
                 "KAIOZEN V24 HDR SIDECAR HOTFIX9: WINDOW_NUDGE_SENT queued=%u width=%u height=%u err=%lu.",
        queued ? 1u : 0u, nudged_w, nudged_h, err);
    return queued != FALSE;
}

static void v24hdr_hotfix9_restore_window_if_needed()
{
    if (!v24hdr_hdr_active() || InterlockedCompareExchange(&g_v24hdr_hotfix9_transition_state, 2, 4) != 4)
        return;
    if (g_v24hdr_hotfix9_nudge_hwnd == nullptr || g_v24hdr_hotfix9_saved_client_width == 0 || g_v24hdr_hotfix9_saved_client_height == 0)
        return;

    SetLastError(0);
    const BOOL queued = PostMessageW(
        g_v24hdr_hotfix9_nudge_hwnd,
        WM_SIZE,
        SIZE_RESTORED,
        MAKELPARAM(g_v24hdr_hotfix9_saved_client_width, g_v24hdr_hotfix9_saved_client_height));
    const DWORD err = queued ? 0 : GetLastError();
    reshade::log::message(
        queued ? reshade::log::level::info : reshade::log::level::warning,
        "KAIOZEN V24 HDR SIDECAR HOTFIX9: WINDOW_NUDGE_RESTORE queued=%u width=%u height=%u err=%lu.",
        queued ? 1u : 0u, g_v24hdr_hotfix9_saved_client_width, g_v24hdr_hotfix9_saved_client_height, err);
}

static void v24hdr_hotfix9_self_resize_last_resort(DXGISwapChain *proxy, IDXGISwapChain *original, const char *phase)
{
    DXGI_SWAP_CHAIN_DESC desc = {};
    const HRESULT desc_hr = original->GetDesc(&desc);
    if (FAILED(desc_hr))
    {
        reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: PRESENT_DESC_FAIL phase=%s hr=0x%08X.", phase, static_cast<unsigned>(desc_hr));
        InterlockedExchange(&g_v24hdr_hotfix9_transition_state, 5);
        return;
    }

    reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: PRESENT_SELF_RESIZE_ATTEMPT phase=%s width=%u height=%u buffers=%u LAST_RESORT=1.", phase, desc.BufferDesc.Width, desc.BufferDesc.Height, desc.BufferCount);
    const HRESULT resize_hr = proxy->ResizeBuffers(
        desc.BufferCount,
        desc.BufferDesc.Width,
        desc.BufferDesc.Height,
        DXGI_FORMAT_R8G8B8A8_UNORM,
        desc.Flags);

    if (SUCCEEDED(resize_hr) && v24hdr_hdr_active())
    {
        InterlockedExchange(&g_v24hdr_hotfix9_transition_state, 2);
        reshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR SIDECAR HOTFIX9: PRESENT_SELF_RESIZE_SUCCESS phase=%s hr=0x%08X.", phase, static_cast<unsigned>(resize_hr));
        if (g_v24hdr_hotfix9_nudge_hwnd != nullptr && g_v24hdr_hotfix9_saved_client_width != 0 && g_v24hdr_hotfix9_saved_client_height != 0)
            PostMessageW(g_v24hdr_hotfix9_nudge_hwnd, WM_SIZE, SIZE_RESTORED, MAKELPARAM(g_v24hdr_hotfix9_saved_client_width, g_v24hdr_hotfix9_saved_client_height));
        return;
    }

    reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: PRESENT_SELF_RESIZE_NO_HDR phase=%s hr=0x%08X active=%u.", phase, static_cast<unsigned>(resize_hr), v24hdr_hdr_active() ? 1u : 0u);
    InterlockedExchange(&g_v24hdr_hotfix9_transition_state, 5);
    reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: WINDOW_NUDGE_TIMEOUT presents=%u.", g_v24hdr_hotfix9_wait_presents);
}

static void v24hdr_hotfix9_present_transition(DXGISwapChain *proxy, IDXGISwapChain *original, const char *phase)
{
    v24hdr_hotfix9_restore_window_if_needed();

    if (!v24hdr_should_attempt_hdr() || v24hdr_hdr_active())
        return;

    const LONG state = InterlockedCompareExchange(&g_v24hdr_hotfix9_transition_state, 1, 0);
    if (state == 4)
    {
        const UINT wait = ++g_v24hdr_hotfix9_wait_presents;
        if (wait == 120)
            v24hdr_hotfix9_post_wm_size(original, true);
        else if (wait == 300)
            v24hdr_hotfix9_self_resize_last_resort(proxy, original, phase);
        return;
    }
    if (state != 0)
        return;

    reshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR SIDECAR HOTFIX9: PRESENT_TRANSITION_ARMED phase=%s.", phase);

    DXGI_SWAP_CHAIN_DESC desc = {};
    const HRESULT desc_hr = original->GetDesc(&desc);
    if (FAILED(desc_hr))
    {
        reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: PRESENT_DESC_FAIL phase=%s hr=0x%08X.", phase, static_cast<unsigned>(desc_hr));
        InterlockedExchange(&g_v24hdr_hotfix9_transition_state, 0);
        return;
    }

    if (desc.BufferDesc.Format == DXGI_FORMAT_R10G10B10A2_UNORM)
    {
        if (v24hdr_apply_hdr10_hotfix5(original, "present_existing_r10"))
        {
            v24hdr_set_hdr_active(true);
            InterlockedExchange(&g_v24hdr_hotfix9_transition_state, 2);
            reshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR SIDECAR HOTFIX9: PRESENT_EXISTING_R10_HDR10_SUCCESS.");
        }
        else
        {
            InterlockedExchange(&g_v24hdr_hotfix9_transition_state, 5);
            reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: PRESENT_EXISTING_R10_HDR10_FAIL.");
        }
        return;
    }

    if (desc.BufferDesc.Format != DXGI_FORMAT_R8G8B8A8_UNORM)
    {
        InterlockedExchange(&g_v24hdr_hotfix9_transition_state, 5);
        reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: PRESENT_UNEXPECTED_FORMAT format=%d.", static_cast<int>(desc.BufferDesc.Format));
        return;
    }

    g_v24hdr_hotfix9_wait_presents = 0;
    InterlockedExchange(&g_v24hdr_hotfix9_transition_state, 4);
    if (!v24hdr_hotfix9_post_wm_size(original, false))
    {
        reshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX9: WINDOW_NUDGE_TRIGGER_FAIL; trying guarded self-resize fallback.");
        v24hdr_hotfix9_self_resize_last_resort(proxy, original, phase);
    }
}

'''

s = once(
    s,
    '#include "runtime_manager.hpp"\n#include "v24hdr_dxgi_gate_hotfix5.hpp"\n',
    '#include "runtime_manager.hpp"\n#include "v24hdr_dxgi_gate_hotfix5.hpp"\n' + transition_helpers + '\n',
    'swap HOTFIX9 transition helpers',
)

start = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::Present(UINT SyncInterval, UINT Flags)')
end = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::GetBuffer(', start)
if start < 0 or end < 0:
    raise RuntimeError('HOTFIX9 Present boundaries missing')
chunk = s[start:end]
# HOTFIX9A builder compatibility fix: use the same native-Present tail anchor shape
# that HOTFIX8 already proved survives the inherited V24 workflow patches. Do not
# depend on 'return hr' remaining adjacent to on_finish_present().
old = (
    '\tconst HRESULT hr = _orig->Present(SyncInterval, Flags);\n'
    '\tg_in_dxgi_runtime = false;\n'
    '\n'
    '\ton_finish_present(hr);\n'
)
new = (
    '\tconst HRESULT hr = _orig->Present(SyncInterval, Flags);\n'
    '\tg_in_dxgi_runtime = false;\n'
    '\n'
    '\tif (SUCCEEDED(hr) && _direct3d_version == reshade::api::device_api::d3d12)\n'
    '\t\tv24hdr_hotfix9_present_transition(this, _orig, "present");\n'
    '\n'
    '\ton_finish_present(hr);\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'HOTFIX9A Present native-success anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
s = s[:start] + chunk + s[end:]

start = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::Present1(UINT SyncInterval, UINT PresentFlags, const DXGI_PRESENT_PARAMETERS *pPresentParameters)')
end = s.find('BOOL    STDMETHODCALLTYPE DXGISwapChain::IsTemporaryMonoSupported()', start)
if start < 0 or end < 0:
    raise RuntimeError('HOTFIX9 Present1 boundaries missing')
chunk = s[start:end]
old = (
    '\tconst HRESULT hr = static_cast<IDXGISwapChain1 *>(_orig)->Present1(SyncInterval, PresentFlags, pPresentParameters);\n'
    '\tg_in_dxgi_runtime = false;\n'
    '\n'
    '\ton_finish_present(hr);\n'
)
new = (
    '\tconst HRESULT hr = static_cast<IDXGISwapChain1 *>(_orig)->Present1(SyncInterval, PresentFlags, pPresentParameters);\n'
    '\tg_in_dxgi_runtime = false;\n'
    '\n'
    '\tif (SUCCEEDED(hr) && _direct3d_version == reshade::api::device_api::d3d12)\n'
    '\t\tv24hdr_hotfix9_present_transition(this, _orig, "present1");\n'
    '\n'
    '\ton_finish_present(hr);\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'HOTFIX9A Present1 native-success anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
s = s[:start] + chunk + s[end:]

start = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::ResizeBuffers(')
end = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::ResizeTarget(', start)
if start < 0 or end < 0:
    raise RuntimeError('ResizeBuffers boundaries missing')
chunk = s[start:end]
old = (
    '\tg_in_dxgi_runtime = true;\n'
    '\tconst HRESULT hr = _orig->ResizeBuffers(BufferCount, Width, Height, NewFormat, SwapChainFlags);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
)
new = (
    '\tconst DXGI_FORMAT v24hdr_requested_format = NewFormat;\n'
    '\tconst bool v24hdr_candidate = _direct3d_version == reshade::api::device_api::d3d12 && NewFormat == DXGI_FORMAT_R8G8B8A8_UNORM;\n'
    '\tbool v24hdr_attempt = v24hdr_candidate && v24hdr_should_attempt_hdr();\n'
    '\tif (v24hdr_candidate && !v24hdr_attempt)\n'
    '\t{\n'
    '\t\tv24hdr_set_hdr_active(false);\n'
    '\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE_SDR_WAITING_FOR_SHADER_ARM.");\n'
    '\t}\n'
    '\tif (v24hdr_attempt)\n'
    '\t{\n'
    '\t\tNewFormat = DXGI_FORMAT_R10G10B10A2_UNORM;\n'
    '#if RESHADE_ADDON\n'
    '\t\t_is_desc_modified = true;\n'
    '#endif\n'
    '\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE_ARMED R8_TO_R10.");\n'
    '\t}\n'
    '\tg_in_dxgi_runtime = true;\n'
    '\tHRESULT hr = _orig->ResizeBuffers(BufferCount, Width, Height, NewFormat, SwapChainFlags);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '\tif (v24hdr_attempt && SUCCEEDED(hr))\n'
    '\t{\n'
    '\t\tif (v24hdr_apply_hdr10_hotfix5(_orig, "resize"))\n'
    '\t\t\tv24hdr_set_hdr_active(true);\n'
    '\t\telse\n'
    '\t\t{\n'
    '\t\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE_HDR10_ROLLBACK_R8.");\n'
    '\t\t\tg_in_dxgi_runtime = true;\n'
    '\t\t\thr = _orig->ResizeBuffers(BufferCount, Width, Height, v24hdr_requested_format, SwapChainFlags);\n'
    '\t\t\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '#if RESHADE_ADDON\n'
    '\t\t\tif (SUCCEEDED(hr)) _is_desc_modified = false;\n'
    '#endif\n'
    '\t\t\tv24hdr_set_hdr_active(false);\n'
    '\t\t\tv24hdr_attempt = false;\n'
    '\t\t}\n'
    '\t}\n'
    '\telse if (v24hdr_attempt && FAILED(hr))\n'
    '\t{\n'
    '\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE_R10_FAIL_ROLLBACK_R8 first_hr=0x%08X.", static_cast<unsigned>(hr));\n'
    '\t\tg_in_dxgi_runtime = true;\n'
    '\t\thr = _orig->ResizeBuffers(BufferCount, Width, Height, v24hdr_requested_format, SwapChainFlags);\n'
    '\t\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '#if RESHADE_ADDON\n'
    '\t\tif (SUCCEEDED(hr)) _is_desc_modified = false;\n'
    '#endif\n'
    '\t\tv24hdr_set_hdr_active(false);\n'
    '\t\tv24hdr_attempt = false;\n'
    '\t}\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'ResizeBuffers native call anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
s = s[:start] + chunk + s[end:]

start = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::ResizeBuffers1(')
end = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::SetHDRMetaData(', start)
if start < 0 or end < 0:
    raise RuntimeError('ResizeBuffers1 boundaries missing')
chunk = s[start:end]
old = (
    '\tg_in_dxgi_runtime = true;\n'
    '\tconst HRESULT hr = static_cast<IDXGISwapChain3 *>(_orig)->ResizeBuffers1(BufferCount, Width, Height, NewFormat, SwapChainFlags, pCreationNodeMask, present_queues.p);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
)
new = (
    '\tconst DXGI_FORMAT v24hdr_requested_format = NewFormat;\n'
    '\tconst bool v24hdr_candidate = _direct3d_version == reshade::api::device_api::d3d12 && NewFormat == DXGI_FORMAT_R8G8B8A8_UNORM;\n'
    '\tbool v24hdr_attempt = v24hdr_candidate && v24hdr_should_attempt_hdr();\n'
    '\tif (v24hdr_candidate && !v24hdr_attempt)\n'
    '\t{\n'
    '\t\tv24hdr_set_hdr_active(false);\n'
    '\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE1_SDR_WAITING_FOR_SHADER_ARM.");\n'
    '\t}\n'
    '\tif (v24hdr_attempt)\n'
    '\t{\n'
    '\t\tNewFormat = DXGI_FORMAT_R10G10B10A2_UNORM;\n'
    '#if RESHADE_ADDON\n'
    '\t\t_is_desc_modified = true;\n'
    '#endif\n'
    '\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE1_ARMED R8_TO_R10.");\n'
    '\t}\n'
    '\tg_in_dxgi_runtime = true;\n'
    '\tHRESULT hr = static_cast<IDXGISwapChain3 *>(_orig)->ResizeBuffers1(BufferCount, Width, Height, NewFormat, SwapChainFlags, pCreationNodeMask, present_queues.p);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '\tif (v24hdr_attempt && SUCCEEDED(hr))\n'
    '\t{\n'
    '\t\tif (v24hdr_apply_hdr10_hotfix5(_orig, "resize1"))\n'
    '\t\t\tv24hdr_set_hdr_active(true);\n'
    '\t\telse\n'
    '\t\t{\n'
    '\t\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE1_HDR10_ROLLBACK_R8.");\n'
    '\t\t\tg_in_dxgi_runtime = true;\n'
    '\t\t\thr = static_cast<IDXGISwapChain3 *>(_orig)->ResizeBuffers1(BufferCount, Width, Height, v24hdr_requested_format, SwapChainFlags, pCreationNodeMask, present_queues.p);\n'
    '\t\t\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '#if RESHADE_ADDON\n'
    '\t\t\tif (SUCCEEDED(hr)) _is_desc_modified = false;\n'
    '#endif\n'
    '\t\t\tv24hdr_set_hdr_active(false);\n'
    '\t\t\tv24hdr_attempt = false;\n'
    '\t\t}\n'
    '\t}\n'
    '\telse if (v24hdr_attempt && FAILED(hr))\n'
    '\t{\n'
    '\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE1_R10_FAIL_ROLLBACK_R8 first_hr=0x%08X.", static_cast<unsigned>(hr));\n'
    '\t\tg_in_dxgi_runtime = true;\n'
    '\t\thr = static_cast<IDXGISwapChain3 *>(_orig)->ResizeBuffers1(BufferCount, Width, Height, v24hdr_requested_format, SwapChainFlags, pCreationNodeMask, present_queues.p);\n'
    '\t\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '#if RESHADE_ADDON\n'
    '\t\tif (SUCCEEDED(hr)) _is_desc_modified = false;\n'
    '#endif\n'
    '\t\tv24hdr_set_hdr_active(false);\n'
    '\t\tv24hdr_attempt = false;\n'
    '\t}\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'ResizeBuffers1 native call anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
s = s[:start] + chunk + s[end:]
write(p, s)

Path('v24hdr-patch-report.txt').write_text(
    '''KAIOZEN_V24_NATIVE_HDR_STREAM_SIDECAR_HOTFIX5_PATCH=PASS
GAME_VISIBLE_D3D12_DEVICE=NATIVE
GAME_VISIBLE_D3D12_PSO=ORIGINAL_NATIVE
RENODX_ADDON=ABSENT
RENODX_SHADER_CONSTANT_BUFFER=BAKED
CRC_IMPLEMENTATION=PINNED_RENODX_EXACT_HEADER
ADAPTIVE_V31_MATCHER=STRICT_SIGNATURE_PLUS_EXACT_OSPRODWIN3_1_0_PINNED_MAP_NATIVE_PSO_ORACLE
HOTFIX11_UBERPOST_MAP=SEMANTIC_DXBC_SIGNATURE_FINGERPRINT
HOTFIX11_FUSED_SHADER_MANIFEST_BYTES=13928
CREATE_GRAPHICS_PSO=ORIGINAL_FIRST_PLUS_PRIVATE_NATIVE_SIDECAR
CREATE_PIPELINE_STATE_STREAM=HOOKED_SLOT47_ORIGINAL_FIRST_PLUS_PRIVATE_NATIVE_SIDECAR
PIPELINE_LIBRARY=LOAD_GRAPHICS_AND_LOAD_STREAM_COVERED_NATIVE
CREATE_COMMAND_LIST=HOOKED_SLOT12_ORIGINAL_FIRST_THEN_SIDECAR_BIND
CREATE_COMMAND_LIST1=HOOKED_SLOT51
COMMAND_LIST_RESET=HOOKED_SLOT10_ORIGINAL_FIRST_THEN_SIDECAR_BIND
COMMAND_LIST_SET_PIPELINE_STATE=HOOKED_SLOT25
SIDECAR_BINDING=ONLY_WHEN_HDR_ACTIVE
CRITICAL_UBERPOST_ARM_GATE=ENABLED
ZERO_SIDECARS_FORCE_HDR=IMPOSSIBLE_BY_DESIGN
SWAPCHAIN_CREATE_BEFORE_ARM=COHERENT_R8_SDR
RESIZE_BEFORE_ARM=COHERENT_R8_SDR
HOTFIX9_PRESENT_TRANSITION=R8_ARMED_ASYNC_WM_SIZE_THEN_GUARDED_SELF_RESIZE
HOTFIX9_PRIMARY_TRANSITION=ASYNC_WM_SIZE_APPLICATION_OWNS_RESIZE
HOTFIX9_WINDOW_RESIZE_TRIGGER=ONE_PIXEL_CLIENT_WM_SIZE_POSTMESSAGE
HOTFIX9_WINDOW_RESTORE=POST_ORIGINAL_CLIENT_WM_SIZE_AFTER_HDR_ACTIVE
MANUAL_RESIZE_REQUIRED=NO
R10_CREATE_FAILURE=ROLLBACK_R8
HDR10_COLORSPACE_FAILURE=ROLLBACK_R8
R10_RESIZE_FAILURE=ROLLBACK_R8
SENTINEL_FAILSAFE=ENABLED
''',
    encoding='utf-8',
    newline='\n',
)
print(Path('v24hdr-patch-report.txt').read_text())
