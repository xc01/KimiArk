# PRTS roadblock targeting evidence

Access date: 2026-10-14 (Asia/Shanghai).

## Source pages

- Roadblock: <https://prts.wiki/w/道路障碍物>
- Selector: <https://prts.wiki/w/选择器>

Full HTML copies are committed at `data/prts/roadblock.html` and
`data/prts/selector.html`.

## Relevant facts

- The roadblock page describes an enemy-faction device with taunt level `-1`,
  and says it is not easily targeted by friendly units.
- The selector page describes target filtering and sorting over a candidate
  list; taunt filtering/sorting applies after candidate filtering and other
  secondary filters, not as a map-wide gate based on any enemy existing.
- Fixed GameData `character_table.json` for `trap_020_roadblock` records HP
  `8000`, DEF `200`, RES `20`, and taunt level `-1`.

## Implementation boundary

`m19.1-local-device-target-v1` removes the unsupported global
`any(active non-neutral enemy)` gate. A device is considered only after the
same operator's ordinary target function has no optional local enemy candidate.
The local candidate must satisfy the operator's range. The simulator chooses
the lowest device ID when multiple local devices remain; exact client ordering
among multiple devices remains UNKNOWN.

This is a deterministic current-model correction. The historical global-gate
simulations remain historical-only and are not evidence of client semantics.
