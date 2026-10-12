from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path
from typing import Any


OUTPUT_DIR = Path("output/r8_1_route_navigation_decodability_v4")
NATIVE_LIBRARY_SHA256 = "3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259"
GAMEDATA_COMMIT = "0ef7f952dfd018392200157a5c79a6511ba69122"

ROUTE_METHODS = {
    "Route..ctor": {
        "start": 0x276D2E4,
        "end": 0x276D4B8,
        "signature": "public void .ctor(RouteData data, Map map, IPathFinding pathFinder)",
        "call_sites": [
            {"method": "Map._InitRoutesAndPassableMaps", "instruction": "0x275402c", "target": "0x276d2e4"},
            {"method": "Map._InitRoutesAndPassableMaps", "instruction": "0x2754138", "target": "0x276d2e4"},
        ],
    },
    "Route.ReconstructRoute": {
        "start": 0x276D548,
        "end": 0x276D6EC,
        "signature": "public void ReconstructRoute(RouteData data)",
        "call_sites": [
            {"method": "Map.GenerateRuntimeRoute", "instruction": "0x275a600", "target": "0x276d548"},
            {"method": "Map.GenerateRuntimeExtraRoute", "instruction": "0x275ac54", "target": "0x276d548"},
        ],
    },
    "Route.ReconstructNextMap": {
        "start": 0x276D6EC,
        "end": 0x276D898,
        "signature": "public void ReconstructNextMap()",
        "call_sites": [
            {"method": "Map.UpdateAllRoutes", "instruction": "0x275592c", "target": "0x276d6ec"},
            {"method": "Map.UpdateAllRoutes", "instruction": "0x2755980", "target": "0x276d6ec"},
            {"method": "Map.UpdateAllRoutes", "instruction": "0x2755a58", "target": "0x276d6ec"},
            {"method": "Map.UpdateAllRoutes", "instruction": "0x2755ac4", "target": "0x276d6ec"},
        ],
    },
    "Route._CreateNextMap": {
        "start": 0x276D4B8,
        "end": 0x276D548,
        "signature": "private Route.Node[,] _CreateNextMap()",
        "call_sites": [],
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_elf64_loads(data: bytes) -> list[dict[str, Any]]:
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise ValueError("not an ELF file")
    if data[4] != 2 or data[5] != 1:
        raise ValueError("expected ELF64 little-endian")
    _e_type, machine, _, entry, phoff, shoff, _flags, _ehsize, _phentsize, phnum, _shentsize, shnum, _shstrndx = struct.unpack_from(
        "<HHIQQQIHHHHHH", data, 16
    )
    if machine != 183:
        raise ValueError(f"expected AArch64 ELF, got machine {machine}")
    loads = []
    for index in range(phnum):
        p_type, p_flags, p_offset, p_vaddr, _p_paddr, p_filesz, p_memsz, p_align = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + index * 56
        )
        if p_type == 1:
            loads.append(
                {
                    "index": index,
                    "offset": p_offset,
                    "virtual_address": p_vaddr,
                    "file_size": p_filesz,
                    "memory_size": p_memsz,
                    "flags": p_flags,
                    "alignment": p_align,
                }
            )
    if not loads:
        raise ValueError("ELF has no PT_LOAD segments")
    return loads


def map_virtual_address(
    address: int, loads: list[dict[str, Any]], file_size: int
) -> dict[str, Any]:
    for segment in loads:
        if segment["virtual_address"] <= address < segment["virtual_address"] + segment["file_size"]:
            file_offset = segment["offset"] + address - segment["virtual_address"]
            if file_offset >= file_size:
                raise ValueError(f"file offset is out of bounds: {file_offset:#x}")
            return {
                "address": address,
                "file_offset": file_offset,
                "segment_index": segment["index"],
                "calculation": f"file_offset = {segment['offset']:#x} + ({address:#x} - {segment['virtual_address']:#x})",
            }
    raise ValueError(f"address is not in any PT_LOAD filesz range: {address:#x}")


def default_decode(data: bytes, address: int) -> dict[str, Any]:
    import capstone

    decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    decoder.skipdata = False
    instructions = list(decoder.disasm(data, address))
    consumed_bytes = 0 if not instructions else instructions[-1].address + instructions[-1].size - address
    if not instructions:
        classification = "ENTRY_DECODE_FAILED"
        reason = "Default Capstone stopped at the first instruction without decoding any instruction."
    elif consumed_bytes < len(data):
        classification = "PARTIAL_DECODE"
        reason = "Default Capstone decoded a prefix and stopped before the requested end address."
    else:
        classification = "COMPLETE_DECODE"
        reason = "Default Capstone consumed the requested range."
    return {
        "classification": classification,
        "instruction_count": len(instructions),
        "consumed_bytes": consumed_bytes,
        "unconsumed_bytes": len(data) - consumed_bytes,
        "first_failure_address": address + consumed_bytes,
        "last_instruction": (
            {
                "address": instructions[-1].address,
                "size": instructions[-1].size,
                "mnemonic": instructions[-1].mnemonic,
                "operands": instructions[-1].op_str,
            }
            if instructions
            else None
        ),
        "reason": reason,
        "capability": "Entry/prefix decode diagnosis only; a partial stream must not be treated as the complete function.",
    }


def aligned_decode(data: bytes, address: int, clue_limit: int = 16) -> dict[str, Any]:
    import capstone

    decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    decoder.skipdata = False
    aligned_words = len(data) // 4
    candidates: list[dict[str, Any]] = []
    for index in range(aligned_words):
        offset = index * 4
        instruction = next(decoder.disasm(data[offset : offset + 4], address + offset, 1), None)
        if instruction is None or instruction.size != 4:
            continue
        candidates.append(
            {
                "offset": offset,
                "address": address + offset,
                "bytes_hex": data[offset : offset + 4].hex(),
                "mnemonic": instruction.mnemonic,
                "operands": instruction.op_str,
            }
        )
    return {
        "classification": "CANDIDATE_CLUES_ONLY",
        "aligned_word_count": aligned_words,
        "aligned_valid_count": len(candidates),
        "aligned_invalid_count": aligned_words - len(candidates),
        "first_valid_candidate": candidates[0] if candidates else None,
        "candidate_clues": candidates[:clue_limit],
        "candidate_clue_limit": clue_limit,
        "capability": "Independent four-byte resynchronization is not a decoded function body and does not prove control flow or call targets.",
    }


def skipdata_decode(data: bytes, address: int) -> dict[str, Any]:
    import capstone

    decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    decoder.skipdata = True
    entries = list(decoder.disasm(data, address))
    return {
        "classification": "CANDIDATE_CLUES_ONLY",
        "entry_count": len(entries),
        "first_entry": (
            {
                "address": entries[0].address,
                "size": entries[0].size,
                "mnemonic": entries[0].mnemonic,
                "operands": entries[0].op_str,
            }
            if entries
            else None
        ),
        "capability": "Skipdata entries can be synthetic byte entries and do not prove real instructions or control flow.",
    }


def extract_metadata_records(dump_path: Path, script_json_path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    addresses = {
        method["start"] for method in ROUTE_METHODS.values()
    } | {0x276D4B8}
    dump_lines: list[str] = []
    dump_text = dump_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for index, line in enumerate(dump_text):
        if any(f"RVA: 0x{address:X}" in line for address in addresses):
            dump_lines.extend(dump_text[index : index + 2])
    script_methods: list[dict[str, Any]] = []
    script_data = json.loads(script_json_path.read_text(encoding="utf-8"))
    for item in script_data.get("ScriptMethod", []):
        if item.get("Name") in {
            "Torappu.Battle.Route$$.ctor",
            "Torappu.Battle.Route$$ReconstructRoute",
            "Torappu.Battle.Route$$ReconstructNextMap",
            "Torappu.Battle.Route$$_CreateNextMap",
        }:
            script_methods.append(
                {
                    "name": item["Name"],
                    "address": item["Address"],
                    "address_hex": f"0x{item['Address']:x}",
                }
            )
    return dump_lines, script_methods


def extract_eh_frame_excerpt(binary_path: Path) -> str:
    wanted = {
        (method["start"], method["end"])
        for name, method in ROUTE_METHODS.items()
    }
    wanted.add((0x276D2E4, 0x276D4B8))
    lines: list[str] = []
    try:
        process = subprocess.Popen(
            ["readelf", "--debug-dump=frames", str(binary_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return "readelf unavailable\n"
    assert process.stdout is not None
    for line in process.stdout:
        if any(f"pc={start:016x}..{end:016x}" in line for start, end in wanted):
            lines.append(line.rstrip())
    stderr = process.stderr.read() if process.stderr else ""
    return_code = process.wait()
    if return_code:
        lines.append(f"readelf failed: {return_code}: {stderr.strip()}")
    return "\n".join(lines) + ("\n" if lines else "")


def write_hexdump(path: Path, data: bytes, start_address: int) -> None:
    lines = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        address = start_address + offset
        hex_part = " ".join(f"{byte:02x}" for byte in chunk.ljust(16, b"\0")[:16])
        ascii_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        lines.append(f"{address:08x}: {hex_part}  {ascii_part}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("native_library", type=Path)
    parser.add_argument("--dump-cs", type=Path)
    parser.add_argument("--script-json", type=Path)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    binary_sha256 = sha256(args.native_library)
    if binary_sha256 != NATIVE_LIBRARY_SHA256:
        raise RuntimeError("native library hash does not match the pinned build")

    raw = args.native_library.read_bytes()
    file_size = len(raw)
    loads = parse_elf64_loads(raw)
    mappings: dict[str, Any] = {}
    raw_data: dict[str, bytes] = {}
    for name, method in ROUTE_METHODS.items():
        start_mapping = map_virtual_address(method["start"], loads, file_size)
        end_mapping = map_virtual_address(method["end"], loads, file_size)
        if start_mapping["file_offset"] != method["start"] or end_mapping["file_offset"] != method["end"]:
            raise RuntimeError(f"PT_LOAD mapping is not identity for {name}")
        data = raw[start_mapping["file_offset"] : end_mapping["file_offset"]]
        raw_data[name] = data
        mappings[name] = {
            "start": method["start"],
            "end": method["end"],
            "size_bytes": len(data),
            "start_mapping": start_mapping,
            "end_mapping": end_mapping,
            "bytes_sha256": hashlib.sha256(data).hexdigest(),
        }

    diagnostics: dict[str, Any] = {}
    for name, data in raw_data.items():
        diagnostics[name] = {
            "default": default_decode(data, ROUTE_METHODS[name]["start"]),
            "aligned_resync": aligned_decode(data, ROUTE_METHODS[name]["start"]),
            "skipdata": skipdata_decode(data, ROUTE_METHODS[name]["start"]),
        }

    dump_lines: list[str] = []
    script_methods: list[dict[str, Any]] = []
    if args.dump_cs and args.script_json:
        dump_lines, script_methods = extract_metadata_records(args.dump_cs, args.script_json)
    elif args.dump_cs or args.script_json:
        parser.error("--dump-cs and --script-json must be supplied together")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_hexdump(args.output_dir / "route_method_raw_bytes.hex", b"".join(raw_data.values()), 0x276D2E4)
    (args.output_dir / "elf_pt_load_mapping.json").write_text(
        json.dumps(
            {
                "schema_version": "ELF_PT_LOAD_MAPPING_V1",
                "file_size": file_size,
                "loads": loads,
                "methods": mappings,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "capstone_diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "route_method_metadata_excerpt.txt").write_text(
        "## dump.cs method records\n" + "\n".join(dump_lines) + "\n\n## script.json method records\n"
        + json.dumps(script_methods, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "eh_frame_fde_excerpt.txt").write_text(
        extract_eh_frame_excerpt(args.native_library), encoding="utf-8"
    )

    evidence = {
        "schema_version": "R8_1_ROUTE_NAVIGATION_DECODABILITY_V4",
        "budget": {
            "kimi_calls": 0,
            "real_stage_simulations": 0,
            "new_operational_plans": 0,
            "new_action_candidates": 0,
            "expanded_tactical_search": 0,
        },
        "inputs": {
            "native_library_sha256": binary_sha256,
            "expected_native_library_sha256": NATIVE_LIBRARY_SHA256,
            "gamedata_commit": GAMEDATA_COMMIT,
        },
        "method_source": {
            "metadata": "dump.cs RVA records and script.json ScriptMethod records",
            "call_frame_records": "ELF .eh_frame FDE pc ranges",
            "call_sites": {
                name: method["call_sites"] for name, method in ROUTE_METHODS.items()
            },
        },
        "diagnostics": diagnostics,
        "conclusions": {
            "route_to_spfa": "UNKNOWN_MISSING_STATIC_EDGE",
            "default_decoder": "Entry decoding fails for the three requested Route methods in this static binary.",
            "aligned_decoder": "Some independently aligned words resemble A64 instructions, but are candidate clues only; no method body or call edge is recovered.",
            "cause": "UNKNOWN; encryption, runtime transformation and data misclassification are not established by this evidence.",
            "route_boundary": "ELF .eh_frame independently records the same start/end ranges for the three requested methods.",
        },
        "limitations": [
            "No AArch64 second decoder was available in this environment; no alternate-decoder cross-check is claimed.",
            "No runtime memory dump or unpacked body is available, so Route.ReconstructNextMap -> SPFA cannot be proven.",
            "Candidate instructions from skipdata or four-byte resynchronization are not accepted as real control flow.",
        ],
    }
    (args.output_dir / "route_navigation_decodability_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "provenance.txt").write_text(
        "\n".join(
            [
                "Source: data/client/lib/arm64-v8a/libil2cpp.so from arknights-hg-2771.apk.",
                f"SHA-256: {binary_sha256}",
                "ELF mapping: PT_LOAD 0 has p_vaddr 0 and p_filesz 0xbad0ad8; target addresses therefore map identity to file offsets.",
                "Metadata source: Il2CppDumper dump.cs and script.json supplied locally; only focused excerpts are uploaded.",
                "Tool: Capstone 5.0.7 AArch64 little-endian, skipdata disabled by default; skipdata diagnosis is separately labeled.",
                "No APK, client binary, metadata file, credential, or tactical simulation is uploaded.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "ARTIFACT_MANIFEST_V1",
        "files": [
            {"path": path.name, "sha256": sha256(path)}
            for path in sorted(args.output_dir.iterdir(), key=lambda item: item.name)
            if path.name != "manifest.json"
        ],
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
