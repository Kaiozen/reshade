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
# - HOTFIX15: HDR swapchain conversion is armed from the first safe native swapchain create/resize;
#   critical RenoDX sidecars can appear later without requiring a visible SDR->HDR transition.
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
// HOTFIX15: RenoDX-style logical pipeline tracking + draw-time replacement.
// The game can bind a PSO before HDR becomes active; official RenoDX reapplies
// a cloned replacement immediately before draw. Track the logical native PSO
// independently from the private sidecar physically bound to the command list.
static std::atomic<uint64_t> g_v24hdr_hotfix14_set_pso_calls{0};
static std::atomic<uint64_t> g_v24hdr_hotfix14_clearstate_calls{0};
static std::atomic<uint64_t> g_v24hdr_hotfix14_draw_time_substitutions{0};
static std::atomic<uint64_t> g_v24hdr_hotfix14_replacement_draws{0};
static std::atomic<uint64_t> g_v24hdr_hotfix14_critical_uberpost_draws{0};
static std::atomic<uint64_t> g_v24hdr_hotfix14_indirect_substitutions{0};
static std::atomic<uint64_t> g_v24hdr_pipeline_library_creates{0};
static std::atomic<uint64_t> g_v24hdr_pipeline_library_load_graphics{0};
static std::atomic<uint64_t> g_v24hdr_pipeline_library_load_stream{0};
static std::atomic<uint64_t> g_v24hdr_stream_parse_skips{0};
static std::atomic<uint64_t> g_v24hdr_adaptive_matches{0};
static std::atomic<uint64_t> g_v24hdr_adaptive_probes{0};
static std::atomic<uint64_t> g_v24hdr_adaptive_ambiguous{0};

static std::mutex g_v24hdr_sidecar_mutex;
static std::unordered_map<ID3D12PipelineState *, ID3D12PipelineState *> g_v24hdr_sidecars;
static std::unordered_map<ID3D12PipelineState *, uint32_t> g_v24hdr_sidecar_crcs;
static std::mutex g_v24hdr_hotfix14_command_state_mutex;
static std::unordered_map<ID3D12GraphicsCommandList *, ID3D12PipelineState *> g_v24hdr_hotfix14_logical_psos;
static std::unordered_set<uint32_t> g_v24hdr_critical_crc_set;
static std::unordered_set<uint32_t> g_v24hdr_observed_crc_set;
static std::unordered_set<void **> g_v24hdr_command_vtables;
static std::unordered_set<void **> g_v24hdr_library_vtables;


// HOTFIX13: native FP16 swapchain-backbuffer clone layer.
// Game-visible resources stay the original native DXGI backbuffers. Game-created
// RTV/SRV descriptors that target a registered backbuffer are redirected to its
// private FP16 clone, and native ResourceBarrier calls are mirrored to that clone.
// The real R10 backbuffer is touched only by the final RenoDX SwapChainPass.
struct v24hdr_hotfix13_clone_entry
{
    ID3D12Resource *original = nullptr;
    ID3D12Resource *clone = nullptr;
    D3D12_RESOURCE_STATES state = D3D12_RESOURCE_STATE_COMMON;
};
static std::recursive_mutex g_v24hdr_hotfix13_clone_mutex;
static std::unordered_map<ID3D12Resource *, v24hdr_hotfix13_clone_entry> g_v24hdr_hotfix13_clones;
static thread_local bool g_v24hdr_hotfix13_clone_bypass = false;
static std::atomic<uint64_t> g_v24hdr_hotfix13_clone_registers{0};
static std::atomic<uint64_t> g_v24hdr_hotfix13_rtv_redirects{0};
static std::atomic<uint64_t> g_v24hdr_hotfix13_srv_redirects{0};
static std::atomic<uint64_t> g_v24hdr_hotfix13_barrier_mirrors{0};

void v24hdr_hotfix13_set_clone_bypass(bool bypass)
{
    g_v24hdr_hotfix13_clone_bypass = bypass;
}

void v24hdr_hotfix13_clear_swapchain_clones()
{
    std::lock_guard<std::recursive_mutex> lock(g_v24hdr_hotfix13_clone_mutex);
    const size_t count = g_v24hdr_hotfix13_clones.size();
    for (auto &pair : g_v24hdr_hotfix13_clones)
    {
        if (pair.second.clone != nullptr) pair.second.clone->Release();
        if (pair.second.original != nullptr) pair.second.original->Release();
    }
    g_v24hdr_hotfix13_clones.clear();
    if (count != 0)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR OUTPUT HOTFIX13: BACKBUFFER_CLONE_MAP_CLEAR count=%llu.",
            static_cast<unsigned long long>(count));
}

bool v24hdr_hotfix13_register_swapchain_clone(ID3D12Resource *original, ID3D12Resource *clone)
{
    if (original == nullptr || clone == nullptr)
        return false;
    const D3D12_RESOURCE_DESC od = original->GetDesc();
    const D3D12_RESOURCE_DESC cd = clone->GetDesc();
    if (od.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE2D || cd.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE2D ||
        od.Format != DXGI_FORMAT_R10G10B10A2_UNORM || cd.Format != DXGI_FORMAT_R16G16B16A16_FLOAT ||
        od.Width != cd.Width || od.Height != cd.Height || od.SampleDesc.Count != 1 || cd.SampleDesc.Count != 1)
        return false;
    std::lock_guard<std::recursive_mutex> lock(g_v24hdr_hotfix13_clone_mutex);
    auto it = g_v24hdr_hotfix13_clones.find(original);
    if (it != g_v24hdr_hotfix13_clones.end())
    {
        if (it->second.clone != nullptr) it->second.clone->Release();
        if (it->second.original != nullptr) it->second.original->Release();
        g_v24hdr_hotfix13_clones.erase(it);
    }
    original->AddRef();
    clone->AddRef();
    g_v24hdr_hotfix13_clones.emplace(original, v24hdr_hotfix13_clone_entry{original, clone, D3D12_RESOURCE_STATE_COMMON});
    const uint64_t n = ++g_v24hdr_hotfix13_clone_registers;
    reshade::log::message(reshade::log::level::info,
        "KAIOZEN V24 HDR OUTPUT HOTFIX13: BACKBUFFER_CLONE_REGISTER count=%llu original=%p clone=%p original_format=%d clone_format=%d width=%llu height=%u.",
        static_cast<unsigned long long>(n), original, clone, static_cast<int>(od.Format), static_cast<int>(cd.Format),
        static_cast<unsigned long long>(od.Width), od.Height);
    return true;
}

static ID3D12Resource *v24hdr_hotfix13_acquire_clone(ID3D12Resource *original)
{
    if (original == nullptr || g_v24hdr_hotfix13_clone_bypass)
        return nullptr;
    std::lock_guard<std::recursive_mutex> lock(g_v24hdr_hotfix13_clone_mutex);
    const auto it = g_v24hdr_hotfix13_clones.find(original);
    if (it == g_v24hdr_hotfix13_clones.end() || it->second.clone == nullptr)
        return nullptr;
    it->second.clone->AddRef();
    return it->second.clone;
}

bool v24hdr_hotfix13_clone_is_present(ID3D12Resource *original)
{
    std::lock_guard<std::recursive_mutex> lock(g_v24hdr_hotfix13_clone_mutex);
    const auto it = g_v24hdr_hotfix13_clones.find(original);
    return it != g_v24hdr_hotfix13_clones.end() && it->second.clone != nullptr &&
        it->second.state == D3D12_RESOURCE_STATE_PRESENT;
}

