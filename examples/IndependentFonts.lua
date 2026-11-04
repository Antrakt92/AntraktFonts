-- Independent addon example: no shared UI, snapshots, migration or SavedVariables.
local _, namespace = ...
local choices = {}
namespace.FontChoices = choices
local fallback = namespace.fallbackFont or STANDARD_TEXT_FONT
local locale = namespace.outputLocale or GetLocale()
local media, records, byID = nil, {}, {}
local refreshQueued = false
local fields = {enUS='latin',deDE='latin',esES='latin',esMX='latin',frFR='latin',itIT='latin',ptBR='latin',
    ruRU='cyrillic',koKR='hangul',zhCN='hans',zhTW='hant'}
local glyphs = {'latin','cyrillic','hans','hant','hangul','japanese'}
local function clean(value, kind)
    local ok, result = pcall(function()
        return type(value) == kind and (type(_G.issecretvalue) ~= 'function' or not _G.issecretvalue(value))
    end)
    return ok and result == true
end
local function text(value, limit)
    return clean(value,'string') and #value > 0 and #value <= limit and not value:find('[%c\127]')
end
assert(text(fallback,1024), 'Provide a tested fallbackFont for your own interface language')
local function plain(value) return clean(value,'table') and getmetatable(value) == nil end
local function supports(font)
    local field = fields[locale]
    if not field then return false end
    if font.region then
        if locale == 'zhCN' or locale == 'zhTW' then
            if font.region ~= locale then return false end
        elseif font.region == 'zhTW' then return false end
    end
    return font[field] == true or (field == 'latin' and font.latinLocales and font.latinLocales[locale] == true)
end
local function readCatalog()
    local provider = rawget(_G,'AntraktFonts')
    if not plain(provider) or type(provider.GetCatalog) ~= 'function' then return nil end
    local catalog = provider.GetCatalog()
    if not plain(catalog) or catalog.formatMajor ~= 1 or not text(catalog.catalogRevision,64)
        or #catalog.catalogRevision ~= 64 or not catalog.catalogRevision:match('^[a-f0-9]+$')
        or not plain(catalog.fonts) then return nil end
    local count = 0
    for key in pairs(catalog.fonts) do
        count = count + 1
        if count > 256 or not clean(key,'number') or key % 1 ~= 0 or key < 1 or key > 256 then return nil end
    end
    if count == 0 then return nil end
    local list, ids, files = {}, {}, {}
    for index = 1,count do
        local font = catalog.fonts[index]
        if not plain(font) or not text(font.id,64) or not font.id:match('^[a-z0-9][a-z0-9%-]*$')
            or ids[font.id] or not text(font.name,128) or not text(font.file,128)
            or not font.file:match('^[A-Za-z0-9_.%-]+%.[to]tf$') or files[font.file:lower()]
            or font.path ~= 'Interface\\AddOns\\AntraktFonts\\fonts\\' .. font.file
            or not text(font.sha256,64) or #font.sha256 ~= 64 or not font.sha256:match('^[a-f0-9]+$') then return nil end
        local copy = {id=font.id,name=font.name,path=font.path,region=font.region}
        for _,field in ipairs(glyphs) do
            if not clean(font[field],'boolean') then return nil end
            copy[field] = font[field]
        end
        if font.region ~= nil and font.region ~= 'zhCN' and font.region ~= 'zhTW' then return nil end
        if font.latinLocales ~= nil then
            if not plain(font.latinLocales) then return nil end
            copy.latinLocales = {}
            local total = 0
            for code,value in pairs(font.latinLocales) do
                total = total + 1
                if total > 7 or not clean(code,'string') or fields[code] ~= 'latin' or not clean(value,'boolean') or value ~= true then return nil end
                copy.latinLocales[code] = true
            end
        end
        ids[font.id], files[font.file:lower()] = copy, true
        list[#list+1] = copy
    end
    return list,ids,catalog.catalogRevision
end
function choices.Resolve()
    if choices.kind == 'catalog' then
        local font = byID[choices.key]
        return font and supports(font) and font.path or fallback
    end
    if choices.kind == 'media' and media then
        local ok,path = pcall(media.Fetch,media,'font',choices.key,true)
        if ok and text(path,1024) then return path end
    end
    return fallback
end
function choices.SelectMedia(name)
    if not text(name,128) then return false end
    choices.kind, choices.key = 'media',name
    return true
end
function choices.SelectCatalog(id)
    if not text(id,64) or not id:match('^[a-z0-9][a-z0-9%-]*$') then return false end
    choices.kind, choices.key = 'catalog',id
    return true
end
function choices.SetLocale(code, readableFallback)
    if not clean(code,'string') or not fields[code] or not text(readableFallback,1024) then return false end
    locale, fallback = code,readableFallback
    return true
end
function choices.ListCatalog()
    local result = {}
    for _,font in ipairs(records) do
        if supports(font) then result[#result+1] = {provider='AntraktFonts',id=font.id,name=font.name,path=font.path} end
    end
    return result
end
local function queueRefresh()
    if refreshQueued then return end
    refreshQueued = true
    C_Timer.After(0,function() refreshQueued = false; choices.Refresh() end)
end
function choices.Refresh()
    local ok,currentMedia = pcall(function() return LibStub and LibStub('LibSharedMedia-3.0',true) end)
    if ok and currentMedia and currentMedia ~= media then
        media = currentMedia
        if type(media.RegisterCallback) == 'function' then
            media.RegisterCallback(choices,'LibSharedMedia_Registered',function(_,kind)
                if kind == 'font' then queueRefresh() end
            end)
        end
    end
    local valid,list,ids,revision = pcall(readCatalog)
    records,byID,choices.revision = {},{},nil
    if valid and list then records,byID,choices.revision = list,ids,revision end
    if type(namespace.OnFontsChanged) == 'function' then namespace.OnFontsChanged() end
end
local events = CreateFrame('Frame')
events:RegisterEvent('ADDON_LOADED')
events:SetScript('OnEvent',function(_,_,name)
    if clean(name,'string') and name == 'AntraktFonts' then queueRefresh() end
end)
-- Startup and ADDON_LOADED cover fully occupied LSM names with zero new callbacks.
choices.Refresh()
