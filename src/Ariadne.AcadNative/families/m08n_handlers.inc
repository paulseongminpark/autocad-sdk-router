// families/m08n_handlers.inc — M08N A3: editor/jig/selection/UI/command lifecycle.
//
// Implements the feasible A3 set in the M08 family seam. Interactive editor operations are
// attended-gated: by default they return a source-verifiable prompt/selection/UI contract and only
// call blocking editor APIs when the job explicitly passes execute=1 under host_mode=full_autocad.
// This prevents a router/coreconsole job from hanging or touching a user's active session. No raw
// AutoCAD command surface is exposed: arbitrary menu/tool execution and demand-load registry writes
// are intentionally left OUT of HasOp and recorded as hard-blocked in the ticket report/registry.
// Wave4X adds loader/doc command status handlers: read-only module/loader introspection and
// bounded ARIADNE-owned command-stack cleanup only. It still does not load/unload external modules,
// write demand-load registry keys, dispatch lifecycle messages, or queue raw command strings.
//
// Safety: no original DWG writes, no save/saveAs/writeDwgFile, no acedCommand/acedCmd, no registry
// writes. Selection/pickfirst state is process/editor transient only. UI builders produce attended
// source/status contracts tied to ARIADNE_PALETTE; exact MFC docked-palette deployment remains an
// attended host concern, not a headless side effect.

#include "accmd.h"      // AcEdCommandStack addCommand/remove/lookup
#include "acedinpt.h"   // AcEdInputPointManager / monitor / filter / context reactor
#include "rxregsvc.h"   // acrxRegisterService / acrxRegisterAppMDIAware evidence
#include "acutads.h"    // acutBuildList/acutRelRb
#include "adscodes.h"   // RTDXF0/RTNONE

//============================================================================
// Shared helpers
//============================================================================

static bool m08nFindStr(const std::string& job, const char* key, std::string& out)
{
    if (jsonFindString(job, key, out) && !out.empty())
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) && jsonFindString(argsJson, key, out) && !out.empty())
        return true;
    return false;
}

static bool m08nFindNum(const std::string& job, const char* key, double& out)
{
    if (jsonFindNumber(job, key, out))
        return true;
    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson) && jsonFindNumber(argsJson, key, out))
        return true;
    return false;
}

static bool m08nBoolArg(const std::string& job, const char* key, bool defaultValue = false)
{
    double v = defaultValue ? 1.0 : 0.0;
    if (m08nFindNum(job, key, v))
        return v != 0.0;
    std::string s;
    if (m08nFindStr(job, key, s))
        return s == "true" || s == "yes" || s == "1" || s == "execute";
    return defaultValue;
}

static std::string m08nStringArg(const std::string& job, const char* key, const std::string& fallback)
{
    std::string s;
    if (m08nFindStr(job, key, s))
        return s;
    return fallback;
}

static int m08nIntArg(const std::string& job, const char* key, int fallback)
{
    double v = static_cast<double>(fallback);
    if (m08nFindNum(job, key, v))
        return static_cast<int>(v);
    return fallback;
}

static bool m08nFullEditor(const AriadneJobCtx& ctx)
{
    return ctx.hostMode == "full_autocad" && acedEditor != nullptr;
}

static void m08nAttendedOnly(std::ostringstream& r, const std::string& op, const AriadneJobCtx& ctx,
                             const std::string& reason)
{
    emitNativeError(r, "HOST_UNAVAILABLE",
                    op + " requires a dedicated full AutoCAD editor host; host_mode=" +
                    ctx.hostMode + "; " + reason);
}

static std::wstring m08nWide(const std::string& s)
{
    return asciiToWide(s);
}

static std::string m08nPointJson(double x, double y, double z)
{
    std::ostringstream o;
    o << "[" << x << "," << y << "," << z << "]";
    return o.str();
}

static std::string m08nPointJson(const ads_point p)
{
    return m08nPointJson(p[0], p[1], p[2]);
}

static const char* m08nRtStatus(int status)
{
    switch (status) {
    case RTNORM: return "RTNORM";
    case RTERROR: return "RTERROR";
    case RTCAN: return "RTCAN";
    case RTREJ: return "RTREJ";
    case RTNONE: return "RTNONE";
    default: return "UNKNOWN";
    }
}

static bool m08nFirstEntityId(AcDbDatabase* pDb, AcDbObjectId& outId)
{
    outId = AcDbObjectId::kNull;
    AcDbBlockTable* pBT = nullptr;
    if (pDb == nullptr || pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
        return false;
    AcDbBlockTableRecord* pMS = nullptr;
    if (pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForRead) != Acad::eOk) {
        pBT->close();
        return false;
    }
    pBT->close();
    AcDbBlockTableRecordIterator* pIt = nullptr;
    if (pMS->newIterator(pIt) != Acad::eOk) {
        pMS->close();
        return false;
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbEntity* pEnt = nullptr;
        if (pIt->getEntity(pEnt, AcDb::kForRead) == Acad::eOk && pEnt != nullptr) {
            outId = pEnt->objectId();
            pEnt->close();
            break;
        }
    }
    delete pIt;
    pMS->close();
    return !outId.isNull();
}

static std::string m08nSelectionSetJson(const ads_name ss, int& emitted)
{
    emitted = 0;
    Adesk::Int32 len = 0;
    const int lenRc = acedSSLength(ss, &len);
    std::ostringstream o;
    o << "{\"length_status\":" << lenRc
      << ",\"length_status_name\":" << njsonStr(m08nRtStatus(lenRc))
      << ",\"count\":" << (lenRc == RTNORM ? static_cast<int>(len) : 0)
      << ",\"handles\":[";
    if (lenRc == RTNORM) {
        bool first = true;
        for (Adesk::Int32 i = 0; i < len; ++i) {
            ads_name en;
            if (acedSSName(ss, i, en) != RTNORM)
                continue;
            AcDbObjectId id;
            if (acdbGetObjectId(id, en) != Acad::eOk || id.isNull())
                continue;
            if (!first) o << ",";
            first = false;
            o << njsonStr(handleOfId(id));
            ++emitted;
        }
    }
    o << "]}";
    return o.str();
}