static void v24hdr_hotfix13_update_clone_state(ID3D12Resource *original, D3D12_RESOURCE_STATES state)
{
    std::lock_guard<std::recursive_mutex> lock(g_v24hdr_hotfix13_clone_mutex);
    const auto it = g_v24hdr_hotfix13_clones.find(original);
    if (it != g_v24hdr_hotfix13_clones.end())
        it->second.state = state;
}

// Cross-translation-unit HDR gate used by DXGI. HOTFIX15 allows startup HDR.
bool v24hdr_should_attempt_hdr()
{
    // HOTFIX15: startup HDR. If the native D3D12 path is eligible, arm HDR from the
    // first safe swapchain create/resize attempt. Full RenoDX shader replacement still
    // becomes active as sidecars appear later, but the output container can be HDR10
    // immediately if the final proxy and colorspace setup succeed.
    return v24hdr_enabled();
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

static uint32_t v24hdr_find_sidecar_crc(ID3D12PipelineState *original)
{
    if (original == nullptr)
        return 0;
    std::lock_guard<std::mutex> lock(g_v24hdr_sidecar_mutex);
    const auto it = g_v24hdr_sidecar_crcs.find(original);
    return it == g_v24hdr_sidecar_crcs.end() ? 0u : it->second;
}

static void v24hdr_hotfix14_track_logical_pso(
    ID3D12GraphicsCommandList *list, ID3D12PipelineState *pipeline)
{
    if (list == nullptr)
        return;
    std::lock_guard<std::mutex> lock(g_v24hdr_hotfix14_command_state_mutex);
    g_v24hdr_hotfix14_logical_psos[list] = pipeline;
}

static ID3D12PipelineState *v24hdr_hotfix14_logical_pso(ID3D12GraphicsCommandList *list)
{
    if (list == nullptr)
        return nullptr;
    std::lock_guard<std::mutex> lock(g_v24hdr_hotfix14_command_state_mutex);
    const auto it = g_v24hdr_hotfix14_logical_psos.find(list);
    return it == g_v24hdr_hotfix14_logical_psos.end() ? nullptr : it->second;
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
            g_v24hdr_sidecar_crcs.emplace(original, crc);
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
    // critical sidecar may appear later; HOTFIX15 startup HDR no longer waits on HDR_READY.
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
static void STDMETHODCALLTYPE v24hdr_CreateShaderResourceView(
    ID3D12Device *, ID3D12Resource *, const D3D12_SHADER_RESOURCE_VIEW_DESC *, D3D12_CPU_DESCRIPTOR_HANDLE);
static void STDMETHODCALLTYPE v24hdr_CreateRenderTargetView(
    ID3D12Device *, ID3D12Resource *, const D3D12_RENDER_TARGET_VIEW_DESC *, D3D12_CPU_DESCRIPTOR_HANDLE);
static void STDMETHODCALLTYPE v24hdr_ResourceBarrier(
    ID3D12GraphicsCommandList *, UINT, const D3D12_RESOURCE_BARRIER *);

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

    if (crc == 0x06D90AA2u)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR OUTPUT HOTFIX13: UBERPOST_RTV count=%u format0=%d sample_count=%u.",
            desc->NumRenderTargets, desc->NumRenderTargets != 0 ? static_cast<int>(desc->RTVFormats[0]) : -1, desc->SampleDesc.Count);

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

static void STDMETHODCALLTYPE v24hdr_CreateShaderResourceView(
    ID3D12Device *device,
    ID3D12Resource *resource,
    const D3D12_SHADER_RESOURCE_VIEW_DESC *desc,
    D3D12_CPU_DESCRIPTOR_HANDLE destination)
{
    auto trampoline = reshade::hooks::call(v24hdr_CreateShaderResourceView, reshade::hooks::vtable_from_instance(device) + 18);
    ID3D12Resource *clone = v24hdr_hotfix13_acquire_clone(resource);
    if (clone == nullptr)
    {
        trampoline(device, resource, desc, destination);
        return;
    }
    D3D12_SHADER_RESOURCE_VIEW_DESC local = {};
    const D3D12_SHADER_RESOURCE_VIEW_DESC *selected = desc;
    if (desc != nullptr)
    {
        local = *desc;
        local.Format = DXGI_FORMAT_R16G16B16A16_FLOAT;
        selected = &local;
    }
    trampoline(device, clone, selected, destination);
    const uint64_t n = ++g_v24hdr_hotfix13_srv_redirects;
    if (n <= 64 || (n % 256u) == 0)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR OUTPUT HOTFIX13: BACKBUFFER_SRV_REDIRECT count=%llu original=%p clone=%p.",
            static_cast<unsigned long long>(n), resource, clone);
    clone->Release();
}

static void STDMETHODCALLTYPE v24hdr_CreateRenderTargetView(
    ID3D12Device *device,
    ID3D12Resource *resource,
    const D3D12_RENDER_TARGET_VIEW_DESC *desc,
    D3D12_CPU_DESCRIPTOR_HANDLE destination)
{
    auto trampoline = reshade::hooks::call(v24hdr_CreateRenderTargetView, reshade::hooks::vtable_from_instance(device) + 20);
    ID3D12Resource *clone = v24hdr_hotfix13_acquire_clone(resource);
    if (clone == nullptr)
    {
        trampoline(device, resource, desc, destination);
        return;
    }
    D3D12_RENDER_TARGET_VIEW_DESC local = {};
    const D3D12_RENDER_TARGET_VIEW_DESC *selected = desc;
    if (desc != nullptr)
    {
        local = *desc;
        local.Format = DXGI_FORMAT_R16G16B16A16_FLOAT;
        selected = &local;
    }
    trampoline(device, clone, selected, destination);
    const uint64_t n = ++g_v24hdr_hotfix13_rtv_redirects;
    if (n <= 64 || (n % 256u) == 0)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR OUTPUT HOTFIX13: BACKBUFFER_RTV_REDIRECT count=%llu original=%p clone=%p.",
            static_cast<unsigned long long>(n), resource, clone);
    clone->Release();
}

