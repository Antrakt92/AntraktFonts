# Antrakt Fonts

<img src="media/antrakt-fonts-icon.png" alt="Antrakt Fonts" width="96" height="96">

46 fonts for World of Warcraft addons, shared through LibSharedMedia.
Install the collection once per game client, then choose a font in your addon's
settings. Each addon keeps its own font, size and profile.

The fonts used to be bundled with StatsPro and Do You Need It? Keeping them in
one package makes regular addon downloads smaller and lets other addons use
the same collection.

**Release files are not available yet.**

## Installation

When files are available, download the build for your client: **Retail: Midnight**
or **WoW Forever beta**. Extract the `AntraktFonts` folder into
`Interface/AddOns` and keep it enabled in the game's AddOns list. A newly
installed addon may need a game restart to appear. GitHub source-code ZIPs are
not installable packages.

Upcoming CurseForge versions of StatsPro and Do You Need It? will list Antrakt
Fonts as a dependency, so the app can install the matching build for you. This
is not live yet. You can also install it manually. Both addons keep a readable
default font when the collection is missing.

Choose your font in the addon that uses it. Antrakt Fonts has no settings window
and does not change the game's fonts. It works without StatsPro or Do You Need
It? installed.

## Fonts

The collection includes DejaVu, Fira Sans, Hack, PT Sans, Source Han and more.
There are fonts for Latin, Cyrillic, Chinese, Japanese and Korean text, but
character support varies by font. Addons can use the included language metadata
to show suitable choices.

Both client builds use the same fonts and file paths, with different client
metadata. Font updates are separate from updates to the addons that use them.

## Questions or problems?

[Open an issue](https://github.com/Antrakt92/AntraktFonts/issues) if something
isn't working. If you'd like to use the collection in your own addon, see the
[connection examples](examples/README.md).

Thanks to [chenrylee](https://github.com/chenrylee) for the idea to move fonts
into a separate package ([StatsPro #10](https://github.com/Antrakt92/StatsPro/issues/10)).

Fonts and libraries keep their own licenses. See the
[credits and licenses](THIRD-PARTY-NOTICES.md) for details. The
[project license](LICENSE) covers the original code.

Development instructions are in [CONTRIBUTING.md](CONTRIBUTING.md); API details
are in [catalog/README.md](catalog/README.md).
