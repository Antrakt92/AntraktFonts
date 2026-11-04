"""Check imported assets, generated contracts and real Lua consumers offline."""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("generate", ROOT / "tools/generate.py")
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = GENERATOR.build_contract()
        cls.source = json.loads((ROOT / "catalog/fonts.json").read_text())
        cls.records = {record["id"]: record for record in cls.contract["fonts"]}
        cls.corpus = json.loads((ROOT / "baseline/corpus.json").read_text())

    def test_generated_files_and_export_digests_are_exact(self):
        for path, data in GENERATOR.outputs().items():
            self.assertEqual(path.read_bytes(), data, path.name)
        exported = json.loads((ROOT / "consumer/files.json").read_text())
        for name, digest in exported["modules"].items():
            self.assertEqual(GENERATOR.sha((ROOT / "consumer" / name).read_bytes()), digest)
        self.assertEqual(exported["catalogRevision"], self.contract["catalogRevision"])

    def test_original_inventory_and_declared_hashes_are_preserved(self):
        fonts = self.source["fonts"]
        self.assertEqual(len(fonts), 46)
        self.assertEqual(sum((ROOT / font["path"]).stat().st_size for font in fonts), 68465504)
        expected = {font["path"] for font in fonts}
        expected.update(font["licenseFile"] for font in fonts)
        actual = {path.relative_to(ROOT).as_posix() for path in (ROOT / "fonts").rglob("*") if path.is_file()}
        self.assertEqual(expected, actual)
        for font in fonts:
            self.assertEqual(GENERATOR.sha((ROOT / font["path"]).read_bytes()).upper(), font["sha256"])
            self.assertEqual(GENERATOR.sha((ROOT / font["licenseFile"]).read_bytes()).upper(), font["licenseSha256"])

    def test_path_aliases_resolve_owned_identity_without_name_guessing(self):
        aliases = {}
        for font in self.source["fonts"]:
            record = self.records[font["id"]]
            self.assertEqual(record["name"], font["name"])
            self.assertEqual(record["path"], "Interface\\AddOns\\AntraktFonts\\" + font["path"].replace("/", "\\"))
            self.assertEqual(record["sha256"].upper(), font["sha256"])
            for key in GENERATOR.GLYPH_FIELDS:
                self.assertEqual(record[key], font.get(key, key == "latin"))
            for path in record["aliases"]:
                self.assertNotIn(path.lower(), aliases)
                aliases[path.lower()] = record["id"]
        self.assertEqual(aliases["interface\\addons\\statspro\\fonts\\firamono-regular.ttf"], "hack")
        self.assertEqual(aliases["interface\\addons\\doyouneedit\\fonts\\liberationmono-regular.ttf"], "hack")
        self.assertNotIn("hack-regular.ttf", aliases)
        self.assertEqual(len(aliases), 96)

    def test_real_binary_glyph_flags_retain_original_language_contract(self):
        required = {field: set() for field in GENERATOR.GLYPH_FIELDS}
        required["latin"].update(range(32, 127))
        required["cyrillic"] = set(range(0x410, 0x450)) | {0x401, 0x451}
        required["japanese"] = set(range(0x3041, 0x3094)) | set(range(0x30A1, 0x30F7))
        for locale, codes in self.corpus["locales"]["StatsPro"].items():
            if locale in GENERATOR.WESTERN_LOCALES:
                required["latin"].update(code for code in codes if 0xC0 <= code <= 0x24F and code not in (0xD7, 0xF7))
            elif locale in ("zhCN", "zhTW"):
                required["hans" if locale == "zhCN" else "hant"].update(code for code in codes if 0x3400 <= code <= 0x9FFF)
            elif locale == "koKR":
                required["hangul"].update(code for code in codes if 0xAC00 <= code <= 0xD7A3)
        for font in self.source["fonts"]:
            binary = TTFont(ROOT / font["path"])
            codes = set(binary.getBestCmap())
            self.assertNotIn("fvar", binary)
            for field, needed in required.items():
                self.assertEqual(needed <= codes, font.get(field, field == "latin"), (font["name"], field))
            if "latinLocales" in font:
                for locale in GENERATOR.WESTERN_LOCALES:
                    needed = set(range(32, 127)) | {code for code in self.corpus["locales"]["StatsPro"][locale] if 0xC0 <= code <= 0x24F and code not in (0xD7, 0xF7)}
                    self.assertEqual(needed <= codes, locale in font["latinLocales"], (font["name"], locale))

    def test_all_new_copy_is_localized_and_covered_by_baseline(self):
        codes = set(TTFont(ROOT / "baseline/AntraktUISans.ttf").getBestCmap())
        self.assertEqual(set(self.contract["messages"]), GENERATOR.LOCALES)
        for locale, values in self.contract["messages"].items():
            self.assertEqual(set(values), GENERATOR.MESSAGE_KEYS)
            for key, text in values.items():
                self.assertEqual({ord(char) for char in text} - codes, set(), (locale, key))
        self.assertEqual(self.contract["baseline"]["file"], "AntraktUISans.ttf")
        self.assertNotIn("path", self.contract["baseline"])
        self.assertEqual(set(self.contract["links"]), {"github", "curseforge", "wago"})

    def test_explicit_enable_action_copy_is_localized_and_bounded(self):
        for locale, values in self.contract["messages"].items():
            with self.subTest(locale=locale):
                for key in ("enable", "reloadRequired", "enableFailed", "reload"):
                    self.assertIn(key, values)
                    self.assertNotIn("%", values[key])
                self.assertEqual(len({values[key] for key in ("enable", "reloadRequired", "enableFailed", "reload", "notLoaded", "disabled")}), 6)
        original = GENERATOR.read_json
        for key in ("enable", "reloadRequired", "enableFailed", "reload"):
            for mutation in ("missing", "placeholder"):
                altered = copy.deepcopy(original("catalog/messages.json"))
                if mutation == "missing":
                    altered["locales"]["enUS"].pop(key)
                else:
                    altered["locales"]["enUS"][key] = "Unexpected %s placeholder"
                with self.subTest(key=key, mutation=mutation), patch.object(GENERATOR, "read_json", side_effect=lambda path: altered if path == "catalog/messages.json" else original(path)):
                    with self.assertRaises(ValueError):
                        GENERATOR.build_contract()

    def test_not_loaded_guidance_is_localized_and_bounded(self):
        for locale, values in self.contract["messages"].items():
            with self.subTest(locale=locale):
                self.assertEqual(len(values), 20)
                self.assertIn("notLoaded", values)
                self.assertNotEqual(values["notLoaded"], values["disabled"])
                self.assertNotEqual(values["notLoaded"], values["settingsMissing"])
                self.assertNotIn("%", values["notLoaded"])
        original = GENERATOR.read_json
        for mutation in ("missing", "extra", "placeholder"):
            altered = copy.deepcopy(original("catalog/messages.json"))
            if mutation == "missing":
                altered["locales"]["enUS"].pop("notLoaded")
            elif mutation == "extra":
                altered["locales"]["enUS"]["unboundedState"] = "Unexpected state"
            else:
                altered["locales"]["enUS"]["notLoaded"] = "Unexpected %s placeholder"
            with self.subTest(mutation=mutation), patch.object(
                GENERATOR, "read_json", side_effect=lambda path: altered if path == "catalog/messages.json" else original(path)
            ):
                with self.assertRaises(ValueError):
                    GENERATOR.build_contract()

    def test_invalid_distribution_links_and_duplicate_id_are_rejected(self):
        original = GENERATOR.read_json
        for bad_source in ("catalog/distribution.json", "catalog/fonts.json"):
            altered = copy.deepcopy(original(bad_source))
            if bad_source.endswith("distribution.json"):
                altered["github"] = "https://unrelated.invalid/owner/repo"
            else:
                altered["fonts"][1]["id"] = altered["fonts"][0]["id"]
            with self.subTest(source=bad_source), patch.object(GENERATOR, "read_json", side_effect=lambda path: altered if path == bad_source else original(path)):
                with self.assertRaises(ValueError):
                    GENERATOR.build_contract()
        for service, bad_url in (
            ("github", "https://user:password@github.com/owner/repo"),
            ("github", "https://github.com/owner/repo?token=private"),
            ("github", "https://github.com/owner/repo#private"),
            ("github", "https://github.com.attacker.invalid/owner/repo"),
            ("github", "http://github.com/owner/repo"),
            ("github", "https://github.com/owner/repo/releases"),
            ("curseforge", "https://www.curseforge.com/minecraft/mc-mods/font"),
            ("wago", "https://addons.wago.io/invalid-path/font"),
        ):
            altered = {"github": None, "curseforge": None, "wago": None, service: bad_url}
            with self.subTest(link=bad_url), patch.object(GENERATOR, "read_json", side_effect=lambda path: altered if path == "catalog/distribution.json" else original(path)):
                with self.assertRaises(ValueError):
                    GENERATOR.build_contract()

    def test_future_catalogue_obeys_shared_format_one_byte_and_count_bounds(self):
        original_json, original_bytes = GENERATOR.read_json, Path.read_bytes
        binary = original_bytes(ROOT / self.source["fonts"][0]["path"])

        def future_source(count=1, filename="future.ttf", name="Future Font", identity="future-font"):
            source = copy.deepcopy(self.source)
            source["retiredFonts"] = {}
            source["fonts"] = []
            for index in range(count):
                font = copy.deepcopy(self.source["fonts"][0])
                font.update(id=identity if count == 1 else "future-" + str(index),
                            name=name if count == 1 else "Future " + str(index),
                            path="fonts/" + (filename if count == 1 else "future-" + str(index) + ".ttf"))
                source["fonts"].append(font)
            return source

        def build_future(source):
            # Future imports legitimately update their receipt; bounds must hold
            # independently of today's exact reviewed inventory and asset names.
            receipt = copy.deepcopy(original_json("catalog/import-receipt.json"))
            receipt["fontCount"] = len(source["fonts"])
            without_ids = {**source, "fonts": [{k: v for k, v in font.items() if k != "id"} for font in source["fonts"]]}
            receipt["canonicalManifestSha256WithoutAddedIds"] = GENERATOR.sha(GENERATOR.canonical(without_ids))
            replacements = {ROOT / font["path"] for font in source["fonts"]}
            def read_json(path):
                if path == "catalog/fonts.json": return source
                if path == "catalog/import-receipt.json": return receipt
                return original_json(path)
            def read_bytes(path):
                return binary if path in replacements else original_bytes(path)
            with patch.object(GENERATOR, "read_json", side_effect=read_json), patch.object(Path, "read_bytes", read_bytes):
                return GENERATOR.build_contract()

        for source in (
            future_source(count=0), future_source(count=257),
            future_source(filename="a" * 125 + ".ttf"),
            future_source(name="\u5b57" * 43),
            future_source(name="Future\x7fFont"),
        ):
            with self.subTest(count=len(source["fonts"]),
                              file_bytes=len(source["fonts"][0]["path"].removeprefix("fonts/").encode()) if source["fonts"] else 0,
                              name_bytes=len(source["fonts"][0]["name"].encode()) if source["fonts"] else 0):
                with self.assertRaises(ValueError): build_future(source)
        for source in (
            future_source(filename="a" * 124 + ".ttf", name="\u5b57" * 42 + "AB", identity="a" * 64),
            future_source(count=256),
        ):
            with self.subTest(valid_count=len(source["fonts"])):
                self.assertEqual(len(build_future(source)["fonts"]), len(source["fonts"]))

    def test_lua_api_snapshot_namespace_and_detached_provider_data(self):
        lua = shutil.which("lua5.1")
        self.assertIsNotNone(lua, "Lua 5.1 is required for the runtime contract test")
        result = subprocess.run([lua, "-"], cwd=ROOT, input=r'''
local checks = 0
local function check(value) checks = checks + 1; assert(value) end
local snapshot = assert(loadfile("consumer/AntraktFontCatalog.lua"))()
check(snapshot.formatMajor == 1 and #snapshot.fonts == 46)
check(_G.AntraktFontCatalog == nil and _G.AntraktFonts == nil)
local namespace = {}
local attached = assert(loadfile("consumer/AntraktFontCatalog.lua"))("Example", namespace)
check(namespace.AntraktFontCatalog == attached)
check(namespace.fontRuntime == nil)
assert(loadfile("AntraktFonts_Catalog.lua"))()
local provider = _G.AntraktFonts.GetCatalog()
check(provider.formatMajor == 1 and provider.catalogRevision == snapshot.catalogRevision)
check(provider.messages == nil and provider.baseline == nil)
for index, font in ipairs(provider.fonts) do
    check(font.id == snapshot.fonts[index].id and font.path == snapshot.fonts[index].path)
    check(font.path:find("Interface\\AddOns\\AntraktFonts\\fonts\\", 1, true) == 1)
end
provider.fonts[1].name = "changed by a picker"
provider.fonts[1].aliases[1] = "changed alias"
local fresh = _G.AntraktFonts.GetCatalog()
check(fresh.fonts[1].name ~= provider.fonts[1].name)
check(fresh.fonts[1].aliases[1] ~= provider.fonts[1].aliases[1])
check(snapshot.baseline.path == nil and snapshot.baseline.file == "AntraktUISans.ttf")
for _, link in pairs(snapshot.links) do check(type(link) == "string" and link:match("^https://")) end
check(snapshot.campaign == "shared-fonts-move-v1")
print("Lua catalogue contract: " .. checks .. " checks passed")
'''.encode(), capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(b"checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