static void STDMETHODCALLTYPE v24hdr_ResourceBarrier(
    ID3D12GraphicsCommandList *list,
    UINT count,
    const D3D12_RESOURCE_BARRIER *barriers)
{
    auto trampoline = reshade::hooks::call(v24hdr_ResourceBarrier, reshade::hooks::vtable_from_instance(list) + 26);
    if (barriers == nullptr || count == 0 || g_v24hdr_hotfix13_clone_bypass)
    {
        trampoline(list, count, barriers);
        return;
    }
    std::vector<D3D12_RESOURCE_BARRIER> mirrors;
    std::vector<ID3D12Resource *> acquired;
    struct state_update { ID3D12Resource *original; D3D12_RESOURCE_STATES state; };
    std::vector<state_update> updates;
    mirrors.reserve(count);
    acquired.reserve(count * 2u);
    updates.reserve(count);
    for (UINT i = 0; i < count; ++i)
    {
        D3D12_RESOURCE_BARRIER b = barriers[i];
        bool changed = false;
        if (b.Type == D3D12_RESOURCE_BARRIER_TYPE_TRANSITION && b.Transition.pResource != nullptr)
        {
            ID3D12Resource *original = b.Transition.pResource;
            if (ID3D12Resource *clone = v24hdr_hotfix13_acquire_clone(original))
            {
                b.Transition.pResource = clone;
                acquired.push_back(clone);
                updates.push_back({original, b.Transition.StateAfter});
                changed = true;
            }
        }
        else if (b.Type == D3D12_RESOURCE_BARRIER_TYPE_UAV && b.UAV.pResource != nullptr)
        {
            if (ID3D12Resource *clone = v24hdr_hotfix13_acquire_clone(b.UAV.pResource))
            {
                b.UAV.pResource = clone;
                acquired.push_back(clone);
                changed = true;
            }
        }
        if (changed)
            mirrors.push_back(b);
    }
    // Keep Unity/D3DMetal's native swapchain state stream intact, then mirror it to
    // the FP16 rendering clone. This avoids touching resource lifetime or queue fences.
    trampoline(list, count, barriers);
    if (!mirrors.empty())
    {
        trampoline(list, static_cast<UINT>(mirrors.size()), mirrors.data());
        const uint64_t total = g_v24hdr_hotfix13_barrier_mirrors.fetch_add(mirrors.size()) + mirrors.size();
        if (total <= 128 || (total % 512u) == 0)
            reshade::log::message(reshade::log::level::info,
                "KAIOZEN V24 HDR OUTPUT HOTFIX13: BACKBUFFER_BARRIER_MIRROR total=%llu batch=%u.",
                static_cast<unsigned long long>(total), static_cast<unsigned>(mirrors.size()));
    }
    for (const auto &u : updates)
        v24hdr_hotfix13_update_clone_state(u.original, u.state);
    for (ID3D12Resource *r : acquired)
        if (r != nullptr) r->Release();
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
    if (SUCCEEDED(hr))
        v24hdr_hotfix14_track_logical_pso(list, initial);
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

    // Always track the game-requested/native logical PSO, even while SDR. This is
    // the crucial RenoDX parity fix: a sidecar may be created and HDR may activate
    // *after* the game last called SetPipelineState.
    v24hdr_hotfix14_track_logical_pso(list, pipeline);
    const uint64_t set_calls = ++g_v24hdr_hotfix14_set_pso_calls;
    if (set_calls <= 32 || (set_calls % 4096u) == 0)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX14: PSO_TRACK source=SetPipelineState total=%llu logical=%p hdr=%u.",
            static_cast<unsigned long long>(set_calls), pipeline, v24hdr_hdr_active() ? 1u : 0u);

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

static void STDMETHODCALLTYPE v24hdr_ClearState(
    ID3D12GraphicsCommandList *list,
    ID3D12PipelineState *pipeline)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_ClearState,
        reshade::hooks::vtable_from_instance(list) + 11);

    // Preserve native ClearState semantics first, then mirror RenoDX's replacement
    // behavior if HDR is active. Logical state always remains the game's original PSO.
    trampoline(list, pipeline);
    v24hdr_hotfix14_track_logical_pso(list, pipeline);
    const uint64_t calls = ++g_v24hdr_hotfix14_clearstate_calls;

    if (v24hdr_hdr_active() && pipeline != nullptr)
    {
        if (ID3D12PipelineState *sidecar = v24hdr_find_sidecar(pipeline))
        {
            auto set_trampoline = reshade::hooks::call(
                v24hdr_SetPipelineState,
                reshade::hooks::vtable_from_instance(list) + 25);
            set_trampoline(list, sidecar);
            const uint32_t crc = v24hdr_find_sidecar_crc(pipeline);
            reshade::log::message(reshade::log::level::info,
                "KAIOZEN V24 HDR SIDECAR HOTFIX14: CLEARSTATE_PSO_SUBSTITUTE total=%llu original=%p sidecar=%p crc=0x%08X.",
                static_cast<unsigned long long>(calls), pipeline, sidecar, crc);
        }
    }
}

static bool v24hdr_hotfix14_apply_draw_replacement(
    ID3D12GraphicsCommandList *list,
    const char *source,
    uint32_t &crc_out)
{
    crc_out = 0;
    if (!v24hdr_hdr_active() || list == nullptr)
        return false;

    ID3D12PipelineState *logical = v24hdr_hotfix14_logical_pso(list);
    if (logical == nullptr)
        return false;
    ID3D12PipelineState *sidecar = v24hdr_find_sidecar(logical);
    if (sidecar == nullptr)
        return false;

    // Bind via the native slot-25 trampoline so this physical bind does not replace
    // the logical game PSO we track above. This mirrors RenoDX ApplyReplacement at draw time.
    auto set_trampoline = reshade::hooks::call(
        v24hdr_SetPipelineState,
        reshade::hooks::vtable_from_instance(list) + 25);
    set_trampoline(list, sidecar);

    crc_out = v24hdr_find_sidecar_crc(logical);
    const uint64_t total = ++g_v24hdr_hotfix14_draw_time_substitutions;
    if (total <= 256 || (total % 1024u) == 0)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX14: DRAW_TIME_PSO_SUBSTITUTE source=%s total=%llu logical=%p sidecar=%p crc=0x%08X critical=%u.",
            source,
            static_cast<unsigned long long>(total),
            logical,
            sidecar,
            crc_out,
            v24hdr_is_critical_uberpost_crc(crc_out) ? 1u : 0u);
    return true;
}

static void v24hdr_hotfix14_note_replacement_draw(const char *source, uint32_t crc)
{
    const uint64_t total = ++g_v24hdr_hotfix14_replacement_draws;
    if (total <= 256 || (total % 1024u) == 0)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX14: DRAW_REPLACEMENT_EXECUTED source=%s total=%llu crc=0x%08X critical=%u.",
            source,
            static_cast<unsigned long long>(total),
            crc,
            v24hdr_is_critical_uberpost_crc(crc) ? 1u : 0u);

    if (v24hdr_is_critical_uberpost_crc(crc))
    {
        const uint64_t critical = ++g_v24hdr_hotfix14_critical_uberpost_draws;
        if (critical <= 256 || (critical % 1024u) == 0)
            reshade::log::message(reshade::log::level::info,
                "KAIOZEN V24 HDR SIDECAR HOTFIX14: CRITICAL_UBERPOST_DRAW_EXECUTED total=%llu crc=0x%08X.",
                static_cast<unsigned long long>(critical), crc);
    }
}

static void STDMETHODCALLTYPE v24hdr_DrawInstanced(
    ID3D12GraphicsCommandList *list,
    UINT vertex_count,
    UINT instance_count,
    UINT start_vertex,
    UINT start_instance)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_DrawInstanced,
        reshade::hooks::vtable_from_instance(list) + 12);
    uint32_t crc = 0;
    const bool replaced = v24hdr_hotfix14_apply_draw_replacement(list, "DrawInstanced", crc);
    trampoline(list, vertex_count, instance_count, start_vertex, start_instance);
    if (replaced)
        v24hdr_hotfix14_note_replacement_draw("DrawInstanced", crc);
}

static void STDMETHODCALLTYPE v24hdr_DrawIndexedInstanced(
    ID3D12GraphicsCommandList *list,
    UINT index_count,
    UINT instance_count,
    UINT start_index,
    INT base_vertex,
    UINT start_instance)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_DrawIndexedInstanced,
        reshade::hooks::vtable_from_instance(list) + 13);
    uint32_t crc = 0;
    const bool replaced = v24hdr_hotfix14_apply_draw_replacement(list, "DrawIndexedInstanced", crc);
    trampoline(list, index_count, instance_count, start_index, base_vertex, start_instance);
    if (replaced)
        v24hdr_hotfix14_note_replacement_draw("DrawIndexedInstanced", crc);
}

