#!/usr/bin/env python3
"""Decode a build-2771 signed FlatLookup ResourceManifest idx."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class ManifestDecodeError(ValueError):
    """Raised when signed framing, table bounds, or FlatBuffer data are invalid."""


class Build2771ResourceManifestDecoder:
    SIGNATURE_LENGTH = 128
    FIELD_BASE = 4
    FIELD_STRIDE = 2

    def __init__(self, data: bytes) -> None:
        self.data = data
        if len(data) < self.SIGNATURE_LENGTH + 8:
            raise ManifestDecodeError("input is shorter than signature plus FlatBuffer framing")

        self.signature = data[: self.SIGNATURE_LENGTH]
        self.payload = data[self.SIGNATURE_LENGTH :]
        root_relative = self._read_u32(self.SIGNATURE_LENGTH)
        self.root = self.SIGNATURE_LENGTH + root_relative
        if self.root + 4 > len(self.data):
            raise ManifestDecodeError("FlatBuffer root is outside the input")

        vtable_relative = self._read_i32(self.root)
        self.vtable = self.root - vtable_relative
        if self.vtable < self.SIGNATURE_LENGTH or self.vtable + 4 > len(self.data):
            raise ManifestDecodeError("FlatBuffer vtable is outside the input")
        self.vtable_length = self._read_u16(self.vtable)
        if self.vtable_length < 4 or self.vtable_length % 2:
            raise ManifestDecodeError("invalid FlatBuffer vtable length")

    def _read_u16(self, offset: int) -> int:
        if offset < 0 or offset + 2 > len(self.data):
            raise ManifestDecodeError(f"u16 read at {offset} is out of bounds")
        return int.from_bytes(self.data[offset : offset + 2], "little")

    def _read_i32(self, offset: int) -> int:
        if offset < 0 or offset + 4 > len(self.data):
            raise ManifestDecodeError(f"i32 read at {offset} is out of bounds")
        return int.from_bytes(self.data[offset : offset + 4], "little", signed=True)

    def _read_u32(self, offset: int) -> int:
        if offset < 0 or offset + 4 > len(self.data):
            raise ManifestDecodeError(f"u32 read at {offset} is out of bounds")
        return int.from_bytes(self.data[offset : offset + 4], "little", signed=False)

    def _slot_offset(self, table: int, field_id: int) -> int:
        if field_id < self.FIELD_BASE or (field_id - self.FIELD_BASE) % self.FIELD_STRIDE:
            raise ManifestDecodeError(f"invalid FlatLookup field id {field_id}")
        slot = (field_id - self.FIELD_BASE) // self.FIELD_STRIDE
        vtable = table - self._read_i32(table)
        if vtable < self.SIGNATURE_LENGTH or vtable + 4 > len(self.data):
            raise ManifestDecodeError(f"vtable for table {table} is outside the input")
        table_vtable_length = self._read_u16(vtable)
        if 4 + 2 * slot > table_vtable_length:
            return 0
        return self._read_u16(vtable + 4 + 2 * slot)

    def _indirect(self, offset: int) -> int:
        target = offset + self._read_u32(offset)
        if target < 0 or target >= len(self.data):
            raise ManifestDecodeError(f"indirect reference at {offset} is out of bounds")
        return target

    def _int(self, table: int, field_id: int) -> int:
        field_offset = self._slot_offset(table, field_id)
        if not field_offset:
            return 0
        return self._read_i32(table + field_offset)

    def _string(self, table: int, field_id: int) -> str | None:
        field_offset = self._slot_offset(table, field_id)
        if not field_offset:
            return None
        target = self._indirect(table + field_offset)
        length = self._read_u32(target)
        end = target + 4 + length
        if end > len(self.data):
            raise ManifestDecodeError(f"string at {target} is truncated")
        try:
            return self.data[target + 4 : end].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ManifestDecodeError(f"string at {target} is not UTF-8") from error

    def _vector(self, table: int, field_id: int) -> tuple[int, int, int]:
        field_offset = self._slot_offset(table, field_id)
        if not field_offset:
            raise ManifestDecodeError(f"required vector field {field_id} is absent")
        vector = self._indirect(table + field_offset)
        count = self._read_u32(vector)
        start = vector + 4
        end = start + 4 * count
        if end > len(self.data):
            raise ManifestDecodeError(f"vector at {vector} is truncated")
        return vector, count, start

    def _table_vector(self, table: int, field_id: int) -> list[int]:
        _, count, start = self._vector(table, field_id)
        return [self._indirect(start + 4 * index) for index in range(count)]

    def _int_vector(self, table: int, field_id: int) -> list[int]:
        _, count, start = self._vector(table, field_id)
        return [self._read_i32(start + 4 * index) for index in range(count)]

    def decode(self) -> dict[str, Any]:
        bundles = []
        for index, table in enumerate(self._table_vector(self.root, 6)):
            bundles.append(
                {
                    "name": self._string(table, 4),
                    "props": self._int(table, 6),
                    "sccIndex": self._int(table, 8),
                    "allDependencies": self._int_vector(table, 10),
                    "_flatbuffer_table": table,
                    "_bundle_index": index,
                }
            )

        assets = []
        for table in self._table_vector(self.root, 8):
            assets.append(
                {
                    "assetName": self._string(table, 4),
                    "bundleIndex": self._int(table, 6),
                    "name": self._string(table, 8),
                    "path": self._string(table, 10),
                    "_flatbuffer_table": table,
                }
            )

        return {
            "rawCount": self._int(self.root, 4),
            "bundles": bundles,
            "assetToBundleList": assets,
        }


def public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "rawCount": manifest["rawCount"],
        "bundles": [
            {key: value for key, value in bundle.items() if not key.startswith("_")}
            for bundle in manifest["bundles"]
        ],
        "assetToBundleList": [
            {key: value for key, value in asset.items() if not key.startswith("_")}
            for asset in manifest["assetToBundleList"]
        ],
    }


def build_summary(source: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    data = source.read_bytes()
    return {
        "schema_version": "M34_BUILD2771_RESOURCE_MANIFEST_DECODER_V1",
        "source": str(source),
        "source_size": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "signature_length": Build2771ResourceManifestDecoder.SIGNATURE_LENGTH,
        "rawCount": manifest["rawCount"],
        "bundle_count": len(manifest["bundles"]),
        "asset_to_bundle_count": len(manifest["assetToBundleList"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, help="write the full decoded manifest as JSON")
    parser.add_argument("--summary", type=Path, help="write a compact verification summary")
    parser.add_argument("--query", help="case-insensitive substring filter over decoded asset fields")
    args = parser.parse_args()

    data = args.source.read_bytes()
    manifest = Build2771ResourceManifestDecoder(data).decode()
    if args.output:
        args.output.write_text(
            json.dumps(public_manifest(manifest), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.summary:
        args.summary.write_text(
            json.dumps(build_summary(args.source, manifest), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    rows = public_manifest(manifest)["assetToBundleList"]
    if args.query:
        needle = args.query.casefold()
        rows = [
            row
            for row in rows
            if needle in " ".join(str(row.get(key, "")) for key in ("assetName", "name", "path")).casefold()
        ]
    print(
        json.dumps(
            {
                "source_sha256": hashlib.sha256(data).hexdigest(),
                "source_size": len(data),
                "rawCount": manifest["rawCount"],
                "bundle_count": len(manifest["bundles"]),
                "asset_to_bundle_count": len(manifest["assetToBundleList"]),
                "query_matches": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
