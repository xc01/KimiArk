# M67 Closeout

M67 did **not** produce an 8-ID current-model fixed-simulator WIN. The best verified result remains the frozen M52 V1 **9-ID WIN**. This is not a proof of 8-ID impossibility, real-game performance, robustness, probability, or global minimality.

Budget ended at **CLI 3/3** and **simulation 2/3**. The unused simulation did not transfer. V3's real CLI process started and exited 1 without a structured plan; repeated `codex_models_manager` model-refresh requests timed out. It was not retried, was not a tactical LOSS, and did not enter static, preflight-before-reservation completion, or `Simulator.run`.

## Loops

1. **V1 — `M67_SPOT_OUTER_MEDICAL_BRIDGE`**: 8 IDs, 33 actions. Contract, execution input, and static checks passed with 0 conflicts/unknowns. Loss: 26 kills / 7 leaks / 6 deaths / life -4. The expected Ansel→Friston HEAL occurred at 1321, and Friston survived to 4869. Steward killed artillery #0 at 4453 after 45 hits totaling 13227.21. Both protected targets reached (`#3@10249`, `#14@15249`). The unresolved break was the central mixed-damage cascade: Ansel@3793, Hibiscus@4393, Steward@4617, Fang@4705, Friston@4869, Melantha@5907. After that, #21 leaked@5104 and #34 leaked@6996.
2. **V2 — `M67_RESERVED_SECOND_BARRAGE`**: 8 IDs, 31 actions. Contract, execution input, and static checks passed with 0 conflicts/unknowns. Loss: 21 / 12 / 7 / life -10. Its expected Ansel→Steward HEAL occurred at 3647, but Ansel and Steward died together at 3793. Steward dealt only 8369.57 to artillery before death; artillery leaked at 5759 and killed protected #3 at 5353. #34 had zero operator damage/BLOCK and leaked at 6996.
3. **V3**: real CLI start counted 3/3, but Codex exited 1 after repeated model-refresh timeouts. No final plan or structure selection existed, so no static, simulation, WIN/LOSS, or replacement result was generated.

## Contribution Assessment

The supplied M52 contribution table identified Friston as the unique central three-block holder and #34 killer, Steward as the unique artillery killer and roadblock #1 destroyer, Midnight as the largest observed interception output, and Beagle as the permanent two-block successor. It also warned that low total healing for medics understated timing value. GPT was free to replace or delete any role.

V1 tested that warning directly: removing Lancet and replacing Beagle with Spot kept artillery and protected-route closure, but did not preserve the central blockade/healing chain. V2 reserved medical skills for the historical shared-barrage window; the predicted heal occurred, yet both central medics and Steward still failed at 3793. Thus neither V1 nor V2 established an 8-ID WIN, and V3 generated no new tactical evidence.
