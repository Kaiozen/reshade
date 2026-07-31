from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

DOUBLE_SCALE = "0x3E70000010000010"  # exact 1.0 / 16777215.0 in FP64
FLOAT_SCALE = "0x3E70000020000000"   # nearest FP32 value, written in LLVM hex-float form
ORIGINAL_FLAGS = 65620
FP32_FLAGS = 65552  # remove FP64 + FP64-extension bits (68), preserve all other requirements

PATTERNS = [
    re.compile(
        r"(?m)^\s*(%\d+) = uitofp i32 (%\d+) to double\n"
        r"\s*(%\d+) = fmul fast double \1, " + re.escape(DOUBLE_SCALE) + r"\n"
        r"\s*(%\d+) = fptrunc double \3 to float$"
    ),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rewrite_module(source: Path, destination: Path) -> dict[str, object]:
    text = source.read_text(encoding="utf-8")
    original = text

    matches = list(PATTERNS[0].finditer(text))
    if len(matches) != 2:
        raise RuntimeError(f"{source}: expected exactly 2 FP64 normalize sequences, found {len(matches)}")

    def repl(match: re.Match[str]) -> str:
        int_to_double_ssa = match.group(1)
        integer_source_ssa = match.group(2)
        final_float_ssa = match.group(4)
        indent = "  "
        return (
            f"{indent}{int_to_double_ssa} = uitofp i32 {integer_source_ssa} to float\n"
            f"{indent}{final_float_ssa} = fmul fast float {int_to_double_ssa}, {FLOAT_SCALE}"
        )

    text, replacement_count = PATTERNS[0].subn(repl, text)
    if replacement_count != 2:
        raise RuntimeError(f"{source}: replaced {replacement_count} FP64 sequences instead of 2")

    old_flag = f"i64 {ORIGINAL_FLAGS}"
    new_flag = f"i64 {FP32_FLAGS}"
    flag_count = text.count(old_flag)
    if flag_count != 1:
        raise RuntimeError(f"{source}: expected one shader-feature mask {ORIGINAL_FLAGS}, found {flag_count}")
    text = text.replace(old_flag, new_flag, 1)

    forbidden = [
        " to double",
        "fmul fast double",
        "fptrunc double",
        DOUBLE_SCALE,
        old_flag,
    ]
    for marker in forbidden:
        if marker in text:
            raise RuntimeError(f"{source}: forbidden FP64 marker survived: {marker}")

    required = [
        "ExecuteTrace",
        "dx.op.traceRay",
        FLOAT_SCALE,
        new_flag,
    ]
    for marker in required:
        if marker not in text:
            raise RuntimeError(f"{source}: required rewritten marker missing: {marker}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8", newline="\n")

    return {
        "source": source.name,
        "destination": destination.name,
        "source_size": len(original.encode("utf-8")),
        "destination_size": destination.stat().st_size,
        "source_sha256": sha256(original.encode("utf-8")),
        "destination_sha256": sha256(destination.read_bytes()),
        "fp64_sequences_replaced": replacement_count,
        "original_feature_flags": ORIGINAL_FLAGS,
        "rewritten_feature_flags": FP32_FLAGS,
        "float_scale": FLOAT_SCALE,
        "contains_miss": "?Miss@@" in text,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", type=Path, required=True)
    parser.add_argument("--combined", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    reports = [
        rewrite_module(args.execute, args.output / "execute-trace-fp32.ll"),
        rewrite_module(args.combined, args.output / "execute-plus-miss-fp32.ll"),
    ]

    manifest = [
        "V30_FP64_TO_FP32_IR_REWRITE",
        "REPLACEMENT=uint24_to_float_then_multiply_by_nearest_fp32_reciprocal",
        f"FP64_SCALE={DOUBLE_SCALE}",
        f"FP32_SCALE={FLOAT_SCALE}",
        f"ORIGINAL_FEATURE_FLAGS={ORIGINAL_FLAGS}",
        f"REWRITTEN_FEATURE_FLAGS={FP32_FLAGS}",
    ]
    for report in reports:
        manifest.append("MODULE=" + " ".join(f"{key}={value}" for key, value in report.items()))
    manifest.append("RESULT=PASS")
    (args.output / "v30-rewrite-manifest.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print("\n".join(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
