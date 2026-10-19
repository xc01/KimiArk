---
name: KimiArk Tactical Loop
description: Run the existing KimiArk read-only observation, contract, and budgeted simulation loop without editing tactics directly.
---

# KimiArk Tactical Loop

1. Call `get_mechanism_facts`; separate GameData facts, current-model rules and UNKNOWN.
2. Call `query_applicable_experience` with stage, mechanics version, failure category, responsibilities and exact prior plan when available. Do not cite or reuse `INVALIDATED` records.
3. Let the tactical model choose structure and actions. Record hypothesis, changed responsibilities, one observable event, and absence interpretation.
4. Call `check_plan_contract` before any simulation. Contract failures are not battle evidence.
5. Call `prepare_frozen_plan_evaluation`. If not `AUTHORIZED`, do not simulate; report budget, lock, immutability, or static reason.
6. Only an authorized call to `evaluate_frozen_plan` may start one deterministic fixed-action simulation in a new immutable diagnostic directory.
7. Call `get_status_and_feedback`; classify `A_CONTRACT_INVALID`, `B_STATIC_CONFLICT`, `B_PROGRAM_OR_MECHANISM_UNKNOWN`, `C_LEGAL_BATTLE_LOSS`, or `D_CURRENT_MODEL_WIN`. Verify prediction separately from full-plan success.
8. Treat simulator WIN, perfect objective scope, targeting variants, faithful certificates and real-game play as separate claims. Operator deaths are recorded but are not an automatic perfect-run veto.
