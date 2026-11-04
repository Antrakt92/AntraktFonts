# Development

Run the complete local gate with:

```text
python scripts/check.py
```

The gate requires Python, the exact existing fontTools dependency in
`requirements-build.txt`, and Lua 5.1 (`lua5.1` and `luac5.1`). It checks source
hashes, generated contracts, font glyph coverage, deterministic baseline rebuilds,
actual bundled library behavior, the shared notice protocol, both package flavors
and Lua syntax. It installs nothing and invokes no hosted tests.

`python tools/generate.py --check` checks committed catalogue outputs without
changing them. See `catalog/README.md` for the API and portable consumer modules.
The baseline recipe in `baseline/` is a separate asset role: consumers carry its
verified TTF and notices. It is excluded from the optional collection's ZIP.

## Connecting another addon

The [integration quickstart](examples/README.md) explains ordinary LSM use and
an optional catalog reader. Its checked [independent example](examples/IndependentFonts.lua)
uses neither core addon nor the migration/notice modules. The local gate executes
that exact source through `tests/test_example_consumer.lua`; it is excluded from
installable provider archives. Your addon retains its own UI, preferences and
readable fallback.

## Local packages

`python scripts/package.py --flavor retail --version <reviewed-version>` builds
the Retail archive; use `--flavor forever` for Forever beta. A version is required;
there is no default or implicit publication. Select it from the full unreleased
range before preparing a release. Source TOCs retain `@project-version@`.
The packager never modifies source files and refuses to overwrite an archive.

Only exact runtime files, fonts, font/library license materials, the project
license, third-party notices and cumulative changelog are included. Each archive
contains one `AntraktFonts/AntraktFonts.toc`, selected for its client. Development
source, baseline inputs, portable consumer modules and test assets are excluded.

The tests use version `0.0.0` only for disposable package fixtures. It is not a
proposed release. No hosted workflow, marketplace project or publication is
created by a build or test command.

## Native acceptance

Offline checks do not establish client loading or visual readability. Before
release, test the matching archive in each supported client with the provider
alone, each consumer, both consumers, and another shared-media addon loaded first.
Confirm the catalogue still works when every normal LSM name is already owned
by another addon and no new registration callback fires.

Check cold login, font selection and preview/cancel, reload, small font sizes,
outlines, mixed Latin/Cyrillic/Chinese/Korean text, CN/TW forms, and combat entry
and exit. Verify that removing the optional package preserves the user's choice
while the consumer uses its readable baseline. Never infer activation from file
existence or an offline SetFont mock.

Discover current client paths and retain installed-addon ownership before any
installation. Builds do not install files or launch the game. Any diagnostic
probe should use fixed sample text and log only sample IDs, font paths, sizes,
flags and application observations; never player names, item data or other
live gameplay text.
