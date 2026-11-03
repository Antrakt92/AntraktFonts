local checks = 0
local function check(value, message)
    checks = checks + 1
    assert(value, message)
end

local function environment(existing)
    local env = setmetatable({ AntraktFontNoticeCoordinator = existing }, { __index = _G })
    env._G = env
    local function load()
        local namespace = {}
        local chunk = assert(loadfile("consumer/AntraktFontNotice.lua"))
        setfenv(chunk, env)
        local module = chunk("Consumer", namespace)
        check(namespace.AntraktFontNotice == module, "module attaches to private namespace")
        return module
    end
    return env, load
end

local function participant(state)
    local item = { state = state, ready = true, shows = 0, writes = 0, durable = true, visible = false }
    function item:callbacks()
        return {
            state = self.state,
            canShow = function() return self.ready end,
            show = function(confirm, suspend)
                self.shows = self.shows + 1
                self.confirm, self.suspend = confirm, suspend
                if self.showError then error("show failed") end
                self.visible = self.showResult ~= false
                return self.visible
            end,
            acknowledge = function()
                self.writes = self.writes + 1
                if self.writeError then error("write failed") end
                if self.durable then self.state = "acknowledged"; return true end
                return false
            end,
            dismiss = function()
                self.dismissals = (self.dismissals or 0) + 1
                if self.dismissError then error("dismiss failed") end
                self.visible = false
                if self.onDismiss then self.onDismiss() end
            end,
        }
    end
    return item
end

for _, order in ipairs({ { "StatsPro", "DoYouNeedIt" }, { "DoYouNeedIt", "StatsPro" } }) do
    local _, load = environment()
    local first, second = load(), load()
    local coordinator = first.GetCoordinator()
    check(second.GetCoordinator() == coordinator, "compatible consumers share coordinator")
    local entries = { StatsPro = participant(), DoYouNeedIt = participant() }
    for _, owner in ipairs(order) do check(coordinator:Register(owner, entries[owner]:callbacks()), "register") end
    check(entries.StatsPro.shows + entries.DoYouNeedIt.shows == 0, "registration does not show before lifecycle request")
    local shown, owner = coordinator:RequestShow()
    check(shown and owner == "DoYouNeedIt", "deterministic ready owner independent of load order")
    coordinator:RequestShow()
    check(entries.DoYouNeedIt.shows == 1 and entries.StatsPro.shows == 0, "one active presentation")
    check(entries.DoYouNeedIt.confirm(), "explicit acknowledgement accepted")
    check(entries.DoYouNeedIt.state == "acknowledged" and entries.StatsPro.state == "acknowledged", "each owner persists acknowledgement")
    check(not coordinator:RequestShow(), "acknowledgement suppresses later release requests")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local fresh, pending = participant("fresh"), participant()
    coordinator:Register("A", fresh:callbacks())
    coordinator:Register("B", pending:callbacks())
    check(coordinator:RequestShow(), "fresh does not suppress pending neighbour")
    check(fresh.shows == 0 and pending.shows == 1, "fresh never owns transition window")
    pending.confirm()
    check(fresh.writes == 0 and pending.writes == 1, "fresh does not receive acknowledgement write")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local pending, known, late = participant(), participant("acknowledged"), participant()
    coordinator:Register("A", pending:callbacks())
    coordinator:Register("B", known:callbacks())
    check(pending.state == "acknowledged" and pending.shows == 0, "persisted real acknowledgement seeds campaign")
    coordinator:Register("C", late:callbacks())
    check(late.state == "acknowledged", "late pending participant persists known acknowledgement")
    check(known.writes == 0 and not coordinator:RequestShow(), "already acknowledged owner is not rewritten")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local first, blocked = participant(), participant()
    blocked.durable = false
    coordinator:Register("A", first:callbacks())
    coordinator:Register("B", blocked:callbacks())
    coordinator:RequestShow(); first.confirm()
    check(first.state == "acknowledged" and blocked.state == nil, "partial failure does not invent durable acknowledgement")
    check(blocked.writes == 1, "one attempt per normal path")
    blocked.durable = true
    check(not coordinator:RequestShow(), "normal request retries save without another window")
    check(blocked.state == "acknowledged" and blocked.writes == 2, "failed save recovers")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local pending, known = participant(), participant("acknowledged")
    pending.writeError = true
    coordinator:Register("A", pending:callbacks())
    coordinator:Register("B", known:callbacks())
    check(pending.state == nil and pending.writes == 1, "save exception does not claim persistence")
    pending.writeError = false
    coordinator:Register("A", pending:callbacks())
    check(pending.state == "acknowledged" and pending.writes == 2, "later registration retries its own save")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local first, second = participant(), participant()
    first.showError = true
    coordinator:Register("A", first:callbacks()); coordinator:Register("B", second:callbacks())
    local shown, owner = coordinator:RequestShow()
    check(shown and owner == "B", "failed owner does not block another ready owner")
    check(first.writes == 0 and second.writes == 0, "show failure never acknowledges")
    check(not first.confirm(), "failed-show acknowledgement is stale")
    second.visible = false
    coordinator:RequestShow()
    check(second.writes == 0 and second.shows == 1, "host hiding alone never acknowledges or transfers ownership")
    check(second.suspend(), "owner releases presentation after hiding for combat")
    local stale = second.confirm
    first.ready, second.ready = false, false
    check(not coordinator:RequestShow(), "combat defers all unready participants")
    check(second.writes == 0, "suspension is not user acknowledgement")
    second.ready = true
    check(coordinator:RequestShow(), "event-driven retry resumes after combat")
    check(not stale(), "old presentation cannot acknowledge new one")
    check(not first.suspend(), "stale suspension cannot release current owner")
    check(second.confirm(), "current presentation can acknowledge")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local item = participant()
    local callbacks = item:callbacks()
    callbacks.canShow = function() error("readiness failed") end
    coordinator:Register("A", callbacks)
    check(not coordinator:RequestShow(), "readiness errors safely defer")
    callbacks.canShow = function() return 1 end
    coordinator:Register("A", callbacks)
    check(not coordinator:RequestShow(), "truthy nonboolean readiness does not authorize display")
    callbacks.canShow = function() return true end
    callbacks.show = function(confirm) confirm(); return false end
    coordinator:Register("A", callbacks)
    check(not coordinator:RequestShow() and item.writes == 0, "construction callback cannot acknowledge failed display")
    callbacks.show = function(confirm) confirm(); return 1 end
    coordinator:Register("A", callbacks)
    check(not coordinator:RequestShow() and item.writes == 0, "truthy nonboolean show result does not acknowledge")
    callbacks.show = function(confirm) confirm(); return true end
    coordinator:Register("A", callbacks)
    check(coordinator:RequestShow() and item.writes == 1, "synchronous explicit action waits for successful display")
