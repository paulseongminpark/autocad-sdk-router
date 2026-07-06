// families/w6_layerstate_handlers.inc — W6-LAYERSTATE family: AcDbLayerStateManager
// ops (saved layer states / filters).
//
// Owned by the W6-LAYERSTATE lane (parallel CADOS wave 6, own worktree/branch).
// #included into AriadneNativeJob.cpp alongside the M08 family .inc files; sees
// every in-TU helper (njsonStr / jsonFind* / jsonFindStringArray / emitNativeError /
// AriadneJobCtx). Same disjoint-file contract as the M08 families: this lane owns
// ONLY this .inc + the minimal registration block in AriadneNativeJob.cpp (the
// #include line + the two `|| w6LayerStateHasOp/Dispatch(...)` chain entries) so
// parallel wave-6 lanes never touch a shared file.
//   - w6LayerStateHasOp(op): true for every op id this family implements.
//   - w6LayerStateDispatch(op, ctx, r): handle it (append "result":{...},
//     "status":"ok"}  or an emitNativeError-style error) and return true; else
//     return false.
//
// SAFETY (hard, same as every WRITE family in this TU): staged-write ONLY.
//   AcDbLayerStateManager(ctx.pDb) operates on the router-staged in-memory copy;
//   layer states live in a dictionary hung off the database's Named Object
//   Dictionary, so mutating them here mutates ctx.pDb like any other symbol-table
//   write in this TU. NEVER call save()/saveAs()/writeDwgFile/_QSAVE here — the
//   accoreconsole job driver (outside this module) persists the staged copy for
//   write_copy jobs, exactly like every sibling write op (write.layer.create,
//   write.entity.*, ...). No acedCommand/acedCmd/acedInvoke.
//
// Boolean args follow this file's existing "frozen"/"plottable"/"off" convention
// (write.layer.create's LayerPropertyArgs, ~line 6149): jsonFindNumber, NOT a JSON
// true/false token parse, so callers pass 1/0. String-array args (mask,
// restore_flags) reuse the shared jsonFindStringArray hand-rolled scanner.
//
// AcDbLayerStateManager (dblstate.h) is a core acdb26 class (no extra
// #pragma comment(lib) needed beyond this project's default ObjectARX linkage,
// same as every other symbol-table API in the sibling families).
#include "dblstate.h"   // AcDbLayerStateManager, LayerStateMask

//============================================================================
// W6 shared helpers (file-static; w6-prefixed so they never collide with a
// sibling family's .inc in the shared TU).
//============================================================================

static bool w6FindNameArg(const std::string& job, std::string& outName)
{
    return jsonFindString(job, "name", outName) && !outName.empty();
}

// mask[] token -> LayerStateMask bit. Unknown tokens are ignored (no fake bit).
static int w6LayerStateMaskBit(const std::string& tok)
{
    if (tok == "on") return AcDbLayerStateManager::kOn;
    if (tok == "frozen") return AcDbLayerStateManager::kFrozen;
    if (tok == "locked") return AcDbLayerStateManager::kLocked;
    if (tok == "plot") return AcDbLayerStateManager::kPlot;
    if (tok == "new_viewport") return AcDbLayerStateManager::kNewViewport;
    if (tok == "color") return AcDbLayerStateManager::kColor;
    if (tok == "linetype") return AcDbLayerStateManager::kLineType;
    if (tok == "lineweight") return AcDbLayerStateManager::kLineWeight;
    if (tok == "plotstyle") return AcDbLayerStateManager::kPlotStyle;
    if (tok == "current_viewport") return AcDbLayerStateManager::kCurrentViewport;
    if (tok == "transparency") return AcDbLayerStateManager::kTransparency;
    if (tok == "all") return AcDbLayerStateManager::kAll;
    return 0;
}

// Optional "mask":[...] job arg -> LayerStateMask. Absent/empty/all-unknown ->
// kAll (AutoCAD's own LAYERSTATE "Save" default: every property is captured).
static AcDbLayerStateManager::LayerStateMask w6ParseSaveMask(const std::string& job)
{
    const std::vector<std::string> tokens = jsonFindStringArray(job, "mask");
    int mask = 0;
    for (size_t i = 0; i < tokens.size(); ++i)
        mask |= w6LayerStateMaskBit(tokens[i]);
    if (mask == 0)
        mask = AcDbLayerStateManager::kAll;
    return static_cast<AcDbLayerStateManager::LayerStateMask>(mask);
}

// Optional "restore_flags":[...] job arg -> the restoreLayerState(nRestoreFlags)
// bitfield. Absent -> (present=false, 0 == kUndefDoNothing), the simple-overload
// default AutoCAD itself uses for a plain named-state restore.
static int w6ParseRestoreFlags(const std::string& job, bool& present)
{
    const std::vector<std::string> tokens = jsonFindStringArray(job, "restore_flags");
    present = !tokens.empty();
    int flags = 0;
    for (size_t i = 0; i < tokens.size(); ++i) {
        const std::string& t = tokens[i];
        if (t == "turn_off") flags |= AcDbLayerStateManager::kUndefTurnOff;
        else if (t == "freeze") flags |= AcDbLayerStateManager::kUndefFreeze;
        else if (t == "restore_as_overrides") flags |= AcDbLayerStateManager::kRestoreAsOverrides;
        // "do_nothing" carries no bit (kUndefDoNothing == 0).
    }
    return flags;
}

