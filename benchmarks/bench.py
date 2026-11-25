"""Reproducible benchmark for chunkweave.

Runs each workload with a fixed seed and reports environment, parameters and
timing as JSON to stdout. Usage: ``python benchmarks/bench.py [out.json]``
"""

import json
import platform
import random
import statistics
import sys
import timeit

from chunkweave import ChunkEngine

sys.stdout.reconfigure(encoding="utf-8")

SEED = 20261125
REPEAT = 5
NUMBER = 20


class BenchProvider:
    """Deterministic pseudo-similarity for benchmarking, no network."""

    def score(self, left: str, right: str) -> float:
        # Hash-free deterministic similarity from character overlap.
        if not left or not right:
            return 0.0
        common = len(set(left) & set(right))
        return common / max(len(set(left)), len(set(right)))


def build_text(rng: random.Random, paragraphs: int, words_per_paragraph: int) -> str:
    vocab = [
        "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
        "iota", "kappa", "lambda", "mu", "nu", "xi", "omicron", "pi", "rho",
        "sigma", "tau",
    ]
    parts = []
    for _ in range(paragraphs):
        sentences = []
        for _ in range(6):
            n = rng.randint(5, words_per_paragraph)
            sentences.append(" ".join(rng.choice(vocab) for _ in range(n)) + ".")
        parts.append(" ".join(sentences))
    return "\n\n".join(parts)


def timed(fn) -> dict:
    best = min(
        timeit.repeat(fn, number=NUMBER, repeat=REPEAT)
    ) / NUMBER
    times = timeit.repeat(fn, number=1, repeat=REPEAT)
    return {
        "best_seconds": round(best, 6),
        "median_seconds": round(statistics.median(times), 6),
    }


def main() -> None:
    rng = random.Random(SEED)
    text = build_text(rng, paragraphs=40, words_per_paragraph=12)
    engine = ChunkEngine()
    engine.set_provider(BenchProvider())

    workloads = {
        "flat_sliding_window": lambda: engine.chunk(
            text,
            {
                "organization": "flat",
                "strategy": "sliding_window",
                "config": {"chunk_size": 500, "overlap": 50},
            },
        ),
        "flat_recursive": lambda: engine.chunk(
            text,
            {
                "organization": "flat",
                "strategy": "recursive",
                "config": {"chunk_size": 500},
            },
        ),
        "flat_semantic": lambda: engine.chunk(
            text,
            {
                "organization": "flat",
                "strategy": "semantic",
                "config": {"threshold": 0.6, "chunk_size": 500},
            },
        ),
        "hierarchical_rec_sw": lambda: engine.chunk(
            text,
            {
                "organization": "hierarchical",
                "levels": [
                    {"strategy": "recursive", "config": {"chunk_size": 800}},
                    {"strategy": "sliding_window", "config": {"chunk_size": 200}},
                ],
            },
        ),
    }
    report = {
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
            "seed": SEED,
            "repeat": REPEAT,
            "number_per_repeat": NUMBER,
        },
        "input": {"text_codepoints": len(text), "paragraphs": 40},
        "results": {},
    }
    for name, fn in workloads.items():
        chunks = fn().chunks
        stats = timed(fn)
        report["results"][name] = {
            "chunks_produced": len(chunks),
            **stats,
        }
        ms = stats["best_seconds"] * 1e3
        print(f"{name}: {len(chunks)} chunks, best {ms:.3f} ms", file=sys.stderr)

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            fh.write(payload)
        print(f"wrote {sys.argv[1]}", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
