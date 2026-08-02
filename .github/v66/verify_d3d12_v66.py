from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
text = SOURCE.read_text(encoding="utf-8")

required = [
    "D3DMetal RTX ray-hit consumer and lighting-history discovery v66",
    "COMMAND_LIST_CONSUMER_HOOKS",
    "WORLD_CONSUMER_FOUND",
    "CONSUMER_OUTPUT",
    "CONSUMER_CANDIDATE",
    "GRAPHICS_CONSUMER_CANDIDATE",
    "MENU_TRANSITION_RESUME",
    "POST_MENU_CONSUMER_RESULT",
    "execute-indirect-compute",
    "direct-compute",
    "normal-menu-gap-threshold-ms=3000",
    "descriptor-scan-limit=96",
    "resource-readback=disabled",
    "resource-barriers=disabled",
    "commands_modified=0",
    "v66_install_command_list_consumer_hooks",
    "v66_observe_consumer_dispatch",
    "v66_note_rewritten_ray_dispatch",
    "D3DMetal RTX AddToStateObject lineage bridge v61",
]
missing = [marker for marker in required if marker not in text]
if missing:
    raise RuntimeError("Missing V66 source markers: " + ", ".join(missing))

for forbidden in [
    "v64_try_capture_timeline(command_list);",
    "D3DMetal RTX u1 target rollover v65: ACTIVE stages=3",
    "v38_install_create_command_queue_hook(device);\n\t\t\t\tv39_install_resource_hooks(device);",
    "functional FP32 forced-miss control v52: ACTIVE",
    "ray-hit output pattern control v53: ACTIVE",
]:
    if forbidden in text:
        raise RuntimeError(f"Forbidden V66 source marker remains: {forbidden}")

if text.count("V66_RAYHIT_CONSUMER_HISTORY_DISCOVERY_PATCH_OK") != 0:
    raise RuntimeError("Patch report marker leaked into C++ source")

print("V66_SOURCE_VERIFICATION_OK")
print("RAYHIT_READBACK=DISABLED")
print("RESOURCE_BARRIERS=DISABLED")
print("DIRECT_COMPUTE_OBSERVER=ENABLED")
print("INDIRECT_COMPUTE_OBSERVER=ENABLED")
print("GRAPHICS_CANDIDATE_OBSERVER=ENABLED")
print("NORMAL_3D_MENU_GAP_THRESHOLD_MS=3000")
print("COMMANDS_MODIFIED=NO")
print("RESULT=PASS")
