"""EDA tool wrappers used as the agent's gates and metrics.

Every candidate RTL goes through four gates, in order, and is rejected at the
first one that fails:

    1. interface  - same ports, same directions, same widths as the original
    2. lint       - Verilator --lint-only -Wall, zero warnings
    3. sim        - the benchmark's self-checking testbench passes (Verilator)
    4. lec        - Yosys SAT equivalence against the ORIGINAL design
                    (proven by induction, or bounded to N cycles)

Only then is it synthesised (Yosys + ABC against the sky130_fd_sc_hd typical
corner liberty) to measure area and critical-path delay.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB_GZ = ROOT / "pdk" / "sky130_fd_sc_hd__tt_025C_1v80.lib.gz"
BUILD = ROOT / "build"


def liberty() -> Path:
    """Decompress the vendored liberty once (ABC cannot read .gz)."""
    lib = BUILD / "sky130_fd_sc_hd__tt_025C_1v80.lib"
    if not lib.exists():
        BUILD.mkdir(parents=True, exist_ok=True)
        with gzip.open(LIB_GZ, "rb") as src, open(lib, "wb") as dst:
            shutil.copyfileobj(src, dst)
    return lib


def _run(cmd: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str]:
    """Run a tool; on timeout kill its whole process group (sby/abc spawn children
    that would otherwise keep running and hold the output pipe open)."""
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, _ = p.communicate()
        return 124, (out or "") + f"\nTIMEOUT after {timeout}s"


def _tail(text: str, n: int = 25) -> str:
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines[-n:])


# --------------------------------------------------------------------------- #
# Benchmark description
# --------------------------------------------------------------------------- #
@dataclass
class Bench:
    name: str
    dir: Path
    top: str
    objective: str                 # "area" | "delay" | "adp"
    max_area_ratio: float = 10.0   # constraints relative to the original design
    max_delay_ratio: float = 10.0
    clock: str | None = None
    reset: str | None = None
    reset_active: int = 0
    lec_depth: int = 20            # bounded-check target depth (cycles)
    lec_min_depth: int = 4         # a bounded result shallower than this is inconclusive
    lec_prove_s: int = 60          # time box for the unbounded proof
    lec_bmc_s: int = 240           # time box for the bounded check
    lec_params: dict = field(default_factory=dict)
    lec_compare: dict = field(default_factory=dict)   # output -> qualifier output
    synth_params: dict = field(default_factory=dict)

    @property
    def original(self) -> Path:
        return self.dir / "rtl" / f"{self.top}.sv"

    @property
    def tb(self) -> Path:
        return self.dir / "tb" / "tb.sv"

    @property
    def spec(self) -> str:
        return (self.dir / "spec.md").read_text()

    @classmethod
    def load(cls, path: Path) -> "Bench":
        cfg = json.loads((path / "bench.json").read_text())
        return cls(name=path.name, dir=path, **cfg)


# --------------------------------------------------------------------------- #
# Gate 1: interface
# --------------------------------------------------------------------------- #
def ports(rtl: Path, top: str, params: dict | None = None) -> dict:
    """Port name -> (direction, width) from Yosys's elaborated netlist."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "p.json"
        chp = "".join(f" -chparam {k} {v}" for k, v in (params or {}).items())
        script = (f"read_verilog -sv {rtl}; hierarchy -top {top}{chp}; proc; "
                  f"write_json {out}")
        rc, log = _run(["yosys", "-q", "-p", script], Path(td))
        if rc:
            raise RuntimeError(_tail(log))
        mod = json.loads(out.read_text())["modules"][top]
        return {n: (p["direction"], len(p["bits"])) for n, p in mod["ports"].items()}


# --------------------------------------------------------------------------- #
# Gate 2: lint
# --------------------------------------------------------------------------- #
def lint(rtl: Path, top: str) -> tuple[bool, str]:
    rc, log = _run(["verilator", "--lint-only", "-Wall", "--top-module", top, str(rtl)], rtl.parent)
    msgs = [l for l in log.splitlines() if l.startswith("%")]
    return rc == 0 and not msgs, "\n".join(msgs[:20])


