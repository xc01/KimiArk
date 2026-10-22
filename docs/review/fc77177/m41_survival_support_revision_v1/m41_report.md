# M41 survival-support R8-7 tactical revision

## Scope and budget

- M39 remains **CLI 4/4, simulations 2/4**; M40 remains **CLI 2/2,
  simulations 1/2**. M41 used **3/3** newly authorized tactical CLI starts and
  **2/3** fixed simulations (1 inherited from M39's remaining allowance plus 2
  new M41 simulations). The final simulation slot was intentionally not spent
  because V3 was statically blocked after the last CLI start.
- Model/provider: `openai` / `gpt-6.1-sol` / `high` with
  `features.apps=false`. No retry, resume, or model/account change occurred.
- Mechanics version remains `m38b-2781-animation-speed-v1`, a 2.7.81 candidate
  model, not build-2771 equality.

| Attempt | Plan | Contract | Static | Simulation | Result |
|---:|---|---|---|---|---|
| 1 | `R8_7_GPT_M41_V1` | PASS | PASS | LOSS | 19 kills / 14 leaks / 9 operator deaths / life -12 |
| 2 | `R8_7_GPT_M41_V2` | PASS | PASS | LOSS | 8 kills / 25 leaks / 11 operator deaths / life -24 |
| 3 | `R8_7_GPT_M41_V3` | PASS | FAIL | none | Hibiscus redeploy at frame 6600 had cooldown active |

Prompt SHA-256 values:

- V1: `18b6bfa63dc0e6f38c2272774e70d93c300e9bb56e702bf2a19f05c9f243b87d`
- V2: `e0765a9f91e9be7761751bd908533c4993eed0d583e0db0987869c109a180a38`
- V3: `7d5f45ff7044c0b2719f77b47c78563b57dcf3d92340af8d4c51d844af2e0d48`

Compressed requests, responses, checks, events, summaries, snapshots, manifests
and per-file hashes are in `evidence/manifest_v1.json`.

## Input and capability correction

The M40 report was corrected: V2 did include 1-star GALLUS² and 2-star 12F.
Steward's highest-defense priority was verified as runtime behavior with a
synthetic two-target regression: a 1500-DEF candidate was selected over a
500-DEF candidate at equal distance. The support tag is now
`RUNTIME_SUPPORTED_HIGH_DEFENSE_PRIORITY`; exact client tie-breaking and ordering
remain UNKNOWN. `tests/simulator` passed with 125 tests after this correction.

## V1 replay

V1 closed the specific M40 V2 support gap. Ansel actually healed Steward seven
times for 3236.80 from frames 2893–3409, including shell damage responses. The
declared first observable was verified at frame 2893. Steward dealt 19 hits and
5629.66 damage to the artillery from frames 2161–3460. This proves the selected
support chain existed, not that treatment throughput was sufficient.

Steward still received five 910.00 shell hits and died at frame 3493. Durin added
two hits / 340.00 damage, but artillery survived and leaked at 5759. The first
hard-goal violation was leak `enemy_1107_uoffcr#11` at frame 3065. `#14` reached
safely at 10133; `#3` died at 5353 from artillery. Four roadblocks were
eventually destroyed. The first observable verifies support only; it does not
prove zero leaks, protected safety, or full tactical success.

## V2 replay

V2 regressed. Its declared opening event—Ansel healing Vanilla during frames
1260–1350—was not observed. Vanilla died at frame 792, the first leak occurred at
frame 881 (`enemy_1108_uterer#1`), and life first reached zero at frame 1535. The
plan produced only two HEAL events, killed 8 enemies, leaked 25, destroyed only
roadblock #3, and neither protected target arrived. This falsifies V2's opening
support hypothesis and its early survivability arrangement.

## V3 static stop

V3 was contract-valid, but the frozen static check found exactly one conflict:
action index 33, `char_120_hibisc` redeploy at frame 6600 on JSON tile `[2,3]`,
reported `REDEPLOY_COOLDOWN_ACTIVE`. The action was not repaired or simulated.
One simulation remains unused.

## Branch comparison

| Plan | WIN | Kills | Leaks | Protected targets | Roadblocks | Operators dead | Life | Artillery damage |
|---|---|---:|---:|---|---:|---:|---:|---:|
| M30 V2 | LOSS | 20 | 13 | both reached | all four | 10 | -10 | 23 / 6626.06 |
| M31 V3 | LOSS | 22 | 11 | `#3` died; `#14` reached | three | 10 | -9 | 29 / 7959.67 |
| M39 V3 | LOSS | 19 | 14 | both reached | all four | 5 | -11 | 20 / 5822.17 |
| M39 V4 | LOSS | 17 | 16 | both died | one | 10 | -15 | 27 / 7609.45 |
| M40 V2 | LOSS | 15 | 18 | `#3` died; `#14` reached | all four | 10 | -16 | 20 / 5696.47 |
| M41 V1 | LOSS | 19 | 14 | `#3` died; `#14` reached | all four | 9 | -12 | 21 / 5969.66 |
| M41 V2 | LOSS | 8 | 25 | both died | one | 11 | -24 | 19 / 4755.88 |
| M41 V3 | LOSS | — | — | — | — | — | — | no simulation |

M41 V1 is the locally useful branch because it produced verified key support and
the best M41 result, but it is not promoted to a WIN and should not be treated as
a complete solution. V2's regression does not invalidate V1's observed support
edge. V3 remains a blocked candidate.

## Status

- These are candidate-model simulator diagnostics, not simulator WIN, perfect
  WIN, probabilistic WIN, faithful, robust, or real-device claims.
- The next tactical decision must treat low-leak interception, artillery
  throughput, and protected-target exposure as jointly required. Repairing only
  one support edge was insufficient.
- A later revision must first supply a contract/static-valid candidate; the
  remaining simulation may then be used without increasing M41 authorization.
