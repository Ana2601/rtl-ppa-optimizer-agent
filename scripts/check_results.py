"""Fail if a replay no longer reproduces the headline results.

Absolute PPA numbers move a little between Yosys/ABC releases, so this checks
floors on the improvement and that the formal gate still decides the same way."""
import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"

# bench -> (minimum improvement %, attempts that must be rejected by the formal gate)
EXPECT = {
    "dual_mac": (35.0, [2]),     # #2 drops the accumulator reset: simulation passes, LEC must not
    "argmax8":  (45.0, []),
    "fir8_sym": (25.0, []),
    "alu32":    (0.0, []),       # no candidate fits the 5 % delay budget
}

ok = True
for bench, (floor, lec_rejects) in EXPECT.items():
    rep = json.loads((RESULTS / bench / "report.json").read_text())
    gain = rep["improvement_%"]
    bad = [a["n"] for a in rep["attempts"] if a["n"] in lec_rejects and a["verdict"] != "rejected:lec"]
    status = "ok" if gain >= floor and not bad else "FAIL"
    ok &= status == "ok"
    print(f"{bench:10s} {rep['objective']:6s} gain {gain:5.1f} % (floor {floor} %)  "
          f"LEC-rejected as expected: {not bad}  {status}")
sys.exit(0 if ok else 1)
