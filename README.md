# Antrakt Fonts

<img src="media/antrakt-fonts-icon.png" alt="Antrakt Fonts" width="96" height="96">

An optional collection of 46 fonts for World of Warcraft addons that support
LibSharedMedia. Install it once per game client; supporting addons can share the
same files while keeping their own font choices, sizes and profiles.

**Development preview:** no public release is available yet. Installable files
will be linked after release validation is complete.

The collection includes Latin, Cyrillic, Chinese, Japanese and Korean faces.
Each font supports its own character set. Supporting addons can use the
included metadata to offer fonts suitable for their selected interface language.

## Installation

When a release is available, choose its packaged ZIP for your client:
**Retail: Midnight** or **Forever beta**. GitHub source-code ZIPs are not
installable addon packages.
Extract its single `AntraktFonts` folder into that client's `Interface/AddOns`
directory. Enable Antrakt Fonts in the AddOns list. Installing a new addon may
require restarting the game. Install only the matching build in each client.

Select a font in the settings of an addon that supports shared fonts. This
package has no separate settings window and does not change the game's fonts
or another addon's settings automatically. Antrakt Fonts does not require
StatsPro or DoYouNeedIt. Those addons can run without this optional collection.

The two client builds use the same font collection and canonical file paths.
Their client metadata differs. The collection updates independently of the
addons that use it; routine stat-data updates do not require new font files.

## Attribution and licenses

Thanks to [chenrylee](https://github.com/chenrylee) for suggesting a separate font
package in [StatsPro #10](https://github.com/Antrakt92/StatsPro/issues/10).

Each font and bundled library retains its own license. See
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md), `fonts/licenses/` and `LICENSES/`.
The project's custom license applies only to original material.

Developers: start with the [integration quickstart](examples/README.md), then see
[CONTRIBUTING.md](CONTRIBUTING.md) and the [shared font contract](catalog/README.md).
The optional integration utilities include localized guidance for 11 interface
locales: English, German, Spanish (Spain and Mexico), French, Italian, Korean,
Portuguese (Brazil), Russian, and Simplified and Traditional Chinese. Font
coverage still varies by face; localized guidance does not imply that every
font supports every language.
