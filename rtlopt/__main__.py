"""python -m rtlopt --bench dual_mac [--backend replay|claude] [--max-evals 10]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import Optimizer
from .llm import ClaudeBackend, ReplayBackend
from .tools import Bench

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LLM-driven RTL PPA optimiser")
    ap.add_argument("--bench", nargs="+", default=None, help="benchmark name(s); default: all")
    ap.add_argument("--backend", choices=["replay", "claude"], default="replay")
    ap.add_argument("--max-evals", type=int, default=10)
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    args = ap.parse_args(argv)

    names = args.bench or sorted(p.name for p in (ROOT / "benchmarks").iterdir() if (p / "bench.json").exists())
    reports = []
    for name in names:
        bench = Bench.load(ROOT / "benchmarks" / name)
        out = args.out / name
        if args.backend == "claude":
            backend = ClaudeBackend(record_dir=out / "trajectory")
        else:
            backend = ReplayBackend(ROOT / "trajectories" / name)
        rep = Optimizer(bench, backend, out, max_evals=args.max_evals).run()
        reports.append(rep)
        print(f"[{name}] {rep['objective']} improved {rep['improvement_%']} % "
              f"(best = attempt {rep['best_attempt']}, LEC {rep['best_lec']})")
    write_summary(args.out, reports)
    return 0


def write_summary(out: Path, reports: list[dict]) -> None:
    rows = ["| Benchmark | Goal | Original area (um²) | Best area | Original delay (ps) | Best delay | Gain | Equivalence | Attempts (accepted) |",
            "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for r in reports:
        b, x = r["baseline"], r["best"]
        acc = sum(a["verdict"] == "accepted" for a in r["attempts"])
        rows.append(f"| `{r['bench']}` | {r['objective']} | {b['area_um2']:.0f} | {x['area_um2']:.0f} | "
                    f"{b['delay_ps']:.0f} | {x['delay_ps']:.0f} | **{r['improvement_%']:.1f} %** | "
                    f"{r['best_lec']} | {len(r['attempts'])} ({acc}) |")
    detail = []
    for r in reports:
        detail.append(f"\n### {r['bench']}\n")
        detail.append("| # | Verdict | Area (um²) | Delay (ps) | Rationale |\n|---|---|---:|---:|---|")
        for a in r["attempts"]:
            p = a["ppa"] or {}
            lec = a["gates"].get("lec", "")
            detail.append(f"| {a['n']} | {a['verdict']}{' (' + lec.split(' ', 1)[1] + ')' if ' ' in lec else ''} | "
                          f"{p.get('area_um2', '-')} | {p.get('delay_ps', '-')} | "
                          f"{a['rationale'].replace('|', chr(92) + '|')[:170]} |")
        front = ", ".join(f"#{q['n']} ({q['area_um2']:.0f} um², {q['delay_ps']:.0f} ps)" for q in r["pareto"])
        detail.append(f"\nArea/delay Pareto front (constraints ignored; #0 = original): {front}\n")
        if r.get("summary"):
            detail.append(f"Agent summary: {r['summary']}\n")
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.md").write_text("\n".join(rows) + "\n" + "\n".join(detail) + "\n")
    print((out / "summary.md").read_text())


if __name__ == "__main__":
    sys.exit(main())
