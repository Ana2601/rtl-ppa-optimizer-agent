# dual_mac: dual-source multiply-accumulate

Accumulates one of two unsigned products per cycle.

| Port | Dir | Width | Meaning |
|---|---|---|---|
| `clk`, `rst_n` | in | 1 | clock, asynchronous active-low reset |
| `in_valid` | in | 1 | accumulate this cycle |
| `clr` | in | 1 | clear the accumulator (has priority over `in_valid`) |
| `sel` | in | 1 | 1: accumulate `a*b`, 0: accumulate `c*d` |
| `a`,`b`,`c`,`d` | in | W=16 | unsigned operands |
| `acc` | out | 40 | accumulator, wraps modulo 2^40 |
| `out_valid` | out | 1 | `in_valid` delayed by one cycle |

Behaviour (cycle accurate, must be preserved exactly):

- reset: `acc = 0`, `out_valid = 0`
- each clock: `out_valid <= in_valid`; if `clr` then `acc <= 0`, else if `in_valid`
  then `acc <= acc + (sel ? a*b : c*d)`

Only one product is consumed per cycle. Latency and every output, every cycle,
must match the original.

Optimisation goal: **minimise area**; critical-path delay may grow by at most 10 %.
