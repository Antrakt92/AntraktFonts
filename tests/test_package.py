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
from unittest.mock import ANY, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("provider_package", ROOT / "scripts/package.py")
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(PACKAGE, "read_inventory", wraps=PACKAGE.read_inventory) as capture:
            cls.packages = PACKAGE.archive_set(tuple(PACKAGE.FLAVORS), "0.0.0", fixture=True)
            capture.assert_called_once_with(ROOT, read_source=ANY)
        for flavor, (first, receipt) in cls.packages.items():
            second, second_receipt = PACKAGE.archive_bytes(flavor, "0.0.0", fixture=True)
            if first != second or receipt != second_receipt:
                raise AssertionError("Paired and single-client builds must produce identical ZIPs and receipts")

    def test_pair_contains_identical_common_files(self):
        retail, forever = (self.packages[flavor][0] for flavor in ("retail", "forever"))
        with zipfile.ZipFile(io.BytesIO(retail)) as first, zipfile.ZipFile(io.BytesIO(forever)) as second:
            self.assertEqual(first.namelist(), second.namelist())
            self.assertEqual(
                [name for name in first.namelist() if first.read(name) != second.read(name)],
                ["AntraktFonts/AntraktFonts.toc"],
            )

    def test_deterministic_exact_client_inventory_and_metadata(self):
        for flavor, (data, receipt) in self.packages.items():
            with self.subTest(flavor=flavor), zipfile.ZipFile(io.BytesIO(data)) as archive:
                expected = {"AntraktFonts/" + name for name in PACKAGE.read_inventory()}
                expected.add("AntraktFonts/AntraktFonts.toc")
                self.assertEqual(set(archive.namelist()), expected)
                self.assertEqual(len(archive.namelist()), len(expected))
                self.assertEqual(len(expected), 94)
                self.assertEqual(archive.testzip(), None)
                toc = archive.read("AntraktFonts/AntraktFonts.toc").decode()
                self.assertIn("## Version: 0.0.0\n", toc)
                self.assertIn("## Interface: " + PACKAGE.FLAVORS[flavor][1] + "\n", toc)
                self.assertIn("## X-AntraktFonts-Flavor: " + flavor + "\n", toc)
                self.assertNotIn("@project-version@", toc)
                self.assertIn("## IconTexture: Interface\\AddOns\\AntraktFonts\\media\\antrakt-fonts-addon.png\n", toc)
                icon = archive.read("AntraktFonts/media/antrakt-fonts-addon.png")
                self.assertEqual(icon, (ROOT / "media/antrakt-fonts-addon.png").read_bytes())
                self.assertEqual(icon[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(icon[25], 6)  # RGBA; transparent corners survive packaging.

                for info in archive.infolist():
                    self.assertEqual(info.date_time, (2000, 1, 1, 0, 0, 0))
                    self.assertNotIn("baseline", info.filename)
                    self.assertNotIn("consumer", info.filename)
                    self.assertNotIn("scripts/", info.filename)
                self.assertEqual(receipt["sha256"], PACKAGE.sha(data))
                self.assertTrue(receipt["fixtureOnly"])
                print("Fixture-only archive " + json.dumps(receipt, sort_keys=True))

    def test_archive_binaries_and_licenses_match_source(self):
        manifest = json.loads((ROOT / "catalog/fonts.json").read_text(encoding="utf-8"))
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

    def test_historical_changelog_heading_does_not_authorize_package(self):
        snapshots = PACKAGE.read_inventory()
        snapshots["CHANGELOG.md"] = b"# Changelog\n\n## 1.2.4 - Current\n\n## 1.2.3 - Historical\n"
        with patch.object(PACKAGE, "read_inventory", return_value=snapshots):
            with self.assertRaisesRegex(ValueError, "first release heading"):
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
            "## LoadOnDemand: 1",
            "## LoadWith: OtherAddon",
            "## Interface-Retail: 999999",
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

    def test_pair_output_collision_preserves_existing_archive(self):
        archives = {"retail": b"retail fixture", "forever": b"forever fixture"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            existing = PACKAGE.write_archive(b"existing", "forever", "1.2.3", output)
            with self.assertRaises(FileExistsError):
                PACKAGE.write_archives(archives, "1.2.3", output)
            self.assertEqual(list(output.iterdir()), [existing])
            self.assertEqual(existing.read_bytes(), b"existing")
        with tempfile.TemporaryDirectory() as directory:
            written = PACKAGE.write_archives(archives, "1.2.3", Path(directory))
            self.assertEqual({flavor: path.read_bytes() for flavor, path in written.items()}, archives)

    def test_pair_writes_do_not_expose_unfinished_archives(self):
        archives = {"retail": b"retail fixture", "forever": b"forever fixture"}
        original_open = Path.open
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)

            def observed_open(path, mode="r", *args, **kwargs):
                if "x" in mode:
                    self.assertFalse(list(output.glob("*.zip")), "a final ZIP is visible before the write completed")
                    self.assertNotEqual(path.parent, output, "archive bytes must be staged before publication")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", observed_open):
                written = PACKAGE.write_archives(archives, "1.2.3", output)
            self.assertEqual({flavor: path.read_bytes() for flavor, path in written.items()}, archives)

    def test_pair_resumes_from_an_identical_completed_archive(self):
        archives = {"retail": b"retail fixture", "forever": b"forever fixture"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            existing = PACKAGE.write_archive(archives["retail"], "retail", "1.2.3", output)
            original_stat = existing.stat()
            written = PACKAGE.write_archives(archives, "1.2.3", output)
            self.assertEqual({flavor: path.read_bytes() for flavor, path in written.items()}, archives)
            self.assertTrue(os.path.samestat(original_stat, existing.stat()))

    def test_pair_rechecks_a_reused_archive_after_publishing_its_peer(self):
        archives = {"retail": b"retail fixture", "forever": b"forever fixture"}
        operation = "rename" if os.name == "nt" else "link"
        promote = getattr(os, operation)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            existing = PACKAGE.write_archive(archives["retail"], "retail", "1.2.3", output)

            def publish(source, target, *args, **kwargs):
                result = promote(source, target, *args, **kwargs)
                existing.write_bytes(b"edited fixture")
                return result

            with patch.object(os, operation, side_effect=publish):
                with self.assertRaisesRegex(ValueError, "Archive changed during publication"):
                    PACKAGE.write_archives(archives, "1.2.3", output)
            self.assertEqual(existing.read_bytes(), b"edited fixture")
            self.assertEqual((output / "AntraktFonts-1.2.3-forever.zip").read_bytes(), archives["forever"])

    def test_pair_publish_collision_preserves_complete_outputs(self):
        archives = {"retail": b"retail fixture", "forever": b"forever fixture"}
        operation = "rename" if os.name == "nt" else "link"
        promote = getattr(os, operation)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            competitor = output / "AntraktFonts-1.2.3-forever.zip"

            def publish(source, target, *args, **kwargs):
                if Path(target) == competitor:
                    competitor.write_bytes(b"competing archive")
                return promote(source, target, *args, **kwargs)

            with patch.object(os, operation, side_effect=publish):
                with self.assertRaises(FileExistsError):
                    PACKAGE.write_archives(archives, "1.2.3", output)
            self.assertEqual((output / "AntraktFonts-1.2.3-retail.zip").read_bytes(), archives["retail"])
            self.assertEqual(competitor.read_bytes(), b"competing archive")

    def test_pair_publish_collision_preserves_a_replaced_first_output(self):
        archives = {"retail": b"retail fixture", "forever": b"forever fixture"}
        operation = "rename" if os.name == "nt" else "link"
        promote = getattr(os, operation)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            retail = output / "AntraktFonts-1.2.3-retail.zip"
            forever = output / "AntraktFonts-1.2.3-forever.zip"

            def publish(source, target, *args, **kwargs):
                if Path(target) == forever:
                    replacement = output / "replacement"
                    replacement.write_bytes(b"replaced archive")
                    replacement.replace(retail)
                    forever.write_bytes(b"competing archive")
                return promote(source, target, *args, **kwargs)

            with patch.object(os, operation, side_effect=publish):
                with self.assertRaises(FileExistsError):
                    PACKAGE.write_archives(archives, "1.2.3", output)
            self.assertEqual(retail.read_bytes(), b"replaced archive")
            self.assertEqual(forever.read_bytes(), b"competing archive")

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
            PACKAGE.read_inventory()

    def test_font_changed_after_digest_check_cannot_enter_archive(self):
        original = PACKAGE.safe_file
        font_path = "fonts/DejaVuSans.ttf"
        reads = 0

        class ChangingFont:
            def read_bytes(self):
                nonlocal reads
                reads += 1
                data = (ROOT / font_path).read_bytes()
                return data if reads == 1 else data + b"modified"

        def source(root, relative):
            return ChangingFont() if relative == font_path else original(root, relative)

        with patch.object(PACKAGE, "safe_file", side_effect=source), self.assertRaises(ValueError):
            PACKAGE.archive_bytes("retail", "0.0.0", fixture=True)

    def test_archive_requires_every_toc_load_target(self):
        snapshots = PACKAGE.read_inventory()
        del snapshots["libs/LibStub/LibStub.lua"]
        with patch.object(PACKAGE, "read_inventory", return_value=snapshots):
            with self.assertRaisesRegex(ValueError, "TOC references missing archive file"):
                PACKAGE.archive_bytes("retail", "0.0.0", fixture=True)

    def test_source_mutation_during_package_is_rejected(self):
        # Simulate an external edit while both archives are built from the snapshot.
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
            PACKAGE.archive_set(("retail", "forever"), "0.0.0", fixture=True)

    def test_provenance_input_drift_during_pair_is_rejected(self):
        read_bytes = Path.read_bytes
        original_build = PACKAGE.build_archive
        compressed = False
        receipt = ROOT / "catalog/import-receipt.json"

        def read(path):
            data = read_bytes(path)
            return b"{}" if compressed and path == receipt else data

        def build(*args):
            nonlocal compressed
            result = original_build(*args)
            compressed = True
            return result

        with patch.object(Path, "read_bytes", read), patch.object(PACKAGE, "build_archive", build):
            with self.assertRaisesRegex(ValueError, "Source changed during packaging: catalog/import-receipt.json"):
                PACKAGE.archive_set(("retail", "forever"), "0.0.0", fixture=True)


if __name__ == "__main__":
    unittest.main()