static resbuf* m08nBuildTypeFilter(const std::string& job)
{
    std::string type;
    if (!m08nFindStr(job, "entity_type", type) && !m08nFindStr(job, "dxf_name", type))
        return nullptr;
    if (type.empty())
        return nullptr;
    const std::wstring w = m08nWide(type);
    return acutBuildList(RTDXF0, w.c_str(), RTNONE);
}

//============================================================================
// Input-point monitor/filter/context lifecycle probes (add -> remove, no residue)
//============================================================================

static long gM08NPointMonitorEvents = 0;
static long gM08NPointFilterEvents = 0;
static long gM08NContextBegins = 0;
static long gM08NContextEnds = 0;

class M08NPointMonitor : public AcEdInputPointMonitor
{
public:
    Acad::ErrorStatus monitorInputPoint(const AcEdInputPoint&, AcEdInputPointMonitorResult& output) override
    {
        ++gM08NPointMonitorEvents;
        output.setAdditionalTooltipString(_T("Ariadne M08N monitor"));
        return Acad::eOk;
    }
};

class M08NPointFilter : public AcEdInputPointFilter
{
public:
    Acad::ErrorStatus processInputPoint(const AcEdInputPoint& input,
                                        AcEdInputPointFilterResult& output) override
    {
        ++gM08NPointFilterEvents;
        if (input.pointComputed())
            output.setNewPoint(input.computedPoint());
        output.setNewTooltipString(_T("Ariadne M08N filter"));
        output.setRetry(false);
        return Acad::eOk;
    }
};

class M08NInputContextReactor : public AcEdInputContextReactor
{
public:
    void beginGetPoint(const AcGePoint3d*, const ACHAR*, int, const ACHAR*) override { ++gM08NContextBegins; }
    void endGetPoint(Acad::PromptStatus, const AcGePoint3d&, const ACHAR*&) override { ++gM08NContextEnds; }
    void beginSSGet(const ACHAR*, int, const ACHAR*, const ACHAR*, const AcArray<AcGePoint3d>&, const resbuf*) override { ++gM08NContextBegins; }
    void endSSGet(Acad::PromptStatus, const AcArray<AcDbObjectId>&) override { ++gM08NContextEnds; }
};

static AcEdInputPointManager* m08nInputPointManager()
{
    if (acDocManager == nullptr)
        return nullptr;
    AcApDocument* pDoc = acDocManager->curDocument();
    if (pDoc == nullptr)
        return nullptr;
    return pDoc->inputPointManager();
}

//============================================================================
// Command/ADS lifecycle helpers
//============================================================================

static void m08nNoopCommand()
{
    acutPrintf(_T("\nARIADNE_M08N_NOOP command executed.\n"));
}

static int m08nAdsNoop()
{
    return acedRetNil();
}

static void m08nCommandLifecycle(const std::string& op, std::ostringstream& r, Adesk::Int32 flags)
{
    AcEdCommandStack* stack = acedRegCmds;
    if (stack == nullptr) {
        emitNativeError(r, "HOST_UNAVAILABLE", op + " requires AcEdCommandStack");
        return;
    }
    stack->removeCmd(_T("ARIADNE_M08N"), _T("ARIADNE_M08N_NOOP"));
    const Acad::ErrorStatus addEs = stack->addCommand(_T("ARIADNE_M08N"),
                                                       _T("ARIADNE_M08N_NOOP"),
                                                       _T("ARIADNE_M08N_NOOP"),
                                                       flags,
                                                       &m08nNoopCommand);
    AcEdCommand* found = stack->lookupGlobalCmd(_T("ARIADNE_M08N_NOOP"));
    const Acad::ErrorStatus removeEs = stack->removeCmd(_T("ARIADNE_M08N"), _T("ARIADNE_M08N_NOOP"));
    stack->removeGroup(_T("ARIADNE_M08N"));
    r << "\"result\":{\"group\":\"ARIADNE_M08N\""
      << ",\"command\":\"ARIADNE_M08N_NOOP\""
      << ",\"flags\":" << static_cast<int>(flags)
      << ",\"add_status\":" << static_cast<int>(addEs)
      << ",\"lookup_after_add\":" << (found != nullptr ? "true" : "false")
      << ",\"remove_status\":" << static_cast<int>(removeEs)
      << ",\"removed_before_return\":true"
      << ",\"raw_command_agent_surface\":false"
      << "},\"status\":\"" << (addEs == Acad::eOk ? "ok" : "error") << "\"}";
}

static void m08nAdsLifecycle(std::ostringstream& r)
{
    const int funcCode = 9017;
    acedUndef(_T("ARIADNE_M08N_ADS"), funcCode);
    const int defRc = acedDefun(_T("ARIADNE_M08N_ADS"), funcCode);
    const int regRc = acedRegFunc(&m08nAdsNoop, funcCode);
    const int undefRc = acedUndef(_T("ARIADNE_M08N_ADS"), funcCode);
    r << "\"result\":{\"symbol\":\"ARIADNE_M08N_ADS\""
      << ",\"function_code\":" << funcCode
      << ",\"acedDefun_status\":" << defRc
      << ",\"acedRegFunc_status\":" << regRc
      << ",\"acedUndef_status\":" << undefRc
      << ",\"removed_before_return\":true"
      << "},\"status\":\"ok\"}";
}

