#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("USAGE: disable_reshade_gui.py source/runtime_gui.cpp source/runtime.cpp")

gui_path = pathlib.Path(sys.argv[1])
runtime_path = pathlib.Path(sys.argv[2])
for p in (gui_path, runtime_path):
    if not p.is_file():
        raise SystemExit(f"GOLD15_PORTABLE_SOURCE_MISSING={p}")

def load(path: pathlib.Path):
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    payload = raw[3:] if bom else raw
    crlf = payload.count(b"\r\n")
    lf = payload.count(b"\n")
    bare = lf - crlf
    if crlf and bare:
        raise SystemExit(f"GOLD15_PORTABLE_MIXED_NEWLINES=FAIL source={path}")
    style = "CRLF" if crlf else "LF"
    text = payload.decode("utf-8").replace("\r\n", "\n")
    return raw, bom, style, text

def save(path: pathlib.Path, bom: bool, style: str, text: str):
    serialized = text.replace("\n", "\r\n") if style == "CRLF" else text
    encoded = serialized.encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" + encoded) if bom else encoded)

gui_raw, gui_bom, gui_style, gui = load(gui_path)
runtime_raw, runtime_bom, runtime_style, runtime = load(runtime_path)
gui_before = hashlib.sha256(gui_raw).hexdigest()
runtime_before = hashlib.sha256(runtime_raw).hexdigest()

# Keep ReShade's GUI machinery and draw_gui housekeeping fully alive.
# Only user-facing startup policy changes.

# Emergency overlay key: Ctrl + Shift + F12 (VK_F12 = 0x7B).
default_block = (
    "\t_overlay_key_data[0] = 0x24;\n"
    "\t_overlay_key_data[1] = false;\n"
    "\t_overlay_key_data[2] = false;\n"
    "\t_overlay_key_data[3] = false;\n"
)
portable_block = (
    "\t_overlay_key_data[0] = 0x7B;\n"
    "\t_overlay_key_data[1] = true;\n"
    "\t_overlay_key_data[2] = true;\n"
    "\t_overlay_key_data[3] = false;\n"
    '\tlog::message(log::level::info, "KAIOZEN GOLD15 PORTABLE: UI_POLICY_ACTIVE");\n'
)
if gui.count(default_block) != 1:
    raise SystemExit(f"GOLD15_PORTABLE_DEFAULT_KEY_ANCHOR=FAIL count={gui.count(default_block)}")
gui = gui.replace(default_block, portable_block, 1)

load_key = '\tconfig_get("INPUT", "KeyOverlay", _overlay_key_data);\n'
if gui.count(load_key) != 1:
    raise SystemExit(f"GOLD15_PORTABLE_LOAD_KEY_ANCHOR=FAIL count={gui.count(load_key)}")
gui = gui.replace(
    load_key,
    load_key
    + "\t_overlay_key_data[0] = 0x7B;\n"
    + "\t_overlay_key_data[1] = true;\n"
    + "\t_overlay_key_data[2] = true;\n"
    + "\t_overlay_key_data[3] = false;\n",
    1,
)

tutorial = (
    '\tif (!global_config().get("OVERLAY", "TutorialProgress", _tutorial_index))\n'
    '\t\tconfig.get("OVERLAY", "TutorialProgress", _tutorial_index);\n'
)
if gui.count(tutorial) != 1:
    raise SystemExit(f"GOLD15_PORTABLE_TUTORIAL_ANCHOR=FAIL count={gui.count(tutorial)}")
gui = gui.replace(tutorial, tutorial + "\t_tutorial_index = 4;\n", 1)

splash = (
    "\tconst bool show_splash_window = _show_splash && (is_loading() || "
    "(_reload_count <= 1 && (_last_present_time - _last_reload_time) < std::chrono::seconds(5)) || "
    "(!_show_overlay && _tutorial_index == 0 && _input != nullptr));\n"
)
if gui.count(splash) != 1:
    raise SystemExit(f"GOLD15_PORTABLE_SPLASH_ANCHOR=FAIL count={gui.count(splash)}")
gui = gui.replace(splash, "\tconst bool show_splash_window = false;\n", 1)

# Disable ReShade's network update request at its constructor call site.
update = "\tcheck_for_update();\n"
if runtime.count(update) != 1:
    raise SystemExit(f"GOLD15_PORTABLE_UPDATE_CHECK_ANCHOR=FAIL count={runtime.count(update)}")
