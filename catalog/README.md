# Shared font contract

`fonts.json` preserves the original font manifest and adds explicit immutable IDs.
The import receipt protects the reviewed original provenance; all 46 font binaries
are unchanged. Font license hashes use the original contract's UTF-8/BOM-aware,
LF-normalized text policy. No runtime component fetches provenance URLs.

`messages.json` owns the fixed `shared-fonts-move-v1` campaign and its 15 strings
in all 11 supported locales. `selectedMissing` takes one safe validated display
name through `%s`. Optional `downloadReduction` takes one formatted measured
percentage (including its percent sign) through `%s`. Show it only when that
consumer's actual old/new release archives have a verified size comparison;
omit it when no measurement is available. Never substitute a guessed percentage.
`distribution.json` contains real public project links or null. Null means the
UI must show `linkUnavailable` instead of an active copy/download action. Local
generation works before marketplace projects exist; no invented project IDs.

Run `python tools/generate.py`, or `python tools/generate.py --check` for a
read-only exact-output check. The generator needs only Python's standard library
and checked local inputs. It does not rebuild the baseline or consult a sibling
checkout. Its outputs and source catalogue snapshots are committed together.

## Provider API

Load `AntraktFonts_Catalog.lua` before the registration module. It exposes:

```lua
local catalog = AntraktFonts.GetCatalog()
-- catalog.formatMajor == 1
-- catalog.catalogRevision is a deterministic SHA256 digest
-- catalog.fonts is an ordered array of detached records
```

Each record has `id`, ordinary unprefixed `name`, `file`, canonical `path`,
declared `sha256`, six explicit glyph booleans, and exact legacy-path `aliases`.
Optional `latinLocales` is a locale-to-true map; optional `region` preserves the
original CN/TW picker rule. IDs do not change when display names change. Alias
matching requires a complete normalized path, never a basename or a same-name
third-party LSM entry. Hashes are build/package evidence, not a Lua claim that
the game has hashed or successfully applied a file.

The API returns detached tables so callers cannot modify another consumer's
catalogue. Actual LSM registration and existence/application checks are separate.
Consumers validate bounded fields and formatMajor, coalesce cache refreshes on
revision changes, and retain their preferences if the provider is unavailable
or incompatible. Normal LSM names never override an existing registration.
Compatibility is based on `formatMajor`, not equality with the consumer snapshot's
revision. A newer compatible catalogue can add faces independently. A changed
revision invalidates cached catalogues; it is not a reason to reject the provider.

## Consumer snapshot

Copy `consumer/AntraktFontCatalog.lua` unchanged into each consumer. It attaches
to `namespace.AntraktFontCatalog` from `local _, namespace = ...` and returns
the same table for standalone fixtures. It creates no global snapshot and does
not assign `fontRuntime`. It contains provider metadata plus `retiredFonts`,
`baseline`, `campaign`, `messages`, and nullable `links`.

`baseline.file` is only `AntraktUISans.ttf`; the consumer resolves its own
`Interface/AddOns/<consumer>/fonts/` path, independently of the optional provider.
Its exact hash is pinned. It declares script coverage, not every Unicode glyph.
Ship the baseline's NOTICE and all baseline license materials too.

`consumer/AntraktFontNotice.lua` is the separately owned shared campaign-state
coordinator. The generator reads but never rewrites it. `consumer/files.json`
pins both portable module hashes and the baseline identity. Consumers copy and
check those bytes; they keep private UI adapters and SavedVariables ownership.
The snapshot does not implement UI, profile migration or notice persistence.

Verification:

```text
python tools/generate.py --check
python -m unittest discover -s tests -p test_catalog.py -v
lua5.1 tests/test_notice.lua
luac5.1 -p AntraktFonts_Catalog.lua consumer/AntraktFontCatalog.lua
```

No marketplace publication, client activation or native visual acceptance is
established by these offline contract checks.