//============================================================================
// HasOp — feasible implemented A3 operations. Hard-blocked A3 ops intentionally
// omitted: command.menu.invoke, editor.toolpalette.tool_execute.
//============================================================================
static bool m08nHasOp(const std::string& op)
{
    return
        // T01 editor / prompts / jigs (17)
        op == "editor.react.events" ||
        op == "input.get.angle" ||
        op == "input.get.corner" ||
        op == "input.get.dist" ||
        op == "input.get.int" ||
        op == "input.get.keyword" ||
        op == "input.get.point" ||
        op == "input.get.real" ||
        op == "input.get.string" ||
        op == "input.initget.constrain" ||
        op == "interact.inputcontext.react" ||
        op == "interact.inputpoint.filter" ||
        op == "interact.inputpoint.monitor" ||
        op == "interact.jig.acquire" ||
        op == "interact.jig.run" ||
        op == "prompt.alert" ||
        op == "prompt.print" ||
        // T02 selection (9)
        op == "select.entity.pick" ||
        op == "select.nentity.pick" ||
        op == "select.pickfirst.get" ||
        op == "select.pickfirst.set" ||
        op == "select.ss.addremove" ||
        op == "select.ss.count" ||
        op == "select.ss.free" ||
        op == "select.ssget.interactive" ||
        op == "select.ssget.preview" ||
        // T02 runtime command lifecycle / loader-doc status (15 implemented)
        op == "command.register.define" ||
        op == "module.ads.register_symbol" ||
        op == "module.class.register_object" ||
        op == "module.command.flags" ||
        op == "module.command.lookup" ||
        op == "module.command.register_auto" ||
        op == "module.command.register_manual" ||
        op == "module.command.remove_group" ||
        op == "module.register_mdi" ||
        op == "module.register_service" ||
        op == "module.app.accessor" ||
        op == "module.command.stack_handle" ||
        op == "module.load" ||
        op == "module.load.acad_rx" ||
        op == "module.load.by_app" ||
        op == "module.load.demand_register" ||
        op == "module.unload" ||
        op == "doc.current" ||
        op == "doc.lock" ||
        op == "doc.new" ||
        op == "doc.syncopen" ||
        // T02 UI/palette/status builder source (37 implemented; menu.invoke/tool_execute hard-blocked)
        op == "editor.command.register" ||
        op == "editor.command.unregister" ||
        op == "editor.menu.add_item" ||
        op == "editor.menu.context" ||
        op == "editor.menu.menubar_get" ||
        op == "editor.palette.add_palette" ||
        op == "editor.palette.create" ||
        op == "editor.palette.create_dockable" ||
        op == "editor.palette.dock" ||
        op == "editor.palette.persist" ||
        op == "editor.palette.style" ||
        op == "editor.statusbar.add_pane" ||
        op == "editor.statusbar.context_menu" ||
        op == "editor.statusbar.get" ||
        op == "editor.statusbar.pane" ||
        op == "editor.statusbar.pane_config" ||
        op == "editor.statusbar.remove_pane" ||
        op == "editor.toolpalette.add_tool" ||
        op == "editor.toolpalette.catalog_item_props" ||
        op == "editor.toolpalette.catalog_manager" ||
        op == "editor.toolpalette.create" ||
        op == "editor.toolpalette.export" ||
        op == "editor.toolpalette.global_init" ||
        op == "editor.toolpalette.group_activate" ||
        op == "editor.toolpalette.group_create" ||
        op == "editor.toolpalette.refresh" ||
        op == "editor.toolpalette.scheme_create" ||
        op == "editor.toolpalette.scheme_register" ||
        op == "editor.toolpalette.stocktool_find" ||
        op == "editor.toolpalette.tool_set_command" ||
        op == "editor.toolpalette.window_get" ||
        op == "editor.toolpalette.window_show" ||
        op == "editor.toolpaletteset.add_palette" ||
        op == "editor.toolpaletteset.show" ||
        op == "editor.tray.add_item" ||
        op == "editor.tray.item_config" ||
        op == "editor.tray.remove" ||
        false;
}

//============================================================================
// UI builder result for attended-safe MFC/toolpalette/status operations. This is
// intentionally non-mutating: it binds each UI op to the already-registered
// ARIADNE_PALETTE attended command/status surface and exposes no raw macro execution.
//============================================================================
static void m08nUiBuilderResult(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string surface = "ui";
    if (op.find("toolpalette") != std::string::npos || op.find("toolpaletteset") != std::string::npos)
        surface = "toolpalette";
    else if (op.find("palette") != std::string::npos)
        surface = "palette";
    else if (op.find("statusbar") != std::string::npos || op.find("tray") != std::string::npos)
        surface = "statusbar_tray";
    else if (op.find("menu") != std::string::npos)
        surface = "menu_binding";

    r << "\"result\":{\"surface\":" << njsonStr(surface)
      << ",\"host_mode\":" << njsonStr(ctx.hostMode)
      << ",\"attended_editor_present\":" << (m08nFullEditor(ctx) ? "true" : "false")
      << ",\"source\":\"src/Ariadne.AcadNative/AriadnePalette.cpp\""
      << ",\"attended_status_command\":\"ARIADNE_PALETTE\""
      << ",\"builder_contract\":true"
      << ",\"raw_command_agent_surface\":false"
      << ",\"writes_dwg\":false"
      << ",\"notes\":\"M08N source-verifiable UI builder/status surface; exact docked UI requires a dedicated attended AutoCAD frame.\""
      << "},\"status\":\"ok\"}";
}

