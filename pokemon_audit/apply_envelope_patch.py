from __future__ import annotations

import base64
import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parts = sorted(ROOT.glob("envelope_patch_payload.part*"))
if not parts:
    raise RuntimeError("envelope patch payload parts are missing")
payload = "".join(p.read_text(encoding="ascii").strip() for p in parts)
data = base64.b64decode(payload)
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
    names = archive.getnames()
    expected = {
        "build_evidence.py",
        "validate_engine_inputs_v2.js",
        "run_ohko_state.js",
        "run_two_hit_state.js",
        "merge_results.py",
        "prepare_runtime_scripts.py",
    }
    if set(names) != expected:
        raise RuntimeError(f"unexpected envelope patch file set: {names}")
    archive.extractall(ROOT, filter="data")
for name in sorted(expected):
    target = ROOT / name
    print(f"patched {name}: {target.stat().st_size} bytes")
