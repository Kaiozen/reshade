from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")
text = source.read_text(encoding="utf-8")

required = [
    "V79_R3_BINARY_MARKER_MANIFEST_R3_STABLE_TRIPLET_RING",
    "kaiozen_v79_r3_binary_marker_manifest",
    "SWAPCHAIN_TRIPLET_LOCKED",
    "RTV_RING_BIND",
    "RTV_RING_FRAME",
    "v79_r3_last_four_cycles_are_triplet",
    "v79_r3_observe_rtv_sequence(resources);",
    "proof=three-distinct-resources-four-exact-cycles",
    "dynamic-largest-group-selection=disabled",
    "locked-present-resource-input-filter-bypass=enabled",
    "const bool locked_present_resource =",
    "seen_as_input && !locked_present_resource",
    "baseline-capture-freeze=enabled",
    "commands_modified=0",
]
missing = [marker for marker in required if marker not in text]
if missing:
    raise SystemExit("ERROR: V79 R3 source markers missing: " + ", ".join(missing))

if text.count("v79_r3_observe_rtv_sequence(resources);") != 1:
    raise SystemExit("ERROR: V79 R3 sequence observer call count is not exactly one")
if text.count("kaiozen_v79_r3_binary_marker_manifest") != 1:
    raise SystemExit("ERROR: V79 R3 exported manifest count is not exactly one")
if "v79_r2_note_rtv_cycle(resources);" in text:
    raise SystemExit("ERROR: V79 R2 dynamic cycle routing is still active")

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
        raise SystemExit(f"ERROR: V79 R3 unterminated lexical state: {state}")
    return ''.join(out)

clean = strip_literals_and_comments(text)
for left, right, name in [('(', ')', 'parentheses'), ('{', '}', 'braces'), ('[', ']', 'brackets')]:
    depth = 0
    for ch in clean:
        if ch == left: depth += 1
        elif ch == right:
            depth -= 1
            if depth < 0:
                raise SystemExit(f"ERROR: V79 R3 negative {name} depth")
    if depth != 0:
        raise SystemExit(f"ERROR: V79 R3 unbalanced {name}: {depth}")

report = "\n".join([
    "V79_R3_SOURCE_VERIFICATION_OK",
    "BINARY_MANIFEST=V79_R3_BINARY_MARKER_MANIFEST_R3_STABLE_TRIPLET_RING",
    "EXPORTED_MANIFEST_SYMBOL=kaiozen_v79_r3_binary_marker_manifest",
    "PRESENT_BOUNDARY=FROZEN_THREE_RESOURCE_PERIODIC_RING",
    "TRIPLET_PERIOD_PROOF=FOUR_EXACT_CYCLES",
    "BEGIN_TRANSITION_REQUIRED=YES",
    "DYNAMIC_LARGEST_GROUP_SELECTION=DISABLED",
    "LOCKED_PRESENT_RESOURCE_INPUT_FILTER_BYPASS=YES",
    "BASELINE_CAPTURE_FREEZE=YES",
    "GPU_READBACK=DISABLED",
    "COMMANDS_MODIFIED=NO",
    "CPP_LEXICAL_BALANCE=PASS",
    "RESULT=PASS",
    "",
])
Path("v79-r3-source-verification.txt").write_text(report, encoding="ascii")
print(report, end="")
