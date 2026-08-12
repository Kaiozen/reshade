#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import pathlib
import sys

if len(sys.argv) != 2:
    raise SystemExit("USAGE: disable_reshade_gui.py source/runtime_gui.cpp")

path = pathlib.Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"GOLD15_CONSUMER_RUNTIME_GUI_MISSING={path}")

raw = path.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
payload = raw[3:] if bom else raw
before_sha = hashlib.sha256(raw).hexdigest()

crlf_count = payload.count(b"\r\n")
lf_count = payload.count(b"\n")
bare_lf_count = lf_count - crlf_count
if crlf_count and bare_lf_count:
    raise SystemExit(
        f"GOLD15_CONSUMER_RUNTIME_GUI_MIXED_NEWLINES=FAIL crlf={crlf_count} bare_lf={bare_lf_count}"
    )
newline_style = "CRLF" if crlf_count else "LF"
text = payload.decode("utf-8").replace("\r\n", "\n")

# HOTFIX5 is deliberately surgical. Do NOT early-return from draw_gui and do NOT
# replace open_overlay. ReShade's normal per-frame GUI housekeeping stays alive.
# We only suppress the user-visible entry points and splash rendering.

# 1) Default overlay shortcut: Home -> disabled (VK 0).
anchor = "\t_overlay_key_data[0] = 0x24;\n"
if text.count(anchor) != 1:
    raise SystemExit(f"GOLD15_CONSUMER_HOME_DEFAULT_ANCHOR=FAIL count={text.count(anchor)}")
text = text.replace(anchor, "\t_overlay_key_data[0] = 0x00;\n", 1)

# Add one binary/log marker in init_gui without changing control flow.
marker_anchor = "\t_overlay_key_data[3] = false;\n"
if text.count(marker_anchor) != 1:
    raise SystemExit(f"GOLD15_CONSUMER_INIT_GUI_MARKER_ANCHOR=FAIL count={text.count(marker_anchor)}")
text = text.replace(
    marker_anchor,
    marker_anchor + '\tlog::message(log::level::info, "KAIOZEN GOLD15 CONSUMER: SURGICAL_UI_LOCK");\n',
    1,
)

# 2) Ignore any old ReShade.ini trying to restore Home (or modifiers).
load_key_anchor = '\tconfig_get("INPUT", "KeyOverlay", _overlay_key_data);\n'
if text.count(load_key_anchor) != 1:
    raise SystemExit(f"GOLD15_CONSUMER_LOAD_KEY_ANCHOR=FAIL count={text.count(load_key_anchor)}")
text = text.replace(
    load_key_anchor,
    load_key_anchor
    + "\t_overlay_key_data[0] = 0;\n"
    + "\t_overlay_key_data[1] = false;\n"
    + "\t_overlay_key_data[2] = false;\n"
    + "\t_overlay_key_data[3] = false;\n",
    1,
)

# 3) Treat tutorial as already completed after config/global config is loaded.
tutorial_anchor = (
    '\tif (!global_config().get("OVERLAY", "TutorialProgress", _tutorial_index))\n'
    '\t\tconfig.get("OVERLAY", "TutorialProgress", _tutorial_index);\n'
)
if text.count(tutorial_anchor) != 1:
    raise SystemExit(f"GOLD15_CONSUMER_TUTORIAL_ANCHOR=FAIL count={text.count(tutorial_anchor)}")
text = text.replace(tutorial_anchor, tutorial_anchor + "\t_tutorial_index = 4;\n", 1)

# 4) Keep draw_gui running, but force every overlay request closed before it can open.
overlay_gate_anchor = "\tif (show_overlay != _show_overlay)\n\t\topen_overlay(show_overlay, show_overlay_source);\n"
if text.count(overlay_gate_anchor) != 1:
    raise SystemExit(f"GOLD15_CONSUMER_OVERLAY_GATE_ANCHOR=FAIL count={text.count(overlay_gate_anchor)}")
text = text.replace(
    overlay_gate_anchor,
    "\t// KAIOZEN GOLD15-CONSUMER: configuration overlay is not exposed in the consumer build.\n"
    "\tshow_overlay = false;\n"
    "\t_show_overlay = false;\n"
    + overlay_gate_anchor,
    1,
)

