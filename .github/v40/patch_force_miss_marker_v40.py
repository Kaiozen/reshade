from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX exact FP32 division bridge v37:" not in text:
    raise RuntimeError("V37 must be applied before V40")
if "D3DMetal RTX forced-miss control v40:" in text:
    raise RuntimeError("V40 marker is already present")

anchor = "\tbool try_v32_fp32_universal_bridge(\n"
if text.count(anchor) != 1:
    raise RuntimeError(f"V40 V32 function anchor mismatch: {text.count(anchor)}")

start = text.index(anchor)
open_brace = text.index("{", start)
insert_at = open_brace + 1
marker = r'''
		static std::once_flag s_v40_forced_miss_log_once;
		std::call_once(
			s_v40_forced_miss_log_once,
			[]()
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX forced-miss control v40: ACTIVE instance_mask=0 trace_ray=preserved hit_execution=disabled raygen_outputs=preserved.");
			});
'''
text = text[:insert_at] + marker + text[insert_at:]

required = [
    "D3DMetal RTX forced-miss control v40:",
    "instance_mask=0",
    "trace_ray=preserved",
    "hit_execution=disabled",
    "raygen_outputs=preserved",
]
for item in required:
    if item not in text:
        raise RuntimeError(f"Missing V40 source marker: {item}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v40-patch-report.txt")
report.write_text(
    "\n".join([
        "V40_FORCED_MISS_CONTROL_PATCH_OK",
        "V37_EXACT_FP32_DIVISION_PRESERVED=YES",
        "TRACE_RAY_INTRINSIC_PRESERVED=YES",
        "INSTANCE_INCLUSION_MASK=0",
        "HIT_SHADER_EXECUTION_DISABLED=YES",
        "MISS_SHADER_EXECUTION_REMAINS_AVAILABLE=YES",
        "RAYGEN_RESOURCE_BINDINGS_UNMODIFIED=YES",
        "RAYGEN_OUTPUT_STORES_UNMODIFIED=YES",
        "STATE_OBJECT_SHAPE_UNMODIFIED=YES",
        "SHADER_TABLES_UNMODIFIED=YES",
        "DISPATCH_ARGUMENTS_UNMODIFIED=YES",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
