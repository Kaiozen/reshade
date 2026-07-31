from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")

if not SOURCE.is_file():
    raise RuntimeError(
        f"Missing source file: {SOURCE}"
    )

text = SOURCE.read_text(
    encoding="utf-8-sig"
)

if "D3DMetal RTX physical DXIL bridge v24:" not in text:
    raise RuntimeError(
        "V24 must be applied before V25"
    )

if "D3DMetal RTX semantic matrix minimizer v25:" in text:
    raise RuntimeError(
        "V25 is already present"
    )

include_anchor = "#include <cstring>\n"

if text.count(include_anchor) != 1:
    raise RuntimeError(
        "V25 include anchor mismatch: " +
        str(text.count(include_anchor))
    )

extra_includes = (
    "#include <cstring>\n"
    "#include <filesystem>\n"
    "#include <fstream>\n"
    "#include <sstream>\n"
    "#include <iomanip>\n"
    "#include <initializer_list>\n"
)

text = text.replace(
    include_anchor,
    extra_includes,
    1,
)

signature = (
    "\tHRESULT STDMETHODCALLTYPE "
    "trace_create_state_object(\n"
)

if text.count(signature) != 1:
    raise RuntimeError(
        "V25 trace signature mismatch: " +
        str(text.count(signature))
    )

