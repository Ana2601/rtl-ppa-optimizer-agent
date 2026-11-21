---
name: rtl-ppa-optimization
description: How to rewrite synthesisable SystemVerilog for lower area or delay without changing behaviour, and which rewrites actually pay off with Yosys + ABC on sky130. Use when optimising an existing RTL module against a PPA goal.
---

# RTL PPA optimisation playbook

## Ground rules

1. **Behaviour is fixed by the spec, not by the code.** Every output must match the
   original every cycle, except where the spec explicitly says a value is don't-care
   (for example data while `valid` is low). Latency is part of behaviour.
2. **Measure, don't assume.** Yosys and ABC already do a lot (constant folding,
   constant-divisor arithmetic, `$macc` merging of adder chains, FSM re-encoding,
   mux-exclusive sharing of some operators). A textbook rewrite that the tool already
   performs gains nothing, and can lose area by hiding structure from it.
3. **One idea per candidate.** If two changes go in together and the result is worse,
   you cannot tell which one hurt.
4. **Respect both axes.** An area goal usually comes with a delay budget and vice versa.
   Read the constraint before choosing a transform.

## Transforms that pay off (and why the tool misses them)

| Transform | When | Typical effect |
|---|---|---|
| **Operand-level resource sharing**: `sel ? a*b : c*d` becomes `(sel?a:c) * (sel?b:d)` | two expensive operators whose results are muxed | about -40 % area for multipliers. Yosys `share` does not merge them when the operands differ |
| **Symmetric-coefficient folding** (linear-phase FIR): `h[k]*(x[k] + x[N-1-k])` | coefficients mirror | halves the multipliers. The tool cannot see the symmetry across registers |
| **Remove resets from pure datapath registers** | the spec makes the data don't-care until a valid/fill condition that the *control* path still resets | about 20 % flop area (`dfrtp_1` 25.0 um² vs `dfxtp_1` 20.0 um²) |
| **Balanced trees instead of chains** (max/min/argmax, priority, comparisons) | delay goal and the operator is associative | about log2(N)/N of the chain depth. ABC restructures AND/OR logic, but not a chain of comparators feeding muxes |
| **Shared adder/subtractor**: `a + (b ^ {N{sub}}) + sub`, with flags from the carry and sign | area goal and the delay budget allows it | fewer adders, but a longer path through the XOR/carry. Check the delay |
| **Constant multiplies as CSD shift-adds** (`47*x` becomes `(x<<<5)+(x<<<4)-x`) | multiplication by a fixed coefficient, especially a negative one or one sign-extended to a wide result | on `fir8_sym`, -16 % area and -17 % delay. Yosys takes `*` by a constant through a generic multiplier plus constant propagation, which does not reach canonical-signed-digit form |
| **Retiming across registers**: compute next-cycle values from the current state and register *them* | a pre-adder or other logic sits between a register and the critical path, and the next register value is already known one cycle early (shift registers) | takes that logic off the critical path at the cost of some flops. On `fir8_sym` it recovered all the delay folding added and still saved area |

## Transforms that usually do NOT pay off with Yosys

- Replacing `x / CONST` or `x % CONST` with a multiply-and-shift: Yosys already reduces
  constant division well, and the explicit multiplier is often larger.
- Hand-writing a popcount or adder tree for a plain `+` loop: `alumacc`/`maccmap`
  already builds an efficient multi-operand adder.
- One-hot or Gray re-encoding of an FSM: `fsm` re-encodes extracted FSMs itself.
- Re-associating a plain sum into a "balanced tree" by hand: Yosys merges the sum into
  one `$macc` and builds its own tree, so the parentheses are ignored.
- Sharing a subtractor between SUB and the compare ops: `alumacc` already merges `<`
  with `-` on the same operands.
- Sharing ADD and SUB in one adder (`a + (b ^ {N{sub}}) + sub`): it saves 9-17 % area,
  but the mode decode and XOR land in front of the carry chain. On `alu32` it cost
  18-58 % delay, even as a carry-select adder.

## Correctness traps

- **Signed arithmetic widths.** In `YW'(a * b)` the product is computed at the
  operands' self-determined width, then extended, so it can overflow. Extend the
  operands first: `YW'(a) * YW'(b)`.
- **Tie-breaking** in max/argmax trees: let the higher-index side win only when it is
  strictly greater. That keeps "lowest index wins" and matches a linear scan.
- **Reset removal on control state.** Counters, valid bits and FSM state must keep
  their reset. Only registers whose power-up value can never reach a compared output
  may lose it.
- **Interface.** Port names, directions and widths must not change.

## Reading the feedback

- `rejected:lint`: fix the warning. Never suppress it.
- `rejected:sim`: the log shows the first mismatches. Compare them with the spec.
- `rejected:lec`: the counterexample trace shows inputs and both designs' outputs
  per cycle. It is a real behavioural difference (the check runs at reduced
  parameter widths, so it is fast).
- `constraint`: the change worked on one axis but broke the budget on the other.
  Combine it with a transform that buys back that axis.
- `no-gain`: the tool already did this. Try a different class of change.
