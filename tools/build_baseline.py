"""Build the offline, pinned multilingual baseline; never fetch or install tools."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import tempfile
import zipfile

from fontTools import subset
from fontTools.merge import Merger
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
FONTTOOLS_VERSION = "4.68.0"
FIXED_TIMESTAMP = 3306758400
FAMILY = "Antrakt UI Sans"
POSTSCRIPT_NAME = "AntraktUISans-Regular"
FONT_REVISION = 1.0  # Font-asset revision, independent of addon release versions.


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_manifest() -> dict:
    manifest = json.loads((BASELINE / "sources.json").read_text(encoding="utf-8"))
    for entry in manifest["materials"]:
        path = BASELINE / entry["path"]
        if digest(path.read_bytes()) != entry["sha256"]:
            raise ValueError(f"Pinned baseline material changed: {entry['path']}")
    return manifest


def rename(font: TTFont, recipe_digest: str) -> None:
    # Preserve upstream attribution, including Droid data that the merger's
    # first-font name-table policy would otherwise silently discard.
    names = {
        0: "Copyright 2015-2021 Google LLC. All Rights Reserved. "
        "Copyright 2018 The Noto Project Authors. "
        "Digitized data copyright Google Corporation © 2006. "
        "Copyright (C) 2008 The Android Open Source Project.",
        1: FAMILY,
        2: "Regular",
        3: f"{POSTSCRIPT_NAME};recipe={recipe_digest}",
        4: f"{FAMILY} Regular",
        5: f"Version {FONT_REVISION:.3f}; derived baseline; recipe {recipe_digest}",
        6: POSTSCRIPT_NAME,
        7: "Noto is a trademark of Google LLC. Droid is a trademark of Google "
        "and may be registered in certain jurisdictions.",
        8: "Original fonts: Monotype Imaging Inc.; Ascender Corporation. "
        "Modified font: Antrakt.",
        9: "Original designs: Monotype Design Team; Steve Matteson.",
        10: "Modified font: Noto Sans plus complementary Droid Sans Fallback "
        "Legacy glyphs; Droid hints removed and outlines scaled 256 to 1000 "
        "UPEM; layout merged; names and embedding metadata updated. "
        "See NOTICE.txt and all accompanying licenses.",
        11: "https://github.com/notofonts/noto-fonts ; "
        "https://android.googlesource.com/platform/frameworks/base/",
        12: "http://www.monotype.com/studio ; "
        "http://www.ascendercorp.com/typedesigners.html",
        13: "The modified combined font is licensed under SIL Open Font "
        "License 1.1. Original Droid portions retain Apache License 2.0 "
        "notices and terms. See NOTICE.txt, licenses/NotoSans-OFL.txt, "
        "licenses/Apache-2.0.txt, licenses/Droid-NOTICE.txt and "
        "licenses/Droid-README.txt. Modified font; no upstream endorsement.",
        14: "https://openfontlicense.org ; "
        "https://www.apache.org/licenses/LICENSE-2.0",
        16: FAMILY,
        17: "Regular",
    }
    font["name"].names = []
    for name_id, text in names.items():
        font["name"].setName(text, name_id, 3, 1, 0x409)
        # The metadata is also representable in Mac Roman, including copyright.
        font["name"].setName(text, name_id, 1, 0, 0)


def build() -> tuple[bytes, dict]:
    if importlib.metadata.version("fonttools") != FONTTOOLS_VERSION:
        raise RuntimeError("Use the exact hash-locked build dependency")
    manifest = source_manifest()
    recipe_digest = digest(
        Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        + json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    )
    noto_path = BASELINE / "sources/NotoSans-Regular.ttf"
    droid_path = BASELINE / "sources/DroidSansFallbackLegacy.ttf"
    noto = TTFont(noto_path, recalcTimestamp=False)
    droid = TTFont(droid_path, recalcTimestamp=False)
    noto_codes = set(noto.getBestCmap())
    droid_codes = set(droid.getBestCmap())
    options = subset.Options()
    options.layout_features = ["*"]
    options.hinting = False
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.harfbuzz_repacker = False
    worker = subset.Subsetter(options=options)
    worker.populate(unicodes=droid_codes - noto_codes)
    worker.subset(droid)
    # This is the whole complementary script inventory, not a UI-text subset.
    scale_upem(droid, noto["head"].unitsPerEm)
    droid["head"].created = droid["head"].modified = FIXED_TIMESTAMP
    with tempfile.TemporaryDirectory() as directory:
        complement_path = Path(directory) / "DroidComplement.ttf"
        droid.save(complement_path)
        merged = Merger().merge([str(noto_path), str(complement_path)])
    merged.recalcTimestamp = False
    merged["head"].created = merged["head"].modified = FIXED_TIMESTAMP
    merged["head"].fontRevision = FONT_REVISION
    # OFL permits embedding and Apache 2.0 sections 2/4 permit the derivative.
    # Do not inherit Droid's historical editable-only metadata (8) as a new
    # restriction on the renamed, OFL-distributed combined font.
    merged["OS/2"].fsType = 0
    rename(merged, recipe_digest)
    output = io.BytesIO()
    merged.save(output)
    data = output.getvalue()
    actual = set(merged.getBestCmap())
    if actual != noto_codes | droid_codes:
        raise ValueError("Merged cmap must preserve the exact source union")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
        entry = zipfile.ZipInfo("AntraktUISans.ttf", date_time=(2000, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        zip_file.writestr(entry, data, compresslevel=6)
    report = {
        "family": FAMILY,
        "recipeSha256": recipe_digest,
        "fonttools": FONTTOOLS_VERSION,
        "sha256": digest(data),
        "bytes": len(data),
        "fontOnlyZipBytes": len(archive.getvalue()),
        "codepoints": len(actual),
        "glyphs": len(merged.getGlyphOrder()),
        "modernHangulSyllables": len(actual & set(range(0xAC00, 0xD7A4))),
        "hanU4E00U9FFF": len(actual & set(range(0x4E00, 0xA000))),
        "hhea": {key: getattr(merged["hhea"], key) for key in ("ascent", "descent", "lineGap")},
        "typo": {key: getattr(merged["OS/2"], key) for key in ("sTypoAscender", "sTypoDescender", "sTypoLineGap")},
        "fsType": merged["OS/2"].fsType,
        "nativeAcceptance": "required",
    }
    return data, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data, report = build()
    if args.check:
        if (BASELINE / "AntraktUISans.ttf").read_bytes() != data:
            raise SystemExit("Baseline differs from the committed generated asset")
        if json.loads((BASELINE / "build.json").read_text()) != report:
            raise SystemExit("Baseline receipt differs from the fresh build")
    if args.output:
        args.output.write_bytes(data)
    if args.receipt:
        args.receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
