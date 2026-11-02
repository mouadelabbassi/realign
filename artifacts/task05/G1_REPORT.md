# REALIGN G1 — Physics Verification Report

**Status:** PASS (tested synthetic physics only)

## Evidence

| Check | Result |
|---|---:|
| Randomized ideal peg configurations | 250 |
| Failures | 0 |
| Total contact/free transitions | 1516 |
| Maximum absolute energy drift, J/kg | 1.710e-09 |
| Maximum Cartesian position jump at contact, m | 1.985e-15 |
| Maximum Cartesian speed jump (lossless), m/s | 4.441e-16 |
| Vertical peg period error against elliptic-integral oracle, s | 6.247757866617576e-11 |

## Assumptions

- Point-mass bob, inextensible string, one planar degree of freedom.
- Point-like, fixed peg; a single designated wrapped side (not contact on both sides).
- Contact transition is ideal and lossless for this randomized suite.
- String remains taut; unsupported slack conditions cause explicit failure.
- The initial release is on the free side of the peg.
- These simulations use *synthetic* states and do not prove experimental identifiability.

## Next gates

- **G2:** Obtain real SAM video masks, calibrated bob tracking and measured camera uncertainty.
- **G3:** Fit baseline models to separate exploration data and evaluate detectability.
- **Meta smoke test:** Requires a local `MODEL_API_KEY`; it has NOT been executed here.

Reproduce with `python scripts/verify_g1.py` from the repository root after installing the package.
