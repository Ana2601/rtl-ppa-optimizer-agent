"""Tests for the gates and the agent loop. Run: python -m unittest -v tests/test_rtlopt.py

The mutant tests are the important ones: each injected bug must be rejected by
the right gate, including one that the testbench cannot see and only the formal
equivalence check catches."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rtlopt import tools                                   # noqa: E402
from rtlopt.agent import Optimizer                         # noqa: E402
from rtlopt.llm import ClaudeBackend, Turn                 # noqa: E402

ALU = tools.Bench.load(ROOT / "benchmarks" / "alu32")
ORIG = ALU.original.read_text()


def mutate(old: str, new: str) -> str:
    assert old in ORIG, old
    return ORIG.replace(old, new)


class Gates(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def verdict(self, rtl: str) -> tuple[str | None, dict]:
        res = tools.evaluate(rtl, ALU, self.tmp)
        failed = next((g for g, v in res["gates"].items() if not v["pass"]), None)
        return failed, res

    def test_original_passes_every_gate(self):
        failed, res = self.verdict(ORIG)
        self.assertIsNone(failed)
        self.assertEqual(res["gates"]["lec"]["verdict"], "PROVEN")
        self.assertGreater(res["ppa"]["area_um2"], 1000)

    def test_port_change_is_rejected_by_interface(self):
        failed, _ = self.verdict(mutate("output logic [31:0] y", "output logic [32:0] y"))
        self.assertEqual(failed, "interface")

    def test_lint_warning_is_rejected(self):
        # functionally identical, but leaves a dead signal behind
        failed, _ = self.verdict(mutate("    always_comb begin",
                                        "    logic [31:0] spare;\n    assign spare = a & b;\n\n    always_comb begin"))
        self.assertEqual(failed, "lint")

    def test_visible_bug_is_rejected_by_simulation(self):
        failed, _ = self.verdict(mutate("SLT:     y = {31'b0, $signed(a) < $signed(b)};",
                                        "SLT:     y = {31'b0, a < b};"))
        self.assertEqual(failed, "sim")

    def test_rare_bug_passes_simulation_but_not_equivalence(self):
        # wrong only for a single value of a: random simulation will not hit it
        failed, res = self.verdict(mutate("ADD:     y = a + b;",
                                          "ADD:     y = (a == 32'hDEAD_BEEF) ? a - b : a + b;"))
        self.assertTrue(res["gates"]["sim"]["pass"])
        self.assertEqual(failed, "lec")


class AgentLoop(unittest.TestCase):
    """The loop with a scripted model: verdicts come from the tools, not the model."""

    def test_accept_reject_and_constraints(self):
        steps = [
            ("evaluate_candidate", {"rationale": "no change", "rtl": ORIG}),
            ("evaluate_candidate", {"rationale": "shared adder",
                                    "rtl": (ROOT / "trajectories/alu32/01_shared_adder.sv").read_text()}),
            ("finish", {"summary": "done"}),
        ]

        class Scripted:
            i = 0

            def step(self, system, messages, tools_):
                name, inp = steps[self.i]
                self.i += 1
                return Turn(text="", tool_calls=[{"id": f"t{self.i}", "name": name, "input": inp}])

        with tempfile.TemporaryDirectory() as td:
            rep = Optimizer(ALU, Scripted(), Path(td), max_evals=5, log=lambda *_: None).run()
        verdicts = [a["verdict"] for a in rep["attempts"]]
        self.assertEqual(verdicts, ["no-gain", "constraint"])      # identical design; delay budget
        self.assertEqual(rep["improvement_%"], 0.0)
        self.assertEqual(rep["summary"], "done")


class ClaudeRequestShape(unittest.TestCase):
    """ClaudeBackend against a stub client: request fields and response parsing."""

    def test_request_and_parse(self):
        seen = {}

        def create(**kw):
            seen.update(kw)
            return SimpleNamespace(
                stop_reason="tool_use", stop_details=None,
                content=[SimpleNamespace(type="text", text="plan"),
                         SimpleNamespace(type="tool_use", id="tu_1", name="finish", input={"summary": "x"})])

        b = ClaudeBackend.__new__(ClaudeBackend)
        b.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
        b.effort, b.rec = "high", None
        turn = b.step("sys", [{"role": "user", "content": "hi"}], [{"name": "finish"}])
        self.assertEqual(seen["model"], "claude-opus-5-5")
        self.assertEqual(seen["output_config"], {"effort": "high"})
        self.assertEqual(seen["fallbacks"], "default")
        self.assertEqual(turn.tool_calls, [{"id": "tu_1", "name": "finish", "input": {"summary": "x"}}])
        self.assertEqual(turn.text, "plan")


if __name__ == "__main__":
    unittest.main(verbosity=2)
