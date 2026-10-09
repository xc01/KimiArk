"""Evidence-only report for the bounded APK timing archaeology pass."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class ClientTimingFinding:
    concept: str
    status: str
    evidence: str
    source: str
    confidence: float
    interpretation: str
    simulator_consequence: str


def client_frame_timing_report(client_root: Path = Path("data/client")) -> tuple[ClientTimingFinding, ...]:
    metadata = client_root / "assets/bin/Data/Managed/Metadata/global-metadata.dat"
    source = str(metadata)
    return (
        ClientTimingFinding("battle logical frame counter", "KNOWN", "waveStartFrameCnt, fixedFrameCnt identifiers", source, 0.9, "Client metadata contains battle/wave frame-count state alongside waveStartTime.", "Use integer frame representation; do not infer frequency."),
        ClientTimingFinding("frame duration/frequency", "UNKNOWN", "No recoverable conversion body or authoritative battle-FPS constant", source, 0.15, "A frame index exists, but its wall-clock duration is unresolved.", "Require an explicit configured FrameClock for seconds conversion."),
        ClientTimingFinding("render/physics timing", "KNOWN", "Unity fixedDeltaTime, fixedUnscaledDeltaTime, targetFrameRate identifiers", source, 0.85, "Generic Unity settings are present; they are not proven to be the battle logic clock.", "Do not label render FPS as client logic FPS."),
        ClientTimingFinding("wave frame/time relationship", "UNKNOWN", "waveStartFrameCnt and waveStartTime coexist; arithmetic is not recoverable", source, 0.2, "Both domains are stored, but conversion and speed/pause effects are unconfirmed.", "Keep real spawn timing/frame relation unresolved."),
        ClientTimingFinding("pause and battle speed", "UNKNOWN", "speedLevel accessors and pause-related identifiers; no battle update body", source, 0.2, "Names show configuration/state vocabulary only.", "No speed or pause assumptions in timeline semantics."),
        ClientTimingFinding("DEPLOY command/effect boundary", "UNKNOWN", "deployment-related metadata strings without recoverable transition body", source, 0.15, "Request, acceptance, instantiation, and combat-active frames cannot be separated from static evidence.", "Timeline frame means desired battle action frame, not touch frame."),
        ClientTimingFinding("ACTIVATE_SKILL command/effect boundary", "UNKNOWN", "skill/cast lifecycle identifiers; no activation transition timing body", source, 0.15, "Skill activation representation is possible, but command/effect offset is unresolved.", "Do not add real skill timing offsets."),
        ClientTimingFinding("RETREAT command/effect boundary", "UNKNOWN", "retreat/undeploy vocabulary; no removal/cooldown transition body", source, 0.15, "Removal, block release, refund, and redeploy timing are unresolved.", "Keep retreat frame as an external desired action frame."),
    )
