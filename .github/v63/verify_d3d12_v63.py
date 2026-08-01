from pathlib import Path

source = Path("source/d3d12/d3d12.cpp").read_text(encoding="utf-8")
patch_report = Path("v63-patch-report.txt").read_text(encoding="utf-8")
normalization_report = Path("v63-normalization-report.txt").read_text(encoding="utf-8")

for marker in [
    "D3DMetal RTX strict FP32 uint24 division v63: ACTIVE",
    "normalization=fdiv-fp32-by-16777215",
    "strict-lineage=v61",
    "v62-forensics=disabled",
    "D3DMetal RTX AddToStateObject lineage bridge v61: REWRITTEN_STEADY_STATE_EXECUTED",
]:
    if marker not in source:
        raise RuntimeError(f"Missing V63 source marker: {marker}")

for forbidden in [
    "v38_install_create_command_queue_hook(device);",
    "v39_install_resource_hooks(device);",
    "v55_install_descriptor_hooks(device);",
    "v57_install_resource_map_hook(resource);",
    "v59_install_resource_unmap_hook(resource);",
    "v62_try_capture_u1_output(command_list);",
    "s_v59_high_frequency_tracking_enabled = true",
]:
    if forbidden in source:
        raise RuntimeError(f"V63 visual build still enables forensic path: {forbidden}")

for marker in [
    "V63_STRICT_FP32_UINT24_DIVISION_VISUAL_PATCH_OK",
    "DXIL_NORMALIZATION=FP32_DIVIDE_BY_EXACT_INTEGER_16777215",
    "V61_STRICT_REWRITTEN_LINEAGE=ENABLED",
    "V62_U1_COPY_READBACK=DISABLED",
    "RESULT=PASS",
]:
    if marker not in patch_report:
        raise RuntimeError(f"Missing V63 patch-report marker: {marker}")

for marker in [
    "V63_STRICT_FP32_UINT24_DIVISION_REFINEMENT_OK",
    "NEW_OPERATION=fdiv_fp32_by_exact_integer_16777215",
    "NORMALIZATION_SITES_REFINED_PER_MODULE=2",
    "RESULT=PASS",
]:
    if marker not in normalization_report:
        raise RuntimeError(f"Missing V63 normalization marker: {marker}")

print("V63_SOURCE_VERIFICATION_OK")
print("NORMALIZATION=FP32_DIVIDE_BY_16777215")
print("STRICT_V61_LINEAGE=ENABLED")
print("V62_FORENSICS=DISABLED")
print("RESULT=PASS")
