# Kaiozen ReShade Experiment Registry

This directory is the durable, machine-readable history for the Zenless Zone Zero D3DMetal RTX investigation.

Each entry records:

- experiment version and parent;
- source commit and build time;
- artifact and runtime hashes;
- exact purpose and safety constraints;
- required result markers;
- final status and no-rerun decisions.

## Status lifecycle

`BUILT_NOT_RUN` → `RUN_PASS`, `RUN_INVALID`, `RUN_FAIL`, or `RETIRED_NO_RERUN`.

Never overwrite an old result. Add a new revision or update only the matching entry with its report hash and final status.
