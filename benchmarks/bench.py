"""Reproducible benchmark for chunkweave.

Runs each workload with a fixed seed and reports environment, parameters and
timing as JSON to stdout. Usage: ``python benchmarks/bench.py [out.json]``

Note: workload keys were renamed ``flat_*``/``hierarchical_*`` to
``single_level_*``/``two_level_*`` when the engine API changed; seed, input
and per-workload parameters are unchanged.
"""

import json
import platform
import random
import statistics
import sys
import timeit

from chunkweave import ChunkEngine, Policy

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


def _policy(levels: list[dict], policy_id: str) -> Policy:
    return Policy.model_validate(
        {
            "api_version": "chunkweave/v1",
            "policy": {"id": policy_id, "name": policy_id, "version": "1.0.0"},
            "pipeline": {"levels": levels},
        }
    )


def main() -> None:
    rng = random.Random(SEED)
    text = build_text(rng, paragraphs=40, words_per_paragraph=12)
    engine = ChunkEngine()
    provider = BenchProvider()

    workloads = {
        "single_level_sliding_window": lambda: engine.execute(
            text,
            _policy(
                [
                    {
                        "name": "l0",
                        "strategy": "sliding_window",
                        "params": {"chunk_size": 500, "overlap": 50},
                    }
                ],
                "bench-sliding",
            ),
            provider=provider,
        ),
        "single_level_recursive": lambda: engine.execute(
            text,
            _policy(
                [
                    {
                        "name": "l0",
                        "strategy": "recursive",
                        "params": {"chunk_size": 500},
                    }
                ],
                "bench-recursive",
            ),
            provider=provider,
        ),
        "single_level_semantic": lambda: engine.execute(
            text,
            _policy(
                [
                    {
                        "name": "l0",
                        "strategy": "semantic",
                        "params": {"threshold": 0.6, "chunk_size": 500},
                    }
                ],
                "bench-semantic",
            ),
            provider=provider,
        ),
        "two_level_recursive_sliding": lambda: engine.execute(
            text,
            _policy(
                [
                    {
                        "name": "l0",
                        "strategy": "recursive",
                        "params": {"chunk_size": 800},
                    },
                    {
                        "name": "l1",
                        "strategy": "sliding_window",
                        "params": {"chunk_size": 200},
                    }
                ],
                "bench-two-level",
            ),
            provider=provider,
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
