from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

OLD_SITE_1 = "%61 = fmul fast float %60, 0x3E70000020000000"
NEW_SITE_1 = "%61 = fdiv float %60, 1.677721500000000e+07"
OLD_SITE_2 = "%229 = fmul fast float %228, 0x3E70000020000000"
NEW_SITE_2 = "%229 = fdiv float %228, 1.677721500000000e+07"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refine(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    before = sha256(path)

    for old, new, label in (
        (OLD_SITE_1, NEW_SITE_1, "uint24 normalization site 1"),
        (OLD_SITE_2, NEW_SITE_2, "uint24 normalization site 2"),
    ):
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{path.name}: {label}: expected one reciprocal multiply, found {count}")
        text = text.replace(old, new, 1)

    if "0x3E70000020000000" in text:
        raise RuntimeError(f"{path.name}: stale reciprocal-multiply constant remains")
    for required in (NEW_SITE_1, NEW_SITE_2):
        if required not in text:
            raise RuntimeError(f"{path.name}: strict FP32 division line is missing: {required}")
    for forbidden in ("to double", "fmul fast double", "fptrunc double"):
        if forbidden in text:
            raise RuntimeError(f"{path.name}: FP64 instruction remains: {forbidden}")

    path.write_text(text, encoding="utf-8", newline="\n")
    return before, sha256(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ir-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    modules = [
        args.ir_dir / "execute-trace-fp32.ll",
        args.ir_dir / "execute-plus-miss-fp32.ll",
    ]
    lines = [
        "V63_STRICT_FP32_UINT24_DIVISION_REFINEMENT_OK",
        "BASE=V30_FP32_RECIPROCAL_MULTIPLY",
        "OLD_OPERATION=fmul_fast_by_nearest_fp32_reciprocal",
        "NEW_OPERATION=fdiv_fp32_by_exact_integer_16777215",
        "FAST_MATH_ON_DIVISION=NO",
        "UINT24_INPUT_EXACTLY_REPRESENTABLE_IN_FP32=YES",
        "NORMALIZATION_SITES_REFINED_PER_MODULE=2",
    ]
    for module in modules:
        if not module.is_file():
            raise RuntimeError(f"Missing generated V30 IR: {module}")
        before, after = refine(module)
        lines.append(
            f"MODULE={module.name} BEFORE_SHA256={before} AFTER_SHA256={after} "
            "SITE1=FP32_DIV SITE2=FP32_DIV"
        )
    lines.append("RESULT=PASS")
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("V63_STRICT_FP32_UINT24_DIVISION_REFINEMENT_OK")


if __name__ == "__main__":
    main()
