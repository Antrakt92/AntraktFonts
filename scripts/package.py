"""Build exact, deterministic client archives without publishing or installing."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FLAVORS = {
    "retail": ("AntraktFonts.toc", "120105"),
    "forever": ("AntraktFonts_Forever.toc", "16001"),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_file(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    if "\\" in relative or ":" in relative or not parts or PurePosixPath(relative).is_absolute() or any(part in (".", "..") for part in parts):
        raise ValueError(f"Unsafe package path: {relative}")
    root = root.resolve(strict=True)
    current = root
    for part in parts:
        current /= part
        info = os.lstat(current)
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise ValueError(f"Reparse points are forbidden in package inputs: {relative}")
    if not current.resolve(strict=True).is_relative_to(root) or not current.is_file():
        raise ValueError(f"Package input escapes source root: {relative}")
    return current


def normalized_text_hash(data: bytes) -> str:
    return sha(data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode())


def validate_version(version: str, fixture: bool = False) -> None:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version) or any(len(part) > 9 or int(part) > 2147483647 for part in version.split(".")):
        raise ValueError("Version must be a canonical bounded MAJOR.MINOR.PATCH")
    if fixture and version != "0.0.0":
        raise ValueError("The disposable fixture bypass is restricted to 0.0.0")
    if not fixture and version == "0.0.0":
        raise ValueError("0.0.0 is reserved for disposable package fixtures")


def validate_toc(text: str, flavor: str, interface: str) -> list[str]:
    headers: dict[str, list[str]] = {}
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("##"):
            if ":" not in line:
                raise ValueError("Malformed TOC metadata header")
            key, value = line[2:].split(":", 1)
            headers.setdefault(key.strip().lower(), []).append(value.strip())
        elif line and not line.startswith("#"):
            entries.append(line.replace("\\", "/"))
    for key, expected in {
        "interface": interface,
        "version": "@project-version@",
        "x-antraktfonts-flavor": flavor,
        "x-curse-project-id": "1783613",
        "icontexture": "Interface\\AddOns\\AntraktFonts\\media\\antrakt-fonts-addon.png",
    }.items():
        if headers.get(key) != [expected]:
            raise ValueError(f"TOC requires one matching {key} header")
    for key in (
        "savedvariables", "savedvariablespercharacter", "dependencies",
        "requireddeps", "requireddependencies", "loadondemand",
    ):
        if key in headers:
            raise ValueError(f"Stateless independent provider forbids TOC header: {key}")
    if text.count("@project-version@") != 1:
        raise ValueError("TOC version placeholder must occur exactly once")
    if entries != ["libs/LibStub/LibStub.lua", "libs/CallbackHandler-1.0/CallbackHandler-1.0.lua", "libs/LibSharedMedia-3.0/LibSharedMedia-3.0.lua", "AntraktFonts_Catalog.lua", "AntraktFonts.lua"]:
        raise ValueError("Unexpected TOC load order or runtime file")
    return entries


def read_inventory(root: Path = ROOT) -> dict[str, bytes]:
    """Read and validate the exact bytes to archive, excluding the client TOC."""
    font_manifest = json.loads(safe_file(root, "catalog/fonts.json").read_text(encoding="utf-8"))
    lib_manifest = json.loads(safe_file(root, "catalog/libraries.json").read_text(encoding="utf-8"))
    if font_manifest["schemaVersion"] != 1 or lib_manifest["schemaVersion"] != 1:
        raise ValueError("Unsupported package source manifest")
    snapshots = {}

    def snapshot(path: str) -> bytes:
        if path not in snapshots:
            snapshots[path] = safe_file(root, path).read_bytes()
        return snapshots[path]

    for path in ("AntraktFonts.lua", "AntraktFonts_Catalog.lua", "LICENSE", "THIRD-PARTY-NOTICES.md", "CHANGELOG.md", "media/antrakt-fonts-addon.png"):
        snapshot(path)
    notice = snapshots["THIRD-PARTY-NOTICES.md"].decode("utf-8")
    for font in font_manifest["fonts"]:
        for path in (font["path"], font["licenseFile"]):
            if path not in notice:
                raise ValueError(f"Missing font notice: {path}")
        if sha(snapshot(font["path"])).upper() != font["sha256"]:
            raise ValueError(f"Changed font binary: {font['path']}")
        if normalized_text_hash(snapshot(font["licenseFile"])).upper() != font["licenseSha256"]:
            raise ValueError(f"Changed font license: {font['licenseFile']}")
    for lib in lib_manifest["libraries"]:
        if normalized_text_hash(snapshot(lib["Path"])).upper() != lib["RuntimeSha256"]:
            raise ValueError(f"Changed bundled library: {lib['Path']}")
        if lib["Path"] not in notice:
            raise ValueError(f"Missing library notice: {lib['Path']}")
        if lib["LicenseFile"]:
            if normalized_text_hash(snapshot(lib["LicenseFile"])).upper() != lib["LicenseTextSha256"]:
                raise ValueError(f"Changed library license: {lib['LicenseFile']}")
        for key, value in lib.items():
            if value and key != "Path" and value not in notice:
                raise ValueError(f"Incomplete library notice {lib['Project']}: {key}")
    # Unexpected asset files are rejected rather than silently shipped or ignored.
    for directory in ("fonts", "libs", "LICENSES"):
        base = root / directory
        for current, directories, files in os.walk(base, followlinks=False):
            for name in directories + files:
                path = Path(current) / name
                info = os.lstat(path)
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                    raise ValueError(f"Reparse point in asset tree: {path.relative_to(root)}")
            for name in files:
                relative = (Path(current) / name).relative_to(root).as_posix()
                if relative not in snapshots:
                    raise ValueError(f"Unexpected asset: {relative}")
    return snapshots


def archive_bytes(flavor: str, version: str, *, fixture: bool = False, root: Path = ROOT) -> tuple[bytes, dict]:
    validate_version(version, fixture)
    if flavor not in FLAVORS:
        raise ValueError("Unknown client flavor")
    spec = importlib.util.spec_from_file_location("antrakt_generate", root / "tools/generate.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generated = generator.outputs()
    toc_source, interface = FLAVORS[flavor]
    snapshots = read_inventory(root)
    for path, expected in generated.items():
        relative = path.relative_to(root).as_posix()
        actual = snapshots[relative] if relative in snapshots else safe_file(root, relative).read_bytes()
        if actual != expected:
            raise ValueError(f"Generated source differs: {relative}")
    snapshots["AntraktFonts.toc"] = safe_file(root, toc_source).read_bytes()
    text = snapshots["AntraktFonts.toc"].decode("utf-8")
    for entry in validate_toc(text, flavor, interface):
        if entry not in snapshots:
            raise ValueError(f"TOC references missing archive file: {entry}")
    if not fixture and not re.search(r"^## " + re.escape(version) + r"(?:\s|$)", snapshots["CHANGELOG.md"].decode(), re.MULTILINE):
        raise ValueError("Prepare the matching cumulative changelog before a release archive")
    source_receipt = sha(json.dumps({archive: sha(data) for archive, data in sorted(snapshots.items())}, sort_keys=True, separators=(",", ":")).encode())
    snapshots["AntraktFonts.toc"] = text.replace("@project-version@", version).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(snapshots.items()):
            entry = zipfile.ZipInfo("AntraktFonts/" + name, date_time=(2000, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data, compresslevel=6)
    for archive, data in snapshots.items():
        source = toc_source if archive == "AntraktFonts.toc" else archive
        current = safe_file(root, source).read_bytes()
        expected = text.encode() if archive == "AntraktFonts.toc" else data
        if current != expected:
            raise ValueError(f"Source changed during packaging: {source}")
    data = output.getvalue()
    return data, {"flavor": flavor, "version": version, "fixtureOnly": fixture, "sha256": sha(data), "bytes": len(data), "fileCount": len(snapshots), "sourceInventorySha256": source_receipt}


def write_archive(data: bytes, flavor: str, version: str, output: Path) -> Path:
    validate_version(version)
    if flavor not in FLAVORS:
        raise ValueError("Unknown client flavor")
    output = output.absolute()
    for path in (output, *output.parents):
        if path.exists():
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("Output directory contains a reparse point")
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"AntraktFonts-{version}-{flavor}.zip"
    if not target.resolve().is_relative_to(output.resolve()):
        raise ValueError("Archive target escapes output directory")
    with target.open("xb") as stream:
        stream.write(data)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flavor", choices=FLAVORS, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / ".release")
    args = parser.parse_args()
    data, receipt = archive_bytes(args.flavor, args.version)
    path = write_archive(data, args.flavor, args.version, args.output)
    print(json.dumps({"archive": str(path), **receipt}, indent=2))


if __name__ == "__main__":
    main()