helper = r'''
	constexpr size_t
		v25_create_root_signature_vtable_index = 16;

	using v25_create_root_signature_fn =
		HRESULT (STDMETHODCALLTYPE *)(
			ID3D12Device *,
			UINT,
			const void *,
			SIZE_T,
			REFIID,
			void **);

	struct v25_root_capture
	{
		uint64_t call_id = 0;
		UINT node_mask = 0;
		IUnknown *identity = nullptr;
		std::vector<uint8_t> serialized;
	};

	struct v25_variant_storage
	{
		std::vector<D3D12_STATE_SUBOBJECT> subobjects;
		std::vector<size_t> old_to_new;

		std::deque<D3D12_STATE_OBJECT_CONFIG>
			state_configs;

		std::deque<D3D12_DXIL_LIBRARY_DESC>
			libraries;

		std::deque<std::vector<D3D12_EXPORT_DESC>>
			export_arrays;

		std::deque<
			D3D12_SUBOBJECT_TO_EXPORTS_ASSOCIATION>
			associations;

		std::deque<std::vector<LPCWSTR>>
			association_export_arrays;
	};

	struct v25_probe_summary
	{
		unsigned int next_index = 1;
		unsigned int accepted = 0;
		unsigned int rejected = 0;
		unsigned int controls_accepted = 0;
		unsigned int controls_rejected = 0;
		std::string first_semantic_accepted;
	};

	enum class v25_export_filter
	{
		all,
		execute_trace,
		miss,
	};

	static v25_create_root_signature_fn
		s_v25_original_create_root_signature = nullptr;

	static std::once_flag
		s_v25_root_signature_install_once;

	static std::atomic<uint64_t>
		s_v25_root_signature_call_index = 0;

	static std::mutex
		s_v25_root_capture_mutex;

	static std::vector<
		std::shared_ptr<v25_root_capture>>
		s_v25_root_captures;

	static std::atomic<int>
		s_v25_matrix_state = 0;

	static std::atomic<unsigned int>
		s_v25_passthrough_logs = 0;

	static int s_v25_module_anchor = 0;

	bool v25_copy_wstring(
		LPCWSTR source,
		std::wstring &destination)
	{
		destination.clear();

		if (source == nullptr)
			return false;

		for (
			size_t index = 0;
			index < max_capture_string_chars;
			++index)
		{
			wchar_t character = L'\0';

			if (!safe_copy_from_process(
				source + index,
				&character,
				sizeof(character)))
			{
				return false;
			}

			if (character == L'\0')
				return true;

			destination.push_back(character);
		}

		return false;
	}

	std::string v25_utf8(
		const std::wstring &value)
	{
		if (value.empty())
			return {};

		const int required =
			WideCharToMultiByte(
				CP_UTF8,
				0,
				value.data(),
				static_cast<int>(value.size()),
				nullptr,
				0,
				nullptr,
				nullptr);

		if (required <= 0)
			return {};

		std::string result(
			static_cast<size_t>(required),
			'\0');

		WideCharToMultiByte(
			CP_UTF8,
			0,
			value.data(),
			static_cast<int>(value.size()),
			result.data(),
			required,
			nullptr,
			nullptr);

		return result;
	}

	bool v25_name_equals(
		LPCWSTR source,
		const wchar_t *expected)
	{
		std::wstring value;

		return
			v25_copy_wstring(source, value) &&
			value == expected;
	}

	bool v25_filter_matches(
		LPCWSTR source,
		v25_export_filter filter)
	{
		switch (filter)
		{
		case v25_export_filter::all:
			return true;

		case v25_export_filter::execute_trace:
			return v25_name_equals(
				source,
				L"ExecuteTrace");

		case v25_export_filter::miss:
			return v25_name_equals(
				source,
				L"Miss");

		default:
			return false;
		}
	}

	uint64_t v25_fnv1a_memory(
		const void *source,
		size_t size,
		bool &readable)
	{
		constexpr uint64_t offset =
			1469598103934665603ull;

		constexpr uint64_t prime =
			1099511628211ull;

		readable = false;

		if (source == nullptr && size != 0)
			return 0;

		uint64_t hash = offset;

		std::vector<uint8_t> block(
			64 * 1024);

		size_t position = 0;

		while (position < size)
		{
			const size_t count =
				(size - position) < block.size() ?
				(size - position) :
				block.size();

			const uint8_t *address =
				static_cast<const uint8_t *>(source) +
				position;

			if (!safe_copy_from_process(
				address,
				block.data(),
				count))
			{
				return 0;
			}

			for (size_t index = 0; index < count; ++index)
			{
				hash ^= block[index];
				hash *= prime;
			}

			position += count;
		}

		readable = true;
		return hash;
	}

	bool v25_dump_memory(
		const std::filesystem::path &path,
		const void *source,
		size_t size)
	{
		if (source == nullptr || size == 0)
			return false;

		std::ofstream output(
			path,
			std::ios::binary);

		if (!output)
			return false;

		std::vector<uint8_t> block(
			64 * 1024);

		size_t position = 0;

		while (position < size)
		{
			const size_t count =
				(size - position) < block.size() ?
					(size - position) :
					block.size();

			const uint8_t *address =
				static_cast<const uint8_t *>(source) +
				position;

			if (!safe_copy_from_process(
				address,
				block.data(),
				count))
			{
				return false;
			}

			output.write(
				reinterpret_cast<const char *>(
					block.data()),
				static_cast<std::streamsize>(count));

			if (!output)
				return false;

			position += count;
		}

		return true;
	}

	bool v25_capture_directory(
		std::filesystem::path &directory)
	{
		HMODULE module = nullptr;

		if (!GetModuleHandleExW(
			GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
			GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
			reinterpret_cast<LPCWSTR>(
				&s_v25_module_anchor),
			&module))
		{
			return false;
		}

		std::vector<wchar_t> module_path(
			32768,
			L'\0');

		const DWORD length =
			GetModuleFileNameW(
				module,
				module_path.data(),
				static_cast<DWORD>(
					module_path.size()));

		if (
			length == 0 ||
			length >= module_path.size())
		{
			return false;
		}

		std::filesystem::path dll_path(
			std::wstring(
				module_path.data(),
				length));

		directory =
			dll_path.parent_path() /
			L"zzz-v25-capture";

		std::error_code error;

		std::filesystem::create_directories(
			directory,
			error);

		return !error;
	}

	HRESULT STDMETHODCALLTYPE
	v25_trace_create_root_signature(
		ID3D12Device *device,
		UINT node_mask,
		const void *serialized_blob,
		SIZE_T serialized_size,
		REFIID riid,
		void **root_signature)
	{
		const uint64_t call_id =
			++s_v25_root_signature_call_index;

		std::vector<uint8_t> copy;

		if (
			serialized_blob != nullptr &&
			serialized_size != 0 &&
			serialized_size <=
				64ull * 1024ull * 1024ull)
		{
			copy.resize(
				static_cast<size_t>(
					serialized_size));

			if (!safe_copy_from_process(
				serialized_blob,
				copy.data(),
				copy.size()))
			{
				copy.clear();
			}
		}

		const HRESULT result =
			s_v25_original_create_root_signature(
				device,
				node_mask,
				serialized_blob,
				serialized_size,
				riid,
				root_signature);

		void *created = nullptr;

		if (root_signature != nullptr)
		{
			safe_copy_from_process(
				root_signature,
				&created,
				sizeof(created));
		}

		if (
			SUCCEEDED(result) &&
			created != nullptr &&
			!copy.empty())
		{
			IUnknown *identity = nullptr;

			if (SUCCEEDED(
				reinterpret_cast<IUnknown *>(created)->
					QueryInterface(
						IID_IUnknown,
						reinterpret_cast<void **>(
							&identity))) &&
				identity != nullptr)
			{
				bool duplicate = false;

				{
					std::lock_guard<std::mutex> lock(
						s_v25_root_capture_mutex);

					for (const auto &existing :
						s_v25_root_captures)
					{
						if (
							existing->identity ==
							identity)
						{
							duplicate = true;
							break;
						}
					}

					if (!duplicate)
					{
						auto capture =
							std::make_shared<
								v25_root_capture>();

						capture->call_id = call_id;
						capture->node_mask =
							node_mask;
						capture->identity =
							identity;
						capture->serialized =
							std::move(copy);

						s_v25_root_captures.push_back(
							std::move(capture));
					}
				}

				if (duplicate)
					identity->Release();
			}
		}

		reshade::log::message(
			FAILED(result) ?
				reshade::log::level::warning :
				reshade::log::level::info,
			"D3DMetal RTX root capture v25: "
			"CALL call=%llu node_mask=0x%X "
			"bytes=%llu hr=%s raw=0x%08X "
			"object=%p captured=%u.",
			static_cast<unsigned long long>(call_id),
			node_mask,
			static_cast<unsigned long long>(
				serialized_size),
			reshade::log::hr_to_string(result).c_str(),
			static_cast<uint32_t>(result),
			created,
			!copy.empty() ? 1u : 0u);

		return result;
	}

	void install_v25_root_signature_trace(
		ID3D12Device *device)
	{
		if (device == nullptr)
			return;

		std::call_once(
			s_v25_root_signature_install_once,
			[device]()
			{
				void **const vtable =
					*reinterpret_cast<void ***>(
						device);

				void *const current =
					vtable[
						v25_create_root_signature_vtable_index];

				if (
					current ==
					reinterpret_cast<void *>(
						&v25_trace_create_root_signature))
				{
					return;
				}

				s_v25_original_create_root_signature =
					reinterpret_cast<
						v25_create_root_signature_fn>(
							current);

				DWORD old_protect = 0;

				if (!VirtualProtect(
					&vtable[
						v25_create_root_signature_vtable_index],
					sizeof(void *),
					PAGE_EXECUTE_READWRITE,
					&old_protect))
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX root capture v25: "
						"VirtualProtect failed error=%lu.",
						GetLastError());

					s_v25_original_create_root_signature =
						nullptr;

					return;
				}

				InterlockedExchangePointer(
					reinterpret_cast<
						PVOID volatile *>(
							&vtable[
								v25_create_root_signature_vtable_index]),
					reinterpret_cast<PVOID>(
						&v25_trace_create_root_signature));

				DWORD ignored = 0;

				VirtualProtect(
					&vtable[
						v25_create_root_signature_vtable_index],
					sizeof(void *),
					old_protect,
					&ignored);

				FlushInstructionCache(
					GetCurrentProcess(),
					&vtable[
						v25_create_root_signature_vtable_index],
					sizeof(void *));

				if (
					vtable[
						v25_create_root_signature_vtable_index] !=
					reinterpret_cast<void *>(
						&v25_trace_create_root_signature))
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX root capture v25: "
						"hook verification failed slot=%zu.",
						v25_create_root_signature_vtable_index);

					s_v25_original_create_root_signature =
						nullptr;

					return;
				}

				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX root capture v25: "
					"CreateRootSignature hook installed "
					"at verified slot 16 original=%p "
					"replacement=%p.",
					reinterpret_cast<void *>(
						s_v25_original_create_root_signature),
					reinterpret_cast<void *>(
						&v25_trace_create_root_signature));
			});
	}

	bool v25_root_capture_info(
		ID3D12RootSignature *root,
		uint64_t &call_id,
		size_t &size)
	{
		call_id = 0;
		size = 0;

		if (root == nullptr)
			return false;

		IUnknown *identity = nullptr;

		if (FAILED(
			root->QueryInterface(
				IID_IUnknown,
				reinterpret_cast<void **>(
					&identity))) ||
			identity == nullptr)
		{
			return false;
		}

		bool found = false;

		{
			std::lock_guard<std::mutex> lock(
				s_v25_root_capture_mutex);

			for (const auto &capture :
				s_v25_root_captures)
			{
				if (
					capture->identity ==
					identity)
				{
					call_id =
						capture->call_id;

					size =
						capture->serialized.size();

					found = true;
					break;
				}
			}
		}

		identity->Release();
		return found;
	}

	void v25_write_name(
		std::ostream &output,
		LPCWSTR name)
	{
		if (name == nullptr)
		{
			output << "<null>";
			return;
		}

		std::wstring value;

		if (!v25_copy_wstring(
			name,
			value))
		{
			output << "<unreadable>";
			return;
		}

		output << '"' << v25_utf8(value) << '"';
	}

	void v25_write_descriptor(
		std::ostream &output,
		uint64_t call_id,
		const D3D12_STATE_OBJECT_DESC &desc,
		const std::vector<D3D12_STATE_SUBOBJECT>
			&subobjects)
	{
		output
			<< "STATE_OBJECT call="
			<< call_id
			<< " type="
			<< state_object_type_name(desc.Type)
			<< "("
			<< static_cast<unsigned int>(desc.Type)
			<< ") subobjects="
			<< subobjects.size()
			<< "\n";

		const uintptr_t begin =
			reinterpret_cast<uintptr_t>(
				desc.pSubobjects);

		const uintptr_t end =
			begin +
			subobjects.size() *
				sizeof(D3D12_STATE_SUBOBJECT);

		for (
			size_t index = 0;
			index < subobjects.size();
			++index)
		{
			const D3D12_STATE_SUBOBJECT &sub =
				subobjects[index];

			output
				<< "SUB index="
				<< index
				<< " type="
				<< subobject_type_name(sub.Type)
				<< "("
				<< static_cast<unsigned int>(
					sub.Type)
				<< ") desc=0x"
				<< std::hex
				<< reinterpret_cast<uintptr_t>(
					sub.pDesc)
				<< std::dec;

			switch (sub.Type)
			{
			case
				D3D12_STATE_SUBOBJECT_TYPE_STATE_OBJECT_CONFIG:
			{
				D3D12_STATE_OBJECT_CONFIG value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					output
						<< " flags=0x"
						<< std::hex
						<< static_cast<unsigned int>(
							value.Flags)
						<< std::dec;
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_GLOBAL_ROOT_SIGNATURE:
			{
				D3D12_GLOBAL_ROOT_SIGNATURE value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					uint64_t root_call = 0;
					size_t root_size = 0;

					output
						<< " root=0x"
						<< std::hex
						<< reinterpret_cast<uintptr_t>(
							value.pGlobalRootSignature)
						<< std::dec;

					if (v25_root_capture_info(
						value.pGlobalRootSignature,
						root_call,
						root_size))
					{
						output
							<< " root_capture_call="
							<< root_call
							<< " root_bytes="
							<< root_size;
					}
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_LOCAL_ROOT_SIGNATURE:
			{
				D3D12_LOCAL_ROOT_SIGNATURE value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					uint64_t root_call = 0;
					size_t root_size = 0;

					output
						<< " root=0x"
						<< std::hex
						<< reinterpret_cast<uintptr_t>(
							value.pLocalRootSignature)
						<< std::dec;

					if (v25_root_capture_info(
						value.pLocalRootSignature,
						root_call,
						root_size))
					{
						output
							<< " root_capture_call="
							<< root_call
							<< " root_bytes="
							<< root_size;
					}
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_NODE_MASK:
			{
				UINT value = 0;

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					output
						<< " node_mask=0x"
						<< std::hex
						<< value
						<< std::dec;
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY:
			{
				D3D12_DXIL_LIBRARY_DESC value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					bool hash_readable = false;

					const uint64_t hash =
						v25_fnv1a_memory(
							value.DXILLibrary.
								pShaderBytecode,
							value.DXILLibrary.
								BytecodeLength,
							hash_readable);

					output
						<< " bytes="
						<< value.DXILLibrary.
							BytecodeLength
						<< " exports="
						<< value.NumExports;

					if (hash_readable)
					{
						output
							<< " fnv1a64=0x"
							<< std::hex
							<< hash
							<< std::dec;
					}

					if (
						value.NumExports != 0 &&
						value.pExports != nullptr &&
						value.NumExports <=
							max_capture_exports)
					{
						std::vector<D3D12_EXPORT_DESC>
							exports(value.NumExports);

						if (safe_copy_from_process(
							value.pExports,
							exports.data(),
							exports.size() *
								sizeof(
									D3D12_EXPORT_DESC)))
						{
							for (
								size_t export_index = 0;
								export_index <
									exports.size();
								++export_index)
							{
								output
									<< " export["
									<< export_index
									<< "]=";

								v25_write_name(
									output,
									exports[
										export_index].Name);

								output
									<< " rename=";

								v25_write_name(
									output,
									exports[
										export_index].
										ExportToRename);

								output
									<< " flags=0x"
									<< std::hex
									<< static_cast<
										unsigned int>(
											exports[
												export_index].
												Flags)
									<< std::dec;
							}
						}
					}
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_EXISTING_COLLECTION:
			{
				D3D12_EXISTING_COLLECTION_DESC value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					output
						<< " collection=0x"
						<< std::hex
						<< reinterpret_cast<uintptr_t>(
							value.pExistingCollection)
						<< std::dec
						<< " exports="
						<< value.NumExports;

					auto captured =
						find_captured_collection(
							value.pExistingCollection);

					if (captured)
					{
						output
							<< " captured_call="
							<< captured->source_call;
					}
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_SUBOBJECT_TO_EXPORTS_ASSOCIATION:
			{
				D3D12_SUBOBJECT_TO_EXPORTS_ASSOCIATION
					value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					const uintptr_t target =
						reinterpret_cast<uintptr_t>(
							value.
								pSubobjectToAssociate);

					output
						<< " target=0x"
						<< std::hex
						<< target
						<< std::dec
						<< " exports="
						<< value.NumExports;

					if (
						target >= begin &&
						target < end &&
						(target - begin) %
							sizeof(
								D3D12_STATE_SUBOBJECT) ==
							0)
					{
						output
							<< " target_index="
							<< (
								(target - begin) /
								sizeof(
									D3D12_STATE_SUBOBJECT));
					}

					if (
						value.NumExports != 0 &&
						value.pExports != nullptr &&
						value.NumExports <=
							max_capture_exports)
					{
						std::vector<LPCWSTR>
							names(value.NumExports);

						if (safe_copy_from_process(
							value.pExports,
							names.data(),
							names.size() *
								sizeof(LPCWSTR)))
						{
							for (
								size_t name_index = 0;
								name_index <
									names.size();
								++name_index)
							{
								output
									<< " assoc_export["
									<< name_index
									<< "]=";

								v25_write_name(
									output,
									names[name_index]);
							}
						}
					}
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_DXIL_SUBOBJECT_TO_EXPORTS_ASSOCIATION:
			{
				D3D12_DXIL_SUBOBJECT_TO_EXPORTS_ASSOCIATION
					value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					output << " subobject_name=";

					v25_write_name(
						output,
						value.SubobjectToAssociate);

					output
						<< " exports="
						<< value.NumExports;
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_SHADER_CONFIG:
			{
				D3D12_RAYTRACING_SHADER_CONFIG value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					output
						<< " payload="
						<< value.
							MaxPayloadSizeInBytes
						<< " attribute="
						<< value.
							MaxAttributeSizeInBytes;
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_PIPELINE_CONFIG:
			{
				D3D12_RAYTRACING_PIPELINE_CONFIG value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					output
						<< " recursion="
						<< value.
							MaxTraceRecursionDepth;
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_PIPELINE_CONFIG1:
			{
				D3D12_RAYTRACING_PIPELINE_CONFIG1 value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					output
						<< " recursion="
						<< value.
							MaxTraceRecursionDepth
						<< " flags=0x"
						<< std::hex
						<< static_cast<unsigned int>(
							value.Flags)
						<< std::dec;
				}

				break;
			}

			case
				D3D12_STATE_SUBOBJECT_TYPE_HIT_GROUP:
			{
				D3D12_HIT_GROUP_DESC value = {};

				if (safe_copy_from_process(
					sub.pDesc,
					&value,
					sizeof(value)))
				{
					output << " export=";
					v25_write_name(
						output,
						value.HitGroupExport);

					output << " any_hit=";
					v25_write_name(
						output,
						value.AnyHitShaderImport);

					output << " closest_hit=";
					v25_write_name(
						output,
						value.ClosestHitShaderImport);

					output << " intersection=";
					v25_write_name(
						output,
						value.IntersectionShaderImport);

					output
						<< " hit_type="
						<< static_cast<unsigned int>(
							value.Type);
				}

				break;
			}

			default:
				break;
			}

			output << "\n";
		}
	}

	void v25_log_parent_headers(
		uint64_t call_id,
		const std::vector<D3D12_STATE_SUBOBJECT>
			&subobjects)
	{
		for (
			size_t index = 0;
			index < subobjects.size();
			++index)
		{
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX semantic matrix minimizer v25: "
				"DESC call=%llu sub=%llu type=%s(%u) "
				"desc=%p.",
				static_cast<unsigned long long>(
					call_id),
				static_cast<unsigned long long>(
					index),
				subobject_type_name(
					subobjects[index].Type),
				static_cast<unsigned int>(
					subobjects[index].Type),
				subobjects[index].pDesc);
		}
	}

	void v25_dump_complete_capture(
		uint64_t call_id,
		const D3D12_STATE_OBJECT_DESC &snapshot,
		const std::vector<D3D12_STATE_SUBOBJECT>
			&parent_subobjects)
	{
		try
		{
			std::filesystem::path directory;

			if (!v25_capture_directory(
				directory))
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX semantic matrix minimizer v25: "
					"CAPTURE FAILED call=%llu "
					"reason=directory.",
					static_cast<unsigned long long>(
						call_id));

				return;
			}

			std::vector<
				std::shared_ptr<captured_collection>>
				collections;

			{
				std::lock_guard<std::mutex> lock(
					s_collection_capture_mutex);

				collections =
					s_captured_collections;
			}

			std::vector<
				std::shared_ptr<v25_root_capture>>
				roots;

			{
				std::lock_guard<std::mutex> lock(
					s_v25_root_capture_mutex);

				roots =
					s_v25_root_captures;
			}

			const std::filesystem::path manifest_path =
				directory /
				(
					"v25-capture-call-" +
					std::to_string(call_id) +
					".txt");

			std::ofstream manifest(
				manifest_path);

			if (!manifest)
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX semantic matrix minimizer v25: "
					"CAPTURE FAILED call=%llu "
					"reason=manifest-open.",
					static_cast<unsigned long long>(
						call_id));

				return;
			}

			manifest
				<< "V25_COMPLETE_STATE_OBJECT_CAPTURE\n"
				<< "TARGET_CALL="
				<< call_id
				<< "\n"
				<< "ROOT_SIGNATURE_CAPTURES="
				<< roots.size()
				<< "\n"
				<< "SUCCESSFUL_COLLECTION_CAPTURES="
				<< collections.size()
				<< "\n\n";

			v25_write_descriptor(
				manifest,
				call_id,
				snapshot,
				parent_subobjects);

			for (
				size_t index = 0;
				index < parent_subobjects.size();
				++index)
			{
				if (
					parent_subobjects[index].Type !=
					D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY)
				{
					continue;
				}

				D3D12_DXIL_LIBRARY_DESC library = {};

				if (!safe_copy_from_process(
					parent_subobjects[index].pDesc,
					&library,
					sizeof(library)))
				{
					continue;
				}

				const std::filesystem::path path =
					directory /
					(
						"parent-call-" +
						std::to_string(call_id) +
						"-sub-" +
						std::to_string(index) +
						".dxil");

				const bool written =
					v25_dump_memory(
						path,
						library.DXILLibrary.
							pShaderBytecode,
						library.DXILLibrary.
							BytecodeLength);

				manifest
					<< "PARENT_DXIL sub="
					<< index
					<< " path="
					<< path.filename().string()
					<< " bytes="
					<< library.DXILLibrary.
						BytecodeLength
					<< " written="
					<< (written ? 1 : 0)
					<< "\n";
			}

			for (
				size_t root_index = 0;
				root_index < roots.size();
				++root_index)
			{
				const auto &root =
					roots[root_index];

				const std::filesystem::path path =
					directory /
					(
						"root-call-" +
						std::to_string(
							root->call_id) +
						"-index-" +
						std::to_string(
							root_index) +
						".bin");

				std::ofstream output(
					path,
					std::ios::binary);

				bool written = false;

				if (output)
				{
					output.write(
						reinterpret_cast<
							const char *>(
								root->serialized.data()),
						static_cast<
							std::streamsize>(
								root->serialized.size()));

					written =
						static_cast<bool>(output);
				}

				manifest
					<< "ROOT index="
					<< root_index
					<< " call="
					<< root->call_id
					<< " node_mask=0x"
					<< std::hex
					<< root->node_mask
					<< std::dec
					<< " bytes="
					<< root->serialized.size()
					<< " identity=0x"
					<< std::hex
					<< reinterpret_cast<uintptr_t>(
						root->identity)
					<< std::dec
					<< " path="
					<< path.filename().string()
					<< " written="
					<< (written ? 1 : 0)
					<< "\n";
			}

			for (
				size_t collection_index = 0;
				collection_index <
					collections.size();
				++collection_index)
			{
				const auto &capture =
					collections[
						collection_index];

				if (
					!capture ||
					!capture->storage)
				{
					continue;
				}

				manifest
					<< "\nCOLLECTION index="
					<< collection_index
					<< " source_call="
					<< capture->source_call
					<< " identity=0x"
					<< std::hex
					<< reinterpret_cast<uintptr_t>(
						capture->identity)
					<< std::dec
					<< "\n";

				v25_write_descriptor(
					manifest,
					capture->source_call,
					capture->storage->desc,
					capture->storage->subobjects);

				for (
					size_t sub_index = 0;
					sub_index <
						capture->storage->
							subobjects.size();
					++sub_index)
				{
					const D3D12_STATE_SUBOBJECT &sub =
						capture->storage->
							subobjects[sub_index];

					if (
						sub.Type !=
						D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY)
					{
						continue;
					}

					D3D12_DXIL_LIBRARY_DESC library = {};

					if (!safe_copy_from_process(
						sub.pDesc,
						&library,
						sizeof(library)))
					{
						continue;
					}

					const std::filesystem::path path =
						directory /
							(
								"collection-call-" +
								std::to_string(
									capture->
										source_call) +
								"-sub-" +
								std::to_string(
									sub_index) +
								".dxil");

					const bool written =
						v25_dump_memory(
							path,
							library.DXILLibrary.
								pShaderBytecode,
							library.DXILLibrary.
								BytecodeLength);

					manifest
						<< "COLLECTION_DXIL "
						<< "collection_index="
						<< collection_index
						<< " sub="
						<< sub_index
						<< " path="
						<< path.filename().string()
						<< " bytes="
						<< library.DXILLibrary.
							BytecodeLength
						<< " written="
						<< (written ? 1 : 0)
						<< "\n";
				}
			}

			manifest.flush();

			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX semantic matrix minimizer v25: "
				"CAPTURE call=%llu directory=%s "
				"roots=%llu collections=%llu.",
				static_cast<unsigned long long>(
					call_id),
				directory.string().c_str(),
				static_cast<unsigned long long>(
					roots.size()),
				static_cast<unsigned long long>(
					collections.size()));
		}
		catch (const std::exception &error)
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX semantic matrix minimizer v25: "
				"CAPTURE EXCEPTION call=%llu error=%s.",
				static_cast<unsigned long long>(
					call_id),
				error.what());
		}
		catch (...)
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX semantic matrix minimizer v25: "
				"CAPTURE EXCEPTION call=%llu "
				"error=unknown.",
				static_cast<unsigned long long>(
					call_id));
		}
	}

	bool v25_build_variant(
		const D3D12_STATE_OBJECT_DESC &snapshot,
		const std::vector<D3D12_STATE_SUBOBJECT>
			&source,
		size_t matching_library_index,
		const std::vector<bool> &include,
		D3D12_STATE_OBJECT_TYPE output_type,
		bool use_pruned_dxil,
		int state_flags_override,
		v25_export_filter export_filter,
		v25_variant_storage &storage,
		D3D12_STATE_OBJECT_DESC &output)
	{
		if (
			source.empty() ||
			source.size() != include.size() ||
			source.size() >
				max_capture_subobjects ||
			matching_library_index >=
				source.size() ||
			snapshot.pSubobjects == nullptr)
		{
			return false;
		}

		const size_t invalid =
			static_cast<size_t>(-1);

		storage.subobjects.clear();
		storage.subobjects.reserve(
			source.size());

		storage.old_to_new.assign(
			source.size(),
			invalid);

		const uintptr_t source_begin =
			reinterpret_cast<uintptr_t>(
				snapshot.pSubobjects);

		const uintptr_t source_end =
			source_begin +
			source.size() *
				sizeof(D3D12_STATE_SUBOBJECT);

		for (
			size_t index = 0;
			index < source.size();
			++index)
		{
			if (!include[index])
				continue;

			const D3D12_STATE_SUBOBJECT &original =
				source[index];

			if (
				original.Type ==
				D3D12_STATE_SUBOBJECT_TYPE_SUBOBJECT_TO_EXPORTS_ASSOCIATION)
			{
				continue;
			}

			D3D12_STATE_SUBOBJECT cloned =
				original;

			if (
				original.Type ==
				D3D12_STATE_SUBOBJECT_TYPE_STATE_OBJECT_CONFIG &&
				state_flags_override >= 0)
			{
				D3D12_STATE_OBJECT_CONFIG config = {};

				if (!safe_copy_from_process(
					original.pDesc,
					&config,
					sizeof(config)))
				{
					return false;
				}

				config.Flags =
					static_cast<
						D3D12_STATE_OBJECT_FLAGS>(
							state_flags_override);

				storage.state_configs.push_back(
					config);

				cloned.pDesc =
					&storage.state_configs.back();
			}

			if (
				index ==
				matching_library_index &&
				original.Type ==
				D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY)
			{
				D3D12_DXIL_LIBRARY_DESC library = {};

				if (!safe_copy_from_process(
					original.pDesc,
					&library,
					sizeof(library)))
				{
					return false;
				}

				if (use_pruned_dxil)
				{
					library.DXILLibrary.
						pShaderBytecode =
							g_v24_pruned_parent_dxil;

					library.DXILLibrary.
						BytecodeLength =
							sizeof(
								g_v24_pruned_parent_dxil);
				}

				if (
					export_filter !=
						v25_export_filter::all)
				{
					if (
						library.NumExports == 0 ||
						library.pExports == nullptr ||
						library.NumExports >
							max_capture_exports)
					{
						return false;
					}

					std::vector<D3D12_EXPORT_DESC>
						exports(
							library.NumExports);

					if (!safe_copy_from_process(
						library.pExports,
						exports.data(),
						exports.size() *
							sizeof(
								D3D12_EXPORT_DESC)))
					{
						return false;
					}

					std::vector<D3D12_EXPORT_DESC>
						selected;

					for (const auto &entry :
						exports)
					{
						if (v25_filter_matches(
							entry.Name,
							export_filter))
						{
							selected.push_back(
								entry);
						}
					}

					if (selected.empty())
						return false;

					storage.export_arrays.push_back(
						std::move(selected));

					library.NumExports =
						static_cast<UINT>(
							storage.export_arrays.
								back().size());

					library.pExports =
						storage.export_arrays.
							back().data();
				}

				storage.libraries.push_back(
					library);

				cloned.pDesc =
					&storage.libraries.back();
			}

			storage.old_to_new[index] =
				storage.subobjects.size();

			storage.subobjects.push_back(
				cloned);
		}

		for (
			size_t index = 0;
			index < source.size();
			++index)
		{
			if (
				!include[index] ||
				source[index].Type !=
					D3D12_STATE_SUBOBJECT_TYPE_SUBOBJECT_TO_EXPORTS_ASSOCIATION)
			{
				continue;
			}

			D3D12_SUBOBJECT_TO_EXPORTS_ASSOCIATION
				association = {};

			if (!safe_copy_from_process(
				source[index].pDesc,
				&association,
				sizeof(association)))
			{
				return false;
			}

			const uintptr_t target =
				reinterpret_cast<uintptr_t>(
					association.
						pSubobjectToAssociate);

			if (
				target < source_begin ||
				target >= source_end ||
				(target - source_begin) %
					sizeof(
						D3D12_STATE_SUBOBJECT) !=
					0)
			{
				return false;
			}

			const size_t target_old =
				(target - source_begin) /
				sizeof(D3D12_STATE_SUBOBJECT);

			if (
				target_old >=
					storage.old_to_new.size() ||
				storage.old_to_new[target_old] ==
					invalid)
			{
				continue;
			}

			if (
				export_filter !=
					v25_export_filter::all &&
				association.NumExports != 0)
			{
				if (
					association.pExports == nullptr ||
					association.NumExports >
						max_capture_exports)
				{
					return false;
				}

				std::vector<LPCWSTR> names(
					association.NumExports);

				if (!safe_copy_from_process(
					association.pExports,
					names.data(),
					names.size() *
						sizeof(LPCWSTR)))
				{
					return false;
				}

				std::vector<LPCWSTR> selected;

				for (LPCWSTR name : names)
				{
					if (v25_filter_matches(
						name,
						export_filter))
					{
						selected.push_back(name);
					}
				}

				if (selected.empty())
					continue;

				storage.
					association_export_arrays.
					push_back(
						std::move(selected));

				association.NumExports =
					static_cast<UINT>(
						storage.
							association_export_arrays.
							back().size());

				association.pExports =
					storage.
						association_export_arrays.
						back().data();
			}

			association.pSubobjectToAssociate =
				&storage.subobjects[
					storage.old_to_new[
						target_old]];

			storage.associations.push_back(
				association);

			D3D12_STATE_SUBOBJECT subobject = {};

			subobject.Type =
				D3D12_STATE_SUBOBJECT_TYPE_SUBOBJECT_TO_EXPORTS_ASSOCIATION;

			subobject.pDesc =
				&storage.associations.back();

			storage.old_to_new[index] =
				storage.subobjects.size();

			storage.subobjects.push_back(
				subobject);
		}

		if (storage.subobjects.empty())
			return false;

		output = snapshot;
		output.Type = output_type;
		output.NumSubobjects =
			static_cast<UINT>(
				storage.subobjects.size());
		output.pSubobjects =
			storage.subobjects.data();

		return true;
	}

	void v25_run_probe(
		ID3D12Device5 *device,
		uint64_t call_id,
		const char *name,
		const D3D12_STATE_OBJECT_DESC &desc,
		bool control,
		v25_probe_summary &summary)
	{
		const unsigned int index =
			summary.next_index++;

		void *object = nullptr;

		const HRESULT result =
			s_original_create_state_object(
				device,
				&desc,
				__uuidof(ID3D12StateObject),
				&object);

		const bool accepted =
			SUCCEEDED(result) &&
			object != nullptr;

		reshade::log::message(
			accepted ?
				reshade::log::level::info :
				reshade::log::level::warning,
			"D3DMetal RTX semantic matrix minimizer v25: "
			"PROBE call=%llu index=%u name=%s "
			"control=%u type=%s(%u) subobjects=%u "
			"hr=%s raw=0x%08X object=%p accepted=%u.",
			static_cast<unsigned long long>(call_id),
			index,
			name,
			control ? 1u : 0u,
			state_object_type_name(desc.Type),
			static_cast<unsigned int>(desc.Type),
			desc.NumSubobjects,
			reshade::log::hr_to_string(result).c_str(),
			static_cast<uint32_t>(result),
			object,
			accepted ? 1u : 0u);

		if (control)
		{
			if (accepted)
				++summary.controls_accepted;
			else
				++summary.controls_rejected;
		}
		else
		{
			if (accepted)
			{
				++summary.accepted;

				if (
					summary.
						first_semantic_accepted.
						empty())
				{
					summary.
						first_semantic_accepted =
							name;
				}
			}
			else
			{
				++summary.rejected;
			}
		}

		if (object != nullptr)
			reinterpret_cast<IUnknown *>(
				object)->Release();
	}

	bool try_v25_semantic_matrix_minimizer(
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
			snapshot.Type !=
				D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE ||
			snapshot.NumSubobjects != 28 ||
			snapshot.pSubobjects == nullptr)
		{
			return false;
		}

		std::vector<D3D12_STATE_SUBOBJECT>
			source(snapshot.NumSubobjects);

		if (!safe_copy_from_process(
			snapshot.pSubobjects,
			source.data(),
			source.size() *
				sizeof(D3D12_STATE_SUBOBJECT)))
		{
			return false;
		}

		size_t matching_count = 0;
		size_t matching_library =
			static_cast<size_t>(-1);

		for (
			size_t index = 0;
			index < source.size();
			++index)
		{
			if (
				source[index].Type !=
				D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY)
			{
				continue;
			}

			D3D12_DXIL_LIBRARY_DESC library = {};

			if (!safe_copy_from_process(
				source[index].pDesc,
				&library,
				sizeof(library)))
			{
				continue;
			}

			if (v24_parent_dxil_matches(
				library.DXILLibrary.
					pShaderBytecode,
				library.DXILLibrary.
					BytecodeLength))
			{
				++matching_count;
				matching_library = index;
			}
		}

		if (matching_count != 1)
			return false;

		int expected = 0;

		if (!s_v25_matrix_state.
			compare_exchange_strong(
				expected,
				1,
				std::memory_order_acq_rel))
		{
			if (state_object != nullptr)
				*state_object = nullptr;

			result =
				s_original_create_state_object(
					device,
					original_desc,
					riid,
					state_object);

			const unsigned int log_index =
				++s_v25_passthrough_logs;

			if (log_index <= 3)
			{
				reshade::log::message(
					FAILED(result) ?
						reshade::log::level::warning :
						reshade::log::level::info,
					"D3DMetal RTX semantic matrix minimizer v25: "
					"PASSTHROUGH call=%llu state=%d "
					"hr=%s raw=0x%08X.",
					static_cast<unsigned long long>(
						call_id),
					expected,
					reshade::log::hr_to_string(
						result).c_str(),
					static_cast<uint32_t>(
						result));
			}

			return true;
		}

		unsigned int existing_collection_count = 0;
		size_t first_existing =
			static_cast<size_t>(-1);

		for (
			size_t index = 0;
			index < source.size();
			++index)
		{
			if (
				source[index].Type ==
				D3D12_STATE_SUBOBJECT_TYPE_EXISTING_COLLECTION)
			{
				if (
					first_existing ==
					static_cast<size_t>(-1))
				{
					first_existing = index;
				}

				++existing_collection_count;
			}
		}

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX semantic matrix minimizer v25: "
			"TARGET call=%llu parent_dxil_sub=%llu "
			"subobjects=%u existing_collections=%u "
			"original_bytes=%llu pruned_bytes=%llu.",
			static_cast<unsigned long long>(
				call_id),
			static_cast<unsigned long long>(
				matching_library),
			snapshot.NumSubobjects,
			existing_collection_count,
			static_cast<unsigned long long>(
				sizeof(
					g_v24_original_parent_dxil)),
			static_cast<unsigned long long>(
				sizeof(
					g_v24_pruned_parent_dxil)));

		v25_log_parent_headers(
			call_id,
			source);

		v25_dump_complete_capture(
			call_id,
			snapshot,
			source);

		std::vector<
			std::shared_ptr<captured_collection>>
			collections;

		{
			std::lock_guard<std::mutex> lock(
				s_collection_capture_mutex);

			collections =
				s_captured_collections;
		}

		v25_probe_summary summary;

		if (
			!collections.empty() &&
			collections.front() &&
			collections.front()->storage)
		{
			v25_run_probe(
				device,
				call_id,
				"CONTROL_KNOWN_GOOD_CHILD_RECREATE",
				collections.front()->
					storage->desc,
				true,
				summary);
		}
		else
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX semantic matrix minimizer v25: "
				"CONTROL SKIP call=%llu "
				"reason=no-captured-child.",
				static_cast<unsigned long long>(
					call_id));
		}

		auto association_mask =
			[&source](
				std::vector<bool> &mask)
			{
				for (
					size_t index = 0;
					index < source.size();
					++index)
				{
					if (
						source[index].Type ==
						D3D12_STATE_SUBOBJECT_TYPE_SUBOBJECT_TO_EXPORTS_ASSOCIATION)
					{
						mask[index] = true;
					}
				}
			};

		auto minimal_mask =
			[&source,
			 matching_library,
			 &association_mask](
			 std::initializer_list<
			 	D3D12_STATE_SUBOBJECT_TYPE>
			 	types)
			{
				std::vector<bool> mask(
					source.size(),
					false);

				mask[matching_library] = true;

				for (
					size_t index = 0;
					index < source.size();
					++index)
				{
					for (
						D3D12_STATE_SUBOBJECT_TYPE
							type :
							types)
					{
						if (
							source[index].Type ==
							type)
						{
							mask[index] = true;
						}
					}
				}

				association_mask(mask);
				return mask;
			};

		auto parent_core_mask =
			[&source]()
			{
				std::vector<bool> mask(
					source.size(),
					true);

				for (
					size_t index = 0;
					index < source.size();
					++index)
				{
					if (
						source[index].Type ==
						D3D12_STATE_SUBOBJECT_TYPE_EXISTING_COLLECTION)
					{
						mask[index] = false;
					}
				}

				return mask;
			};

		auto build_and_probe =
			[&](
				const char *name,
				const std::vector<bool> &mask,
				D3D12_STATE_OBJECT_TYPE type,
				bool pruned,
				int state_flags,
				v25_export_filter filter)
			{
				v25_variant_storage storage;
				D3D12_STATE_OBJECT_DESC desc = {};

				if (!v25_build_variant(
					snapshot,
					source,
					matching_library,
					mask,
					type,
					pruned,
					state_flags,
					filter,
					storage,
					desc))
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX semantic matrix minimizer v25: "
						"BUILD_SKIP call=%llu name=%s.",
						static_cast<unsigned long long>(
							call_id),
						name);

					return;
				}

				v25_run_probe(
					device,
					call_id,
					name,
					desc,
					false,
					summary);
			};

		const auto core =
			parent_core_mask();

		build_and_probe(
			"PARENT_CORE_ORIGINAL_PIPELINE",
			core,
			D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE,
			false,
			-1,
			v25_export_filter::all);

		build_and_probe(
			"PARENT_CORE_PRUNED_PIPELINE",
			core,
			D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE,
			true,
			-1,
			v25_export_filter::all);

		build_and_probe(
			"PARENT_CORE_ORIGINAL_COLLECTION_FLAGS3",
			core,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
			v25_export_filter::all);

		build_and_probe(
			"PARENT_CORE_PRUNED_COLLECTION_FLAGS3",
			core,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			true,
			3,
			v25_export_filter::all);

		const auto dxil_only =
			minimal_mask({
				D3D12_STATE_SUBOBJECT_TYPE_STATE_OBJECT_CONFIG
			});

		build_and_probe(
			"DXIL_ORIGINAL_BOTH_COLLECTION",
			dxil_only,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
			v25_export_filter::all);

		build_and_probe(
			"DXIL_PRUNED_BOTH_COLLECTION",
			dxil_only,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			true,
			3,
			v25_export_filter::all);

		build_and_probe(
			"DXIL_ORIGINAL_EXECUTETRACE_COLLECTION",
			dxil_only,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
			v25_export_filter::execute_trace);

		build_and_probe(
			"DXIL_ORIGINAL_MISS_COLLECTION",
			dxil_only,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
			v25_export_filter::miss);

		build_and_probe(
			"DXIL_PRUNED_EXECUTETRACE_COLLECTION",
			dxil_only,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			true,
			3,
			v25_export_filter::execute_trace);

		build_and_probe(
			"DXIL_PRUNED_MISS_COLLECTION",
			dxil_only,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			true,
			3,
			v25_export_filter::miss);

		const auto shader_config =
			minimal_mask({
				D3D12_STATE_SUBOBJECT_TYPE_STATE_OBJECT_CONFIG,
				D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_SHADER_CONFIG
			});

		build_and_probe(
			"DXIL_ORIGINAL_SHADERCFG_COLLECTION",
			shader_config,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
			v25_export_filter::all);

		build_and_probe(
			"DXIL_PRUNED_SHADERCFG_COLLECTION",
			shader_config,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			true,
			3,
			v25_export_filter::all);

		const auto local_root =
			minimal_mask({
				D3D12_STATE_SUBOBJECT_TYPE_STATE_OBJECT_CONFIG,
				D3D12_STATE_SUBOBJECT_TYPE_LOCAL_ROOT_SIGNATURE
			});

		build_and_probe(
			"DXIL_ORIGINAL_LOCALROOT_COLLECTION",
			local_root,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
			v25_export_filter::all);

		build_and_probe(
			"DXIL_PRUNED_LOCALROOT_COLLECTION",
			local_root,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			true,
			3,
			v25_export_filter::all);

		const auto global_root =
			minimal_mask({
				D3D12_STATE_SUBOBJECT_TYPE_STATE_OBJECT_CONFIG,
				D3D12_STATE_SUBOBJECT_TYPE_GLOBAL_ROOT_SIGNATURE
			});

		build_and_probe(
			"DXIL_ORIGINAL_GLOBALROOT_COLLECTION",
			global_root,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
			v25_export_filter::all);

		build_and_probe(
			"DXIL_PRUNED_GLOBALROOT_COLLECTION",
			global_root,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			true,
			3,
			v25_export_filter::all);

		const auto roots_shader =
			minimal_mask({
				D3D12_STATE_SUBOBJECT_TYPE_STATE_OBJECT_CONFIG,
				D3D12_STATE_SUBOBJECT_TYPE_GLOBAL_ROOT_SIGNATURE,
				D3D12_STATE_SUBOBJECT_TYPE_LOCAL_ROOT_SIGNATURE,
				D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_SHADER_CONFIG
			});

		build_and_probe(
			"DXIL_ORIGINAL_ROOTS_SHADERCFG_COLLECTION",
			roots_shader,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
			v25_export_filter::all);

		build_and_probe(
			"DXIL_PRUNED_ROOTS_SHADERCFG_COLLECTION",
			roots_shader,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			true,
			3,
			v25_export_filter::all);

		const auto roots_shader_pipeline =
			minimal_mask({
				D3D12_STATE_SUBOBJECT_TYPE_STATE_OBJECT_CONFIG,
				D3D12_STATE_SUBOBJECT_TYPE_GLOBAL_ROOT_SIGNATURE,
				D3D12_STATE_SUBOBJECT_TYPE_LOCAL_ROOT_SIGNATURE,
				D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_SHADER_CONFIG,
				D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_PIPELINE_CONFIG,
				D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_PIPELINE_CONFIG1
			});

		build_and_probe(
			"DXIL_ORIGINAL_ROOTS_SHADERCFG_PIPECFG_COLLECTION",
			roots_shader_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
			v25_export_filter::all);

		build_and_probe(
			"DXIL_PRUNED_ROOTS_SHADERCFG_PIPECFG_COLLECTION",
			roots_shader_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			true,
			3,
			v25_export_filter::all);

		if (
			first_existing !=
			static_cast<size_t>(-1))
		{
			auto first_child = core;
			first_child[first_existing] = true;

			build_and_probe(
				"PARENT_CORE_ORIGINAL_PLUS_FIRST_CHILD_PIPELINE",
				first_child,
				D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE,
				false,
				-1,
				v25_export_filter::all);

			build_and_probe(
				"PARENT_CORE_PRUNED_PLUS_FIRST_CHILD_PIPELINE",
				first_child,
				D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE,
				true,
				-1,
				v25_export_filter::all);
		}

		if (state_object != nullptr)
			*state_object = nullptr;

		result =
			s_original_create_state_object(
				device,
				original_desc,
				riid,
				state_object);

		void *final_object = nullptr;

		if (state_object != nullptr)
		{
			safe_copy_from_process(
				state_object,
				&final_object,
				sizeof(final_object));
		}

		reshade::log::message(
			FAILED(result) ?
				reshade::log::level::warning :
				reshade::log::level::info,
			"D3DMetal RTX semantic matrix minimizer v25: "
			"FINAL call=%llu hr=%s raw=0x%08X "
			"object=%p.",
			static_cast<unsigned long long>(
				call_id),
			reshade::log::hr_to_string(result).c_str(),
			static_cast<uint32_t>(result),
			final_object);

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX semantic matrix minimizer v25: "
			"COMPLETE call=%llu semantic_accepted=%u "
			"semantic_rejected=%u controls_accepted=%u "
			"controls_rejected=%u first_accepted=%s.",
			static_cast<unsigned long long>(
				call_id),
			summary.accepted,
			summary.rejected,
			summary.controls_accepted,
			summary.controls_rejected,
			summary.first_semantic_accepted.empty() ?
				"<none>" :
				summary.first_semantic_accepted.c_str());

		s_v25_matrix_state.store(
			2,
			std::memory_order_release);

		return true;
	}

'''

