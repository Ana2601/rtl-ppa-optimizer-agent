"""The optimisation loop.

    propose (model) -> gates: interface, lint, sim, LEC -> synthesise -> accept / reject
          ^                                                              |
          +---------------- structured feedback (JSON) <-----------------+

The model never decides whether a candidate is accepted: the tools do. A
candidate is accepted only if it passes every gate, meets the spec's area /
delay constraints, and improves the objective by at least MIN_GAIN.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import tools
from .prompts import system_prompt, task_prompt

MIN_GAIN = 0.005          # 0.5 %: below this a "win" is synthesis noise

TOOLS = [
    {
        "name": "evaluate_candidate",
        "description": (
            "Submit a complete rewrite of the module for evaluation. It runs the interface "
            "check, Verilator lint (-Wall, zero warnings), the benchmark testbench, a formal "
            "equivalence check against the ORIGINAL design, and Yosys+ABC synthesis on "
            "sky130_fd_sc_hd. Returns each gate's verdict, the PPA, and whether the candidate "
            "became the new best. Always submit the whole module, never a fragment."),
        "input_schema": {
            "type": "object",
            "properties": {
                "rationale": {"type": "string",
                              "description": "What you changed and why you expect it to help."},
                "rtl": {"type": "string", "description": "The complete SystemVerilog module."},
            },
            "required": ["rationale", "rtl"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "get_best",
        "description": "Return the current best RTL and its PPA (the original if nothing was accepted yet).",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "finish",
        "description": "End the optimisation when further gains are unlikely. Summarise what worked and what did not.",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def objective(ppa: dict, kind: str) -> float:
    if kind == "area":
        return ppa["area_um2"]
    if kind == "delay":
        return ppa["delay_ps"]
    return ppa["area_um2"] * ppa["delay_ps"]          # "adp": area-delay product


@dataclass
class Attempt:
    n: int
    rationale: str
    verdict: str                  # accepted | rejected:<gate> | no-gain | constraint
    gates: dict
    ppa: dict | None
    seconds: float


@dataclass
class Optimizer:
    bench: tools.Bench
    backend: object
    out: Path
    max_evals: int = 10
    log: callable = print
    attempts: list = field(default_factory=list)

    def run(self) -> dict:
        b = self.bench
        work = self.out / "work"
        self.log(f"[{b.name}] baseline: gates + synthesis of the original design")
        base = tools.evaluate(b.original.read_text(), b, work / "00_original")
        if "ppa" not in base:
            raise RuntimeError(f"original design fails its own gates: {json.dumps(base['gates'])[:2000]}")
        self.baseline = base["ppa"]
        self.best = {"rtl": b.original.read_text(), "ppa": base["ppa"], "lec": "-", "n": 0}
        self.log(f"[{b.name}] baseline area={self.baseline['area_um2']} um2 "
                 f"delay={self.baseline['delay_ps']} ps cells={self.baseline['cells']}")

        system = system_prompt(b)
        messages: list = [{"role": "user", "content": task_prompt(b, self.baseline)}]
        summary = None
        turns = 0
        while len(self.attempts) < self.max_evals and turns < self.max_evals * 3:
            turns += 1
            turn = self.backend.step(system, messages, TOOLS)
            messages.append({"role": "assistant", "content": turn.raw_content if turn.raw_content is not None
                             else _blocks(turn)})
            if turn.text:
                self.log(f"[{b.name}] model: {turn.text.strip()[:400]}")
            if not turn.tool_calls:
                break
            results = []
            for call in turn.tool_calls:
                out, done = self._dispatch(call, work)
                results.append({"type": "tool_result", "tool_use_id": call["id"],
                                "content": json.dumps(out, indent=1)})
                if done:
                    summary = call["input"].get("summary", "")
            messages.append({"role": "user", "content": results})
            if summary is not None:
                break

        report = self._report(summary)
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / f"{b.top}.best.sv").write_text(self.best["rtl"])
        (self.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        return report

    # ------------------------------------------------------------------ #
    def _dispatch(self, call: dict, work: Path) -> tuple[dict, bool]:
        name, inp = call["name"], call["input"]
        if name == "get_best":
            return {"rtl": self.best["rtl"], "ppa": self.best["ppa"]}, False
        if name == "finish":
            return {"ok": True}, True
        if name != "evaluate_candidate":
            return {"error": f"unknown tool {name}"}, False
        if len(self.attempts) >= self.max_evals:
            return {"error": "evaluation budget exhausted; call finish"}, False

        n = len(self.attempts) + 1
        t0 = time.time()
        res = tools.evaluate(inp["rtl"], self.bench, work / f"{n:02d}")
        dt = round(time.time() - t0, 1)
        failed = next((g for g, v in res["gates"].items() if not v["pass"]), None)
        out = {"attempt": n, "gates": {g: ("PASS" if v["pass"] else "FAIL") +
                                       (f" {v['verdict']}" if "verdict" in v else "")
                                       for g, v in res["gates"].items()}}
        if failed:
            verdict = f"rejected:{failed}"
            out["failed_gate"] = failed
            out["log"] = res["gates"][failed]["log"][:4000]
        else:
            ppa = res["ppa"]
            k = self.bench.objective
            feasible, why = self._constraints(ppa)
            gain = 1 - objective(ppa, k) / objective(self.best["ppa"], k)
            out["ppa"] = ppa
            out["vs_original"] = self._delta(ppa, self.baseline)
            out["vs_best"] = self._delta(ppa, self.best["ppa"])
            if not feasible:
                verdict = "constraint"
                out["result"] = f"REJECTED - violates a spec constraint: {why}"
            elif gain < MIN_GAIN:
                verdict = "no-gain"
                out["result"] = (f"REJECTED - {k} is not better than the current best "
                                 f"({gain*100:+.1f} %; need at least +{MIN_GAIN*100:.1f} %)")
            else:
                verdict = "accepted"
                self.best = {"rtl": inp["rtl"], "ppa": ppa, "lec": res["gates"]["lec"]["verdict"], "n": n}
                out["result"] = f"ACCEPTED - new best, {k} improved {gain*100:.1f} % over the previous best"
        out["evaluations_left"] = self.max_evals - n
        self.attempts.append(Attempt(n, inp.get("rationale", ""), verdict, out["gates"], res.get("ppa"), dt))
        p = res.get("ppa")
        self.log(f"[{self.bench.name}] #{n} {verdict:18s} "
                 + (f"area={p['area_um2']} delay={p['delay_ps']}" if p else "") + f"  ({dt}s)")
        return out, False

    def _constraints(self, ppa: dict) -> tuple[bool, str]:
        b, base = self.bench, self.baseline
        if ppa["area_um2"] > base["area_um2"] * b.max_area_ratio:
            return False, (f"area {ppa['area_um2']} > {b.max_area_ratio:.2f} x original "
                           f"({base['area_um2'] * b.max_area_ratio:.1f})")
        if ppa["delay_ps"] > base["delay_ps"] * b.max_delay_ratio:
            return False, (f"delay {ppa['delay_ps']} ps > {b.max_delay_ratio:.2f} x original "
                           f"({base['delay_ps'] * b.max_delay_ratio:.1f} ps)")
        return True, ""

    @staticmethod
    def _delta(p: dict, ref: dict) -> dict:
        pct = lambda a, b: round((a / b - 1) * 100, 1) if b else 0.0
        return {"area_%": pct(p["area_um2"], ref["area_um2"]),
                "delay_%": pct(p["delay_ps"], ref["delay_ps"]),
                "cells": p["cells"] - ref["cells"], "flops": p["flops"] - ref["flops"]}

    def _pareto(self) -> list[dict]:
        """Non-dominated (area, delay) points among all verified designs, constraints ignored."""
        pts = [{"n": 0, "area_um2": self.baseline["area_um2"], "delay_ps": self.baseline["delay_ps"]}]
        pts += [{"n": a.n, "area_um2": a.ppa["area_um2"], "delay_ps": a.ppa["delay_ps"]}
                for a in self.attempts if a.ppa]
        front = [p for p in pts if not any(
            q["area_um2"] <= p["area_um2"] and q["delay_ps"] <= p["delay_ps"] and q != p and
            (q["area_um2"] < p["area_um2"] or q["delay_ps"] < p["delay_ps"]) for q in pts)]
        return sorted(front, key=lambda p: p["area_um2"])

    def _report(self, summary: str | None) -> dict:
        return {
            "pareto": self._pareto(),
            "bench": self.bench.name, "objective": self.bench.objective,
            "baseline": self.baseline, "best": self.best["ppa"], "best_attempt": self.best["n"],
            "best_lec": self.best["lec"],
            "improvement_%": round((1 - objective(self.best["ppa"], self.bench.objective)
                                    / objective(self.baseline, self.bench.objective)) * 100, 1),
            "attempts": [a.__dict__ for a in self.attempts],
            "summary": summary,
            "tools": tools.tool_versions(),
        }


def _blocks(turn) -> list:
    blocks = [{"type": "text", "text": turn.text}] if turn.text else []
    blocks += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["input"]}
               for c in turn.tool_calls]
    return blocks
