# Antrakt UI Sans baseline

This is the reproducible baseline asset for consumer addons. It is separate
from the optional 46-font collection and is not automatically included in that
collection's installable archive. Consumers commit the verified generated TTF
and all accompanying notices/licenses; their ordinary builds need no sibling
checkout, fontTools, network access or font regeneration.

Build with the exact dependency in `../requirements-build.txt` already available:

```text
python tools/build_baseline.py --output baseline/AntraktUISans.ttf --receipt baseline/build.json
python -m unittest discover -s tests -p test_baseline.py -v
python tools/build_baseline.py --check
```

The script reads only pinned local sources, verifies every source/license hash,
keeps the Noto mappings first, removes overlapping Droid mappings and Droid
hinting, scales its complementary outlines from 256 to 1000 UPEM, then merges
OpenType layout and outlines. This keeps the full Unicode union, not a subset
of current UI translations. It fixes timestamps and records the recipe digest
in the renamed font. Both independent test rebuilds must equal the checked asset.
The new font family's own revision is 1.000 in both name ID 5 and head.fontRevision;
it is independent of consumer/provider release versions and upstream revisions.

## Coverage and remaining acceptance

The font contains 32,092 mapped codepoints, including all 11,172 modern Hangul
syllables, Russian letters, and 16,504 Han characters in U+4E00..U+9FFF. This is
not every Unicode character. `corpus.json` records the actual pre-transition
runtime locale-table inventories and full-source non-ASCII inventories.
StatsPro's warning U+26A0 and expand/collapse minus U+2212 are explicitly missing;
the consumer transition must replace those UI symbols with supported graphics
or ASCII controls before its live zero-missing coverage gate can pass. Historical
fixture tests identify the exact gaps rather than hiding arbitrary missing text.

The output deliberately retains merger-derived conservative metrics:
hhea ascent/descent/lineGap 1069/-293/0; OS/2 typographic values 1069/-293/63.
The latter lineGap is the rounded scaled Droid value, not an unexplained
replacement for zero. No metric is reduced to claim a layout improvement.
All Noto Unicode advance widths, its fpgm/prep/cvt programs and tables survive.
Droid complementary glyphs are unhinted after scaling; visual quality is unproven.

Native acceptance is required in both supported clients: fresh cold load,
SetFont/GetFont application, small HUD sizes, outlines, text width/height,
mixed Latin/Cyrillic/Chinese/Korean names, CN/TW regional forms, profile/UI
previews and combat/reload. Offline cmap, checksum and rebuild tests do not
establish game loading or readability. See `build.json` for exact size/hash.

## Derivative licensing and metadata

`sources.json` pins both original binaries and unmodified upstream licenses.
The combined modified font is distributed under OFL-1.1, with the original
Droid Apache-2.0 terms, copyright, trademarks and NOTICE retained. The renamed
family is Antrakt UI Sans; it is not an official Noto or Droid release.
`NOTICE.txt` describes the changes and original authors. Ship it and the entire
`licenses/` directory alongside every copy of the TTF. The font's name records
include both original copyright/authorship/trademark and license information.

The basis for the combined derivative is Apache 2.0 sections 2 and 4, including
the provision permitting additional/different terms for a derivative as a
whole while retaining Apache obligations, plus OFL conditions 2/3/5 and FAQ 3.2.
This does not relicense or remove the original Droid source's Apache notices.

The output's OS/2 fsType is explicitly zero (installable embedding), rather than
inheriting Droid's historical editable-only value 8: OFL permits embedding and
the included Apache license grants reproduction/derivative distribution without
that metadata restriction. Source binaries are unchanged. This follows the OFL
FAQ's instruction to avoid metadata contradicting the license; it changes no
copyright, trademark or source-license terms.

References:

- https://www.apache.org/licenses/LICENSE-2.0 (sections 2 and 4)
- https://openfontlicense.org/ofl-faq/ (3.2 and 4.2.2)
- https://learn.microsoft.com/en-us/typography/opentype/spec/os2#fstype
- https://fonttools.readthedocs.io/en/latest/merge.html
- https://fonttools.readthedocs.io/en/latest/ttLib/scaleUpem.html

`build-tool.json` records the build-tool provenance review. It is a build-time
dependency only. The installed Python sources matched the official hash-pinned
wheel after LF/CRLF normalization; no new package was installed for this build.
