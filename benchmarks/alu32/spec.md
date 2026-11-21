# alu32: 32-bit integer ALU

Purely combinational.

| `op` | Name | `y` |
|---|---|---|
| 0 | ADD | `a + b` (mod 2^32) |
| 1 | SUB | `a - b` (mod 2^32) |
| 2 | SLT | 1 if `a < b` as signed two's-complement, else 0 |
| 3 | SLTU | 1 if `a < b` as unsigned, else 0 |
| 4 | AND | `a & b` |
| 5 | OR | `a \| b` |
| 6 | XOR | `a ^ b` |
| 7 | SEQ | 1 if `a == b`, else 0 |

Every `op` value is legal and must give exactly this result for all inputs.

Optimisation goal: **minimise area**; the critical-path delay may grow by at most 5 %.
