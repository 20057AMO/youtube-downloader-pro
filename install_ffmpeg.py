"""Cross-platform FFmpeg/FFprobe installer.

Downloads prebuilt static binaries for Linux, macOS or Windows into the active
virtual environment (or ./bin when no virtual environment is active).

Usage:
    python install_ffmpeg.py          # download and install
    python install_ffmpeg.py --check  # only verify an existing installation

Standard library only.
"""

from __future__ import annotations

import argparse
import inspect
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

LINUX_BASE_URL = "https://johnvansickle.com/ffmpeg/releases"
WINDOWS_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
MACOS_URLS = {
    "ffmpeg": "https://evermeet.cx/ffmpeg/getrelease/zip",
    "ffprobe": "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip",
}
DOWNLOAD_TIMEOUT_SECONDS = 120
USER_AGENT = "ytd-ffmpeg-installer/1.0"


class InstallError(RuntimeError):
    """Raised when automatic installation cannot continue."""


def tool_names() -> tuple[str, str]:
    """Executable names for the current platform."""
    if os.name == "nt":
        return "ffmpeg.exe", "ffprobe.exe"
    return "ffmpeg", "ffprobe"


def get_bin_dir() -> Path:
    """Return the venv scripts directory, or the repo-local ./bin fallback."""
    if sys.prefix != sys.base_prefix:
        scripts_dir = sysconfig.get_path("scripts")
        if scripts_dir:
            return Path(scripts_dir)
        return Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    return Path(__file__).resolve().parent / "bin"