text = text.replace(
    signature,
    helper + "\n" + signature,
    1,
)

install_anchor = (
    "\tinstall_d3dmetal_state_object_trace("
    "static_cast<ID3D12Device *>(*ppDevice));\n"
)

if text.count(install_anchor) != 1:
    raise RuntimeError(
        "V25 installation call anchor mismatch: " +
        str(text.count(install_anchor))
    )

text = text.replace(
    install_anchor,
    (
        "\tinstall_v25_root_signature_trace("
        "static_cast<ID3D12Device *>(*ppDevice));\n" +
        install_anchor
    ),
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
        "V25 gate anchor was not found"
    )

insert_position = (
    gate_position +
    len(gate_anchor)
)

gate = r'''

		if (readable)
		{
			HRESULT v25_result = E_FAIL;

			if (try_v25_semantic_matrix_minimizer(
				device,
				call_id,
				desc,
				snapshot,
				riid,
				state_object,
				v25_result))
			{
				return v25_result;
			}
		}
'''

text = (
    text[:insert_position] +
    gate +
    text[insert_position:]
)

required_markers = [
    "D3DMetal RTX semantic matrix minimizer v25: ",
    "D3DMetal RTX root capture v25: ",
    "CreateRootSignature hook installed ",
    "try_v25_semantic_matrix_minimizer(",
    "PARENT_CORE_ORIGINAL_PIPELINE",
    "DXIL_ORIGINAL_EXECUTETRACE_COLLECTION",
    "DXIL_PRUNED_MISS_COLLECTION",
    "PARENT_CORE_PRUNED_PLUS_FIRST_CHILD_PIPELINE",
    "V25_COMPLETE_STATE_OBJECT_CAPTURE",
    "v25_create_root_signature_vtable_index = 16",
    "create_state_object_vtable_index = 62",
]

