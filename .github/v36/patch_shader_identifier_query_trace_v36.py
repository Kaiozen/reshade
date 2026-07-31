from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX indirect execution trace v34:" not in text:
    raise RuntimeError("V34 must be applied before V36")
if "D3DMetal RTX shader-identifier query trace v36:" in text:
    raise RuntimeError("V36 is already present")

v32_anchor = "\tstatic std::atomic<unsigned int> s_v32_rewrite_attempts = 0;\n"
if text.count(v32_anchor) != 1:
    raise RuntimeError(f"V36 V32 helper anchor mismatch: {text.count(v32_anchor)}")

helper = r'''
	using v36_get_shader_identifier_fn = void *(STDMETHODCALLTYPE *)(
		ID3D12StateObjectProperties *,
		LPCWSTR);

	constexpr size_t v36_get_shader_identifier_slot = 3;

	static v36_get_shader_identifier_fn s_v36_original_get_shader_identifier = nullptr;
	static std::once_flag s_v36_identifier_hook_once;
	static std::atomic<bool> s_v36_identifier_hook_installed = false;
	static std::atomic<uint64_t> s_v36_identifier_query_total = 0;
	static std::mutex s_v36_properties_mutex;
	static std::unordered_map<void *, uint64_t> s_v36_registered_properties;

	bool v36_copy_export_name(LPCWSTR export_name, char (&ascii)[160])
	{
		ascii[0] = '\0';
		if (export_name == nullptr)
		{
			memcpy(ascii, "NULL", 5);
			return false;
		}

		bool complete = false;
		for (size_t index = 0; index + 1 < sizeof(ascii); ++index)
		{
			wchar_t character = 0;
			if (!safe_copy_from_process(export_name + index, &character, sizeof(character)))
			{
				memcpy(ascii, "UNREADABLE", 11);
				return false;
			}
			if (character == L'\0')
			{
				ascii[index] = '\0';
				complete = true;
				break;
			}
			ascii[index] = character >= 0x20 && character <= 0x7E ?
				static_cast<char>(character) : '?';
		}
		ascii[sizeof(ascii) - 1] = '\0';
		return complete;
	}

	void v36_identifier_to_hex(const void *identifier, char (&hex)[65])
	{
		memset(hex, 0, sizeof(hex));
		if (identifier == nullptr)
		{
			memcpy(hex, "NONE", 5);
			return;
		}

		unsigned char bytes[D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES] = {};
		if (!safe_copy_from_process(identifier, bytes, sizeof(bytes)))
		{
			memcpy(hex, "UNREADABLE", 11);
			return;
		}

		static const char digits[] = "0123456789abcdef";
		for (size_t index = 0; index < D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES; ++index)
		{
			hex[index * 2] = digits[bytes[index] >> 4];
			hex[index * 2 + 1] = digits[bytes[index] & 0x0F];
		}
		hex[64] = '\0';
	}

	void *STDMETHODCALLTYPE v36_trace_get_shader_identifier(
		ID3D12StateObjectProperties *properties,
		LPCWSTR export_name)
	{
		void *identifier = nullptr;
		if (s_v36_original_get_shader_identifier != nullptr)
			identifier = s_v36_original_get_shader_identifier(properties, export_name);

		uint64_t state_call = 0;
		bool registered = false;
		{
			std::lock_guard<std::mutex> lock(s_v36_properties_mutex);
			const auto found = s_v36_registered_properties.find(properties);
			if (found != s_v36_registered_properties.end())
			{
				registered = true;
				state_call = found->second;
			}
		}

		char export_ascii[160] = {};
		v36_copy_export_name(export_name, export_ascii);
		char identifier_hex[65] = {};
		v36_identifier_to_hex(identifier, identifier_hex);

		const uint64_t query_index = ++s_v36_identifier_query_total;
		reshade::log::message(
			registered ? reshade::log::level::info : reshade::log::level::debug,
			"D3DMetal RTX shader-identifier query trace v36: GET_SHADER_IDENTIFIER query_index=%llu registered=%u state_call=%llu properties=%p export=%s present=%u identifier_hex=%s.",
			static_cast<unsigned long long>(query_index),
			registered ? 1u : 0u,
			static_cast<unsigned long long>(state_call),
			properties,
			export_ascii,
			identifier != nullptr ? 1u : 0u,
			identifier_hex);

		return identifier;
	}

	void v36_register_state_object_properties(
		ID3D12StateObjectProperties *properties,
		uint64_t state_call)
	{
		if (properties == nullptr)
			return;

		void **const vtable = *reinterpret_cast<void ***>(properties);
		std::call_once(s_v36_identifier_hook_once, [vtable]()
		{
			void *const current = vtable[v36_get_shader_identifier_slot];
			if (current == reinterpret_cast<void *>(&v36_trace_get_shader_identifier))
			{
				s_v36_identifier_hook_installed.store(true, std::memory_order_release);
				return;
			}

			s_v36_original_get_shader_identifier =
				reinterpret_cast<v36_get_shader_identifier_fn>(current);

			DWORD old_protect = 0;
			bool installed = false;
			if (VirtualProtect(
				&vtable[v36_get_shader_identifier_slot],
				sizeof(void *),
				PAGE_EXECUTE_READWRITE,
				&old_protect))
			{
				InterlockedExchangePointer(
					reinterpret_cast<PVOID volatile *>(
						&vtable[v36_get_shader_identifier_slot]),
					reinterpret_cast<PVOID>(&v36_trace_get_shader_identifier));

				DWORD ignored = 0;
				VirtualProtect(
					&vtable[v36_get_shader_identifier_slot],
					sizeof(void *),
					old_protect,
					&ignored);
				FlushInstructionCache(
					GetCurrentProcess(),
					&vtable[v36_get_shader_identifier_slot],
					sizeof(void *));
				installed =
					vtable[v36_get_shader_identifier_slot] ==
						reinterpret_cast<void *>(&v36_trace_get_shader_identifier);
			}

			s_v36_identifier_hook_installed.store(installed, std::memory_order_release);
			reshade::log::message(
				installed ? reshade::log::level::info : reshade::log::level::warning,
				"D3DMetal RTX shader-identifier query trace v36: IDENTIFIER_HOOK installed=%u slot=%zu original=%p replacement=%p.",
				installed ? 1u : 0u,
				v36_get_shader_identifier_slot,
				reinterpret_cast<void *>(s_v36_original_get_shader_identifier),
				reinterpret_cast<void *>(&v36_trace_get_shader_identifier));

			if (!installed)
				s_v36_original_get_shader_identifier = nullptr;
		});

		{
			std::lock_guard<std::mutex> lock(s_v36_properties_mutex);
			s_v36_registered_properties[properties] = state_call;
		}

		const void *execute_identifier = nullptr;
		const void *sort_identifier = nullptr;
		const void *miss_identifier = nullptr;
		if (s_v36_original_get_shader_identifier != nullptr)
		{
			execute_identifier = s_v36_original_get_shader_identifier(properties, L"ExecuteTrace");
			sort_identifier = s_v36_original_get_shader_identifier(properties, L"ExecuteTrace_SortRay");
			miss_identifier = s_v36_original_get_shader_identifier(properties, L"Miss");
		}

		char execute_hex[65] = {};
		char sort_hex[65] = {};
		char miss_hex[65] = {};
		v36_identifier_to_hex(execute_identifier, execute_hex);
		v36_identifier_to_hex(sort_identifier, sort_hex);
		v36_identifier_to_hex(miss_identifier, miss_hex);

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX shader-identifier query trace v36: PROPERTIES_REGISTER state_call=%llu properties=%p hook=%u probe_execute=%u probe_sort=%u probe_miss=%u execute_hex=%s sort_hex=%s miss_hex=%s.",
			static_cast<unsigned long long>(state_call),
			properties,
			s_v36_identifier_hook_installed.load(std::memory_order_acquire) ? 1u : 0u,
			execute_identifier != nullptr ? 1u : 0u,
			sort_identifier != nullptr ? 1u : 0u,
			miss_identifier != nullptr ? 1u : 0u,
			execute_hex,
			sort_hex,
			miss_hex);
	}

'''