static void STDMETHODCALLTYPE v24hdr_ExecuteIndirect(
    ID3D12GraphicsCommandList *list,
    ID3D12CommandSignature *command_signature,
    UINT max_command_count,
    ID3D12Resource *argument_buffer,
    UINT64 argument_buffer_offset,
    ID3D12Resource *count_buffer,
    UINT64 count_buffer_offset)
{
    auto trampoline = reshade::hooks::call(
        v24hdr_ExecuteIndirect,
        reshade::hooks::vtable_from_instance(list) + 59);
    uint32_t crc = 0;
    const bool replaced = v24hdr_hotfix14_apply_draw_replacement(list, "ExecuteIndirect", crc);
    if (replaced)
        ++g_v24hdr_hotfix14_indirect_substitutions;
    trampoline(list, command_signature, max_command_count, argument_buffer, argument_buffer_offset, count_buffer, count_buffer_offset);
    if (replaced)
        v24hdr_hotfix14_note_replacement_draw("ExecuteIndirect", crc);
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
        const bool clearstate = reshade::hooks::install(
            "ID3D12GraphicsCommandList::ClearState [V24HDR14]", vtable, 11, &v24hdr_ClearState);
        const bool draw = reshade::hooks::install(
            "ID3D12GraphicsCommandList::DrawInstanced [V24HDR14]", vtable, 12, &v24hdr_DrawInstanced);
        const bool draw_indexed = reshade::hooks::install(
            "ID3D12GraphicsCommandList::DrawIndexedInstanced [V24HDR14]", vtable, 13, &v24hdr_DrawIndexedInstanced);
        const bool setpso = reshade::hooks::install(
            "ID3D12GraphicsCommandList::SetPipelineState [V24HDR5]", vtable, 25, &v24hdr_SetPipelineState);
        const bool barriers = reshade::hooks::install(
            "ID3D12GraphicsCommandList::ResourceBarrier [V24HDR13]", vtable, 26, &v24hdr_ResourceBarrier);
        const bool indirect = reshade::hooks::install(
            "ID3D12GraphicsCommandList::ExecuteIndirect [V24HDR14]", vtable, 59, &v24hdr_ExecuteIndirect);
        if (reset || clearstate || draw || draw_indexed || setpso || barriers || indirect)
            ++g_v24hdr_command_list_hooks;
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR SIDECAR HOTFIX14: COMMAND_LIST_HOOK reset=%u clear=%u draw=%u draw_indexed=%u set_pso=%u barriers=%u indirect=%u vtable=%p total=%llu.",
            reset ? 1u : 0u, clearstate ? 1u : 0u, draw ? 1u : 0u, draw_indexed ? 1u : 0u,
            setpso ? 1u : 0u, barriers ? 1u : 0u, indirect ? 1u : 0u, vtable,
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
        ID3D12GraphicsCommandList *list = nullptr;
        if (SUCCEEDED(reinterpret_cast<IUnknown *>(*ppCommandList)->QueryInterface(IID_PPV_ARGS(&list))) && list != nullptr)
        {
            v24hdr_hotfix14_track_logical_pso(list, initial);
            if (v24hdr_hdr_active() && initial != nullptr)
            {
                if (ID3D12PipelineState *sidecar = v24hdr_find_sidecar(initial))
                {
                    auto set_trampoline = reshade::hooks::call(
                        v24hdr_SetPipelineState,
                        reshade::hooks::vtable_from_instance(list) + 25);
                    set_trampoline(list, sidecar);
                    ++g_v24hdr_initial_pso_substitutions;
                }
            }
            list->Release();
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
    {
        v24hdr_install_command_list_hooks(reinterpret_cast<IUnknown *>(*ppCommandList));
        ID3D12GraphicsCommandList *list = nullptr;
        if (SUCCEEDED(reinterpret_cast<IUnknown *>(*ppCommandList)->QueryInterface(IID_PPV_ARGS(&list))) && list != nullptr)
        {
            v24hdr_hotfix14_track_logical_pso(list, nullptr);
            list->Release();
        }
    }
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
    const bool srv = reshade::hooks::install(
        "ID3D12Device::CreateShaderResourceView [V24HDR13]", base_vtable, 18, &v24hdr_CreateShaderResourceView);
    const bool rtv = reshade::hooks::install(
        "ID3D12Device::CreateRenderTargetView [V24HDR13]", base_vtable, 20, &v24hdr_CreateRenderTargetView);

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
        "KAIOZEN V24 HDR SIDECAR HOTFIX14: ACTIVE shader_count=%llu native_identity=1 addon_runtime=0 sidecar_psos=1 draw_time_parity=1 arm_before_hdr=1 fp16_backbuffer_clones=1 graphics_hook=%u stream_hook=%u library_hook=%u command_list_hook=%u command_list1_hook=%u srv_hook=%u rtv_hook=%u.",
        static_cast<unsigned long long>(g_v24hdr_shader_count),
        graphics ? 1u : 0u,
        stream ? 1u : 0u,
        pipeline_library ? 1u : 0u,
        command_list ? 1u : 0u,
        command_list1 ? 1u : 0u,
        srv ? 1u : 0u,
        rtv ? 1u : 0u);
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
extern bool v24hdr_hotfix13_prepare_final_proxy(IDXGISwapChain *swapchain, const char *phase);
extern bool v24hdr_hotfix13_register_swapchain_clone(ID3D12Resource *original, ID3D12Resource *clone);
extern void v24hdr_hotfix13_clear_swapchain_clones();
extern void v24hdr_hotfix13_set_clone_bypass(bool bypass);
extern bool v24hdr_hotfix13_clone_is_present(ID3D12Resource *original);
extern void v24hdr_hotfix13_reset_final_proxy();

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
    '\t\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR STARTUP HOTFIX15: STARTUP_HDR_ATTEMPT phase=create.");\n'
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
    '\t\tif (v24hdr_hotfix13_prepare_final_proxy(*ppSwapChain, "create") && v24hdr_apply_hdr10_hotfix5(*ppSwapChain, "create"))\n'
    '\t\t{\n'
    '\t\t\tv24hdr_set_hdr_active(true);\n'
    '\t\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 HDR STARTUP HOTFIX15: STARTUP_HDR_ACTIVE phase=create.");\n'
    '\t\t}\n'
    '\t\telse\n'
    '\t\t{\n'
    '\t\t\tv24hdr_hotfix13_reset_final_proxy();\n'
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
# DXGI ResizeBuffers/ResizeBuffers1: HOTFIX15 may convert eligible R8->R10 from startup; failures roll back to R8.
# A failed colorspace set is treated as a failure and rolled all the way back to R8.
# ======================================================================================
p = Path('source/dxgi/dxgi_swapchain.cpp')
s = read(p)
s = once(s, '#include "runtime_manager.hpp"\n', '#include "runtime_manager.hpp"\n#include "v24hdr_dxgi_gate_hotfix5.hpp"\n#include "v24hdr_swapchain_proxy_shaders.hpp"\n', 'swap HOTFIX12 includes')

# HOTFIX13: RenoDX critical UberPost remains intermediate-only. Game backbuffer writes are redirected to FP16 clones; encode those only at the final native Present boundary.
# HOTFIX13_NATIVE_FP16_BACKBUFFER_CLONE=1
# HOTFIX13_NO_PRESENT_COPY=1
# Previous HOTFIX12 wording follows for lineage:
# RenoDX's critical UberPost remains an intermediate pass. Encode that
# intermediate frame only at the final D3D12 swapchain boundary with the exact
# pinned RenoDX D3D12 swapchain proxy shaders.
final_proxy_helpers = r'''
static std::recursive_mutex g_v24hdr_hotfix13_proxy_mutex;
static IDXGISwapChain *g_v24hdr_hotfix13_proxy_owner = nullptr;
static com_ptr<ID3D12RootSignature> g_v24hdr_hotfix13_proxy_root_signature;
static com_ptr<ID3D12PipelineState> g_v24hdr_hotfix13_proxy_pso;
static com_ptr<ID3D12DescriptorHeap> g_v24hdr_hotfix13_proxy_srv_heap;
static com_ptr<ID3D12DescriptorHeap> g_v24hdr_hotfix13_proxy_rtv_heap;
static std::vector<ID3D12Resource *> g_v24hdr_hotfix13_backbuffers;
static std::vector<ID3D12Resource *> g_v24hdr_hotfix13_clones;
static UINT g_v24hdr_hotfix13_proxy_width = 0;
static UINT g_v24hdr_hotfix13_proxy_height = 0;
static UINT g_v24hdr_hotfix13_proxy_buffers = 0;
static UINT g_v24hdr_hotfix13_proxy_rtv_stride = 0;
static UINT g_v24hdr_hotfix13_proxy_srv_stride = 0;
static uint64_t g_v24hdr_hotfix13_proxy_prepare_count = 0;
static uint64_t g_v24hdr_hotfix13_proxy_draw_count = 0;
static uint64_t g_v24hdr_hotfix13_proxy_draw_fail_count = 0;

static void v24hdr_hotfix13_reset_final_proxy_locked()
{
    v24hdr_hotfix13_clear_swapchain_clones();
    for (ID3D12Resource *r : g_v24hdr_hotfix13_clones) if (r != nullptr) r->Release();
    for (ID3D12Resource *r : g_v24hdr_hotfix13_backbuffers) if (r != nullptr) r->Release();
    g_v24hdr_hotfix13_clones.clear();
    g_v24hdr_hotfix13_backbuffers.clear();
    g_v24hdr_hotfix13_proxy_rtv_heap.reset();
    g_v24hdr_hotfix13_proxy_srv_heap.reset();
    g_v24hdr_hotfix13_proxy_pso.reset();
    g_v24hdr_hotfix13_proxy_root_signature.reset();
    g_v24hdr_hotfix13_proxy_owner = nullptr;
    g_v24hdr_hotfix13_proxy_width = 0;
    g_v24hdr_hotfix13_proxy_height = 0;
    g_v24hdr_hotfix13_proxy_buffers = 0;
    g_v24hdr_hotfix13_proxy_rtv_stride = 0;
    g_v24hdr_hotfix13_proxy_srv_stride = 0;
}

void v24hdr_hotfix13_reset_final_proxy()
{
    std::lock_guard<std::recursive_mutex> lock(g_v24hdr_hotfix13_proxy_mutex);
    v24hdr_hotfix13_reset_final_proxy_locked();
}

static bool v24hdr_hotfix13_prepare_fail(const char *phase, HRESULT hr, ID3D12Resource *back0, ID3D12Device *device, IDXGISwapChain3 *sc3)
{
    if (back0 != nullptr) back0->Release();
    if (device != nullptr) device->Release();
    if (sc3 != nullptr) sc3->Release();
    v24hdr_hotfix13_reset_final_proxy_locked();
    reshade::log::message(reshade::log::level::warning,
        "KAIOZEN V24 HDR OUTPUT HOTFIX13: FP16_CLONE_PREPARE_FAIL phase=%s hr=0x%08X HDR_BLOCKED=1.",
        phase, static_cast<unsigned>(hr));
    return false;
}

bool v24hdr_hotfix13_prepare_final_proxy(IDXGISwapChain *swapchain, const char *phase)
{
    std::lock_guard<std::recursive_mutex> lock(g_v24hdr_hotfix13_proxy_mutex);
    if (swapchain == nullptr) return false;
    IDXGISwapChain3 *sc3 = nullptr;
    ID3D12Device *device = nullptr;
    ID3D12Resource *back0 = nullptr;
    HRESULT hr = swapchain->QueryInterface(IID_PPV_ARGS(&sc3));
    if (FAILED(hr) || sc3 == nullptr) return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3);
    DXGI_SWAP_CHAIN_DESC desc = {};
    hr = sc3->GetDesc(&desc);
    if (FAILED(hr) || desc.BufferDesc.Format != DXGI_FORMAT_R10G10B10A2_UNORM || desc.BufferCount == 0)
        return v24hdr_hotfix13_prepare_fail(phase, FAILED(hr) ? hr : E_INVALIDARG, back0, device, sc3);
    hr = sc3->GetDevice(IID_PPV_ARGS(&device));
    if (FAILED(hr) || device == nullptr) return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3);
    hr = sc3->GetBuffer(0, IID_PPV_ARGS(&back0));
    if (FAILED(hr) || back0 == nullptr) return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3);
    const D3D12_RESOURCE_DESC back_desc = back0->GetDesc();
    if (back_desc.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE2D || back_desc.Format != DXGI_FORMAT_R10G10B10A2_UNORM ||
        back_desc.SampleDesc.Count != 1 || back_desc.Width == 0 || back_desc.Height == 0)
        return v24hdr_hotfix13_prepare_fail(phase, E_INVALIDARG, back0, device, sc3);

    if (g_v24hdr_hotfix13_proxy_owner == swapchain && g_v24hdr_hotfix13_proxy_width == static_cast<UINT>(back_desc.Width) &&
        g_v24hdr_hotfix13_proxy_height == back_desc.Height && g_v24hdr_hotfix13_proxy_buffers == desc.BufferCount &&
        g_v24hdr_hotfix13_proxy_pso != nullptr && g_v24hdr_hotfix13_backbuffers.size() == desc.BufferCount &&
        g_v24hdr_hotfix13_clones.size() == desc.BufferCount)
    {
        back0->Release(); device->Release(); sc3->Release(); return true;
    }
    v24hdr_hotfix13_reset_final_proxy_locked();

    D3D12_DESCRIPTOR_RANGE range = {};
    range.RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV; range.NumDescriptors = 1; range.BaseShaderRegister = 0;
    D3D12_ROOT_PARAMETER param = {};
    param.ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    param.DescriptorTable.NumDescriptorRanges = 1; param.DescriptorTable.pDescriptorRanges = &range;
    param.ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    D3D12_STATIC_SAMPLER_DESC sampler = {};
    sampler.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
    sampler.AddressU = sampler.AddressV = sampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
    sampler.MaxAnisotropy = 1; sampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
    sampler.BorderColor = D3D12_STATIC_BORDER_COLOR_TRANSPARENT_BLACK;
    sampler.MinLOD = 0.0f; sampler.MaxLOD = D3D12_FLOAT32_MAX; sampler.ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    D3D12_ROOT_SIGNATURE_DESC rs_desc = {};
    rs_desc.NumParameters = 1; rs_desc.pParameters = &param; rs_desc.NumStaticSamplers = 1; rs_desc.pStaticSamplers = &sampler;
    rs_desc.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;
    ID3DBlob *serialized = nullptr, *errors = nullptr;
    hr = D3D12SerializeRootSignature(&rs_desc, D3D_ROOT_SIGNATURE_VERSION_1, &serialized, &errors);
    if (FAILED(hr) || serialized == nullptr)
    {
        if (errors != nullptr) errors->Release(); if (serialized != nullptr) serialized->Release();
        return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3);
    }
    if (errors != nullptr) errors->Release();
    hr = device->CreateRootSignature(0, serialized->GetBufferPointer(), serialized->GetBufferSize(), IID_PPV_ARGS(&g_v24hdr_hotfix13_proxy_root_signature));
    serialized->Release();
    if (FAILED(hr) || g_v24hdr_hotfix13_proxy_root_signature == nullptr)
        return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3);

    D3D12_GRAPHICS_PIPELINE_STATE_DESC pso = {};
    pso.pRootSignature = g_v24hdr_hotfix13_proxy_root_signature.get();
    pso.VS = {g_v24hdr_hotfix12_proxy_vs, g_v24hdr_hotfix12_proxy_vs_size};
    pso.PS = {g_v24hdr_hotfix12_proxy_ps, g_v24hdr_hotfix12_proxy_ps_size};
    D3D12_RENDER_TARGET_BLEND_DESC rt_blend = {};
    rt_blend.SrcBlend = D3D12_BLEND_ONE; rt_blend.DestBlend = D3D12_BLEND_ZERO; rt_blend.BlendOp = D3D12_BLEND_OP_ADD;
    rt_blend.SrcBlendAlpha = D3D12_BLEND_ONE; rt_blend.DestBlendAlpha = D3D12_BLEND_ZERO; rt_blend.BlendOpAlpha = D3D12_BLEND_OP_ADD;
    rt_blend.LogicOp = D3D12_LOGIC_OP_NOOP; rt_blend.RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
    for (UINT i = 0; i < 8; ++i) pso.BlendState.RenderTarget[i] = rt_blend;
    pso.SampleMask = UINT_MAX; pso.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID; pso.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
    pso.RasterizerState.DepthClipEnable = TRUE; pso.DepthStencilState.DepthEnable = FALSE; pso.DepthStencilState.StencilEnable = FALSE;
    pso.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE; pso.NumRenderTargets = 1;
    pso.RTVFormats[0] = DXGI_FORMAT_R10G10B10A2_UNORM; pso.SampleDesc.Count = 1;
    hr = device->CreateGraphicsPipelineState(&pso, IID_PPV_ARGS(&g_v24hdr_hotfix13_proxy_pso));
    if (FAILED(hr) || g_v24hdr_hotfix13_proxy_pso == nullptr)
        return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3);

    D3D12_DESCRIPTOR_HEAP_DESC srv_heap_desc = {};
    srv_heap_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV; srv_heap_desc.NumDescriptors = desc.BufferCount;
    srv_heap_desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    hr = device->CreateDescriptorHeap(&srv_heap_desc, IID_PPV_ARGS(&g_v24hdr_hotfix13_proxy_srv_heap));
    if (FAILED(hr)) return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3);
    D3D12_DESCRIPTOR_HEAP_DESC rtv_heap_desc = {};
    rtv_heap_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV; rtv_heap_desc.NumDescriptors = desc.BufferCount;
    hr = device->CreateDescriptorHeap(&rtv_heap_desc, IID_PPV_ARGS(&g_v24hdr_hotfix13_proxy_rtv_heap));
    if (FAILED(hr)) return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3);
    g_v24hdr_hotfix13_proxy_srv_stride = device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
    g_v24hdr_hotfix13_proxy_rtv_stride = device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
    D3D12_CPU_DESCRIPTOR_HANDLE srv_handle = g_v24hdr_hotfix13_proxy_srv_heap->GetCPUDescriptorHandleForHeapStart();
    D3D12_CPU_DESCRIPTOR_HANDLE rtv_handle = g_v24hdr_hotfix13_proxy_rtv_heap->GetCPUDescriptorHandleForHeapStart();
    D3D12_HEAP_PROPERTIES heap = {}; heap.Type = D3D12_HEAP_TYPE_DEFAULT; heap.CreationNodeMask = 1; heap.VisibleNodeMask = 1;

    for (UINT i = 0; i < desc.BufferCount; ++i)
    {
        ID3D12Resource *buffer = nullptr, *clone = nullptr;
        hr = sc3->GetBuffer(i, IID_PPV_ARGS(&buffer));
        if (FAILED(hr) || buffer == nullptr) { if (buffer != nullptr) buffer->Release(); return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3); }
        const D3D12_RESOURCE_DESC bd = buffer->GetDesc();
        if (bd.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE2D || bd.Format != DXGI_FORMAT_R10G10B10A2_UNORM ||
            bd.Width != back_desc.Width || bd.Height != back_desc.Height || bd.SampleDesc.Count != 1)
        { buffer->Release(); return v24hdr_hotfix13_prepare_fail(phase, E_INVALIDARG, back0, device, sc3); }
        D3D12_RESOURCE_DESC cd = bd;
        cd.Format = DXGI_FORMAT_R16G16B16A16_FLOAT;
        cd.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
        hr = device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &cd, D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(&clone));
        if (FAILED(hr) || clone == nullptr)
        { if (clone != nullptr) clone->Release(); buffer->Release(); return v24hdr_hotfix13_prepare_fail(phase, hr, back0, device, sc3); }
        if (!v24hdr_hotfix13_register_swapchain_clone(buffer, clone))
        { clone->Release(); buffer->Release(); return v24hdr_hotfix13_prepare_fail(phase, E_FAIL, back0, device, sc3); }
        g_v24hdr_hotfix13_backbuffers.push_back(buffer);
        g_v24hdr_hotfix13_clones.push_back(clone);
        D3D12_SHADER_RESOURCE_VIEW_DESC srv = {};
        srv.Format = DXGI_FORMAT_R16G16B16A16_FLOAT; srv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
        srv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING; srv.Texture2D.MipLevels = 1;
        device->CreateShaderResourceView(clone, &srv, srv_handle);
        v24hdr_hotfix13_set_clone_bypass(true);
        device->CreateRenderTargetView(buffer, nullptr, rtv_handle);
        v24hdr_hotfix13_set_clone_bypass(false);
        srv_handle.ptr += g_v24hdr_hotfix13_proxy_srv_stride;
        rtv_handle.ptr += g_v24hdr_hotfix13_proxy_rtv_stride;
    }

    g_v24hdr_hotfix13_proxy_owner = swapchain;
    g_v24hdr_hotfix13_proxy_width = static_cast<UINT>(back_desc.Width);
    g_v24hdr_hotfix13_proxy_height = back_desc.Height;
    g_v24hdr_hotfix13_proxy_buffers = desc.BufferCount;
    ++g_v24hdr_hotfix13_proxy_prepare_count;
    reshade::log::message(reshade::log::level::info,
        "KAIOZEN V24 HDR OUTPUT HOTFIX13: FP16_BACKBUFFER_CLONES_READY phase=%s count=%llu width=%u height=%u buffers=%u original_format=%d clone_format=%d no_present_copy=1.",
        phase, static_cast<unsigned long long>(g_v24hdr_hotfix13_proxy_prepare_count), g_v24hdr_hotfix13_proxy_width,
        g_v24hdr_hotfix13_proxy_height, g_v24hdr_hotfix13_proxy_buffers,
        static_cast<int>(DXGI_FORMAT_R10G10B10A2_UNORM), static_cast<int>(DXGI_FORMAT_R16G16B16A16_FLOAT));
    back0->Release(); device->Release(); sc3->Release(); return true;
}

static void v24hdr_hotfix13_draw_fail(const char *reason)
{
    ++g_v24hdr_hotfix13_proxy_draw_fail_count;
    reshade::log::message(reshade::log::level::warning,
        "KAIOZEN V24 HDR OUTPUT HOTFIX13: FINAL_PROXY_DRAW_FAIL reason=%s count=%llu.",
        reason, static_cast<unsigned long long>(g_v24hdr_hotfix13_proxy_draw_fail_count));
}

static void v24hdr_hotfix13_final_proxy_draw(IDXGISwapChain *swapchain, reshade::d3d12::command_queue_impl *queue)
{
    if (!v24hdr_hdr_active() || swapchain == nullptr || queue == nullptr) return;
    std::lock_guard<std::recursive_mutex> lock(g_v24hdr_hotfix13_proxy_mutex);
    if (g_v24hdr_hotfix13_proxy_owner != swapchain || g_v24hdr_hotfix13_proxy_pso == nullptr ||
        g_v24hdr_hotfix13_proxy_srv_heap == nullptr || g_v24hdr_hotfix13_proxy_rtv_heap == nullptr ||
        g_v24hdr_hotfix13_backbuffers.size() != g_v24hdr_hotfix13_proxy_buffers || g_v24hdr_hotfix13_clones.size() != g_v24hdr_hotfix13_proxy_buffers)
    { v24hdr_hotfix13_draw_fail("NOT_PREPARED"); return; }
    IDXGISwapChain3 *sc3 = nullptr;
    if (FAILED(swapchain->QueryInterface(IID_PPV_ARGS(&sc3))) || sc3 == nullptr) { v24hdr_hotfix13_draw_fail("QUERY_SWAPCHAIN3"); return; }
    const UINT index = sc3->GetCurrentBackBufferIndex(); sc3->Release();
    if (index >= g_v24hdr_hotfix13_proxy_buffers) { v24hdr_hotfix13_draw_fail("BAD_BACKBUFFER_INDEX"); return; }
    ID3D12Resource *back = g_v24hdr_hotfix13_backbuffers[index];
    ID3D12Resource *clone = g_v24hdr_hotfix13_clones[index];
    if (back == nullptr || clone == nullptr || !v24hdr_hotfix13_clone_is_present(back))
    { v24hdr_hotfix13_draw_fail("CLONE_NOT_PRESENT"); return; }
    reshade::api::command_list *api_cmd = queue->get_immediate_command_list();
    auto *cmd = api_cmd != nullptr ? reinterpret_cast<ID3D12GraphicsCommandList *>(api_cmd->get_native()) : nullptr;
    if (cmd == nullptr) { v24hdr_hotfix13_draw_fail("NO_IMMEDIATE_COMMAND_LIST"); return; }

    // No backbuffer copy. The game has rendered directly into the FP16 clone via redirected RTVs.
    v24hdr_hotfix13_set_clone_bypass(true);
    D3D12_RESOURCE_BARRIER barriers[2] = {};
    barriers[0].Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barriers[0].Transition.pResource = clone; barriers[0].Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barriers[0].Transition.StateBefore = D3D12_RESOURCE_STATE_PRESENT; barriers[0].Transition.StateAfter = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
    barriers[1].Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barriers[1].Transition.pResource = back; barriers[1].Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barriers[1].Transition.StateBefore = D3D12_RESOURCE_STATE_PRESENT; barriers[1].Transition.StateAfter = D3D12_RESOURCE_STATE_RENDER_TARGET;
    cmd->ResourceBarrier(2, barriers);
    ID3D12DescriptorHeap *heaps[] = {g_v24hdr_hotfix13_proxy_srv_heap.get()};
    cmd->SetDescriptorHeaps(1, heaps); cmd->SetGraphicsRootSignature(g_v24hdr_hotfix13_proxy_root_signature.get());
    cmd->SetPipelineState(g_v24hdr_hotfix13_proxy_pso.get());
    D3D12_GPU_DESCRIPTOR_HANDLE srv = g_v24hdr_hotfix13_proxy_srv_heap->GetGPUDescriptorHandleForHeapStart();
    srv.ptr += static_cast<UINT64>(index) * g_v24hdr_hotfix13_proxy_srv_stride;
    cmd->SetGraphicsRootDescriptorTable(0, srv); cmd->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    D3D12_VIEWPORT vp = {}; vp.Width = static_cast<float>(g_v24hdr_hotfix13_proxy_width); vp.Height = static_cast<float>(g_v24hdr_hotfix13_proxy_height); vp.MaxDepth = 1.0f;
    D3D12_RECT scissor = {0, 0, static_cast<LONG>(g_v24hdr_hotfix13_proxy_width), static_cast<LONG>(g_v24hdr_hotfix13_proxy_height)};
    cmd->RSSetViewports(1, &vp); cmd->RSSetScissorRects(1, &scissor);
    D3D12_CPU_DESCRIPTOR_HANDLE rtv = g_v24hdr_hotfix13_proxy_rtv_heap->GetCPUDescriptorHandleForHeapStart();
    rtv.ptr += static_cast<SIZE_T>(index) * g_v24hdr_hotfix13_proxy_rtv_stride;
    cmd->OMSetRenderTargets(1, &rtv, FALSE, nullptr); cmd->DrawInstanced(3, 1, 0, 0);
    barriers[0].Transition.StateBefore = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE; barriers[0].Transition.StateAfter = D3D12_RESOURCE_STATE_PRESENT;
    barriers[1].Transition.StateBefore = D3D12_RESOURCE_STATE_RENDER_TARGET; barriers[1].Transition.StateAfter = D3D12_RESOURCE_STATE_PRESENT;
    cmd->ResourceBarrier(2, barriers);
    v24hdr_hotfix13_set_clone_bypass(false);
    ++g_v24hdr_hotfix13_proxy_draw_count;
    if (g_v24hdr_hotfix13_proxy_draw_count <= 32 || (g_v24hdr_hotfix13_proxy_draw_count % 120u) == 0)
        reshade::log::message(reshade::log::level::info,
            "KAIOZEN V24 HDR OUTPUT HOTFIX13: FINAL_PROXY_DRAW count=%llu backbuffer=%u source=FP16_CLONE output=R10_HDR10 no_copy=1 width=%u height=%u.",
            static_cast<unsigned long long>(g_v24hdr_hotfix13_proxy_draw_count), index, g_v24hdr_hotfix13_proxy_width, g_v24hdr_hotfix13_proxy_height);
}

'''

# HOTFIX15 retains HOTFIX9's asynchronous resize machinery only as a fallback; startup HDR normally activates earlier. Try a
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
        if (v24hdr_hotfix13_prepare_final_proxy(original, "present_existing_r10") && v24hdr_apply_hdr10_hotfix5(original, "present_existing_r10"))
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
    '#include "runtime_manager.hpp"\n#include "v24hdr_dxgi_gate_hotfix5.hpp"\n#include "v24hdr_swapchain_proxy_shaders.hpp"\n',
    '#include "runtime_manager.hpp"\n#include "v24hdr_dxgi_gate_hotfix5.hpp"\n#include "v24hdr_swapchain_proxy_shaders.hpp"\n' + final_proxy_helpers + transition_helpers + '\n',
    'swap HOTFIX12 final proxy plus HOTFIX9 transition helpers',
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

# HOTFIX13 native FP16 clone path, retaining HOTFIX12B native-bridge compatibility: the inherited V24 D3DMetal bridge
# deliberately replaces the COM-proxy D3D12CommandQueue cast with the private
# reshade::d3d12::command_queue_impl member. Anchor to that actual post-bridge
# flush and feed the same private implementation object to the final proxy draw.
# This keeps game-visible D3D12 objects native and never resurrects the proxy cast.
# HOTFIX13_FINAL_PRESENT_ANCHOR=PRIVATE_D3D12_IMPL_FLUSH
on_present_start = s.find('void DXGISwapChain::on_present(')
on_present_end = s.find('void DXGISwapChain::on_finish_present(', on_present_start)
if on_present_start < 0 or on_present_end < 0:
    raise RuntimeError('HOTFIX13 on_present boundaries missing')
on_present_chunk = s[on_present_start:on_present_end]
d3d12_case = on_present_chunk.find('case reshade::api::device_api::d3d12:')
if d3d12_case < 0:
    raise RuntimeError('HOTFIX13 D3D12 on_present case missing')
d3d12_chunk = on_present_chunk[d3d12_case:]
flush_token = '_direct3d_command_queue_impl->flush_immediate_command_list();'
if d3d12_chunk.count(flush_token) != 1:
    raise RuntimeError(f'HOTFIX13 private D3D12 final flush count={d3d12_chunk.count(flush_token)}')
flush_pos = d3d12_chunk.find(flush_token)
present_effect_pos = d3d12_chunk.rfind('reshade::present_effect_runtime(_impl);', 0, flush_pos)
if present_effect_pos < 0:
    raise RuntimeError('HOTFIX13 D3D12 present_effect_runtime missing before private final flush')
line_start = d3d12_chunk.rfind('\n', 0, flush_pos) + 1
indent = d3d12_chunk[line_start:flush_pos]
if indent.strip() != '':
    raise RuntimeError('HOTFIX13 private D3D12 flush indentation parse failed')
proxy_insert = (
    indent + 'if (v24hdr_hdr_active())\n'
    + indent + '\tv24hdr_hotfix13_final_proxy_draw(_orig, _direct3d_command_queue_impl);\n'
)
d3d12_chunk = d3d12_chunk[:line_start] + proxy_insert + d3d12_chunk[line_start:]
on_present_chunk = on_present_chunk[:d3d12_case] + d3d12_chunk
s = s[:on_present_start] + on_present_chunk + s[on_present_end:]
if 'static_cast<D3D12CommandQueue *>(_direct3d_command_queue)' in s:
    raise RuntimeError('HOTFIX13 proxy-only D3D12 queue cast reintroduced')

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
    '\tif (_direct3d_version == reshade::api::device_api::d3d12) v24hdr_hotfix13_reset_final_proxy();\n'
    '\tg_in_dxgi_runtime = true;\n'
    '\tHRESULT hr = _orig->ResizeBuffers(BufferCount, Width, Height, NewFormat, SwapChainFlags);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '\tif (v24hdr_attempt && SUCCEEDED(hr))\n'
    '\t{\n'
    '\t\tif (v24hdr_hotfix13_prepare_final_proxy(_orig, "resize") && v24hdr_apply_hdr10_hotfix5(_orig, "resize"))\n'
    '\t\t\tv24hdr_set_hdr_active(true);\n'
    '\t\telse\n'
    '\t\t{\n'
    '\t\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE_HDR10_ROLLBACK_R8.");\n'
    '\t\t\tv24hdr_hotfix13_reset_final_proxy();\n'
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
    '\t\tv24hdr_hotfix13_reset_final_proxy();\n'
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
    '\tif (_direct3d_version == reshade::api::device_api::d3d12) v24hdr_hotfix13_reset_final_proxy();\n'
    '\tg_in_dxgi_runtime = true;\n'
    '\tHRESULT hr = static_cast<IDXGISwapChain3 *>(_orig)->ResizeBuffers1(BufferCount, Width, Height, NewFormat, SwapChainFlags, pCreationNodeMask, present_queues.p);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '\tif (v24hdr_attempt && SUCCEEDED(hr))\n'
    '\t{\n'
    '\t\tif (v24hdr_hotfix13_prepare_final_proxy(_orig, "resize1") && v24hdr_apply_hdr10_hotfix5(_orig, "resize1"))\n'
    '\t\t\tv24hdr_set_hdr_active(true);\n'
    '\t\telse\n'
    '\t\t{\n'
    '\t\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 HDR SIDECAR HOTFIX5: RESIZE1_HDR10_ROLLBACK_R8.");\n'
    '\t\t\tv24hdr_hotfix13_reset_final_proxy();\n'
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
    '\t\tv24hdr_hotfix13_reset_final_proxy();\n'
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
HOTFIX13_UBERPOST_STAGE=RENDER_INTERMEDIATE_ONLY
HOTFIX13_FINAL_OUTPUT_STAGE=NATIVE_FP16_BACKBUFFER_CLONE_TO_R10_PROXY
HOTFIX13_FINAL_PROXY_POSITION=AFTER_PRESENT_EFFECT_RUNTIME_BEFORE_D3D12_IMMEDIATE_FLUSH
HOTFIX13_FINAL_ENCODING=HDR10_PQ_BT2020
HOTFIX13_FP16_CLONES_REQUIRED_BEFORE_HDR_ACTIVE=YES
HOTFIX13_NO_PRESENT_COPY=PASS\nHOTFIX13_FP16_BACKBUFFER_CLONE=PASS
CREATE_GRAPHICS_PSO=ORIGINAL_FIRST_PLUS_PRIVATE_NATIVE_SIDECAR
CREATE_PIPELINE_STATE_STREAM=HOOKED_SLOT47_ORIGINAL_FIRST_PLUS_PRIVATE_NATIVE_SIDECAR
PIPELINE_LIBRARY=LOAD_GRAPHICS_AND_LOAD_STREAM_COVERED_NATIVE
CREATE_COMMAND_LIST=HOOKED_SLOT12_ORIGINAL_FIRST_THEN_SIDECAR_BIND
CREATE_COMMAND_LIST1=HOOKED_SLOT51
COMMAND_LIST_RESET=HOOKED_SLOT10_ORIGINAL_FIRST_THEN_SIDECAR_BIND
COMMAND_LIST_SET_PIPELINE_STATE=HOOKED_SLOT25
COMMAND_LIST_CLEAR_STATE=HOOKED_SLOT11_RENO_DX_LOGICAL_PSO_TRACK
COMMAND_LIST_DRAW_INSTANCED=HOOKED_SLOT12_DRAW_TIME_REPLACEMENT
COMMAND_LIST_DRAW_INDEXED_INSTANCED=HOOKED_SLOT13_DRAW_TIME_REPLACEMENT
COMMAND_LIST_EXECUTE_INDIRECT=HOOKED_SLOT59_DRAW_TIME_REPLACEMENT
HOTFIX15_DRAW_TIME_REPLACEMENT=RENO_DX_APPLY_REPLACEMENT_PARITY
HOTFIX15_LOGICAL_PSO_TRACKING=GAME_ORIGINAL_INDEPENDENT_OF_PHYSICAL_SIDECAR
HOTFIX15_CRITICAL_UBERPOST_DRAW_PROOF=ENABLED
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