# --------------------------------------------------------------------------- #
# Gate 3: simulation
# --------------------------------------------------------------------------- #
def simulate(rtl: Path, bench: Bench, work: Path) -> tuple[bool, str]:
    obj = work / "obj_sim"
    rc, log = _run(["verilator", "--binary", "--timing", "-j", "4", "--Mdir", str(obj),
                    "--top-module", "tb", "-o", "simv", str(bench.tb), str(rtl)], work, 900)
    if rc:
        return False, "compile failed:\n" + _tail(log)
    rc, log = _run([str(obj / "simv")], work, 600)
    ok = rc == 0 and re.search(r"^PASS\b", log, re.M) is not None and "FAIL" not in log
    return ok, _tail(log, 12)


# --------------------------------------------------------------------------- #
# Gate 4: logic equivalence (Yosys miter + SAT)
# --------------------------------------------------------------------------- #
def _lec_wrapper(p: dict, bench: Bench) -> str:
    """A formal top that drives both designs with the same inputs and asserts
    their outputs match. An output listed in bench.lec_compare is only compared
    while its qualifier (e.g. a valid flag) is high in the original design -
    that is how "data is don't-care while valid is low" is expressed."""
    ins = [n for n, (d, _) in p.items() if d == "input"]
    outs = [n for n, (d, _) in p.items() if d == "output"]
    w = lambda n: f"[{p[n][1]-1}:0] " if p[n][1] > 1 else ""
    lines = ["module lec_top("]
    lines.append(",\n".join(f"  input wire {w(n)}{n}" for n in ins) + ");")
    for side in ("gold", "gate"):
        for n in outs:
            lines.append(f"  wire {w(n)}{side}_{n};")
        conns = [f".{n}({n})" for n in ins] + [f".{n}({side}_{n})" for n in outs]
        lines.append(f"  lec_{side} u_{side}({', '.join(conns)});")
    seq = bench.clock is not None
    if seq and bench.reset:
        # cycle 0 is the reset cycle; outputs are compared from cycle 1 on
        lines.append("  reg f_init = 1'b1;")
        lines.append(f"  always @(posedge {bench.clock}) f_init <= 1'b0;")
        lines.append(f"  always @* if (f_init) assume ({bench.reset} == 1'b{bench.reset_active});")
    lines.append("  always @* begin")
    guard = "!f_init && " if seq and bench.reset else ""
    for n in outs:
        q = bench.lec_compare.get(n)
        cond = guard + (f"gold_{q}" if q else "1'b1")
        lines.append(f"    if ({cond}) assert (gold_{n} == gate_{n});")
    lines.append("  end")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


SBY = """[options]
mode {mode}
{depth}
timeout {timeout}

[engines]
{engine}

[script]
read_verilog -sv gold.sv
hierarchy -top {top}{chp}
proc
flatten
rename {top} lec_gold
design -stash gold
read_verilog -sv gate.sv
hierarchy -top {top}{chp}
proc
flatten
rename {top} lec_gate
design -stash gate
design -copy-from gold -as lec_gold lec_gold
design -copy-from gate -as lec_gate lec_gate
read_verilog -formal lec_top.sv
prep -top lec_top

[files]
{gold}
{gate}
{wrapper}
"""