text = text.replace(v32_anchor, helper + "\n" + v32_anchor, 1)

v32_start_marker = "\tbool try_v32_fp32_universal_bridge(\n"
v32_start = text.find(v32_start_marker)
if v32_start < 0:
    raise RuntimeError("V36 could not find try_v32_fp32_universal_bridge")
v32_open = text.find("{", v32_start)
if v32_open < 0:
    raise RuntimeError("V36 could not find V32 opening brace")

depth = 0
v32_end = -1
for position in range(v32_open, len(text)):
    if text[position] == "{":
        depth += 1
    elif text[position] == "}":
        depth -= 1
        if depth == 0:
            v32_end = position + 1
            break
if v32_end < 0:
    raise RuntimeError("V36 could not find V32 closing brace")

v32_function = text[v32_start:v32_end]
old_release = '''\t\t\t\tmiss_present = properties->GetShaderIdentifier(L"Miss") != nullptr;
\t\t\t\tproperties->Release();
'''
new_release = '''\t\t\t\tmiss_present = properties->GetShaderIdentifier(L"Miss") != nullptr;
\t\t\t\tv36_register_state_object_properties(properties, call_id);
\t\t\t\tproperties->Release();
'''
if v32_function.count(old_release) != 1:
    raise RuntimeError(
        f"V36 V32 registration anchor mismatch: {v32_function.count(old_release)}")
v32_function = v32_function.replace(old_release, new_release, 1)
text = text[:v32_start] + v32_function + text[v32_end:]

required = [
    "D3DMetal RTX shader-identifier query trace v36:",
    "IDENTIFIER_HOOK installed=",
    "PROPERTIES_REGISTER state_call=",
    "GET_SHADER_IDENTIFIER query_index=",
    "ExecuteTrace_SortRay",
    "v36_register_state_object_properties(properties, call_id);",
    "v36_get_shader_identifier_slot = 3",
    "identifier_hex=%s",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V36 source marker: {marker}")

if text.count("v36_register_state_object_properties(properties, call_id);") != 1:
    raise RuntimeError("V36 registration was not inserted exactly once")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v36-patch-report.txt")
report.write_text(
    "\n".join([
        "V36_SHADER_IDENTIFIER_QUERY_TRACE_PATCH_OK",
        "V34_INDIRECT_RAY_TRACE_PRESERVED=YES",
        "GET_SHADER_IDENTIFIER_SLOT=3",
        "V32_REWRITTEN_PROPERTIES_REGISTRATION=ENABLED",
        "ALL_IDENTIFIER_NAMES_LOGGED=ENABLED",
        "ALL_IDENTIFIER_RESULTS_LOGGED=ENABLED",
        "EXECUTETRACE_SORTRAY_BASELINE_PROBE=ENABLED",
        "STATE_OBJECT_UNMODIFIED=YES",
        "IDENTIFIER_RESULTS_UNMODIFIED=YES",
        "SHADER_TABLES_UNMODIFIED=YES",
        "DISPATCH_ARGUMENTS_UNMODIFIED=YES",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
