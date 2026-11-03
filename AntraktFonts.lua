-- Register shared media without replacing another addon's existing handle.
local provider = _G.AntraktFonts
local media = LibStub and LibStub("LibSharedMedia-3.0", true)
if not provider or type(provider.GetCatalog) ~= "function" or not media then return end

local catalog = provider.GetCatalog()
local locale = GetLocale()
for _, font in ipairs(catalog.fonts) do
    local mask = 0
    -- LSM groups Western clients, while partial faces have exact locale coverage.
    if font.latin or (font.latinLocales and font.latinLocales[locale]) then
        mask = mask + media.LOCALE_BIT_western
    end
    if font.cyrillic then mask = mask + media.LOCALE_BIT_ruRU end
    if font.hans then mask = mask + media.LOCALE_BIT_zhCN end
    if font.hant then mask = mask + media.LOCALE_BIT_zhTW end
    if font.hangul then mask = mask + media.LOCALE_BIT_koKR end
    media:Register(media.MediaType.FONT, font.name, font.path, mask)
end