end

do
    local alien = { formatMajor = 2, campaign = "shared-fonts-move-v1" }
    local env, load = environment(alien)
    local module = load()
    local coordinator = module.GetCoordinator()
    check(coordinator ~= alien and env.AntraktFontNoticeCoordinator == alien, "unknown protocol is isolated without global overwrite")
    check(module.GetCoordinator() == coordinator, "isolated coordinator persists for this consumer")
    local item = participant()
    coordinator:Register("A", item:callbacks())
    check(coordinator:RequestShow() and item.confirm(), "isolated notice still works")
    check(not coordinator:Register("", item:callbacks()), "invalid owner rejected")
    check(not coordinator:Register("B", { state = true }), "invalid callback registration rejected")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local visible, known = participant(), participant("acknowledged")
    coordinator:Register("A", visible:callbacks()); coordinator:RequestShow()
    local staleConfirm, staleSuspend = visible.confirm, visible.suspend
    visible.onDismiss = function()
        check(not staleConfirm(), "OnHide during programmatic dismissal cannot acknowledge")
        check(not staleSuspend(), "dismissal invalidates ownership before reentry")
        check(not coordinator:RequestShow(), "known acknowledgement prevents reentrant display")
    end
    coordinator:Register("B", known:callbacks())
    check(not visible.visible and visible.dismissals == 1, "late persisted acknowledgement dismisses active host window")
    check(not staleConfirm() and not coordinator:RequestShow(), "dismissed presentation stays stale without duplicate window")
    check(visible.writes == 1 and known.writes == 0, "only pending owner's persistence callback runs")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local item = participant()
    coordinator:Register("A", item:callbacks()); coordinator:RequestShow()
    local stale = item.confirm
    coordinator:Register("A", item:callbacks())
    check(not item.visible and item.dismissals == 1, "replacing an active registration dismisses its old window")
    check(not stale() and item.writes == 0, "replacement does not count as user acknowledgement")
    check(coordinator:RequestShow() and item.shows == 2, "normal request can show replacement registration")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local item = participant()
    item.dismissError = true
    coordinator:Register("A", item:callbacks()); coordinator:RequestShow()
    local oldConfirm, oldSuspend = item.confirm, item.suspend
    coordinator:Register("A", item:callbacks())
    check(not oldConfirm(), "failed replacement dismissal still invalidates acknowledgement")
    coordinator:RequestShow()
    check(item.shows == 1 and item.writes == 0, "failed dismissal leaves presentation busy without duplicate")
    item.visible = false
    check(oldSuspend(), "host can release its failed-close presentation after actually hiding it")
    check(coordinator:RequestShow() and item.shows == 2, "released busy presentation permits a normal replacement")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local visible, known = participant(), participant("acknowledged")
    visible.dismissError, visible.writeError = true, true
    coordinator:Register("A", visible:callbacks()); coordinator:RequestShow()
    local stale = visible.confirm
    check(coordinator:Register("B", known:callbacks()), "dismiss exception is contained")
    check(not stale() and visible.state == nil, "dismiss/save failure cannot fabricate persisted acknowledgement")
    local busy, owner = coordinator:RequestShow()
    check(busy and owner == "A" and visible.shows == 1, "failed-close window remains busy after known acknowledgement")
    visible.visible = false
    check(visible.suspend(), "host releases acknowledged busy window after actually hiding it")
    check(not coordinator:RequestShow(), "acknowledged campaign no longer busy after host suspension")
