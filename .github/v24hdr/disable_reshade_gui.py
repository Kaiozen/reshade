#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import pathlib
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("USAGE: disable_reshade_gui.py ReShade.vcxproj")

path = pathlib.Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"GOLD15_CONSUMER_PROJECT_MISSING={path}")

raw = path.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
payload = raw[3:] if bom else raw
text = payload.decode("utf-8")
before_sha = hashlib.sha256(raw).hexdigest()

pattern = re.compile(r"(<PreprocessorDefinitions(?:\s+Condition=\"[^\"]*\")?>)(.*?)(</PreprocessorDefinitions>)", re.DOTALL)
removed = 0
changed_tags = 0

def patch_tag(m: re.Match[str]) -> str:
    global removed, changed_tags
    body = m.group(2)
    parts = body.split(';')
    kept = []
    local_removed = 0
    for part in parts:
        if part.strip() == 'RESHADE_GUI':
            local_removed += 1
        else:
            kept.append(part)
    if local_removed:
        removed += local_removed
        changed_tags += 1
        body = ';'.join(kept)
    return m.group(1) + body + m.group(3)

patched = pattern.sub(patch_tag, text)
if removed < 1:
    raise SystemExit("GOLD15_CONSUMER_RESHADER_GUI_DEFINE_NOT_FOUND=FAIL")

# The x64 Release configuration used for the runtime must exist, and no compile-definition tag may still carry RESHADE_GUI.
if "'$(Configuration)|$(Platform)'=='Release|x64'" not in patched:
    raise SystemExit("GOLD15_CONSUMER_RELEASE_X64_GROUP_NOT_FOUND=FAIL")
for definition in pattern.finditer(patched):
    if re.search(r"(?<![A-Za-z0-9_])RESHADE_GUI(?![A-Za-z0-9_])", definition.group(2)):
        raise SystemExit("GOLD15_CONSUMER_GUI_DEFINE_SURVIVED=FAIL")

# No source file is edited. Only the project compile definition is changed.
encoded = patched.encode("utf-8")
after_raw = (b"\xef\xbb\xbf" + encoded) if bom else encoded
path.write_bytes(after_raw)
after_sha = hashlib.sha256(after_raw).hexdigest()
if before_sha == after_sha:
    raise SystemExit("GOLD15_CONSUMER_PROJECT_HASH_UNCHANGED=FAIL")

report = pathlib.Path('gold15-consumer-gui-report.txt')
report.write_text(
    "\n".join([
        "KAIOZEN_GOLD15_CONSUMER_NO_GUI",
        "CHANGE_SCOPE=RESHADER_PROJECT_PREPROCESSOR_DEFINITION_ONLY",
        f"PROJECT={path.as_posix()}",
        f"PROJECT_SHA256_BEFORE={before_sha}",
        f"PROJECT_SHA256_AFTER={after_sha}",
        f"RESHADE_GUI_TOKENS_REMOVED={removed}",
        f"PREPROCESSOR_TAGS_CHANGED={changed_tags}",
        "RELEASE_X64_RESHADE_GUI=ABSENT",
        "HDR_SOURCE_FILES_EDITED=NO",
        "RENODX_SHADER_ASSETS_EDITED=NO",
        "PROJECT_ENCODING_AND_LINE_ENDINGS=PRESERVED",
        "GOLD15_CONSUMER_GUI_DEFINE_REMOVED=PASS",
        ""
    ]), encoding='utf-8', newline='\n'
)
print(f"GOLD15_CONSUMER_PROJECT_SHA256_BEFORE={before_sha}")
print(f"GOLD15_CONSUMER_PROJECT_SHA256_AFTER={after_sha}")
print(f"GOLD15_CONSUMER_RESHADE_GUI_TOKENS_REMOVED={removed}")
print("GOLD15_CONSUMER_RELEASE_X64_RESHADE_GUI=ABSENT")
print("GOLD15_CONSUMER_GUI_DEFINE_REMOVED=PASS")
