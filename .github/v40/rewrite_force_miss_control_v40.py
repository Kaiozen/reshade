from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--ir-dir", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()

ir_dir = Path(args.ir_dir)
report_path = Path(args.report)

targets = [
    ir_dir / "execute-trace-fp32.ll",
    ir_dir / "execute-plus-miss-fp32.ll",
]

old_fragment = (
    "i32 %400, i32 %399, i32 0, i32 1, i32 0, "
    "float %389, float %390, float %391"
)
new_fragment = (
    "i32 %400, i32 0, i32 0, i32 1, i32 0, "
    "float %389, float %390, float %391"
)

report_lines = [
    "V40_FORCE_MISS_IR_REWRITE",
    "CONTROL=INSTANCE_INCLUSION_MASK_ZERO",
    "TRACE_RAY_INTRINSIC_PRESERVED=YES",
    "RAYGEN_RESOURCE_BINDINGS_PRESERVED=YES",
    "RAYGEN_OUTPUT_STORES_PRESERVED=YES",
    "MISS_SHADER_PRESERVED=YES",
    "HIT_SHADER_EXECUTION_DISABLED_BY_MASK=YES",
]

for path in targets:
    if not path.is_file():
        raise RuntimeError(f"Missing V40 input IR: {path}")

    text = path.read_text(encoding="utf-8")
    trace_lines = [
        line for line in text.splitlines()
        if "call void @dx.op.traceRay.struct.RayIntersection_RT" in line
    ]
    if len(trace_lines) != 1:
        raise RuntimeError(
            f"{path.name}: expected exactly one TraceRay call, found {len(trace_lines)}"
        )

    trace_line = trace_lines[0]
    if old_fragment not in trace_line:
        raise RuntimeError(
            f"{path.name}: expected original TraceRay argument fragment was not found"
        )
    if new_fragment in text:
        raise RuntimeError(f"{path.name}: V40 rewrite appears already applied")

    text = text.replace(old_fragment, new_fragment, 1)

    rewritten_lines = [
        line for line in text.splitlines()
        if "call void @dx.op.traceRay.struct.RayIntersection_RT" in line
    ]
    if len(rewritten_lines) != 1 or new_fragment not in rewritten_lines[0]:
        raise RuntimeError(f"{path.name}: rewritten TraceRay line verification failed")
    if old_fragment in rewritten_lines[0]:
        raise RuntimeError(f"{path.name}: old instance-mask argument remains")

    path.write_text(text, encoding="utf-8", newline="\n")
    report_lines.append(
        f"MODULE={path.name} TRACE_RAY_CALLS=1 INSTANCE_MASK=0 RESULT=PASS"
    )

report_lines += ["RESULT=PASS", ""]
report_path.write_text("\n".join(report_lines), encoding="utf-8", newline="\n")
print(report_path.read_text(encoding="utf-8"))
