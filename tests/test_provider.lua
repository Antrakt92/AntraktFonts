-- Exercise the actual bundled libraries and provider, not a fake media registry.
local checks = 0
local function check(value, message)
    checks = checks + 1
    assert(value, message)
end

local function band(left, right)
    local result, place = 0, 1
    while left > 0 and right > 0 do
        if left % 2 == 1 and right % 2 == 1 then result = result + place end
        left, right, place = math.floor(left / 2), math.floor(right / 2), place * 2
    end
    return result
end

local function load(env, path)
    local chunk = assert(loadfile(path))
    setfenv(chunk, env)
    return chunk("AntraktFonts", {})
end

local function client(locale, missing, occupied, expectedCount)
    local env = setmetatable({}, { __index = _G })
    env._G = env
    env.getfenv = function() return env end
    env.strmatch = string.match
    env.GetLocale = function() return locale end
    env.bit = { band = band }
    env.securecallfunction = function(callback, ...) return callback(...) end
    env.C_UIFileAsset = { IsKnownFile = function() return not missing end }
    load(env, "libs/LibStub/LibStub.lua")
    load(env, "libs/CallbackHandler-1.0/CallbackHandler-1.0.lua")
    load(env, "libs/LibSharedMedia-3.0/LibSharedMedia-3.0.lua")
    load(env, "AntraktFonts_Catalog.lua")
    local media = env.LibStub("LibSharedMedia-3.0")
    local catalog = env.AntraktFonts.GetCatalog()
    if occupied then
        local all = media.LOCALE_BIT_western + media.LOCALE_BIT_ruRU
            + media.LOCALE_BIT_zhCN + media.LOCALE_BIT_zhTW + media.LOCALE_BIT_koKR
        for _, font in ipairs(catalog.fonts) do
            media:Register("font", font.name, "Interface\\AddOns\\OtherFonts\\" .. font.file, all)
        end
    end
    local registrations = 0
    local listener = {}
    media.RegisterCallback(listener, "LibSharedMedia_Registered", function(_, kind)
        if kind == "font" then registrations = registrations + 1 end
    end)
    local previousDefault, previousGlobal = media:GetDefault("font"), media:GetGlobal("font")
    load(env, "AntraktFonts.lua")
    local fields = { enUS = "latin", ruRU = "cyrillic", zhCN = "hans", zhTW = "hant", koKR = "hangul" }
    local paths = media:HashTable("font")
    for _, font in ipairs(catalog.fonts) do
        local expected
        if occupied then expected = "Interface\\AddOns\\OtherFonts\\" .. font.file
        elseif not missing and (font[fields[locale] or "latin"]
            or (font.latinLocales and font.latinLocales[locale])) then expected = font.path end
        check(paths[font.name] == expected, "actual LSM locale/existence/ownership: " .. locale .. "/" .. font.name)
    end
    check(media:GetDefault("font") == previousDefault, "provider does not change the media default")
    check(media:GetGlobal("font") == previousGlobal, "provider does not change global overrides")
    check(registrations == (not missing and not occupied and expectedCount or 0),
        "expected number of new registrations for " .. locale)
    if not occupied and not missing and locale == "zhTW" then
        for _, name in ipairs({ "Source Han Sans CN", "Source Han Sans TW", "Source Han Serif CN", "Source Han Serif TW" }) do
            check(paths[name] ~= nil, "standard LSM keeps both regional forms on zhTW: " .. name)
        end
    end
    check(#env.AntraktFonts.GetCatalog().fonts == 46, "metadata remains available without new registrations")
end

-- Both archive flavors ship this same runtime. Package tests check each TOC.
local locales = {
    { "enUS", 46 }, { "deDE", 41 }, { "esES", 41 }, { "esMX", 41 }, { "frFR", 41 },
    { "itIT", 40 }, { "ptBR", 40 }, { "ruRU", 35 }, { "zhCN", 4 }, { "zhTW", 4 }, { "koKR", 2 },
}
for _, locale in ipairs(locales) do
    client(locale[1], false, false, locale[2])
    client(locale[1], false, true, locale[2])
    client(locale[1], true, false, locale[2])
end

local withoutLibrary = setmetatable({}, { __index = _G })
withoutLibrary._G = withoutLibrary
load(withoutLibrary, "AntraktFonts_Catalog.lua")
load(withoutLibrary, "AntraktFonts.lua")
check(#withoutLibrary.AntraktFonts.GetCatalog().fonts == 46, "metadata API does not depend on media registration")
print("Actual shared-media provider: " .. checks .. " checks passed")
