"""Prompts. The system prompt carries the role, the rules, and the skill files;
it is identical across turns so it caches."""
from __future__ import annotations

import json
from pathlib import Path

from .tools import Bench

SKILLS = Path(__file__).resolve().parent.parent / "skills"


def _skills() -> str:
    out = []
    for f in sorted(SKILLS.glob("*/SKILL.md")):
        out.append(f"<skill path=\"{f.relative_to(SKILLS.parent)}\">\n{f.read_text()}\n</skill>")
    return "\n\n".join(out)


def system_prompt(bench: Bench) -> str:
    return f"""You are an RTL optimisation engineer. You improve the power-performance-area
of an existing SystemVerilog module without changing its behaviour.

You work through tools. `evaluate_candidate` runs your complete rewrite through four gates
(interface, Verilator lint, the testbench, formal equivalence against the original) and then
synthesises it with Yosys + ABC on the sky130_fd_sc_hd library. The tools decide whether a
candidate is accepted; your job is to propose candidates that are likely to win and to learn
from every verdict.

How to work:
- Read the spec first: it defines what must be preserved and what is don't-care.
- Form a hypothesis about where the area or delay comes from before you rewrite anything.
- Make one kind of change per candidate, so each verdict teaches you something.
- After a rejection, read the gate's log and fix the cause; don't resubmit a variation blindly.
- When a candidate meets one goal but breaks the other constraint, look for a second
  transform that recovers it, on top of the best design so far.
- Stop with `finish` when you have no idea left that you expect to gain at least 0.5 %,
  or when the evaluation budget is nearly used. Say what worked and what did not.

Keep the text between tool calls short: the hypothesis and the plan, not a transcript.

{_skills()}
"""


def task_prompt(bench: Bench, baseline: dict) -> str:
    cons = []
    if bench.max_area_ratio < 10:
        cons.append(f"area <= {bench.max_area_ratio:.2f} x original")
    if bench.max_delay_ratio < 10:
        cons.append(f"delay <= {bench.max_delay_ratio:.2f} x original")
    return f"""Optimise `{bench.top}`.

Objective: minimise **{bench.objective}**. Constraints: {', '.join(cons) or 'none'}.

<spec>
{bench.spec}
</spec>

<original_rtl file="{bench.original.name}">
{bench.original.read_text()}
</original_rtl>

Baseline PPA of the original (Yosys + ABC, sky130_fd_sc_hd tt_025C_1v80):
{json.dumps(baseline, indent=1)}

Equivalence is checked at reduced parameters {json.dumps(bench.lec_params) if bench.lec_params else '(full size)'},
so keep the design parametric. Outputs compared only under a qualifier: {json.dumps(bench.lec_compare) or 'none'}.
"""
