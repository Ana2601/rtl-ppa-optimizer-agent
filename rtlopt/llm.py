"""Model backends for the optimisation agent.

ClaudeBackend   - live: Claude Opus 5.5 through the Anthropic Messages API with
                  tool use. Every turn is also recorded as a trajectory so the run
                  can be replayed later without an API key.
ReplayBackend   - offline: replays a recorded trajectory (the proposals only).
                  Every verdict is still recomputed by the real EDA tools, so a
                  replay proves the tool chain, not the model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MODEL = "claude-opus-5-5"


@dataclass
class Turn:
    """One assistant turn, backend-neutral."""
    text: str
    tool_calls: list[dict]          # [{"id", "name", "input"}]
    raw_content: object = None      # the API's content blocks, passed back verbatim


class ClaudeBackend:
    def __init__(self, record_dir: Path | None = None, effort: str = "high"):
        import anthropic                     # imported lazily: replay needs no SDK
        self.anthropic = anthropic
        self.client = anthropic.Anthropic()  # ANTHROPIC_API_KEY or an `ant auth login` profile
        self.effort = effort
        self.rec = TrajectoryWriter(record_dir) if record_dir else None

    def step(self, system: str, messages: list, tools: list[dict]) -> Turn:
        resp = self.client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=system,
            tools=tools,
            messages=messages,
            output_config={"effort": self.effort},
            # if a safety classifier declines, retry server-side on a fallback model
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model declined the request: {resp.stop_details}")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("model output hit max_tokens; the candidate RTL was truncated")
        text = "\n".join(b.text for b in resp.content if b.type == "text")
        calls = [{"id": b.id, "name": b.name, "input": b.input}
                 for b in resp.content if b.type == "tool_use"]
        turn = Turn(text=text, tool_calls=calls, raw_content=resp.content)
        if self.rec:
            self.rec.add(turn)
        return turn


class ReplayBackend:
    """Replays trajectories/<bench>/trajectory.json. A step can name an .sv file
    for the `rtl` argument so candidates stay readable on disk."""

    def __init__(self, traj_dir: Path):
        self.dir = traj_dir
        self.steps = json.loads((traj_dir / "trajectory.json").read_text())["steps"]
        self.i = 0

    def step(self, system: str, messages: list, tools: list[dict]) -> Turn:
        if self.i >= len(self.steps):
            return Turn(text="(trajectory exhausted)", tool_calls=[])
        s = self.steps[self.i]
        self.i += 1
        calls = []
        for j, c in enumerate(s.get("tool_calls", [])):
            inp = dict(c["input"])
            if "rtl_file" in inp:
                inp["rtl"] = (self.dir / inp.pop("rtl_file")).read_text()
            calls.append({"id": f"replay_{self.i}_{j}", "name": c["name"], "input": inp})
        return Turn(text=s.get("text", ""), tool_calls=calls)


@dataclass
class TrajectoryWriter:
    dir: Path
    steps: list = field(default_factory=list)

    def __post_init__(self):
        self.dir.mkdir(parents=True, exist_ok=True)

    def add(self, turn: Turn) -> None:
        calls = []
        for c in turn.tool_calls:
            inp = dict(c["input"])
            if "rtl" in inp:
                fname = f"{len(self.steps) + 1:02d}_candidate.sv"
                (self.dir / fname).write_text(inp.pop("rtl"))
                inp["rtl_file"] = fname
            calls.append({"name": c["name"], "input": inp})
        self.steps.append({"text": turn.text, "tool_calls": calls})
        (self.dir / "trajectory.json").write_text(
            json.dumps({"model": MODEL, "steps": self.steps}, indent=2) + "\n")
