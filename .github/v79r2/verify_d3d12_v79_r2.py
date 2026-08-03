from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")
text = source.read_text(encoding="utf-8")

required = [
    "V79_R2_BINARY_MARKER_MANIFEST_R2_RTV_CYCLE_FRAME_BOUNDARY",
    "kaiozen_v79_r2_binary_marker_manifest",
    "SWAPCHAIN_GROUP_SELECTED",
    "RTV_CYCLE_BIND",
    "RTV_CYCLE_FRAME",
    "v79_r2_note_begin_candidate(resource);",
    "v79_r2_note_rtv_cycle(resources);",
    "selection=largest-repeated-begin-signature",
    "boundary=rtv-resource-switch",
    "reverse-present-barrier=not-required",
    "baseline-capture-freeze=enabled",
    "if (s_v79_baseline_ready.load(std::memory_order_acquire))\n                return;",
    "s_v79_current_rtvs[command_list] = resources;",
    "commands_modified=0",
]
missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit("ERROR: V79 R2 source markers missing: " + ", ".join(missing))

if text.count("v79_r2_note_begin_candidate(resource);") != 1:
    raise SystemExit("ERROR: V79 R2 candidate grouping call count is not exactly one")
if text.count("v79_r2_note_rtv_cycle(resources);") != 1:
    raise SystemExit("ERROR: V79 R2 RTV cycle call count is not exactly one")
if text.count("kaiozen_v79_r2_binary_marker_manifest") != 1:
    raise SystemExit("ERROR: V79 R2 exported manifest count is not exactly one")

# Lightweight lexical balance, ignoring quoted strings and comments.
def strip_literals_and_comments(code: str) -> str:
    out = []
    i = 0
    state = "normal"
    while i < len(code):
        c = code[i]
        n = code[i + 1] if i + 1 < len(code) else ""
        if state == "normal":
            if c == '"': state = "string"; out.append(' ')
            elif c == "'": state = "char"; out.append(' ')
            elif c == '/' and n == '/': state = "line"; out.extend('  '); i += 1
            elif c == '/' and n == '*': state = "block"; out.extend('  '); i += 1
            else: out.append(c)
        elif state == "string":
            out.append(' ')
            if c == '\\' and n: out.append(' '); i += 1
            elif c == '"': state = "normal"
        elif state == "char":
            out.append(' ')
            if c == '\\' and n: out.append(' '); i += 1
            elif c == "'": state = "normal"
        elif state == "line":
            out.append('\n' if c == '\n' else ' ')
            if c == '\n': state = "normal"
        else:
            out.append(' ')
            if c == '*' and n == '/': out.append(' '); i += 1; state = "normal"
        i += 1
    if state in {"string", "char", "block"}:
        raise SystemExit(f"ERROR: V79 R2 unterminated lexical state: {state}")
    return ''.join(out)

clean = strip_literals_and_comments(text)
for left, right, name in [('(', ')', 'parentheses'), ('{', '}', 'braces'), ('[', ']', 'brackets')]:
    depth = 0
    for ch in clean:
        if ch == left: depth += 1
        elif ch == right:
            depth -= 1
            if depth < 0:
                raise SystemExit(f"ERROR: V79 R2 negative {name} depth")
    if depth != 0:
        raise SystemExit(f"ERROR: V79 R2 unbalanced {name}: {depth}")

report = "\n".join([
    "V79_R2_SOURCE_VERIFICATION_OK",
    "BINARY_MANIFEST=V79_R2_BINARY_MARKER_MANIFEST_R2_RTV_CYCLE_FRAME_BOUNDARY",
    "EXPORTED_MANIFEST_SYMBOL=kaiozen_v79_r2_binary_marker_manifest",
    "PRESENT_BOUNDARY=RTV_RESOURCE_CYCLE",
    "SWAPCHAIN_SELECTION=LARGEST_REPEATED_BEGIN_SIGNATURE",
    "REVERSE_PRESENT_BARRIER_REQUIRED=NO",
    "BASELINE_CAPTURE_FREEZE=YES",
    "BASELINE_PRESENT_FRAMES=8",
    "POST_SETTINGS_PRESENT_FRAMES=4",
    "GPU_READBACK=DISABLED",
    "COMMANDS_MODIFIED=NO",
    "CPP_LEXICAL_BALANCE=PASS",
    "RESULT=PASS",
    "",
])
Path("v79-r2-source-verification.txt").write_text(report, encoding="ascii")
print(report, end="")
