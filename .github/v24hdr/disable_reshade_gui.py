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

# Git can materialize this source as LF or CRLF on Windows. HOTFIX1 incorrectly
# matched LF bytes only. HOTFIX2 normalizes a uniform source to LF for semantic
# matching, then restores the original newline convention byte-for-byte style.
crlf_count = payload.count(b"\r\n")
lf_count = payload.count(b"\n")
bare_lf_count = lf_count - crlf_count
if crlf_count and bare_lf_count:
    raise SystemExit(
        f"GOLD15_CONSUMER_RUNTIME_GUI_MIXED_NEWLINES=FAIL crlf={crlf_count} bare_lf={bare_lf_count}"
    )
newline_style = "CRLF" if crlf_count else "LF"

text_original = payload.decode("utf-8")
text = text_original.replace("\r\n", "\n")

# Keep RESHADE_GUI compiled. Only weld shut the two user-facing entry paths.
draw_anchor = """void reshade::runtime::draw_gui()\n{\n\tassert(_is_initialized);\n"""
draw_count = text.count(draw_anchor)
if draw_count != 1:
    raise SystemExit(f"GOLD15_CONSUMER_DRAW_GUI_ANCHOR=FAIL count={draw_count}")

draw_replacement = draw_anchor + """
\t// KAIOZEN GOLD15-CONSUMER: retain ReShade's core/runtime layout, but make its UI inert.
\t// This executes before overlay shortcuts, splash/OSD, ImGui rendering, or input blocking.
\tstatic bool kaiozen_consumer_ui_marker_logged = false;
\tif (!kaiozen_consumer_ui_marker_logged)
\t{
\t\tlog::message(log::level::info, "KAIOZEN GOLD15 CONSUMER: RESHADE_UI_SUPPRESSED");
\t\tkaiozen_consumer_ui_marker_logged = true;
\t}
\t_show_overlay = false;
\t_show_splash = false;
\treturn;
"""
text = text.replace(draw_anchor, draw_replacement, 1)

open_anchor = """bool reshade::runtime::open_overlay(bool open, api::input_source source)\n{\n"""
open_count = text.count(open_anchor)
if open_count != 1:
    raise SystemExit(f"GOLD15_CONSUMER_OPEN_OVERLAY_ANCHOR=FAIL count={open_count}")

open_replacement = open_anchor + """
\t// KAIOZEN GOLD15-CONSUMER: no caller may expose the ReShade configuration UI.
\t(void)open;
\t(void)source;
\t_show_overlay = false;
\treturn false;
"""
text = text.replace(open_anchor, open_replacement, 1)

required = [
    'KAIOZEN GOLD15 CONSUMER: RESHADE_UI_SUPPRESSED',
    '_show_overlay = false;',
    '_show_splash = false;',
    'void reshade::runtime::draw_gui()',
    'bool reshade::runtime::open_overlay(bool open, api::input_source source)',
]
for marker in required:
    if marker not in text:
        raise SystemExit(f"GOLD15_CONSUMER_SILENT_GUI_MARKER_MISSING={marker}")

# Restore exactly one uniform newline convention and original UTF-8 BOM state.
if newline_style == "CRLF":
    serialized = text.replace("\n", "\r\n")
else:
    serialized = text
encoded = serialized.encode("utf-8")
after_raw = (b"\xef\xbb\xbf" + encoded) if bom else encoded
path.write_bytes(after_raw)
after_sha = hashlib.sha256(after_raw).hexdigest()
if before_sha == after_sha:
    raise SystemExit("GOLD15_CONSUMER_RUNTIME_GUI_HASH_UNCHANGED=FAIL")

report = pathlib.Path('gold15-consumer-gui-report.txt')
report.write_text(
    "\n".join([
        "KAIOZEN_GOLD15_CONSUMER_SILENT_GUI_HOTFIX2",
        "CHANGE_SCOPE=SOURCE_RUNTIME_GUI_CPP_ONLY",
        f"SOURCE={path.as_posix()}",
        f"SOURCE_NEWLINE_STYLE={newline_style}",
        f"SOURCE_SHA256_BEFORE={before_sha}",
        f"SOURCE_SHA256_AFTER={after_sha}",
        "RESHADE_GUI_COMPILE_DEFINITION_CHANGED=NO",
        "RESHADE_GUI_CORE_LAYOUT=RETAINED",
        "DRAW_GUI_EARLY_RETURN=YES",
        "OPEN_OVERLAY_FORCED_CLOSED=YES",
        "STARTUP_SPLASH_RENDER_PATH=UNREACHABLE",
        "HOME_OVERLAY_TOGGLE_PATH=UNREACHABLE",
        "HDR_SOURCE_FILES_EDITED=NO",
        "RENODX_SHADER_ASSETS_EDITED=NO",
        "GOLD15_CONSUMER_SILENT_GUI_SOURCE_PATCH=PASS",
        ""
    ]), encoding='utf-8', newline='\n'
)
print(f"GOLD15_CONSUMER_RUNTIME_GUI_NEWLINE_STYLE={newline_style}")
print(f"GOLD15_CONSUMER_RUNTIME_GUI_SHA256_BEFORE={before_sha}")
print(f"GOLD15_CONSUMER_RUNTIME_GUI_SHA256_AFTER={after_sha}")
print("GOLD15_CONSUMER_RESHADE_GUI_COMPILE_DEFINITION=RETAINED")
print("GOLD15_CONSUMER_DRAW_GUI=SUPPRESSED")
print("GOLD15_CONSUMER_OPEN_OVERLAY=FORCED_CLOSED")
print("GOLD15_CONSUMER_SILENT_GUI_SOURCE_PATCH=PASS")
