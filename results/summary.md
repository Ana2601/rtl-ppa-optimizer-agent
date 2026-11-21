| Benchmark | Goal | Original area (um²) | Best area | Original delay (ps) | Best delay | Gain | Equivalence | Attempts (accepted) |
|---|---|---:|---:|---:|---:|---:|---|---|
| `alu32` | area | 2890 | 2890 | 5395 | 5395 | **0.0 %** | - | 9 (0) |
| `argmax8` | delay | 3851 | 4016 | 10074 | 4562 | **54.7 %** | PROVEN | 4 (1) |
| `dual_mac` | area | 19457 | 11119 | 9230 | 8477 | **42.9 %** | PROVEN | 3 (1) |
| `fir8_sym` | area | 15914 | 10254 | 6478 | 4630 | **35.6 %** | PROVEN | 5 (3) |

### alu32

| # | Verdict | Area (um²) | Delay (ps) | Rationale |
|---|---|---:|---:|---|
| 1 | constraint (PROVEN) | 2472.37 | 7391.3 | One shared 33-bit adder/subtractor for ADD/SUB/SLT/SLTU; flags from carry and sign. |
| 2 | no-gain (PROVEN) | 2941.57 | 5314.7 | Compute a == b as ~\|(a ^ b), sharing the XOR array with the XOR op. |
| 3 | constraint (PROVEN) | 2941.57 | 5722.6 | Dedicated adder for ADD; one 33-bit subtractor shared by SUB, SLT, SLTU. |
| 4 | rejected:lint | - | - | Shared adder with the carry-in folded in: {1'b0,a,1'b1} + {1'b0,b^sub,sub}. |
| 5 | constraint (PROVEN) | 2411.06 | 8513.7 | Same as previous, with t[0] explicitly consumed by an unused_ signal. |
| 6 | constraint (PROVEN) | 2636.28 | 6375.8 | Shared adder/subtractor as a 2 x 16-bit carry-select adder. |
| 7 | rejected:lint | - | - | Shared adder/subtractor as a 4 x 8-bit carry-select adder. |
| 8 | rejected:lint | - | - | Same 4 x 8-bit carry-select, with the block carries as explicit assigns. |
| 9 | constraint (PROVEN) | 2707.6 | 6454.0 | Same as previous, without the unused c[0]. |

Area/delay Pareto front (constraints ignored; #0 = original): #5 (2411 um², 8514 ps), #1 (2472 um², 7391 ps), #6 (2636 um², 6376 ps), #0 (2890 um², 5395 ps), #2 (2942 um², 5315 ps)

Agent summary: No candidate met the 5 % delay budget, so the original stands. Yosys already shares the compare logic with the subtractor and the equality with the XOR. Sharing ADD and SUB in one adder buys area at a large delay cost; Pareto points measured: -9 % area at +18 % delay (16-bit carry-select), -14 % at +37 %, -17 % at +58 %.


### argmax8

| # | Verdict | Area (um²) | Delay (ps) | Rationale |
|---|---|---:|---:|---|
| 1 | accepted (PROVEN) | 4016.35 | 4562.5 | Tournament tree (3 comparator levels) instead of a 7-step linear scan; the right side wins only when strictly greater. |
| 2 | constraint (PROVEN) | 7682.37 | 3004.9 | All-pairs comparison: lane i wins if >= every lower lane and > every higher lane; one-hot AND-OR output mux. |
| 3 | constraint (PROVEN) | 4769.57 | 3909.5 | Hybrid: pairwise level, then all-pairs over the 4 survivors. |
| 4 | constraint (PROVEN) | 4810.86 | 3514.1 | Hybrid with exactly one comparator per survivor pair; the opposite relation is its negation. |

Area/delay Pareto front (constraints ignored; #0 = original): #0 (3851 um², 10074 ps), #1 (4016 um², 4562 ps), #3 (4770 um², 3910 ps), #4 (4811 um², 3514 ps), #2 (7682 um², 3005 ps)

Agent summary: Tournament tree: -55 % delay at +4 % area, proven equivalent. Faster structures exist (all-pairs: -70 % delay; hybrid: -61 % to -65 %), but they need 1.24x to 2x the area, outside the spec's 1.2x budget. They are on the Pareto front if the budget changes.


### dual_mac

| # | Verdict | Area (um²) | Delay (ps) | Rationale |
|---|---|---:|---:|---|
| 1 | accepted (PROVEN) | 11119.41 | 8477.0 | Operand-level resource sharing: (sel ? a : c) * (sel ? b : d) instead of muxing two products. |
| 2 | rejected:lec (FAIL) | - | - | Drop the async reset from acc (clr already zeroes it); keep it on out_valid. |
| 3 | no-gain (PROVEN) | 11418.45 | 8109.2 | acc <= (acc & ~clr) + (p & (in_valid & ~clr)): no muxes in front of the accumulator flops. |

Area/delay Pareto front (constraints ignored; #0 = original): #1 (11119 um², 8477 ps), #3 (11418 um², 8109 ps)

Agent summary: Sharing one multiplier between the two operand pairs is the big win (-43 % area, also faster). Removing the accumulator reset is not legal (acc is observable right after reset; formal caught what simulation missed). Masking instead of muxing did not help.


### fir8_sym

| # | Verdict | Area (um²) | Delay (ps) | Rationale |
|---|---|---:|---:|---|
| 1 | constraint (PROVEN) | 11033.08 | 7308.9 | Fold symmetric taps (4 multipliers behind pre-adders) and drop the reset from the delay line and y; control registers keep their reset. |
| 2 | accepted (PROVEN) | 15282.16 | 6425.8 | Only remove the reset from the datapath registers (delay line, y); keep the direct-form multipliers. |
| 3 | constraint (PROVEN) | 11000.55 | 7676.1 | Fold the taps and sum the 4 products as (p0+p1)+(p2+p3) to recover the pre-adder delay. |
| 4 | accepted (PROVEN) | 12174.18 | 5584.2 | Fold the taps with the pre-adders retimed into registers (sums computed from the current delay line for the next cycle); tap[7] disappears. Datapath stays reset-free. |
| 5 | accepted (PROVEN) | 10253.58 | 4630.4 | Write the constant multiplies as canonical-signed-digit shift-adds: 3=2+1, -11=-16+4+1, 25=16+8+1, 47=32+16-1. |

Area/delay Pareto front (constraints ignored; #0 = original): #5 (10254 um², 4630 ps)

Agent summary: Three transforms stacked: (1) no reset on datapath registers whose contents are don't-care until the fill counter (which keeps its reset) raises out_valid; (2) symmetric-tap folding with the pre-adders retimed into registers, which removes 4 multipliers without adding delay; (3) CSD shift-adds for the constant multiplies. A balanced adder tree did nothing: Yosys rebuilds the sum itself.

