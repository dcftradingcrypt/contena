from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parts = sorted(ROOT.glob("envelope_patch_v2.part*"))
expected_part_names = [f"envelope_patch_v2.part{i:02d}" for i in range(1, 17)]
if [p.name for p in parts] != expected_part_names:
    raise RuntimeError(f"envelope patch v2 parts are incomplete: {[p.name for p in parts]}")
payload = "".join(p.read_text(encoding="ascii") for p in parts)
if len(payload) != 30908:
    raise RuntimeError(f"envelope patch v2 length mismatch: {len(payload)}")
if hashlib.sha256(payload.encode("ascii")).hexdigest() != "669f0919f1353659d8ec8dea57df9650304a5e5ad3826b3cf5952307d0bd3dc7":
    raise RuntimeError("envelope patch v2 payload SHA-256 mismatch")
data = base64.b64decode(payload, validate=True)
if hashlib.sha256(data).hexdigest() != "8dcc2a88170f80f2de0787e77c167f87685f99e7a13462adfb13a1c36ed3e47e":
    raise RuntimeError("envelope patch v2 archive SHA-256 mismatch")
expected = {
    "build_evidence.py",
    "validate_engine_inputs_v2.js",
    "run_ohko_state.js",
    "run_two_hit_state.js",
    "merge_results.py",
    "prepare_runtime_scripts.py",
}
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
    names = archive.getnames()
    if set(names) != expected:
        raise RuntimeError(f"unexpected envelope patch file set: {names}")
    archive.extractall(ROOT, filter="data")
for name in sorted(expected):
    target = ROOT / name
    print(f"patched {name}: {target.stat().st_size} bytes")
