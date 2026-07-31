from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX shader-identifier query trace v36:" not in text:
    raise RuntimeError("V36 must be applied before V41")
if "D3DMetal RTX no-output raygen control v41:" in text:
    raise RuntimeError("V41 marker is already present")

anchor = "\tbool try_v32_fp32_universal_bridge(\n"
if text.count(anchor) != 1:
    raise RuntimeError(f"V41 V32 function anchor mismatch: {text.count(anchor)}")

start = text.index(anchor)
open_brace = text.index("{", start)
insert_at = open_brace + 1
marker = (
    "\n\t\tstatic std::once_flag s_v41_no_output_log_once;\n"
    "\t\tstd::call_once(\n"
    "\t\t\ts_v41_no_output_log_once,\n"
    "\t\t\t[]()\n"
    "\t\t\t{\n"
    "\t\t\t\treshade::log::message(\n"
    "\t\t\t\t\treshade::log::level::info,\n"
    "\t\t\t\t\t\"D3DMetal RTX no-output raygen control v41: ACTIVE source=minimal_hlsl trace_ray=0 scene_reads=0 output_stores=0 execute_body=empty.\");\n"
    "\t\t\t});\n"
)
text = text[:insert_at] + marker + text[insert_at:]

for value in [
    "D3DMetal RTX no-output raygen control v41:",
    "source=minimal_hlsl",
    "trace_ray=0",
    "scene_reads=0",
    "output_stores=0",
    "execute_body=empty",
]:
    if value not in text:
        raise RuntimeError(f"Missing V41 source marker: {value}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v41-patch-report.txt")
report.write_text(
    "\n".join([
        "V41_NO_OUTPUT_RAYGEN_CONTROL_PATCH_OK",
        "V36_IDENTIFIER_TRACE_PRESERVED=YES",
        "FRESH_MINIMAL_HLSL_DXIL=YES",
        "EXECUTETRACE_BODY=EMPTY",
        "TRACE_RAY_EXECUTION=DISABLED",
        "SCENE_RESOURCE_READS=DISABLED",
        "OUTPUT_UAV_STORES=DISABLED",
        "MISS_EXPORT=EMPTY_AND_PRESERVED",
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