// LayerStateMask -> JSON string array, in a fixed field order (mirrors the
// enum declaration order in dblstate.h) so re-extraction is deterministic.
static std::string w6LayerStateMaskJson(int mask)
{
    static const struct { int bit; const char* name; } kBits[] = {
        { AcDbLayerStateManager::kOn, "on" },
        { AcDbLayerStateManager::kFrozen, "frozen" },
        { AcDbLayerStateManager::kLocked, "locked" },
        { AcDbLayerStateManager::kPlot, "plot" },
        { AcDbLayerStateManager::kNewViewport, "new_viewport" },
        { AcDbLayerStateManager::kColor, "color" },
        { AcDbLayerStateManager::kLineType, "linetype" },
        { AcDbLayerStateManager::kLineWeight, "lineweight" },
        { AcDbLayerStateManager::kPlotStyle, "plotstyle" },
        { AcDbLayerStateManager::kCurrentViewport, "current_viewport" },
        { AcDbLayerStateManager::kTransparency, "transparency" },
    };
    std::ostringstream a;
    a << "[";
    bool first = true;
    for (size_t i = 0; i < sizeof(kBits) / sizeof(kBits[0]); ++i) {
        if ((mask & kBits[i].bit) == 0)
            continue;
        if (!first) a << ",";
        first = false;
        a << njsonStr(std::string(kBits[i].name));
    }
    a << "]";
    return a.str();
}

static bool w6LayerStateHasOp(const std::string& op)
{
    return op == "inspect.layerstates.list"
        || op == "write.layerstate.save"
        || op == "write.layerstate.restore"
        || op == "write.layerstate.delete";
}

