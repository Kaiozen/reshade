from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
text = SOURCE.read_text(encoding="utf-8")

required = [
    "D3DMetal RTX u1 target rollover v65",
    "U1_TARGET_GENERATION",
    "U1_REFRESH_RESULT",
    "PIPELINE_ROLLOVER",
    "STALE_TARGET_REJECTED",
    "ROLLOVER_CAPTURE_RECORDED",
    "ROLLOVER_QUEUE_SUBMITTED",
    "ROLLOVER_SNAPSHOT_RESULT",
    "initial-thresholds=96,512 rollover-threshold=64",
    "s_v65_u1_target_generation",
    "s_v65_initial_pipeline_id",
    "v65_refresh_current_u1_target",
    "pipeline_id != initial_pipeline_id",
    "current_generation != target_generation",
    "D3DMetal RTX AddToStateObject lineage bridge v61",
]

missing = [marker for marker in required if marker not in text]
if missing:
    raise RuntimeError("Missing V65 source markers: " + ", ".join(missing))

for forbidden in [
    "ACTIVE stages=3 thresholds=96,512,1400",
    "functional FP32 forced-miss control v52: ACTIVE",
    "ray-hit output pattern control v53: ACTIVE",
]:
    if forbidden in text:
        raise RuntimeError(f"Forbidden V65 source marker remains: {forbidden}")

if text.count("V65_U1_TARGET_ROLLOVER_PATCH_OK") != 0:
    raise RuntimeError("Patch report marker leaked into C++ source")

print("V65_SOURCE_VERIFICATION_OK")
print("INITIAL_WORLD_SNAPSHOT_THRESHOLDS=96,512")
print("POST_ROLLOVER_THRESHOLD=64")
print("TARGET_GENERATION_TRACKING=ENABLED")
print("PIPELINE_ROLLOVER_REFRESH=ENABLED")
print("STALE_TARGET_REJECTION=ENABLED")
print("RESULT=PASS")
