"""Deterministic fingerprint: identical input -> identical serialized output.

Runs all four strategy/organization combinations over a fixed multilingual
text and prints a sha256 fingerprint of the canonical JSON. Used to verify
behavioral parity between the source tree and the packaged wheel.
"""
import hashlib
import json
import sys

from chunkweave import ChunkEngine

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


CONFIGS = [
    {
        "name": "flat_sliding",
        "config": {
            "organization": "flat",
            "strategy": "sliding_window",
            "config": {"chunk_size": 80, "overlap": 10},
        },
    },
    {
        "name": "flat_recursive",
        "config": {
            "organization": "flat",
            "strategy": "recursive",
            "config": {"chunk_size": 60, "separators": ["\n\n", "\n", "。", ""], "overlap": 5},
        },
    },
    {
        "name": "flat_semantic",
        "config": {
            "organization": "flat",
            "strategy": "semantic",
            "config": {"threshold": 0.5, "chunk_size": 100, "unit_separators": ["\n", ". "]},
        },
    },
    {
        "name": "hier_rec_sw",
        "config": {
            "organization": "hierarchical",
            "levels": [
                {
                    "strategy": "recursive",
                    "config": {"chunk_size": 120, "separators": ["\n\n", "\n"]},
                },
                {"strategy": "sliding_window", "config": {"chunk_size": 40, "overlap": 0}},
            ],
        },
    },
]


def main() -> None:
    engine = ChunkEngine()
    engine.set_provider(FakeProvider())
    out = {}
    for item in CONFIGS:
        result = engine.chunk(TEXT, item["config"])
        out[item["name"]] = result.to_dict()
    canonical = json.dumps(out, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    counts = {k: len(v["chunks"]) for k, v in out.items()}
    print(json.dumps({"fingerprint": digest, "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
