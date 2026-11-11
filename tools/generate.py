"""Generate the provider catalogue and portable consumer snapshot offline."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LOCALES = {"enUS", "deDE", "esES", "esMX", "frFR", "itIT", "koKR", "ptBR", "ruRU", "zhCN", "zhTW"}
WESTERN_LOCALES = LOCALES - {"koKR", "ruRU", "zhCN", "zhTW"}
GLYPH_FIELDS = ("latin", "cyrillic", "hans", "hant", "hangul", "japanese")
LEGACY_ADDONS = ("StatsPro", "DoYouNeedIt")
BASELINE_ID = "antrakt-ui-sans"
BASELINE_FILENAME = "AntraktUISans.ttf"
MESSAGE_KEYS = {
    "title", "missing", "ready", "settingsMissing", "selectedMissing", "disabled", "notLoaded",
    "incompatible", "assetUnavailable", "details", "gotIt", "copyLink",
    "copyTitle", "copyInstructions", "linkUnavailable",
    "downloadReduction", "enable", "reloadRequired", "enableFailed", "reload",
}


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bytes(path: str) -> bytes:
    return (ROOT / path).read_bytes()


def read_json(path: str) -> dict:
    return json.loads(read_bytes(path).decode("utf-8"))


def clean_text(value: object, maximum: int = 1024) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def build_contract(read_source: Callable[[str], bytes] | None = None) -> dict:
    read = read_source or read_bytes

    def metadata(path: str) -> dict:
        if read_source is None:
            return read_json(path)
        return json.loads(read(path).decode("utf-8"))

    source = metadata("catalog/fonts.json")
    receipt = metadata("catalog/import-receipt.json")
    if not isinstance(source["fonts"], list) or not 1 <= len(source["fonts"]) <= 256:
        raise ValueError("Font catalogue must contain 1 to 256 records")
    without_ids = {**source, "fonts": [{key: value for key, value in font.items() if key != "id"} for font in source["fonts"]]}
    if sha(canonical(without_ids)) != receipt["canonicalManifestSha256WithoutAddedIds"]:
        raise ValueError("Font provenance differs from its reviewed import receipt")
    if source["schemaVersion"] != 1 or len(source["fonts"]) != receipt["fontCount"]:
        raise ValueError("Unsupported source catalogue")
    retired = source["retiredFonts"]
    if not isinstance(retired, dict):
        raise ValueError("Invalid retired font map")
    records, identities, filenames, names = [], set(), set(), set()
    for font in source["fonts"]:
        identity = font["id"]
        filename = font["path"].removeprefix("fonts/")
        if not clean_text(identity, 64) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identity):
            raise ValueError("Invalid stable font ID")
        if identity == BASELINE_ID:
            raise ValueError(f"Reserved baseline font ID: {identity}")
        if len(filename) > 128 or not re.fullmatch(r"[A-Za-z0-9_.-]+\.(ttf|otf)", filename) or font["path"] != "fonts/" + filename:
            raise ValueError("Invalid font file path")
        if filename.lower() == BASELINE_FILENAME.lower():
            raise ValueError(f"Reserved baseline font filename: {filename}")
        if not clean_text(font["name"], 128) or len(font["name"].encode("utf-8")) > 128:
            raise ValueError("Invalid font name")
        if identity in identities or filename.lower() in filenames or font["name"] in names:
            raise ValueError("Duplicate font identity, file or name")
        identities.add(identity)
        filenames.add(filename.lower())
        names.add(font["name"])
        for key in ("sha256", "licenseSha256"):
            if not re.fullmatch(r"[A-F0-9]{64}", font[key]):
                raise ValueError("Invalid source hash")
        if sha(read(font["path"])).upper() != font["sha256"]:
            raise ValueError(f"Font binary differs from provenance: {filename}")
        license_path = font["licenseFile"]
        if not re.fullmatch(r"fonts/licenses/[A-Za-z0-9_.-]+\.txt", license_path):
            raise ValueError("Invalid license file path")
        license_text = read(license_path).decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        if sha(license_text.encode()).upper() != font["licenseSha256"]:
            raise ValueError(f"License differs from provenance: {license_path}")
        if not clean_text(font["source"]) or not font["source"].startswith("https://"):
            raise ValueError("Invalid provenance URL")
        if not clean_text(font["license"], 64) or not clean_text(font["sourceRevision"], 128):
            raise ValueError("Missing license or pinned source revision")
        record = {
            "id": identity, "name": font["name"], "file": filename,
            "path": "Interface\\AddOns\\AntraktFonts\\fonts\\" + filename,
            "sha256": font["sha256"].lower(),
        }
        for key in GLYPH_FIELDS:
            value = font.get(key, key == "latin")
            if type(value) is not bool:
                raise ValueError(f"Invalid coverage flag: {key}")
            record[key] = value
        if "region" in font:
            if font["region"] not in ("zhCN", "zhTW"):
                raise ValueError("Invalid glyph presentation region")
            record["region"] = font["region"]
        if "latinLocales" in font:
            locales = font["latinLocales"]
            if not isinstance(locales, list) or not locales or len(set(locales)) != len(locales) or not set(locales) <= WESTERN_LOCALES:
                raise ValueError("Invalid Latin locale coverage")
            record["latinLocales"] = {locale: True for locale in locales}
        aliases = [filename] + sorted(old for old, target in retired.items() if target == filename)
        record["aliases"] = ["Interface\\AddOns\\" + addon + "\\fonts\\" + old for addon in LEGACY_ADDONS for old in aliases]
        records.append(record)
    if any(target.lower() not in filenames for target in retired.values()):
        raise ValueError("Retired font target is not in the catalogue")
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]+\.(ttf|otf)", filename) for filename in retired):
        raise ValueError("Invalid retired filename")
    message_source = metadata("catalog/messages.json")
    if message_source["campaign"] != "shared-fonts-move-v1":
        raise ValueError("Unexpected font-transition campaign")
    messages = message_source["locales"]
    if set(messages) != LOCALES:
        raise ValueError("Every supported locale needs font-transition copy")
    for locale, values in messages.items():
        if set(values) != MESSAGE_KEYS or not all(clean_text(value, 1024) for value in values.values()):
            raise ValueError(f"Invalid font-transition messages: {locale}")
        for key, text in values.items():
            placeholders = re.findall(r"%.", text)
            if placeholders != (["%s"] if key in ("selectedMissing", "downloadReduction") else []):
                raise ValueError(f"Unexpected message placeholders: {locale}/{key}")
    links = metadata("catalog/distribution.json")
    if set(links) != {"github", "curseforge", "wago"}:
        raise ValueError("Unexpected distribution service")
    for service, value in links.items():
        if value is None:
            continue
        if not clean_text(value, 512):
            raise ValueError(f"Invalid distribution link: {service}")
        url = urlsplit(value)
        hosts, pattern = {
            "github": ({"github.com"}, r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?"),
            "curseforge": ({"curseforge.com", "www.curseforge.com"}, r"/wow/addons/[a-z0-9-]+/?"),
            "wago": ({"addons.wago.io"}, r"/addons/[A-Za-z0-9-]+/?"),
        }[service]
        if url.scheme != "https" or url.netloc not in hosts or url.username or url.password or url.query or url.fragment or not re.fullmatch(pattern, url.path):
            raise ValueError(f"Invalid distribution link: {service}")
    baseline = metadata("baseline/build.json")
    if sha(read("baseline/" + BASELINE_FILENAME)) != baseline["sha256"]:
        raise ValueError("Baseline differs from its pinned build receipt")
    contract = {
        "formatMajor": 1,
        "fonts": records,
        "retiredFonts": retired,
        "baseline": {
            "id": BASELINE_ID, "name": baseline["family"],
            "file": BASELINE_FILENAME, "sha256": baseline["sha256"],
            **{key: True for key in GLYPH_FIELDS},
        },
        "campaign": message_source["campaign"],
        "messages": messages,
        "links": links,
    }
    return {"catalogRevision": sha(canonical(contract)), **contract}


def lua(value: object, depth: int = 0) -> str:
    if value is None:
        return "nil"
    if type(value) is bool:
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    indent = "    " * depth
    child_indent = indent + "    "
    if isinstance(value, list):
        items = [lua(child, depth + 1) + "," for child in value]
    elif isinstance(value, dict):
        items = [f"[{lua(key)}] = {lua(child, depth + 1)}," for key, child in value.items()]
    else:
        raise TypeError(type(value))
    return "{\n" + "\n".join(child_indent + child for child in items) + "\n" + indent + "}"


def outputs(read_source: Callable[[str], bytes] | None = None) -> dict[Path, bytes]:
    contract = build_contract(read_source)
    provider = {key: contract[key] for key in ("formatMajor", "catalogRevision", "fonts")}
    header = "-- Generated by tools/generate.py; edit the source catalogues instead.\n"
    provider_lua = header + "local catalog = " + lua(provider) + "\n\n" + """-- Give callers detached records so a picker cannot mutate another addon's data.
