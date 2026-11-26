"""Deterministic fingerprint: identical input -> identical serialized output.

Runs the same four workloads as before over a fixed multilingual text and
prints a sha256 fingerprint of the canonical JSON. Used to verify
behavioral parity between the source tree and the packaged wheel.
"""
import hashlib
import json
import sys

from chunkweave import ChunkEngine, Policy

TEXT = (
    "第一章 概述。\n"
    "切分引擎把文本分解为带元数据的小块。Emoji 👍🏻 与组合字符 e\u0301 按码点计数。\n"
    "Fruit: apples, pears, bananas. Fruit: oranges, lemons.\n"
    "Calculus: derivatives measure change. Integrals accumulate area.\n\n"
    "第二章 细节。\n"
    "递归切分按分隔符优先级下推，窗口切分按固定步长滑动。\n"
) * 3


class FakeProvider:
    def score(self, left: str, right: str) -> float:
        lw, rw = left.split(), right.split()
        if not lw or not rw:
            return 1.0
        return 0.9 if lw[-1].rstrip("。.") == rw[0].lstrip("第") else 0.3


def _policy(levels, pid):
    return Policy.model_validate(
        {
            "api_version": "chunkweave/v1",
            "policy": {"id": pid, "name": pid, "version": "1.0.0"},
            "pipeline": {"levels": levels},
            "metadata": {"include": {"strategy": False, "organization": False}},
        }
    )


POLICIES = [
    (
        "single_level_sliding",
        _policy(
            [
                {
                    "name": "l0",
                    "strategy": "sliding_window",
                    "params": {"chunk_size": 80, "overlap": 10},
                }
            ],
            "fp-flat-sliding",
        ),
    ),
    (
        "single_level_recursive",
        _policy(
            [
                {
                    "name": "l0",
                    "strategy": "recursive",
                    "params": {
                        "chunk_size": 60,
                        "separators": ["\n\n", "\n", "。", ""],
                        "overlap": 5,
                    },
                }
            ],
            "fp-flat-recursive",
        ),
    ),
    (
        "single_level_semantic",
        _policy(
            [
                {
                    "name": "l0",
                    "strategy": "semantic",
                    "params": {
                        "threshold": 0.5,
                        "chunk_size": 100,
                        "unit_separators": ["\n", ". "],
                    },
                }
            ],
            "fp-flat-semantic",
        ),
    ),
    (
        "two_level_recursive_sliding",
        _policy(
            [
                {
                    "name": "l0",
                    "strategy": "recursive",
                    "params": {"chunk_size": 120, "separators": ["\n\n", "\n"]},
                },
                {
                    "name": "l1",
                    "strategy": "sliding_window",
                    "params": {"chunk_size": 40, "overlap": 0},
                },
            ],
            "fp-hier",
        ),
    ),
]


def main() -> None:
    engine = ChunkEngine()
    out = {}
    for name, policy in POLICIES:
        result = engine.execute(TEXT, policy, provider=FakeProvider())
        dump = result.model_dump()
        # volatile per-execution fields are not part of the fingerprint
        dump.pop("execution_id")
        dump.pop("execution_time_ms")
        out[name] = dump
    canonical = json.dumps(out, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    counts = {k: len(v["chunks"]) for k, v in out.items()}
    print(json.dumps({"fingerprint": digest, "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