# 5) Suppress only the top Splash Window. The rest of draw_gui remains untouched.
splash_anchor = (
    "\tconst bool show_splash_window = _show_splash && (is_loading() || "
    "(_reload_count <= 1 && (_last_present_time - _last_reload_time) < std::chrono::seconds(5)) || "
    "(!_show_overlay && _tutorial_index == 0 && _input != nullptr));\n"
)
if text.count(splash_anchor) != 1:
    raise SystemExit(f"GOLD15_CONSUMER_SPLASH_ANCHOR=FAIL count={text.count(splash_anchor)}")
text = text.replace(splash_anchor, "\tconst bool show_splash_window = false;\n", 1)

# Guard against accidentally reintroducing the failed HOTFIX2 strategy.
for forbidden in [
    "KAIOZEN GOLD15 CONSUMER: RESHADE_UI_SUPPRESSED",
    "return;\n\t_show_overlay = false;",
    "OPEN_OVERLAY_FORCED_CLOSED=YES",
]:
    if forbidden in text:
        raise SystemExit(f"GOLD15_CONSUMER_FORBIDDEN_OLD_STRATEGY_PRESENT={forbidden}")

required = [
    "KAIOZEN GOLD15 CONSUMER: SURGICAL_UI_LOCK",
    "_overlay_key_data[0] = 0x00;",
    "_tutorial_index = 4;",
    "show_overlay = false;",
    "const bool show_splash_window = false;",
    "void reshade::runtime::draw_gui()",
    "bool reshade::runtime::open_overlay(bool open, api::input_source source)",
]
for marker in required:
    if marker not in text:
        raise SystemExit(f"GOLD15_CONSUMER_SURGICAL_UI_MARKER_MISSING={marker}")

serialized = text.replace("\n", "\r\n") if newline_style == "CRLF" else text
encoded = serialized.encode("utf-8")
after_raw = (b"\xef\xbb\xbf" + encoded) if bom else encoded
path.write_bytes(after_raw)
after_sha = hashlib.sha256(after_raw).hexdigest()
if before_sha == after_sha:
    raise SystemExit("GOLD15_CONSUMER_RUNTIME_GUI_HASH_UNCHANGED=FAIL")

report = pathlib.Path("gold15-consumer-gui-report.txt")
report.write_text(
    "\n".join([
        "KAIOZEN_GOLD15_CONSUMER_SURGICAL_UI_HOTFIX5",
        "CHANGE_SCOPE=SOURCE_RUNTIME_GUI_CPP_ONLY",
        f"SOURCE={path.as_posix()}",
        f"SOURCE_NEWLINE_STYLE={newline_style}",
        f"SOURCE_SHA256_BEFORE={before_sha}",
        f"SOURCE_SHA256_AFTER={after_sha}",
        "RESHADE_GUI_COMPILE_DEFINITION_CHANGED=NO",
        "RESHADE_GUI_CORE_LAYOUT=RETAINED",
        "DRAW_GUI_EARLY_RETURN=NO",
        "DRAW_GUI_NORMAL_HOUSEKEEPING=RETAINED",
        "OPEN_OVERLAY_FUNCTION_REPLACED=NO",
        "HOME_DEFAULT_KEY=DISABLED",
        "CONFIG_OVERLAY_KEY=FORCED_DISABLED",
        "TUTORIAL_PROGRESS=FORCED_COMPLETE_4",
        "STARTUP_SPLASH_RENDER=FORCED_FALSE",
        "OVERLAY_VISIBILITY=FORCED_FALSE_PER_FRAME",
        "HDR_SOURCE_FILES_EDITED=NO",
        "RENODX_SHADER_ASSETS_EDITED=NO",
        "GOLD15_CONSUMER_SURGICAL_UI_SOURCE_PATCH=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)

print(f"GOLD15_CONSUMER_RUNTIME_GUI_NEWLINE_STYLE={newline_style}")
print(f"GOLD15_CONSUMER_RUNTIME_GUI_SHA256_BEFORE={before_sha}")
print(f"GOLD15_CONSUMER_RUNTIME_GUI_SHA256_AFTER={after_sha}")
print("GOLD15_CONSUMER_DRAW_GUI_NORMAL_HOUSEKEEPING=RETAINED")
print("GOLD15_CONSUMER_HOME_KEY=DISABLED")
print("GOLD15_CONSUMER_TUTORIAL=FORCED_COMPLETE")
print("GOLD15_CONSUMER_SPLASH=FORCED_OFF")
print("GOLD15_CONSUMER_OVERLAY=FORCED_HIDDEN")
print("GOLD15_CONSUMER_SURGICAL_UI_SOURCE_PATCH=PASS")
