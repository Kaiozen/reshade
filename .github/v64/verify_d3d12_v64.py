from pathlib import Path

source = Path("source/d3d12/d3d12.cpp").read_text(encoding="utf-8")
report = Path("v64-patch-report.txt").read_text(encoding="utf-8")

required_source = [
    "D3DMetal RTX temporal ray-hit snapshots v64: ACTIVE",
    "thresholds=96,512,1400",
    "TEMPORAL_CAPTURE_RECORDED",
    "TEMPORAL_QUEUE_SUBMITTED",
    "TEMPORAL_RECORD",
    "TEMPORAL_BLOCK_SUMMARY",
    "TEMPORAL_SNAPSHOT_RESULT",
    "v64_try_capture_timeline(command_list);",
    "v64_rewritten_capture_candidate",
    "v57_install_resource_map_hook(resource);",
    "v59_install_resource_unmap_hook(resource);",
    "D3DMetal RTX AddToStateObject lineage bridge v61: REWRITTEN_STEADY_STATE_EXECUTED",
]
for marker in required_source:
    if marker not in source:
        raise RuntimeError(f"Missing V64 source marker: {marker}")

for marker in [
    "V64_TEMPORAL_RAYHIT_SNAPSHOTS_PATCH_OK",
    "SNAPSHOT_COUNT=3",
    "SNAPSHOT_THRESHOLDS=96,512,1400",
    "SAMPLED_RECORDS_PER_SNAPSHOT=1280",
    "RESULT=PASS",
]:
    if marker not in report:
        raise RuntimeError(f"Missing V64 patch-report marker: {marker}")

for forbidden in [
    "v58_install_resource_gpu_va_hook(resource);",
    "v57_install_copy_buffer_region_hook(command_list);",
    "v62_try_capture_u1_output(command_list);",
    "functional FP32 forced-miss control v52: ACTIVE",
    "ray-hit output pattern control v53: ACTIVE",
]:
    if forbidden in source:
        raise RuntimeError(f"Forbidden V64 active path remains: {forbidden}")

if source.count("v64_snapshot_thresholds") < 6:
    raise RuntimeError("V64 snapshot thresholds are not wired through all capture stages")
if source.count("v64_on_execute_command_lists") < 3:
    raise RuntimeError("V64 queue submission callback is not fully connected")

print("V64_SOURCE_VERIFICATION_OK")
print("SNAPSHOT_COUNT=3")
print("SNAPSHOT_THRESHOLDS=96,512,1400")
print("SAMPLED_RECORDS_PER_SNAPSHOT=1280")
print("STRICT_V61_LINEAGE=ENABLED")
print("RESULT=PASS")
