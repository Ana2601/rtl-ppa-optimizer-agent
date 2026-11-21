# argmax8: registered arg-max over 8 lanes

Finds the largest of eight unsigned W=16-bit lanes and its index, one result per cycle.

| Port | Dir | Width | Meaning |
|---|---|---|---|
| `clk`, `rst_n` | in | 1 | clock, asynchronous active-low reset |
| `in_valid` | in | 1 | capture a result this cycle |
| `lanes` | in | 8*W | lane i is `lanes[i*W +: W]` |
| `max_val` | out | W | largest lane value |
| `max_idx` | out | 3 | index of the largest lane; **ties go to the lowest index** |
| `out_valid` | out | 1 | `in_valid` delayed by one cycle |

Cycle behaviour (must be preserved exactly): on reset all outputs are 0. Each clock,
`out_valid <= in_valid`, and when `in_valid` is high `max_val`/`max_idx` load the
arg-max of `lanes`; otherwise they hold.

Optimisation goal: **minimise the critical-path delay** (this block sits on a
scheduler's critical path); area may grow by at most 20 %. Latency must stay 1 cycle.
