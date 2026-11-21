# fir8_sym: 8-tap linear-phase FIR filter

`y[n] = sum_{k=0..7} h[k] * x[n-k]` with the symmetric coefficient set
`h = [3, -11, 25, 47, 47, 25, -11, 3]`. Signed 12-bit samples in, signed 24-bit out.

| Port | Dir | Width | Meaning |
|---|---|---|---|
| `clk`, `rst_n` | in | 1 | clock, asynchronous active-low reset |
| `in_valid` | in | 1 | `x` carries a new sample this cycle |
| `x` | in | 12 | signed input sample |
| `y` | out | 24 | signed filter output |
| `out_valid` | out | 1 | `y` holds a valid output this cycle |

Timing: a sample presented in cycle t produces its output in cycle t+2
(`out_valid` high for exactly that cycle).

Validity: `out_valid` is only raised once the delay line has received 8 samples
since reset. **`y` is don't-care whenever `out_valid` is low** - downstream logic
never samples it then. `out_valid` itself must match the original every cycle.

Optimisation goal: **minimise area**; the critical-path delay may grow by at most 10 %.