def download(url: str, destination: Path) -> None:
    """Download url to destination, turning network errors into InstallError."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(
            request, timeout=DOWNLOAD_TIMEOUT_SECONDS
        ) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except (urllib.error.URLError, OSError) as exc:
        raise InstallError(f"download failed for {url}: {exc}") from exc


def _safe_tar_members(
    tar: tarfile.TarFile, names: set[str]
) -> list[tarfile.TarInfo]:
    """Select only regular ffmpeg/ffprobe members with safe relative paths."""
    selected = []
    for member in tar.getmembers():
        if not member.isfile():
            continue
        normalized = member.name.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            continue
        if Path(normalized).name in names:
            selected.append(member)
    return selected


def _extract_tar_members(
    tar: tarfile.TarFile, members: list[tarfile.TarInfo], destination: Path
) -> None:
    """Extract selected members using the PEP 706 data filter when available."""
    supports_filter = False
    try:
        parameters = inspect.signature(tar.extractall).parameters
        supports_filter = "filter" in parameters or any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
    except (TypeError, ValueError):
        supports_filter = False

    if supports_filter:
        try:
            tar.extractall(path=destination, members=members, filter="data")
            return
        except TypeError:
            # Older backports may expose the argument but reject the value.
            pass
    tar.extractall(path=destination, members=members)


def _install_binary(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if os.name != "nt":
        target.chmod(0o755)


def install_tar_tools(archive: Path, bin_dir: Path) -> None:
    """Extract ffmpeg/ffprobe from a .tar.xz archive into bin_dir."""
    names = set(tool_names())
    with tarfile.open(archive, "r:xz") as tar:
        members = _safe_tar_members(tar, names)
        found = {Path(member.name.replace("\\", "/")).name for member in members}
        missing = names - found
        if missing:
            raise InstallError(f"archive is missing: {', '.join(sorted(missing))}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            _extract_tar_members(tar, members, temp_path)
            for name in names:
                matches = [path for path in temp_path.rglob(name) if path.is_file()]
                if not matches:
                    raise InstallError(f"{name} not found after extraction")
                _install_binary(matches[0], bin_dir / name)


def install_zip_tools(archive: Path, bin_dir: Path, names: set[str]) -> None:
    """Extract only the named binaries from a zip archive into bin_dir."""
    installed: set[str] = set()
    with zipfile.ZipFile(archive) as zip_file:
        for member in zip_file.infolist():
            if member.is_dir():
                continue
            member_name = Path(member.filename.replace("\\", "/")).name
            if member_name not in names or member_name in installed:
                continue
            # A symlink stores its target string, not binary content.
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                continue
            target = bin_dir / member_name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            if os.name != "nt":
                target.chmod(0o755)
            installed.add(member_name)

    missing = names - installed
    if missing:
        raise InstallError(f"archive is missing: {', '.join(sorted(missing))}")


def install_linux(bin_dir: Path) -> None:
    machine = platform.machine().lower()
    arch = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "x64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine)
    if not arch:
        raise InstallError(
            f"unsupported Linux architecture: {machine}. "
            "Install FFmpeg with your package manager instead."
        )

    url = f"{LINUX_BASE_URL}/ffmpeg-release-{arch}-static.tar.xz"
    with tempfile.TemporaryDirectory() as temp_dir:
        archive = Path(temp_dir) / "ffmpeg.tar.xz"
        download(url, archive)
        install_tar_tools(archive, bin_dir)


def install_macos_with_brew() -> None:
    """Fallback used when the static macOS downloads are unreachable."""
    brew = shutil.which("brew")
    if not brew:
        raise InstallError(
            "macOS static downloads failed and Homebrew is not installed. "
            "Install FFmpeg manually with `brew install ffmpeg` "
            "(https://brew.sh) or from https://evermeet.cx/ffmpeg/."
        )

    print("Static downloads failed; falling back to Homebrew...")
    result = subprocess.run([brew, "install", "ffmpeg"], check=False)
    if result.returncode != 0:
        raise InstallError(
            "`brew install ffmpeg` failed. Install FFmpeg manually from "
            "https://evermeet.cx/ffmpeg/."
        )


def install_macos(bin_dir: Path) -> None:
    try:
        for name, url in MACOS_URLS.items():
            with tempfile.TemporaryDirectory() as temp_dir:
                archive = Path(temp_dir) / f"{name}.zip"
                download(url, archive)
                install_zip_tools(archive, bin_dir, {name})
    except InstallError as exc:
        print(f"macOS static download failed: {exc}", file=sys.stderr)
        install_macos_with_brew()


def install_windows(bin_dir: Path) -> None:
    names = {"ffmpeg.exe", "ffprobe.exe"}
    with tempfile.TemporaryDirectory() as temp_dir:
        archive = Path(temp_dir) / "ffmpeg.zip"
        download(WINDOWS_URL, archive)
        install_zip_tools(archive, bin_dir, names)


def find_tool(name: str) -> Path | None:
    """Prefer the venv/repo install, then fall back to PATH."""
    candidate = get_bin_dir() / name
    if candidate.is_file():
        return candidate
    found = shutil.which(name)
    return Path(found) if found else None


def version_line(tool: Path) -> str:
    """Run `<tool> -version` and return its first output line."""
    try:
        result = subprocess.run(
            [str(tool), "-version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InstallError(f"cannot run {tool}: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        detail = detail or f"exit code {result.returncode}"
        raise InstallError(f"{tool} failed: {detail}")

    lines = (result.stdout or result.stderr).strip().splitlines()
    if not lines:
        raise InstallError(f"{tool} returned no version information")
    return lines[0]


def verify_installation() -> int:
    """Report whether ffmpeg and ffprobe are usable. Return 0 when both work."""
    missing: list[str] = []
    for name in tool_names():
        tool = find_tool(name)
        if tool is None:
            missing.append(name)
            continue
        try:
            print(f"{name}: {version_line(tool)} ({tool})")
        except InstallError as exc:
            print(f"{name}: {exc}", file=sys.stderr)
            missing.append(name)

    if missing:
        print(
            "FFmpeg is not ready. Run `python install_ffmpeg.py` to install it.",
            file=sys.stderr,
        )
        return 1
    return 0


def install() -> int:
    bin_dir = get_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    print(f"Installing FFmpeg into {bin_dir} ...")

    system = platform.system()
    if system == "Linux":
        install_linux(bin_dir)
    elif system == "Darwin":
        install_macos(bin_dir)
    elif system == "Windows":
        install_windows(bin_dir)
    else:
        raise InstallError(
            f"unsupported operating system: {system}. "
            "Install FFmpeg with your package manager instead."
        )

    status = verify_installation()
    if status == 0 and sys.prefix == sys.base_prefix:
        print(
            f"Note: {bin_dir} is not on PATH. Add it to PATH so yt-dlp can find "
            "FFmpeg when running outside a virtual environment."
        )
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install prebuilt FFmpeg and FFprobe binaries."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="only check whether ffmpeg and ffprobe are usable",
    )
    args = parser.parse_args(argv)

    if args.check:
        return verify_installation()

    try:
        return install()
    except InstallError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