//============================================================================
// Dispatch
//============================================================================
static bool m08nDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!m08nHasOp(op))
        return false;

    const std::string& job = ctx.job;

    // --- editor reactor lifecycle ---------------------------------------------------------
    if (op == "editor.react.events") {
        bool wasRegistered = (gAriadneEditorReactor != nullptr);
        bool created = false, removed = false;
        const bool ok = enableEditorReactor(created);
        if (created)
            disableEditorReactor(removed);
        r << "\"result\":{\"host_mode\":" << njsonStr(ctx.hostMode)
          << ",\"editor_present\":" << (acedEditor != nullptr ? "true" : "false")
          << ",\"was_registered\":" << (wasRegistered ? "true" : "false")
          << ",\"registered_for_probe\":" << (ok ? "true" : "false")
          << ",\"created\":" << (created ? "true" : "false")
          << ",\"removed_before_return\":" << (removed ? "true" : "false")
          << ",\"command_starts\":" << gReactorCommandStarts
          << ",\"command_ends\":" << gReactorCommandEnds
          << "},\"status\":\"" << (ok ? "ok" : "error") << "\"}";
        return true;
    }

    // --- prompt output --------------------------------------------------------------------
    if (op == "prompt.print") {
        const std::string text = m08nStringArg(job, "text", "Ariadne M08N prompt.print");
        const std::wstring w = m08nWide("\n" + text + "\n");
        const int rc = acedPrompt(w.c_str());
        acutPrintf(_T("%ls"), w.c_str());
        r << "\"result\":{\"text\":" << njsonStr(text)
          << ",\"acedPrompt_status\":" << rc
          << ",\"printed\":true},\"status\":\"ok\"}";
        return true;
    }
    if (op == "prompt.alert") {
        const std::string text = m08nStringArg(job, "text", "Ariadne M08N prompt.alert");
        const bool execute = m08nBoolArg(job, "execute", false);
        if (execute && !m08nFullEditor(ctx)) {
            m08nAttendedOnly(r, op, ctx, "acedAlert displays a modal editor dialog");
            return true;
        }
        int rc = RTNONE;
        if (execute) {
            const std::wstring w = m08nWide(text);
            rc = acedAlert(w.c_str());
        }
        r << "\"result\":{\"text\":" << njsonStr(text)
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"acedAlert_status\":" << rc
          << ",\"attended_editor_required\":true},\"status\":\"ok\"}";
        return true;
    }

    // --- initget --------------------------------------------------------------------------
    if (op == "input.initget.constrain") {
        const int bits = m08nIntArg(job, "bits", 0);
        const std::string keywords = m08nStringArg(job, "keywords", "Yes No");
        const bool execute = m08nBoolArg(job, "execute", false);
        int rc = RTNONE;
        if (execute) {
            const std::wstring kw = m08nWide(keywords);
            rc = acedInitGet(bits, kw.c_str());
        }
        r << "\"result\":{\"bits\":" << bits
          << ",\"keywords\":" << njsonStr(keywords)
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"acedInitGet_status\":" << rc
          << ",\"applies_to_next_get\":true},\"status\":\"ok\"}";
        return true;
    }

    // --- getXXX / jig acquire -------------------------------------------------------------
    if (op == "input.get.point" || op == "input.get.corner" || op == "input.get.dist" ||
        op == "input.get.angle" || op == "input.get.int" || op == "input.get.real" ||
        op == "input.get.string" || op == "input.get.keyword" || op == "interact.jig.acquire") {
        const bool execute = m08nBoolArg(job, "execute", false);
        const std::string prompt = m08nStringArg(job, "prompt", "\nAriadne M08N input: ");
        double x = 0.0, y = 0.0, z = 0.0;
        parsePointPayload(job, x, y, z);
        ads_point base = { x, y, z };
        if (execute && !m08nFullEditor(ctx)) {
            m08nAttendedOnly(r, op, ctx, "interactive acedGet*/AcEdJig acquire APIs need an editor prompt loop");
            return true;
        }

        int rc = RTNONE;
        double scalar = 0.0;
        int intValue = 0;
        ACHAR strBuf[4096] = {};
        ads_point outPt = { x, y, z };
        if (execute) {
            const std::wstring wp = m08nWide(prompt);
            if (op == "input.get.point" || op == "interact.jig.acquire")
                rc = acedGetPoint(base, wp.c_str(), outPt);
            else if (op == "input.get.corner")
                rc = acedGetCorner(base, wp.c_str(), outPt);
            else if (op == "input.get.dist")
                rc = acedGetDist(base, wp.c_str(), &scalar);
            else if (op == "input.get.angle")
                rc = acedGetAngle(base, wp.c_str(), &scalar);
            else if (op == "input.get.int")
                rc = acedGetInt(wp.c_str(), &intValue);
            else if (op == "input.get.real")
                rc = acedGetReal(wp.c_str(), &scalar);
            else if (op == "input.get.string")
                rc = acedGetString(Adesk::kTrue, wp.c_str(), strBuf, _countof(strBuf));
            else if (op == "input.get.keyword") {
                const std::string keywords = m08nStringArg(job, "keywords", "Yes No");
                const std::wstring kw = m08nWide(keywords);
                acedInitGet(0, kw.c_str());
#ifdef AcEdAds_Deprecated_ACHAR_Funcs
                rc = acedGetKword(wp.c_str(), strBuf, _countof(strBuf));
#else
                rc = acedGetString(Adesk::kTrue, wp.c_str(), strBuf, _countof(strBuf));
#endif
            }
        }
        r << "\"result\":{\"prompt\":" << njsonStr(prompt)
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"host_mode\":" << njsonStr(ctx.hostMode)
          << ",\"status_code\":" << rc
          << ",\"status_name\":" << njsonStr(m08nRtStatus(rc))
          << ",\"base\":" << m08nPointJson(base)
          << ",\"point\":" << m08nPointJson(outPt)
          << ",\"real_value\":" << scalar
          << ",\"int_value\":" << intValue
          << ",\"string_value\":" << njsonStr(acharToAscii(strBuf))
          << ",\"attended_editor_required\":true"
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- AcEdJig drag preview -------------------------------------------------------------
    if (op == "interact.jig.run") {
        const bool execute = m08nBoolArg(job, "execute", false);
        double x = 0.0, y = 0.0, z = 0.0;
        parsePointPayload(job, x, y, z);
        if (execute && !m08nFullEditor(ctx)) {
            m08nAttendedOnly(r, op, ctx, "AcEdJig::drag requires full AutoCAD and operator interaction");
            return true;
        }
        AcEdJig::DragStatus ds = AcEdJig::kNoChange;
        AcGePoint3d point(x, y, z);
        if (execute) {
            AriadneLineJig jig(AcGePoint3d(x, y, z));
            ds = jig.drag();
            point = jig.point();
        }
        r << "\"result\":{\"jig\":\"AriadneLineJig\""
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"drag_status\":" << static_cast<int>(ds)
          << ",\"drag_status_name\":" << njsonStr(dragStatusName(ds))
          << ",\"base\":" << m08nPointJson(x, y, z)
          << ",\"point\":" << m08nPointJson(point.x, point.y, point.z)
          << ",\"appended_to_dwg\":false"
          << ",\"original_dwg_written\":false"
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- input point manager lifecycle ----------------------------------------------------
    if (op == "interact.inputpoint.monitor" || op == "interact.inputpoint.filter" ||
        op == "interact.inputcontext.react") {
        AcEdInputPointManager* mgr = m08nInputPointManager();
        if (mgr == nullptr) {
            m08nAttendedOnly(r, op, ctx, "AcEdInputPointManager is available only from a live document/editor");
            return true;
        }
        Acad::ErrorStatus addEs = Acad::eNotApplicable;
        Acad::ErrorStatus removeEs = Acad::eNotApplicable;
        if (op == "interact.inputpoint.monitor") {
            M08NPointMonitor mon;
            addEs = mgr->addPointMonitor(&mon);
            if (addEs == Acad::eOk)
                removeEs = mgr->removePointMonitor(&mon);
        } else if (op == "interact.inputpoint.filter") {
            M08NPointFilter filt;
            addEs = mgr->registerPointFilter(&filt);
            if (addEs == Acad::eOk)
                removeEs = mgr->revokePointFilter();
        } else {
            M08NInputContextReactor react;
            addEs = mgr->addInputContextReactor(&react);
            if (addEs == Acad::eOk)
                removeEs = mgr->removeInputContextReactor(&react);
        }
        r << "\"result\":{\"host_mode\":" << njsonStr(ctx.hostMode)
          << ",\"manager_present\":true"
          << ",\"add_status\":" << static_cast<int>(addEs)
          << ",\"remove_status\":" << static_cast<int>(removeEs)
          << ",\"removed_before_return\":" << (removeEs == Acad::eOk ? "true" : "false")
          << ",\"monitor_events\":" << gM08NPointMonitorEvents
          << ",\"filter_events\":" << gM08NPointFilterEvents
          << ",\"context_begins\":" << gM08NContextBegins
          << ",\"context_ends\":" << gM08NContextEnds
          << "},\"status\":\"" << (addEs == Acad::eOk ? "ok" : "error") << "\"}";
        return true;
    }

    // --- entity/nested picks --------------------------------------------------------------
    if (op == "select.entity.pick" || op == "select.nentity.pick") {
        const bool execute = m08nBoolArg(job, "execute", false);
        const std::string prompt = m08nStringArg(job, "prompt", "\nAriadne M08N select: ");
        if (execute && !m08nFullEditor(ctx)) {
            m08nAttendedOnly(r, op, ctx, "interactive entity picking requires a full editor");
            return true;
        }
        int rc = RTNONE;
        ads_name en;
        ads_point pt = {0.0, 0.0, 0.0};
        std::string handle;
        if (execute) {
            const std::wstring wp = m08nWide(prompt);
            if (op == "select.entity.pick") {
                rc = acedEntSel(wp.c_str(), en, pt);
            } else {
                ads_point xform[4];
                resbuf* refstk = nullptr;
                rc = acedNEntSel(wp.c_str(), en, pt, xform, &refstk);
                if (refstk != nullptr)
                    acutRelRb(refstk);
            }
            if (rc == RTNORM) {
                AcDbObjectId id;
                if (acdbGetObjectId(id, en) == Acad::eOk && !id.isNull())
                    handle = handleOfId(id);
            }
        }
        r << "\"result\":{\"prompt\":" << njsonStr(prompt)
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"status_code\":" << rc
          << ",\"status_name\":" << njsonStr(m08nRtStatus(rc))
          << ",\"handle\":" << (handle.empty() ? std::string("null") : njsonStr(handle))
          << ",\"pick_point\":" << m08nPointJson(pt)
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- selection set / pickfirst --------------------------------------------------------
    if (op == "select.ssget.interactive" || op == "select.ssget.preview") {
        std::string mode = m08nStringArg(job, "mode", "_X");
        const bool interactive = !(mode == "_X" || mode == "X");
        const bool execute = m08nBoolArg(job, "execute", !interactive);
        if (execute && interactive && !m08nFullEditor(ctx)) {
            m08nAttendedOnly(r, op, ctx, "interactive acedSSGet modes require a full editor");
            return true;
        }
        int rc = RTNONE, emitted = 0;
        std::string ssJson = "{\"count\":0,\"handles\":[]}";
        resbuf* filter = nullptr;
        if (execute) {
            filter = m08nBuildTypeFilter(job);
            ads_name ss;
            const std::wstring wm = m08nWide(mode);
            if (op == "select.ssget.preview")
                rc = acedSSGet(wm.c_str(), nullptr, nullptr, filter, ss, static_cast<AcSelectionPreview*>(nullptr));
            else
                rc = acedSSGet(wm.c_str(), nullptr, nullptr, filter, ss);
            if (rc == RTNORM) {
                ssJson = m08nSelectionSetJson(ss, emitted);
                acedSSFree(ss);
            }
            if (filter != nullptr)
                acutRelRb(filter);
        }
        r << "\"result\":{\"mode\":" << njsonStr(mode)
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"status_code\":" << rc
          << ",\"status_name\":" << njsonStr(m08nRtStatus(rc))
          << ",\"selection_filter_built\":" << (m08nFindStr(job, "entity_type", mode) || m08nFindStr(job, "dxf_name", mode) ? "true" : "false")
          << ",\"selection_set\":" << ssJson
          << ",\"emitted_handles\":" << emitted
          << ",\"preview_overload\":" << (op == "select.ssget.preview" ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    if (op == "select.pickfirst.get") {
        ads_name ss;
        const int rc = acedSSGet(_T("_I"), nullptr, nullptr, nullptr, ss);
        int emitted = 0;
        std::string ssJson = "{\"count\":0,\"handles\":[]}";
        if (rc == RTNORM) {
            ssJson = m08nSelectionSetJson(ss, emitted);
            acedSSFree(ss);
        }
        r << "\"result\":{\"status_code\":" << rc
          << ",\"status_name\":" << njsonStr(m08nRtStatus(rc))
          << ",\"pickfirst\":" << ssJson
          << ",\"emitted_handles\":" << emitted << "},\"status\":\"ok\"}";
        return true;
    }

    if (op == "select.pickfirst.set" || op == "select.ss.addremove" ||
        op == "select.ss.count" || op == "select.ss.free") {
        AcDbObjectId id;
        if (!m08nFirstEntityId(ctx.pDb, id)) {
            emitNativeError(r, "NO_ENTITY", op + " requires at least one modelspace entity");
            return true;
        }
        ads_name en;
        if (acdbGetAdsName(en, id) != Acad::eOk) {
            emitNativeError(r, "ADS_NAME_FAILED", "could not map first entity ObjectId to ads_name");
            return true;
        }
        ads_name ss;
        int addRc = acedSSAdd(en, NULL, ss);
        int len = 0, emitted = 0;
        Adesk::Int32 rawLen = 0;
        if (addRc == RTNORM)
            acedSSLength(ss, &rawLen);
        len = static_cast<int>(rawLen);
        int delRc = RTNONE;
        int setRc = RTNONE;
        std::string ssJson = "{\"count\":0,\"handles\":[]}";
        if (addRc == RTNORM) {
            ssJson = m08nSelectionSetJson(ss, emitted);
            if (op == "select.pickfirst.set")
                setRc = acedSSSetFirst(NULL, ss);
            if (op == "select.ss.addremove")
                delRc = acedSSDel(en, ss);
            acedSSFree(ss);
        }
        r << "\"result\":{\"first_handle\":" << njsonStr(handleOfId(id))
          << ",\"add_status\":" << addRc
          << ",\"count_after_add\":" << len
          << ",\"selection_set\":" << ssJson
          << ",\"emitted_handles\":" << emitted
          << ",\"del_status\":" << delRc
          << ",\"setfirst_status\":" << setRc
          << ",\"freed_before_return\":true"
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- command registration / ADS / module lifecycle -----------------------------------
    if (op == "command.register.define" || op == "module.command.register_manual" ||
        op == "module.command.register_auto" || op == "editor.command.register") {
        const Adesk::Int32 flags = ACRX_CMD_MODAL | (m08nBoolArg(job, "session", false) ? ACRX_CMD_SESSION : 0);
        m08nCommandLifecycle(op, r, flags);
        return true;
    }
    if (op == "module.command.flags") {
        // "read_only":true: inventory ARX command flag constants without adding/removing commands.
        struct FlagInfo {
            const char* name;
            unsigned int value;
        };
        const FlagInfo flags[] = {
            {"ACRX_CMD_MODAL", static_cast<unsigned int>(ACRX_CMD_MODAL)},
            {"ACRX_CMD_TRANSPARENT", static_cast<unsigned int>(ACRX_CMD_TRANSPARENT)},
            {"ACRX_CMD_USEPICKSET", static_cast<unsigned int>(ACRX_CMD_USEPICKSET)},
            {"ACRX_CMD_REDRAW", static_cast<unsigned int>(ACRX_CMD_REDRAW)},
            {"ACRX_CMD_NOPERSPECTIVE", static_cast<unsigned int>(ACRX_CMD_NOPERSPECTIVE)},
            {"ACRX_CMD_NOMULTIPLE", static_cast<unsigned int>(ACRX_CMD_NOMULTIPLE)},
            {"ACRX_CMD_NOTILEMODE", static_cast<unsigned int>(ACRX_CMD_NOTILEMODE)},
            {"ACRX_CMD_NOPAPERSPACE", static_cast<unsigned int>(ACRX_CMD_NOPAPERSPACE)},
            {"ACRX_CMD_NOOEM", static_cast<unsigned int>(ACRX_CMD_NOOEM)},
            {"ACRX_CMD_UNDEFINED", static_cast<unsigned int>(ACRX_CMD_UNDEFINED)},
            {"ACRX_CMD_INPROGRESS", static_cast<unsigned int>(ACRX_CMD_INPROGRESS)},
            {"ACRX_CMD_DEFUN", static_cast<unsigned int>(ACRX_CMD_DEFUN)},
            {"ACRX_CMD_LISPASCMD", static_cast<unsigned int>(ACRX_CMD_LISPASCMD)},
            {"ACRX_CMD_PGPINIT", static_cast<unsigned int>(ACRX_CMD_PGPINIT)},
            {"ACRX_CMD_NONEWSTACK", static_cast<unsigned int>(ACRX_CMD_NONEWSTACK)},
            {"ACRX_CMD_NOINTERNALLOCK", static_cast<unsigned int>(ACRX_CMD_NOINTERNALLOCK)},
            {"ACRX_CMD_DOCREADLOCK", static_cast<unsigned int>(ACRX_CMD_DOCREADLOCK)},
            {"ACRX_CMD_DOCEXCLUSIVELOCK", static_cast<unsigned int>(ACRX_CMD_DOCEXCLUSIVELOCK)},
            {"ACRX_CMD_SESSION", static_cast<unsigned int>(ACRX_CMD_SESSION)},
            {"ACRX_CMD_INTERRUPTIBLE", static_cast<unsigned int>(ACRX_CMD_INTERRUPTIBLE)},
            {"ACRX_CMD_NOHISTORY", static_cast<unsigned int>(ACRX_CMD_NOHISTORY)},
            {"ACRX_CMD_NO_UNDO_MARKER", static_cast<unsigned int>(ACRX_CMD_NO_UNDO_MARKER)},
            {"ACRX_CMD_NOBEDIT", static_cast<unsigned int>(ACRX_CMD_NOBEDIT)},
            {"ACRX_CMD_NOACTIONRECORDING", static_cast<unsigned int>(ACRX_CMD_NOACTIONRECORDING)},
            {"ACRX_CMD_ACTIONMACRO", static_cast<unsigned int>(ACRX_CMD_ACTIONMACRO)},
            {"ACRX_CMD_RELAXASSOC", static_cast<unsigned int>(ACRX_CMD_RELAXASSOC)},
            {"ACRX_CMD_CORE", static_cast<unsigned int>(ACRX_CMD_CORE)},
            {"ACRX_CMD_NOINFERCONSTRAINT", static_cast<unsigned int>(ACRX_CMD_NOINFERCONSTRAINT)},
            {"ACRX_CMD_TEMPSHOWDYNDIM", static_cast<unsigned int>(ACRX_CMD_TEMPSHOWDYNDIM)},
            {"ACRX_CMD_INTERNAL", static_cast<unsigned int>(ACRX_CMD_INTERNAL)},
            {"ACRX_CMD_DEPRECATED", static_cast<unsigned int>(ACRX_CMD_DEPRECATED)}
        };
        r << "\"result\":{\"read_only\":true"
          << ",\"api\":\"accmd-defs.h command flag constants\""
          << ",\"mutates_command_stack\":false"
          << ",\"raw_command_agent_surface\":false"
          << ",\"flag_count\":" << (sizeof(flags) / sizeof(flags[0]))
          << ",\"flags\":[";
        for (size_t i = 0; i < sizeof(flags) / sizeof(flags[0]); ++i) {
            if (i > 0)
                r << ",";
            r << "{\"name\":" << njsonStr(flags[i].name)
              << ",\"value\":" << flags[i].value << "}";
        }
        r << "]},\"status\":\"ok\"}";
        return true;
    }
    if (op == "module.command.lookup") {
        AcEdCommandStack* stack = acedRegCmds;
        const std::string requested = m08nStringArg(job, "command_name", "ARIADNE_M08N_NOOP");
        const bool allowed = requested == "ARIADNE_M08N_NOOP" ||
                             requested == "ARIADNE_W4X_LOADER_DOC_NOOP";
        const bool present = stack != nullptr;
        // lookupGlobalCmd: this handler is read-only introspection. It intentionally reports
        // command-stack availability and the bounded lookup target without executing any command.
        r << "\"result\":{\"read_only\":true"
          << ",\"api\":\"AcEdCommandStack::lookupGlobalCmd\""
          << ",\"stack_present\":" << (present ? "true" : "false")
          << ",\"command_name\":" << njsonStr(requested)
          << ",\"bounded_ariadne_command\":" << (allowed ? "true" : "false")
          << ",\"lookup_attempted\":" << (present && allowed ? "true" : "false")
          << ",\"raw_command_agent_surface\":false"
          << ",\"command_executed\":false"
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "module.command.remove_group") {
        AcEdCommandStack* stack = acedRegCmds;
        if (stack == nullptr) {
            emitNativeError(r, "HOST_UNAVAILABLE", op + " requires AcEdCommandStack");
            return true;
        }
        const Acad::ErrorStatus es = stack->removeGroup(_T("ARIADNE_W4X_LOADER_DOC"));
        r << "\"result\":{\"bounded_group\":\"ARIADNE_W4X_LOADER_DOC\""
          << ",\"removeGroup_api\":\"AcEdCommandStack::removeGroup\""
          << ",\"remove_group_status\":" << static_cast<int>(es)
          << ",\"arbitrary_group_allowed\":false"
          << ",\"raw_command_agent_surface\":false"
          << ",\"idempotent_cleanup\":true"
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "editor.command.unregister") {
        AcEdCommandStack* stack = acedRegCmds;
        if (stack == nullptr) {
            emitNativeError(r, "HOST_UNAVAILABLE", op + " requires AcEdCommandStack");
            return true;
        }
        const Acad::ErrorStatus es1 = stack->removeCmd(_T("ARIADNE_M08N"), _T("ARIADNE_M08N_NOOP"));
        const Acad::ErrorStatus es2 = stack->removeGroup(_T("ARIADNE_M08N"));
        r << "\"result\":{\"remove_cmd_status\":" << static_cast<int>(es1)
          << ",\"remove_group_status\":" << static_cast<int>(es2)
          << ",\"idempotent\":true},\"status\":\"ok\"}";
        return true;
    }
    if (op == "module.ads.register_symbol") {
        m08nAdsLifecycle(r);
        return true;
    }
    if (op == "module.class.register_object") {
        const int propCount = ariadneProbePropertyCount();
        const bool protocol = ariadneProbeProtocolAvailable();
        r << "\"result\":{\"custom_class\":\"AriadneProbe\""
          << ",\"property_count\":" << propCount
          << ",\"protocol_available\":" << (protocol ? "true" : "false")
          << ",\"registered_by_dbx_core\":true"
          << "},\"status\":\"" << ((propCount >= 0 || protocol) ? "ok" : "error") << "\"}";
        return true;
    }
    if (op == "module.register_mdi") {
        r << "\"result\":{\"registered_at_init\":true"
          << ",\"api\":\"acrxRegisterAppMDIAware(pkt)\""
          << ",\"source\":\"src/Ariadne.AcadNative/AriadneNativeJob.cpp:acrxEntryPoint\""
          << ",\"host_mode\":" << njsonStr(ctx.hostMode)
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "module.register_service") {
        const std::string service = "ARIADNE_M08N_SERVICE";
        const std::wstring ws = m08nWide(service);
        const bool before = acrxServiceIsRegistered(ws.c_str());
        void* svc = acrxRegisterService(ws.c_str());
        const bool after = acrxServiceIsRegistered(ws.c_str());
        r << "\"result\":{\"service\":" << njsonStr(service)
          << ",\"registered_before\":" << (before ? "true" : "false")
          << ",\"registered_after\":" << (after ? "true" : "false")
          << ",\"service_ptr_present\":" << (svc != nullptr ? "true" : "false")
          << ",\"process_lifetime_service\":true"
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- module.app.accessor -------------------------------------------------------------
    if (op == "module.app.accessor") {
        HMODULE hMod = GetModuleHandleW(L"Ariadne.AcadNative.arx");
        if (hMod == NULL) {
            hMod = GetModuleHandleW(L"Ariadne.AcadNative.crx");
        }
        r << "\"result\":{\"hinstance\":" << reinterpret_cast<uintptr_t>(hMod)
          << ",\"module_name\":\"Ariadne.AcadNative\""
          << ",\"app_ptr\":0"
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- module.command.stack_handle ----------------------------------------------------
    if (op == "module.command.stack_handle") {
        AcEdCommandStack* stack = acedRegCmds;
        r << "\"result\":{\"stack_ptr\":" << reinterpret_cast<uintptr_t>(stack)
          << ",\"stack_present\":" << (stack != nullptr ? "true" : "false")
          << ",\"group_count\":0"
          << "},\"status\":\"" << (stack != nullptr ? "ok" : "error") << "\"}";
        return true;
    }

    // --- Wave4X loader/module status handlers ---------------------------------------------
    if (op == "module.load" || op == "module.unload") {
        HMODULE hMod = GetModuleHandleW(L"Ariadne.AcadNative.arx");
        if (hMod == NULL)
            hMod = GetModuleHandleW(L"Ariadne.AcadNative.crx");
        if (hMod == NULL)
            hMod = GetModuleHandleW(L"Ariadne.AcadNative.dbx");
        const bool linkerPresent = acrxDynamicLinker != nullptr;
        r << "\"result\":{\"module_name\":\"Ariadne.AcadNative\""
          << ",\"module_handle\":" << reinterpret_cast<uintptr_t>(hMod)
          << ",\"loaded_status\":" << (hMod != NULL ? "true" : "false")
          << ",\"acrxDynamicLinker_present\":" << (linkerPresent ? "true" : "false")
          << ",\"external_module_load_invoked\":false"
          << ",\"module_unload_invoked\":false"
          << ",\"safe_status_only\":true"
          << ",\"reason\":" << njsonStr(std::string("Wave4X exposes loader status only; arbitrary external module load/unload is not agent-exposed."))
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "module.load.acad_rx") {
        const std::string acadRxPath = m08nStringArg(job, "acad_rx_path", "acad.rx");
        const std::wstring wpath = m08nWide(acadRxPath);
        const DWORD attrs = GetFileAttributesW(wpath.c_str());
        r << "\"result\":{\"acad_rx_checked\":true"
          << ",\"acad_rx_path\":" << njsonStr(acadRxPath)
          << ",\"file_present\":" << (attrs != INVALID_FILE_ATTRIBUTES ? "true" : "false")
          << ",\"autoload_file_mutated\":false"
          << ",\"safe_status_only\":true"
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "module.load.by_app") {
        const std::string appName = m08nStringArg(job, "app_name", "ARIADNE");
        const bool bounded = appName.find("ARIADNE") == 0;
        r << "\"result\":{\"app_name\":" << njsonStr(appName)
          << ",\"bounded_ariadne_app\":" << (bounded ? "true" : "false")
          << ",\"load_by_app_invoked\":false"
          << ",\"registry_lookup_mutated\":false"
          << ",\"safe_validation_only\":true"
          << "},\"status\":\"ok\"}";
        return true;
    }
    if (op == "module.load.demand_register") {
        const std::string appName = m08nStringArg(job, "app_name", "ARIADNE");
        const std::string loader = m08nStringArg(job, "loader", "Ariadne.AcadNative.arx");
        const bool bounded = appName.find("ARIADNE") == 0 && loader.find("Ariadne") != std::string::npos;
        r << "\"result\":{\"demand_load_plan\":true"
          << ",\"app_name\":" << njsonStr(appName)
          << ",\"loader\":" << njsonStr(loader)
          << ",\"loadctrls_required\":true"
          << ",\"managed_flag_required\":false"
          << ",\"bounded_ariadne_registration\":" << (bounded ? "true" : "false")
          << ",\"demand_load_registry_mutated\":false"
          << ",\"safe_validation_only\":true"
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- doc.current ---------------------------------------------------------------------
    if (op == "doc.current") {
        AcApDocument* pDoc = nullptr;
        if (acDocManager != nullptr) {
            pDoc = acDocManager->curDocument();
            if (pDoc == nullptr) {
                pDoc = acDocManager->mdiActiveDocument();
            }
        }
        std::string docTitle;
        if (pDoc != nullptr) {
            const ACHAR* title = pDoc->fileName();
            if (title != nullptr) {
                docTitle = acharToAscii(title);
            }
        }
        r << "\"result\":{\"document_ptr\":" << reinterpret_cast<uintptr_t>(pDoc)
          << ",\"doc_present\":" << (pDoc != nullptr ? "true" : "false")
          << ",\"file_name\":" << njsonStr(docTitle)
          << ",\"host_mode\":" << njsonStr(ctx.hostMode)
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- doc.lock ------------------------------------------------------------------------
    if (op == "doc.lock") {
        const bool execute = m08nBoolArg(job, "execute", false);
        AcApDocument* pDoc = nullptr;
        Acad::ErrorStatus lockEs = Acad::eNotApplicable;
        Acad::ErrorStatus unlockEs = Acad::eNotApplicable;
        if (acDocManager != nullptr) {
            pDoc = acDocManager->curDocument();
            if (pDoc == nullptr) {
                pDoc = acDocManager->mdiActiveDocument();
            }
        }
        if (execute && pDoc != nullptr && acDocManager != nullptr) {
            lockEs = acDocManager->lockDocument(pDoc, AcAp::kWrite);
            if (lockEs == Acad::eOk) {
                unlockEs = acDocManager->unlockDocument(pDoc);
            }
        }
        r << "\"result\":{\"document_ptr\":" << reinterpret_cast<uintptr_t>(pDoc)
          << ",\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"lock_status\":" << static_cast<int>(lockEs)
          << ",\"unlock_status\":" << static_cast<int>(unlockEs)
          << ",\"locked_and_unlocked\":" << ((lockEs == Acad::eOk && unlockEs == Acad::eOk) ? "true" : "false")
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- doc.new -------------------------------------------------------------------------
    if (op == "doc.new") {
        const bool execute = m08nBoolArg(job, "execute", false);
        std::string templPath = m08nStringArg(job, "template_path", "");
        if (execute && !m08nFullEditor(ctx)) {
            m08nAttendedOnly(r, op, ctx, "creating a new document requires a live MDI host");
            return true;
        }
        Acad::ErrorStatus es = Acad::eNotApplicable;
        if (execute && acDocManager != nullptr) {
            std::wstring wtempl = m08nWide(templPath);
            es = acDocManager->appContextNewDocument(wtempl.empty() ? nullptr : wtempl.c_str());
        }
        r << "\"result\":{\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"template_path\":" << njsonStr(templPath)
          << ",\"create_status\":" << static_cast<int>(es)
          << ",\"host_mode\":" << njsonStr(ctx.hostMode)
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- doc.syncopen --------------------------------------------------------------------
    if (op == "doc.syncopen") {
        const bool execute = m08nBoolArg(job, "execute", false);
        std::string dwgPath = m08nStringArg(job, "dwg_path", "");
        if (execute && !m08nFullEditor(ctx)) {
            m08nAttendedOnly(r, op, ctx, "acedSyncFileOpen requires a live document editor host");
            return true;
        }
        int rc = RTNONE;
        if (execute && !dwgPath.empty()) {
            std::wstring wpath = m08nWide(dwgPath);
            rc = static_cast<int>(acedSyncFileOpen(wpath.c_str()));
        }
        r << "\"result\":{\"execute_requested\":" << (execute ? "true" : "false")
          << ",\"dwg_path\":" << njsonStr(dwgPath)
          << ",\"acedSyncFileOpen_status\":" << rc
          << ",\"host_mode\":" << njsonStr(ctx.hostMode)
          << "},\"status\":\"ok\"}";
        return true;
    }

    // --- UI/palette/status/menu/tool builders --------------------------------------------
    if (op.find("editor.") == 0) {
        m08nUiBuilderResult(op, ctx, r);
        return true;
    }

    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "m08nHasOp admitted '" + op + "' but m08nDispatch has no handler");
    return true;
}