end

for _, mode in ipairs({ "throw", "false" }) do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local partial, nextOwner = participant(), participant()
    local callbacks = partial:callbacks()
    callbacks.show = function(confirm, suspend)
        partial.confirm, partial.suspend, partial.visible = confirm, suspend, true
        if mode == "throw" then error("partially constructed window") end
        return false
    end
    coordinator:Register("A", callbacks); coordinator:Register("B", nextOwner:callbacks())
    local shown, owner = coordinator:RequestShow()
    check(shown and owner == "B" and not partial.visible, "partial failed show is dismissed before another owner: " .. mode)
    check(partial.writes == 0 and not partial.confirm(), "partial failed show never acknowledges: " .. mode)
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local partial, nextOwner = participant(), participant()
    partial.dismissError = true
    local callbacks = partial:callbacks()
    callbacks.show = function(confirm, suspend)
        partial.confirm, partial.suspend, partial.visible = confirm, suspend, true
        error("partial window cannot be dismissed")
    end
    coordinator:Register("A", callbacks); coordinator:Register("B", nextOwner:callbacks())
    local shown, owner = coordinator:RequestShow()
    check(shown and owner == "A" and partial.visible and nextOwner.shows == 0, "failed show cleanup leaves ownership busy")
    check(not partial.confirm() and partial.writes == 0, "failed cleanup cannot acknowledge")
    partial.visible = false
    check(partial.suspend(), "host can release failed-show ownership after actual hide")
    callbacks.canShow = function() return false end
    coordinator:Register("A", callbacks)
    check(coordinator:RequestShow() and nextOwner.shows == 1, "actual cleanup permits another ready owner")
end

do
    local _, load = environment()
    local coordinator = load().GetCoordinator()
    local item, nextOwner = participant(), participant()
    local callbacks = item:callbacks()
    callbacks.dismiss = nil
    callbacks.show = function(confirm, suspend)
        item.confirm, item.suspend, item.visible = confirm, suspend, true
        return false
    end
    coordinator:Register("A", callbacks); coordinator:Register("B", nextOwner:callbacks())
    local busy, owner = coordinator:RequestShow()
    check(busy and owner == "A" and nextOwner.shows == 0, "missing cleanup fails closed rather than opening another owner")
    check(not item.confirm() and item.writes == 0, "missing cleanup cannot acknowledge failed display")
end

print("Notice coordinator: " .. checks .. " checks passed")