def _sby(work: Path, name: str, mode: str, engine: str, depth: int, bench: Bench,
         gold: Path, gate: Path, wrapper: Path, timeout: int) -> tuple[str, str]:
    chp = "".join(f" -chparam {k} {v}" for k, v in bench.lec_params.items())
    cfg = SBY.format(mode=mode, depth=f"depth {depth}" if depth else "", engine=engine,
                     timeout=timeout, top=bench.top, chp=chp, gold=f"gold.sv {gold}",
                     gate=f"gate.sv {gate}", wrapper=f"lec_top.sv {wrapper}")
    # ([files] lines are "<name in the job dir> <source path>")
    f = work / f"{name}.sby"
    f.write_text(cfg)
    rc, log = _run(["sby", "-f", f.name], work, timeout + 120)
    # an engine can report FAIL and the job still end in ERROR if trace conversion fails
    failed = "DONE (FAIL" in log or re.search(r"engine_\d+ \([^)]*\) returned FAIL", log)
    status = ("PASS" if "DONE (PASS" in log else "FAIL" if failed else
              "TIMEOUT" if ("DONE (TIMEOUT" in log or rc == 124) else "UNKNOWN")
    return status, log


def _abc(aig: Path, cmd: str, timeout: int) -> tuple[int, str]:
    return _run(["yosys-abc", "-c", f"read_aiger {aig}; fold; strash; {cmd}"], aig.parent, timeout)


def lec(gold: Path, gate: Path, bench: Bench, work: Path) -> tuple[str, str]:
    """Returns (verdict, log). verdict is PROVEN, BOUNDED(k), or FAIL.

    The miter (lec_top) drives both designs with the same inputs and asserts
    their outputs match; SymbiYosys turns it into an AIGER model. Register
    power-up values are left FREE (as on silicon); reset is held in cycle 0 and
    outputs are compared from cycle 1 on, so a register that loses its reset only
    passes if its power-up value can never reach a compared output.

    combinational:  ABC `dprove` (SAT sweeping + CEC)              -> PROVEN / FAIL
    sequential:     ABC `pdr` (unbounded, time-boxed)                -> PROVEN / FAIL
                    else ABC `bmc3` from reset, time-boxed           -> BOUNDED(k) / FAIL
    """
    p = ports(gold, bench.top, bench.lec_params)
    wrapper = work / "lec_top.sv"
    wrapper.write_text(_lec_wrapper(p, bench))
    seq = bench.clock is not None
    st, log = _sby(work, "lec_prove", "prove", "abc pdr", 0, bench, gold, gate, wrapper,
                   bench.lec_prove_s if seq else 20)
    aig = work / "lec_prove" / "model" / "design_aiger.aig"
    if st == "PASS":
        return "PROVEN", "unbounded proof (abc pdr)"
    if not aig.exists():
        return "FAIL", "could not build the equivalence model:\n" + _tail(log)
    if st == "FAIL" or not seq:
        # find the shallowest mismatch, then replay it with the SMT engine for a readable trace
        rc, out = _abc(aig, f"bmc3 -F {bench.lec_depth} -v", bench.lec_bmc_s + 60)
        m = re.search(r"was asserted in frame (\d+)", out)
        if not seq and not m:
            rc, out = _abc(aig, "dprove", 600)
            if "UNSATISFIABLE" in out or "equivalent" in out or "proved" in out:
                return "PROVEN", "combinational equivalence (abc dprove / CEC)"
            return "FAIL", "equivalence check inconclusive:\n" + _tail(out)
        if m or st == "FAIL":
            depth = int(m.group(1)) + 2 if m else bench.lec_depth
            st2, log2 = _sby(work, "lec_cex", "bmc", "smtbmc z3", depth, bench, gold, gate, wrapper,
                             bench.lec_bmc_s)
            return "FAIL", _cex(work / "lec_cex", log2)
    # bounded check from reset; bmc3 reports how many frames it covered
    n = bench.lec_depth
    rc, out = _abc(aig, f"bmc3 -F {n} -T {bench.lec_bmc_s} -v", bench.lec_bmc_s + 60)
    m = re.search(r"was asserted in frame (\d+)", out)
    if m:
        st2, log2 = _sby(work, "lec_cex", "bmc", "smtbmc z3", int(m.group(1)) + 2, bench, gold, gate,
                         wrapper, bench.lec_bmc_s)
        return "FAIL", _cex(work / "lec_cex", log2)
    frames = [int(m) for m in re.findall(r"^\s*(\d+)\s*[+:]", out, re.M)]
    reached = (max(frames) + 1) if frames else 0
    if "No output asserted in" in out:
        m = re.search(r"No output asserted in (\d+) frames", out)
        reached = int(m.group(1)) if m else n
    if reached >= bench.lec_min_depth:
        return f"BOUNDED({reached})", (f"no mismatch within {reached} cycles of reset; "
                                       f"unbounded proof did not finish in {bench.lec_prove_s}s")
    return "FAIL", (f"inconclusive: bounded check only reached {reached} cycles "
                    f"(need >= {bench.lec_min_depth} to cover the design's latency)")