runtime = runtime.replace(
    update,
    '\tlog::message(log::level::info, "KAIOZEN GOLD15 PORTABLE: UPDATE_CHECK_DISABLED");\n',
    1,
)

# Explicitly forbid the previous overlay-killing strategies.
for forbidden in [
    "show_overlay = false;\n\t_show_overlay = false;",
    "KAIOZEN GOLD15 CONSUMER: RESHADE_UI_SUPPRESSED",
]:
    if forbidden in gui:
        raise SystemExit(f"GOLD15_PORTABLE_FORBIDDEN_GUI_STRATEGY={forbidden}")

required_gui = [
    "KAIOZEN GOLD15 PORTABLE: UI_POLICY_ACTIVE",
    "_overlay_key_data[0] = 0x7B;",
    "_overlay_key_data[1] = true;",
    "_overlay_key_data[2] = true;",
    "_tutorial_index = 4;",
    "const bool show_splash_window = false;",
    "void reshade::runtime::draw_gui()",
    "bool reshade::runtime::open_overlay(bool open, api::input_source source)",
]
for marker in required_gui:
    if marker not in gui:
        raise SystemExit(f"GOLD15_PORTABLE_GUI_MARKER_MISSING={marker}")

if "check_for_update();" in runtime:
    raise SystemExit("GOLD15_PORTABLE_UPDATE_CHECK_SURVIVED=FAIL")
if "KAIOZEN GOLD15 PORTABLE: UPDATE_CHECK_DISABLED" not in runtime:
    raise SystemExit("GOLD15_PORTABLE_UPDATE_MARKER_MISSING=FAIL")

save(gui_path, gui_bom, gui_style, gui)
save(runtime_path, runtime_bom, runtime_style, runtime)
gui_after = hashlib.sha256(gui_path.read_bytes()).hexdigest()
runtime_after = hashlib.sha256(runtime_path.read_bytes()).hexdigest()

report = pathlib.Path("gold15-consumer-gui-report.txt")
report.write_text(
    "\n".join([
        "KAIOZEN_GOLD15_PORTABLE_UI_POLICY_HOTFIX1",
        "CHANGE_SCOPE=RUNTIME_GUI_POLICY_PLUS_UPDATE_CALLSITE",
        f"RUNTIME_GUI_NEWLINE_STYLE={gui_style}",
        f"RUNTIME_NEWLINE_STYLE={runtime_style}",
        f"RUNTIME_GUI_SHA256_BEFORE={gui_before}",
        f"RUNTIME_GUI_SHA256_AFTER={gui_after}",
        f"RUNTIME_SHA256_BEFORE={runtime_before}",
        f"RUNTIME_SHA256_AFTER={runtime_after}",
        "RESHADE_GUI_COMPILE_DEFINITION_CHANGED=NO",
        "DRAW_GUI_EARLY_RETURN=NO",
        "DRAW_GUI_NORMAL_HOUSEKEEPING=RETAINED",
        "OPEN_OVERLAY_FUNCTION_REPLACED=NO",
        "OVERLAY_EMERGENCY_KEY=CTRL_SHIFT_F12",
        "TUTORIAL_PROGRESS=FORCED_COMPLETE_4",
        "STARTUP_SPLASH_RENDER=FORCED_FALSE",
        "UPDATE_CHECK=COMPILED_OUT_AT_CALLSITE",
        "OVERLAY_VISIBILITY=USER_TOGGLE_RETAINED",
        "GOLD15_PORTABLE_UI_POLICY_SOURCE_PATCH=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)

print(f"GOLD15_PORTABLE_RUNTIME_GUI_NEWLINE_STYLE={gui_style}")
print(f"GOLD15_PORTABLE_RUNTIME_NEWLINE_STYLE={runtime_style}")
print("GOLD15_PORTABLE_DRAW_GUI_HOUSEKEEPING=RETAINED")
print("GOLD15_PORTABLE_OVERLAY_KEY=CTRL_SHIFT_F12")
print("GOLD15_PORTABLE_TUTORIAL=FORCED_COMPLETE")
print("GOLD15_PORTABLE_SPLASH=FORCED_OFF")
print("GOLD15_PORTABLE_UPDATE_CHECK=DISABLED")
print("GOLD15_PORTABLE_UI_POLICY_SOURCE_PATCH=PASS")
