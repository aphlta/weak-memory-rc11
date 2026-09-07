#!/usr/bin/env python3
"""生成约简规模实验（噪声 load 数量变化）。

论文用：固定 observe 的 MP/SB 骨架，增加独立 noise 地址上的 relaxed 读，
使全枚举组合按 2^n 增长，而 relevant 约简后组合数保持为常数。

重新生成：
  python3 scripts/gen_scale_benchmarks.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples"


def write(name: str, obj: dict) -> Path:
    path = OUT / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def mp_noise(n: int, *, fence: bool = False) -> dict:
    """MP + n 个噪声地址。observe=f,r；每噪声 1 store + 1 load ⇒ 每噪声 ×2 候选。"""
    init = {"x": 0, "flag": 0}
    for i in range(n):
        init[f"n{i}"] = 0

    t0 = []
    for i in range(n):
        t0.append(
            {"op": "store", "loc": f"n{i}", "value": 1, "atomic": True, "order": "relaxed"}
        )
    t0.append({"op": "store", "loc": "x", "value": 1, "atomic": True, "order": "relaxed"})
    if fence:
        t0.append({"op": "fence", "order": "seq_cst"})
        t0.append({"op": "store", "loc": "flag", "value": 1, "atomic": True, "order": "relaxed"})
    else:
        t0.append({"op": "store", "loc": "flag", "value": 1, "atomic": True, "order": "release"})

    t1 = []
    for i in range(n):
        t1.append(
            {
                "op": "load",
                "loc": f"n{i}",
                "target": f"t{i}",
                "atomic": True,
                "order": "relaxed",
            }
        )
    if fence:
        t1.append({"op": "load", "loc": "flag", "target": "f", "atomic": True, "order": "relaxed"})
        t1.append({"op": "fence", "order": "seq_cst"})
        t1.append({"op": "load", "loc": "x", "target": "r", "atomic": True, "order": "relaxed"})
    else:
        t1.append({"op": "load", "loc": "flag", "target": "f", "atomic": True, "order": "acquire"})
        t1.append({"op": "load", "loc": "x", "target": "r", "atomic": True, "order": "relaxed"})
    t1.append({"op": "assert_eq", "left": "r", "right": 1, "when": {"f": 1}})

    tag = "fence" if fence else "ra"
    return {
        "name": f"mp-{tag}-noise-{n}",
        "observe": ["f", "r"],
        "initial_memory": init,
        "threads": [t0, t1],
    }


def sb_noise(n: int) -> dict:
    init = {"x": 0, "y": 0}
    for i in range(n):
        init[f"n{i}"] = 0
    t0 = []
    for i in range(n):
        t0.append(
            {"op": "store", "loc": f"n{i}", "value": 1, "atomic": True, "order": "relaxed"}
        )
        t0.append(
            {
                "op": "load",
                "loc": f"n{i}",
                "target": f"u{i}",
                "atomic": True,
                "order": "relaxed",
            }
        )
    t0 += [
        {"op": "store", "loc": "x", "value": 1, "atomic": True, "order": "relaxed"},
        {"op": "load", "loc": "y", "target": "a", "atomic": True, "order": "relaxed"},
    ]
    t1 = [
        {"op": "store", "loc": "y", "value": 1, "atomic": True, "order": "relaxed"},
        {"op": "load", "loc": "x", "target": "b", "atomic": True, "order": "relaxed"},
    ]
    return {
        "name": f"sb-noise-{n}",
        "observe": ["a", "b"],
        "initial_memory": init,
        "threads": [t0, t1],
    }


def lb_noise(n: int) -> dict:
    """Load Buffering + 噪声；弱态 a=b=1 可能出现。"""
    init = {"x": 0, "y": 0}
    for i in range(n):
        init[f"n{i}"] = 0
    t0 = []
    for i in range(n):
        t0.append(
            {"op": "store", "loc": f"n{i}", "value": 1, "atomic": True, "order": "relaxed"}
        )
        t0.append(
            {
                "op": "load",
                "loc": f"n{i}",
                "target": f"u{i}",
                "atomic": True,
                "order": "relaxed",
            }
        )
    t0 += [
        {"op": "load", "loc": "y", "target": "a", "atomic": True, "order": "relaxed"},
        {"op": "store", "loc": "x", "value": 1, "atomic": True, "order": "relaxed"},
    ]
    t1 = [
        {"op": "load", "loc": "x", "target": "b", "atomic": True, "order": "relaxed"},
        {"op": "store", "loc": "y", "value": 1, "atomic": True, "order": "relaxed"},
    ]
    return {
        "name": f"lb-noise-{n}",
        "observe": ["a", "b"],
        "initial_memory": init,
        "threads": [t0, t1],
    }


def main() -> None:
    generated = []
    for n in (4, 5, 6, 7):
        generated.append(write(f"scale_mp_ra_noise_{n}.json", mp_noise(n, fence=False)))
    for n in (4, 5, 6):
        generated.append(write(f"scale_mp_fence_noise_{n}.json", mp_noise(n, fence=True)))
    for n in (2, 3, 4):
        generated.append(write(f"scale_sb_noise_{n}.json", sb_noise(n)))
    for n in (2, 3, 4):
        generated.append(write(f"scale_lb_noise_{n}.json", lb_noise(n)))

    print("generated:")
    for path in generated:
        print(" ", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