def _cex(job: Path, log: str) -> str:
    """Summarise the counterexample: the failing assertion and the trace values
    of the compared outputs, cycle by cycle."""
    out = [l.split("engine_0:")[-1].strip(" #") for l in log.splitlines() if "Assert failed" in l][:4]
    vcd = next(job.glob("engine_0/*.vcd"), None)
    if vcd:
        out.append(f"counterexample trace: {vcd}")
        out.extend(_vcd_table(vcd))
    return "\n".join(out) if out else _tail(log)


def _vcd_table(vcd: Path, max_cycles: int = 24) -> list[str]:
    """Tiny VCD reader: per-cycle values of the top-level gold_/gate_ outputs and inputs."""
    ids, names, cur, rows = {}, [], {}, []
    scope = []
    t = None
    for line in vcd.read_text().splitlines():
        tok = line.split()
        if not tok:
            continue
        if tok[0] == "$scope":
            scope.append(tok[2])
        elif tok[0] == "$upscope":
            scope.pop()
        elif tok[0] == "$var" and len(scope) == 1:
            nm = tok[4]
            if not nm.startswith(("f_", "_")):
                ids[tok[3]] = nm
                if nm not in names:
                    names.append(nm)
        elif tok[0].startswith("#"):
            if t is not None:
                rows.append(dict(cur))
            t = int(tok[0][1:])
        elif tok[0][0] in "01xz" and len(tok) == 1 and tok[0][1:] in ids:
            cur[ids[tok[0][1:]]] = tok[0][0]
        elif tok[0][0] == "b" and len(tok) == 2 and tok[1] in ids:
            v = tok[0][1:]
            cur[ids[tok[1]]] = hex(int(v, 2)) if set(v) <= {"0", "1"} else v
    if t is not None:
        rows.append(dict(cur))
    rows = rows[::2][:max_cycles] if len(rows) > 2 else rows   # one row per clock period
    names = [n for n in names if n != "clk"][:14]
    table = ["cycle " + " ".join(names)]
    for i, r in enumerate(rows):
        table.append(f"{i:5d} " + " ".join(str(r.get(n, "?")) for n in names))
    return table


# --------------------------------------------------------------------------- #
# Metrics: Yosys + ABC on sky130_fd_sc_hd (tt_025C_1v80)
# --------------------------------------------------------------------------- #
# Delay-aware mapping close to what OpenROAD-flow-scripts uses for sky130:
# structural choices (&dch), delay-oriented mapping (&nf), then buffering and
# gate sizing, and finally a static timing report (stime) of the mapped logic.
ABC_SCRIPT = ("strash;ifraig;dc2;strash;&get,-n;&dch,-f;&nf,-R,1000;&put;"
              "buffer,-p;upsize;dnsize;topo;stime,-p")
# Same exclusions OpenROAD-flow-scripts applies to sky130hd: low-power-flow,
# probe and clock-only cells are not for general logic.
DONT_USE = "".join(f" -dont_use sky130_fd_sc_hd__{c}" for c in
                   ("lpflow_*", "probe_p_*", "probec_p_*", "clkdlybuf*", "clkbuf_16", "dlygate*", "dlymetal*"))


