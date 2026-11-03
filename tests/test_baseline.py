"""Offline binary, provenance and preference-independent baseline checks."""

import importlib.util
import json
from pathlib import Path
import struct
import unittest

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "baseline"
SPEC = importlib.util.spec_from_file_location("build_baseline", ROOT / "tools/build_baseline.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first, cls.receipt = BUILDER.build()
        cls.second, cls.second_receipt = BUILDER.build()
        cls.font = TTFont(BASE / "AntraktUISans.ttf", checkChecksums=2)
        cls.cmap = cls.font.getBestCmap()
        cls.codes = set(cls.cmap)
        cls.noto = TTFont(BASE / "sources/NotoSans-Regular.ttf")
        cls.droid = TTFont(BASE / "sources/DroidSansFallbackLegacy.ttf")
        cls.corpus = json.loads((BASE / "corpus.json").read_text())

    def test_two_rebuilds_match_generated_font_and_receipt(self):
        self.assertEqual(self.first, self.second)
        self.assertEqual(self.receipt, self.second_receipt)
        self.assertEqual(self.first, (BASE / "AntraktUISans.ttf").read_bytes())
        self.assertEqual(self.receipt, json.loads((BASE / "build.json").read_text()))

    def test_pinned_sources_and_licenses(self):
        manifest = BUILDER.source_manifest()
        self.assertEqual(len(manifest["materials"]), 6)
        self.assertEqual(manifest["derivativeLicense"], "OFL-1.1")
        self.assertEqual(manifest["retainedOriginalDroidLicense"], "Apache-2.0")
        self.assertIn("fonttools==4.68.0 --hash=sha256:", (ROOT / "requirements-build.txt").read_text())

    def test_cmap_is_complete_source_union(self):
        self.assertEqual(self.codes, set(self.noto.getBestCmap()) | set(self.droid.getBestCmap()))
        self.assertEqual(len(self.codes), 32092)
        self.assertTrue(set(range(0xAC00, 0xD7A4)) <= self.codes)
        self.assertTrue((set(range(0x410, 0x450)) | {0x401, 0x451}) <= self.codes)
        self.assertEqual(len(self.codes & set(range(0x4E00, 0xA000))), 16504)

    def test_noto_metrics_and_hint_programs_preserved(self):
        for code, glyph in self.noto.getBestCmap().items():
            self.assertEqual(self.font["hmtx"][self.cmap[code]], self.noto["hmtx"][glyph])
        for tag in ("fpgm", "prep"):
            self.assertEqual(self.font[tag].program.getBytecode(), self.noto[tag].program.getBytecode())
        self.assertEqual(self.font["cvt "].values, self.noto["cvt "].values)

    def test_droid_complement_does_not_retain_unscaled_hints(self):
        complement = set(self.droid.getBestCmap()) - set(self.noto.getBestCmap())
        for code in complement:
            glyph = self.font["glyf"][self.cmap[code]]
            if hasattr(glyph, "program"):
                self.assertEqual(glyph.program.getBytecode(), b"")

    def test_real_corpus_documents_exact_transition_symbol_gaps(self):
        # Historical before-transition corpus is an audit fixture. The two
        # specific UI replacements remain consumer release work, never a
        # blanket exception in the live consumer's zero-missing glyph gate.
        for addon, locales in self.corpus["locales"].items():
            self.assertEqual(len(locales), 11)
            expected = set() if addon == "DoYouNeedIt" else {0x26A0}
            for locale, codes in locales.items():
                self.assertEqual(set(codes) - self.codes, expected, (addon, locale))
        self.assertEqual(set(self.corpus["sourceNonAscii"]["StatsPro"]) - self.codes, {0x2212, 0x26A0})
        self.assertEqual(set(self.corpus["sourceNonAscii"]["Do-You-Need-It-"]) - self.codes, set())
        self.assertEqual(set(self.corpus["pendingUiReplacements"]), {"U+2212", "U+26A0"})

    def test_static_truetype_and_structural_integrity(self):
        self.font.ensureDecompiled()
        self.assertEqual(self.font.sfntVersion, "\x00\x01\x00\x00")
        self.assertNotIn("fvar", self.font)
        self.assertLess(self.font["maxp"].numGlyphs, 65536)
        glyphs = set(self.font.getGlyphOrder())
        for glyph in self.font["glyf"].glyphs.values():
            if glyph.isComposite():
                self.assertTrue({part.glyphName for part in glyph.components} <= glyphs)
        self.assertEqual(len(self.font["loca"].locations), len(glyphs) + 1)
        self.assertEqual(self.font["loca"].locations[-1], len(self.font.reader["glyf"]))
        padded = self.first + b"\0" * (-len(self.first) % 4)
        self.assertEqual(sum(struct.unpack(f">{len(padded) // 4}I", padded)) & 0xFFFFFFFF, 0xB1B0AFBA)
        bmp, full = {}, {}
        for table in self.font["cmap"].tables:
            if table.platformID == 3 and table.format in (4, 12):
                (bmp if table.format == 4 else full).update(table.cmap)
        self.assertTrue(all(full[code] == glyph for code, glyph in bmp.items()))

    def test_deliberate_metrics_and_embedding_rights_metadata(self):
        self.assertEqual(self.font["head"].unitsPerEm, 1000)
        self.assertEqual(tuple(getattr(self.font["hhea"], key) for key in ("ascent", "descent", "lineGap")), (1069, -293, 0))
        self.assertEqual(tuple(getattr(self.font["OS/2"], key) for key in ("sTypoAscender", "sTypoDescender", "sTypoLineGap")), (1069, -293, 63))
        self.assertEqual(self.font["OS/2"].fsType, 0)

    def test_renamed_derivative_preserves_both_attributions(self):
        records = {record.nameID: record.toUnicode() for record in self.font["name"].names}
        self.assertEqual(records[1], "Antrakt UI Sans")
        self.assertEqual(records[6], "AntraktUISans-Regular")
        self.assertIn("recipe", records[3])
        self.assertRegex(records[5], r"^Version 1\.000; derived baseline; recipe [a-f0-9]{64}$")
        self.assertEqual(self.font["head"].fontRevision, 1.0)
        self.assertIn("Google LLC", records[0])
        self.assertIn("Google Corporation © 2006", records[0])
        self.assertIn("Android Open Source Project", records[0])
        self.assertIn("Noto is a trademark", records[7])
        self.assertIn("Droid is a trademark", records[7])
        self.assertIn("Monotype", records[8])
        self.assertIn("Ascender", records[8])
        self.assertIn("Steve Matteson", records[9])
        self.assertIn("Modified font", records[10])
        self.assertIn("SIL Open Font", records[13])
        self.assertIn("Apache License 2.0", records[13])
        self.assertIn("NotoSans-OFL.txt", records[13])
        self.assertIn("Droid-NOTICE.txt", records[13])


if __name__ == "__main__":
    unittest.main()
