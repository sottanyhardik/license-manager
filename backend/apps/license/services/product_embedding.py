"""Local, free text embeddings for product matching (owner decision 2026-11-18).

Model: ``sentence-transformers/all-MiniLM-L6-v2`` — official quantized ONNX
files at a pinned revision, run with ONNX Runtime (CPU, 1 thread) and the
``tokenizers`` library. No PyTorch, no Transformers, no generative model, no
network at inference time. Inference runs only in the Celery matching task,
never in a web request.

Files are downloaded once (``manage.py product_matching_model --download``),
verified against the checksums Hugging Face publishes for that revision, and
stored under ``PRODUCT_MATCH_MODEL_DIR`` (default ``backend/var/models``).
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MAX_TOKENS = 256
CHUNK_WORDS, CHUNK_OVERLAP = 120, 30
DEFAULT_BATCH, MAX_BATCH = 4, 8

# variant -> (path in repo, sha256 published by Hugging Face (LFS oid), size)
_ARM_AVX512_SHA = "4278337fd0ff3c68bfb6291042cad8ab363e1d9fbc43dcb499fe91c871902474"
ONNX_FILES = {
    "arm64": ("onnx/model_qint8_arm64.onnx", _ARM_AVX512_SHA, 23026053),
    "avx512_vnni": ("onnx/model_qint8_avx512_vnni.onnx", _ARM_AVX512_SHA, 23026053),
    "avx512": ("onnx/model_qint8_avx512.onnx", _ARM_AVX512_SHA, 23026053),
    "avx2": ("onnx/model_quint8_avx2.onnx", "b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21", 23046789),
}
# tokenizer.json is a plain git object: verified by its git blob sha1.
TOKENIZER_FILE = ("tokenizer.json", "cb202bfe2e3c98645018a6d12f182a434c9d3e02", 466247)


class EmbeddingUnavailable(RuntimeError):
    """Model files missing / unverified or CPU unsupported — callers fall back to deterministic matching."""


def model_dir() -> Path:
    base = os.environ.get("PRODUCT_MATCH_MODEL_DIR") or str(Path(__file__).resolve().parents[3] / "var" / "models")
    return Path(base) / "all-MiniLM-L6-v2" / MODEL_REVISION


def cpu_variant() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine in {"x86_64", "amd64"}:
        flags = ""
        try:
            flags = Path("/proc/cpuinfo").read_text(errors="ignore")
        except OSError:
            pass
        if re.search(r"\bavx512_vnni\b", flags):
            return "avx512_vnni"
        if re.search(r"\bavx512f\b", flags):
            return "avx512"
        if re.search(r"\bavx2\b", flags) or not flags:
            return "avx2"
    raise EmbeddingUnavailable(f"Unsupported CPU architecture {machine!r} for the quantized ONNX model")


def model_version() -> str:
    return f"{MODEL_REPO}@{MODEL_REVISION[:12]}:{cpu_variant()}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324 - git object id, not security


def files_status() -> dict:
    variant = cpu_variant()
    onnx_path, onnx_sha, _ = ONNX_FILES[variant]
    root = model_dir()
    onnx_file, tok_file = root / Path(onnx_path).name, root / TOKENIZER_FILE[0]
    return {
        "variant": variant, "dir": str(root),
        "onnx": {"file": onnx_file.name, "present": onnx_file.exists(), "verified": onnx_file.exists() and _sha256(onnx_file) == onnx_sha,
                 "bytes": onnx_file.stat().st_size if onnx_file.exists() else None},
        "tokenizer": {"present": tok_file.exists(), "verified": tok_file.exists() and _git_blob_sha1(tok_file) == TOKENIZER_FILE[1]},
    }


def download_model() -> dict:
    """Fetch the pinned files for this CPU, verify checksums, install atomically."""
    import requests

    variant = cpu_variant()
    root = model_dir()
    root.mkdir(parents=True, exist_ok=True)
    targets = [(ONNX_FILES[variant][0], ONNX_FILES[variant][1], _sha256), (TOKENIZER_FILE[0], TOKENIZER_FILE[1], _git_blob_sha1)]
    for repo_path, expected, digest in targets:
        final = root / Path(repo_path).name
        if final.exists() and digest(final) == expected:
            continue
        url = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{repo_path}"
        tmp = final.with_suffix(final.suffix + ".part")
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with tmp.open("wb") as fh:
                for block in response.iter_content(1 << 20):
                    fh.write(block)
        actual = digest(tmp)
        if actual != expected:
            tmp.unlink(missing_ok=True)
            raise EmbeddingUnavailable(f"Checksum mismatch for {repo_path}: {actual} != {expected}")
        tmp.replace(final)
    return files_status()


def prepare_text(text: str | None) -> str:
    """Whitespace / punctuation clean-up only — technical words are preserved."""
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return re.sub(r"\s*([/,;:])\s*", r"\1 ", value)


def text_hash(text: str) -> str:
    return hashlib.sha256(prepare_text(text).encode()).hexdigest()


def chunks(text: str) -> list[tuple[str, float]]:
    """Overlapping word windows (each well under 256 tokens); the first carries the product name, so it weighs more."""
    words = prepare_text(text).split(" ")
    if len(words) <= CHUNK_WORDS:
        return [(" ".join(words), 1.0)]
    out, start = [], 0
    while start < len(words):
        window = words[start:start + CHUNK_WORDS]
        out.append((" ".join(window), 1.5 if start == 0 else 1.0))
        if start + CHUNK_WORDS >= len(words):
            break
        start += CHUNK_WORDS - CHUNK_OVERLAP
    return out


@dataclass
class _Runtime:
    session: object
    tokenizer: object
    input_names: set


_runtime: _Runtime | None = None
_lock = threading.Lock()


def _load() -> _Runtime:
    global _runtime
    with _lock:  # never load the model twice in one process
        if _runtime is not None:
            return _runtime
        status = files_status()
        if not (status["onnx"]["verified"] and status["tokenizer"]["verified"]):
            raise EmbeddingUnavailable("Model files missing or unverified — run `manage.py product_matching_model --download`")
        import onnxruntime as ort
        from tokenizers import Tokenizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.enable_cpu_mem_arena = False
        root = model_dir()
        session = ort.InferenceSession(str(root / Path(ONNX_FILES[status["variant"]][0]).name), sess_options=options,
                                       providers=["CPUExecutionProvider"])
        tokenizer = Tokenizer.from_file(str(root / TOKENIZER_FILE[0]))
        tokenizer.enable_truncation(MAX_TOKENS)
        tokenizer.enable_padding()
        _runtime = _Runtime(session, tokenizer, {i.name for i in session.get_inputs()})
        return _runtime


def _encode(pieces: list[str]) -> np.ndarray:
    runtime = _load()
    encoded = runtime.tokenizer.encode_batch(pieces)
    ids = np.array([e.ids for e in encoded], dtype=np.int64)
    mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
    feeds = {"input_ids": ids, "attention_mask": mask}
    if "token_type_ids" in runtime.input_names:
        feeds["token_type_ids"] = np.zeros_like(ids)
    hidden = runtime.session.run(None, feeds)[0]  # (batch, tokens, 384)
    weights = mask[..., None].astype(np.float32)
    pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
    return pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9, None)


def embed(texts: list[str], *, batch_size: int = DEFAULT_BATCH, before_batch=None) -> np.ndarray:
    """Unit-length float32 vectors, one per text. Long texts → weighted mean of chunk vectors.
    ``before_batch()`` is called before each batch (memory guard / pause checks)."""
    batch_size = max(1, min(int(batch_size), MAX_BATCH))
    plan = [(index, piece, weight) for index, text in enumerate(texts) for piece, weight in chunks(text)]
    sums = np.zeros((len(texts), 384), dtype=np.float32)
    for start in range(0, len(plan), batch_size):
        if before_batch:
            before_batch()
        part = plan[start:start + batch_size]
        vectors = _encode([piece for _, piece, _ in part])
        for (index, _, weight), vector in zip(part, vectors, strict=True):
            sums[index] += weight * vector
    return sums / np.clip(np.linalg.norm(sums, axis=1, keepdims=True), 1e-9, None)


def to_bytes(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def from_bytes(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32)


def available_memory_mb() -> float | None:
    """Linux MemAvailable (the production signal); None where /proc is absent (dev machines)."""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def peak_rss_mb() -> float:
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024
