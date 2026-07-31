from pathlib import Path
import hashlib

ROOT = Path(".")
SOURCE = ROOT / "source/d3d12/d3d12.cpp"

ASSET_DIR = Path(__file__).resolve().parent

ORIGINAL_PATH = ASSET_DIR / "zzz-parent-dxil-v20.bin"
PRUNED_PATH = ASSET_DIR / "zzz-parent-execute-miss-pruned-v23-5.dxil"

EXPECTED_ORIGINAL_SIZE = 26964
EXPECTED_PRUNED_SIZE = 13704

EXPECTED_ORIGINAL_SHA = (
    "02d3db46e867f0b38da35a492101ae35544f5f93425fb4fb29120aeeea431869"
)

EXPECTED_PRUNED_SHA = (
    "a315cdb97c6d21f4e2ecb50e38de733f8a76f1c86ac14f6ac44d42b72a041ba8"
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require_file(path):
    if not path.is_file():
        raise RuntimeError(f"Missing required file: {path}")


def cpp_array(name, data):
    lines = []

    for offset in range(0, len(data), 16):
        chunk = data[offset:offset + 16]

        lines.append(
            "\t" +
            ", ".join(
                f"0x{byte:02X}"
                for byte in chunk
            ) +
            ","
        )

    return (
        f"alignas(16) static const uint8_t {name}[] = {{\n" +
        "\n".join(lines) +
        "\n};\n"
    )


for required in (
    SOURCE,
    ORIGINAL_PATH,
    PRUNED_PATH,
):
    require_file(required)

original = ORIGINAL_PATH.read_bytes()
pruned = PRUNED_PATH.read_bytes()

if len(original) != EXPECTED_ORIGINAL_SIZE:
    raise RuntimeError(
        f"Original DXIL size mismatch: {len(original)}"
    )

if len(pruned) != EXPECTED_PRUNED_SIZE:
    raise RuntimeError(
        f"Pruned DXIL size mismatch: {len(pruned)}"
    )

if sha256(original) != EXPECTED_ORIGINAL_SHA:
    raise RuntimeError(
        "Original DXIL SHA256 mismatch: " +
        sha256(original)
    )

if sha256(pruned) != EXPECTED_PRUNED_SHA:
    raise RuntimeError(
        "Pruned DXIL SHA256 mismatch: " +
        sha256(pruned)
    )


def model_rewrite(subobjects):
    matches = [
        index
        for index, item in enumerate(subobjects)
        if (
            item["type"] == "dxil" and
            item["blob"] == original
        )
    ]

    if len(matches) != 1:
        return None

    cloned = [
        dict(item)
        for item in subobjects
    ]

    cloned[matches[0]]["blob"] = pruned

    for index, item in enumerate(subobjects):
        if item["type"] != "association":
            continue

        target = item["target"]

        if (
            not isinstance(target, int) or
            target < 0 or
            target >= len(cloned)
        ):
            return None

        cloned[index]["target_object"] = cloned[target]

    return cloned


exports_identity = object()

source_model = [
    {
        "type": "dxil",
        "blob": original,
        "exports": exports_identity,
    },
    {
        "type": "config",
        "flags": 4,
    },
    {
        "type": "association",
        "target": 0,
    },
]

rewritten_model = model_rewrite(source_model)

assert rewritten_model is not None
assert rewritten_model[0]["blob"] == pruned
assert rewritten_model[0]["exports"] is exports_identity
assert rewritten_model[2]["target_object"] is rewritten_model[0]

assert source_model[0]["blob"] == original
assert "target_object" not in source_model[2]

assert model_rewrite([
    {
        "type": "dxil",
        "blob": b"not-the-parent",
        "exports": exports_identity,
    }
]) is None

assert model_rewrite([
    {
        "type": "dxil",
        "blob": original,
        "exports": exports_identity,
    },
    {
        "type": "association",
        "target": 99,
    },
]) is None

text = SOURCE.read_text(
    encoding="utf-8-sig"
)

if "D3DMetal RTX physical DXIL bridge v24:" in text:
    raise RuntimeError(
        "V24 bridge is already present"
    )

if "#include <cstring>\n" not in text:
    include_anchor = "#include <algorithm>\n"

    if text.count(include_anchor) != 1:
        raise RuntimeError(
            "cstring include anchor mismatch: " +
            str(text.count(include_anchor))
        )

    text = text.replace(
        include_anchor,
        include_anchor + "#include <cstring>\n",
        1,
    )

signature = (
    "\tHRESULT STDMETHODCALLTYPE trace_create_state_object(\n"
)

if text.count(signature) != 1:
    raise RuntimeError(
        "trace function signature count mismatch: " +
        str(text.count(signature))
    )

helper = (
    cpp_array(
        "g_v24_original_parent_dxil",
        original,
    ) +
    "\n" +
    cpp_array(
        "g_v24_pruned_parent_dxil",
        pruned,
    ) +
r'''

	bool v24_parent_dxil_matches(
		const void *shader_bytecode,
		size_t bytecode_length)
	{
		if (
			shader_bytecode == nullptr ||
			bytecode_length !=
				sizeof(g_v24_original_parent_dxil))
		{
			return false;
		}

		std::vector<uint8_t> candidate(
			sizeof(g_v24_original_parent_dxil));

		if (!safe_copy_from_process(
			shader_bytecode,
			candidate.data(),
			candidate.size()))
		{
			return false;
		}

		return std::memcmp(
			candidate.data(),
			g_v24_original_parent_dxil,
			sizeof(g_v24_original_parent_dxil)) == 0;
	}

	bool try_v24_physical_dxil_bridge(
		ID3D12Device5 *device,
		uint64_t call_id,
		const D3D12_STATE_OBJECT_DESC *original_desc,
		const D3D12_STATE_OBJECT_DESC &snapshot,
		REFIID riid,
		void **state_object,
		HRESULT &result)
	{
		if (
			original_desc == nullptr ||
			snapshot.NumSubobjects == 0 ||
			snapshot.NumSubobjects > max_capture_subobjects ||
			snapshot.pSubobjects == nullptr)
		{
			return false;
		}

		std::vector<D3D12_STATE_SUBOBJECT>
			source_subobjects(snapshot.NumSubobjects);

		if (!safe_copy_from_process(
			snapshot.pSubobjects,
			source_subobjects.data(),
			source_subobjects.size() *
				sizeof(D3D12_STATE_SUBOBJECT)))
		{
			return false;
		}

		size_t matching_library_count = 0;
		size_t matching_library_index =
			static_cast<size_t>(-1);

		for (
			size_t index = 0;
			index < source_subobjects.size();
			++index)
		{
			const D3D12_STATE_SUBOBJECT &subobject =
				source_subobjects[index];

			if (
				subobject.Type !=
				D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY)
			{
				continue;
			}

			D3D12_DXIL_LIBRARY_DESC library = {};

			if (!safe_copy_from_process(
				subobject.pDesc,
				&library,
				sizeof(library)))
			{
				continue;
			}

			if (!v24_parent_dxil_matches(
				library.DXILLibrary.pShaderBytecode,
				library.DXILLibrary.BytecodeLength))
			{
				continue;
			}

			++matching_library_count;
			matching_library_index = index;
		}

		if (matching_library_count == 0)
			return false;

		auto forward_original_once = [&]() -> bool
		{
			if (state_object != nullptr)
				*state_object = nullptr;

			result = s_original_create_state_object(
				device,
				original_desc,
				riid,
				state_object);

			return true;
		};

		if (matching_library_count != 1)
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX physical DXIL bridge v24: "
				"ABORT call=%llu reason=match-count "
				"matches=%llu expected=1; "
				"forwarding original once.",
				static_cast<unsigned long long>(call_id),
				static_cast<unsigned long long>(
					matching_library_count));

			return forward_original_once();
		}

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX physical DXIL bridge v24: "
			"MATCH call=%llu subobject=%llu "
			"original_bytes=%llu "
			"original_sha="
			"02d3db46e867f0b38da35a492101ae355"
			"44f5f93425fb4fb29120aeeea431869.",
			static_cast<unsigned long long>(call_id),
			static_cast<unsigned long long>(
				matching_library_index),
			static_cast<unsigned long long>(
				sizeof(g_v24_original_parent_dxil)));

		std::vector<D3D12_STATE_SUBOBJECT>
			cloned_subobjects = source_subobjects;

		D3D12_DXIL_LIBRARY_DESC
			replacement_library = {};

		if (!safe_copy_from_process(
			source_subobjects[
				matching_library_index].pDesc,
			&replacement_library,
			sizeof(replacement_library)))
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX physical DXIL bridge v24: "
				"ABORT call=%llu "
				"reason=matching-library-unreadable; "
				"forwarding original once.",
				static_cast<unsigned long long>(call_id));

			return forward_original_once();
		}

		replacement_library.DXILLibrary.pShaderBytecode =
			g_v24_pruned_parent_dxil;

		replacement_library.DXILLibrary.BytecodeLength =
			sizeof(g_v24_pruned_parent_dxil);

		cloned_subobjects[
			matching_library_index].pDesc =
			&replacement_library;

		std::deque<
			D3D12_SUBOBJECT_TO_EXPORTS_ASSOCIATION>
			cloned_associations;

		const uintptr_t source_begin =
			reinterpret_cast<uintptr_t>(
				snapshot.pSubobjects);

		const size_t source_bytes =
			source_subobjects.size() *
			sizeof(D3D12_STATE_SUBOBJECT);

		size_t remapped_association_count = 0;

		for (
			size_t index = 0;
			index < source_subobjects.size();
			++index)
		{
			const D3D12_STATE_SUBOBJECT &source_subobject =
				source_subobjects[index];

			if (
				source_subobject.Type !=
				D3D12_STATE_SUBOBJECT_TYPE_SUBOBJECT_TO_EXPORTS_ASSOCIATION)
			{
				continue;
			}

			D3D12_SUBOBJECT_TO_EXPORTS_ASSOCIATION
				association = {};

			if (!safe_copy_from_process(
				source_subobject.pDesc,
				&association,
				sizeof(association)))
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX physical DXIL bridge v24: "
					"ABORT call=%llu "
					"reason=association-unreadable "
					"sub=%llu; forwarding original once.",
					static_cast<unsigned long long>(call_id),
					static_cast<unsigned long long>(index));

				return forward_original_once();
			}

			const uintptr_t target =
				reinterpret_cast<uintptr_t>(
					association.pSubobjectToAssociate);

			if (target < source_begin)
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX physical DXIL bridge v24: "
					"ABORT call=%llu "
					"reason=association-target-before-array "
					"sub=%llu; forwarding original once.",
					static_cast<unsigned long long>(call_id),
					static_cast<unsigned long long>(index));

				return forward_original_once();
			}

			const uintptr_t offset =
				target - source_begin;

			if (
				offset >= source_bytes ||
				offset %
					sizeof(D3D12_STATE_SUBOBJECT) != 0)
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX physical DXIL bridge v24: "
					"ABORT call=%llu "
					"reason=association-target-invalid "
					"sub=%llu offset=%llu bytes=%llu; "
					"forwarding original once.",
					static_cast<unsigned long long>(call_id),
					static_cast<unsigned long long>(index),
					static_cast<unsigned long long>(offset),
					static_cast<unsigned long long>(
						source_bytes));

				return forward_original_once();
			}

			const size_t target_index =
				static_cast<size_t>(
					offset /
					sizeof(D3D12_STATE_SUBOBJECT));

			association.pSubobjectToAssociate =
				&cloned_subobjects[target_index];

			cloned_associations.push_back(
				association);

			cloned_subobjects[index].pDesc =
				&cloned_associations.back();

			++remapped_association_count;
		}

		D3D12_STATE_OBJECT_DESC rewritten_desc =
			snapshot;

		rewritten_desc.pSubobjects =
			cloned_subobjects.data();

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX physical DXIL bridge v24: "
			"READY call=%llu replacement_bytes=%llu "
			"replacement_sha="
			"a315cdb97c6d21f4e2ecb50e38de733f"
			"8a76f1c86ac14f6ac44d42b72a041ba8 "
			"associations_remapped=%llu "
			"exports_preserved=1 subobjects=%u.",
			static_cast<unsigned long long>(call_id),
			static_cast<unsigned long long>(
				sizeof(g_v24_pruned_parent_dxil)),
			static_cast<unsigned long long>(
				remapped_association_count),
			rewritten_desc.NumSubobjects);

		if (state_object != nullptr)
			*state_object = nullptr;

		result = s_original_create_state_object(
			device,
			&rewritten_desc,
			riid,
			state_object);

		void *created_object = nullptr;

		if (state_object != nullptr)
		{
			safe_copy_from_process(
				state_object,
				&created_object,
				sizeof(created_object));
		}

		reshade::log::message(
			FAILED(result) ?
				reshade::log::level::warning :
				reshade::log::level::info,
			"D3DMetal RTX physical DXIL bridge v24: "
			"POST call=%llu hr=%s raw=0x%08X object=%p.",
			static_cast<unsigned long long>(call_id),
			reshade::log::hr_to_string(result).c_str(),
			static_cast<uint32_t>(result),
			created_object);

		if (
			SUCCEEDED(result) &&
			created_object != nullptr)
		{
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX physical DXIL bridge v24: "
				"ACTIVE call=%llu; physically pruned "
				"ExecuteTrace-plus-Miss parent DXIL "
				"was accepted by the native compiler.",
				static_cast<unsigned long long>(call_id));
		}

		return true;
	}

'''
)

text = text.replace(
    signature,
    helper + "\n" + signature,
    1,
)

trace_position = text.find(signature)

gate_anchor = (
    "\t\tD3D12_STATE_OBJECT_DESC snapshot = {};\n"
    "\t\tconst bool readable = "
    "safe_copy_from_process(desc, &snapshot, sizeof(snapshot));\n"
)

gate_position = text.find(
    gate_anchor,
    trace_position,
)

if gate_position < 0:
    raise RuntimeError(
        "V24 gate anchor was not found"
    )

gate_insert_position = (
    gate_position +
    len(gate_anchor)
)

gate = r'''

		if (readable)
		{
			HRESULT v24_result = E_FAIL;

			if (try_v24_physical_dxil_bridge(
				device,
				call_id,
				desc,
				snapshot,
				riid,
				state_object,
				v24_result))
			{
				return v24_result;
			}
		}
'''

text = (
    text[:gate_insert_position] +
    gate +
    text[gate_insert_position:]
)

required_markers = [
    "D3DMetal RTX physical DXIL bridge v24: MATCH",
    "D3DMetal RTX physical DXIL bridge v24: READY",
    "D3DMetal RTX physical DXIL bridge v24: POST",
    "D3DMetal RTX physical DXIL bridge v24: ACTIVE",
    "g_v24_original_parent_dxil",
    "g_v24_pruned_parent_dxil",
    "try_v24_physical_dxil_bridge(",
    "std::memcmp(",
    "create_state_object_vtable_index = 62",
]

for marker in required_markers:
    if marker not in text:
        raise RuntimeError(
            "Missing V24 source marker: " +
            marker
        )

trace_position = text.find(signature)

gate_position = text.find(
    "if (try_v24_physical_dxil_bridge(",
    trace_position,
)

legacy_position = text.find(
    "const HRESULT original_hr = "
    "s_original_create_state_object",
    trace_position,
)

if not (
    trace_position >= 0 and
    gate_position > trace_position and
    legacy_position > gate_position
):
    raise RuntimeError(
        "V24 gate ordering is invalid"
    )

SOURCE.write_text(
    text,
    encoding="utf-8",
    newline="\n",
)

report = Path("v24-patch-report.txt")

report.write_text(
    "\n".join([
        "V24_PHYSICAL_DXIL_BRIDGE_PATCH_OK",
        "V24_DESCRIPTOR_HARNESS_PASS",
        f"ORIGINAL_SIZE={len(original)}",
        f"ORIGINAL_SHA256={sha256(original)}",
        f"PRUNED_SIZE={len(pruned)}",
        f"PRUNED_SHA256={sha256(pruned)}",
        "MATCH_REPLACEMENT=PASS",
        "EXPORTS_UNCHANGED=PASS",
        "ASSOCIATION_REMAP=PASS",
        "NONMATCH_UNCHANGED=PASS",
        "SOURCE_NOT_MUTATED=PASS",
        "MALFORMED_ASSOCIATION_REJECTED=PASS",
        "GATE_BEFORE_LEGACY_CALL=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)

print(report.read_text(encoding="utf-8"))
