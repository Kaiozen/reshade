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

function_signature = 'define void @"\\01?ExecuteTrace@@YAXXZ"() #0 {'

def replace_execute_body(text: str, name: str) -> str:
    start = text.find(function_signature)
    if start < 0:
        raise RuntimeError(f"{name}: ExecuteTrace definition was not found")

    open_brace = text.find("{", start)
    if open_brace < 0:
        raise RuntimeError(f"{name}: ExecuteTrace opening brace was not found")

    depth = 0
    end = -1
    for index in range(open_brace, len(text)):
        character = text[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break

    if end < 0:
        raise RuntimeError(f"{name}: ExecuteTrace closing brace was not found")

    old_body = text[start:end]
    required = [
        "dx.op.traceRay.struct.RayIntersection_RT",
        "dx.op.rawBufferStore.i32",
        "dx.op.dispatchRaysIndex.i32",
        "_RWRayHitBuffer",
    ]
    for marker in required:
        if marker not in old_body:
            raise RuntimeError(f"{name}: original ExecuteTrace body lost marker {marker}")

    replacement = function_signature + "\n  ret void\n}"
    return text[:start] + replacement + text[end:]

report = [
    "V41_NO_OUTPUT_RAYGEN_IR_REWRITE",
    "EXECUTETRACE_BODY=RET_VOID",
    "TRACE_RAY_CALLS=0",
    "SCENE_RESOURCE_READS=0",
    "OUTPUT_UAV_STORES=0",
    "DISPATCH_INDEX_READS=0",
    "MISS_EXPORT_PRESERVED_IN_COMBINED_MODULE=YES",
]

for path in targets:
    if not path.is_file():
        raise RuntimeError(f"Missing V41 input IR: {path}")

    text = path.read_text(encoding="utf-8")
    text = replace_execute_body(text, path.name)

    start = text.find(function_signature)
    end = text.find("\n}", start) + 2
    body = text[start:end]
    if body != function_signature + "\n  ret void\n}":
        raise RuntimeError(f"{path.name}: no-output body verification failed")

    path.write_text(text, encoding="utf-8", newline="\n")
    report.append(f"MODULE={path.name} EXECUTETRACE_RET_VOID=YES RESULT=PASS")

report += ["RESULT=PASS", ""]
report_path.write_text("\n".join(report), encoding="utf-8", newline="\n")
print(report_path.read_text(encoding="utf-8"))