local function copy(value)
    if type(value) ~= "table" then return value end
    local result = {}
    for key, child in pairs(value) do result[key] = copy(child) end
    return result
end
_G.AntraktFonts = { GetCatalog = function() return copy(catalog) end }
return catalog
"""
    consumer_lua = header + "local _, namespace = ...\nlocal catalog = " + lua(contract) + "\n" + """if type(namespace) == "table" then namespace.AntraktFontCatalog = catalog end
return catalog
"""
    generated = {
        ROOT / "AntraktFonts_Catalog.lua": provider_lua.encode(),
        ROOT / "consumer/AntraktFontCatalog.lua": consumer_lua.encode(),
    }
    try:
        notice = (read_source or read_bytes)("consumer/AntraktFontNotice.lua")
    except FileNotFoundError as error:
        raise ValueError("The canonical shared notice module is missing") from error
    exported = {
        "schemaVersion": 1,
        "catalogRevision": contract["catalogRevision"],
        "modules": {
            "AntraktFontCatalog.lua": sha(consumer_lua.encode()),
            "AntraktFontNotice.lua": sha(notice),
        },
        "baseline": contract["baseline"],
    }
    generated[ROOT / "consumer/files.json"] = (json.dumps(exported, indent=2) + "\n").encode()
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, data in outputs().items():
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise SystemExit(f"Generated file differs: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print("Font catalogue and consumer snapshot: verified" if args.check else "Font catalogue and consumer snapshot: generated")


if __name__ == "__main__":
    main()
