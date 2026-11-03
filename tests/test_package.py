"""Exact client artifacts and containment/failure-path package regressions."""

import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("provider_package", ROOT / "scripts/package.py")
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packages = {}
        for flavor in PACKAGE.FLAVORS:
            first, receipt = PACKAGE.archive_bytes(flavor, "0.0.0", fixture=True)
            second, second_receipt = PACKAGE.archive_bytes(flavor, "0.0.0", fixture=True)
            if first != second or receipt != second_receipt:
                raise AssertionError("Client archives must rebuild byte-for-byte")
            cls.packages[flavor] = first, receipt

    def test_deterministic_exact_client_inventory_and_metadata(self):
        for flavor, (data, receipt) in self.packages.items():
            with self.subTest(flavor=flavor), zipfile.ZipFile(io.BytesIO(data)) as archive:
                expected = {"AntraktFonts/" + name for name in PACKAGE.inventory()}
                expected.add("AntraktFonts/AntraktFonts.toc")
                self.assertEqual(set(archive.namelist()), expected)
                self.assertEqual(len(archive.namelist()), len(expected))
                self.assertEqual(len(expected), 93)
                self.assertEqual(archive.testzip(), None)
                toc = archive.read("AntraktFonts/AntraktFonts.toc").decode()
                self.assertIn("## Version: 0.0.0\n", toc)
                self.assertIn("## Interface: " + PACKAGE.FLAVORS[flavor][1] + "\n", toc)
                self.assertIn("## X-AntraktFonts-Flavor: " + flavor + "\n", toc)
                self.assertNotIn("@project-version@", toc)
                for info in archive.infolist():
                    self.assertEqual(info.date_time, (2000, 1, 1, 0, 0, 0))
                    self.assertNotIn("baseline", info.filename)
                    self.assertNotIn("consumer", info.filename)
                    self.assertNotIn("scripts/", info.filename)
                self.assertEqual(receipt["sha256"], PACKAGE.sha(data))
                self.assertTrue(receipt["fixtureOnly"])
                print("Fixture-only archive " + json.dumps(receipt, sort_keys=True))

    def test_archive_binaries_and_licenses_match_source(self):
        manifest = json.loads((ROOT / "catalog/fonts.json").read_text())
        for data, _ in self.packages.values():
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for font in manifest["fonts"]:
                    self.assertEqual(PACKAGE.sha(archive.read("AntraktFonts/" + font["path"])).upper(), font["sha256"])
                    self.assertEqual(PACKAGE.normalized_text_hash(archive.read("AntraktFonts/" + font["licenseFile"])).upper(), font["licenseSha256"])

    def test_unsafe_source_paths_and_reparse_input_are_rejected(self):
        for path in ("../LICENSE", "/LICENSE", "C:/LICENSE", "fonts\\face.ttf", "fonts/../../LICENSE"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                PACKAGE.safe_file(ROOT, path)
        real_lstat = os.lstat
        def reparse(path, *args, **kwargs):
            result = real_lstat(path, *args, **kwargs)
            if Path(path) == ROOT / "LICENSE":
                return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
            return result
        with patch.object(PACKAGE.os, "lstat", side_effect=reparse), self.assertRaises(ValueError):
            PACKAGE.safe_file(ROOT, "LICENSE")

    def test_real_symbolic_link_is_rejected_when_platform_allows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "actual").write_text("source")
            try:
                (root / "linked").symlink_to(root / "actual")
            except OSError as error:
                self.skipTest("OS does not permit symlink fixture: " + str(error))
            with self.assertRaises(ValueError):
                PACKAGE.safe_file(root, "linked")

    def test_invalid_versions_and_unprepared_release_fail_closed(self):
        for version in ("v1.2.3", "1.2.3-beta", "01.2.3", "1.2.3\n", "1.2", "1.2.999999999999", "0.0.0"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                PACKAGE.validate_version(version)
        with self.assertRaises(ValueError):
            PACKAGE.validate_version("1.2.3", fixture=True)
        with self.assertRaises(ValueError):
            PACKAGE.archive_bytes("retail", "1.2.3")

    def test_duplicate_or_stateful_dependent_toc_headers_are_rejected(self):
        original = PACKAGE.safe_file
        source = (ROOT / "AntraktFonts.toc").read_bytes()
        # The existing valid header remains present in each mutation. A substring
        # check must not bless conflicting/duplicate client metadata.
        for header in (
            "## Interface: 999999",
            "## Version: 1.2.3",
            "## X-AntraktFonts-Flavor: forever",
            "## interface: 120105",
            "## SavedVariables: SharedFontDB",
            "## SavedVariablesPerCharacter: SharedFontCharacterDB",
            "## Dependencies: StatsPro",
            "## RequiredDeps: DoYouNeedIt",
            "## RequiredDependencies: StatsPro",
        ):
            class MutatedToc:
                def read_bytes(self):
                    return source + header.encode() + b"\n"
            def read(root, relative):
                path = original(root, relative)
                return MutatedToc() if relative == "AntraktFonts.toc" else path
            with self.subTest(header=header), patch.object(PACKAGE, "safe_file", side_effect=read), self.assertRaises(ValueError):
                PACKAGE.archive_bytes("retail", "0.0.0", fixture=True)

    def test_output_never_overwrites_or_accepts_path_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            target = PACKAGE.write_archive(b"fixture", "retail", "1.2.3", Path(directory))
            with self.assertRaises(FileExistsError):
                PACKAGE.write_archive(b"replacement", "retail", "1.2.3", Path(directory))
            self.assertEqual(target.read_bytes(), b"fixture")
            for flavor, version in (("../escape", "1.2.3"), ("retail", "../escape")):
                with self.assertRaises(ValueError):
                    PACKAGE.write_archive(b"fixture", flavor, version, Path(directory))

    def test_changed_font_binary_hash_is_rejected(self):
        # No source file is modified: simulate one failed binary digest.
        original = PACKAGE.sha
        calls = 0
        def mutate(data):
            nonlocal calls
            calls += 1
            if calls == 1:
                return "0" * 64
            return original(data)
        with patch.object(PACKAGE, "sha", side_effect=mutate), self.assertRaises(ValueError):
            PACKAGE.inventory()

    def test_source_mutation_during_package_is_rejected(self):
        # Simulate an external edit between snapshotting and final byte readback.
        # Mutating an in-memory reader keeps the real checkout untouched.
        original_file = PACKAGE.safe_file
        original_close = zipfile.ZipFile.close
        compressed = False
        class DriftingSource:
            def read_bytes(self):
                data = (ROOT / "AntraktFonts.lua").read_bytes()
                return data + b"\n-- changed during packaging" if compressed else data
        def source(root, relative):
            path = original_file(root, relative)
            return DriftingSource() if relative == "AntraktFonts.lua" else path
        def close(archive):
            nonlocal compressed
            original_close(archive)
            compressed = True
        with patch.object(PACKAGE, "safe_file", side_effect=source), patch.object(zipfile.ZipFile, "close", close), self.assertRaisesRegex(ValueError, "Source changed during packaging"):
            PACKAGE.archive_bytes("retail", "0.0.0", fixture=True)


if __name__ == "__main__":
    unittest.main()
