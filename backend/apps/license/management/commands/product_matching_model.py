"""Install / inspect / benchmark the local product-matching embedding model.

    manage.py product_matching_model --status      # CPU variant, files, checksums, RAM, swap
    manage.py product_matching_model --download    # fetch pinned files for this CPU and verify checksums
    manage.py product_matching_model --benchmark   # load + batch 4 / 8 latency, peak RSS (run on the target server)
"""
import os
import platform
import time
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.license.services import product_embedding as pe


def _meminfo() -> dict:
    out = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                out[key] = f"{int(value.split()[0]) // 1024} MB"
    except OSError:
        out["note"] = "/proc/meminfo not available on this OS"
    return out


class Command(BaseCommand):
    help = "Install, verify and benchmark the local MiniLM ONNX model used by product matching."

    def add_arguments(self, parser):
        parser.add_argument("--status", action="store_true")
        parser.add_argument("--download", action="store_true")
        parser.add_argument("--benchmark", action="store_true")

    def handle(self, *args, **options):
        self.stdout.write(f"machine={platform.machine()} cpus={os.cpu_count()} python={platform.python_version()} {_meminfo()}")
        try:
            self.stdout.write(f"variant={pe.cpu_variant()} model_version={pe.model_version()}")
        except pe.EmbeddingUnavailable as exc:
            self.stderr.write(str(exc))
            return
        if options["download"]:
            self.stdout.write(f"download: {pe.download_model()}")
        if options["status"] or not (options["download"] or options["benchmark"]):
            self.stdout.write(f"files: {pe.files_status()}")
        if options["benchmark"]:
            sample = [
                "PP", "Polypropylene granules (moulding grade)", "Aluminium foil 7607", "Alu foil for packing",
                "Natural flavours", "Sun flower oil, refined", "RELEVANT FATS AND OILS NAMELY OLIVE OIL (HSN 1509,1510) / SUNFLOWER OIL "
                "(HSN 1512) / COTTON SEED OIL (HSN 1512) / MUSTARD OIL (HSN 1514) " * 3, "Paper and paper board 150-300 GSM",
            ]
            start = time.perf_counter()
            pe.embed(sample[:1])
            self.stdout.write(f"load+first={time.perf_counter() - start:.2f}s rss={pe.peak_rss_mb():.0f}MB")
            for batch in (4, 8):
                start = time.perf_counter()
                for _ in range(5):
                    pe.embed(sample, batch_size=batch)
                per = (time.perf_counter() - start) / (5 * len(sample))
                self.stdout.write(f"batch={batch} per_record={per * 1000:.1f}ms peak_rss={pe.peak_rss_mb():.0f}MB available={pe.available_memory_mb()}")
            vectors = pe.embed(["PP", "Polypropylene", "Aluminium foil", "Alu foil", "Sunflower oil", "Paper board"])
            sims = vectors @ vectors.T
            self.stdout.write(f"sanity: PP~polypropylene={sims[0, 1]:.2f} foil~alu-foil={sims[2, 3]:.2f} PP~paper-board={sims[0, 5]:.2f}")
