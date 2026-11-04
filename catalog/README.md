# Shared font contract

`fonts.json` preserves the original font manifest and adds explicit immutable IDs.
The import receipt protects the reviewed original provenance; all 46 font binaries
are unchanged. Font license hashes use the original contract's UTF-8/BOM-aware,
LF-normalized text policy. No runtime component fetches provenance URLs.

`messages.json` owns the fixed `shared-fonts-move-v1` campaign and its 20 strings
in all 11 supported locales. `notLoaded` gives neutral AddOns-list/reload guidance
when the collection is not loaded, without asserting installation status.
`disabled` remains the explicit enable instruction. `enable`, `reloadRequired`,
`enableFailed`, and `reload` support consumer-owned, explicit button actions.
Only display `reloadRequired` after confirming the addon is enabled. A separate
reload click is required; neither opening help nor enabling the addon authorizes
an automatic reload. The coordinator owns no action UI or addon-loading APIs.

`selectedMissing` takes one safe validated display name through `%s`. Optional `downloadReduction` takes one formatted measured
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

For third-party addons, start with the [integration quickstart](../examples/README.md).
The installed provider loads its own `AntraktFonts_Catalog.lua` before its
registration module. Once present and loaded, it exposes:

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

Format 1 permits 1–256 records. IDs are ASCII slugs of at most 64 bytes;
filenames are ASCII and at most 128 bytes; display names are at most 128 UTF-8
bytes. ASCII control characters are forbidden. The generator enforces these common
bounds before producing a catalogue for independently updated consumers.

Keep published IDs and canonical filenames stable across compatible updates.
Consumers may save a complete path without saving a font ID; an older snapshot
cannot recover a renamed path for a face added after that snapshot was shipped.
Update the binary at its existing path, or introduce a new face at a new path.
Changing or retiring a published path requires a separately reviewed compatibility
and migration change rather than routine file cleanup.

The API returns detached tables so callers cannot modify another consumer's
catalogue. Actual LSM registration and existence/application checks are separate.
Consumers validate bounded fields and formatMajor, coalesce cache refreshes on
revision changes, and retain their preferences if the provider is unavailable
or incompatible. Normal LSM names never override an existing registration.
Compatibility is based on `formatMajor`, not equality with the consumer snapshot's
revision. A newer compatible catalogue can add faces independently. A changed
revision invalidates cached catalogues; it is not a reason to reject the provider.

## Optional migration utilities

The consumer snapshot and notice coordinator below support migration in existing
consumers such as StatsPro and DoYouNeedIt. They are not required for either the
standard LSM route or an independent `GetCatalog()` reader. Third-party authors
do not need to copy these utilities or the baseline to use the collection.

### Consumer snapshot

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

Register each consumer with its own campaign state and `canShow`, `show`,
`dismiss`, and `acknowledge` callbacks. `RequestShow()` schedules an automatic
pending notice; `RequestInfo(owner)` explicitly opens contextual help through
the same ownership token, including for fresh or acknowledged accounts. Opening
or hiding a window never acknowledges it. An explicit confirmation persists each
participant's own data; failed writes may retry on a later normal lifecycle event.
Manual contextual requests still honor combat gates and existing modal ownership.
Automatic migration information is unnecessary when the collection is already
compatible and available. A consumer may persist its own `satisfied` state and
map that to coordinator `fresh` (nonpending), rather than falsely acknowledging
other participants. Only an actual user confirmation seeds shared acknowledgement.

Verification:

```text
python tools/generate.py --check
python -m unittest discover -s tests -p test_catalog.py -v
lua5.1 tests/test_notice.lua
luac5.1 -p AntraktFonts_Catalog.lua consumer/AntraktFontCatalog.lua
```

No marketplace publication, client activation or native visual acceptance is
established by these offline contract checks.