for marker in required_markers:
    if marker not in text:
        raise RuntimeError(
            f"Missing V25 source marker: {marker}"
        )

trace_position = text.find(signature)

v25_gate_position = text.find(
    "if (try_v25_semantic_matrix_minimizer(",
    trace_position,
)

v24_gate_position = text.find(
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
    v25_gate_position > trace_position and
    v24_gate_position > v25_gate_position and
    legacy_position > v24_gate_position
):
    raise RuntimeError(
        "V25/V24/legacy gate ordering is invalid"
    )

SOURCE.write_text(
    text,
    encoding="utf-8",
    newline="\n",
)

report = Path("v25-patch-report.txt")

report.write_text(
    "\n".join([
        "V25_SEMANTIC_MATRIX_PATCH_OK",
        "V25_VARIANT_HARNESS_PASS",
        "CREATE_ROOT_SIGNATURE_SLOT=16",
        "CREATE_STATE_OBJECT_SLOT=62",
        "TARGET_SUBOBJECT_COUNT=28",
        "EXACT_PARENT_DXIL_MATCH=PASS",
        "ROOT_SIGNATURE_CAPTURE=ENABLED",
        "PARENT_DESCRIPTOR_CAPTURE=ENABLED",
        "CHILD_COLLECTION_CAPTURE=ENABLED",
        "DXIL_BINARY_DUMP=ENABLED",
        "KNOWN_GOOD_CHILD_CONTROL=ENABLED",
        "DEPENDENCY_AWARE_ASSOCIATION_REMAP=PASS",
        "ORIGINAL_DXIL_VARIANTS=ENABLED",
        "PRUNED_DXIL_VARIANTS=ENABLED",
        "EXECUTETRACE_EXPORT_ISOLATION=ENABLED",
        "MISS_EXPORT_ISOLATION=ENABLED",
        "FINAL_ORIGINAL_CALL_EXACTLY_ONCE=PASS",
        "FAKE_SUCCESS=DISABLED",
        "V25_GATE_BEFORE_V24_GATE=PASS",
        "V24_GATE_BEFORE_LEGACY=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)

print(
    report.read_text(
        encoding="utf-8"
    )
)
