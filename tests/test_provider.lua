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

local function client(locale, missing, occupied)
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
        elseif not missing and font[fields[locale]] then expected = font.path end
        check(paths[font.name] == expected, "actual LSM locale/existence/ownership: " .. locale .. "/" .. font.name)
    end
    check(media:GetDefault("font") == previousDefault, "provider does not change the media default")
    check(media:GetGlobal("font") == previousGlobal, "provider does not change global overrides")
    if occupied or missing then check(registrations == 0, "no invented registration callback") end
    check(#env.AntraktFonts.GetCatalog().fonts == 46, "metadata remains available without new registrations")
end

for _, flavor in ipairs({ "retail", "forever" }) do
    for _, locale in ipairs({ "enUS", "ruRU", "zhCN", "zhTW", "koKR" }) do
        client(locale, false, false)
        client(locale, false, true)
        client(locale, true, false)
    end
    check(flavor ~= nil, "both client build scenarios run")
end

local withoutLibrary = setmetatable({}, { __index = _G })
withoutLibrary._G = withoutLibrary
load(withoutLibrary, "AntraktFonts_Catalog.lua")
load(withoutLibrary, "AntraktFonts.lua")
check(#withoutLibrary.AntraktFonts.GetCatalog().fonts == 46, "metadata API does not depend on media registration")
print("Actual shared-media provider: " .. checks .. " checks passed")
