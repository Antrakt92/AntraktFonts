-- Load the documented independent example unchanged against actual bundled LSM.
local checks = 0
local function check(value,message) checks=checks+1;assert(value,message) end
local function clone(value)
    if type(value)~='table' then return value end
    local result={};for key,child in pairs(value) do result[key]=clone(child) end;return result
end
local function band(left,right)
    local result,place=0,1
    while left>0 and right>0 do
        if left%2==1 and right%2==1 then result=result+place end
        left,right,place=math.floor(left/2),math.floor(right/2),place*2
    end
    return result
end
local function load(env,path,name,namespace)
    local chunk=assert(loadfile(path));setfenv(chunk,env);return chunk(name or 'AntraktFonts',namespace or {})
end
local function fixture(locale,withLibrary)
    local env=setmetatable({},{__index=_G});env._G=env
    env.STANDARD_TEXT_FONT='Fonts\\FRIZQT__.TTF';env.GetLocale=function()return locale end
    env.getfenv=function()return env end;env.strmatch=string.match;env.bit={band=band}
    env.securecallfunction=function(callback,...)return callback(...)end
    env.C_UIFileAsset={IsKnownFile=function()return true end}
    local frames,timers={},{}
    env.C_Timer={After=function(_,callback)timers[#timers+1]=callback end}
    env.CreateFrame=function()
        local frame={};function frame:RegisterEvent(event)self.event=event end
        function frame:SetScript(event,callback)self[event]=callback end
        frames[#frames+1]=frame;return frame
    end
    function env.fire(name)for _,frame in ipairs(frames)do frame.OnEvent(frame,'ADDON_LOADED',name)end end
    function env.flush()local pending=timers;timers={};for _,callback in ipairs(pending)do callback()end end
    if withLibrary then
        load(env,'libs/LibStub/LibStub.lua');load(env,'libs/CallbackHandler-1.0/CallbackHandler-1.0.lua')
        load(env,'libs/LibSharedMedia-3.0/LibSharedMedia-3.0.lua')
    end
    local namespace={fallbackFont='Fonts\\FRIZQT__.TTF',outputLocale=locale,refreshes=0}
    namespace.OnFontsChanged=function()namespace.refreshes=namespace.refreshes+1 end
    function env.example()load(env,'examples/IndependentFonts.lua','IndependentFonts',namespace);return namespace.FontChoices end
    return env,namespace
end
for _,flavor in ipairs({'retail','forever'})do
    local tocPath=flavor=='retail' and 'examples/IndependentFonts.toc' or 'examples/IndependentFonts_Forever.toc'
    local file=assert(io.open(tocPath));local toc=file:read('*a');file:close()
    local providerToc=flavor=='retail' and 'AntraktFonts.toc' or 'AntraktFonts_Forever.toc'
    local source=assert(io.open(providerToc));local interface=assert(source:read('*a'):match('## Interface:%s*(%d+)'));source:close()
    check(toc:find('## Interface: '..interface,1,true) and toc:find('## OptionalDeps: AntraktFonts',1,true),'example TOC matches client and keeps provider optional')
    check(toc:find('IndependentFonts.lua',1,true) and not toc:find('SavedVariables',1,true) and not toc:find('## Dependencies:',1,true),'example TOC uses actual snippet without required dependency or persistence')
    local env,ns=fixture('enUS',false);local choices=env.example()
    check(choices.Resolve()==ns.fallbackFont,'absent library/provider retains independent fallback')
    check(#choices.ListCatalog()==0 and choices.revision==nil,'absent provider has no invented catalogue')
    check(choices.SelectCatalog('future-face'),'selection can retain a currently missing immutable ID')
    check(choices.Resolve()==ns.fallbackFont and choices.key=='future-face','missing provider never rewrites selection')
    check(env.StatsPro==nil and env.DoYouNeedIt==nil and env.StatsProDB==nil and env.DoYouNeedItDB==nil,'independent example has no core dependency or SavedVariables')
    check(env.FontChoices==nil,'consumer state belongs only to its own namespace')
    load(env,'AntraktFonts_Catalog.lua');load(env,'AntraktFonts.lua')
    env.fire('AntraktFonts');env.flush()
    local independent=env.AntraktFonts.GetCatalog().fonts[1]
    choices.SelectCatalog(independent.id)
    check(choices.Resolve()==independent.path,'catalogue route does not require LibSharedMedia')

    for _,occupied in ipairs({false,true})do
        local active,own=fixture('enUS',true)
        load(active,'AntraktFonts_Catalog.lua')
        local catalog=active.AntraktFonts.GetCatalog();active.AntraktFonts=nil
        local media=active.LibStub('LibSharedMedia-3.0')
        if occupied then
            local mask=media.LOCALE_BIT_western+media.LOCALE_BIT_ruRU+media.LOCALE_BIT_zhCN+media.LOCALE_BIT_zhTW+media.LOCALE_BIT_koKR
            for _,font in ipairs(catalog.fonts)do media:Register('font',font.name,'Interface\\AddOns\\OtherMedia\\'..font.file,mask)end
        end
        local oldDefault,oldGlobal=media:GetDefault('font'),media:GetGlobal('font')
        local api=active.example();api.SelectCatalog(catalog.fonts[1].id)
        check(api.Resolve()==own.fallbackFont,'late provider initially keeps own fallback')
        load(active,'AntraktFonts_Catalog.lua');load(active,'AntraktFonts.lua')
        local before=own.refreshes
        active.fire('AntraktFonts');active.flush()
        check(own.refreshes==before+1,'late provider event coalesces registration burst into one refresh')
        check(api.Resolve()==catalog.fonts[1].path,'canonical API resolves exact provider file despite occupied LSM names')
        check(#api.ListCatalog()>0,'independent picker receives live faces')
        api.SelectMedia(catalog.fonts[1].name)
        local expected=occupied and 'Interface\\AddOns\\OtherMedia\\'..catalog.fonts[1].file or catalog.fonts[1].path
        check(api.Resolve()==expected,'standard LSM route respects first owner rather than claiming same-name identity')
        api.SelectMedia('Missing external face');check(api.Resolve()==own.fallbackFont,'missing LSM name never silently uses another media default')
        local calls=0;local getter=active.AntraktFonts.GetCatalog
        active.AntraktFonts.GetCatalog=function()calls=calls+1;return getter()end
        api.SelectCatalog(catalog.fonts[1].id)
        for _=1,30 do api.Resolve()end
        check(calls==0,'resolve does not clone catalogues in a render path')
        local future=clone(catalog);future.catalogRevision=string.rep('a',64)
        local face=clone(future.fonts[1]);face.id='future-face';face.file='FutureFace.ttf';face.name='Future Face'
        face.path='Interface\\AddOns\\AntraktFonts\\fonts\\FutureFace.ttf';future.fonts[#future.fonts+1]=face
        active.AntraktFonts={GetCatalog=function()return clone(future)end}
        api.Refresh();api.SelectCatalog('future-face')
        check(api.revision==future.catalogRevision and api.Resolve()==face.path,'new compatible revision/ID requires no copied consumer snapshot')
        local rows=api.ListCatalog();rows[1].path='mutated local UI row'
        api.SelectCatalog(catalog.fonts[1].id);check(api.Resolve()==catalog.fonts[1].path,'UI list edits cannot mutate cached choice identity')
        active.AntraktFonts={GetCatalog=function()return {formatMajor=2}end};api.Refresh()
        check(api.Resolve()==own.fallbackFont and api.key==catalog.fonts[1].id,'incompatible major keeps selected ID and own fallback')
        check(media:GetDefault('font')==oldDefault and media:GetGlobal('font')==oldGlobal,'example never changes library defaults or global overrides')
        active.AntraktFonts=nil;api.Refresh();check(api.Resolve()==own.fallbackFont,'provider removal keeps consumer functional')
    end
    local ready,own=fixture('enUS',true)
    load(ready,'AntraktFonts_Catalog.lua');load(ready,'AntraktFonts.lua')
    local api=ready.example();local catalog=ready.AntraktFonts.GetCatalog()
    check(api.Resolve()==own.fallbackFont and api.kind==nil,'provider presence never automatically selects a font')
    api.SelectCatalog(catalog.fonts[1].id)
    check(api.Resolve()==catalog.fonts[1].path,'provider loaded first is read immediately')
    for _,locale in ipairs({'enUS','deDE','esES','esMX','frFR','itIT','ptBR','ruRU','koKR','zhCN','zhTW'})do
        check(api.SetLocale(locale,'Fonts\\FixtureFallback.ttf'),'explicit output locale accepts caller-owned readable fallback')
        local rows=api.ListCatalog();check(#rows>0,'supported output locale has compatible catalogue rows')
        for _,row in ipairs(rows)do
            check(row.provider=='AntraktFonts' and row.path:find('Interface\\AddOns\\AntraktFonts\\fonts\\',1,true)==1,'external identity is provider plus immutable ID')
            for _,font in ipairs(catalog.fonts)do
                if font.id==row.id then
                    local fields={enUS='latin',deDE='latin',esES='latin',esMX='latin',frFR='latin',itIT='latin',ptBR='latin',ruRU='cyrillic',koKR='hangul',zhCN='hans',zhTW='hant'}
                    check(font[fields[locale]] or (fields[locale]=='latin' and font.latinLocales and font.latinLocales[locale]),'locale picker honors declared exact coverage')
                    if font.region and (locale=='zhCN' or locale=='zhTW')then check(font.region==locale,'Chinese forms honor region metadata')end
                end
            end
        end
    end
    check(not api.SetLocale('unknown','Fonts\\Fallback.ttf'),'unknown output locale is rejected')
    check(not api.SelectCatalog('../foreign') and not api.SelectMedia(string.rep('x',129)),'example bounds its own selection fields')
end
local env,ns=fixture('enUS',true);local api=env.example()
local media=env.LibStub('LibSharedMedia-3.0')
media:Register('font','External without provider','Interface\\AddOns\\External\\Own.ttf',media.LOCALE_BIT_western)
api.SelectMedia('External without provider')
check(api.Resolve()=='Interface\\AddOns\\External\\Own.ttf','LSM route works independently of the provider API')
load(env,'AntraktFonts_Catalog.lua');local valid=env.AntraktFonts.GetCatalog()
api.SelectCatalog(valid.fonts[1].id)
for _,mutate in ipairs({
    function(value)value.formatMajor=2 end,
    function(value)value.catalogRevision='unbounded or unsupported revision' end,
    function(value)value.fonts={} end,
    function(value)value.fonts[2].id=value.fonts[1].id end,
    function(value)value.fonts[1].path='Interface\\AddOns\\Other\\Font.ttf' end,
    function(value)value.fonts[1].hangul='true' end,
    function(value)value.fonts[1].latinLocales={unknown=true} end,
    function(value)value.fonts[300]=clone(value.fonts[1]) end,
})do
    local damaged=clone(valid);mutate(damaged)
    env.AntraktFonts={GetCatalog=function()return damaged end};api.Refresh()
    check(api.Resolve()==ns.fallbackFont and api.key==valid.fonts[1].id,'malformed format-one metadata preserves preference and fallback')
end
env.AntraktFonts={GetCatalog=function()error('unavailable provider')end};api.Refresh()
check(api.Resolve()==ns.fallbackFont,'provider exceptions preserve own fallback')
local future=clone(valid);future.fonts={};future.catalogRevision=string.rep('b',64)
for index=1,256 do
    local font=clone(valid.fonts[1]);font.id='face-'..index;font.file='Face'..index..'.ttf';font.name='Face '..index
    font.path='Interface\\AddOns\\AntraktFonts\\fonts\\'..font.file;future.fonts[index]=font
end
env.AntraktFonts={GetCatalog=function()return clone(future)end};api.Refresh();api.SelectCatalog('face-256')
check(#api.ListCatalog()==256 and api.Resolve()==future.fonts[256].path,'valid format-one maximum works without a 46-face assumption')
future.fonts[257]=clone(future.fonts[256]);future.fonts[257].id='over-limit';api.Refresh()
check(api.Resolve()==ns.fallbackFont,'format-one count overflow rejects atomically')
local file=assert(io.open('examples/README.md'));local guide=file:read('*a');file:close()
check(guide:find('(IndependentFonts.lua)',1,true) and guide:find('(IndependentFonts.toc)',1,true),'quickstart links to the exact executed source and optional TOC')
print('Documented independent consumer: '..checks..' checks passed')
