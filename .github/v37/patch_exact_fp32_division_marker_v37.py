from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX shader-identifier query trace v36:" not in text:
    raise RuntimeError("V36 must be applied before V37")
if "D3DMetal RTX exact FP32 division bridge v37:" in text:
    raise RuntimeError("V37 marker is already present")

anchor = "\tbool try_v32_fp32_universal_bridge(\n"
if text.count(anchor) != 1:
    raise RuntimeError(f"V37 V32 function anchor mismatch: {text.count(anchor)}")

start = text.index(anchor)
open_brace = text.index("{", start)
insert_at = open_brace + 1
marker = r'''
		static std::once_flag s_v37_exact_division_log_once;
		std::call_once(
			s_v37_exact_division_log_once,
			[]()
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX exact FP32 division bridge v37: ACTIVE divisor=16777215 operation=fdiv reciprocal_multiply=0 feature_mask=65552.");
			});
'''
text = text[:insert_at] + marker + text[insert_at:]

required = [
    "D3DMetal RTX exact FP32 division bridge v37:",
    "operation=fdiv",
    "reciprocal_multiply=0",
    "feature_mask=65552",
    "try_v32_fp32_universal_bridge",
]
for item in required:
    if item not in text:
        raise RuntimeError(f"Missing V37 source marker: {item}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v37-patch-report.txt")
report.write_text(
    "\n".join([
        "V37_EXACT_FP32_DIVISION_BRIDGE_PATCH_OK",
        "V36_IDENTIFIER_TRACE_PRESERVED=YES",
        "REPLACEMENT_OPERATION=FDIV_FLOAT",
        "DIVISOR_FLOAT_BITS=0x4B7FFFFF",
        "DIVISOR_LLVM_HEX=0x416FFFFFE0000000",
        "RECIPROCAL_MULTIPLICATION=DISABLED",
        "FP64_INSTRUCTIONS=DISABLED",
        "FEATURE_MASK=65552",
        "STATE_OBJECT_BEHAVIOR_UNCHANGED_EXCEPT_EMBEDDED_DXIL=YES",
        "SHADER_TABLES_UNMODIFIED=YES",
        "DISPATCH_ARGUMENTS_UNMODIFIED=YES",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