static bool w6LayerStateDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    const std::string& job = ctx.job;
    AcDbDatabase* pDb = ctx.pDb;

    //-----------------------------------------------------------------------
    // inspect.layerstates.list — every saved layer state (name, description,
    // layer count, masked properties). Optional include_hidden/include_xref
    // (0/1, default 1 each — matches getLayerStateNames' own defaults).
    //-----------------------------------------------------------------------
    if (op == "inspect.layerstates.list") {
        double flag = 1.0;
        const bool includeHidden = jsonFindNumber(job, "include_hidden", flag) ? (flag != 0.0) : true;
        flag = 1.0;
        const bool includeXref = jsonFindNumber(job, "include_xref", flag) ? (flag != 0.0) : true;

        AcDbLayerStateManager lsm(pDb);
        AcStringArray names;
        const Acad::ErrorStatus es = lsm.getLayerStateNames(names, includeHidden, includeXref);
        if (es != Acad::eOk) {
            emitNativeError(r, "LAYERSTATE_LIST_FAILED",
                            "AcDbLayerStateManager::getLayerStateNames failed (es="
                            + std::to_string(static_cast<int>(es)) + ")");
            return true;
        }

        std::ostringstream arr;
        arr << "[";
        for (int i = 0; i < names.length(); ++i) {
            const AcString nm = names[i];
            AcString desc;
            lsm.getLayerStateDescription(nm.kwszPtr(), desc);   // best-effort; "" on failure
            AcDbLayerStateManager::LayerStateMask mask = AcDbLayerStateManager::kNone;
            lsm.getLayerStateMask(nm.kwszPtr(), mask);
            AcStringArray layers;
            lsm.getLayerStateLayers(layers, nm.kwszPtr(), false);
            const bool hasVp = lsm.layerStateHasViewportData(nm.kwszPtr());
            const bool isDependent = lsm.isDependentLayerState(nm.kwszPtr());

            if (i != 0) arr << ",";
            arr << "{\"name\":" << njsonStr(nm.kwszPtr())
                << ",\"description\":" << njsonStr(desc.kwszPtr())
                << ",\"layer_count\":" << layers.length()
                << ",\"masked_properties\":" << w6LayerStateMaskJson(static_cast<int>(mask))
                << ",\"has_viewport_data\":" << (hasVp ? "true" : "false")
                << ",\"is_dependent\":" << (isDependent ? "true" : "false")
                << "}";
        }
        arr << "]";
        r << "\"result\":{\"layer_states\":" << arr.str() << ",\"count\":" << names.length() << "},"
          << "\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // write.layerstate.save — snapshot the CURRENT layer table into a named
    // state on the staged db. Required "name"; optional "description",
    // "mask":[...] (default all properties), "overwrite" (0/1, default 1 —
    // re-saving an existing name updates it, matching the LAYERSTATE command's
    // own "Save" dialog behavior).
    //-----------------------------------------------------------------------
    if (op == "write.layerstate.save") {
        std::string name;
        if (!w6FindNameArg(job, name)) {
            emitNativeError(r, "MISSING_ARG", "write.layerstate.save requires a 'name'");
            return true;
        }
        std::string description;
        const bool hasDescription = jsonFindString(job, "description", description);
        double flag = 1.0;
        const bool overwrite = jsonFindNumber(job, "overwrite", flag) ? (flag != 0.0) : true;
        const AcDbLayerStateManager::LayerStateMask mask = w6ParseSaveMask(job);

        AcDbLayerStateManager lsm(pDb);
        const std::wstring nameW = asciiToWide(name);
        const bool existedBefore = lsm.hasLayerState(nameW.c_str());
        if (existedBefore && !overwrite) {
            emitNativeError(r, "LAYERSTATE_EXISTS",
                            "layer state '" + name + "' already exists and overwrite=0");
            return true;
        }

        const Acad::ErrorStatus es = lsm.saveLayerState(nameW.c_str(), mask);
        if (es != Acad::eOk) {
            emitNativeError(r, "LAYERSTATE_SAVE_FAILED",
                            "AcDbLayerStateManager::saveLayerState('" + name + "') failed (es="
                            + std::to_string(static_cast<int>(es)) + ")");
            return true;
        }
        std::string descError;
        if (hasDescription) {
            const Acad::ErrorStatus descEs =
                lsm.setLayerStateDescription(nameW.c_str(), asciiToWide(description).c_str());
            if (descEs != Acad::eOk)
                descError = "setLayerStateDescription failed (es=" + std::to_string(static_cast<int>(descEs)) + ")";
        }
        AcStringArray layers;
        lsm.getLayerStateLayers(layers, nameW.c_str(), false);

        r << "\"result\":{\"saved\":true"
          << ",\"name\":" << njsonStr(name)
          << ",\"overwritten\":" << (existedBefore ? "true" : "false")
          << ",\"mask\":" << w6LayerStateMaskJson(static_cast<int>(mask))
          << ",\"layer_count\":" << layers.length();
        if (hasDescription)
            r << ",\"description\":" << njsonStr(description)
              << ",\"description_error\":" << (descError.empty() ? "null" : njsonStr(descError));
        r << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // write.layerstate.restore — apply a named layer state to the staged db.
    // Required "name". Optional "restore_flags":[turn_off|freeze|
    // restore_as_overrides] — absent uses the plain restoreLayerState(name)
    // overload (AcDbObjectId::kNull viewport, kUndefDoNothing semantics); the
    // simple overload is the only one exercised by this lane's live cert (no
    // viewport-scoped restore — kCurrentViewport/kNewViewport are non-goals
    // here, same as the mask decode's honesty about what was actually run).
    //-----------------------------------------------------------------------
    if (op == "write.layerstate.restore") {
        std::string name;
        if (!w6FindNameArg(job, name)) {
            emitNativeError(r, "MISSING_ARG", "write.layerstate.restore requires a 'name'");
            return true;
        }
        AcDbLayerStateManager lsm(pDb);
        const std::wstring nameW = asciiToWide(name);
        if (!lsm.hasLayerState(nameW.c_str())) {
            emitNativeError(r, "LAYERSTATE_NOT_FOUND", "no saved layer state named '" + name + "'");
            return true;
        }

        bool flagsPresent = false;
        const int flags = w6ParseRestoreFlags(job, flagsPresent);
        const Acad::ErrorStatus es = flagsPresent
            ? lsm.restoreLayerState(nameW.c_str(), AcDbObjectId::kNull, flags, nullptr)
            : lsm.restoreLayerState(nameW.c_str());
        if (es != Acad::eOk) {
            emitNativeError(r, "LAYERSTATE_RESTORE_FAILED",
                            "AcDbLayerStateManager::restoreLayerState('" + name + "') failed (es="
                            + std::to_string(static_cast<int>(es)) + ")");
            return true;
        }

        r << "\"result\":{\"restored\":true"
          << ",\"name\":" << njsonStr(name)
          << ",\"restore_flags_applied\":" << (flagsPresent ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    //-----------------------------------------------------------------------
    // write.layerstate.delete — remove a named layer state from the staged db.
    //-----------------------------------------------------------------------
    if (op == "write.layerstate.delete") {
        std::string name;
        if (!w6FindNameArg(job, name)) {
            emitNativeError(r, "MISSING_ARG", "write.layerstate.delete requires a 'name'");
            return true;
        }
        AcDbLayerStateManager lsm(pDb);
        const std::wstring nameW = asciiToWide(name);
        if (!lsm.hasLayerState(nameW.c_str())) {
            emitNativeError(r, "LAYERSTATE_NOT_FOUND", "no saved layer state named '" + name + "'");
            return true;
        }
        const Acad::ErrorStatus es = lsm.deleteLayerState(nameW.c_str());
        if (es != Acad::eOk) {
            emitNativeError(r, "LAYERSTATE_DELETE_FAILED",
                            "AcDbLayerStateManager::deleteLayerState('" + name + "') failed (es="
                            + std::to_string(static_cast<int>(es)) + ")");
            return true;
        }
        r << "\"result\":{\"deleted\":true,\"name\":" << njsonStr(name) << "},\"status\":\"ok\"}";
        return true;
    }

    return false;
}
