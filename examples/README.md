# Integrating fonts in another addon

You can use either route below. Both are optional: keep your own readable fallback,
font settings and renderer when Antrakt Fonts is absent. Neither route requires
StatsPro or DoYouNeedIt, copying the collection, our baseline, migration aliases,
a catalog snapshot, or the shared notice coordinator. No UI toolkit is required.

## Standard LibSharedMedia route

If your addon already uses LibSharedMedia-3.0, the enabled Antrakt Fonts addon
registers ordinary font names with that library. Use your existing picker and
refresh it when media is registered. For example, resolve your selected name with
`media:Fetch("font", selectedName, true)` and use your own fallback when it returns
nil. The final `true` prevents an unknown name silently choosing LSM's default.
LSM's existing global override, if one is configured, still follows LSM semantics.

Do not replace another addon's registration or set LSM's global/default font.
The first owner of a name wins. A same-name third-party font is a valid LSM choice,
but does not identify a particular Antrakt Fonts file. Libraries register fonts
for the client locale; a different output language needs your own filtering.

## Catalog route for an exact file or a custom picker

The loaded provider exposes `_G.AntraktFonts.GetCatalog()`. Call it at startup,
on `ADDON_LOADED` for `AntraktFonts`, or when opening/refreshing your own picker.
Validate `formatMajor == 1` and the bounded fields in the
[API contract](../catalog/README.md). Cache the result; do not call it every frame
or once per rendered label. It returns detached tables.

The identity is **provider `AntraktFonts` plus immutable font `id`**. Render from
its canonical `path`, not a guessed basename or a global LSM name. Published IDs
and filenames stay stable across compatible updates. Accept a new compatible
`catalogRevision`; a differing revision invalidates cached choices and can add
faces without shipping a snapshot in your addon. An unknown major format falls
back without overwriting the user's selection.

Filter using the six glyph flags, optional `latinLocales`, and CN/TW `region`.
A script flag is not a promise of every Unicode character or correct regional
forms. Metadata and file existence do not prove that a native FontString applied
a file. Use your renderer's normal asset activation and `GetFont` checks, retaining
fallback behavior and the selected identity when a file cannot be applied.
`SetFont` returning nil is not by itself a failure.

## Checked independent example

[IndependentFonts.lua](IndependentFonts.lua) is the actual standalone example
executed by the local tests. It uses only its own addon namespace, transient
selection and caller-owned fallback. It can resolve either a standard LSM name
or a canonical catalog ID. It creates no visible window or SavedVariables and
does not enable/load another addon, set a global font, or change another addon's
settings. It is example code, not a new required provider API or framework.

Use the optional dependency from [IndependentFonts.toc](IndependentFonts.toc).
For Forever beta use [IndependentFonts_Forever.toc](IndependentFonts_Forever.toc),
named `IndependentFonts.toc` in that example addon's folder. In an existing addon,
retain its own Interface metadata and load this Lua after its normal setup. An
existing embedded LSM copy can stay in its usual place; the example also handles
LSM being absent. Installing this example is not part of the provider package.

The namespace can supply `fallbackFont`, `outputLocale` and `OnFontsChanged`
before the file loads. Its default fallback is the client's `STANDARD_TEXT_FONT`;
replace it with a font you have tested for your own UI. For a different output
language, call `SetLocale(locale, readableFallback)` with a suitable fallback.

The example's `FontChoices.SelectMedia(name)` and `SelectCatalog(id)` change only
its in-memory choice. `Resolve()` returns the chosen path or fallback without
rewriting that choice. `ListCatalog()` returns locale-filtered rows for your own
picker. Your addon decides whether and how to persist a choice and apply it to
its own widgets. Provider presence does not select a font automatically.

The example reads the catalog initially even when all LSM names are occupied.
It listens for the provider's `ADDON_LOADED` event as well as coalesced LSM font
registration callbacks, since a fully occupied registry emits no new callback.
Call `FontChoices.Refresh()` when your own picker opens to refresh its cached
catalog. `OnFontsChanged` is where your addon can refresh its UI. There is no
per-frame polling or automatic application to someone else's FontObjects.

Run the example regression with `lua5.1 tests/test_example_consumer.lua`, or the
full gate with `python scripts/check.py`. The gate discovers this `test_*.lua`
fixture and checks the example's Lua syntax. The fixture uses the actual bundled
LSM and executes this same file with provider absent/present/late, colliding names,
all names occupied, locale changes, newer revisions and unsupported formats.
Offline checks establish these integration contracts, not native visual acceptance.
