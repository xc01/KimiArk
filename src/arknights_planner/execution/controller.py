"""Replaceable local device controls.  ADB is never contacted at import time."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess
import time
from typing import Protocol


class DeviceControllerError(RuntimeError):
    pass


class ADBUnavailableError(DeviceControllerError):
    pass


class DeviceSelectionError(DeviceControllerError):
    pass


class ScreenshotError(DeviceControllerError):
    pass


@dataclass(frozen=True)
class ScreenshotCapture:
    path: str
    width: int
    height: int
    monotonic_time: float


class DeviceController(Protocol):
    @property
    def device_id(self) -> str: ...

    def current_monotonic_time(self) -> float: ...

    def sleep_until(self, deadline: float) -> None: ...

    def screen_size(self) -> tuple[int, int]: ...

    def screenshot(self, path: Path) -> ScreenshotCapture: ...

    def tap(self, point: tuple[int, int]) -> None: ...

    def swipe(self, start: tuple[int, int], end: tuple[int, int], duration_seconds: float) -> None: ...


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Read PNG IHDR dimensions without introducing an image-processing dependency."""
    signature = b"\x89PNG\r\n\x1a\n"
    if len(data) < 24 or data[:8] != signature or data[12:16] != b"IHDR":
        raise ScreenshotError("ADB screenshot did not return a PNG IHDR")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


@dataclass
class MockDeviceController:
    """Deterministic virtual device used by normal unit tests and dry-runs."""

    resolution: tuple[int, int] = (1920, 1080)
    identifier: str = "mock-device"
    now: float = 100.0
    commands: list[tuple] = field(default_factory=list)

    @property
    def device_id(self) -> str:
        return self.identifier

    def current_monotonic_time(self) -> float:
        return self.now

    def sleep_until(self, deadline: float) -> None:
        self.commands.append(("sleep_until", deadline))
        self.now = max(self.now, deadline)

    def screen_size(self) -> tuple[int, int]:
        return self.resolution

    def screenshot(self, path: Path) -> ScreenshotCapture:
        path.parent.mkdir(parents=True, exist_ok=True)
        width, height = self.resolution
        # Valid enough for the local IHDR reader; screenshot pixels are deliberately
        # not synthesized because this is not a visual-recognition milestone.
        path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big"))
        self.commands.append(("screenshot", str(path)))
        return ScreenshotCapture(str(path), width, height, self.now)

    def tap(self, point: tuple[int, int]) -> None:
        self.commands.append(("tap", point))

    def swipe(self, start: tuple[int, int], end: tuple[int, int], duration_seconds: float) -> None:
        self.commands.append(("swipe", start, end, duration_seconds))
        self.now += duration_seconds


class ADBDeviceController:
    """Small local `adb` wrapper for one explicitly selected Android device."""

    def __init__(self, *, serial: str | None = None, adb_path: str = "adb", timeout_seconds: float = 15.0):
        self.serial = serial
        self.adb_path = adb_path
        self.timeout_seconds = timeout_seconds
        self._resolved_serial: str | None = None

    @staticmethod
    def command_for(*, adb_path: str, serial: str, arguments: tuple[str, ...]) -> tuple[str, ...]:
        return (adb_path, "-s", serial, *arguments)

    def _require_adb(self) -> None:
        if shutil.which(self.adb_path) is None:
            raise ADBUnavailableError(f"adb is unavailable: {self.adb_path}")

    def _run(self, arguments: tuple[str, ...], *, binary: bool = False) -> bytes:
        self._require_adb()
        completed = subprocess.run(
            arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            message = completed.stderr.decode("utf-8", errors="replace").strip()
            raise DeviceControllerError(message or f"ADB command failed: {' '.join(arguments)}")
        return completed.stdout

    def resolve_device(self) -> str:
        if self._resolved_serial:
            return self._resolved_serial
        output = self._run((self.adb_path, "devices")).decode("utf-8", errors="replace")
        devices = []
        for line in output.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        if self.serial:
            if self.serial not in devices:
                raise DeviceSelectionError(f"requested ADB device is unavailable: {self.serial}")
            self._resolved_serial = self.serial
        elif not devices:
            raise DeviceSelectionError("no ADB device is available")
        elif len(devices) > 1:
            raise DeviceSelectionError("multiple ADB devices are available; configure an explicit serial")
        else:
            self._resolved_serial = devices[0]
        return self._resolved_serial

    @property
    def device_id(self) -> str:
        return self.resolve_device()

    def _device_command(self, *arguments: str) -> tuple[str, ...]:
        return self.command_for(adb_path=self.adb_path, serial=self.resolve_device(), arguments=tuple(arguments))

    def current_monotonic_time(self) -> float:
        return time.monotonic()

    def sleep_until(self, deadline: float) -> None:
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

    def screen_size(self) -> tuple[int, int]:
        output = self._run(self._device_command("shell", "wm", "size")).decode("utf-8", errors="replace")
        for line in output.splitlines():
            if "x" in line:
                token = line.rsplit(" ", 1)[-1]
                try:
                    width, height = token.split("x", 1)
                    return int(width), int(height)
                except ValueError:
                    continue
        raise DeviceControllerError(f"unable to parse ADB screen size: {output.strip()}")

    def screenshot(self, path: Path) -> ScreenshotCapture:
        data = self._run(self._device_command("exec-out", "screencap", "-p"), binary=True)
        try:
            width, height = png_dimensions(data)
        except ScreenshotError as error:
            raise ScreenshotError(f"ADB screenshot failure: {error}") from error
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return ScreenshotCapture(str(path), width, height, self.current_monotonic_time())

    def tap(self, point: tuple[int, int]) -> None:
        self._run(self._device_command("shell", "input", "tap", str(point[0]), str(point[1])))

    def swipe(self, start: tuple[int, int], end: tuple[int, int], duration_seconds: float) -> None:
        duration_ms = max(1, round(duration_seconds * 1000))
        self._run(self._device_command(
            "shell", "input", "swipe", str(start[0]), str(start[1]), str(end[0]), str(end[1]), str(duration_ms),
        ))