@dataclass
class PPA:
    area_um2: float
    cells: int
    flops: int
    delay_ps: float
    cell_mix: dict

    def as_dict(self) -> dict:
        return asdict(self)


def synth(rtl: Path, bench: Bench, work: Path) -> PPA:
    lib = liberty()
    chp = "".join(f" -chparam {k} {v}" for k, v in bench.synth_params.items())
    abc_script = work / "abc.script"
    abc_script.write_text("\n".join(ABC_SCRIPT.replace(",", " ").split(";")) + "\n")
    script = (
        f"read_verilog -sv {rtl}; hierarchy -top {bench.top}{chp}; "
        f"synth -top {bench.top} -flatten; "
        f"dfflibmap -liberty {lib}{DONT_USE}; "
        f"abc -liberty {lib}{DONT_USE} -script {abc_script}; "
        "opt_clean -purge; "
        f"tee -o {work / 'stat.json'} stat -json -liberty {lib}"
    )
    rc, log = _run(["yosys", "-p", script], work, 1800)
    if rc:
        raise RuntimeError("synthesis failed:\n" + _tail(log))
    delays = [float(m) for m in re.findall(r"Delay\s*=\s*([\d.]+)\s*ps", log)]
    stat = json.loads((work / "stat.json").read_text())
    top = stat["modules"].get(f"\\{bench.top}") or next(iter(stat["modules"].values()))
    cells = top.get("cells_by_type") or top.get("num_cells_by_type") or {}
    flops = sum(n for c, n in cells.items() if re.search(r"__(df|edf|sdf|dl)", c))
    mix = dict(sorted(((c.replace("sky130_fd_sc_hd__", ""), n) for c, n in cells.items()),
                      key=lambda kv: -kv[1])[:12])
    return PPA(area_um2=round(float(top["area"]), 2), cells=int(top.get("num_cells", 0)),
               flops=flops, delay_ps=round(max(delays) if delays else 0.0, 1), cell_mix=mix)


# --------------------------------------------------------------------------- #
# The full gate chain for one candidate
# --------------------------------------------------------------------------- #
def evaluate(rtl_text: str, bench: Bench, work: Path) -> dict:
    """Run every gate on a candidate; returns a JSON-able verdict."""
    work.mkdir(parents=True, exist_ok=True)
    cand = work / f"{bench.top}.sv"
    cand.write_text(rtl_text)
    res: dict = {"gates": {}}

    try:
        want = ports(bench.original, bench.top)
        got = ports(cand, bench.top)
    except RuntimeError as e:
        res["gates"]["interface"] = {"pass": False, "log": str(e)}
        return res
    diff = {k: (want.get(k), got.get(k)) for k in set(want) | set(got) if want.get(k) != got.get(k)}
    res["gates"]["interface"] = {"pass": not diff,
                                 "log": "" if not diff else f"port mismatch (want, got): {diff}"}
    if diff:
        return res

    ok, log = lint(cand, bench.top)
    res["gates"]["lint"] = {"pass": ok, "log": log}
    if not ok:
        return res

    ok, log = simulate(cand, bench, work)
    res["gates"]["sim"] = {"pass": ok, "log": log}
    if not ok:
        return res

    verdict, log = lec(bench.original, cand, bench, work)
    res["gates"]["lec"] = {"pass": verdict != "FAIL", "verdict": verdict, "log": log}
    if verdict == "FAIL":
        return res

    res["ppa"] = synth(cand, bench, work).as_dict()
    return res


def tool_versions() -> dict:
    v = {}
    for name, cmd in {"yosys": ["yosys", "-V"], "verilator": ["verilator", "--version"]}.items():
        rc, out = _run(cmd, Path.cwd(), 30)
        v[name] = out.strip().splitlines()[0] if out.strip() else "?"
    return v


if os.environ.get("RTLOPT_DEBUG"):
    print(tool_versions())
