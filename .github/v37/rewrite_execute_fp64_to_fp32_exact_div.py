from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

DOUBLE_SCALE = "0x3E70000010000010"  # exact 1 / 16777215 in FP64
FLOAT_DENOMINATOR = "0x416FFFFFE0000000"  # exact FP32 value 16777215.0
ORIGINAL_FLAGS = 65620
FP32_FLAGS = 65552

PATTERN = re.compile(
    r"(?m)^\s*(%\d+) = uitofp i32 (%\d+) to double\n"
    r"\s*(%\d+) = fmul fast double \1, " + re.escape(DOUBLE_SCALE) + r"\n"
    r"\s*(%\d+) = fptrunc double \3 to float$"
)

EXECUTE_FUNCTION = re.compile(
    r'define void @"\\01\?ExecuteTrace@@YAXXZ"\(\) #\d+ \{\n(.*?)\n\}',
    re.DOTALL,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def audit_execute_trace_numbering(text: str, source: Path) -> int:
    match = EXECUTE_FUNCTION.search(text)
    if not match:
        raise RuntimeError(f"{source}: ExecuteTrace body was not found")

    numbers: list[int] = []
    for line in match.group(1).splitlines():
        definition = re.match(r"\s*%(\d+)\s*=", line)
        if definition:
            numbers.append(int(definition.group(1)))
            continue
        label = re.match(r"; <label>:(\d+)", line)
        if label:
            numbers.append(int(label.group(1)))

    if not numbers:
        raise RuntimeError(f"{source}: ExecuteTrace has no numbered SSA values")

    expected = list(range(1, max(numbers) + 1))
    if numbers != expected:
        mismatch = next(
            (index for index, pair in enumerate(zip(numbers, expected)) if pair[0] != pair[1]),
            min(len(numbers), len(expected)),
        )
        actual = numbers[mismatch] if mismatch < len(numbers) else "END"
        wanted = expected[mismatch] if mismatch < len(expected) else "END"
        raise RuntimeError(
            f"{source}: ExecuteTrace SSA numbering broke at position {mismatch}: "
            f"expected %{wanted}, found %{actual}"
        )

    return max(numbers)


def rewrite_module(source: Path, destination: Path) -> dict[str, object]:
    text = source.read_text(encoding="utf-8")
    original = text

    matches = list(PATTERN.finditer(text))
    if len(matches) != 2:
        raise RuntimeError(
            f"{source}: expected exactly 2 FP64 normalization sequences, found {len(matches)}"
        )

    for match in matches:
        first_id = int(match.group(1)[1:])
        middle_id = int(match.group(3)[1:])
        final_id = int(match.group(4)[1:])
        if (middle_id, final_id) != (first_id + 1, first_id + 2):
            raise RuntimeError(
                f"{source}: non-consecutive FP64 SSA IDs: "
                f"%{first_id}, %{middle_id}, %{final_id}"
            )

    def replacement(match: re.Match[str]) -> str:
        first_ssa = match.group(1)
        integer_source = match.group(2)
        middle_ssa = match.group(3)
        final_ssa = match.group(4)
        return (
            f"  {first_ssa} = uitofp i32 {integer_source} to float\n"
            f"  {middle_ssa} = fdiv fast float {first_ssa}, {FLOAT_DENOMINATOR}\n"
            f"  {final_ssa} = fadd fast float {middle_ssa}, 0.000000e+00"
        )

    text, replacement_count = PATTERN.subn(replacement, text)
    if replacement_count != 2:
        raise RuntimeError(
            f"{source}: replaced {replacement_count} FP64 sequences instead of 2"
        )

    old_flag = f"i64 {ORIGINAL_FLAGS}"
    new_flag = f"i64 {FP32_FLAGS}"
    if text.count(old_flag) != 1:
        raise RuntimeError(
            f"{source}: expected one feature mask {ORIGINAL_FLAGS}, found {text.count(old_flag)}"
        )
    text = text.replace(old_flag, new_flag, 1)

    forbidden = [
        " to double",
        "fmul fast double",
        "fptrunc double",
        DOUBLE_SCALE,
        "0x3E70000020000000",
        old_flag,
    ]
    for marker in forbidden:
        if marker in text:
            raise RuntimeError(f"{source}: forbidden marker survived: {marker}")

    required = [
        "ExecuteTrace",
        "dx.op.traceRay",
        FLOAT_DENOMINATOR,
        "fdiv fast float",
        new_flag,
        "fadd fast float",
    ]
    for marker in required:
        if marker not in text:
            raise RuntimeError(f"{source}: required exact-division marker missing: {marker}")

    max_ssa = audit_execute_trace_numbering(text, source)

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
        "identity_instructions_inserted": replacement_count,
        "original_feature_flags": ORIGINAL_FLAGS,
        "rewritten_feature_flags": FP32_FLAGS,
        "fp32_divisor": FLOAT_DENOMINATOR,
        "fp32_operation": "fdiv",
        "contains_miss": "?Miss@@" in text,
        "ssa_numbering_preserved": True,
        "execute_trace_max_ssa": max_ssa,
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
        "V37_FP64_TO_EXACT_FP32_DIVISION_REWRITE",
        "REPLACEMENT=FP32_DIVISION_BY_EXACT_16777215",
        "FLOAT_DENOMINATOR=0x416FFFFFE0000000",
        "RECIPROCAL_MULTIPLICATION=DISABLED",
        "SSA_NUMBERING_AUDIT=PASS",
    ]
    for report in reports:
        manifest.append(
            "MODULE=" + report["destination"] + " " +
            "source_size=" + str(report["source_size"]) + " " +
            "destination_size=" + str(report["destination_size"]) + " " +
            "source_sha256=" + str(report["source_sha256"]) + " " +
            "destination_sha256=" + str(report["destination_sha256"]) + " " +
            "fp64_sequences_replaced=" + str(report["fp64_sequences_replaced"]) + " " +
            "identity_instructions_inserted=" + str(report["identity_instructions_inserted"]) + " " +
            "original_feature_flags=" + str(report["original_feature_flags"]) + " " +
            "rewritten_feature_flags=" + str(report["rewritten_feature_flags"]) + " " +
            "fp32_operation=" + str(report["fp32_operation"]) + " " +
            "fp32_divisor=" + str(report["fp32_divisor"]) + " " +
            "contains_miss=" + str(report["contains_miss"]) + " " +
            "ssa_numbering_preserved=" + str(report["ssa_numbering_preserved"]) + " " +
            "execute_trace_max_ssa=" + str(report["execute_trace_max_ssa"])
        )
    manifest += ["EXACT_DIVISION_REWRITE=PASS", "RESULT=PASS"]

    manifest_path = args.output / "v30-rewrite-manifest.txt"
    manifest_path.write_text("\n".join(manifest) + "\n", encoding="utf-8", newline="\n")
    print(manifest_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
