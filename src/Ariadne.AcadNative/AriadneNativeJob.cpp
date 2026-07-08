//////////////////////////////////////////////////////////////////////////////
// AriadneNativeJob.cpp
//
// Native ObjectARX job control plane — the C++ mirror of the managed
// CadJobRunner. Registers the ARIADNE_NATIVE_JOB command which reads a JSON
// job (env ARIADNE_CAD_JOB_IN), dispatches by operation id, and writes a JSON
// result (env ARIADNE_CAD_JOB_OUT). Also owns the module acrxEntryPoint that
// registers the AriadneProbe custom class.
//
// P1 de-risk milestone: minimal hand-rolled JSON (to be replaced by a vendored
// JSON header in P1-full). Ops: inspect.database.summary,
// extend.customclass.create, inspect.customclass.count.
//////////////////////////////////////////////////////////////////////////////
#include <string>
#include <sstream>
#include <fstream>
#include <cstdlib>
#include <vector>
#include <ios>
#include <iomanip>
#include <limits>
#include <tchar.h>
#include <windows.h>

#include "aced.h"
#include "rxregsvc.h"
#include "dbmain.h"
#include "dbtrans.h"   // M08B-T03: AcTransactionManager / AcTransaction (txn wrappers)
#include "dbdict.h"
#include "dbents.h"
#include "dbmtext.h"
#include "dbpl.h"
#include "dbhatch.h"
#include "geell2d.h"   // a1-hatchread: AcGeEllipArc2d (hatch edge-loop ellipse-arc edges --
                       // dbhatch.h itself only pulls in gelnsg2d.h/gearc2d.h, not this one)
#include "genurb2d.h"  // a1-hatchread: AcGeNurbCurve2d (hatch edge-loop spline edges --
                       // same gap: dbhatch.h does not transitively include it)
#include "imgdef.h"    // wA-cert: AcDbRasterImageDef (rasterimage/wipeout read branch --
                       // m08g_handlers.inc also includes this, but that #include is textually
                       // AFTER collectEntitiesFromBlock in this TU (families/*.inc are included
                       // near the end of this file) -- needed here too for the read side)
#include "imgent.h"    // wA-cert: AcDbRasterImage (rasterimage read branch)
#include "dbwipe.h"    // wA-cert: AcDbWipeout (wipeout read branch -- IS-A AcDbRasterImage)
#include "dbmpolygon.h" // wA-cert: AcDbMPolygon (mpolygon read branch)
#include "dbelipse.h"  // T3a: AcDbEllipse (collectModelSpaceGraph read branch)
#include "dbdim.h"     // T3a: AcDbRotatedDimension; T3a-batch2: AcDbAlignedDimension/
                       // AcDbRadialDimension/AcDbDiametricDimension; T3a-batch3:
                       // AcDbOrdinateDimension (same header)
#include "dbspline.h"  // T3a-batch2: AcDbSpline (collectModelSpaceGraph read branch)
#include "dblead.h"    // T3a-batch3: AcDbLeader (collectModelSpaceGraph read branch --
                       // families/m08h_handlers.inc's own #include is textually AFTER
                       // collectModelSpaceGraph in this TU, so this needs its own copy)
#include "dbmline.h"   // w3-wbug: AcDbMline (collectModelSpaceGraph read branch --
                       // families/m08g_handlers.inc's own #include is textually AFTER
                       // collectModelSpaceGraph in this TU, so this needs its own copy)
#include "dbmleader.h" // w3-mleader: AcDbMLeader (collectModelSpaceGraph read branch --
                       // families/m08h_handlers.inc's own #include is textually AFTER
                       // collectModelSpaceGraph in this TU, so this needs its own copy)
#include "dbray.h"     // w3-simple1: AcDbRay (collectModelSpaceGraph read branch --
                       // families/m08g_handlers.inc's own #include is textually AFTER
                       // collectModelSpaceGraph in this TU, so this needs its own copy)
#include "dbxline.h"   // w3-simple1: AcDbXline (collectModelSpaceGraph read branch --
                       // families/m08g_handlers.inc's own #include is textually AFTER
                       // collectModelSpaceGraph in this TU, so this needs its own copy)
#include "dbsol3d.h"   // wS-solids/S8: AcDb3dSolid (collectEntitiesFromBlock read branch --
                       // families/m08g_handlers.inc's own #include is textually AFTER
                       // collectEntitiesFromBlock in this TU, so this needs its own copy)
#include "dbregion.h"  // wS-solids/S8: AcDbRegion (same reason as dbsol3d.h above)
#include "dbsurf.h"    // wS-solids/S8: AcDbSurface (same reason as dbsol3d.h above)
#include "dbnurbsurf.h" // wS-solids/S8: AcDbNurbSurface (same reason as dbsol3d.h above --
                       // MUST be visible for the AcDbNurbSurface::cast branch, which is
                       // ORDERED BEFORE AcDbSurface::cast in collectEntitiesFromBlock
                       // since AcDbNurbSurface derives from AcDbSurface)
#include "dbbody.h"    // wS-solids/S8: AcDbBody (same reason as dbsol3d.h above)
#include "dbxrecrd.h"
#include "dbsymtb.h"
#include "dbcolor.h"
#include "dbapserv.h"
#include "dblayout.h"
#include "AcDbLMgr.h"
#include "dbobjectoverrule.h"
#include "dbjig.h"
#include "acdocman.h"
#include "acutads.h"
#include "adscodes.h"
#include "acedads.h"   // M07B: acedSSGet/acedSSName/acedSSLength/acedSSFree (pickfirst selection)
#include "acdbads.h"   // M07B: acdbGetObjectId (ads_name -> AcDbObjectId)
#include "dbmaterial.h"    // w7-materials: AcDbMaterial property read (families/materials_read.inc
                           // is textually AFTER the helpers, but the cast/accessors need full defs)
#include "acgimaterial.h"  // w7-materials: AcGiMaterialColor/AcGiMaterialMap construction
#include "dbAnnotationScale.h"       // w7-annoscale: AcDbAnnotationScale (pulls dbObjContext.h)
#include "dbObjectContextManager.h"  // w7-annoscale: AcDbObjectContextManager
#include "dbObjectContextCollection.h" // w7-annoscale: collection + iterator
#include "dbObjectContextInterface.h"  // w7-annoscale: per-entity participation PE

#include "..\Ariadne.AcadNativeDbx\AriadneDbxApi.h"

// Export the API-version symbol so AutoCAD/RealDWG can verify the module
// (replaces the need for a .def file). (poly.h pattern.)
#ifdef _WIN64
#pragma comment(linker, "/export:acrxGetApiVersion,PRIVATE")
#else
#pragma comment(linker, "/export:_acrxGetApiVersion,PRIVATE")
#endif

//============================================================================
// Tiny helpers
//============================================================================
// Round-trip-safe double serialization (north-star precision fix).
//
// std::ostringstream defaults to defaultfloat + precision(6): 6 SIGNIFICANT
// figures. Every JSON emitter in this translation unit (this file plus every
// families/*.inc it #includes below) built its numbers by inserting a bare
// double into a std::ostringstream, so any coordinate/angle/radius needing
// more than 6 sig figs was silently truncated on the way out -- e.g. a line
// endpoint 645229.5 serialized as 645230, an arc end_angle 3.14159265
// serialized as 3.14159. Both the read/extraction path and the write-op
// result echo share this same ostringstream idiom, so the loss was symmetric.
// kJsonDoublePrecision is setprecision(max_digits10) (17): the smallest
// precision that round-trips every double exactly, with no added notation or
// trailing-zero padding (defaultfloat, the ostringstream default floatfield,
// is left untouched -- only the precision changes). Every JSON-building
// std::ostringstream in this file and in the families/*.inc headers below now
// calls ".precision(kJsonDoublePrecision)" right after construction so no
// emission site could be missed; integer/bool/string/handle formatting is
// unaffected (precision() only governs floating-point conversion).
static const std::streamsize kJsonDoublePrecision = std::numeric_limits<double>::max_digits10;

// Round-trip-safe formatter for doubles built outside an ostringstream (e.g.
// std::string "+" concatenation via std::to_string). Same precision contract
// as kJsonDoublePrecision above.
static std::string fmtNum(double v)
{
    std::ostringstream tmp;
    tmp << std::defaultfloat << std::setprecision(kJsonDoublePrecision) << v;
    return tmp.str();
}

static std::string readAllBytes(const wchar_t* path)
{
    std::ifstream f(path, std::ios::binary);
    if (!f.good())
        return std::string();
    std::ostringstream ss; ss.precision(kJsonDoublePrecision);
    ss << f.rdbuf();
    return ss.str();
}

static std::string wideToAscii(const std::wstring& wide)
{
    std::string out;
    out.reserve(wide.size());
    for (wchar_t c : wide)
        out.push_back((c >= 0 && c <= 127) ? static_cast<char>(c) : '?');
    return out;
}

// M02 D3 fix: lossless UTF-16 -> UTF-8. Used by acharToAscii() so every entity
// /layer/block/text string emitted into the DWG Graph IR preserves non-ASCII
// code points (e.g. the Korean layer "설비OPEN") instead of mapping them to '?'.
// The IR result file is read back as UTF-8 (PowerShell -Encoding UTF8 / Python
// utf-8-sig), so UTF-8 bytes are the correct on-disk encoding. ASCII input is a
// strict subset of UTF-8, so existing ASCII output is byte-identical (no
// regression to the 29 wired ops).
static std::string wideToUtf8(const std::wstring& wide)
{
    if (wide.empty())
        return std::string();
    const int needed = WideCharToMultiByte(
        CP_UTF8, 0, wide.c_str(), static_cast<int>(wide.size()),
        nullptr, 0, nullptr, nullptr);
    if (needed <= 0)
        return std::string();
    std::string out(static_cast<size_t>(needed), '\0');
    WideCharToMultiByte(
        CP_UTF8, 0, wide.c_str(), static_cast<int>(wide.size()),
        &out[0], needed, nullptr, nullptr);
    return out;
}

// M07B: UTF-8 -> UTF-16. Used by the ARIADNE_NATIVE_JOB_ARGS env-file channel to
// turn JSON path strings (written by the harness as UTF-8) back into wide paths
// without the lossy ASCII funnel. ASCII input is a strict subset, so ASCII paths
// are unchanged.
static std::wstring utf8ToWide(const std::string& s)
{
    if (s.empty())
        return std::wstring();
    const int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(),
                                      static_cast<int>(s.size()), nullptr, 0);
    if (n <= 0)
        return std::wstring();
    std::wstring w(static_cast<size_t>(n), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), static_cast<int>(s.size()), &w[0], n);
    return w;
}

// w3-utf8 fix: despite the historical name, this is the write-path symbol-table
// name/key/value funnel used by every AcDbBlockTable/AcDbLayerTable/RegAppTable/
// AcDbLayoutManager/xdata/dictionary lookup and setter in this file and in
// families/*.inc (block name, layer name, dict key/value, regapp name, layout
// name, ...). It used to widen each byte 1:1, silently corrupting any non-ASCII
// input -- e.g. native_sample.dwg's 245 real block definitions are all Korean
// names, and none of them resolved through AcDbBlockTable::getAt/has because the
// widened wchar_t sequence never matched the real UTF-16 symbol-table record.
// The JSON job the harness writes is UTF-8 (same convention as wideToUtf8's
// read-side counterpart above), so this now delegates to utf8ToWide. ASCII
// input is a strict subset of UTF-8, so every existing ASCII call site is
// byte-identical (no regression). The rename to utf8ToWide-only is a deferred
// cosmetic cleanup -- call sites are unchanged to keep this diff additive, same
// rationale as acharToAscii's historical-name note below.
static std::wstring asciiToWide(const std::string& value)
{
    return utf8ToWide(value);
}

static bool moduleDirectory(std::wstring& outDir);
// M07B: attended-only ARIADNE_PALETTE registration lives in AriadnePalette.cpp,
// compiled ONLY into the .arx module. Declared (not defined) here at file scope;
// the call site in acrxEntryPoint is wrapped in #ifndef ARIADNE_NATIVE_CRX so the
// headless .crx never references the symbol.
extern "C" void ariadneRegisterPaletteCommand();
// Forward decl: collectModelSpaceGraph (defined below) calls acharToAscii,
// whose definition sits further down next to the reactor helpers.
static std::string acharToAscii(const ACHAR* text);
// Handle helpers are defined with the M02 rich-graph collectors (below
// collectModelSpaceGraph) but used inside it; forward-declare them.
static std::string handleOf(AcDbObject* pObj);
static std::string handleOfId(const AcDbObjectId& id);

static std::wstring gJobInOverride;
static std::wstring gJobOutOverride;
static std::wstring gJobHostModeOverride;
static bool gUseMailboxOverride = false;

static std::wstring fullAutoCadMailboxPath()
{
    std::wstring dir;
    if (!moduleDirectory(dir))
        return std::wstring();
    for (int i = 0; i < 5; ++i) {
        const size_t slash = dir.find_last_of(L"\\/");
        if (slash == std::wstring::npos)
            return std::wstring();
        dir = dir.substr(0, slash);
    }
    return dir + L"\\runs\\full_autocad_native_job_mailbox.txt";
}

static std::wstring readMailboxSetting(const std::wstring& key)
{
    const std::wstring mailboxPath = fullAutoCadMailboxPath();
    if (mailboxPath.empty())
        return std::wstring();
    const std::string mailbox = readAllBytes(mailboxPath.c_str());
    const std::string prefix = wideToAscii(key) + "=";
    size_t pos = 0;
    while (pos < mailbox.size()) {
        size_t end = mailbox.find_first_of("\r\n", pos);
        if (end == std::string::npos)
            end = mailbox.size();
        const std::string line = mailbox.substr(pos, end - pos);
        if (line.rfind(prefix, 0) == 0)
            return asciiToWide(line.substr(prefix.size()));
        pos = end + 1;
        while (pos < mailbox.size() && (mailbox[pos] == '\r' || mailbox[pos] == '\n'))
            ++pos;
    }
    return std::wstring();
}

static std::wstring readJobPathSetting(const wchar_t* key)
{
    const std::wstring keyName(key);
    if (keyName == L"ARIADNE_CAD_JOB_IN" && !gJobInOverride.empty())
        return gJobInOverride;
    if (keyName == L"ARIADNE_CAD_JOB_OUT" && !gJobOutOverride.empty())
        return gJobOutOverride;
    if (keyName == L"ARIADNE_CAD_JOB_HOST_MODE" && !gJobHostModeOverride.empty())
        return gJobHostModeOverride;
    if (gUseMailboxOverride) {
        const std::wstring mailboxValue = readMailboxSetting(keyName);
        if (!mailboxValue.empty())
            return mailboxValue;
    }

    wchar_t acadEnv[4096] = {};
    if (acedGetEnv(key, acadEnv, _countof(acadEnv)) == RTNORM &&
        acadEnv[0] != L'\0') {
        return std::wstring(acadEnv);
    }

    const wchar_t* processEnv = _wgetenv(key);
    if (processEnv != nullptr && processEnv[0] != L'\0')
        return std::wstring(processEnv);

    return std::wstring();
}

static bool jsonFindString(const std::string& j, const char* key, std::string& out)
{
    const std::string k = std::string("\"") + key + "\"";
    size_t p = j.find(k);
    if (p == std::string::npos) return false;
    p = j.find(':', p + k.size());
    if (p == std::string::npos) return false;
    p = j.find('"', p);
    if (p == std::string::npos) return false;
    const size_t q = j.find('"', p + 1);
    if (q == std::string::npos) return false;
    out = j.substr(p + 1, q - p - 1);
    return true;
}

static bool jsonFindNumber(const std::string& j, const char* key, double& out)
{
    const std::string k = std::string("\"") + key + "\"";
    size_t p = j.find(k);
    if (p == std::string::npos) return false;
    p = j.find(':', p + k.size());
    if (p == std::string::npos) return false;
    out = strtod(j.c_str() + p + 1, nullptr);
    return true;
}

static double jsonFindNumberOr(const std::string& j, const char* firstKey,
                               const char* fallbackKey, double defaultValue)
{
    double value = defaultValue;
    if (jsonFindNumber(j, firstKey, value))
        return value;
    if (fallbackKey != nullptr && jsonFindNumber(j, fallbackKey, value))
        return value;
    return defaultValue;
}

static bool jsonFindObject(const std::string& j, const char* key, std::string& out)
{
    const std::string k = std::string("\"") + key + "\"";
    size_t p = j.find(k);
    if (p == std::string::npos) return false;
    p = j.find(':', p + k.size());
    if (p == std::string::npos) return false;
    p = j.find('{', p);
    if (p == std::string::npos) return false;

    int depth = 0;
    bool inString = false;
    bool escaped = false;
    for (size_t i = p; i < j.size(); ++i) {
        const char c = j[i];
        if (inString) {
            if (escaped) {
                escaped = false;
            }
            else if (c == '\\') {
                escaped = true;
            }
            else if (c == '"') {
                inString = false;
            }
            continue;
        }
        if (c == '"') {
            inString = true;
            continue;
        }
        if (c == '{') {
            ++depth;
        }
        else if (c == '}') {
            --depth;
            if (depth == 0) {
                out = j.substr(p, i - p + 1);
                return true;
            }
        }
    }
    return false;
}

// TABLES tier-2 (p9-tables2): parse an optional {"x":..,"y":..,"z":..} nested
// job-arg object into 3 doubles -- returns true iff ``key`` was present in
// ``job`` AT ALL (this file's hasX-flag optional-field convention: an absent
// key means "don't touch this field", not "set it to zero"). A present-but-
// incomplete object (missing "z", e.g. a 2D caller) defaults the missing
// component(s) to 0.0 rather than failing the whole field -- callers that
// only need 2 components (UCS/VIEW/VPORT's AcGePoint2d fields) simply ignore
// the unused z out-param. Shared by every point/vector-valued symbol-table
// record field UCS/VIEW/VPORT introduce (layer/dimstyle had none).
static bool jsonFindPoint3(const std::string& job, const char* key,
                           double& x, double& y, double& z)
{
    std::string obj;
    if (!jsonFindObject(job, key, obj))
        return false;
    x = 0.0; y = 0.0; z = 0.0;
    jsonFindNumber(obj, "x", x);
    jsonFindNumber(obj, "y", y);
    jsonFindNumber(obj, "z", z);
    return true;
}

// M07B: minimal "key":["a","b",...] string-array extractor for the live pump
// `handles` payload. Mirrors the hand-rolled jsonFind* idiom (no vendored JSON);
// returns raw inter-quote substrings (callers pass forward-slash/ASCII hex, so no
// unescape is needed). Stops at the first ']'.
static std::vector<std::string> jsonFindStringArray(const std::string& j, const char* key)
{
    std::vector<std::string> out;
    const std::string k = std::string("\"") + key + "\"";
    size_t p = j.find(k);
    if (p == std::string::npos) return out;
    p = j.find('[', p);
    if (p == std::string::npos) return out;
    const size_t end = j.find(']', p);
    if (end == std::string::npos) return out;
    size_t i = p + 1;
    while (i < end) {
        const size_t q1 = j.find('"', i);
        if (q1 == std::string::npos || q1 >= end) break;
        const size_t q2 = j.find('"', q1 + 1);
        if (q2 == std::string::npos || q2 > end) break;
        out.push_back(j.substr(q1 + 1, q2 - q1 - 1));
        i = q2 + 1;
    }
    return out;
}

// w3-ltts: minimal "key":[n1,n2,...] plain-number-array extractor for
// LINETYPE dash patterns (AcDbLinetypeTableRecord::setDashLengthAt takes one
// double per index -- positive=dash, negative=gap, 0=dot, per DXF/AutoCAD
// LINETYPE semantics; this file has no opinion on the sign, it just
// round-trips whatever the caller supplies). Mirrors jsonFindStringArray's
// hand-rolled idiom (no vendored JSON) directly above, but scans bare
// strtod-parseable numbers instead of quoted strings. Stops at the first ']'.
static std::vector<double> jsonFindNumberArray(const std::string& j, const char* key)
{
    std::vector<double> out;
    const std::string k = std::string("\"") + key + "\"";
    size_t p = j.find(k);
    if (p == std::string::npos) return out;
    p = j.find('[', p);
    if (p == std::string::npos) return out;
    const size_t end = j.find(']', p);
    if (end == std::string::npos) return out;
    size_t i = p + 1;
    while (i < end) {
        while (i < end && (j[i] == ',' || j[i] == ' ' || j[i] == '\t' ||
                            j[i] == '\r' || j[i] == '\n'))
            ++i;
        if (i >= end) break;
        char* parseEnd = nullptr;
        const double value = strtod(j.c_str() + i, &parseEnd);
        if (parseEnd == j.c_str() + i) break;  // no numeric token here -- stop
        out.push_back(value);
        i = static_cast<size_t>(parseEnd - j.c_str());
    }
    return out;
}

static bool parsePointFromObject(const std::string& objectJson, double& x, double& y, double& z)
{
    if (!jsonFindNumber(objectJson, "x", x))
        return false;
    if (!jsonFindNumber(objectJson, "y", y))
        return false;
    if (!jsonFindNumber(objectJson, "z", z))
        z = 0.0;
    return true;
}

static bool parsePointPayload(const std::string& job, double& x, double& y, double& z)
{
    std::string pointJson;
    if (jsonFindObject(job, "point", pointJson) && parsePointFromObject(pointJson, x, y, z))
        return true;
    if (jsonFindObject(job, "base", pointJson) && parsePointFromObject(pointJson, x, y, z))
        return true;

    std::string argsJson;
    if (jsonFindObject(job, "args", argsJson)) {
        if (jsonFindObject(argsJson, "point", pointJson) &&
            parsePointFromObject(pointJson, x, y, z)) {
            return true;
        }
        if (jsonFindObject(argsJson, "base", pointJson) &&
            parsePointFromObject(pointJson, x, y, z)) {
            return true;
        }
    }
    return false;
}

// E-b: the canonical JSON string-escape used by every njsonStr() call in
// this file. Was `"` / `\` only -- any control character (< 0x20, e.g. a
// literal '\n' inside an M08N prompt string, AriadneNativeJob.cpp line
// ~505's writeResult()/acutPrintf-adjacent native UI text) fell through
// unescaped, producing JSON that `json.load()` rejects with "Invalid
// control character" (see tools/cert_artifact_index.py findings --
// 55 malformed result JSONs, e.g.
// runs/native_batch_20260629_135844/results/245_input.get.point.json,
// confirmed live: a raw 0x0A landed at byte offset 127 inside the
// "prompt" string). Fix: \b \f \n \r \t get their short escapes (matches
// every JSON encoder); every other control byte gets \u00XX. Non-ASCII
// UTF-8 continuation/lead bytes are always >= 0x80 (> 0x20), so this is
// unchanged for them -- Korean/non-ASCII fidelity is untouched.
static std::string jsonEscape(const std::string& value)
{
    static const char kHexDigits[] = "0123456789abcdef";
    std::string out;
    out.reserve(value.size());
    for (unsigned char c : value) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b";  break;
            case '\f': out += "\\f";  break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if (c < 0x20) {
                    out += "\\u00";
                    out.push_back(kHexDigits[(c >> 4) & 0x0F]);
                    out.push_back(kHexDigits[c & 0x0F]);
                } else {
                    out.push_back(static_cast<char>(c));
                }
        }
    }
    return out;
}

static void writeResult(const wchar_t* path, const std::string& json)
{
    if (path != nullptr) {
        std::ofstream out(path, std::ios::binary | std::ios::trunc);
        if (out.good())
            out << json;
        acutPrintf(_T("\nARIADNE_NATIVE_JOB result written: %ls\n"), path);
        return;
    }
    acutPrintf(_T("\nARIADNE_NATIVE_JOB result produced without output file\n"));
}

//============================================================================
// Database helpers
//============================================================================
static const TCHAR kAriadneDbxModule[] = _T("Ariadne.AcadNativeDbx.dbx");
static const TCHAR kAriadneNativeDict[] = _T("ARIADNE_NATIVE");

static bool moduleDirectory(std::wstring& outDir)
{
    HMODULE hModule = nullptr;
    if (!GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCWSTR>(&moduleDirectory),
            &hModule)) {
        return false;
    }

    wchar_t path[MAX_PATH] = {};
    const DWORD len = GetModuleFileNameW(hModule, path, MAX_PATH);
    if (len == 0 || len >= MAX_PATH)
        return false;

    outDir.assign(path, len);
    const size_t slash = outDir.find_last_of(L"\\/");
    if (slash == std::wstring::npos)
        return false;
    outDir.resize(slash);
    return true;
}

// M07B: reliable attended-vs-headless discriminator. acedEditor is NON-null in
// BOTH accoreconsole and full AutoCAD (accoreconsole has an AcEditor singleton; it
// just lacks an interactive/graphics editor), so it cannot gate the attended ops.
// The host EXECUTABLE name is bulletproof: accoreconsole.exe (headless) vs acad.exe
// (attended). GetModuleFileNameW(NULL) returns the running host exe path.
static bool hostIsFullAutoCad()
{
    wchar_t path[MAX_PATH] = {};
    const DWORD len = GetModuleFileNameW(NULL, path, MAX_PATH);
    if (len == 0 || len >= MAX_PATH)
        return false;
    const std::wstring p(path, len);
    const size_t slash = p.find_last_of(L"\\/");
    const std::wstring base = (slash == std::wstring::npos) ? p : p.substr(slash + 1);
    return _wcsicmp(base.c_str(), L"acad.exe") == 0;
}

static bool loadDbxCore()
{
    std::wstring dir;
    if (moduleDirectory(dir)) {
        const std::wstring dbxPath = dir + L"\\" + kAriadneDbxModule;
        if (acrxLoadModule(dbxPath.c_str(), 0))
            return true;
    }
    return acrxLoadModule(kAriadneDbxModule, 0);
}

static int countSymbolTable(AcDbObjectId tableId)
{
    AcDbSymbolTable* pTable = nullptr;
    if (acdbOpenObject(pTable, tableId, AcDb::kForRead) != Acad::eOk)
        return -1;
    AcDbSymbolTableIterator* pIt = nullptr;
    if (pTable->newIterator(pIt) != Acad::eOk) {
        pTable->close();
        return -1;
    }
    int n = 0;
    for (pIt->start(); !pIt->done(); pIt->step())
        ++n;
    delete pIt;
    pTable->close();
    return n;
}

// Count entities in model space; optionally only AriadneProbe instances.
static bool countModelSpace(AcDbDatabase* pDb, int& total, int& probes)
{
    total = 0;
    probes = 0;
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
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
        if (pIt->getEntity(pEnt, AcDb::kForRead) == Acad::eOk) {
            ++total;
            if (ariadneIsProbeEntity(pEnt))
                ++probes;
            pEnt->close();
        }
    }
    delete pIt;
    pMS->close();
    return true;
}

static bool entityMatchesType(const AcDbEntity* pEnt, const std::string& type)
{
    if (type.empty())
        return true;
    if (type == "LINE")
        return AcDbLine::cast(pEnt) != nullptr;
    if (type == "CIRCLE")
        return AcDbCircle::cast(pEnt) != nullptr;
    if (type == "INSERT")
        return AcDbBlockReference::cast(pEnt) != nullptr;
    if (type == "TEXT")
        return AcDbText::cast(pEnt) != nullptr;
    return false;
}

static bool countModelSpaceEntitiesByType(AcDbDatabase* pDb, const std::string& type,
                                          int& total, int& matching)
{
    total = 0;
    matching = 0;
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
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
        if (pIt->getEntity(pEnt, AcDb::kForRead) == Acad::eOk) {
            ++total;
            if (entityMatchesType(pEnt, type))
                ++matching;
            pEnt->close();
        }
    }
    delete pIt;
    pMS->close();
    return true;
}

struct RichGraphCounters
{
    int xdataBlocks = 0;
    int xdataItems = 0;
    int extensionDictionaries = 0;
    int extensionDictionaryEntries = 0;
    int extensionXrecords = 0;
    int extensionXrecordItems = 0;
    int hatchLoops = 0;
    int hatchLoopVertices = 0;
};

//============================================================================
// M08B-T02: generic serializers + UTF-8 JSON writer.
//
// The reusable serialization primitives the M08 family tickets (C-F) build on, so
// per-op handlers never re-implement string encoding or the common AcDbObject/
// AcDbEntity field shapes. ALL string output is UTF-8 (acharToAscii()/wideToUtf8(),
// lossless) -- never the lossy wideToAscii() '?' funnel. njsonStr() is the
// canonical UTF-8 JSON-string writer.
//============================================================================

// UTF-8 JSON string writer: returns a fully-quoted, escaped JSON string token
// (e.g.  "설비OPEN" ) preserving non-ASCII code points as UTF-8 bytes; only JSON
// metacharacters are escaped. nullptr -> "". Three overloads cover the ACHAR*
// (entity/layer/class names), wide, and already-decoded std::string (handles) cases.
static std::string njsonStr(const ACHAR* s)
{
    return std::string("\"") + jsonEscape(s != nullptr ? acharToAscii(s) : std::string()) + "\"";
}
static std::string njsonStr(const std::wstring& s)
{
    return std::string("\"") + jsonEscape(wideToUtf8(s)) + "\"";
}
static std::string njsonStr(const std::string& utf8)
{
    return std::string("\"") + jsonEscape(utf8) + "\"";
}

// Generic AcDbObject common fields (NO enclosing braces; caller wraps). The shared
// shape every persisted object carries: handle, RX class name, owner handle.
static std::string serializeObjectCommon(AcDbObject* pObj)
{
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << "\"handle\":" << njsonStr(handleOf(pObj));
    const ACHAR* cls = (pObj != nullptr && pObj->isA() != nullptr) ? pObj->isA()->name() : nullptr;
    o << ",\"class\":" << njsonStr(cls);
    o << ",\"owner\":" << njsonStr(pObj != nullptr ? handleOfId(pObj->ownerId()) : std::string());
    return o.str();
}

// Generic AcDbEntity common fields (NO enclosing braces): object-common + the
// entity-common graphics properties. The base every entity handler reuses.
static std::string serializeEntityCommon(AcDbEntity* pEnt)
{
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << serializeObjectCommon(pEnt);
    if (pEnt != nullptr) {
        o << ",\"layer\":" << njsonStr(pEnt->layer());
        o << ",\"color_index\":" << static_cast<int>(pEnt->colorIndex());
        o << ",\"linetype\":" << njsonStr(pEnt->linetype());
        o << ",\"visible\":" << (pEnt->visibility() == AcDb::kVisible ? "true" : "false");
    }
    return o.str();
}

static bool resbufCodeIsString(short code)
{
    return code == 1 || code == 2 || code == 3 || code == 4 || code == 5 ||
           code == 6 || code == 7 || code == 8 || code == 9 ||
           code == 100 || code == 102 ||
           (code >= 300 && code <= 309) ||
           (code >= 1000 && code <= 1005);
}

static bool resbufCodeIsPoint(short code)
{
    return (code >= 10 && code <= 18) ||
           code == 1010 || code == 1011 || code == 1012 || code == 1013;
}

static bool resbufCodeIsReal(short code)
{
    return (code >= 40 && code <= 59) ||
           code == 1040 || code == 1041 || code == 1042;
}

static bool resbufCodeIsInt16(short code)
{
    return (code >= 60 && code <= 79) || code == 1070;
}

static bool resbufCodeIsInt32(short code)
{
    return (code >= 90 && code <= 99) || code == 1071;
}

// #118: lowercase hex encoding for resbuf binary-chunk group codes (310,
// 1004 xdata) -- READ side only. Was byte_count-only (the actual payload was
// dropped, unlike every other supported code, which always round-trips a
// "value"). Write-side support for 1004 was investigated and reverted: a
// by-value ads_binary through acutBuildList's variadic 1004 slot produced a
// resbuf that crashed AutoCAD's own DWG reader on next re-open (Access
// Violation, reproduced live via op_roundtrip_probe -- see build_log.md), so
// this fix stays read-only; verified by regression (plain string xdata and
// the full database graph walk both still work with this change present)
// rather than a live round-trip, since no safe write path for 1004 exists
// yet to construct one.
static std::string bytesToHexLower(const char* buf, int len)
{
    static const char kHexDigits[] = "0123456789abcdef";
    std::string out;
    if (buf == nullptr || len <= 0)
        return out;
    out.reserve(static_cast<size_t>(len) * 2);
    for (int i = 0; i < len; ++i) {
        const unsigned char b = static_cast<unsigned char>(buf[i]);
        out.push_back(kHexDigits[(b >> 4) & 0x0F]);
        out.push_back(kHexDigits[b & 0x0F]);
    }
    return out;
}

static std::string resbufItemJson(const resbuf* rb)
{
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << "{\"code\":" << rb->restype;
    const short code = rb->restype;
    if (resbufCodeIsString(code)) {
        // M08B-T02: route through the canonical UTF-8 JSON writer (byte-identical
        // output; now covers njsonStr() under the existing resbuf/xdata tests).
        o << ",\"value\":" << njsonStr(rb->resval.rstring);
    }
    else if (resbufCodeIsPoint(code)) {
        o << ",\"value\":[" << rb->resval.rpoint[0] << ","
          << rb->resval.rpoint[1] << "," << rb->resval.rpoint[2] << "]";
    }
    else if (resbufCodeIsReal(code)) {
        o << ",\"value\":" << rb->resval.rreal;
    }
    else if (resbufCodeIsInt16(code)) {
        o << ",\"value\":" << rb->resval.rint;
    }
    else if (resbufCodeIsInt32(code)) {
        o << ",\"value\":" << rb->resval.rlong;
    }
    else if (code >= 290 && code <= 299) {
        o << ",\"value\":" << (rb->resval.rint != 0 ? "true" : "false");
    }
    else if (code == 310 || code == 1004) {
        // #118: was byte_count-only (the actual payload was dropped, unlike
        // every other supported code, which always round-trips a "value").
        // Now also emits the raw bytes as a lowercase hex string.
        o << ",\"value_kind\":\"binary\",\"byte_count\":" << rb->resval.rbinary.clen
          << ",\"value\":" << njsonStr(bytesToHexLower(rb->resval.rbinary.buf, rb->resval.rbinary.clen));
    }
    else {
        o << ",\"value_kind\":\"unhandled\"";
    }
    o << "}";
    return o.str();
}

static std::string resbufItemsJson(resbuf* rb, int& itemCount)
{
    itemCount = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    for (resbuf* cur = rb; cur != nullptr; cur = cur->rbnext) {
        if (!first)
            arr << ",";
        first = false;
        arr << resbufItemJson(cur);
        ++itemCount;
    }
    arr << "]";
    return arr.str();
}

static std::string xdataBlocksJson(resbuf* rb, int& blockCount, int& itemCount)
{
    blockCount = 0;
    itemCount = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool firstBlock = true;
    bool blockOpen = false;
    bool firstItem = true;
    for (resbuf* cur = rb; cur != nullptr; cur = cur->rbnext) {
        if (cur->restype == 1001) {
            if (blockOpen)
                arr << "]}";
            if (!firstBlock)
                arr << ",";
            firstBlock = false;
            blockOpen = true;
            firstItem = true;
            const ACHAR* raw = cur->resval.rstring;
            arr << "{\"app\":\"" << jsonEscape(raw != nullptr ? acharToAscii(raw) : std::string())
                << "\",\"items\":[";
            ++blockCount;
            continue;
        }
        if (!blockOpen) {
            if (!firstBlock)
                arr << ",";
            firstBlock = false;
            blockOpen = true;
            firstItem = true;
            arr << "{\"app\":\"\",\"items\":[";
            ++blockCount;
        }
        if (!firstItem)
            arr << ",";
        firstItem = false;
        arr << resbufItemJson(cur);
        ++itemCount;
    }
    if (blockOpen)
        arr << "]}";
    arr << "]";
    return arr.str();
}

static std::string xrecordJson(AcDbXrecord* pXrec,
                               const std::string& handle,
                               const std::string& ownerHandle,
                               const std::string& key,
                               int& itemCount)
{
    itemCount = 0;
    std::string items = "[]";
    resbuf* rb = nullptr;
    const Acad::ErrorStatus es = pXrec->rbChain(&rb);
    if (es == Acad::eOk && rb != nullptr) {
        items = resbufItemsJson(rb, itemCount);
        acutRelRb(rb);
    }
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << "{\"handle\":\"" << jsonEscape(handle) << "\""
      << ",\"owner_handle\":\"" << jsonEscape(ownerHandle) << "\""
      << ",\"key\":\"" << jsonEscape(key) << "\""
      << ",\"item_count\":" << itemCount
      << ",\"items\":" << items << "}";
    return o.str();
}

static std::string dictionaryEntriesJson(AcDbDictionary* pDict,
                                         const std::string& dictHandle,
                                         std::ostringstream& xrecords,
                                         bool& xrecordFirst,
                                         RichGraphCounters& counters)
{
    std::ostringstream entries; entries.precision(kJsonDoublePrecision);
    entries << "[";
    bool first = true;
    AcDbDictionaryIterator* pIt = pDict->newIterator();
    for (; pIt != nullptr && !pIt->done(); pIt->next()) {
        const ACHAR* keyRaw = pIt->name();
        const std::string key = (keyRaw != nullptr) ? acharToAscii(keyRaw) : std::string();
        const AcDbObjectId valueId = pIt->objectId();
        const std::string valueHandle = handleOfId(valueId);
        std::string className;
        bool isXrecord = false;

        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, valueId, AcDb::kForRead) == Acad::eOk) {
            if (pObj->isA() != nullptr)
                className = acharToAscii(pObj->isA()->name());
            AcDbXrecord* pXrec = AcDbXrecord::cast(pObj);
            if (pXrec != nullptr) {
                isXrecord = true;
                int itemCount = 0;
                if (!xrecordFirst)
                    xrecords << ",";
                xrecordFirst = false;
                xrecords << xrecordJson(pXrec, valueHandle, dictHandle, key, itemCount);
                ++counters.extensionXrecords;
                counters.extensionXrecordItems += itemCount;
            }
            pObj->close();
        }

        if (!first)
            entries << ",";
        first = false;
        entries << "{\"key\":\"" << jsonEscape(key) << "\""
                << ",\"value_handle\":\"" << jsonEscape(valueHandle) << "\""
                << ",\"class_name\":\"" << jsonEscape(className) << "\""
                << ",\"is_xrecord\":" << (isXrecord ? "true" : "false") << "}";
        ++counters.extensionDictionaryEntries;
    }
    delete pIt;
    entries << "]";
    return entries.str();
}

static std::string extensionDictionaryJson(const std::string& ownerHandle,
                                           const AcDbObjectId& dictId,
                                           std::ostringstream& xrecords,
                                           bool& xrecordFirst,
                                           RichGraphCounters& counters)
{
    if (dictId.isNull())
        return std::string();

    AcDbDictionary* pDict = nullptr;
    if (acdbOpenObject(pDict, dictId, AcDb::kForRead) != Acad::eOk)
        return std::string();

    const std::string dictHandle = handleOf(pDict);
    const std::string entries = dictionaryEntriesJson(
        pDict, dictHandle, xrecords, xrecordFirst, counters);
    pDict->close();
    ++counters.extensionDictionaries;

    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << "{\"owner_handle\":\"" << jsonEscape(ownerHandle) << "\""
      << ",\"handle\":\"" << jsonEscape(dictHandle) << "\""
      << ",\"entries\":" << entries << "}";
    return o.str();
}

// a1-hatchread: one hatch boundary edge, from the AcDbHatch::getLoopAt edge-array
// overload. edgePtr is the raw AcGeVoidPointerArray element for this edge;
// edgeType is AutoCAD's own AcDbHatch::HatchEdgeType tag (kLine=1/kCirArc=2/
// kEllArc=3/kSpline=4) telling us which AcGeCurve2d subclass it actually points
// at -- ObjectARX's documented contract is that EACH of these edge objects is
// individually heap-allocated by getLoopAt and ownership passes to the caller
// (must be deleted here, once, after this function has read it). Coordinates
// are the curve's own 2D (loop-plane) values -- the hatch's elevation/normal
// (emitted once at the entity level, not per-edge) already places that plane
// in space, so no z is fabricated here (unlike the polyline-loop vertices
// below, which keep the pre-existing "[x,y,elevation]" shape for continuity
// with what op_roundtrip_probe/ir_builder already expect from THAT branch).
static std::string hatchEdgeJson(void* edgePtr, int edgeType)
{
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    switch (edgeType) {
    case AcDbHatch::kLine: {
        AcGeLineSeg2d* seg = static_cast<AcGeLineSeg2d*>(edgePtr);
        const AcGePoint2d sp = seg->startPoint();
        const AcGePoint2d ep = seg->endPoint();
        o << "{\"type\":\"line\""
          << ",\"start\":[" << sp.x << "," << sp.y << "]"
          << ",\"end\":[" << ep.x << "," << ep.y << "]}";
        delete seg;
        break;
    }
    case AcDbHatch::kCirArc: {
        AcGeCircArc2d* a = static_cast<AcGeCircArc2d*>(edgePtr);
        const AcGePoint2d c = a->center();
        o << "{\"type\":\"circ_arc\""
          << ",\"center\":[" << c.x << "," << c.y << "]"
          << ",\"radius\":" << a->radius()
          << ",\"start_angle\":" << a->startAng()
          << ",\"end_angle\":" << a->endAng()
          << ",\"counterclockwise\":" << (a->isClockWise() ? "false" : "true") << "}";
        delete a;
        break;
    }
    case AcDbHatch::kEllArc: {
        AcGeEllipArc2d* e = static_cast<AcGeEllipArc2d*>(edgePtr);
        const AcGePoint2d c = e->center();
        const AcGeVector2d maj = e->majorAxis();
        o << "{\"type\":\"ellipse_arc\""
          << ",\"center\":[" << c.x << "," << c.y << "]"
          << ",\"major_axis\":[" << maj.x << "," << maj.y << "]"
          << ",\"major_radius\":" << e->majorRadius()
          << ",\"minor_radius\":" << e->minorRadius()
          << ",\"start_angle\":" << e->startAng()
          << ",\"end_angle\":" << e->endAng()
          << ",\"counterclockwise\":" << (e->isClockWise() ? "false" : "true") << "}";
        delete e;
        break;
    }
    case AcDbHatch::kSpline: {
        AcGeNurbCurve2d* n = static_cast<AcGeNurbCurve2d*>(edgePtr);
        int degree = 0;
        Adesk::Boolean rational = Adesk::kFalse, periodic = Adesk::kFalse;
        AcGeKnotVector knots;
        AcGePoint2dArray ctrlPts;
        AcGeDoubleArray weights;
        n->getDefinitionData(degree, rational, periodic, knots, ctrlPts, weights);
        std::ostringstream cps; cps.precision(kJsonDoublePrecision);
        cps << "[";
        for (int cpi = 0; cpi < ctrlPts.length(); ++cpi) {
            if (cpi) cps << ",";
            const AcGePoint2d p = ctrlPts[cpi];
            cps << "[" << p.x << "," << p.y << "]";
        }
        cps << "]";
        std::ostringstream kns; kns.precision(kJsonDoublePrecision);
        kns << "[";
        for (int ki = 0; ki < knots.length(); ++ki) {
            if (ki) kns << ",";
            kns << knots[ki];
        }
        kns << "]";
        o << "{\"type\":\"spline\""
          << ",\"degree\":" << degree
          << ",\"rational\":" << (rational ? "true" : "false")
          << ",\"periodic\":" << (periodic ? "true" : "false")
          << ",\"control_points\":" << cps.str()
          << ",\"knots\":" << kns.str() << "}";
        delete n;
        break;
    }
    default:
        // No-fake-success: an edge type AutoCAD did not document to us yet
        // (HatchEdgeType is a closed 4-value enum today) is surfaced honestly
        // instead of silently dropped or misdecoded. Nothing to delete: we
        // never cast (and therefore never identified an owning type for) an
        // unrecognized edgePtr, so leaking a typed delete on an unknown
        // subclass would be worse than leaving this one edge unreleased.
        o << "{\"type\":\"unknown\",\"raw_edge_type\":" << edgeType << "}";
        break;
    }
    return o.str();
}

static std::string hatchLoopsJson(AcDbHatch* pHatch, int& loopCount, int& vertexCount)
{
    loopCount = 0;
    vertexCount = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool firstLoop = true;
    const int loops = pHatch->numLoops();
    const double elevation = pHatch->elevation();
    for (int li = 0; li < loops; ++li) {
        const Adesk::Int32 loopType = pHatch->loopTypeAt(li);
        const bool isPolylineLoop = (loopType & AcDbHatch::kPolyline) != 0;
        const bool loopClosed = (loopType & AcDbHatch::kNotClosed) == 0;
        if (!firstLoop)
            arr << ",";
        firstLoop = false;
        arr << "{\"index\":" << li
            << ",\"loop_type\":" << loopType
            << ",\"closed\":" << (loopClosed ? "true" : "false");
        if (isPolylineLoop) {
            // Unchanged from the original polyline-vertex path (T3a-era):
            // getLoopAt's vertices/bulges overload is the one ObjectARX
            // guarantees for a kPolyline loop.
            AcGePoint2dArray vertices;
            AcGeDoubleArray bulges;
            Adesk::Int32 loopTypeOut = 0;
            const Acad::ErrorStatus es = pHatch->getLoopAt(li, loopTypeOut, vertices, bulges);
            arr << ",\"status\":\"" << (es == Acad::eOk ? "ok" : "unavailable") << "\""
                << ",\"vertices\":[";
            if (es == Acad::eOk) {
                ++loopCount;
                const int n = vertices.length();
                for (int vi = 0; vi < n; ++vi) {
                    if (vi != 0)
                        arr << ",";
                    const AcGePoint2d p = vertices[vi];
                    const double bulge = (vi < bulges.length()) ? bulges[vi] : 0.0;
                    arr << "{\"point\":[" << p.x << "," << p.y << "," << elevation << "]"
                        << ",\"bulge\":" << bulge << "}";
                    ++vertexCount;
                }
            }
            arr << "]}";
        } else {
            // a1-hatchread: non-polyline (edge) loop -- the getLoopAt overload
            // this branch was missing entirely before: every line/arc/ellipse/
            // spline-bounded hatch loop surfaced as an empty "unavailable"
            // vertices:[] (the polyline-only overload legitimately fails on a
            // loop that is not kPolyline), silently losing 100% of that loop's
            // boundary geometry.
            Adesk::Int32 loopTypeOut = 0;
            AcGeVoidPointerArray edgePtrs;
            AcGeIntArray edgeTypes;
            const Acad::ErrorStatus es = pHatch->getLoopAt(li, loopTypeOut, edgePtrs, edgeTypes);
            arr << ",\"status\":\"" << (es == Acad::eOk ? "ok" : "unavailable") << "\""
                << ",\"edges\":[";
            if (es == Acad::eOk) {
                ++loopCount;
                const int n = edgePtrs.length();
                for (int ei = 0; ei < n; ++ei) {
                    if (ei != 0)
                        arr << ",";
                    arr << hatchEdgeJson(edgePtrs[ei], edgeTypes[ei]);
                    ++vertexCount;  // rough boundary-geometry-item tally, same
                                    // counter the polyline branch above uses
                                    // for its per-vertex count.
                }
            }
            arr << "]}";
        }
    }
    arr << "]";
    return arr.str();
}

static std::string hatchPatternDefinitionsJson(AcDbHatch* pHatch)
{
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool firstDef = true;
    const int defs = pHatch->numPatternDefinitions();
    for (int di = 0; di < defs; ++di) {
        double angle = 0.0, baseX = 0.0, baseY = 0.0, offsetX = 0.0, offsetY = 0.0;
        AcGeDoubleArray dashes;
        const Acad::ErrorStatus es =
            pHatch->getPatternDefinitionAt(di, angle, baseX, baseY, offsetX, offsetY, dashes);
        if (es != Acad::eOk)
            continue;
        if (!firstDef)
            arr << ",";
        firstDef = false;
        // ObjectARX reports hatch definition angles in radians; preserve that
        // verbatim so .pat synthesis is the single degrees-conversion site.
        arr << "{\"angle\":" << angle
            << ",\"base\":[" << baseX << "," << baseY << "]"
            << ",\"offset\":[" << offsetX << "," << offsetY << "]"
            << ",\"dashes\":[";
        for (int dashIdx = 0; dashIdx < dashes.length(); ++dashIdx) {
            if (dashIdx != 0)
                arr << ",";
            arr << dashes[dashIdx];
        }
        arr << "]}";
    }
    arr << "]";
    return arr.str();
}

static bool jsonArrayHasItems(const std::string& arr)
{
    return arr.size() > 2 && arr.find_first_not_of(" \t\r\n", 1) != arr.size() - 1;
}

static std::string jsonArrayInner(const std::string& arr)
{
    if (arr.size() < 2)
        return std::string();
    return arr.substr(1, arr.size() - 2);
}

static std::string mergeJsonArrays(const std::string& left, const std::string& right)
{
    const bool hasLeft = jsonArrayHasItems(left);
    const bool hasRight = jsonArrayHasItems(right);
    if (!hasLeft && !hasRight)
        return "[]";
    if (!hasLeft)
        return right;
    if (!hasRight)
        return left;
    return "[" + jsonArrayInner(left) + "," + jsonArrayInner(right) + "]";
}

// wS-solids/S8: minimal bbox emitter shared by the 5 ASM/solids classes below
// (AcDb3dSolid/AcDbSurface/AcDbNurbSurface/AcDbRegion/AcDbBody) -- none of
// them has a per-class cast branch today (WaveS0 finding G3 in build_log.md),
// so every one extracts as the bare {handle,dxf_name,layer,owner_handle,
// space} generic record with no geometry signal at all, not even bbox.
// getGeomExtents is a cheap AcDbEntity virtual (not an AcBr/ASM call) --
// Tier A per WaveS0's cert design: a real bbox now; richer geometry.
// brep_envelope (volume/area/centroid/face counts, mirroring the AcBr fields
// this wave's B6 gate already reads per-op) is deferred to a future Tier B
// bulk-extraction pass.
static std::string bboxJsonField(AcDbEntity* pEnt)
{
    AcDbExtents ext;
    if (pEnt->getGeomExtents(ext) != Acad::eOk || !ext.isValid())
        return std::string();
    const AcGePoint3d mn = ext.minPoint();
    const AcGePoint3d mx = ext.maxPoint();
    std::ostringstream o;
    o << ",\"bbox\":[" << mn.x << "," << mn.y << "," << mn.z << ","
      << mx.x << "," << mx.y << "," << mx.z << "]";
    return o.str();
}

//----------------------------------------------------------------------------
// collectEntitiesFromBlock
//
// w3-blockdef: generalized from the original collectModelSpaceGraph (which is
// now a thin *Model_Space-only wrapper below) so block-DEFINITION contents
// can reuse the exact same per-entity extraction the ~25 certified kinds
// already use, instead of a second hand-maintained copy. Pure read: walk
// pBTR's owned entities (any block-table-record -- *Model_Space via
// collectModelSpaceGraph, or a named block def via collectBlockDefinitions)
// and emit ONE IR record per entity into a nested JSON array (entitiesJson),
// tagged with the caller-supplied spaceLabel ("model" | "block"), and the
// total entity count (total). Caller opens/closes pBTR; this function only
// opens/closes its own entity iterator over it. Uses the same comma-first
// appendJsonString / jsonEscape idiom as the other emitters in this file.
// Floats use the default ostringstream precision, exactly like the existing
// write.entity.* emitters.
//
// acharToAscii() (despite its historical name) emits UTF-8, not ASCII -- see
// its own definition below -- so non-ASCII layer/type/text names round-trip
// correctly here for both spaces; no fidelity limitation to document.
//----------------------------------------------------------------------------
static bool collectEntitiesFromBlock(AcDbBlockTableRecord* pBTR, const char* spaceLabel,
                                     int& total,
                                     std::string& entitiesJson,
                                     std::string& extensionDictionariesJson,
                                     std::string& extensionXrecordsJson,
                                     RichGraphCounters& richCounters)
{
    total = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    std::ostringstream extensionDictionaries; extensionDictionaries.precision(kJsonDoublePrecision);
    extensionDictionaries << "[";
    bool extensionDictionaryFirst = true;
    std::ostringstream extensionXrecords; extensionXrecords.precision(kJsonDoublePrecision);
    extensionXrecords << "[";
    bool extensionXrecordFirst = true;

    AcDbBlockTableRecordIterator* pIt = nullptr;
    if (pBTR->newIterator(pIt) != Acad::eOk)
        return false;

    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbEntity* pEnt = nullptr;
        if (pIt->getEntity(pEnt, AcDb::kForRead) != Acad::eOk)
            continue;
        ++total;

        // handle (this entity's persistent objectId handle, ascii hex)
        std::string handleStr;
        {
            AcDbHandle h;
            pEnt->getAcDbHandle(h);
            ACHAR hbuf[40] = {};
            if (h.getIntoAsciiBuffer(hbuf, 40))
                handleStr = acharToAscii(hbuf);
        }
        // owner handle (model-space BTR) via the objectId, no extra open needed
        std::string ownerStr;
        {
            const AcDbHandle oh = pEnt->ownerId().handle();
            ACHAR obuf[40] = {};
            if (oh.getIntoAsciiBuffer(obuf, 40))
                ownerStr = acharToAscii(obuf);
        }
        // dxf_name from the runtime class, layer from the entity
        const std::string dxfName = (pEnt->isA() != nullptr)
            ? acharToAscii(pEnt->isA()->name()) : std::string();
        const std::string layer = acharToAscii(pEnt->layer());

        if (!first)
            arr << ",";
        first = false;
        arr << "{\"handle\":\"" << jsonEscape(handleStr) << "\""
            << ",\"dxf_name\":\"" << jsonEscape(dxfName) << "\""
            << ",\"layer\":\"" << jsonEscape(layer) << "\""
            << ",\"owner_handle\":\"" << jsonEscape(ownerStr) << "\""
            << ",\"space\":\"" << spaceLabel << "\"";

        resbuf* xdata = pEnt->xData(nullptr);
        if (xdata != nullptr) {
            int blockCount = 0, itemCount = 0;
            const std::string blocksJson = xdataBlocksJson(xdata, blockCount, itemCount);
            acutRelRb(xdata);
            if (blockCount > 0) {
                arr << ",\"xdata\":" << blocksJson;
                richCounters.xdataBlocks += blockCount;
                richCounters.xdataItems += itemCount;
            }
        }

        const AcDbObjectId extDictId = pEnt->extensionDictionary();
        if (!extDictId.isNull()) {
            arr << ",\"extension_dictionary_handle\":\""
                << jsonEscape(handleOfId(extDictId)) << "\"";
            const std::string extJson = extensionDictionaryJson(
                handleStr, extDictId, extensionXrecords, extensionXrecordFirst, richCounters);
            if (!extJson.empty()) {
                if (!extensionDictionaryFirst)
                    extensionDictionaries << ",";
                extensionDictionaryFirst = false;
                extensionDictionaries << extJson;
            }
        }

        // type-specific geometry by cast (cheap accessors only)
        if (AcDbLine* pLine = AcDbLine::cast(pEnt)) {
            const AcGePoint3d s = pLine->startPoint();
            const AcGePoint3d e = pLine->endPoint();
            arr << ",\"start\":[" << s.x << "," << s.y << "," << s.z << "]"
                << ",\"end\":[" << e.x << "," << e.y << "," << e.z << "]";
        }
        else if (AcDbArc* pArc = AcDbArc::cast(pEnt)) {
            // AcDbArc derives from AcDbCircle; test arc BEFORE circle.
            const AcGePoint3d c = pArc->center();
            arr << ",\"center\":[" << c.x << "," << c.y << "," << c.z << "]"
                << ",\"radius\":" << pArc->radius()
                << ",\"start_angle\":" << pArc->startAngle()
                << ",\"end_angle\":" << pArc->endAngle();
        }
        else if (AcDbCircle* pCir = AcDbCircle::cast(pEnt)) {
            const AcGePoint3d c = pCir->center();
            arr << ",\"center\":[" << c.x << "," << c.y << "," << c.z << "]"
                << ",\"radius\":" << pCir->radius();
        }
        // T3a: AcDbEllipse derives from AcDbCurve (not from AcDbCircle/AcDbArc),
        // so its cast() ordering relative to them is not load-bearing -- placed
        // here purely to group the curve-ish primitives together.
        else if (AcDbEllipse* pEl = AcDbEllipse::cast(pEnt)) {
            const AcGePoint3d c = pEl->center();
            const AcGeVector3d major = pEl->majorAxis();
            const AcGeVector3d nrm = pEl->normal();
            arr << ",\"center\":[" << c.x << "," << c.y << "," << c.z << "]"
                << ",\"major_axis\":[" << major.x << "," << major.y << "," << major.z << "]"
                << ",\"radius_ratio\":" << pEl->radiusRatio()
                << ",\"start_angle\":" << pEl->startAngle()
                << ",\"end_angle\":" << pEl->endAngle()
                << ",\"normal\":[" << nrm.x << "," << nrm.y << "," << nrm.z << "]";
        }
        // T3a-batch2: AcDbSpline, also grouped here with the other curve-ish
        // primitives (derives from AcDbCurve directly, no cast-order concern).
        // degree/closed/fit_points are direct, args-derivable echoes of what
        // write.entity.spline's fit-point ctor (m08g_handlers.inc) was given --
        // order-1, always non-periodic/non-closed for that op, and the literal
        // input "points" array -- so those three are honest P-gate ground
        // truth. spline_control_points/spline_knots are ALSO extracted
        // (AcDbSpline::getNurbsData, one call) but are AutoCAD's OWN
        // fit-to-NURBS conversion result, not derivable from this op's own
        // args alone -- ir_builder.py surfaces them as TOP-LEVEL entity
        // fields (never inside "geometry"), the exact same treatment T3a gave
        // dim_block_handle/dim_block_name below, and for the exact same
        // reason (see op_roundtrip_probe.py's _expect_create_spline).
        else if (AcDbSpline* pSpl = AcDbSpline::cast(pEnt)) {
            arr << ",\"degree\":" << pSpl->degree()
                << ",\"closed\":" << (pSpl->isClosed() ? "true" : "false");
            const int nFit = pSpl->numFitPoints();
            arr << ",\"fit_points\":[";
            for (int fi = 0; fi < nFit; ++fi) {
                AcGePoint3d fp;
                if (pSpl->getFitPointAt(fi, fp) != Acad::eOk)
                    break;
                if (fi != 0) arr << ",";
                arr << "[" << fp.x << "," << fp.y << "," << fp.z << "]";
            }
            arr << "]";
            int nurbsDegree = 0;
            Adesk::Boolean rational = Adesk::kFalse, closedFlag = Adesk::kFalse, periodic = Adesk::kFalse;
            AcGePoint3dArray ctrlPts;
            AcGeDoubleArray knots, weights;
            double ctrlTol = 0.0, knotTol = 0.0;
            if (pSpl->getNurbsData(nurbsDegree, rational, closedFlag, periodic, ctrlPts, knots,
                                   weights, ctrlTol, knotTol) == Acad::eOk) {
                arr << ",\"spline_control_points\":[";
                for (int ci = 0; ci < ctrlPts.length(); ++ci) {
                    if (ci != 0) arr << ",";
                    arr << "[" << ctrlPts[ci].x << "," << ctrlPts[ci].y << "," << ctrlPts[ci].z << "]";
                }
                arr << "]";
                arr << ",\"spline_knots\":[";
                for (int ki = 0; ki < knots.length(); ++ki) {
                    if (ki != 0) arr << ",";
                    arr << knots[ki];
                }
                arr << "]";
            }
        }
        else if (AcDbBlockReference* pRef = AcDbBlockReference::cast(pEnt)) {
            const AcGePoint3d p = pRef->position();
            const AcGeScale3d sc = pRef->scaleFactors();
            arr << ",\"position\":[" << p.x << "," << p.y << "," << p.z << "]"
                << ",\"scale\":[" << sc.sx << "," << sc.sy << "," << sc.sz << "]"
                << ",\"rotation\":" << pRef->rotation();
            std::string blockName;
            AcDbBlockTableRecord* pDef = nullptr;
            if (acdbOpenObject(pDef, pRef->blockTableRecord(),
                               AcDb::kForRead) == Acad::eOk) {
                const ACHAR* nameRaw = nullptr;
                if (pDef->getName(nameRaw) == Acad::eOk)
                    blockName = acharToAscii(nameRaw);
                pDef->close();
            }
            arr << ",\"block_name\":\"" << jsonEscape(blockName) << "\""
                << ",\"block_record_handle\":\"" << jsonEscape(handleOfId(pRef->blockTableRecord())) << "\"";
            // p3-insattr: attached ATTRIB values, grouped on the INSERT itself.
            // attributeIterator() walks objects appended via appendAttribute()
            // (write.entity.blockref's new "attributes" job arg, m08g_handlers.
            // inc) -- each ALSO appears as its own top-level entity below (see
            // the AcDbAttribute branch just after this one: appendAttribute
            // adds it to the same owner space as the block reference, per the
            // ObjectARX Developer's Guide), so this is a convenience cross-
            // reference, not the only place the data lives. Mirrors schemas/
            // dwg_graph_ir.v1.schema.json's $defs/block_reference.attributes[]
            // shape (tag/value/handle), plus position/height for richer fidelity.
            {
                std::ostringstream attrs; attrs.precision(kJsonDoublePrecision);
                attrs << "[";
                bool afirst = true;
                AcDbObjectIterator* pAIt = pRef->attributeIterator();
                for (; pAIt != nullptr && !pAIt->done(); pAIt->step()) {
                    AcDbAttribute* pA = nullptr;
                    if (acdbOpenObject(pA, pAIt->objectId(), AcDb::kForRead) != Acad::eOk)
                        continue;
                    const AcGePoint3d ap = pA->position();
                    if (!afirst) attrs << ",";
                    afirst = false;
                    attrs << "{\"handle\":\"" << jsonEscape(handleOfId(pAIt->objectId())) << "\""
                          << ",\"tag\":\"" << jsonEscape(acharToAscii(pA->tagConst())) << "\""
                          << ",\"value\":\"" << jsonEscape(acharToAscii(pA->textStringConst())) << "\""
                          << ",\"position\":[" << ap.x << "," << ap.y << "," << ap.z << "]"
                          << ",\"height\":" << pA->height() << "}";
                    pA->close();
                }
                delete pAIt;
                attrs << "]";
                arr << ",\"attributes\":" << attrs.str();
            }
        }
        // p3-insattr: AcDbAttributeDefinition (ATTDEF) -- derives from AcDbText
        // (dbents.h), so this branch MUST precede the generic AcDbText cast
        // below, or every ATTDEF would silently fall into the generic text
        // shape (position/text/height only -- no tag/prompt/flags). Position/
        // height/text reuse AcDbText's own accessors (inherited); tag/prompt/
        // constant/invisible/verifiable/preset are ATTDEF-specific (dbents.h).
        else if (AcDbAttributeDefinition* pAttDef = AcDbAttributeDefinition::cast(pEnt)) {
            const AcGePoint3d p = pAttDef->position();
            arr << ",\"position\":[" << p.x << "," << p.y << "," << p.z << "]"
                << ",\"text\":\"" << jsonEscape(acharToAscii(pAttDef->textStringConst())) << "\""
                << ",\"height\":" << pAttDef->height()
                << ",\"tag\":\"" << jsonEscape(acharToAscii(pAttDef->tagConst())) << "\""
                << ",\"prompt\":\"" << jsonEscape(acharToAscii(pAttDef->promptConst())) << "\""
                << ",\"constant\":" << (pAttDef->isConstant() ? "true" : "false")
                << ",\"invisible\":" << (pAttDef->isInvisible() ? "true" : "false")
                << ",\"verifiable\":" << (pAttDef->isVerifiable() ? "true" : "false")
                << ",\"preset\":" << (pAttDef->isPreset() ? "true" : "false");
        }
        // p3-insattr: AcDbAttribute (ATTRIB) -- also derives from AcDbText (same
        // cast-order requirement as AcDbAttributeDefinition above). This branch
        // is what a standalone top-level ATTRIB entity hits when this function
        // walks a block/modelspace's own entity iterator (appendAttribute adds
        // the ATTRIB to the same owner space as its block reference); the
        // AcDbBlockReference branch above ALSO surfaces the same data grouped
        // as a convenience "attributes" array on the owning INSERT.
        else if (AcDbAttribute* pAttr = AcDbAttribute::cast(pEnt)) {
            const AcGePoint3d p = pAttr->position();
            arr << ",\"position\":[" << p.x << "," << p.y << "," << p.z << "]"
                << ",\"text\":\"" << jsonEscape(acharToAscii(pAttr->textStringConst())) << "\""
                << ",\"height\":" << pAttr->height()
                << ",\"tag\":\"" << jsonEscape(acharToAscii(pAttr->tagConst())) << "\""
                << ",\"constant\":" << (pAttr->isConstant() ? "true" : "false")
                << ",\"invisible\":" << (pAttr->isInvisible() ? "true" : "false")
                << ",\"verifiable\":" << (pAttr->isVerifiable() ? "true" : "false")
                << ",\"preset\":" << (pAttr->isPreset() ? "true" : "false");
        }
        else if (AcDbMText* pM = AcDbMText::cast(pEnt)) {
            const AcGePoint3d p = pM->location();
            arr << ",\"position\":[" << p.x << "," << p.y << "," << p.z << "]"
                << ",\"text\":\"" << jsonEscape(acharToAscii(pM->contents())) << "\""
                << ",\"height\":" << pM->textHeight();
        }
        else if (AcDbText* pT = AcDbText::cast(pEnt)) {
            const AcGePoint3d p = pT->position();
            arr << ",\"position\":[" << p.x << "," << p.y << "," << p.z << "]"
                << ",\"text\":\"" << jsonEscape(acharToAscii(pT->textStringConst())) << "\""
                << ",\"height\":" << pT->height();
        }
        else if (AcDbPolyline* pPl = AcDbPolyline::cast(pEnt)) {
            const unsigned int n = pPl->numVerts();
            arr << ",\"vertex_count\":" << n
                << ",\"closed\":" << (pPl->isClosed() ? "true" : "false")
                << ",\"vertices\":[";
            for (unsigned int vi = 0; vi < n; ++vi) {
                AcGePoint3d vp;
                if (pPl->getPointAt(vi, vp) != Acad::eOk)
                    break;
                double bulge = 0.0;
                pPl->getBulgeAt(vi, bulge);
                if (vi != 0)
                    arr << ",";
                arr << "{\"point\":[" << vp.x << "," << vp.y << "," << vp.z << "]"
                    << ",\"bulge\":" << bulge << "}";
            }
            arr << "]";
        }
        // M02: old-style 2D/3D polylines store vertices as owned sub-entities
        // (AcDb2dVertex / AcDb3dPolylineVertex) walked via vertexIterator(), not
        // getPointAt(). Without this branch these (1874 POLYLINE in the golden)
        // carried no coordinate geometry. position() is OCS for 2D; emitted as-is.
        // p4-poly2d: extended with elevation/default_start_width/default_end_width
        // (entity-level) and per-vertex bulge/start_width/end_width (was bare
        // [x,y,z]) so the deep write.entity.polyline2d.deep write path (AcDb2dPolyline
        // + AcDb2dVertex append) has a schema to roundtrip against. Harmless for
        // any pre-existing AcDb2dPolyline this branch already read (M02 comment
        // above) -- these are additional fields, not a removed one.
        else if (AcDb2dPolyline* p2d = AcDb2dPolyline::cast(pEnt)) {
            arr << ",\"closed\":" << (p2d->isClosed() ? "true" : "false")
                << ",\"elevation\":" << p2d->elevation()
                << ",\"default_start_width\":" << p2d->defaultStartWidth()
                << ",\"default_end_width\":" << p2d->defaultEndWidth()
                << ",\"vertices\":[";
            AcDbObjectIterator* pVi = p2d->vertexIterator();
            bool vfirst = true;
            for (; pVi != nullptr && !pVi->done(); pVi->step()) {
                AcDb2dVertex* pV = nullptr;
                if (acdbOpenObject(pV, pVi->objectId(), AcDb::kForRead) == Acad::eOk) {
                    const AcGePoint3d vp = pV->position();
                    if (!vfirst) arr << ",";
                    vfirst = false;
                    arr << "{\"point\":[" << vp.x << "," << vp.y << "," << vp.z << "]"
                        << ",\"bulge\":" << pV->bulge()
                        << ",\"start_width\":" << pV->startWidth()
                        << ",\"end_width\":" << pV->endWidth() << "}";
                    pV->close();
                }
            }
            delete pVi;
            arr << "]";
        }
        else if (AcDb3dPolyline* p3d = AcDb3dPolyline::cast(pEnt)) {
            arr << ",\"closed\":" << (p3d->isClosed() ? "true" : "false")
                << ",\"vertices\":[";
            AcDbObjectIterator* pVi = p3d->vertexIterator();
            bool vfirst = true;
            for (; pVi != nullptr && !pVi->done(); pVi->step()) {
                AcDb3dPolylineVertex* pV = nullptr;
                if (acdbOpenObject(pV, pVi->objectId(), AcDb::kForRead) == Acad::eOk) {
                    const AcGePoint3d vp = pV->position();
                    if (!vfirst) arr << ",";
                    vfirst = false;
                    arr << "[" << vp.x << "," << vp.y << "," << vp.z << "]";
                    pV->close();
                }
            }
            delete pVi;
            arr << "]";
        }
        // w3-pmesh: AcDbPolygonMesh (M x N mesh grid) -- the SAME owned-
        // sub-entity vertexIterator() idiom AcDb2dPolyline/AcDb3dPolyline use
        // above, walking AcDbPolygonMeshVertex instead (both declared in
        // dbents.h, already included above -- no new #include needed).
        // m08g_handlers.inc's one-shot AcDbPolygonMesh ctor hardcodes
        // mClosed=nClosed=Adesk::kFalse (no "m_closed"/"n_closed" job field is
        // ever read there), so isMClosed()/isNClosed() are expected to always
        // read back false for this op -- live-verified 2026-07-02 w3-pmesh
        // re-cert.
        else if (AcDbPolygonMesh* pMesh = AcDbPolygonMesh::cast(pEnt)) {
            arr << ",\"m_size\":" << pMesh->mSize()
                << ",\"n_size\":" << pMesh->nSize()
                << ",\"m_closed\":" << (pMesh->isMClosed() ? "true" : "false")
                << ",\"n_closed\":" << (pMesh->isNClosed() ? "true" : "false")
                << ",\"vertices\":[";
            AcDbObjectIterator* pVi = pMesh->vertexIterator();
            bool vfirst = true;
            for (; pVi != nullptr && !pVi->done(); pVi->step()) {
                AcDbPolygonMeshVertex* pV = nullptr;
                if (acdbOpenObject(pV, pVi->objectId(), AcDb::kForRead) == Acad::eOk) {
                    const AcGePoint3d vp = pV->position();
                    if (!vfirst) arr << ",";
                    vfirst = false;
                    arr << "[" << vp.x << "," << vp.y << "," << vp.z << "]";
                    pV->close();
                }
            }
            delete pVi;
            arr << "]";
        }
        // w3-pfmesh: AcDbPolyFaceMesh -- unlike AcDbPolygonMesh's
        // vertexIterator() above (which yields ONLY AcDbPolygonMeshVertex
        // sub-entities), this class's vertexIterator() walks BOTH owned
        // sub-entity kinds m08g_handlers.inc's write.entity.polyfacemesh
        // handler appends, in append order: N AcDbPolyFaceMeshVertex objects
        // (one per "points"/"vertices" arg, same plain-position vertex shape
        // AcDbPolygonMeshVertex/AcDb3dPolylineVertex above already use)
        // followed by exactly 1 AcDbFaceRecord -- the handler NEVER reads a
        // "faces" job field at all, it hardcodes a single face referencing
        // vertex indices {1,2,3, len>=4?4:3} (a deterministic FUNCTION of
        // vertex count, not an independent arg -- live-verified 2026-07-02
        // w3-pfmesh re-cert). Both sub-entity kinds derive from AcDbVertex
        // (dbents.h) so are opened generically via that common base, then
        // discriminated with AcDbPolyFaceMeshVertex::cast()/AcDbFaceRecord::
        // cast() -- the SAME open-as-base-then-cast idiom this function's own
        // top-level entity loop already uses one level up (AcDbEntity* pEnt).
        else if (AcDbPolyFaceMesh* pFM = AcDbPolyFaceMesh::cast(pEnt)) {
            std::ostringstream vtx, fac;
            vtx.precision(kJsonDoublePrecision);
            fac.precision(kJsonDoublePrecision);
            bool vfirst = true, ffirst = true;
            AcDbObjectIterator* pVi = pFM->vertexIterator();
            for (; pVi != nullptr && !pVi->done(); pVi->step()) {
                AcDbVertex* pSub = nullptr;
                if (acdbOpenObject(pSub, pVi->objectId(), AcDb::kForRead) != Acad::eOk)
                    continue;
                if (AcDbPolyFaceMeshVertex* pV = AcDbPolyFaceMeshVertex::cast(pSub)) {
                    const AcGePoint3d vp = pV->position();
                    if (!vfirst) vtx << ",";
                    vfirst = false;
                    vtx << "[" << vp.x << "," << vp.y << "," << vp.z << "]";
                } else if (AcDbFaceRecord* pF = AcDbFaceRecord::cast(pSub)) {
                    if (!ffirst) fac << ",";
                    ffirst = false;
                    fac << "[";
                    for (Adesk::UInt16 fi = 0; fi < 4; ++fi) {
                        Adesk::Int16 vidx = 0;
                        pF->getVertexAt(fi, vidx);
                        if (fi) fac << ",";
                        fac << vidx;
                    }
                    fac << "]";
                }
                pSub->close();
            }
            delete pVi;
            arr << ",\"vertices\":[" << vtx.str() << "]"
                << ",\"faces\":[" << fac.str() << "]";
        }
        else if (AcDbHatch* pHatch = AcDbHatch::cast(pEnt)) {
            int loopCount = 0, vertexCount = 0;
            const std::string loopsJson = hatchLoopsJson(pHatch, loopCount, vertexCount);
            const AcGeVector3d hNormal = pHatch->normal();
            const bool isSolidFill = pHatch->isSolidFill() ? true : false;
            const bool isGradientHatch = pHatch->isGradient() ? true : false;
            const int patternDefinitionCount =
                (!isSolidFill && !isGradientHatch) ? pHatch->numPatternDefinitions() : 0;
            const std::string patternDefinitionsJson =
                (patternDefinitionCount > 0) ? hatchPatternDefinitionsJson(pHatch) : std::string();
            // a1-hatchread: pattern/style/gradient state -- previously only
            // pattern_name + loops surfaced; is_solid_fill/is_associative/
            // pattern_scale/pattern_angle/pattern_double/hatch_style/elevation/
            // normal were entirely unread (loops was also silently incomplete,
            // see hatchLoopsJson above).
            arr << ",\"pattern_name\":\"" << jsonEscape(acharToAscii(pHatch->patternName())) << "\""
                << ",\"pattern_type\":" << static_cast<int>(pHatch->patternType())
                // a1-hatchread cross-oracle cert (all 669 real hatches, exact
                // handle match against an independent LibreDWG+ezdxf DXF
                // parse): patternAngle() is radians, like every other
                // ObjectARX angle accessor this file already surfaces
                // (start/endAngle above) -- DXF group 52 stores the SAME
                // angle in degrees, so a raw compare against a DXF/ezdxf
                // reader will show a mismatch here that is a unit
                // convention, not a decode bug (math.degrees(this) == the
                // DXF value, verified exactly, 0 exceptions across 669).
                << ",\"pattern_angle\":" << pHatch->patternAngle()
                << ",\"pattern_scale\":" << pHatch->patternScale()
                << ",\"pattern_double\":" << (pHatch->patternDouble() ? "true" : "false")
                << ",\"hatch_style\":" << static_cast<int>(pHatch->hatchStyle())
                << ",\"is_solid_fill\":" << (isSolidFill ? "true" : "false")
                << ",\"is_associative\":" << (pHatch->associative() ? "true" : "false")
                << ",\"is_gradient\":" << (isGradientHatch ? "true" : "false")
                << ",\"elevation\":" << pHatch->elevation()
                << ",\"normal\":[" << hNormal.x << "," << hNormal.y << "," << hNormal.z << "]"
                << ",\"loop_count\":" << loopCount
                << ",\"loops\":" << loopsJson;
            if (patternDefinitionCount > 0)
                arr << ",\"pattern_definitions\":" << patternDefinitionsJson;
            if (isGradientHatch) {
                arr << ",\"gradient_name\":\"" << jsonEscape(acharToAscii(pHatch->gradientName())) << "\""
                    << ",\"gradient_type\":" << static_cast<int>(pHatch->gradientType())
                    << ",\"gradient_angle\":" << pHatch->gradientAngle();
            }
            // Associated boundary object ids (associative hatches only, via
            // getAssocObjIdsAt) are deliberately NOT resolved here: those ids
            // name the OTHER entities (e.g. a circle) this hatch tracks, which
            // is live-DB-state, not a property of the hatch itself -- same
            // reasoning T3a's dim_block_handle omission-from-geometry already
            // documents for dimensions (see op_roundtrip_probe.py). Noted as
            // an honest exclusion, not silently dropped.
            richCounters.hatchLoops += loopCount;
            richCounters.hatchLoopVertices += vertexCount;
        }
        // wA-cert: AcDbWipeout MUST be cast-checked BEFORE AcDbRasterImage below --
        // AcDbWipeout IS-A AcDbRasterImage (dbwipe.h), so AcDbRasterImage::cast()
        // would also succeed for a wipeout instance and swallow it into the plain-
        // image branch first if the order were reversed (same "more-derived-class-
        // first" rule this function already follows elsewhere, e.g. AcDbRotatedDimension
        // before the generic dimension handling below). Shares the same field set as
        // AcDbRasterImage (origin/u/v/image_size/clip boundary/source file) plus its
        // own frame() visibility flag.
        else if (AcDbWipeout* pWipe = AcDbWipeout::cast(pEnt)) {
            AcGePoint3d origin; AcGeVector3d uVec, vVec;
            pWipe->getOrientation(origin, uVec, vVec);
            const AcGeVector2d imgSize = pWipe->imageSize();
            std::string sourceFileName;
            const AcDbObjectId defId = pWipe->imageDefId();
            if (!defId.isNull()) {
                AcDbRasterImageDef* pDef = nullptr;
                if (acdbOpenObject(pDef, defId, AcDb::kForRead) == Acad::eOk) {
                    sourceFileName = wideToUtf8(std::wstring(pDef->sourceFileName()));
                    pDef->close();
                }
            }
            const AcGePoint2dArray& clipVerts = pWipe->clipBoundary();
            std::ostringstream clipArr;
            for (int ci = 0; ci < clipVerts.length(); ++ci) {
                if (ci) clipArr << ",";
                clipArr << "[" << clipVerts[ci].x << "," << clipVerts[ci].y << "]";
            }
            arr << ",\"kind\":\"wipeout\""
                << ",\"origin\":[" << origin.x << "," << origin.y << "," << origin.z << "]"
                << ",\"u_vector\":[" << uVec.x << "," << uVec.y << "," << uVec.z << "]"
                << ",\"v_vector\":[" << vVec.x << "," << vVec.y << "," << vVec.z << "]"
                << ",\"image_size\":[" << imgSize.x << "," << imgSize.y << "]"
                << ",\"clip_boundary_type\":" << static_cast<int>(pWipe->clipBoundaryType())
                << ",\"clip_boundary\":[" << clipArr.str() << "]"
                << ",\"source_file_name\":\"" << jsonEscape(sourceFileName) << "\""
                << ",\"frame_on\":" << (pWipe->frame() ? "true" : "false");
        }
        // wA-cert: plain AcDbRasterImage (write.entity.rasterimage). Same field
        // set as the AcDbWipeout branch above, minus frame_on (Wipeout-only).
        else if (AcDbRasterImage* pImg = AcDbRasterImage::cast(pEnt)) {
            AcGePoint3d origin; AcGeVector3d uVec, vVec;
            pImg->getOrientation(origin, uVec, vVec);
            const AcGeVector2d imgSize = pImg->imageSize();
            std::string sourceFileName;
            const AcDbObjectId defId = pImg->imageDefId();
            if (!defId.isNull()) {
                AcDbRasterImageDef* pDef = nullptr;
                if (acdbOpenObject(pDef, defId, AcDb::kForRead) == Acad::eOk) {
                    sourceFileName = wideToUtf8(std::wstring(pDef->sourceFileName()));
                    pDef->close();
                }
            }
            const AcGePoint2dArray& clipVerts = pImg->clipBoundary();
            std::ostringstream clipArr;
            for (int ci = 0; ci < clipVerts.length(); ++ci) {
                if (ci) clipArr << ",";
                clipArr << "[" << clipVerts[ci].x << "," << clipVerts[ci].y << "]";
            }
            arr << ",\"kind\":\"rasterimage\""
                << ",\"origin\":[" << origin.x << "," << origin.y << "," << origin.z << "]"
                << ",\"u_vector\":[" << uVec.x << "," << uVec.y << "," << uVec.z << "]"
                << ",\"v_vector\":[" << vVec.x << "," << vVec.y << "," << vVec.z << "]"
                << ",\"image_size\":[" << imgSize.x << "," << imgSize.y << "]"
                << ",\"clip_boundary_type\":" << static_cast<int>(pImg->clipBoundaryType())
                << ",\"clip_boundary\":[" << clipArr.str() << "]"
                << ",\"source_file_name\":\"" << jsonEscape(sourceFileName) << "\"";
        }
        // wA-cert: AcDbMPolygon -- derives directly from AcDbEntity (dbmpolygon.h),
        // no relation to AcDbHatch despite sharing the AcDbHatch::HatchPatternType
        // enum for setPattern() in the write handler, so ordering relative to the
        // AcDbHatch branch above is not load-bearing.
        else if (AcDbMPolygon* pMPoly = AcDbMPolygon::cast(pEnt)) {
            const int mpolyLoopCount = pMPoly->numMPolygonLoops();
            const double mpolyElevation = pMPoly->elevation();
            std::ostringstream loopsArr;
            for (int li = 0; li < mpolyLoopCount; ++li) {
                AcGePoint2dArray lverts; AcGeDoubleArray lbulges;
                pMPoly->getMPolygonLoopAt(li, lverts, lbulges);
                if (li) loopsArr << ",";
                loopsArr << "{\"index\":" << li << ",\"vertices\":[";
                for (int vi = 0; vi < lverts.length(); ++vi) {
                    if (vi) loopsArr << ",";
                    const double bulge = (vi < lbulges.length()) ? lbulges[vi] : 0.0;
                    // wA-cert: 3-element [x,y,elevation] point, matching
                    // AcDbHatch's hatchLoopsJson convention above (broadcasts
                    // the entity's own flat elevation() as every loop vertex's
                    // z) -- "loops" is a generic bare-passthrough in
                    // ir_builder.py's _geometry_from_native_entity, so this
                    // shape must match the sibling kind it mirrors.
                    loopsArr << "{\"point\":[" << lverts[vi].x << "," << lverts[vi].y << "," << mpolyElevation << "]"
                             << ",\"bulge\":" << bulge << "}";
                }
                loopsArr << "]}";
            }
            const AcGeVector3d mpolyNormal = pMPoly->normal();
            arr << ",\"kind\":\"mpolygon\""
                << ",\"pattern_name\":\"" << jsonEscape(acharToAscii(pMPoly->patternName())) << "\""
                << ",\"elevation\":" << pMPoly->elevation()
                << ",\"normal\":[" << mpolyNormal.x << "," << mpolyNormal.y << "," << mpolyNormal.z << "]"
                << ",\"loop_count\":" << mpolyLoopCount
                << ",\"loops\":[" << loopsArr.str() << "]";
        }
        // T3a: AcDbRotatedDimension -- the one dimension subtype write.entity.
        // dim.rotated actually creates. Derives directly from AcDbDimension
        // (NOT from AcDbAlignedDimension), so no other branch here casts to it.
        else if (AcDbRotatedDimension* pDim = AcDbRotatedDimension::cast(pEnt)) {
            const AcGePoint3d p1 = pDim->xLine1Point();
            const AcGePoint3d p2 = pDim->xLine2Point();
            const AcGePoint3d dl = pDim->dimLinePoint();
            double measurement = 0.0;
            const bool haveMeasurement = (pDim->measurement(measurement) == Acad::eOk);
            arr << ",\"xline1_point\":[" << p1.x << "," << p1.y << "," << p1.z << "]"
                << ",\"xline2_point\":[" << p2.x << "," << p2.y << "," << p2.z << "]"
                << ",\"dim_line_point\":[" << dl.x << "," << dl.y << "," << dl.z << "]"
                << ",\"rotation\":" << pDim->rotation();
            if (haveMeasurement)
                arr << ",\"measurement\":" << measurement;
            // dimBlockId resolved to its anonymous defining block's handle/name --
            // as cheap as the AcDbBlockReference branch's block_name lookup above
            // (one extra acdbOpenObject+getName()). Deliberately NOT surfaced by
            // ir_builder.py inside "geometry": the anonymous block name (*Dn) is a
            // live-DB-state-dependent counter, not derivable from an op's own args
            // alone, so it must never enter the P-gate's geometry fingerprint --
            // ir_builder.py's _entity_from_native lifts it as a top-level
            // dim_block_handle/dim_block_name field instead (see op_roundtrip_
            // probe.py's _expect_create_dimension for the full rationale).
            const AcDbObjectId dimBlockId = pDim->dimBlockId();
            if (!dimBlockId.isNull()) {
                arr << ",\"dim_block_handle\":\"" << jsonEscape(handleOfId(dimBlockId)) << "\"";
                std::string dimBlockName;
                AcDbBlockTableRecord* pDimDef = nullptr;
                if (acdbOpenObject(pDimDef, dimBlockId, AcDb::kForRead) == Acad::eOk) {
                    const ACHAR* nameRaw = nullptr;
                    if (pDimDef->getName(nameRaw) == Acad::eOk)
                        dimBlockName = acharToAscii(nameRaw);
                    pDimDef->close();
                }
                arr << ",\"dim_block_name\":\"" << jsonEscape(dimBlockName) << "\"";
            }
        }
        // T3a-batch2: AcDbAlignedDimension -- same 3-defining-points +
        // measurement shape as AcDbRotatedDimension above, minus "rotation":
        // an aligned dimension has no independent rotation arg -- its
        // dimension line is always parallel to the xLine1->xLine2 baseline by
        // definition (that is what "aligned" means). Derives directly from
        // AcDbDimension (NOT from AcDbRotatedDimension), so cast ordering
        // relative to it is not load-bearing.
        else if (AcDbAlignedDimension* pAl = AcDbAlignedDimension::cast(pEnt)) {
            const AcGePoint3d p1 = pAl->xLine1Point();
            const AcGePoint3d p2 = pAl->xLine2Point();
            const AcGePoint3d dl = pAl->dimLinePoint();
            double measurement = 0.0;
            const bool haveMeasurement = (pAl->measurement(measurement) == Acad::eOk);
            arr << ",\"xline1_point\":[" << p1.x << "," << p1.y << "," << p1.z << "]"
                << ",\"xline2_point\":[" << p2.x << "," << p2.y << "," << p2.z << "]"
                << ",\"dim_line_point\":[" << dl.x << "," << dl.y << "," << dl.z << "]";
            if (haveMeasurement)
                arr << ",\"measurement\":" << measurement;
            const AcDbObjectId dimBlockId = pAl->dimBlockId();
            if (!dimBlockId.isNull()) {
                arr << ",\"dim_block_handle\":\"" << jsonEscape(handleOfId(dimBlockId)) << "\"";
                std::string dimBlockName;
                AcDbBlockTableRecord* pDimDef = nullptr;
                if (acdbOpenObject(pDimDef, dimBlockId, AcDb::kForRead) == Acad::eOk) {
                    const ACHAR* nameRaw = nullptr;
                    if (pDimDef->getName(nameRaw) == Acad::eOk)
                        dimBlockName = acharToAscii(nameRaw);
                    pDimDef->close();
                }
                arr << ",\"dim_block_name\":\"" << jsonEscape(dimBlockName) << "\"";
            }
        }
        // T3a-batch2: AcDbRadialDimension -- center/chord_point are direct
        // ctor-arg echoes (no rotation-style re-anchoring degree of freedom
        // applies here); measurement is the dimensioned radius. leaderLength()
        // is ALSO extracted but live-verified (2026-07-02 re-cert) to be
        // AutoCAD's own recomputed value (reset to 0 when no leader is
        // actually needed at the current dimstyle's text/arrow size), not a
        // ctor-arg echo -- ir_builder.py surfaces it top-level, unasserted
        // (see op_roundtrip_probe.py's _expect_create_dimension_radial).
        else if (AcDbRadialDimension* pRad = AcDbRadialDimension::cast(pEnt)) {
            const AcGePoint3d ctr = pRad->center();
            const AcGePoint3d chord = pRad->chordPoint();
            double measurement = 0.0;
            const bool haveMeasurement = (pRad->measurement(measurement) == Acad::eOk);
            arr << ",\"center\":[" << ctr.x << "," << ctr.y << "," << ctr.z << "]"
                << ",\"chord_point\":[" << chord.x << "," << chord.y << "," << chord.z << "]"
                << ",\"leader_length\":" << pRad->leaderLength();
            if (haveMeasurement)
                arr << ",\"measurement\":" << measurement;
            const AcDbObjectId dimBlockId = pRad->dimBlockId();
            if (!dimBlockId.isNull()) {
                arr << ",\"dim_block_handle\":\"" << jsonEscape(handleOfId(dimBlockId)) << "\"";
                std::string dimBlockName;
                AcDbBlockTableRecord* pDimDef = nullptr;
                if (acdbOpenObject(pDimDef, dimBlockId, AcDb::kForRead) == Acad::eOk) {
                    const ACHAR* nameRaw = nullptr;
                    if (pDimDef->getName(nameRaw) == Acad::eOk)
                        dimBlockName = acharToAscii(nameRaw);
                    pDimDef->close();
                }
                arr << ",\"dim_block_name\":\"" << jsonEscape(dimBlockName) << "\"";
            }
        }
        // T3a-batch2: AcDbDiametricDimension -- chord_point/far_chord_point
        // are direct ctor-arg echoes; measurement is the dimensioned diameter.
        // leaderLength() has the identical live-discovered non-echo behavior
        // documented on the AcDbRadialDimension branch above.
        else if (AcDbDiametricDimension* pDia = AcDbDiametricDimension::cast(pEnt)) {
            const AcGePoint3d chord = pDia->chordPoint();
            const AcGePoint3d farChord = pDia->farChordPoint();
            double measurement = 0.0;
            const bool haveMeasurement = (pDia->measurement(measurement) == Acad::eOk);
            arr << ",\"chord_point\":[" << chord.x << "," << chord.y << "," << chord.z << "]"
                << ",\"far_chord_point\":[" << farChord.x << "," << farChord.y << "," << farChord.z << "]"
                << ",\"leader_length\":" << pDia->leaderLength();
            if (haveMeasurement)
                arr << ",\"measurement\":" << measurement;
            const AcDbObjectId dimBlockId = pDia->dimBlockId();
            if (!dimBlockId.isNull()) {
                arr << ",\"dim_block_handle\":\"" << jsonEscape(handleOfId(dimBlockId)) << "\"";
                std::string dimBlockName;
                AcDbBlockTableRecord* pDimDef = nullptr;
                if (acdbOpenObject(pDimDef, dimBlockId, AcDb::kForRead) == Acad::eOk) {
                    const ACHAR* nameRaw = nullptr;
                    if (pDimDef->getName(nameRaw) == Acad::eOk)
                        dimBlockName = acharToAscii(nameRaw);
                    pDimDef->close();
                }
                arr << ",\"dim_block_name\":\"" << jsonEscape(dimBlockName) << "\"";
            }
        }
        // T3a-batch3: AcDbOrdinateDimension -- defining_point/leader_end_point
        // are direct ctor-arg echoes; use_x_axis mirrors isUsingXAxis() (the
        // write handler passes its own use_x_axis arg straight to the ctor).
        // measurement is the dimensioned ordinate value, guarded by
        // measurement()'s own ErrorStatus like every other dimension branch
        // above. origin() is NOT a write.entity.dim.ordinate ctor arg (the
        // handler never calls setOrigin -- it stays whatever AutoCAD defaults
        // it to) so it is extracted for completeness but kept top-level, same
        // treatment as dim_block_handle/dim_block_name (see op_roundtrip_
        // probe.py's _expect_create_dimension_ordinate).
        else if (AcDbOrdinateDimension* pOrd = AcDbOrdinateDimension::cast(pEnt)) {
            const AcGePoint3d defPt = pOrd->definingPoint();
            const AcGePoint3d leadEnd = pOrd->leaderEndPoint();
            const AcGePoint3d origin = pOrd->origin();
            double measurement = 0.0;
            const bool haveMeasurement = (pOrd->measurement(measurement) == Acad::eOk);
            arr << ",\"defining_point\":[" << defPt.x << "," << defPt.y << "," << defPt.z << "]"
                << ",\"leader_end_point\":[" << leadEnd.x << "," << leadEnd.y << "," << leadEnd.z << "]"
                << ",\"use_x_axis\":" << (pOrd->isUsingXAxis() ? "true" : "false")
                << ",\"origin\":[" << origin.x << "," << origin.y << "," << origin.z << "]";
            if (haveMeasurement)
                arr << ",\"measurement\":" << measurement;
            const AcDbObjectId dimBlockId = pOrd->dimBlockId();
            if (!dimBlockId.isNull()) {
                arr << ",\"dim_block_handle\":\"" << jsonEscape(handleOfId(dimBlockId)) << "\"";
                std::string dimBlockName;
                AcDbBlockTableRecord* pDimDef = nullptr;
                if (acdbOpenObject(pDimDef, dimBlockId, AcDb::kForRead) == Acad::eOk) {
                    const ACHAR* nameRaw = nullptr;
                    if (pDimDef->getName(nameRaw) == Acad::eOk)
                        dimBlockName = acharToAscii(nameRaw);
                    pDimDef->close();
                }
                arr << ",\"dim_block_name\":\"" << jsonEscape(dimBlockName) << "\"";
            }
        }
        // w3-dimarc: AcDbArcDimension -- an arc-length dimension. Derives
        // directly from AcDbDimension (NOT from any dimension branch above),
        // so cast ordering relative to them is not load-bearing. centerPoint/
        // xLine1Point/xLine2Point are extracted under the same field names
        // (center/xline1_point/xline2_point) the rotated/aligned/ordinate
        // branches above already use, and are verbatim ctor-arg echoes
        // (live-verified). arcPoint is extracted too, but the ObjectARX
        // header documents it as "the point which the arc length dimension's
        // dimension arc passes through" -- the same placement-only semantic
        // AcDbRotatedDimension's dimLinePoint has (T3a) -- and it is NOT a
        // verbatim echo: LIVE-VERIFIED (2026-07-02 w3-dimarc re-cert, 3
        // roundtrips) that AutoCAD discards the input arcPoint's own position
        // and re-places it at exactly 1/3 of the xLine1Point->xLine2Point
        // angular span, same radius as xLine1Point from centerPoint (see
        // op_roundtrip_probe.py's _arc_dimension_arc_point for the derived
        // formula and its verified scope).
        else if (AcDbArcDimension* pArcDim = AcDbArcDimension::cast(pEnt)) {
            const AcGePoint3d ctr = pArcDim->centerPoint();
            const AcGePoint3d p1 = pArcDim->xLine1Point();
            const AcGePoint3d p2 = pArcDim->xLine2Point();
            const AcGePoint3d arcPt = pArcDim->arcPoint();
            double measurement = 0.0;
            const bool haveMeasurement = (pArcDim->measurement(measurement) == Acad::eOk);
            arr << ",\"center\":[" << ctr.x << "," << ctr.y << "," << ctr.z << "]"
                << ",\"xline1_point\":[" << p1.x << "," << p1.y << "," << p1.z << "]"
                << ",\"xline2_point\":[" << p2.x << "," << p2.y << "," << p2.z << "]"
                << ",\"arc_point\":[" << arcPt.x << "," << arcPt.y << "," << arcPt.z << "]";
            if (haveMeasurement)
                arr << ",\"measurement\":" << measurement;
            const AcDbObjectId dimBlockId = pArcDim->dimBlockId();
            if (!dimBlockId.isNull()) {
                arr << ",\"dim_block_handle\":\"" << jsonEscape(handleOfId(dimBlockId)) << "\"";
                std::string dimBlockName;
                AcDbBlockTableRecord* pDimDef = nullptr;
                if (acdbOpenObject(pDimDef, dimBlockId, AcDb::kForRead) == Acad::eOk) {
                    const ACHAR* nameRaw = nullptr;
                    if (pDimDef->getName(nameRaw) == Acad::eOk)
                        dimBlockName = acharToAscii(nameRaw);
                    pDimDef->close();
                }
                arr << ",\"dim_block_name\":\"" << jsonEscape(dimBlockName) << "\"";
            }
        }
        // w3-ang2: AcDb2LineAngularDimension -- a 2-line angular dimension.
        // Derives directly from AcDbDimension (NOT from AcDbArcDimension or
        // any other branch above), so cast ordering relative to them is not
        // load-bearing. xLine1Start/xLine1End/xLine2Start/xLine2End are
        // extracted under new field names (this op's ctor takes 4 line
        // endpoints, not the 2-point-per-line "xline1_point"/"xline2_point"
        // shape the rotated/aligned/arc dimension branches above use) and are
        // verbatim ctor-arg echoes (live-verified). arcPoint is extracted
        // too, but is NOT a verbatim echo: LIVE-VERIFIED (2026-07-02 w3-ang2
        // re-cert, 4 real accoreconsole roundtrips, 2 different apex points)
        // that AutoCAD re-anchors it to exactly 1/3 of whichever of the 2
        // lines' 4 apex-sectors the input arcPoint's angle selects, at the
        // SAME radius as the input arcPoint's own distance from the apex --
        // the same 1/3-of-span rule w3-dimarc found for AcDbArcDimension's
        // arcPoint, now confirmed on a structurally different class (see
        // op_roundtrip_probe.py's _angular2line_sector for the full formula
        // and its verified scope).
        else if (AcDb2LineAngularDimension* p2L = AcDb2LineAngularDimension::cast(pEnt)) {
            const AcGePoint3d l1s = p2L->xLine1Start();
            const AcGePoint3d l1e = p2L->xLine1End();
            const AcGePoint3d l2s = p2L->xLine2Start();
            const AcGePoint3d l2e = p2L->xLine2End();
            const AcGePoint3d arcPt = p2L->arcPoint();
            double measurement = 0.0;
            const bool haveMeasurement = (p2L->measurement(measurement) == Acad::eOk);
            arr << ",\"xline1_start\":[" << l1s.x << "," << l1s.y << "," << l1s.z << "]"
                << ",\"xline1_end\":[" << l1e.x << "," << l1e.y << "," << l1e.z << "]"
                << ",\"xline2_start\":[" << l2s.x << "," << l2s.y << "," << l2s.z << "]"
                << ",\"xline2_end\":[" << l2e.x << "," << l2e.y << "," << l2e.z << "]"
                << ",\"arc_point\":[" << arcPt.x << "," << arcPt.y << "," << arcPt.z << "]";
            if (haveMeasurement)
                arr << ",\"measurement\":" << measurement;
            const AcDbObjectId dimBlockId = p2L->dimBlockId();
            if (!dimBlockId.isNull()) {
                arr << ",\"dim_block_handle\":\"" << jsonEscape(handleOfId(dimBlockId)) << "\"";
                std::string dimBlockName;
                AcDbBlockTableRecord* pDimDef = nullptr;
                if (acdbOpenObject(pDimDef, dimBlockId, AcDb::kForRead) == Acad::eOk) {
                    const ACHAR* nameRaw = nullptr;
                    if (pDimDef->getName(nameRaw) == Acad::eOk)
                        dimBlockName = acharToAscii(nameRaw);
                    pDimDef->close();
                }
                arr << ",\"dim_block_name\":\"" << jsonEscape(dimBlockName) << "\"";
            }
        }
        // w3-ang3: AcDb3PointAngularDimension -- a 3-point angular dimension.
        // Derives directly from AcDbDimension (NOT from AcDbArcDimension or
        // AcDb2LineAngularDimension), so cast ordering relative to them is not
        // load-bearing. Its ctor (centerPoint, xLine1Point, xLine2Point,
        // arcPoint, dimText, dimStyle) is IDENTICAL in shape to
        // AcDbArcDimension's, so this branch reuses the SAME field names
        // (center/xline1_point/xline2_point/arc_point) the arc-dimension
        // branch above already uses. center/xLine1Point/xLine2Point are
        // verbatim ctor-arg echoes (live-verified). arcPoint is NOT a verbatim
        // echo, and its re-anchoring rule is a HYBRID of the two sibling
        // angular dims, NOT identical to either alone -- LIVE-VERIFIED
        // (2026-07-02 w3-ang3 cert, 3 real accoreconsole roundtrips against
        // tests/fixtures/native_sample.dwg, 3 different center/xLine-radius/
        // span combinations; the 2nd and 3rd DELIBERATELY gave the input
        // arcPoint a different distance from centerPoint than xLine1Point/
        // xLine2Point have, which is what exposed this): AutoCAD re-places
        // arcPoint's ANGLE at exactly 1/3 of the xLine1Point->xLine2Point
        // angular span (same direction-resolution rule w3-dimarc found for
        // AcDbArcDimension.arcPoint()), but preserves the RADIUS as the INPUT
        // arcPoint's OWN distance from centerPoint -- NOT xLine1Point's
        // distance from centerPoint (which is what AcDbArcDimension.
        // arcPoint() uses). The radius rule instead matches
        // AcDb2LineAngularDimension.arcPoint() (w3-ang2: preserves the input
        // arc_point's own distance from the apex). A naive "identical to
        // AcDbArcDimension" first attempt passed case 1 (input arcPoint's
        // radius == xLine1Point's radius there, 50 both, by construction) but
        // FAILED cases 2/3 (radius 18/25 vs xLine1's 30/40) until corrected to
        // this hybrid rule -- confirmed to float precision (max observed
        // error ~2e-15) once corrected. UNLIKE AcDbArcDimension (an
        // ARC-LENGTH dimension: measurement = radius * angular span),
        // measurement here is the plain ANGULAR width in radians -- the SAME
        // semantic AcDb2LineAngularDimension.measurement() has, and this part
        // WAS correct on the first attempt (see op_roundtrip_probe.py's
        // _angular3pt_measurement / _angular3pt_arc_point for the derived
        // formulas and verified scope, which mirrors _arc_dimension_
        // signed_span's own caveat: only verified for an input arc_point on
        // the same CCW-from-xLine1 side as the resolved short span, with that
        // span < 180 degrees).
        else if (AcDb3PointAngularDimension* p3pt = AcDb3PointAngularDimension::cast(pEnt)) {
            const AcGePoint3d ctr = p3pt->centerPoint();
            const AcGePoint3d p1 = p3pt->xLine1Point();
            const AcGePoint3d p2 = p3pt->xLine2Point();
            const AcGePoint3d arcPt = p3pt->arcPoint();
            double measurement = 0.0;
            const bool haveMeasurement = (p3pt->measurement(measurement) == Acad::eOk);
            arr << ",\"center\":[" << ctr.x << "," << ctr.y << "," << ctr.z << "]"
                << ",\"xline1_point\":[" << p1.x << "," << p1.y << "," << p1.z << "]"
                << ",\"xline2_point\":[" << p2.x << "," << p2.y << "," << p2.z << "]"
                << ",\"arc_point\":[" << arcPt.x << "," << arcPt.y << "," << arcPt.z << "]";
            if (haveMeasurement)
                arr << ",\"measurement\":" << measurement;
            const AcDbObjectId dimBlockId = p3pt->dimBlockId();
            if (!dimBlockId.isNull()) {
                arr << ",\"dim_block_handle\":\"" << jsonEscape(handleOfId(dimBlockId)) << "\"";
                std::string dimBlockName;
                AcDbBlockTableRecord* pDimDef = nullptr;
                if (acdbOpenObject(pDimDef, dimBlockId, AcDb::kForRead) == Acad::eOk) {
                    const ACHAR* nameRaw = nullptr;
                    if (pDimDef->getName(nameRaw) == Acad::eOk)
                        dimBlockName = acharToAscii(nameRaw);
                    pDimDef->close();
                }
                arr << ",\"dim_block_name\":\"" << jsonEscape(dimBlockName) << "\"";
            }
        }
        // w3-radl: AcDbRadialDimensionLarge -- a jogged (large) radius
        // dimension. Derives directly from AcDbDimension (NOT from
        // AcDbRadialDimension), so cast ordering relative to it is not
        // load-bearing (same non-issue w3-dimarc/w3-ang2/w3-ang3 documented
        // for their own AcDbDimension-direct classes). center/chordPoint are
        // the SAME "true center of the dimensioned arc" / "point on that arc"
        // pair AcDbRadialDimension already uses, so measurement (the
        // dimensioned radius) has the identical semantic: the center<->
        // chordPoint distance. overrideCenter/jogPoint/jogAngle are the 3
        // extra jog-symbol placement args write.entity.dim.radiallarge's ctor
        // takes (m08h_handlers.inc) with no plain-radial equivalent -- all 5
        // are extracted here; whether each survives as a verbatim ctor-arg
        // echo or gets AutoCAD-re-anchored (the arc_point pattern w3-dimarc/
        // w3-ang2/w3-ang3 all found on THEIR placement-only points) is
        // determined by op_roundtrip_probe.py's live re-cert, not assumed
        // here.
        else if (AcDbRadialDimensionLarge* pRadL = AcDbRadialDimensionLarge::cast(pEnt)) {
            const AcGePoint3d ctr = pRadL->center();
            const AcGePoint3d chord = pRadL->chordPoint();
            const AcGePoint3d ovrCtr = pRadL->overrideCenter();
            const AcGePoint3d jogPt = pRadL->jogPoint();
            double measurement = 0.0;
            const bool haveMeasurement = (pRadL->measurement(measurement) == Acad::eOk);
            arr << ",\"center\":[" << ctr.x << "," << ctr.y << "," << ctr.z << "]"
                << ",\"chord_point\":[" << chord.x << "," << chord.y << "," << chord.z << "]"
                << ",\"override_center\":[" << ovrCtr.x << "," << ovrCtr.y << "," << ovrCtr.z << "]"
                << ",\"jog_point\":[" << jogPt.x << "," << jogPt.y << "," << jogPt.z << "]"
                << ",\"jog_angle\":" << pRadL->jogAngle();
            if (haveMeasurement)
                arr << ",\"measurement\":" << measurement;
            const AcDbObjectId dimBlockId = pRadL->dimBlockId();
            if (!dimBlockId.isNull()) {
                arr << ",\"dim_block_handle\":\"" << jsonEscape(handleOfId(dimBlockId)) << "\"";
                std::string dimBlockName;
                AcDbBlockTableRecord* pDimDef = nullptr;
                if (acdbOpenObject(pDimDef, dimBlockId, AcDb::kForRead) == Acad::eOk) {
                    const ACHAR* nameRaw = nullptr;
                    if (pDimDef->getName(nameRaw) == Acad::eOk)
                        dimBlockName = acharToAscii(nameRaw);
                    pDimDef->close();
                }
                arr << ",\"dim_block_name\":\"" << jsonEscape(dimBlockName) << "\"";
            }
        }
        // T3a-batch3: AcDbLeader -- vertices are direct, args-derivable echoes
        // of write.entity.leader's vertices/points ctor-arg loop (appendVertex
        // per point, no transform). has_arrow_head/splined are deterministic
        // constants for THIS op (enableArrowHead()/setToStraightLeader() are
        // always called, unconditional on any arg) -- extracted and asserted
        // the same way T3a-batch2 asserted create_spline's always-False
        // "closed". Emitted as a plain [x,y,z]-array "vertices" (mirrors
        // AcDb2dPolyline/AcDb3dPolyline above, not AcDbPolyline's {point,bulge}
        // shape -- a leader vertex has no bulge concept), so it reuses
        // ir_builder.py's existing generic "vertices" lift with zero Python
        // change. annotation_handle (setAnnotationObjId) is deliberately NOT
        // extracted here: this batch's own valid-arg fixture never exercises
        // the optional annotation (an annotated leader appends a SECOND entity
        // -- the AcDbMText -- which is out of scope for a single-entity
        // geometry P-gate cert; see op_roundtrip_probe.py's
        // _expect_create_leader).
        else if (AcDbLeader* pLdr = AcDbLeader::cast(pEnt)) {
            const int nVerts = pLdr->numVertices();
            arr << ",\"vertices\":[";
            for (int vi = 0; vi < nVerts; ++vi) {
                const AcGePoint3d vp = pLdr->vertexAt(vi);
                if (vi != 0) arr << ",";
                arr << "[" << vp.x << "," << vp.y << "," << vp.z << "]";
            }
            arr << "]";
            arr << ",\"has_arrow_head\":" << (pLdr->hasArrowHead() ? "true" : "false")
                << ",\"splined\":" << (pLdr->isSplined() ? "true" : "false");
        }
        // w3-mleader: AcDbMLeader -- a multileader (leader line(s) + MText
        // content). Does NOT derive from AcDbLeader (a separate, newer,
        // AcDbEntity-direct class), so this branch's position in the chain is
        // not load-bearing. write.entity.mleader always builds exactly ONE
        // leader with exactly ONE leader line (a single addLeader/
        // addLeaderLine call each), so this branch flattens ALL leader-line
        // vertices across the whole entity (getLeaderLineIndexes's no-arg
        // overload -- defensive; expected to be exactly 1 line for this op)
        // into a single plain [x,y,z]-array "vertices" -- the SAME shape
        // AcDbLeader/AcDbMline above already use, so it reuses ir_builder.py's
        // existing generic "vertices" lift with zero Python change.
        // ir_builder.py's _NATIVE_CLASS_TO_DXF_KIND already had an
        // AcDbMLeader -> (MULTILEADER, leader) entry from an earlier batch,
        // so this op needed NO ir_builder.py change at all. mtext()/
        // contents()/textHeight() mirror the AcDbMText branch above ("text"/
        // "height") -- write.entity.mleader always calls setMText with a
        // non-null AcDbMText, so pMT should never be null in practice, but
        // mtext()'s own doc comment says it CAN return NULL ("if there is no
        // mtext content"), so this guards it rather than assuming. Per
        // mtext()'s doc comment ("returned mtext should be deleted"), pMT is
        // a plain heap copy (NOT database-resident) -- delete, not close().
        else if (AcDbMLeader* pML = AcDbMLeader::cast(pEnt)) {
            AcArray<int> lineIdx;
            pML->getLeaderLineIndexes(lineIdx);
            arr << ",\"vertices\":[";
            bool vfirst = true;
            for (int lj = 0; lj < lineIdx.length(); ++lj) {
                int nVerts = 0;
                pML->numVertices(lineIdx[lj], nVerts);
                for (int vi = 0; vi < nVerts; ++vi) {
                    AcGePoint3d vp;
                    if (pML->getVertex(lineIdx[lj], vi, vp) != Acad::eOk)
                        continue;
                    if (!vfirst) arr << ",";
                    vfirst = false;
                    arr << "[" << vp.x << "," << vp.y << "," << vp.z << "]";
                }
            }
            arr << "]";
            AcDbMText* pMT = pML->mtext();
            if (pMT != nullptr) {
                arr << ",\"text\":\"" << jsonEscape(acharToAscii(pMT->contents())) << "\""
                    << ",\"height\":" << pMT->textHeight();
                delete pMT;
            }
        }
        // w3-wbug: AcDbMline -- vertices are direct, args-derivable echoes of
        // write.entity.mline's points/vertices ctor-arg loop (appendSeg per
        // point, no transform). Emitted as a plain [x,y,z]-array "vertices"
        // (same shape as AcDbLeader above, no bulge concept), so it reuses ir_
        // builder.py's existing generic "vertices" lift with zero Python change
        // to that helper -- only a new _NATIVE_CLASS_TO_DXF_KIND entry is
        // needed. "closed" is a direct echo of write.entity.mline's own
        // "closed" arg (setClosedMline), mirroring AcDb2dPolyline/3dPolyline's
        // shape above. Does NOT derive from any other class this chain already
        // casts to (a direct AcDbEntity subclass), so this branch's position in
        // the chain is not load-bearing.
        else if (AcDbMline* pMl = AcDbMline::cast(pEnt)) {
            const int nVerts = pMl->numVertices();
            arr << ",\"vertices\":[";
            for (int vi = 0; vi < nVerts; ++vi) {
                const AcGePoint3d vp = pMl->vertexAt(vi);
                if (vi != 0) arr << ",";
                arr << "[" << vp.x << "," << vp.y << "," << vp.z << "]";
            }
            arr << "]";
            arr << ",\"closed\":" << (pMl->closedMline() ? "true" : "false");
        }
        // p8-simple2: AcDbFace/AcDbSolid/AcDbTrace (write.entity.face/
        // solid2d/trace, m08g_handlers.inc) are all flat 4-point entities
        // built from the same p0..p3 job keys -- grouped together here.
        // Neither derives from the other or from anything cast above (all
        // three: public AcDbEntity directly, dbents.h), so cast ordering is
        // not load-bearing, same as AcDbEllipse's note above. AcDbFace uses
        // its own getVertexAt()/isEdgeVisibleAt() accessors; AcDbSolid/
        // AcDbTrace share the identical getPointAt() signature. Points are
        // emitted verbatim from whatever the API returns post-persist (no
        // reordering here) -- ir_builder.py/op_roundtrip_probe.py assert the
        // MEASURED vertex convention (AutoCAD's own SOLID/TRACE "bow-tie"
        // 3rd/4th-vertex storage is a live question, not an assumption).
        else if (AcDbFace* pFace = AcDbFace::cast(pEnt)) {
            AcGePoint3d v0, v1, v2, v3;
            pFace->getVertexAt(0, v0);
            pFace->getVertexAt(1, v1);
            pFace->getVertexAt(2, v2);
            pFace->getVertexAt(3, v3);
            arr << ",\"p0\":[" << v0.x << "," << v0.y << "," << v0.z << "]"
                << ",\"p1\":[" << v1.x << "," << v1.y << "," << v1.z << "]"
                << ",\"p2\":[" << v2.x << "," << v2.y << "," << v2.z << "]"
                << ",\"p3\":[" << v3.x << "," << v3.y << "," << v3.z << "]";
            arr << ",\"edge_visibility\":[";
            for (int ei = 0; ei < 4; ++ei) {
                Adesk::Boolean vis = Adesk::kTrue;
                pFace->isEdgeVisibleAt(static_cast<Adesk::UInt16>(ei), vis);
                if (ei != 0) arr << ",";
                arr << (vis ? "true" : "false");
            }
            arr << "]";
        }
        else if (AcDbSolid* pSolid = AcDbSolid::cast(pEnt)) {
            AcGePoint3d v0, v1, v2, v3;
            pSolid->getPointAt(0, v0);
            pSolid->getPointAt(1, v1);
            pSolid->getPointAt(2, v2);
            pSolid->getPointAt(3, v3);
            arr << ",\"p0\":[" << v0.x << "," << v0.y << "," << v0.z << "]"
                << ",\"p1\":[" << v1.x << "," << v1.y << "," << v1.z << "]"
                << ",\"p2\":[" << v2.x << "," << v2.y << "," << v2.z << "]"
                << ",\"p3\":[" << v3.x << "," << v3.y << "," << v3.z << "]";
        }
        else if (AcDbTrace* pTrace = AcDbTrace::cast(pEnt)) {
            AcGePoint3d v0, v1, v2, v3;
            pTrace->getPointAt(0, v0);
            pTrace->getPointAt(1, v1);
            pTrace->getPointAt(2, v2);
            pTrace->getPointAt(3, v3);
            arr << ",\"p0\":[" << v0.x << "," << v0.y << "," << v0.z << "]"
                << ",\"p1\":[" << v1.x << "," << v1.y << "," << v1.z << "]"
                << ",\"p2\":[" << v2.x << "," << v2.y << "," << v2.z << "]"
                << ",\"p3\":[" << v3.x << "," << v3.y << "," << v3.z << "]";
        }
        // w3-simple1: AcDbPoint -- a single-point entity (dbents.h, already
        // included above, no new #include needed). "position" is a direct,
        // args-derivable echo of write.entity.point's own AcDbPoint(pos) ctor
        // arg (m08g_handlers.inc). Derives directly from AcDbEntity (not
        // AcDbCurve), so this branch's position in the chain is not
        // load-bearing.
        else if (AcDbPoint* pPt = AcDbPoint::cast(pEnt)) {
            const AcGePoint3d p = pPt->position();
            arr << ",\"position\":[" << p.x << "," << p.y << "," << p.z << "]";
        }
        // w3-simple1: AcDbRay -- a semi-infinite line (dbray.h, included
        // above). base_point is a direct echo of write.entity.ray's
        // setBasePoint(base) ctor arg; unit_dir is AutoCAD's OWN
        // normalization of the input "direction" vector (setUnitDir always
        // stores a UNIT vector, never the raw arg verbatim) -- ground truth
        // in op_roundtrip_probe.py must assert the normalized vector, not
        // args["direction"] as-is. Derives from AcDbCurve directly (not
        // AcDbLine/Arc/Circle/Ellipse/Spline), so this branch's position in
        // the chain is not load-bearing.
        else if (AcDbRay* pRay = AcDbRay::cast(pEnt)) {
            const AcGePoint3d b = pRay->basePoint();
            const AcGeVector3d d = pRay->unitDir();
            arr << ",\"base_point\":[" << b.x << "," << b.y << "," << b.z << "]"
                << ",\"unit_dir\":[" << d.x << "," << d.y << "," << d.z << "]";
        }
        // w3-simple1: AcDbXline -- an infinite construction line (dbxline.h,
        // included above). Same base_point/unit_dir shape and normalization
        // caveat as AcDbRay directly above (setUnitDir always stores a unit
        // vector).
        else if (AcDbXline* pXl = AcDbXline::cast(pEnt)) {
            const AcGePoint3d b = pXl->basePoint();
            const AcGeVector3d d = pXl->unitDir();
            arr << ",\"base_point\":[" << b.x << "," << b.y << "," << b.z << "]"
                << ",\"unit_dir\":[" << d.x << "," << d.y << "," << d.z << "]";
        }
        // wS-solids/S8: the 5 ASM/solids classes (WaveS0 finding G3) -- Tier A
        // fix, bbox only (see bboxJsonField above). ir_builder.py's dxf_name
        // kind table (not this cast chain) assigns the "solid3d"/"surface"/
        // "nurbsurface"/"region"/"body" geometry.kind discriminator, so
        // branch ORDER here only controls which extra fields get appended,
        // not classification -- except ORDER IS LOAD-BEARING for
        // AcDbNurbSurface vs AcDbSurface specifically: AcDbNurbSurface
        // DERIVES from AcDbSurface, so its branch must precede AcDbSurface's
        // or ::cast(pEnt) would match the base-class branch first for every
        // nurbsurface. AcDb3dSolid/AcDbRegion/AcDbBody are sibling
        // AcDbModelerGeometry subclasses (no inheritance overlap with each
        // other or with AcDbSurface), so their relative order is not
        // load-bearing.
        else if (AcDb3dSolid* pSol3d = AcDb3dSolid::cast(pEnt)) {
            arr << bboxJsonField(pSol3d);
        }
        else if (AcDbNurbSurface* pNurb = AcDbNurbSurface::cast(pEnt)) {
            arr << bboxJsonField(pNurb);
        }
        else if (AcDbSurface* pSurf = AcDbSurface::cast(pEnt)) {
            arr << bboxJsonField(pSurf);
        }
        else if (AcDbRegion* pReg = AcDbRegion::cast(pEnt)) {
            arr << bboxJsonField(pReg);
        }
        else if (AcDbBody* pBody = AcDbBody::cast(pEnt)) {
            arr << bboxJsonField(pBody);
        }

        arr << "}";
        pEnt->close();
    }

    delete pIt;
    arr << "]";
    extensionDictionaries << "]";
    extensionXrecords << "]";
    entitiesJson = arr.str();
    extensionDictionariesJson = extensionDictionaries.str();
    extensionXrecordsJson = extensionXrecords.str();
    return true;
}

// collectModelSpaceGraph: thin *Model_Space wrapper preserving the exact
// original signature/behavior. Opens *Model_Space, delegates the actual walk
// to collectEntitiesFromBlock (spaceLabel="model") above, closes it again.
static bool collectModelSpaceGraph(AcDbDatabase* pDb, int& total,
                                   std::string& entitiesJson,
                                   std::string& extensionDictionariesJson,
                                   std::string& extensionXrecordsJson,
                                   RichGraphCounters& richCounters)
{
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
        return false;
    AcDbBlockTableRecord* pMS = nullptr;
    if (pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForRead) != Acad::eOk) {
        pBT->close();
        return false;
    }
    pBT->close();

    const bool ok = collectEntitiesFromBlock(
        pMS, "model", total, entitiesJson, extensionDictionariesJson,
        extensionXrecordsJson, richCounters);
    pMS->close();
    return ok;
}

//----------------------------------------------------------------------------
// Rich database graph (M02): symbol tables, block table records, block
// definitions, layouts, xrefs, and the named-object dictionary, emitted as
// JSON fragments that the inspect.database.graph op splices alongside the
// model-space entities[]. All strings go through acharToAscii() (now UTF-8),
// so non-ASCII names survive. Every collector is a guarded pure read; a section
// that cannot open its table returns "[]" / "{}" and is marked accordingly in
// the coverage report (no-fake-success: present sections are real, skipped
// sections are named).
//----------------------------------------------------------------------------
static std::string handleOf(AcDbObject* pObj)
{
    if (pObj == nullptr)
        return std::string();
    AcDbHandle h;
    pObj->getAcDbHandle(h);
    ACHAR buf[40] = {};
    if (h.getIntoAsciiBuffer(buf, 40))
        return acharToAscii(buf);
    return std::string();
}

static std::string handleOfId(const AcDbObjectId& id)
{
    const AcDbHandle h = id.handle();
    ACHAR buf[40] = {};
    if (h.getIntoAsciiBuffer(buf, 40))
        return acharToAscii(buf);
    return std::string();
}

// Generic {handle,name} list for any symbol table (linetypes, text styles,
// dim styles, viewports, regapps). Uses the base AcDbSymbolTable iterator so
// it never needs a per-table typed API.
static std::string symbolTableRecordsJson(AcDbObjectId tableId, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbSymbolTable* pTable = nullptr;
    if (acdbOpenObject(pTable, tableId, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbSymbolTableIterator* pIt = nullptr;
    if (pTable->newIterator(pIt) != Acad::eOk) {
        pTable->close();
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbSymbolTableRecord* pRec = nullptr;
        if (pIt->getRecord(pRec, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pRec->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const std::string handle = handleOf(pRec);
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\"}";
            ++count;
            pRec->close();
        }
    }
    delete pIt;
    pTable->close();
    arr << "]";
    return arr.str();
}

// Resolve a linetype table record's NAME from its object id -- surfaces a
// layer's linetype as a human-readable string (matching the entity-level
// "linetype" field's shape) rather than a raw, engine-local object id. Empty
// string if the id is null/unresolvable -- never fabricated.
static std::string linetypeNameOf(AcDbObjectId ltId)
{
    if (ltId.isNull())
        return std::string();
    AcDbLinetypeTableRecord* pLtRec = nullptr;
    if (acdbOpenObject(pLtRec, ltId, AcDb::kForRead) != Acad::eOk)
        return std::string();
    const ACHAR* nameRaw = nullptr;
    std::string name;
    if (pLtRec->getName(nameRaw) == Acad::eOk)
        name = acharToAscii(nameRaw);
    pLtRec->close();
    return name;
}

// TABLES tier-2 (p9-tables2): {"x":..,"y":..,"z":..} emission for a 3-component
// point/vector record field -- the read-side mirror of jsonFindPoint3, same
// key shape so a record-diff's flat `actual.get(k) != v` compare (op_
// roundtrip_probe.py) works directly against the write-side args dict, no
// coordinate-shape translation needed on either side.
static std::string point3Json(double x, double y, double z)
{
    std::ostringstream s; s.precision(kJsonDoublePrecision);
    s << "{\"x\":" << x << ",\"y\":" << y << ",\"z\":" << z << "}";
    return s.str();
}

// TABLES tier-2 (p9-tables2): {"x":..,"y":..} emission for a 2-component
// point record field (AcGePoint2d) -- VIEW/VPORT's centerPoint()/
// lowerLeftCorner()/upperRightCorner() etc. Sibling of point3Json, same
// jsonFindPoint3-parse-side convention (a 2D caller just ignores the unused
// z out-param).
static std::string point2Json(double x, double y)
{
    std::ostringstream s; s.precision(kJsonDoublePrecision);
    s << "{\"x\":" << x << ",\"y\":" << y << "}";
    return s.str();
}

// Layer table with color + state flags (the highest-value symbol table; carries
// the non-ASCII names the D3 fix targets).
static std::string layersRichJson(AcDbDatabase* pDb, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbLayerTable* pLT = nullptr;
    if (pDb->getLayerTable(pLT, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbLayerTableIterator* pIt = nullptr;
    if (pLT->newIterator(pIt) != Acad::eOk) {
        pLT->close();
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbLayerTableRecord* pRec = nullptr;
        if (pIt->getRecord(pRec, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pRec->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const int colorIndex = pRec->color().colorIndex();
            const std::string linetypeName = linetypeNameOf(pRec->linetypeObjectId());
            const int lineweight = static_cast<int>(pRec->lineWeight());
            const std::string handle = handleOf(pRec);
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\""
                << ",\"color_index\":" << colorIndex
                << ",\"linetype\":\"" << jsonEscape(linetypeName) << "\""
                << ",\"lineweight\":" << lineweight
                << ",\"frozen\":" << (pRec->isFrozen() ? "true" : "false")
                << ",\"off\":" << (pRec->isOff() ? "true" : "false")
                << ",\"locked\":" << (pRec->isLocked() ? "true" : "false")
                << ",\"plottable\":" << (pRec->isPlottable() ? "true" : "false")
                << ",\"is_xref_dependent\":" << (pRec->isDependent() ? "true" : "false")
                << "}";
            ++count;
            pRec->close();
        }
    }
    delete pIt;
    pLT->close();
    arr << "]";
    return arr.str();
}

// DIMSTYLE table (w3-dimstyle + p1-dimvars): AcDbDimStyleTableRecord exposes
// ~78 dimension variables as individual get/set pairs (dbdimvar.h) -- p1-
// dimvars extended this from the original representative 10-field subset
// (dimtxt/dimasz/dimexe/dimexo/dimdec/dimscale/dimclrd/dimclre/dimclrt/
// dimse1) to the full honestly-settable surface (see DimStylePropertyArgs
// below); every remaining DIMVAR dbdimvar.h declares a get/set pair for is
// now wired here too. dimclrd/dimclre/dimclrt/dimtfillclr are surfaced as a
// plain colorIndex() int, matching the layer record's own "color_index"
// convention (AcCmColor's full RGB/book-color shape is out of scope for
// both tables today).
// p1-dimvars: resolve an ObjectId-typed DIMVAR (dimblk*/dimldrblk/dimltype/
// dimltex1/dimltex2/dimtxsty) back to its symbol name for JSON output.
// AcDbSymbolTableRecord::getName is shared by every symbol-table record
// kind (block/linetype/textstyle/...), so one generic open-as-base-class
// helper covers all 8 fields. A null id (never set -- the common case on a
// freshly-created dimstyle) is not an error; it emits an empty string,
// matching the DIMSTYLE dialog's own "none selected" UI.
static std::string dimStyleObjectIdName(const AcDbObjectId& id)
{
    if (id.isNull())
        return std::string();
    AcDbSymbolTableRecord* pRec = nullptr;
    if (acdbOpenObject(pRec, id, AcDb::kForRead) != Acad::eOk)
        return std::string();
    const ACHAR* nameRaw = nullptr;
    std::string name;
    if (pRec->getName(nameRaw) == Acad::eOk)
        name = acharToAscii(nameRaw);
    pRec->close();
    return name;
}

static std::string dimStylesRichJson(AcDbDatabase* pDb, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbDimStyleTable* pDST = nullptr;
    if (pDb->getDimStyleTable(pDST, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbDimStyleTableIterator* pIt = nullptr;
    if (pDST->newIterator(pIt) != Acad::eOk) {
        pDST->close();
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbDimStyleTableRecord* pRec = nullptr;
        if (pIt->getRecord(pRec, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pRec->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const std::string handle = handleOf(pRec);
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\""
                << ",\"dimtxt\":" << pRec->dimtxt()
                << ",\"dimasz\":" << pRec->dimasz()
                << ",\"dimexe\":" << pRec->dimexe()
                << ",\"dimexo\":" << pRec->dimexo()
                << ",\"dimdec\":" << pRec->dimdec()
                << ",\"dimscale\":" << pRec->dimscale()
                << ",\"dimclrd\":" << pRec->dimclrd().colorIndex()
                << ",\"dimclre\":" << pRec->dimclre().colorIndex()
                << ",\"dimclrt\":" << pRec->dimclrt().colorIndex()
                << ",\"dimse1\":" << (pRec->dimse1() ? "true" : "false")
                // p1-dimvars: full DIMVAR surface (dbdimvar.h) below,
                // matching applyDimStyleProperties/the job-args parse block
                // field-for-field.
                << ",\"dimaltf\":" << pRec->dimaltf()
                << ",\"dimaltrnd\":" << pRec->dimaltrnd()
                << ",\"dimcen\":" << pRec->dimcen()
                << ",\"dimdle\":" << pRec->dimdle()
                << ",\"dimdli\":" << pRec->dimdli()
                << ",\"dimgap\":" << pRec->dimgap()
                << ",\"dimjogang\":" << pRec->dimjogang()
                << ",\"dimlfac\":" << pRec->dimlfac()
                << ",\"dimrnd\":" << pRec->dimrnd()
                << ",\"dimtfac\":" << pRec->dimtfac()
                << ",\"dimtm\":" << pRec->dimtm()
                << ",\"dimtp\":" << pRec->dimtp()
                << ",\"dimtsz\":" << pRec->dimtsz()
                << ",\"dimtvp\":" << pRec->dimtvp()
                << ",\"dimfxlen\":" << pRec->dimfxlen()
                << ",\"dimmzf\":" << pRec->dimmzf()
                << ",\"dimaltmzf\":" << pRec->dimaltmzf()
                << ",\"dimadec\":" << pRec->dimadec()
                << ",\"dimaltd\":" << pRec->dimaltd()
                << ",\"dimalttd\":" << pRec->dimalttd()
                << ",\"dimalttz\":" << pRec->dimalttz()
                << ",\"dimaltu\":" << pRec->dimaltu()
                << ",\"dimaltz\":" << pRec->dimaltz()
                << ",\"dimarcsym\":" << pRec->dimarcsym()
                << ",\"dimatfit\":" << pRec->dimatfit()
                << ",\"dimaunit\":" << pRec->dimaunit()
                << ",\"dimazin\":" << pRec->dimazin()
                << ",\"dimfrac\":" << pRec->dimfrac()
                << ",\"dimjust\":" << pRec->dimjust()
                << ",\"dimlunit\":" << pRec->dimlunit()
                << ",\"dimtad\":" << pRec->dimtad()
                << ",\"dimtdec\":" << pRec->dimtdec()
                << ",\"dimtfill\":" << pRec->dimtfill()
                << ",\"dimtmove\":" << pRec->dimtmove()
                << ",\"dimtolj\":" << pRec->dimtolj()
                << ",\"dimtzin\":" << pRec->dimtzin()
                << ",\"dimzin\":" << pRec->dimzin()
                << ",\"dimalt\":" << (pRec->dimalt() ? "true" : "false")
                << ",\"dimlim\":" << (pRec->dimlim() ? "true" : "false")
                << ",\"dimsah\":" << (pRec->dimsah() ? "true" : "false")
                << ",\"dimsd1\":" << (pRec->dimsd1() ? "true" : "false")
                << ",\"dimsd2\":" << (pRec->dimsd2() ? "true" : "false")
                << ",\"dimse2\":" << (pRec->dimse2() ? "true" : "false")
                << ",\"dimsoxd\":" << (pRec->dimsoxd() ? "true" : "false")
                << ",\"dimtih\":" << (pRec->dimtih() ? "true" : "false")
                << ",\"dimtix\":" << (pRec->dimtix() ? "true" : "false")
                << ",\"dimtofl\":" << (pRec->dimtofl() ? "true" : "false")
                << ",\"dimtoh\":" << (pRec->dimtoh() ? "true" : "false")
                << ",\"dimtol\":" << (pRec->dimtol() ? "true" : "false")
                << ",\"dimupt\":" << (pRec->dimupt() ? "true" : "false")
                << ",\"dimfxlenon\":" << (pRec->dimfxlenOn() ? "true" : "false")
                << ",\"dimtxtdirection\":" << (pRec->dimtxtdirection() ? "true" : "false")
                << ",\"dimapost\":\"" << jsonEscape(acharToAscii(pRec->dimapost())) << "\""
                << ",\"dimpost\":\"" << jsonEscape(acharToAscii(pRec->dimpost())) << "\""
                << ",\"dimmzs\":\"" << jsonEscape(acharToAscii(pRec->dimmzs())) << "\""
                << ",\"dimaltmzs\":\"" << jsonEscape(acharToAscii(pRec->dimaltmzs())) << "\""
                << ",\"dimdsep\":\"" << jsonEscape(wideToUtf8(std::wstring(1, pRec->dimdsep()))) << "\""
                << ",\"dimtfillclr\":" << pRec->dimtfillclr().colorIndex()
                << ",\"dimlwd\":" << static_cast<int>(pRec->dimlwd())
                << ",\"dimlwe\":" << static_cast<int>(pRec->dimlwe())
                << ",\"dimblk\":\"" << jsonEscape(dimStyleObjectIdName(pRec->dimblk())) << "\""
                << ",\"dimblk1\":\"" << jsonEscape(dimStyleObjectIdName(pRec->dimblk1())) << "\""
                << ",\"dimblk2\":\"" << jsonEscape(dimStyleObjectIdName(pRec->dimblk2())) << "\""
                << ",\"dimldrblk\":\"" << jsonEscape(dimStyleObjectIdName(pRec->dimldrblk())) << "\""
                << ",\"dimltype\":\"" << jsonEscape(dimStyleObjectIdName(pRec->dimltype())) << "\""
                << ",\"dimltex1\":\"" << jsonEscape(dimStyleObjectIdName(pRec->dimltex1())) << "\""
                << ",\"dimltex2\":\"" << jsonEscape(dimStyleObjectIdName(pRec->dimltex2())) << "\""
                << ",\"dimtxsty\":\"" << jsonEscape(dimStyleObjectIdName(pRec->dimtxsty())) << "\""
                << "}";
            ++count;
            pRec->close();
        }
    }
    delete pIt;
    pDST->close();
    arr << "]";
    return arr.str();
}

// TABLES tier-2 (p9-tables2): UCS table -- AcDbUCSTableRecord's full settable
// surface (origin/x_axis/y_axis; see UcsPropertyArgs above for the scope
// note). Unlike layer/dimstyle, every field here is point/vector-valued, so
// this is the first rich extractor to use point3Json instead of a bare
// scalar `<<`.
static std::string ucsRichJson(AcDbDatabase* pDb, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbUCSTable* pUT = nullptr;
    if (pDb->getUCSTable(pUT, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbUCSTableIterator* pIt = nullptr;
    if (pUT->newIterator(pIt) != Acad::eOk) {
        pUT->close();
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbUCSTableRecord* pRec = nullptr;
        if (pIt->getRecord(pRec, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pRec->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const std::string handle = handleOf(pRec);
            const AcGePoint3d origin = pRec->origin();
            const AcGeVector3d xAxis = pRec->xAxis();
            const AcGeVector3d yAxis = pRec->yAxis();
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\""
                << ",\"origin\":" << point3Json(origin.x, origin.y, origin.z)
                << ",\"x_axis\":" << point3Json(xAxis.x, xAxis.y, xAxis.z)
                << ",\"y_axis\":" << point3Json(yAxis.x, yAxis.y, yAxis.z)
                << "}";
            ++count;
            pRec->close();
        }
    }
    delete pIt;
    pUT->close();
    arr << "]";
    return arr.str();
}

// TABLES tier-2 (p9-tables2): VIEW table -- the representative
// AcDbAbstractViewTableRecord "camera" subset ViewPropertyArgs above writes
// (center/height/width/target/view_direction/twist/lens_length/
// perspective/front-back clip). center is AcGePoint2d (point2Json); target/
// view_direction are AcGePoint3d/AcGeVector3d (point3Json).
static std::string viewsRichJson(AcDbDatabase* pDb, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbViewTable* pVT = nullptr;
    if (pDb->getViewTable(pVT, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbViewTableIterator* pIt = nullptr;
    if (pVT->newIterator(pIt) != Acad::eOk) {
        pVT->close();
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbViewTableRecord* pRec = nullptr;
        if (pIt->getRecord(pRec, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pRec->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const std::string handle = handleOf(pRec);
            const AcGePoint2d center = pRec->centerPoint();
            const AcGePoint3d target = pRec->target();
            const AcGeVector3d viewDir = pRec->viewDirection();
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\""
                << ",\"center\":" << point2Json(center.x, center.y)
                << ",\"height\":" << pRec->height()
                << ",\"width\":" << pRec->width()
                << ",\"target\":" << point3Json(target.x, target.y, target.z)
                << ",\"view_direction\":" << point3Json(viewDir.x, viewDir.y, viewDir.z)
                << ",\"twist\":" << pRec->viewTwist()
                << ",\"lens_length\":" << pRec->lensLength()
                << ",\"perspective_enabled\":" << (pRec->perspectiveEnabled() ? "true" : "false")
                << ",\"front_clip_distance\":" << pRec->frontClipDistance()
                << ",\"front_clip_enabled\":" << (pRec->frontClipEnabled() ? "true" : "false")
                << ",\"back_clip_distance\":" << pRec->backClipDistance()
                << ",\"back_clip_enabled\":" << (pRec->backClipEnabled() ? "true" : "false")
                << "}";
            ++count;
            pRec->close();
        }
    }
    delete pIt;
    pVT->close();
    arr << "]";
    return arr.str();
}

// TABLES tier-2 (p9-tables2): VPORT table -- the viewport-specific subset
// VportPropertyArgs (below, near upsertViewRecord) writes: the paperspace/
// screen rectangle (lower_left/upper_right) plus the SAME shared
// AcDbAbstractViewTableRecord center/height/width/target/view_direction/
// twist VIEW already certifies on this base class, plus a handful of
// viewport-only interactive-editing toggles (ucs_follow_mode/circle_sides/
// grid_enabled/snap_enabled/snap_angle/ucs_per_viewport).
//
// QUIRK (measured on the fixture, see build_log.md): AcDbViewportTable is
// the one symbol table where AutoCAD itself may legitimately store
// MULTIPLE records sharing the reserved name "*Active" (one per currently
// active tiled viewport pane) -- this extractor enumerates every record
// exactly as UCS/VIEW do above (one JSON element per record, own handle),
// so "*Active" duplication surfaces here as multiple array elements
// sharing the same name field. That is the correct, honest representation
// of what AutoCAD actually stores; record-diff callers must join on a
// caller-chosen unique name, never on the literal "*Active".
static std::string vportsRichJson(AcDbDatabase* pDb, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbViewportTable* pVPT = nullptr;
    if (pDb->getViewportTable(pVPT, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbViewportTableIterator* pIt = nullptr;
    if (pVPT->newIterator(pIt) != Acad::eOk) {
        pVPT->close();
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbViewportTableRecord* pRec = nullptr;
        if (pIt->getRecord(pRec, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pRec->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const std::string handle = handleOf(pRec);
            const AcGePoint2d lowerLeft = pRec->lowerLeftCorner();
            const AcGePoint2d upperRight = pRec->upperRightCorner();
            const AcGePoint2d center = pRec->centerPoint();
            const AcGePoint3d target = pRec->target();
            const AcGeVector3d viewDir = pRec->viewDirection();
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\""
                << ",\"lower_left\":" << point2Json(lowerLeft.x, lowerLeft.y)
                << ",\"upper_right\":" << point2Json(upperRight.x, upperRight.y)
                << ",\"center\":" << point2Json(center.x, center.y)
                << ",\"height\":" << pRec->height()
                << ",\"width\":" << pRec->width()
                << ",\"target\":" << point3Json(target.x, target.y, target.z)
                << ",\"view_direction\":" << point3Json(viewDir.x, viewDir.y, viewDir.z)
                << ",\"twist\":" << pRec->viewTwist()
                << ",\"ucs_follow_mode\":" << (pRec->ucsFollowMode() ? "true" : "false")
                << ",\"circle_sides\":" << static_cast<int>(pRec->circleSides())
                << ",\"grid_enabled\":" << (pRec->gridEnabled() ? "true" : "false")
                << ",\"snap_enabled\":" << (pRec->snapEnabled() ? "true" : "false")
                << ",\"snap_angle\":" << pRec->snapAngle()
                << ",\"ucs_per_viewport\":" << (pRec->isUcsSavedWithViewport() ? "true" : "false")
                << "}";
            ++count;
            pRec->close();
        }
    }
    delete pIt;
    pVPT->close();
    arr << "]";
    return arr.str();
}

// LINETYPE table with the D-class TABLES tier's representative field subset
// (w3-ltts): AcDbLinetypeTableRecord's own name/comments plus its dash
// pattern (numDashes()/dashLengthAt(i) -- positive=dash, negative=gap, 0=dot,
// per DXF/AutoCAD LINETYPE semantics). patternLength() is AutoCAD-maintained
// FROM the dash array rather than an independent write input, so it is out
// of scope here -- not part of write.linetype.create's own write contract
// (see LinetypePropertyArgs below). Complex-linetype shape/text embedding
// (shapeStyleAt/textAt et al.) is likewise out of scope: this covers simple
// dash-only patterns only, the same "representative, not exhaustive" scoping
// dimStylesRichJson already established for DIMVARs above.
static std::string linetypesRichJson(AcDbDatabase* pDb, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbLinetypeTable* pLTT = nullptr;
    if (pDb->getLinetypeTable(pLTT, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbLinetypeTableIterator* pIt = nullptr;
    if (pLTT->newIterator(pIt) != Acad::eOk) {
        pLTT->close();
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbLinetypeTableRecord* pRec = nullptr;
        if (pIt->getRecord(pRec, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pRec->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const ACHAR* commentsRaw = nullptr;
            std::string comments;
            if (pRec->comments(commentsRaw) == Acad::eOk)
                comments = acharToAscii(commentsRaw);
            const std::string handle = handleOf(pRec);
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\""
                << ",\"description\":\"" << jsonEscape(comments) << "\""
                << ",\"dash_lengths\":[";
            const int numDashes = pRec->numDashes();
            for (int di = 0; di < numDashes; ++di) {
                if (di > 0)
                    arr << ",";
                arr << pRec->dashLengthAt(di);
            }
            arr << "]}";
            ++count;
            pRec->close();
        }
    }
    delete pIt;
    pLTT->close();
    arr << "]";
    return arr.str();
}

// TEXTSTYLE table with the D-class TABLES tier's representative field subset
// (w3-ltts): AcDbTextStyleTableRecord's SHX/TTF font reference pair
// (fileName/bigFontFileName -- plain filename strings, not validated/
// resolved against disk at set time, unlike a LAYER's linetype which must
// resolve to an in-database object), textSize/xScale/obliquingAngle, and the
// two named boolean state flags AutoCAD exposes for a style (isShapeFile/
// isVertical -- there is no third; flagBits' other bits have no dedicated
// accessor). Field names on the wire (font_file/big_font_file/height/
// width_factor/oblique_angle) match schemas/dwg_graph_ir.v1.schema.json's
// pre-existing text_style_record $def, not the raw ObjectARX method names --
// height is the AutoCAD STYLE-dialog term for what the API calls textSize.
// priorSize()/setFont()'s Windows-typeface path are out of scope, the same
// "representative, not exhaustive" scoping dimStylesRichJson/
// linetypesRichJson already established above.
static std::string textStylesRichJson(AcDbDatabase* pDb, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbTextStyleTable* pTST = nullptr;
    if (pDb->getTextStyleTable(pTST, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbTextStyleTableIterator* pIt = nullptr;
    if (pTST->newIterator(pIt) != Acad::eOk) {
        pTST->close();
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbTextStyleTableRecord* pRec = nullptr;
        if (pIt->getRecord(pRec, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pRec->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const ACHAR* fontFileRaw = nullptr;
            std::string fontFile;
            if (pRec->fileName(fontFileRaw) == Acad::eOk)
                fontFile = acharToAscii(fontFileRaw);
            const ACHAR* bigFontRaw = nullptr;
            std::string bigFont;
            if (pRec->bigFontFileName(bigFontRaw) == Acad::eOk)
                bigFont = acharToAscii(bigFontRaw);
            const std::string handle = handleOf(pRec);
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\""
                << ",\"font_file\":\"" << jsonEscape(fontFile) << "\""
                << ",\"big_font_file\":\"" << jsonEscape(bigFont) << "\""
                << ",\"height\":" << pRec->textSize()
                << ",\"width_factor\":" << pRec->xScale()
                << ",\"oblique_angle\":" << pRec->obliquingAngle()
                << ",\"is_shape_file\":" << (pRec->isShapeFile() ? "true" : "false")
                << ",\"is_vertical\":" << (pRec->isVertical() ? "true" : "false")
                << "}";
            ++count;
            pRec->close();
        }
    }
    delete pIt;
    pTST->close();
    arr << "]";
    return arr.str();
}

// Block table records + the capturable block-definition projection.
// w3-blockdef: def geometry is now INLINED under
// block_definitions[].def_entities (the docs/DWG_GRAPH_IR_SPEC.md Section
// 4.3 "inlined" strategy) via the SAME collectEntitiesFromBlock per-entity
// extraction collectModelSpaceGraph uses -- NOT referenced from the top-level
// entities[] by owner_handle. The flat entities[] stays modelspace-only; its
// length is the golden-pinned truth-gate numerator
// (tests/golden/expected_counts.json's modelspace_total), so block-def
// contents must never be appended there.
static std::string blockTableRecordsJson(AcDbDatabase* pDb, int& btrCount,
                                         int& capturedBlockDefs,
                                         std::string& blockDefsJson)
{
    btrCount = 0;
    capturedBlockDefs = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    std::ostringstream defs; defs.precision(kJsonDoublePrecision);
    defs << "[";
    bool dfirst = true;

    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk) {
        blockDefsJson = "[]";
        return "[]";
    }
    AcDbBlockTableIterator* pIt = nullptr;
    if (pBT->newIterator(pIt) != Acad::eOk) {
        pBT->close();
        blockDefsJson = "[]";
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbBlockTableRecord* pBTR = nullptr;
        if (pIt->getRecord(pBTR, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pBTR->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const bool isLayout = pBTR->isLayout();
            const bool isAnon = pBTR->isAnonymous();
            const bool isXref = pBTR->isFromExternalReference();
            const bool emitBlockDef = !isLayout && !isXref;
            int entityCount = 0;
            std::string defEntitiesJson = "[]";
            if (emitBlockDef) {
                // Capture every non-layout, non-xref block definition. Named
                // defs preserve the legacy payload shape; anonymous *U###/*D###
                // defs gain only an additive "anonymous":true marker so
                // downstream rebuild can distinguish clone/remap paths later.
                // entityCount comes from this SAME walk, so it can never
                // disagree with len(def_entities). extension-dictionary/
                // xrecord content and richCounters aggregation for block-def-
                // owned entities are local/discarded here (v1 scope) -- the
                // top-level extension_dictionaries[]/xrecords[]/coverage.counts
                // stay modelspace-only, byte-identical to before this change.
                std::string defExtDicts, defExtXrecords;
                RichGraphCounters localCounters;
                collectEntitiesFromBlock(pBTR, "block", entityCount, defEntitiesJson,
                                         defExtDicts, defExtXrecords, localCounters);
            } else {
                AcDbBlockTableRecordIterator* pEIt = nullptr;
                if (pBTR->newIterator(pEIt) == Acad::eOk) {
                    for (pEIt->start(); !pEIt->done(); pEIt->step())
                        ++entityCount;
                    delete pEIt;
                }
            }
            const std::string handle = handleOf(pBTR);
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\""
                << ",\"is_layout\":" << (isLayout ? "true" : "false")
                << ",\"is_anonymous\":" << (isAnon ? "true" : "false")
                << ",\"is_xref\":" << (isXref ? "true" : "false")
                << ",\"entity_count\":" << entityCount << "}";
            ++btrCount;
            if (emitBlockDef) {
                ++capturedBlockDefs;
                if (!dfirst)
                    defs << ",";
                dfirst = false;
                defs << "{\"handle\":\"" << jsonEscape(handle) << "\""
                     << ",\"name\":\"" << jsonEscape(name) << "\"";
                if (isAnon)
                    defs << ",\"anonymous\":true";
                defs << ",\"entity_count\":" << entityCount
                     << ",\"def_entities\":" << defEntitiesJson << "}";
            }
            pBTR->close();
        }
    }
    delete pIt;
    pBT->close();
    arr << "]";
    defs << "]";
    blockDefsJson = defs.str();
    return arr.str();
}

static std::string layoutsRichJson(AcDbDatabase* pDb, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbDictionary* pLayouts = nullptr;
    if (pDb->getLayoutDictionary(pLayouts, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbDictionaryIterator* pIt = pLayouts->newIterator();
    for (; pIt != nullptr && !pIt->done(); pIt->next()) {
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, pIt->objectId(), AcDb::kForRead) == Acad::eOk) {
            AcDbLayout* pLayout = AcDbLayout::cast(pObj);
            if (pLayout != nullptr) {
                const ACHAR* nameRaw = nullptr;
                std::string name;
                if (pLayout->getLayoutName(nameRaw) == Acad::eOk)
                    name = acharToAscii(nameRaw);
                const int tab = pLayout->getTabOrder();
                const std::string btrHandle = handleOfId(pLayout->getBlockTableRecordId());
                const std::string handle = handleOf(pObj);
                if (!first)
                    arr << ",";
                first = false;
                arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                    << ",\"name\":\"" << jsonEscape(name) << "\""
                    << ",\"tab_order\":" << tab
                    << ",\"block_table_record_handle\":\"" << jsonEscape(btrHandle) << "\"}";
                ++count;
            }
            pObj->close();
        }
    }
    delete pIt;
    pLayouts->close();
    arr << "]";
    return arr.str();
}

static std::string xrefsRichJson(AcDbDatabase* pDb, int& count)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
        return "[]";
    AcDbBlockTableIterator* pIt = nullptr;
    if (pBT->newIterator(pIt) != Acad::eOk) {
        pBT->close();
        return "[]";
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbBlockTableRecord* pBTR = nullptr;
        if (pIt->getRecord(pBTR, AcDb::kForRead) == Acad::eOk) {
            if (pBTR->isFromExternalReference()) {
                const ACHAR* nameRaw = nullptr;
                std::string name;
                if (pBTR->getName(nameRaw) == Acad::eOk)
                    name = acharToAscii(nameRaw);
                const ACHAR* pathRaw = nullptr;
                std::string path;
                if (pBTR->pathName(pathRaw) == Acad::eOk && pathRaw != nullptr)
                    path = acharToAscii(pathRaw);
                const bool overlay = pBTR->isFromOverlayReference();
                const bool unloaded = pBTR->isUnloaded();
                const std::string handle = handleOf(pBTR);
                if (!first)
                    arr << ",";
                first = false;
                arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                    << ",\"name\":\"" << jsonEscape(name) << "\""
                    << ",\"path\":\"" << jsonEscape(path) << "\""
                    << ",\"is_overlay\":" << (overlay ? "true" : "false")
                    << ",\"status\":\"" << (unloaded ? "unloaded" : "resolved") << "\"}";
                ++count;
            }
            pBTR->close();
        }
    }
    delete pIt;
    pBT->close();
    arr << "]";
    return arr.str();
}

// Named object dictionary: emit its entries (key -> value handle) as ONE
// dictionary_record, and surface any XRECORD living directly under it. Deeper
// (nested-dictionary) xrecords + full resbuf decode are a documented partial.
static std::string namedObjectDictJson(AcDbDatabase* pDb, int& entryCount,
                                       int& xrecordCount, int& xrecordItemCount,
                                       std::string& xrecordsJson)
{
    entryCount = 0;
    xrecordCount = 0;
    xrecordItemCount = 0;
    std::ostringstream entries; entries.precision(kJsonDoublePrecision);
    entries << "[";
    bool efirst = true;
    std::ostringstream xrecs; xrecs.precision(kJsonDoublePrecision);
    xrecs << "[";
    bool xfirst = true;

    AcDbDictionary* pNOD = nullptr;
    if (pDb->getNamedObjectsDictionary(pNOD, AcDb::kForRead) != Acad::eOk) {
        xrecordsJson = "[]";
        return "[]";
    }
    const std::string nodHandle = handleOf(pNOD);
    AcDbDictionaryIterator* pIt = pNOD->newIterator();
    for (; pIt != nullptr && !pIt->done(); pIt->next()) {
        const ACHAR* keyRaw = pIt->name();
        const std::string key = (keyRaw != nullptr) ? acharToAscii(keyRaw) : std::string();
        const AcDbObjectId vid = pIt->objectId();
        const std::string vh = handleOfId(vid);
        if (!efirst)
            entries << ",";
        efirst = false;
        entries << "{\"key\":\"" << jsonEscape(key) << "\""
                << ",\"value_handle\":\"" << jsonEscape(vh) << "\"}";
        ++entryCount;
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, vid, AcDb::kForRead) == Acad::eOk) {
            if (AcDbXrecord::cast(pObj) != nullptr) {
                if (!xfirst)
                    xrecs << ",";
                xfirst = false;
                int itemCount = 0;
                xrecs << xrecordJson(AcDbXrecord::cast(pObj), vh, nodHandle, key, itemCount);
                xrecordItemCount += itemCount;
                ++xrecordCount;
            }
            pObj->close();
        }
    }
    delete pIt;
    pNOD->close();
    entries << "]";
    xrecs << "]";
    xrecordsJson = xrecs.str();
    return entries.str();
}

static std::string databaseMetaJson(AcDbDatabase* pDb)
{
    const AcGePoint3d ins = pDb->insbase();
    const AcGePoint3d emin = pDb->extmin();
    const AcGePoint3d emax = pDb->extmax();
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << "{\"insbase\":[" << ins.x << "," << ins.y << "," << ins.z << "]"
      << ",\"extents\":{\"extmin\":[" << emin.x << "," << emin.y << "," << emin.z << "]"
      << ",\"extmax\":[" << emax.x << "," << emax.y << "," << emax.z << "]}"
      << ",\"units\":{\"insunits\":" << static_cast<int>(pDb->insunits())
      << ",\"linear_units\":" << static_cast<int>(pDb->lunits())
      << ",\"angular_units\":" << static_cast<int>(pDb->aunits())
      << ",\"linear_precision\":" << static_cast<int>(pDb->luprec())
      << ",\"angular_precision\":" << static_cast<int>(pDb->auprec()) << "}}";
    return o.str();
}

// Compose the rich sections into a JSON fragment (no outer braces; the op branch
// splices it after entities[]). coverageJson reports per-section status so a
// consumer can tell implemented from partial/skipped without guessing.
static std::string collectDatabaseGraph(AcDbDatabase* pDb,
                                        const std::string& extensionDictionariesJson,
                                        const std::string& extensionXrecordsJson,
                                        const RichGraphCounters& richCounters,
                                        std::string& coverageJson)
{
    std::ostringstream sec; sec.precision(kJsonDoublePrecision);
    std::ostringstream present; present.precision(kJsonDoublePrecision);
    bool pfirst = true;
    auto addPresent = [&](const char* name) {
        if (!pfirst) present << ",";
        pfirst = false;
        present << "\"" << name << "\"";
    };

    sec << "\"database\":" << databaseMetaJson(pDb);
    addPresent("database");

    int layerCount = 0, ltCount = 0, tsCount = 0, dsCount = 0, vpCount = 0, raCount = 0, ucsCount = 0, viewCount = 0;
    const std::string layersJson = layersRichJson(pDb, layerCount);
    const std::string linetypesJson = linetypesRichJson(pDb, ltCount);
    const std::string textStylesJson = textStylesRichJson(pDb, tsCount);
    const std::string dimStylesJson = dimStylesRichJson(pDb, dsCount);
    const std::string appIdsJson = symbolTableRecordsJson(pDb->regAppTableId(), raCount);
    // p9-tables2: UCS/VIEW/VPORT tables, rich (record-diff capable) from day
    // one -- unlike app_ids/linetypes/text_styles above, which still use the
    // generic {handle,name}-only symbolTableRecordsJson pending their own
    // record-diff tickets.
    const std::string ucsJson = ucsRichJson(pDb, ucsCount);
    const std::string viewsJson = viewsRichJson(pDb, viewCount);
    const std::string viewportsJson = vportsRichJson(pDb, vpCount);
    sec << ",\"symbol_tables\":{\"layers\":" << layersJson
        << ",\"linetypes\":" << linetypesJson
        << ",\"text_styles\":" << textStylesJson
        << ",\"dim_styles\":" << dimStylesJson
        << ",\"viewports\":" << viewportsJson
        << ",\"app_ids\":" << appIdsJson
        << ",\"ucs\":" << ucsJson
        << ",\"views\":" << viewsJson << "}";
    addPresent("symbol_tables");

    int btrCount = 0, capturedBlockDefs = 0;
    std::string blockDefsJson;
    const std::string btrJson = blockTableRecordsJson(pDb, btrCount, capturedBlockDefs, blockDefsJson);
    sec << ",\"block_table_records\":" << btrJson
        << ",\"block_definitions\":" << blockDefsJson;
    addPresent("block_table_records");
    addPresent("block_definitions");

    int layoutCount = 0;
    sec << ",\"layouts\":" << layoutsRichJson(pDb, layoutCount);
    addPresent("layouts");

    int xrefCount = 0;
    sec << ",\"xrefs\":" << xrefsRichJson(pDb, xrefCount);
    addPresent("xrefs");

    int dictEntryCount = 0, xrecordCount = 0, xrecordItemCount = 0;
    std::string xrecordsJson;
    const std::string nodEntries = namedObjectDictJson(
        pDb, dictEntryCount, xrecordCount, xrecordItemCount, xrecordsJson);
    const std::string mergedXrecords = mergeJsonArrays(xrecordsJson, extensionXrecordsJson);
    sec << ",\"dictionaries\":[{\"name\":\"ACAD_NAMED_OBJECTS\",\"entries\":" << nodEntries << "}]"
        << ",\"extension_dictionaries\":" << extensionDictionariesJson
        << ",\"xrecords\":" << mergedXrecords;
    addPresent("dictionaries");
    addPresent("extension_dictionaries");
    addPresent("xrecords");
    addPresent("xdata");
    addPresent("hatch_loops");

    std::ostringstream cov; cov.precision(kJsonDoublePrecision);
    cov << "{\"layers\":\"implemented\""
        << ",\"linetypes\":\"implemented\""
        << ",\"text_styles\":\"implemented\""
        << ",\"dim_styles\":\"implemented\""
        << ",\"ucs\":\"implemented\""
        << ",\"views\":\"implemented\""
        << ",\"viewports\":\"implemented\""
        << ",\"block_table_records\":\"implemented\""
        << ",\"block_definitions\":\"implemented\""
        << ",\"layouts\":\"implemented\""
        << ",\"xrefs\":\"implemented\""
        << ",\"dictionaries\":\"implemented\""
        << ",\"xrecords\":\"implemented\""
        << ",\"xdata\":\"implemented\""
        << ",\"extension_dictionaries\":\"implemented\""
        << ",\"hatch_loops\":\"implemented\""
        << ",\"proxy_objects\":\"partial\""   // surfaced via entities[] dxf_name; deep decode = M03
        << ",\"counts\":{\"layers\":" << layerCount
        << ",\"linetypes\":" << ltCount
        << ",\"text_styles\":" << tsCount
        << ",\"dim_styles\":" << dsCount
        << ",\"viewports\":" << vpCount
        << ",\"app_ids\":" << raCount
        << ",\"ucs\":" << ucsCount
        << ",\"views\":" << viewCount
        << ",\"block_table_records\":" << btrCount
        << ",\"block_definitions\":" << capturedBlockDefs
        << ",\"layouts\":" << layoutCount
        << ",\"xrefs\":" << xrefCount
        << ",\"dictionary_entries\":" << dictEntryCount
        << ",\"xrecords\":" << (xrecordCount + richCounters.extensionXrecords)
        << ",\"xrecord_items\":" << (xrecordItemCount + richCounters.extensionXrecordItems)
        << ",\"xdata_blocks\":" << richCounters.xdataBlocks
        << ",\"xdata_items\":" << richCounters.xdataItems
        << ",\"extension_dictionaries\":" << richCounters.extensionDictionaries
        << ",\"extension_dictionary_entries\":" << richCounters.extensionDictionaryEntries
        << ",\"extension_xrecords\":" << richCounters.extensionXrecords
        << ",\"extension_xrecord_items\":" << richCounters.extensionXrecordItems
        << ",\"hatch_loops\":" << richCounters.hatchLoops
        << ",\"hatch_loop_vertices\":" << richCounters.hatchLoopVertices << "}"
        << ",\"sections_present\":[" << present.str() << "]"
        << ",\"sections_skipped\":[\"groups\",\"materials\",\"plot_settings\"]}";
    coverageJson = cov.str();
    return sec.str();
}

static Acad::ErrorStatus appendProbe(AcDbDatabase* pDb,
                                     const AcGePoint3d& center, double sz)
{
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
        return Acad::eInvalidInput;
    AcDbBlockTableRecord* pMS = nullptr;
    if (pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite) != Acad::eOk) {
        pBT->close();
        return Acad::eInvalidInput;
    }
    pBT->close();

    AcDbEntity* pProbe = nullptr;
    Acad::ErrorStatus es = ariadneCreateProbeEntity(
        pProbe,
        center.x,
        center.y,
        center.z,
        sz);
    if (es != Acad::eOk)
        return es;

    AcDbObjectId id;
    es = pMS->appendAcDbEntity(id, pProbe);
    pMS->close();
    if (es == Acad::eOk)
        pProbe->close();
    else
        delete pProbe;
    return es;
}

// M07B firing self-test helper: find the first AriadneProbe in model space (its
// objectId), used to FIRE the object overrule (acdbOpenObject) and the selection
// monitor (acedSSSetFirst) deterministically without any acedCommand reentrancy.
static bool findFirstProbe(AcDbDatabase* pDb, AcDbObjectId& outId)
{
    outId = AcDbObjectId::kNull;
    if (pDb == nullptr)
        return false;
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
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
    bool found = false;
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbEntity* pE = nullptr;
        if (pIt->getEntity(pE, AcDb::kForRead) == Acad::eOk) {
            if (ariadneIsProbeEntity(pE)) {
                outId = pE->objectId();
                found = true;
                pE->close();
                break;
            }
            pE->close();
        }
    }
    delete pIt;
    pMS->close();
    return found;
}

static Acad::ErrorStatus openAriadneDict(AcDbDatabase* pDb, AcDb::OpenMode mode,
                                         bool createIfMissing,
                                         AcDbDictionary*& pDict)
{
    pDict = nullptr;
    AcDbDictionary* pNamed = nullptr;
    Acad::ErrorStatus es = pDb->getNamedObjectsDictionary(
        pNamed,
        createIfMissing ? AcDb::kForWrite : AcDb::kForRead);
    if (es != Acad::eOk)
        return es;

    AcDbObject* pObj = nullptr;
    es = pNamed->getAt(kAriadneNativeDict, pObj, mode);
    if (es == Acad::eKeyNotFound && createIfMissing) {
        pDict = new AcDbDictionary();
        AcDbObjectId dictId;
        es = pNamed->setAt(kAriadneNativeDict, pDict, dictId);
        pNamed->close();
        return es;
    }
    pNamed->close();
    if (es != Acad::eOk)
        return es;

    pDict = AcDbDictionary::cast(pObj);
    if (pDict == nullptr) {
        if (pObj != nullptr)
            pObj->close();
        return Acad::eWrongObjectType;
    }
    return Acad::eOk;
}

static std::string acharToAscii(const ACHAR* text)
{
    // NOTE (M02): despite the historical name, this now emits UTF-8, not ASCII.
    // The rename to acharToUtf8 is a deferred cosmetic cleanup (call sites are
    // unchanged to keep this diff additive); behavior for pure-ASCII input is
    // byte-identical. See wideToUtf8 for the D3 fidelity rationale.
    if (text == nullptr)
        return std::string();
#ifdef _UNICODE
    const std::wstring wide(text);
    return wideToUtf8(wide);
#else
    return std::string(text);
#endif
}

static int gReactorCommandStarts = 0;
static int gReactorCommandEnds = 0;
static std::string gReactorLastCommand;

class AriadneEditorReactor : public AcEditorReactor
{
public:
    void commandWillStart(const ACHAR* cmdStr) override
    {
        ++gReactorCommandStarts;
        gReactorLastCommand = acharToAscii(cmdStr);
    }

    void commandEnded(const ACHAR* cmdStr) override
    {
        ++gReactorCommandEnds;
        gReactorLastCommand = acharToAscii(cmdStr);
    }
};

static AriadneEditorReactor* gAriadneEditorReactor = nullptr;

static bool enableEditorReactor(bool& created)
{
    created = false;
    if (gAriadneEditorReactor != nullptr)
        return true;
    AcEditor* pEditor = acedEditor;
    if (pEditor == nullptr)
        return false;
    gAriadneEditorReactor = new AriadneEditorReactor();
    pEditor->addReactor(gAriadneEditorReactor);
    created = true;
    return true;
}

static bool disableEditorReactor(bool& removed)
{
    removed = false;
    if (gAriadneEditorReactor == nullptr)
        return true;
    AcEditor* pEditor = acedEditor;
    if (pEditor != nullptr)
        pEditor->removeReactor(gAriadneEditorReactor);
    delete gAriadneEditorReactor;
    gAriadneEditorReactor = nullptr;
    removed = true;
    return true;
}

// --- Selection monitor (registration headless-safe; live pickfirst events attended-only) ---
// Mirrors AriadneEditorReactor: an AcEditorReactor subclass counting interactive
// selection changes via pickfirstModified() (aced.h:541). Under coreconsole acedEditor
// is null so enable returns false (honest gating); the callbacks only fire in a full
// editor. Registration is provable headless; live events require attended AutoCAD.
static int gSelMonPickfirstMods = 0;
static int gSelMonCommandEnds = 0;

class AriadneSelectionMonitor : public AcEditorReactor
{
public:
    void pickfirstModified() override { ++gSelMonPickfirstMods; }
    void commandEnded(const ACHAR* /*cmdStr*/) override { ++gSelMonCommandEnds; }
};

static AriadneSelectionMonitor* gAriadneSelectionMonitor = nullptr;

static bool enableSelectionMonitor(bool& created)
{
    created = false;
    if (gAriadneSelectionMonitor != nullptr)
        return true;
    AcEditor* pEditor = acedEditor;
    if (pEditor == nullptr)
        return false; // coreconsole: no interactive editor -> live events attended-only
    gAriadneSelectionMonitor = new AriadneSelectionMonitor();
    pEditor->addReactor(gAriadneSelectionMonitor);
    created = true;
    return true;
}

static bool disableSelectionMonitor(bool& removed)
{
    removed = false;
    if (gAriadneSelectionMonitor == nullptr)
        return true;
    AcEditor* pEditor = acedEditor;
    if (pEditor != nullptr)
        pEditor->removeReactor(gAriadneSelectionMonitor);
    delete gAriadneSelectionMonitor;
    gAriadneSelectionMonitor = nullptr;
    removed = true;
    return true;
}

static int gOverruleOpenCalls = 0;
static int gOverruleCloseCalls = 0;

class AriadneObjectOverrule : public AcDbObjectOverrule
{
public:
    bool isApplicable(const AcRxObject* pOverruledSubject) const override
    {
        const AcDbEntity* pEntity = AcDbEntity::cast(pOverruledSubject);
        return ariadneIsProbeEntity(pEntity);
    }

    Acad::ErrorStatus open(AcDbObject* pSubject, AcDb::OpenMode mode) override
    {
        ++gOverruleOpenCalls;
        return AcDbObjectOverrule::open(pSubject, mode);
    }

    Acad::ErrorStatus close(AcDbObject* pSubject) override
    {
        ++gOverruleCloseCalls;
        return AcDbObjectOverrule::close(pSubject);
    }
};

static AriadneObjectOverrule* gAriadneObjectOverrule = nullptr;

static AcRxClass* objectOverruleTargetClass()
{
    return AcDbEntity::desc();
}

static bool enableObjectOverrule(bool& created)
{
    created = false;
    if (gAriadneObjectOverrule != nullptr)
        return true;
    AcRxClass* pTargetClass = objectOverruleTargetClass();
    if (pTargetClass == nullptr)
        return false;

    AriadneObjectOverrule* pOverrule = new AriadneObjectOverrule();
    Acad::ErrorStatus es = AcRxOverrule::addOverrule(pTargetClass, pOverrule, true);
    if (es != Acad::eOk) {
        delete pOverrule;
        return false;
    }
    gAriadneObjectOverrule = pOverrule;
    AcRxOverrule::setIsOverruling(true);
    created = true;
    return true;
}

static bool disableObjectOverrule(bool& removed)
{
    removed = false;
    if (gAriadneObjectOverrule == nullptr)
        return true;
    AcRxClass* pTargetClass = objectOverruleTargetClass();
    if (pTargetClass != nullptr)
        AcRxOverrule::removeOverrule(pTargetClass, gAriadneObjectOverrule);
    delete gAriadneObjectOverrule;
    gAriadneObjectOverrule = nullptr;
    removed = true;
    return true;
}

static const char* dragStatusName(AcEdJig::DragStatus status)
{
    switch (status) {
    case AcEdJig::kModeless: return "kModeless";
    case AcEdJig::kNoChange: return "kNoChange";
    case AcEdJig::kCancel: return "kCancel";
    case AcEdJig::kOther: return "kOther";
    case AcEdJig::kNull: return "kNull";
    case AcEdJig::kNormal: return "kNormal";
    default: return "kKeywordOrUnknown";
    }
}

static const char* acedGetPointStatusName(int status)
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

class AriadneLineJig : public AcEdJig
{
public:
    explicit AriadneLineJig(const AcGePoint3d& base)
        : mLine(new AcDbLine(base, base)), mBase(base), mPoint(base)
    {
        setDispPrompt(_T("\nAriadne jig point: "));
        setUserInputControls((UserInputControls)(kAccept3dCoordinates |
                                                kNoZeroResponseAccepted |
                                                kNoNegativeResponseAccepted));
    }

    ~AriadneLineJig()
    {
        delete mLine;
        mLine = nullptr;
    }

    AcDbEntity* entity() const override
    {
        return mLine;
    }

    DragStatus sampler() override
    {
        AcGePoint3d point;
        DragStatus status = acquirePoint(point, mBase);
        if (status == kNormal) {
            if (point == mPoint)
                return kNoChange;
            mPoint = point;
        }
        return status;
    }

    Adesk::Boolean update() override
    {
        if (mLine != nullptr)
            mLine->setEndPoint(mPoint);
        return Adesk::kTrue;
    }

    AcGePoint3d point() const
    {
        return mPoint;
    }

private:
    AcDbLine* mLine;
    AcGePoint3d mBase;
    AcGePoint3d mPoint;
};

static std::string runLineJigProbe(const std::string& job,
                                   const std::string& jobHostMode)
{
    if (jobHostMode != "full_autocad") {
        return std::string()
            + "{\"host\":\"" + jsonEscape(jobHostMode) + "\","
            + "\"supported\":false,"
            + "\"interactive_editor_required\":true,"
            + "\"reason\":\"AcEdJig drag requires the full AutoCAD editor interaction loop\"}";
    }

    double x = 0.0, y = 0.0, z = 0.0;
    parsePointPayload(job, x, y, z);

    ads_point seed = { x, y, z };
    ads_point userPoint = { x, y, z };
    const int status = acedGetPoint(seed, _T("\nAriadne jig point: "), userPoint);
    if (status != RTNORM) {
        userPoint[0] = x;
        userPoint[1] = y;
        userPoint[2] = z;
    }

    const double ux = userPoint[0];
    const double uy = userPoint[1];
    const double uz = userPoint[2];
    const bool fallbackUsed = (status != RTNORM);

    return std::string()
        + "{\"host\":\"" + jsonEscape(jobHostMode) + "\","
        + "\"supported\":true,"
        + "\"jig\":\"AcEdJig\","
        + "\"drag_status\":" + std::to_string(status) + ","
        + "\"drag_status_name\":\"" + acedGetPointStatusName(status) + "\","
        + "\"input_method\":\"acedGetPoint\","
        + "\"fallback_used\":" + (fallbackUsed ? "true" : "false") + ","
        + "\"base\":[" + fmtNum(x) + "," + fmtNum(y) + "," + fmtNum(z) + "],"
        + "\"point\":[" + fmtNum(ux) + "," + fmtNum(uy) + "," + fmtNum(uz) + "]}";
}

static Acad::ErrorStatus ensureLayer(AcDbDatabase* pDb, const std::string& name,
                                     int colorIndex, bool& created)
{
    created = false;
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbLayerTable* pLT = nullptr;
    Acad::ErrorStatus es = pDb->getLayerTable(pLT, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    if (pLT->has(nameW.c_str())) {
        pLT->close();
        return Acad::eOk;
    }

    AcDbLayerTableRecord* pLayer = new AcDbLayerTableRecord();
    pLayer->setName(nameW.c_str());
    if (colorIndex > 0) {
        AcCmColor color;
        color.setColorIndex(static_cast<Adesk::UInt16>(colorIndex));
        pLayer->setColor(color);
    }

    AcDbObjectId id;
    es = pLT->add(id, pLayer);
    pLT->close();
    if (es == Acad::eOk) {
        created = true;
        pLayer->close();
    }
    else {
        delete pLayer;
    }
    return es;
}

// D-class TABLES tier (w3-tables): optional per-field overrides for a LAYER
// table record write. Each hasX flag says whether the caller actually
// supplied that field -- an absent field is left UNTOUCHED (see
// upsertLayerRecord), which is what lets a "change color_index only" write
// surface as exactly ONE modified field on re-extraction rather than a
// silent reset of every other property back to some default.
struct LayerPropertyArgs {
    bool hasColor = false;      int colorIndex = 0;
    bool hasLinetype = false;   std::string linetype;
    bool hasLineweight = false; int lineweight = 0;
    bool hasPlottable = false;  bool plottable = true;
    bool hasFrozen = false;     bool frozen = false;
    bool hasOff = false;        bool off = false;
    bool hasLocked = false;     bool locked = false;
};

// Apply every PRESENT field in props onto pLayer (open for write -- either a
// not-yet-added new record or an existing one reopened kForWrite). A
// requested linetype not already loaded into this database is loaded from
// the standard AutoCAD linetype definition file (acad.lin, resolved via the
// support-file search path -- the same mechanism the LINETYPE command's own
// "Load" option uses) and retried once; a name that still can't be resolved
// is reported in linetypeError rather than silently dropped (no-fake-success).
static void applyLayerProperties(AcDbLayerTableRecord* pLayer, AcDbDatabase* pDb,
                                 const LayerPropertyArgs& props, std::string& linetypeError)
{
    linetypeError.clear();
    if (props.hasColor && props.colorIndex > 0) {
        AcCmColor color;
        color.setColorIndex(static_cast<Adesk::UInt16>(props.colorIndex));
        pLayer->setColor(color);
    }
    if (props.hasLinetype && !props.linetype.empty()) {
        const std::wstring ltNameW = asciiToWide(props.linetype);
        AcDbObjectId ltId;
        bool resolved = false;
        AcDbLinetypeTable* pLTT = nullptr;
        if (pDb->getLinetypeTable(pLTT, AcDb::kForRead) == Acad::eOk) {
            resolved = (pLTT->getAt(ltNameW.c_str(), ltId) == Acad::eOk);
            pLTT->close();
        }
        if (!resolved) {
            pDb->loadLineTypeFile(ltNameW.c_str(), L"acad.lin");
            if (pDb->getLinetypeTable(pLTT, AcDb::kForRead) == Acad::eOk) {
                resolved = (pLTT->getAt(ltNameW.c_str(), ltId) == Acad::eOk);
                pLTT->close();
            }
        }
        if (resolved)
            pLayer->setLinetypeObjectId(ltId);
        else
            linetypeError = "linetype '" + props.linetype +
                             "' not found and could not be loaded from acad.lin";
    }
    if (props.hasLineweight)
        pLayer->setLineWeight(static_cast<AcDb::LineWeight>(props.lineweight));
    if (props.hasPlottable)
        pLayer->setIsPlottable(props.plottable);
    if (props.hasFrozen)
        pLayer->setIsFrozen(props.frozen);
    if (props.hasOff)
        pLayer->setIsOff(props.off);
    if (props.hasLocked)
        pLayer->setIsLocked(props.locked);
}

// D-class TABLES tier: create-or-update a named LAYER record (write.layer.
// create's handler). A brand-new layer defaults to color 7 when the caller
// didn't specify one -- matches ensureLayer's long-standing default, so
// existing create_layer callers with no color_index are unaffected. Updating
// an EXISTING layer applies ONLY the fields present in props; omitted fields
// are left exactly as they were. This is the upsert behavior ensureLayer
// intentionally does not have: ensureLayer's callers (appendLine/
// appendCircle) only ever need "make sure this layer exists" and a real
// no-op on an existing layer is correct for them, so ensureLayer stays
// untouched; this sibling is what write.layer.create uses so it can also
// update an already-existing layer's properties.
static Acad::ErrorStatus upsertLayerRecord(AcDbDatabase* pDb, const std::string& name,
                                           const LayerPropertyArgs& props, bool& created,
                                           std::string& linetypeError)
{
    created = false;
    linetypeError.clear();
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbLayerTable* pLT = nullptr;
    Acad::ErrorStatus es = pDb->getLayerTable(pLT, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    AcDbObjectId existingId;
    if (pLT->getAt(nameW.c_str(), existingId) == Acad::eOk) {
        pLT->close();
        AcDbLayerTableRecord* pLayer = nullptr;
        es = acdbOpenObject(pLayer, existingId, AcDb::kForWrite);
        if (es != Acad::eOk)
            return es;
        applyLayerProperties(pLayer, pDb, props, linetypeError);
        pLayer->close();
        return Acad::eOk;
    }

    AcDbLayerTableRecord* pLayer = new AcDbLayerTableRecord();
    pLayer->setName(nameW.c_str());
    LayerPropertyArgs createProps = props;
    if (!createProps.hasColor) {
        createProps.hasColor = true;
        createProps.colorIndex = 7;
    }
    applyLayerProperties(pLayer, pDb, createProps, linetypeError);

    AcDbObjectId id;
    es = pLT->add(id, pLayer);
    pLT->close();
    if (es == Acad::eOk) {
        created = true;
        pLayer->close();
    }
    else {
        delete pLayer;
    }
    return es;
}

// D-class TABLES tier (w3-dimstyle + p1-dimvars): optional per-field
// overrides for a DIMSTYLE table record write -- same hasX-flag upsert
// contract LayerPropertyArgs/applyLayerProperties established above (an
// absent field is left UNTOUCHED). p1-dimvars extended this from the
// original representative 10-DIMVAR subset to the full honestly-settable
// surface out of AcDbDimStyleTableRecord's ~78 dimension variables
// (dbdimvar.h) -- any field dbdimvar.h declares a get/set pair for and this
// struct does NOT carry is a measured, documented exclusion (build_log.md),
// not a silent gap (Rule 12).
struct DimStylePropertyArgs {
    bool hasDimtxt = false;   double dimtxt = 2.5;
    bool hasDimasz = false;   double dimasz = 2.5;
    bool hasDimexe = false;   double dimexe = 1.25;
    bool hasDimexo = false;   double dimexo = 0.625;
    bool hasDimdec = false;   int dimdec = 4;
    bool hasDimscale = false; double dimscale = 1.0;
    bool hasDimclrd = false;  int dimclrd = 0;
    bool hasDimclre = false;  int dimclre = 0;
    bool hasDimclrt = false;  int dimclrt = 0;
    bool hasDimse1 = false;   bool dimse1 = false;

    // p1-dimvars: the remaining ~68 DIMVARs (dbdimvar.h) -- same hasX-flag
    // upsert contract as the 10 fields above (an absent field is left
    // UNTOUCHED). Grouped by C++ type, same relative order as the header.

    // doubles
    bool hasDimaltf = false;   double dimaltf = 25.4;
    bool hasDimaltrnd = false; double dimaltrnd = 0.0;
    bool hasDimcen = false;    double dimcen = 0.09;
    bool hasDimdle = false;    double dimdle = 0.0;
    bool hasDimdli = false;    double dimdli = 0.38;
    bool hasDimgap = false;    double dimgap = 0.09;
    bool hasDimjogang = false; double dimjogang = 0.7853981633974483;
    bool hasDimlfac = false;   double dimlfac = 1.0;
    bool hasDimrnd = false;    double dimrnd = 0.0;
    bool hasDimtfac = false;   double dimtfac = 1.0;
    bool hasDimtm = false;     double dimtm = 0.0;
    bool hasDimtp = false;     double dimtp = 0.0;
    bool hasDimtsz = false;    double dimtsz = 0.0;
    bool hasDimtvp = false;    double dimtvp = 0.0;
    bool hasDimfxlen = false;  double dimfxlen = 1.0;
    bool hasDimmzf = false;    double dimmzf = 1.0;
    bool hasDimaltmzf = false; double dimaltmzf = 1.0;

    // ints
    bool hasDimadec = false;   int dimadec = 0;
    bool hasDimaltd = false;   int dimaltd = 2;
    bool hasDimalttd = false;  int dimalttd = 2;
    bool hasDimalttz = false;  int dimalttz = 0;
    bool hasDimaltu = false;   int dimaltu = 2;
    bool hasDimaltz = false;   int dimaltz = 0;
    bool hasDimarcsym = false; int dimarcsym = 0;
    bool hasDimatfit = false;  int dimatfit = 3;
    bool hasDimaunit = false;  int dimaunit = 0;
    bool hasDimazin = false;   int dimazin = 0;
    bool hasDimfrac = false;   int dimfrac = 0;
    bool hasDimjust = false;   int dimjust = 0;
    bool hasDimlunit = false;  int dimlunit = 2;
    bool hasDimtad = false;    int dimtad = 0;
    bool hasDimtdec = false;   int dimtdec = 4;
    bool hasDimtfill = false;  int dimtfill = 0;
    bool hasDimtmove = false;  int dimtmove = 0;
    bool hasDimtolj = false;   int dimtolj = 0;
    bool hasDimtzin = false;   int dimtzin = 0;
    bool hasDimzin = false;    int dimzin = 0;

    // bools
    bool hasDimalt = false;          bool dimalt = false;
    bool hasDimlim = false;          bool dimlim = false;
    bool hasDimsah = false;          bool dimsah = false;
    bool hasDimsd1 = false;          bool dimsd1 = false;
    bool hasDimsd2 = false;          bool dimsd2 = false;
    bool hasDimse2 = false;          bool dimse2 = false;
    bool hasDimsoxd = false;         bool dimsoxd = false;
    bool hasDimtih = false;          bool dimtih = false;
    bool hasDimtix = false;          bool dimtix = false;
    bool hasDimtofl = false;         bool dimtofl = false;
    bool hasDimtoh = false;          bool dimtoh = false;
    bool hasDimtol = false;          bool dimtol = false;
    bool hasDimupt = false;          bool dimupt = false;
    bool hasDimfxlenOn = false;      bool dimfxlenOn = false;
    bool hasDimtxtdirection = false; bool dimtxtdirection = false;

    // content strings -- empty is a legitimate "clear" value, unlike the
    // ObjectId-name fields below (mirrors AutoCAD's own dimapost/dimpost
    // semantics: an empty prefix/suffix is meaningful, not "unset")
    bool hasDimapost = false;  std::string dimapost;
    bool hasDimpost = false;   std::string dimpost;
    bool hasDimmzs = false;    std::string dimmzs;
    bool hasDimaltmzs = false; std::string dimaltmzs;

    // single-character decimal separator, carried as a 1-char UTF-8 string
    // on the wire (widened + truncated to its first ACHAR at apply time)
    bool hasDimdsep = false;   std::string dimdsep = ".";

    // AcCmColor (colorIndex()-only, same convention as dimclrd/e/t above)
    bool hasDimtfillclr = false; int dimtfillclr = 0;

    // AcDb::LineWeight (int on the wire, same convention as write.layer.
    // create's "lineweight")
    bool hasDimlwd = false; int dimlwd = 0;
    bool hasDimlwe = false; int dimlwe = 0;

    // ObjectId-typed: resolved by NAME (never a raw handle), empty/absent
    // leaves the field untouched -- mirrors LayerPropertyArgs.linetype's
    // "hasX && !empty()" gate exactly.
    bool hasDimblk = false;    std::string dimblk;
    bool hasDimblk1 = false;   std::string dimblk1;
    bool hasDimblk2 = false;   std::string dimblk2;
    bool hasDimldrblk = false; std::string dimldrblk;
    bool hasDimltype = false;  std::string dimltype;
    bool hasDimltex1 = false;  std::string dimltex1;
    bool hasDimltex2 = false;  std::string dimltex2;
    bool hasDimtxsty = false;  std::string dimtxsty;
};

// p1-dimvars: DIMLTYPE/DIMLTEX1/DIMLTEX2 name resolution -- a dimstyle's
// linetype fields need the SAME "not loaded yet -> try acad.lin once"
// fallback applyLayerProperties already established for a layer's linetype
// (see its own comment above). Duplicated here as a small dimstyle-local
// helper rather than reworking applyLayerProperties into a shared utility,
// to keep this wave's diff additive-only while other agents concurrently
// edit this same file.
static bool resolveDimStyleLinetype(AcDbDatabase* pDb, const std::string& name, AcDbObjectId& outId)
{
    const std::wstring nameW = asciiToWide(name);
    AcDbLinetypeTable* pLTT = nullptr;
    bool resolved = false;
    if (pDb->getLinetypeTable(pLTT, AcDb::kForRead) == Acad::eOk) {
        resolved = (pLTT->getAt(nameW.c_str(), outId) == Acad::eOk);
        pLTT->close();
    }
    if (!resolved) {
        pDb->loadLineTypeFile(nameW.c_str(), L"acad.lin");
        if (pDb->getLinetypeTable(pLTT, AcDb::kForRead) == Acad::eOk) {
            resolved = (pLTT->getAt(nameW.c_str(), outId) == Acad::eOk);
            pLTT->close();
        }
    }
    return resolved;
}

// p1-dimvars: DIMTXSTY name resolution. Unlike a linetype, there is no
// standard "load this text style from a support file" mechanism, so a name
// not already in the TEXTSTYLE table is a real failure, not a
// resolve-or-load-once retry ("Standard" always exists in every DWG, same
// as layer "0" and linetype "Continuous").
static bool resolveTextStyleByName(AcDbDatabase* pDb, const std::string& name, AcDbObjectId& outId)
{
    const std::wstring nameW = asciiToWide(name);
    AcDbTextStyleTable* pTST = nullptr;
    if (pDb->getTextStyleTable(pTST, AcDb::kForRead) != Acad::eOk)
        return false;
    const bool resolved = (pTST->getAt(nameW.c_str(), outId) == Acad::eOk);
    pTST->close();
    return resolved;
}

// Apply every PRESENT field in props onto pRec (open for write -- either a
// not-yet-added new record or an existing one reopened kForWrite). Mirrors
// applyLayerProperties' has-flag gating exactly. p1-dimvars: pDb (for the
// ObjectId-typed fields' table lookups) and resolutionError (accumulates
// every failed name resolution, semicolon-separated, mirroring
// applyLayerProperties' own linetypeError out-param -- no-fake-success: a
// name that can't be resolved is reported, never silently dropped) are new;
// the original 10 fields are untouched.
static void applyDimStyleProperties(AcDbDimStyleTableRecord* pRec, AcDbDatabase* pDb,
                                    const DimStylePropertyArgs& props, std::string& resolutionError)
{
    resolutionError.clear();
    if (props.hasDimtxt)
        pRec->setDimtxt(props.dimtxt);
    if (props.hasDimasz)
        pRec->setDimasz(props.dimasz);
    if (props.hasDimexe)
        pRec->setDimexe(props.dimexe);
    if (props.hasDimexo)
        pRec->setDimexo(props.dimexo);
    if (props.hasDimdec)
        pRec->setDimdec(props.dimdec);
    if (props.hasDimscale)
        pRec->setDimscale(props.dimscale);
    if (props.hasDimclrd) {
        AcCmColor c; c.setColorIndex(static_cast<Adesk::UInt16>(props.dimclrd));
        pRec->setDimclrd(c);
    }
    if (props.hasDimclre) {
        AcCmColor c; c.setColorIndex(static_cast<Adesk::UInt16>(props.dimclre));
        pRec->setDimclre(c);
    }
    if (props.hasDimclrt) {
        AcCmColor c; c.setColorIndex(static_cast<Adesk::UInt16>(props.dimclrt));
        pRec->setDimclrt(c);
    }
    if (props.hasDimse1)
        pRec->setDimse1(props.dimse1);

    // p1-dimvars: doubles
    if (props.hasDimaltf)    pRec->setDimaltf(props.dimaltf);
    if (props.hasDimaltrnd)  pRec->setDimaltrnd(props.dimaltrnd);
    if (props.hasDimcen)     pRec->setDimcen(props.dimcen);
    if (props.hasDimdle)     pRec->setDimdle(props.dimdle);
    if (props.hasDimdli)     pRec->setDimdli(props.dimdli);
    if (props.hasDimgap)     pRec->setDimgap(props.dimgap);
    if (props.hasDimjogang)  pRec->setDimjogang(props.dimjogang);
    if (props.hasDimlfac)    pRec->setDimlfac(props.dimlfac);
    if (props.hasDimrnd)     pRec->setDimrnd(props.dimrnd);
    if (props.hasDimtfac)    pRec->setDimtfac(props.dimtfac);
    if (props.hasDimtm)      pRec->setDimtm(props.dimtm);
    if (props.hasDimtp)      pRec->setDimtp(props.dimtp);
    if (props.hasDimtsz)     pRec->setDimtsz(props.dimtsz);
    if (props.hasDimtvp)     pRec->setDimtvp(props.dimtvp);
    if (props.hasDimfxlen)   pRec->setDimfxlen(props.dimfxlen);
    if (props.hasDimmzf)     pRec->setDimmzf(props.dimmzf);
    if (props.hasDimaltmzf)  pRec->setDimaltmzf(props.dimaltmzf);

    // p1-dimvars: ints
    if (props.hasDimadec)   pRec->setDimadec(props.dimadec);
    if (props.hasDimaltd)   pRec->setDimaltd(props.dimaltd);
    if (props.hasDimalttd)  pRec->setDimalttd(props.dimalttd);
    if (props.hasDimalttz)  pRec->setDimalttz(props.dimalttz);
    if (props.hasDimaltu)   pRec->setDimaltu(props.dimaltu);
    if (props.hasDimaltz)   pRec->setDimaltz(props.dimaltz);
    if (props.hasDimarcsym) pRec->setDimarcsym(props.dimarcsym);
    if (props.hasDimatfit)  pRec->setDimatfit(props.dimatfit);
    if (props.hasDimaunit)  pRec->setDimaunit(props.dimaunit);
    if (props.hasDimazin)   pRec->setDimazin(props.dimazin);
    if (props.hasDimfrac)   pRec->setDimfrac(props.dimfrac);
    if (props.hasDimjust)   pRec->setDimjust(props.dimjust);
    if (props.hasDimlunit)  pRec->setDimlunit(props.dimlunit);
    if (props.hasDimtad)    pRec->setDimtad(props.dimtad);
    if (props.hasDimtdec)   pRec->setDimtdec(props.dimtdec);
    if (props.hasDimtfill)  pRec->setDimtfill(props.dimtfill);
    if (props.hasDimtmove)  pRec->setDimtmove(props.dimtmove);
    if (props.hasDimtolj)   pRec->setDimtolj(props.dimtolj);
    if (props.hasDimtzin)   pRec->setDimtzin(props.dimtzin);
    if (props.hasDimzin)    pRec->setDimzin(props.dimzin);

    // p1-dimvars: bools
    if (props.hasDimalt)          pRec->setDimalt(props.dimalt);
    if (props.hasDimlim)          pRec->setDimlim(props.dimlim);
    if (props.hasDimsah)          pRec->setDimsah(props.dimsah);
    if (props.hasDimsd1)          pRec->setDimsd1(props.dimsd1);
    if (props.hasDimsd2)          pRec->setDimsd2(props.dimsd2);
    if (props.hasDimse2)          pRec->setDimse2(props.dimse2);
    if (props.hasDimsoxd)         pRec->setDimsoxd(props.dimsoxd);
    if (props.hasDimtih)          pRec->setDimtih(props.dimtih);
    if (props.hasDimtix)          pRec->setDimtix(props.dimtix);
    if (props.hasDimtofl)         pRec->setDimtofl(props.dimtofl);
    if (props.hasDimtoh)          pRec->setDimtoh(props.dimtoh);
    if (props.hasDimtol)          pRec->setDimtol(props.dimtol);
    if (props.hasDimupt)          pRec->setDimupt(props.dimupt);
    if (props.hasDimfxlenOn)      pRec->setDimfxlenOn(props.dimfxlenOn);
    if (props.hasDimtxtdirection) pRec->setDimtxtdirection(props.dimtxtdirection);

    // p1-dimvars: content strings (empty is a legitimate "clear" value)
    if (props.hasDimapost)  pRec->setDimapost(asciiToWide(props.dimapost).c_str());
    if (props.hasDimpost)   pRec->setDimpost(asciiToWide(props.dimpost).c_str());
    if (props.hasDimmzs)    pRec->setDimmzs(asciiToWide(props.dimmzs).c_str());
    if (props.hasDimaltmzs) pRec->setDimaltmzs(asciiToWide(props.dimaltmzs).c_str());

    // p1-dimvars: single-character decimal separator
    if (props.hasDimdsep && !props.dimdsep.empty()) {
        const std::wstring w = asciiToWide(props.dimdsep);
        if (!w.empty())
            pRec->setDimdsep(w[0]);
    }

    // p1-dimvars: fill color (AcCmColor, same colorIndex()-only convention
    // as dimclrd/e/t above)
    if (props.hasDimtfillclr) {
        AcCmColor c; c.setColorIndex(static_cast<Adesk::UInt16>(props.dimtfillclr));
        pRec->setDimtfillclr(c);
    }

    // p1-dimvars: lineweight enum (int on the wire, same convention as
    // write.layer.create's "lineweight")
    if (props.hasDimlwd)
        pRec->setDimlwd(static_cast<AcDb::LineWeight>(props.dimlwd));
    if (props.hasDimlwe)
        pRec->setDimlwe(static_cast<AcDb::LineWeight>(props.dimlwe));

    // p1-dimvars: ObjectId-typed fields resolved by NAME. Arrow-block fields
    // go through AcDbDimStyleTableRecord's own const-ACHAR*-name setter
    // overload (it resolves/auto-creates AutoCAD's reserved pseudo-names --
    // "_DOT", "_OPEN", etc -- the same mechanism the DIMSTYLE dialog's arrow
    // dropdown uses; a real user block name works the same way). Linetype
    // and text-style fields go through the two resolver helpers above.
    if (props.hasDimblk && !props.dimblk.empty()) {
        if (pRec->setDimblk(asciiToWide(props.dimblk).c_str()) != Acad::eOk)
            resolutionError += "dimblk '" + props.dimblk + "' could not be resolved; ";
    }
    if (props.hasDimblk1 && !props.dimblk1.empty()) {
        if (pRec->setDimblk1(asciiToWide(props.dimblk1).c_str()) != Acad::eOk)
            resolutionError += "dimblk1 '" + props.dimblk1 + "' could not be resolved; ";
    }
    if (props.hasDimblk2 && !props.dimblk2.empty()) {
        if (pRec->setDimblk2(asciiToWide(props.dimblk2).c_str()) != Acad::eOk)
            resolutionError += "dimblk2 '" + props.dimblk2 + "' could not be resolved; ";
    }
    if (props.hasDimldrblk && !props.dimldrblk.empty()) {
        if (pRec->setDimldrblk(asciiToWide(props.dimldrblk).c_str()) != Acad::eOk)
            resolutionError += "dimldrblk '" + props.dimldrblk + "' could not be resolved; ";
    }
    if (props.hasDimltype && !props.dimltype.empty()) {
        AcDbObjectId ltId;
        if (resolveDimStyleLinetype(pDb, props.dimltype, ltId))
            pRec->setDimltype(ltId);
        else
            resolutionError += "dimltype '" + props.dimltype + "' not found and could not be loaded from acad.lin; ";
    }
    if (props.hasDimltex1 && !props.dimltex1.empty()) {
        AcDbObjectId ltId;
        if (resolveDimStyleLinetype(pDb, props.dimltex1, ltId))
            pRec->setDimltex1(ltId);
        else
            resolutionError += "dimltex1 '" + props.dimltex1 + "' not found and could not be loaded from acad.lin; ";
    }
    if (props.hasDimltex2 && !props.dimltex2.empty()) {
        AcDbObjectId ltId;
        if (resolveDimStyleLinetype(pDb, props.dimltex2, ltId))
            pRec->setDimltex2(ltId);
        else
            resolutionError += "dimltex2 '" + props.dimltex2 + "' not found and could not be loaded from acad.lin; ";
    }
    if (props.hasDimtxsty && !props.dimtxsty.empty()) {
        AcDbObjectId tsId;
        if (resolveTextStyleByName(pDb, props.dimtxsty, tsId))
            pRec->setDimtxsty(tsId);
        else
            resolutionError += "dimtxsty '" + props.dimtxsty + "' not found in TEXTSTYLE table; ";
    }
}

// D-class TABLES tier: create-or-update a named DIMSTYLE record (write.
// dimstyle.create's handler) -- mirrors upsertLayerRecord's upsert contract
// exactly (see its own comment above): a brand-new dimstyle starts from
// AcDbDimStyleTableRecord's own ctor defaults (no forced non-default field
// the way a new layer forces color 7), and updating an EXISTING dimstyle
// applies ONLY the fields present in props; omitted fields are left exactly
// as they were.
static Acad::ErrorStatus upsertDimStyleRecord(AcDbDatabase* pDb, const std::string& name,
                                              const DimStylePropertyArgs& props, bool& created,
                                              std::string& resolutionError)
{
    created = false;
    resolutionError.clear();
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbDimStyleTable* pDST = nullptr;
    Acad::ErrorStatus es = pDb->getDimStyleTable(pDST, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    AcDbObjectId existingId;
    if (pDST->getAt(nameW.c_str(), existingId) == Acad::eOk) {
        pDST->close();
        AcDbDimStyleTableRecord* pRec = nullptr;
        es = acdbOpenObject(pRec, existingId, AcDb::kForWrite);
        if (es != Acad::eOk)
            return es;
        applyDimStyleProperties(pRec, pDb, props, resolutionError);
        pRec->close();
        return Acad::eOk;
    }

    AcDbDimStyleTableRecord* pRec = new AcDbDimStyleTableRecord();
    pRec->setName(nameW.c_str());
    applyDimStyleProperties(pRec, pDb, props, resolutionError);

    AcDbObjectId id;
    es = pDST->add(id, pRec);
    pDST->close();
    if (es == Acad::eOk) {
        created = true;
        pRec->close();
    }
    else {
        delete pRec;
    }
    return es;
}

// TABLES tier-2 (p9-tables2, D-class): optional per-field overrides for a UCS
// table record write -- same hasX-flag upsert contract LayerPropertyArgs/
// DimStylePropertyArgs established above (an absent field is left UNTOUCHED).
// AcDbUCSTableRecord (dbsymtb.h) is a small, complete class: origin/xAxis/
// yAxis are its ENTIRE settable surface (ucsBaseOrigin() is a PER-
// ORTHOGRAPHIC-VIEW auxiliary point, a different API shape, out of scope) --
// unlike DIMSTYLE's ~70-DIMVAR partial coverage, this is the FULL record.
struct UcsPropertyArgs {
    bool hasOrigin = false; double originX = 0.0, originY = 0.0, originZ = 0.0;
    bool hasXAxis = false;  double xAxisX = 1.0, xAxisY = 0.0, xAxisZ = 0.0;
    bool hasYAxis = false;  double yAxisX = 0.0, yAxisY = 1.0, yAxisZ = 0.0;
};

// Apply every PRESENT field in props onto pRec (open for write -- either a
// not-yet-added new record or an existing one reopened kForWrite). Mirrors
// applyLayerProperties/applyDimStyleProperties' has-flag gating exactly. No
// orthogonality/unit-length normalization is enforced here (the UCS command's
// own UI invariant, not a AcDbUCSTableRecord setter constraint) -- xAxis/
// yAxis are stored exactly as given.
static void applyUcsProperties(AcDbUCSTableRecord* pRec, const UcsPropertyArgs& props)
{
    if (props.hasOrigin)
        pRec->setOrigin(AcGePoint3d(props.originX, props.originY, props.originZ));
    if (props.hasXAxis)
        pRec->setXAxis(AcGeVector3d(props.xAxisX, props.xAxisY, props.xAxisZ));
    if (props.hasYAxis)
        pRec->setYAxis(AcGeVector3d(props.yAxisX, props.yAxisY, props.yAxisZ));
}

// TABLES tier-2: create-or-update a named UCS record (write.ucs.create's
// handler) -- mirrors upsertLayerRecord/upsertDimStyleRecord's upsert
// contract exactly: a brand-new UCS starts from AcDbUCSTableRecord's own ctor
// defaults (origin (0,0,0), xAxis (1,0,0), yAxis (0,1,0) -- WCS-aligned, no
// forced non-default field the way a new layer forces color 7), and updating
// an EXISTING UCS applies ONLY the fields present in props; omitted fields
// are left exactly as they were.
static Acad::ErrorStatus upsertUcsRecord(AcDbDatabase* pDb, const std::string& name,
                                         const UcsPropertyArgs& props, bool& created)
{
    created = false;
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbUCSTable* pUT = nullptr;
    Acad::ErrorStatus es = pDb->getUCSTable(pUT, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    AcDbObjectId existingId;
    if (pUT->getAt(nameW.c_str(), existingId) == Acad::eOk) {
        pUT->close();
        AcDbUCSTableRecord* pRec = nullptr;
        es = acdbOpenObject(pRec, existingId, AcDb::kForWrite);
        if (es != Acad::eOk)
            return es;
        applyUcsProperties(pRec, props);
        pRec->close();
        return Acad::eOk;
    }

    AcDbUCSTableRecord* pRec = new AcDbUCSTableRecord();
    pRec->setName(nameW.c_str());
    applyUcsProperties(pRec, props);

    AcDbObjectId id;
    es = pUT->add(id, pRec);
    pUT->close();
    if (es == Acad::eOk) {
        created = true;
        pRec->close();
    }
    else {
        delete pRec;
    }
    return es;
}

// TABLES tier-2 (p9-tables2, D-class): optional per-field overrides for a
// VIEW table record write -- same hasX-flag upsert contract established
// above. AcDbViewTableRecord derives from AcDbAbstractViewTableRecord (the
// shared base VPORT also derives from -- see ViewportPropertyArgs below);
// this is a REPRESENTATIVE subset of that base's "camera" properties
// (center/height/width/target/view_direction/twist/lens_length/
// perspective/front-back clip), covering one field of every underlying
// value shape (2D point, double, 3D point, 3D vector, bool). Excluded
// (honest gap, not wired here): isPaperspaceView, category_name/layer_state
// (strings), layout/camera/sun/visual_style/background (object-id refs to
// other DB objects), thumbnail/preview image, annotation scale, and the
// UCS-per-view association -- all a different value shape or a cross-table
// reference this pass does not resolve.
struct ViewPropertyArgs {
    bool hasCenter = false;    double centerX = 0.0, centerY = 0.0;
    bool hasHeight = false;    double height = 1.0;
    bool hasWidth = false;     double width = 1.0;
    bool hasTarget = false;    double targetX = 0.0, targetY = 0.0, targetZ = 0.0;
    bool hasViewDir = false;   double viewDirX = 0.0, viewDirY = 0.0, viewDirZ = 1.0;
    bool hasTwist = false;     double twist = 0.0;
    bool hasLensLength = false; double lensLength = 50.0;
    bool hasPerspective = false; bool perspective = false;
    bool hasFrontClipDist = false; double frontClipDist = 0.0;
    bool hasFrontClipOn = false;   bool frontClipOn = false;
    bool hasBackClipDist = false;  double backClipDist = 0.0;
    bool hasBackClipOn = false;    bool backClipOn = false;
};

// Apply every PRESENT field in props onto pRec (open for write -- either a
// not-yet-added new record or an existing one reopened kForWrite). Mirrors
// applyLayerProperties/applyUcsProperties' has-flag gating exactly.
static void applyViewProperties(AcDbViewTableRecord* pRec, const ViewPropertyArgs& props)
{
    if (props.hasCenter)
        pRec->setCenterPoint(AcGePoint2d(props.centerX, props.centerY));
    if (props.hasHeight)
        pRec->setHeight(props.height);
    if (props.hasWidth)
        pRec->setWidth(props.width);
    if (props.hasTarget)
        pRec->setTarget(AcGePoint3d(props.targetX, props.targetY, props.targetZ));
    if (props.hasViewDir)
        pRec->setViewDirection(AcGeVector3d(props.viewDirX, props.viewDirY, props.viewDirZ));
    if (props.hasTwist)
        pRec->setViewTwist(props.twist);
    if (props.hasLensLength)
        pRec->setLensLength(props.lensLength);
    if (props.hasPerspective)
        pRec->setPerspectiveEnabled(props.perspective);
    if (props.hasFrontClipDist)
        pRec->setFrontClipDistance(props.frontClipDist);
    if (props.hasFrontClipOn)
        pRec->setFrontClipEnabled(props.frontClipOn);
    if (props.hasBackClipDist)
        pRec->setBackClipDistance(props.backClipDist);
    if (props.hasBackClipOn)
        pRec->setBackClipEnabled(props.backClipOn);
}

// TABLES tier-2: create-or-update a named VIEW record (write.view.create's
// handler) -- mirrors upsertLayerRecord/upsertUcsRecord's upsert contract
// exactly: a brand-new VIEW starts from AcDbViewTableRecord's own ctor
// defaults, and updating an EXISTING VIEW applies ONLY the fields present in
// props; omitted fields are left exactly as they were.
static Acad::ErrorStatus upsertViewRecord(AcDbDatabase* pDb, const std::string& name,
                                          const ViewPropertyArgs& props, bool& created)
{
    created = false;
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbViewTable* pVT = nullptr;
    Acad::ErrorStatus es = pDb->getViewTable(pVT, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    AcDbObjectId existingId;
    if (pVT->getAt(nameW.c_str(), existingId) == Acad::eOk) {
        pVT->close();
        AcDbViewTableRecord* pRec = nullptr;
        es = acdbOpenObject(pRec, existingId, AcDb::kForWrite);
        if (es != Acad::eOk)
            return es;
        applyViewProperties(pRec, props);
        pRec->close();
        return Acad::eOk;
    }

    AcDbViewTableRecord* pRec = new AcDbViewTableRecord();
    pRec->setName(nameW.c_str());
    applyViewProperties(pRec, props);

    AcDbObjectId id;
    es = pVT->add(id, pRec);
    pVT->close();
    if (es == Acad::eOk) {
        created = true;
        pRec->close();
    }
    else {
        delete pRec;
    }
    return es;
}

// TABLES tier-2 (p9-tables2, D-class): optional per-field overrides for a
// VPORT table record write -- same hasX-flag upsert contract as UCS/VIEW
// above. AcDbViewportTableRecord derives from the SAME AcDbAbstractView
// TableRecord base as VIEW (center/height/width/target/view_direction/
// twist already proven certified there), plus a distinct viewport-only
// surface: the paperspace/screen rectangle (lowerLeftCorner/
// upperRightCorner) and a handful of interactive-editing toggles. This
// pass narrows to that viewport-specific set PLUS the shared base's
// center/height/width/target/view_direction/twist -- deliberately NOT
// lens_length/perspective/clip-plane fields, since those are camera
// fields already proven on this exact shared base class via VIEW;
// re-certifying them again here would not be a new signal. Excluded
// (honest gap, not wired here): number() (read-only slot index -- no
// setter exists in the header); fastZoomsEnabled (the header hardcodes
// the getter to `true` and the setter is a documented no-op stub -- not a
// real persisted property); iconEnabled/iconAtOrigin (UCS-icon display
// toggles); gridIncrements/snapBase/snapIncrements/snapPair/
// isometricSnapEnabled (additional snap/grid sub-parameters -- one
// representative field per concern was chosen instead of the full
// family, same "representative subset" philosophy VIEW already used);
// the newer "GridDisplay" sub-group (isGridBoundToLimits/isGridAdaptive/
// isGridSubdivisionRestricted/isGridFollow/gridMajor); background/
// visualStyle/sunId/lighting/tone-operator (object-id or complex nested
// refs to other DB objects, same category VIEW already excluded);
// gsView (a live AcGsView* rendering handle, not persisted DWG data); and
// the richer UCS query/set API (getUcs/setUcs/isUcsOrthographic/ucsName/
// elevation/setElevation/setUcsToWorld -- ucs_follow_mode/
// ucs_per_viewport below are the two simple flags this pass certifies
// instead).
//
// NOTE the asymmetric ObjectARX API for the last flag: the SETTER is
// setUcsPerViewport(bool) but the GETTER is isUcsSavedWithViewport() --
// different names for the same underlying property per the ObjectARX
// header (dbsymtb.h), not a typo on this pass's part.
struct VportPropertyArgs {
    bool hasLowerLeft = false;  double lowerLeftX = -1.0, lowerLeftY = -1.0;
    bool hasUpperRight = false; double upperRightX = 1.0, upperRightY = 1.0;
    bool hasCenter = false;     double centerX = 0.0, centerY = 0.0;
    bool hasHeight = false;     double height = 1.0;
    bool hasWidth = false;      double width = 1.0;
    bool hasTarget = false;     double targetX = 0.0, targetY = 0.0, targetZ = 0.0;
    bool hasViewDir = false;    double viewDirX = 0.0, viewDirY = 0.0, viewDirZ = 1.0;
    bool hasTwist = false;      double twist = 0.0;
    bool hasUcsFollow = false;  bool ucsFollow = false;
    bool hasCircleSides = false; int circleSides = 8;
    bool hasGridEnabled = false; bool gridEnabled = false;
    bool hasSnapEnabled = false; bool snapEnabled = false;
    bool hasSnapAngle = false;  double snapAngle = 0.0;
    bool hasUcsPerViewport = false; bool ucsPerViewport = false;
};

static void applyVportProperties(AcDbViewportTableRecord* pRec, const VportPropertyArgs& props)
{
    if (props.hasLowerLeft)
        pRec->setLowerLeftCorner(AcGePoint2d(props.lowerLeftX, props.lowerLeftY));
    if (props.hasUpperRight)
        pRec->setUpperRightCorner(AcGePoint2d(props.upperRightX, props.upperRightY));
    if (props.hasCenter)
        pRec->setCenterPoint(AcGePoint2d(props.centerX, props.centerY));
    if (props.hasHeight)
        pRec->setHeight(props.height);
    if (props.hasWidth)
        pRec->setWidth(props.width);
    if (props.hasTarget)
        pRec->setTarget(AcGePoint3d(props.targetX, props.targetY, props.targetZ));
    if (props.hasViewDir)
        pRec->setViewDirection(AcGeVector3d(props.viewDirX, props.viewDirY, props.viewDirZ));
    if (props.hasTwist)
        pRec->setViewTwist(props.twist);
    if (props.hasUcsFollow)
        pRec->setUcsFollowMode(props.ucsFollow);
    if (props.hasCircleSides)
        pRec->setCircleSides(static_cast<Adesk::UInt16>(props.circleSides));
    if (props.hasGridEnabled)
        pRec->setGridEnabled(props.gridEnabled);
    if (props.hasSnapEnabled)
        pRec->setSnapEnabled(props.snapEnabled);
    if (props.hasSnapAngle)
        pRec->setSnapAngle(props.snapAngle);
    if (props.hasUcsPerViewport)
        pRec->setUcsPerViewport(props.ucsPerViewport);
}

// TABLES tier-2: create-or-update a named VPORT record (write.vport.create's
// handler) -- mirrors upsertViewRecord's upsert contract exactly. QUIRK
// (measured, see build_log.md): AcDbViewportTable is the one symbol table
// where AutoCAD itself may store MULTIPLE records sharing the reserved
// name "*Active" (one per currently active tiled viewport pane) -- getAt
// on that literal name is therefore ambiguous BY DESIGN, not a bug in this
// upsert. Unaffected for any caller-chosen name other than "*Active"
// (ordinary uniqueness applies there, exactly like UCS/VIEW/LAYER);
// callers of this op should never literally name a record "*Active".
static Acad::ErrorStatus upsertVportRecord(AcDbDatabase* pDb, const std::string& name,
                                           const VportPropertyArgs& props, bool& created)
{
    created = false;
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbViewportTable* pVPT = nullptr;
    Acad::ErrorStatus es = pDb->getViewportTable(pVPT, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    AcDbObjectId existingId;
    if (pVPT->getAt(nameW.c_str(), existingId) == Acad::eOk) {
        pVPT->close();
        AcDbViewportTableRecord* pRec = nullptr;
        es = acdbOpenObject(pRec, existingId, AcDb::kForWrite);
        if (es != Acad::eOk)
            return es;
        applyVportProperties(pRec, props);
        // #128 WORKAROUND (measured via live op_roundtrip_probe run, see
        // build_log.md): setCircleSides() DOES take effect in-memory on an
        // existing record -- a same-process readback right after this call
        // confirms the new value -- but when circle_sides is the ONLY field
        // an update call touches, AutoCAD's own save pipeline does not treat
        // the record as modified and the change never reaches the saved DWG
        // (reproduced: circle_sides-only update round-trips back to the OLD
        // value; bundling it with any other AcDbAbstractViewTableRecord
        // field change, e.g. height, makes it stick). Re-asserting height to
        // its OWN current value is a true no-op that reliably forces that
        // recognition, without altering any caller-visible field.
        if (props.hasCircleSides)
            pRec->setHeight(pRec->height());
        pRec->close();
        return Acad::eOk;
    }

    AcDbViewportTableRecord* pRec = new AcDbViewportTableRecord();
    pRec->setName(nameW.c_str());
    applyVportProperties(pRec, props);

    AcDbObjectId id;
    es = pVPT->add(id, pRec);
    pVPT->close();
    if (es == Acad::eOk) {
        created = true;
        pRec->close();
    }
    else {
        delete pRec;
    }
    return es;
}

// D-class TABLES tier (w3-ltts): optional per-field overrides for a LINETYPE
// table record write -- same hasX-flag upsert contract LayerPropertyArgs/
// DimStylePropertyArgs established above (an absent field is left
// UNTOUCHED). Unlike every scalar field so far, the dash pattern is
// array-shaped: hasDashLengths gates the WHOLE array as one unit, since
// AutoCAD's own setNumDashes/setDashLengthAt pair has no concept of a
// partial per-index update (setNumDashes resizes/reallocates the array) --
// "change the dash pattern" always means "replace it in full". An explicit
// dash_lengths:[] on an update is indistinguishable from an omitted field
// (both read as hasDashLengths=false); mirrors write.layer.create's own
// empty-string-means-absent convention for "linetype" above. A real reset to
// zero dashes only ever needs a brand-new linetype (which already starts at
// the AcDbLinetypeTableRecord ctor's own zero-dash default), not an update,
// so this is not a functional gap in practice.
struct LinetypePropertyArgs {
    bool hasDescription = false;  std::string description;
    bool hasDashLengths = false;  std::vector<double> dashLengths;
};

// Apply every PRESENT field in props onto pRec (open for write -- either a
// not-yet-added new record or an existing one reopened kForWrite). Mirrors
// applyDimStyleProperties' has-flag gating exactly.
static void applyLinetypeProperties(AcDbLinetypeTableRecord* pRec, const LinetypePropertyArgs& props)
{
    if (props.hasDescription) {
        const std::wstring descW = asciiToWide(props.description);
        pRec->setComments(descW.c_str());
    }
    if (props.hasDashLengths) {
        pRec->setNumDashes(static_cast<int>(props.dashLengths.size()));
        for (size_t i = 0; i < props.dashLengths.size(); ++i)
            pRec->setDashLengthAt(static_cast<int>(i), props.dashLengths[i]);
    }
    else if (props.hasDescription) {
        // EMPIRICAL WORKAROUND (w3-ltts, live-verified via controlled A/B on
        // staged native_sample.dwg): AutoCAD's core LTYPE persistence ties
        // the comments field to the dash-pattern recompute trigger --
        // setComments() alone on an EXISTING (reopened kForWrite) record
        // does NOT survive save+reload unless setNumDashes/setDashLengthAt
        // is ALSO called in the same edit session, even to the record's own
        // unchanged values. A description-only update silently reverted
        // without this; re-applying the CURRENT pattern verbatim (a no-op on
        // the dash data itself, and harmless on a brand-new 0-dash record
        // too) makes it persist correctly. Only reached when the caller did
        // NOT also supply dash_lengths (that branch above already touches
        // the pattern for real).
        const int currentNumDashes = pRec->numDashes();
        std::vector<double> currentLengths;
        currentLengths.reserve(static_cast<size_t>(currentNumDashes));
        for (int i = 0; i < currentNumDashes; ++i)
            currentLengths.push_back(pRec->dashLengthAt(i));
        pRec->setNumDashes(currentNumDashes);
        for (int i = 0; i < currentNumDashes; ++i)
            pRec->setDashLengthAt(i, currentLengths[i]);
    }
}

// D-class TABLES tier: create-or-update a named LINETYPE record (write.
// linetype.create's handler) -- mirrors upsertDimStyleRecord's upsert
// contract exactly (see its own comment above): a brand-new linetype starts
// from AcDbLinetypeTableRecord's own ctor defaults (no forced non-default
// field), and updating an EXISTING linetype applies ONLY the fields present
// in props; omitted fields are left exactly as they were.
static Acad::ErrorStatus upsertLinetypeRecord(AcDbDatabase* pDb, const std::string& name,
                                              const LinetypePropertyArgs& props, bool& created)
{
    created = false;
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbLinetypeTable* pLTT = nullptr;
    Acad::ErrorStatus es = pDb->getLinetypeTable(pLTT, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    AcDbObjectId existingId;
    if (pLTT->getAt(nameW.c_str(), existingId) == Acad::eOk) {
        pLTT->close();
        AcDbLinetypeTableRecord* pRec = nullptr;
        es = acdbOpenObject(pRec, existingId, AcDb::kForWrite);
        if (es != Acad::eOk)
            return es;
        applyLinetypeProperties(pRec, props);
        pRec->close();
        return Acad::eOk;
    }

    AcDbLinetypeTableRecord* pRec = new AcDbLinetypeTableRecord();
    pRec->setName(nameW.c_str());
    applyLinetypeProperties(pRec, props);

    AcDbObjectId id;
    es = pLTT->add(id, pRec);
    pLTT->close();
    if (es == Acad::eOk) {
        created = true;
        pRec->close();
    }
    else {
        delete pRec;
    }
    return es;
}

// D-class TABLES tier (w3-ltts): optional per-field overrides for a
// TEXTSTYLE table record write -- same hasX-flag upsert contract every
// sibling struct above established (an absent field is left UNTOUCHED).
// fontFile/bigFontFile are plain filename strings AutoCAD stores verbatim on
// the record (unlike a LAYER's linetype reference, these are NOT resolved
// against an in-database object or validated against disk at set time --
// see AcDbTextStyleTableRecord::setFileName's own contract). Member names
// here match the wire/JSON vocabulary (font_file/big_font_file/height, per
// schemas/dwg_graph_ir.v1.schema.json's text_style_record $def), not the
// raw ObjectARX method names (fileName/bigFontFileName/textSize) -- the
// setter calls below still use the real API.
struct TextStylePropertyArgs {
    bool hasFontFile = false;    std::string fontFile;
    bool hasBigFontFile = false; std::string bigFontFile;
    bool hasHeight = false;      double height = 0.0;
    bool hasWidthFactor = false; double widthFactor = 1.0;
    bool hasObliqueAngle = false; double obliqueAngle = 0.0;
    bool hasIsShapeFile = false;  bool isShapeFile = false;
    bool hasIsVertical = false;   bool isVertical = false;
};

// Apply every PRESENT field in props onto pRec (open for write -- either a
// not-yet-added new record or an existing one reopened kForWrite). Mirrors
// applyLinetypeProperties'/applyDimStyleProperties' has-flag gating exactly.
static void applyTextStyleProperties(AcDbTextStyleTableRecord* pRec, const TextStylePropertyArgs& props)
{
    if (props.hasFontFile) {
        const std::wstring fontFileW = asciiToWide(props.fontFile);
        pRec->setFileName(fontFileW.c_str());
    }
    if (props.hasBigFontFile) {
        const std::wstring bigFontW = asciiToWide(props.bigFontFile);
        pRec->setBigFontFileName(bigFontW.c_str());
    }
    if (props.hasHeight)
        pRec->setTextSize(props.height);
    if (props.hasWidthFactor)
        pRec->setXScale(props.widthFactor);
    if (props.hasObliqueAngle)
        pRec->setObliquingAngle(props.obliqueAngle);
    if (props.hasIsShapeFile)
        pRec->setIsShapeFile(props.isShapeFile);
    if (props.hasIsVertical)
        pRec->setIsVertical(props.isVertical);
}

// D-class TABLES tier: create-or-update a named TEXTSTYLE record (write.
// textstyle.create's handler) -- mirrors upsertLinetypeRecord's upsert
// contract exactly (see its own comment above): a brand-new textstyle starts
// from AcDbTextStyleTableRecord's own ctor defaults, and updating an
// EXISTING textstyle applies ONLY the fields present in props; omitted
// fields are left exactly as they were.
static Acad::ErrorStatus upsertTextStyleRecord(AcDbDatabase* pDb, const std::string& name,
                                               const TextStylePropertyArgs& props, bool& created)
{
    created = false;
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbTextStyleTable* pTST = nullptr;
    Acad::ErrorStatus es = pDb->getTextStyleTable(pTST, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    AcDbObjectId existingId;
    if (pTST->getAt(nameW.c_str(), existingId) == Acad::eOk) {
        pTST->close();
        AcDbTextStyleTableRecord* pRec = nullptr;
        es = acdbOpenObject(pRec, existingId, AcDb::kForWrite);
        if (es != Acad::eOk)
            return es;
        applyTextStyleProperties(pRec, props);
        pRec->close();
        return Acad::eOk;
    }

    AcDbTextStyleTableRecord* pRec = new AcDbTextStyleTableRecord();
    pRec->setName(nameW.c_str());
    applyTextStyleProperties(pRec, props);

    AcDbObjectId id;
    es = pTST->add(id, pRec);
    pTST->close();
    if (es == Acad::eOk) {
        created = true;
        pRec->close();
    }
    else {
        delete pRec;
    }
    return es;
}

static Acad::ErrorStatus appendLine(AcDbDatabase* pDb, const std::string& layer,
                                    const AcGePoint3d& start,
                                    const AcGePoint3d& end,
                                    int& modelspaceAfter)
{
    modelspaceAfter = 0;
    if (!layer.empty()) {
        bool layerCreated = false;
        Acad::ErrorStatus layerEs = ensureLayer(pDb, layer, 7, layerCreated);
        if (layerEs != Acad::eOk)
            return layerEs;
    }

    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
    if (es != Acad::eOk)
        return es;

    AcDbBlockTableRecord* pMS = nullptr;
    es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
    pBT->close();
    if (es != Acad::eOk)
        return es;

    AcDbLine* pLine = new AcDbLine(start, end);
    if (!layer.empty()) {
        const std::wstring layerW = asciiToWide(layer);
        pLine->setLayer(layerW.c_str());
    }

    AcDbObjectId id;
    es = pMS->appendAcDbEntity(id, pLine);
    pMS->close();
    if (es == Acad::eOk)
        pLine->close();
    else
        delete pLine;

    int probes = 0;
    countModelSpace(pDb, modelspaceAfter, probes);
    return es;
}

static Acad::ErrorStatus appendCircle(AcDbDatabase* pDb, const std::string& layer,
                                      const AcGePoint3d& center,
                                      double radius,
                                      int& modelspaceAfter)
{
    modelspaceAfter = 0;
    if (radius <= 0.0)
        return Acad::eInvalidInput;
    if (!layer.empty()) {
        bool layerCreated = false;
        Acad::ErrorStatus layerEs = ensureLayer(pDb, layer, 7, layerCreated);
        if (layerEs != Acad::eOk)
            return layerEs;
    }

    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
    if (es != Acad::eOk)
        return es;

    AcDbBlockTableRecord* pMS = nullptr;
    es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
    pBT->close();
    if (es != Acad::eOk)
        return es;

    AcDbCircle* pCircle = new AcDbCircle(center, AcGeVector3d(0.0, 0.0, 1.0), radius);
    if (!layer.empty()) {
        const std::wstring layerW = asciiToWide(layer);
        pCircle->setLayer(layerW.c_str());
    }

    AcDbObjectId id;
    es = pMS->appendAcDbEntity(id, pCircle);
    pMS->close();
    if (es == Acad::eOk)
        pCircle->close();
    else
        delete pCircle;

    int probes = 0;
    countModelSpace(pDb, modelspaceAfter, probes);
    return es;
}

static Acad::ErrorStatus appendRecord(AcDbDatabase* pDb, const std::string& key,
                                      int value, int& recordsAfter)
{
    recordsAfter = 0;
    AcDbDictionary* pDict = nullptr;
    Acad::ErrorStatus es = openAriadneDict(pDb, AcDb::kForWrite, true, pDict);
    if (es != Acad::eOk)
        return es;

    AcDbObject* pRecord = nullptr;
    es = ariadneCreateRecordObject(pRecord, value);
    if (es != Acad::eOk) {
        pDict->close();
        return es;
    }

    AcDbObjectId recordId;
    const std::wstring keyW = asciiToWide(key);
    es = pDict->setAt(keyW.c_str(), pRecord, recordId);
    if (es == Acad::eOk)
        pRecord->close();
    else
        delete pRecord;

    AcDbDictionaryIterator* pIt = pDict->newIterator();
    for (; pIt != nullptr && !pIt->done(); pIt->next()) {
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, pIt->objectId(), AcDb::kForRead) == Acad::eOk) {
            if (ariadneIsRecordObject(pObj))
                ++recordsAfter;
            pObj->close();
        }
    }
    delete pIt;
    pDict->close();
    return es;
}

static bool countRecords(AcDbDatabase* pDb, int& records)
{
    records = 0;
    AcDbDictionary* pDict = nullptr;
    Acad::ErrorStatus es = openAriadneDict(pDb, AcDb::kForRead, false, pDict);
    if (es == Acad::eKeyNotFound)
        return true;
    if (es != Acad::eOk)
        return false;

    AcDbDictionaryIterator* pIt = pDict->newIterator();
    for (; pIt != nullptr && !pIt->done(); pIt->next()) {
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, pIt->objectId(), AcDb::kForRead) == Acad::eOk) {
            if (ariadneIsRecordObject(pObj))
                ++records;
            pObj->close();
        }
    }
    delete pIt;
    pDict->close();
    return true;
}

static Acad::ErrorStatus setXrecord(AcDbDatabase* pDb, const std::string& key,
                                    const std::string& value)
{
    if (key.empty())
        return Acad::eInvalidInput;

    AcDbDictionary* pDict = nullptr;
    Acad::ErrorStatus es = openAriadneDict(pDb, AcDb::kForWrite, true, pDict);
    if (es != Acad::eOk)
        return es;

    const std::wstring valueW = asciiToWide(value);
    resbuf* rb = acutBuildList(AcDb::kDxfText, valueW.c_str(), 0);
    if (rb == nullptr) {
        pDict->close();
        return Acad::eOutOfMemory;
    }

    const std::wstring keyW = asciiToWide(key);
    AcDbObject* pObj = nullptr;
    es = pDict->getAt(keyW.c_str(), pObj, AcDb::kForWrite);
    if (es == Acad::eOk) {
        AcDbXrecord* pXrecord = AcDbXrecord::cast(pObj);
        if (pXrecord == nullptr) {
            pObj->close();
            acutRelRb(rb);
            pDict->close();
            return Acad::eWrongObjectType;
        }
        es = pXrecord->setFromRbChain(*rb);
        pXrecord->close();
    }
    else if (es == Acad::eKeyNotFound) {
        AcDbXrecord* pXrecord = new AcDbXrecord();
        es = pXrecord->setFromRbChain(*rb);
        if (es == Acad::eOk) {
            AcDbObjectId id;
            es = pDict->setAt(keyW.c_str(), pXrecord, id);
        }
        if (es == Acad::eOk)
            pXrecord->close();
        else
            delete pXrecord;
    }

    acutRelRb(rb);
    pDict->close();
    return es;
}

static bool getXrecord(AcDbDatabase* pDb, const std::string& key,
                       std::string& value, bool& found)
{
    value.clear();
    found = false;
    if (key.empty())
        return false;

    AcDbDictionary* pDict = nullptr;
    Acad::ErrorStatus es = openAriadneDict(pDb, AcDb::kForRead, false, pDict);
    if (es == Acad::eKeyNotFound)
        return true;
    if (es != Acad::eOk)
        return false;

    const std::wstring keyW = asciiToWide(key);
    AcDbObject* pObj = nullptr;
    es = pDict->getAt(keyW.c_str(), pObj, AcDb::kForRead);
    if (es == Acad::eKeyNotFound) {
        pDict->close();
        return true;
    }
    if (es != Acad::eOk) {
        pDict->close();
        return false;
    }

    AcDbXrecord* pXrecord = AcDbXrecord::cast(pObj);
    if (pXrecord == nullptr) {
        pObj->close();
        pDict->close();
        return false;
    }

    resbuf* rb = nullptr;
    es = pXrecord->rbChain(&rb);
    if (es == Acad::eOk && rb != nullptr) {
        for (resbuf* cur = rb; cur != nullptr; cur = cur->rbnext) {
            if (cur->restype == AcDb::kDxfText) {
                value = acharToAscii(cur->resval.rstring);
                found = true;
                break;
            }
        }
        acutRelRb(rb);
    }
    pXrecord->close();
    pDict->close();
    return es == Acad::eOk;
}

static Acad::ErrorStatus ensureRegApp(AcDbDatabase* pDb, const std::string& app)
{
    if (app.empty())
        return Acad::eInvalidInput;

    const std::wstring appW = asciiToWide(app);
    AcDbRegAppTable* pTable = nullptr;
    Acad::ErrorStatus es = pDb->getRegAppTable(pTable, AcDb::kForRead);
    if (es != Acad::eOk)
        return es;
    if (pTable->has(appW.c_str())) {
        pTable->close();
        return Acad::eOk;
    }
    pTable->close();

    es = pDb->getRegAppTable(pTable, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;
    AcDbRegAppTableRecord* pRecord = new AcDbRegAppTableRecord();
    pRecord->setName(appW.c_str());
    AcDbObjectId id;
    es = pTable->add(id, pRecord);
    pTable->close();
    if (es == Acad::eOk)
        pRecord->close();
    else
        delete pRecord;
    return es;
}

static Acad::ErrorStatus setDatabaseXdata(AcDbDatabase* pDb, const std::string& app,
                                          const std::string& value)
{
    Acad::ErrorStatus es = ensureRegApp(pDb, app);
    if (es != Acad::eOk)
        return es;

    AcDbDictionary* pDict = nullptr;
    es = openAriadneDict(pDb, AcDb::kForWrite, true, pDict);
    if (es != Acad::eOk)
        return es;

    const std::wstring appW = asciiToWide(app);
    const std::wstring valueW = asciiToWide(value);
    resbuf* rb = acutBuildList(
        AcDb::kDxfRegAppName, appW.c_str(),
        AcDb::kDxfXdAsciiString, valueW.c_str(),
        0);
    if (rb == nullptr) {
        pDict->close();
        return Acad::eOutOfMemory;
    }

    es = pDict->setXData(rb);
    acutRelRb(rb);
    pDict->close();
    return es;
}

static bool getDatabaseXdata(AcDbDatabase* pDb, const std::string& app,
                             std::string& value, bool& found)
{
    value.clear();
    found = false;
    if (app.empty())
        return false;

    AcDbDictionary* pDict = nullptr;
    Acad::ErrorStatus es = openAriadneDict(pDb, AcDb::kForRead, false, pDict);
    if (es == Acad::eKeyNotFound)
        return true;
    if (es != Acad::eOk)
        return false;

    const std::wstring appW = asciiToWide(app);
    resbuf* rb = pDict->xData(appW.c_str());
    if (rb != nullptr) {
        for (resbuf* cur = rb; cur != nullptr; cur = cur->rbnext) {
            if (cur->restype == AcDb::kDxfXdAsciiString) {
                value = acharToAscii(cur->resval.rstring);
                found = true;
                break;
            }
        }
        acutRelRb(rb);
    }
    pDict->close();
    return true;
}

static void appendJsonString(std::ostringstream& out, bool& first,
                             const std::string& value)
{
    if (!first)
        out << ",";
    out << "\"" << jsonEscape(value) << "\"";
    first = false;
}

static bool countBlockDefinitions(AcDbDatabase* pDb, const std::string& targetName,
                                  int& definitionCount, bool& targetFound,
                                  std::string& namesJson)
{
    definitionCount = 0;
    targetFound = false;
    std::ostringstream names; names.precision(kJsonDoublePrecision);
    names << "[";
    bool first = true;

    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
        return false;

    AcDbBlockTableIterator* pIt = nullptr;
    if (pBT->newIterator(pIt) != Acad::eOk) {
        pBT->close();
        return false;
    }

    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbBlockTableRecord* pBTR = nullptr;
        if (pIt->getRecord(pBTR, AcDb::kForRead) == Acad::eOk) {
            const bool isUserBlock =
                !pBTR->isLayout() &&
                !pBTR->isAnonymous() &&
                !pBTR->isFromExternalReference();
            if (isUserBlock) {
                const ACHAR* nameRaw = nullptr;
                std::string name;
                if (pBTR->getName(nameRaw) == Acad::eOk)
                    name = acharToAscii(nameRaw);
                ++definitionCount;
                if (!targetName.empty() && name == targetName)
                    targetFound = true;
                appendJsonString(names, first, name);
            }
            pBTR->close();
        }
    }

    delete pIt;
    pBT->close();
    names << "]";
    namesJson = names.str();
    return true;
}

// --- M08 inspect-enumeration helpers (pure read; mirror countBlockDefinitions
// /collectModelSpaceGraph idioms: SymbolTable/BTR iterators opened kForRead, the
// comma-first jsonEscape emitter, acharToAscii name funnel). Same documented
// non-ASCII fidelity limitation as the rest of this file (code points > 127 ->
// '?'); the underlying DWG bytes are unchanged. ---

// inspect.layers: enumerate every layer-table record with its display flags.
static bool listLayerRecords(AcDbDatabase* pDb, int& count, std::string& layersJson)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbLayerTable* pTable = nullptr;
    if (pDb->getLayerTable(pTable, AcDb::kForRead) != Acad::eOk)
        return false;
    AcDbLayerTableIterator* pIt = nullptr;
    if (pTable->newIterator(pIt) != Acad::eOk) {
        pTable->close();
        return false;
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbLayerTableRecord* pRec = nullptr;
        if (pIt->getRecord(pRec, AcDb::kForRead) == Acad::eOk) {
            const ACHAR* nameRaw = nullptr;
            std::string name;
            if (pRec->getName(nameRaw) == Acad::eOk)
                name = acharToAscii(nameRaw);
            const bool isOff = pRec->isOff() ? true : false;
            const bool isFrozen = pRec->isFrozen() ? true : false;
            const bool isLocked = pRec->isLocked() ? true : false;
            const int colorIndex = static_cast<int>(pRec->color().colorIndex());
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"name\":\"" << jsonEscape(name) << "\""
                << ",\"off\":" << (isOff ? "true" : "false")
                << ",\"frozen\":" << (isFrozen ? "true" : "false")
                << ",\"locked\":" << (isLocked ? "true" : "false")
                << ",\"color\":" << colorIndex << "}";
            ++count;
            pRec->close();
        }
    }
    delete pIt;
    pTable->close();
    arr << "]";
    layersJson = arr.str();
    return true;
}

// inspect.blocks: enumerate user block definitions with each block's entity count.
static bool listBlockDefinitionsDetailed(AcDbDatabase* pDb, int& count,
                                         std::string& blocksJson)
{
    count = 0;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
        return false;
    AcDbBlockTableIterator* pIt = nullptr;
    if (pBT->newIterator(pIt) != Acad::eOk) {
        pBT->close();
        return false;
    }
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbBlockTableRecord* pBTR = nullptr;
        if (pIt->getRecord(pBTR, AcDb::kForRead) == Acad::eOk) {
            const bool isUserBlock =
                !pBTR->isLayout() &&
                !pBTR->isAnonymous() &&
                !pBTR->isFromExternalReference();
            if (isUserBlock) {
                const ACHAR* nameRaw = nullptr;
                std::string name;
                if (pBTR->getName(nameRaw) == Acad::eOk)
                    name = acharToAscii(nameRaw);
                int entCount = 0;
                AcDbBlockTableRecordIterator* pEIt = nullptr;
                if (pBTR->newIterator(pEIt) == Acad::eOk) {
                    for (pEIt->start(); !pEIt->done(); pEIt->step())
                        ++entCount;
                    delete pEIt;
                }
                if (!first)
                    arr << ",";
                first = false;
                arr << "{\"name\":\"" << jsonEscape(name) << "\""
                    << ",\"entity_count\":" << entCount << "}";
                ++count;
            }
            pBTR->close();
        }
    }
    delete pIt;
    pBT->close();
    arr << "]";
    blocksJson = arr.str();
    return true;
}

// inspect.entities: per-entity handle/dxf_name/layer over model space, optional
// type filter (reuses entityMatchesType). Bounded page: emits up to `limit`
// records but reports the true total/matching counts and a truncated flag (no
// silent cap).
static bool listModelSpaceEntities(AcDbDatabase* pDb, const std::string& type,
                                   int limit, int& total, int& matching,
                                   int& returned, bool& truncated,
                                   std::string& entitiesJson)
{
    total = 0;
    matching = 0;
    returned = 0;
    truncated = false;
    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
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
        if (pIt->getEntity(pEnt, AcDb::kForRead) != Acad::eOk)
            continue;
        ++total;
        if (entityMatchesType(pEnt, type)) {
            ++matching;
            if (returned < limit) {
                std::string handleStr;
                {
                    AcDbHandle h;
                    pEnt->getAcDbHandle(h);
                    ACHAR hbuf[40] = {};
                    if (h.getIntoAsciiBuffer(hbuf, 40))
                        handleStr = acharToAscii(hbuf);
                }
                const std::string dxfName = (pEnt->isA() != nullptr)
                    ? acharToAscii(pEnt->isA()->name()) : std::string();
                const std::string layer = acharToAscii(pEnt->layer());
                if (!first)
                    arr << ",";
                first = false;
                arr << "{\"handle\":\"" << jsonEscape(handleStr) << "\""
                    << ",\"dxf_name\":\"" << jsonEscape(dxfName) << "\""
                    << ",\"layer\":\"" << jsonEscape(layer) << "\"}";
                ++returned;
            }
        }
        pEnt->close();
    }
    delete pIt;
    pMS->close();
    arr << "]";
    entitiesJson = arr.str();
    truncated = (matching > returned);
    return true;
}

static Acad::ErrorStatus createSimpleBlock(AcDbDatabase* pDb,
                                           const std::string& name,
                                           bool& created,
                                           int& definitionCount,
                                           bool seedLine = true)
{
    created = false;
    definitionCount = 0;
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForWrite);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    if (pBT->has(nameW.c_str())) {
        pBT->close();
        bool found = false;
        std::string namesJson;
        countBlockDefinitions(pDb, name, definitionCount, found, namesJson);
        return Acad::eOk;
    }

    AcDbBlockTableRecord* pBlock = new AcDbBlockTableRecord();
    pBlock->setName(nameW.c_str());
    AcDbObjectId blockId;
    es = pBT->add(blockId, pBlock);
    pBT->close();
    if (es != Acad::eOk) {
        delete pBlock;
        return es;
    }

    if (seedLine) {
        // Self-test heritage: the original op proved writability by seeding a
        // visible line. Regen synthesis passes seed_line=0 - a phantom
        // (0,0,0)->(5,0,0) line in every rebuilt definition was the measured
        // "+1 per def" fixed-point drift (GEN2 / R4b blockdef_diff).
        AcDbLine* pLine = new AcDbLine(AcGePoint3d(0.0, 0.0, 0.0),
                                      AcGePoint3d(5.0, 0.0, 0.0));
        AcDbObjectId lineId;
        es = pBlock->appendAcDbEntity(lineId, pLine);
        if (es == Acad::eOk) {
            pLine->close();
            created = true;
        }
        else {
            delete pLine;
        }
    }
    else {
        created = true;
    }
    pBlock->close();

    bool found = false;
    std::string namesJson;
    countBlockDefinitions(pDb, name, definitionCount, found, namesJson);
    return es;
}

static Acad::ErrorStatus insertBlockReference(AcDbDatabase* pDb,
                                              const std::string& name,
                                              const AcGePoint3d& position,
                                              int& modelspaceAfter)
{
    modelspaceAfter = 0;
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbBlockTable* pBT = nullptr;
    Acad::ErrorStatus es = pDb->getBlockTable(pBT, AcDb::kForRead);
    if (es != Acad::eOk)
        return es;

    const std::wstring nameW = asciiToWide(name);
    AcDbObjectId blockId;
    es = pBT->getAt(nameW.c_str(), blockId);
    if (es != Acad::eOk) {
        pBT->close();
        return es;
    }

    AcDbBlockTableRecord* pMS = nullptr;
    es = pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite);
    pBT->close();
    if (es != Acad::eOk)
        return es;

    AcDbBlockReference* pRef = new AcDbBlockReference(position, blockId);
    AcDbObjectId refId;
    es = pMS->appendAcDbEntity(refId, pRef);
    pMS->close();
    if (es == Acad::eOk)
        pRef->close();
    else
        delete pRef;

    int probes = 0;
    countModelSpace(pDb, modelspaceAfter, probes);
    return es;
}

static Acad::ErrorStatus createLayout(AcDbDatabase* pDb, const std::string& name,
                                      bool& created, int& layoutCount)
{
    created = false;
    layoutCount = 0;
    if (name.empty())
        return Acad::eInvalidInput;

    AcDbLayoutManager* pLayoutManager =
        acdbHostApplicationServices()->layoutManager();
    if (pLayoutManager == nullptr)
        return Acad::eNotApplicable;

    const std::wstring nameW = asciiToWide(name);
    if (!pLayoutManager->layoutExists(nameW.c_str(), pDb)) {
        AcDbObjectId layoutId;
        AcDbObjectId blockTableRecordId;
        Acad::ErrorStatus es = pLayoutManager->createLayout(
            nameW.c_str(),
            layoutId,
            blockTableRecordId,
            pDb);
        if (es != Acad::eOk)
            return es;
        created = true;
    }

    AcDbDictionary* pLayouts = nullptr;
    Acad::ErrorStatus es = pDb->getLayoutDictionary(pLayouts, AcDb::kForRead);
    if (es == Acad::eOk) {
        AcDbDictionaryIterator* pIt = pLayouts->newIterator();
        for (; pIt != nullptr && !pIt->done(); pIt->next())
            ++layoutCount;
        delete pIt;
        pLayouts->close();
    }
    return es;
}

static bool listLayouts(AcDbDatabase* pDb, int& layoutCount, std::string& namesJson)
{
    layoutCount = 0;
    std::ostringstream names; names.precision(kJsonDoublePrecision);
    names << "[";
    bool first = true;

    AcDbDictionary* pLayouts = nullptr;
    if (pDb->getLayoutDictionary(pLayouts, AcDb::kForRead) != Acad::eOk)
        return false;

    AcDbDictionaryIterator* pIt = pLayouts->newIterator();
    for (; pIt != nullptr && !pIt->done(); pIt->next()) {
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, pIt->objectId(), AcDb::kForRead) == Acad::eOk) {
            AcDbLayout* pLayout = AcDbLayout::cast(pObj);
            if (pLayout != nullptr) {
                const ACHAR* nameRaw = nullptr;
                if (pLayout->getLayoutName(nameRaw) == Acad::eOk)
                    appendJsonString(names, first, acharToAscii(nameRaw));
                ++layoutCount;
            }
            pObj->close();
        }
    }
    delete pIt;
    pLayouts->close();
    names << "]";
    namesJson = names.str();
    return true;
}

static bool listXrefs(AcDbDatabase* pDb, int& xrefCount, std::string& namesJson)
{
    xrefCount = 0;
    std::ostringstream names; names.precision(kJsonDoublePrecision);
    names << "[";
    bool first = true;

    AcDbBlockTable* pBT = nullptr;
    if (pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk)
        return false;
    AcDbBlockTableIterator* pIt = nullptr;
    if (pBT->newIterator(pIt) != Acad::eOk) {
        pBT->close();
        return false;
    }

    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbBlockTableRecord* pBTR = nullptr;
        if (pIt->getRecord(pBTR, AcDb::kForRead) == Acad::eOk) {
            if (pBTR->isFromExternalReference()) {
                const ACHAR* nameRaw = nullptr;
                std::string name;
                if (pBTR->getName(nameRaw) == Acad::eOk)
                    name = acharToAscii(nameRaw);
                appendJsonString(names, first, name);
                ++xrefCount;
            }
            pBTR->close();
        }
    }

    delete pIt;
    pBT->close();
    names << "]";
    namesJson = names.str();
    return true;
}

static std::string runtimeCapabilitiesJson(const std::string& jobHostMode)
{
    const bool fullAutoCad = (jobHostMode == "full_autocad");
    return std::string()
        + "{\"host\":\"" + jsonEscape(jobHostMode) + "\","
        + "\"full_autocad_job\":" + (fullAutoCad ? "true" : "false") + ","
        + "\"active_document\":" + (fullAutoCad ? "true" : "false") + ","
        + "\"database_write\":true,"
        + "\"custom_entities\":true,"
        + "\"custom_objects\":true,"
        + "\"protocol_extensions\":true,"
        + "\"xrecords\":true,"
        + "\"xdata\":true,"
        + "\"blocks\":true,"
        + "\"layouts\":true,"
        + "\"xrefs_inspect\":true,"
        + "\"reactors\":{\"implemented\":true,\"registered\":" + (gAriadneEditorReactor != nullptr ? "true" : "false") + "},"
        + "\"selection_monitor\":{\"implemented\":true,\"registered\":" + (gAriadneSelectionMonitor != nullptr ? "true" : "false") + ",\"live_events\":\"attended_only\"},"
        + "\"overrules\":{\"implemented\":true,\"registered\":" + (gAriadneObjectOverrule != nullptr ? "true" : "false") + "},"
        + "\"jigs\":{\"interactive\":" + (fullAutoCad ? "true" : "false") + ","
        + "\"implemented\":true,"
        + "\"reason\":\"" + (fullAutoCad
            ? "Full AutoCAD has an editor interaction loop"
            : "Core Console has no interactive editor prompt loop") + "\"}}";
}

static std::string reactorRegistryJson(const std::string& jobHostMode)
{
    return std::string()
        + "{\"host\":\"" + jsonEscape(jobHostMode) + "\","
        + "\"registered\":" + (gAriadneEditorReactor != nullptr ? "true" : "false") + ","
        + "\"count\":" + (gAriadneEditorReactor != nullptr ? "1" : "0") + ","
        + "\"command_starts\":" + std::to_string(gReactorCommandStarts) + ","
        + "\"command_ends\":" + std::to_string(gReactorCommandEnds) + ","
        + "\"last_command\":\"" + jsonEscape(gReactorLastCommand) + "\","
        + "\"items\":" + (gAriadneEditorReactor != nullptr ? "[\"AriadneEditorReactor\"]" : "[]") + "}";
}

static std::string selectionMonitorRegistryJson(const std::string& jobHostMode)
{
    const bool fullAutoCad = (jobHostMode == "full_autocad");
    return std::string()
        + "{\"host\":\"" + jsonEscape(jobHostMode) + "\","
        + "\"implemented\":true,"
        + "\"registered\":" + (gAriadneSelectionMonitor != nullptr ? "true" : "false") + ","
        + "\"interactive_editor_required\":true,"
        + "\"live_events_supported\":" + (fullAutoCad ? "true" : "false") + ","
        + "\"pickfirst_modified\":" + std::to_string(gSelMonPickfirstMods) + ","
        + "\"command_ends\":" + std::to_string(gSelMonCommandEnds) + ","
        + "\"items\":" + (gAriadneSelectionMonitor != nullptr ? "[\"AriadneSelectionMonitor\"]" : "[]") + ","
        + "\"reason\":\"" + (fullAutoCad
            ? "Full AutoCAD editor delivers interactive selection notifications"
            : "Core Console has no interactive pick UI, but programmatic pickfirst (acedSSSetFirst) still fires pickfirstModified -- see firing_report counts") + "\"}";
}

static std::string overruleRegistryJson(const std::string& jobHostMode)
{
    return std::string()
        + "{\"host\":\"" + jsonEscape(jobHostMode) + "\","
        + "\"implemented\":true,"
        + "\"registered\":" + (gAriadneObjectOverrule != nullptr ? "true" : "false") + ","
        + "\"count\":" + (gAriadneObjectOverrule != nullptr ? "1" : "0") + ","
        + "\"global_overruling\":" + (AcRxOverrule::isOverruling() ? "true" : "false") + ","
        + "\"target\":\"AcDbEntity with AriadneProbe predicate\","
        + "\"open_calls\":" + std::to_string(gOverruleOpenCalls) + ","
        + "\"close_calls\":" + std::to_string(gOverruleCloseCalls) + ","
        + "\"items\":" + (gAriadneObjectOverrule != nullptr ? "[\"AriadneObjectOverrule\"]" : "[]") + "}";
}

static std::string jigHostSupportJson(const std::string& jobHostMode)
{
    const bool fullAutoCad = (jobHostMode == "full_autocad");
    return std::string()
        + "{\"host\":\"" + jsonEscape(jobHostMode) + "\","
        + "\"implemented\":true,"
        + "\"supported\":" + (fullAutoCad ? "true" : "false") + ","
        + "\"interactive_editor_required\":true,"
        + "\"point_probe_operation\":\"live.jig.point_probe\","
        + "\"reason\":\"" + (fullAutoCad
            ? "Full AutoCAD has an editor interaction loop"
            : "Jigs require a full AutoCAD editor interaction loop, not Core Console batch execution") + "\"}";
}

//============================================================================
// Command: ARIADNE_NATIVE_JOB
//============================================================================
//============================================================================
// M08B-T03: transaction / handle-resolver wrappers (with AriadneDocumentWriteLock
// below, the safe scoped-DB-access infra the M08 family/write tickets build on).
//
// RAII guarantees a transaction always closes. The staged-write wrapper commits
// ONLY via commit(); any uncommitted scope exit (early return / failure / thrown)
// auto-ABORTS -> rollback. No original DWG is ever written: these operate on the
// router-staged copy in memory; nothing here calls save()/saveAs().
//============================================================================

// Scoped READ transaction. endTransaction() on exit (reads roll back nothing).
class AriadneReadTransaction
{
public:
    explicit AriadneReadTransaction(AcDbDatabase* pDb)
        : mMgr(nullptr), mTxn(nullptr)
    {
        if (pDb != nullptr) {
            mMgr = pDb->transactionManager();
            if (mMgr != nullptr)
                mTxn = mMgr->startTransaction();
        }
    }
    ~AriadneReadTransaction()
    {
        if (mMgr != nullptr && mTxn != nullptr)
            mMgr->endTransaction();
    }
    bool active() const { return mTxn != nullptr; }
    AcTransaction* txn() const { return mTxn; }
private:
    AcDbTransactionManager* mMgr;
    AcTransaction* mTxn;
    AriadneReadTransaction(const AriadneReadTransaction&);
    AriadneReadTransaction& operator=(const AriadneReadTransaction&);
};

// Scoped STAGED-WRITE transaction. commit() keeps the staged mutation; an
// uncommitted dtor abortTransaction()s -> rollback (the "failure rolls back"
// contract). Never touches the original file.
class AriadneStagedWriteTransaction
{
public:
    explicit AriadneStagedWriteTransaction(AcDbDatabase* pDb)
        : mMgr(nullptr), mTxn(nullptr), mCommitted(false)
    {
        if (pDb != nullptr) {
            mMgr = pDb->transactionManager();
            if (mMgr != nullptr)
                mTxn = mMgr->startTransaction();
        }
    }
    ~AriadneStagedWriteTransaction()
    {
        if (mMgr != nullptr && mTxn != nullptr && !mCommitted)
            mMgr->abortTransaction();   // rollback on any uncommitted exit
    }
    bool active() const { return mTxn != nullptr; }
    AcTransaction* txn() const { return mTxn; }
    // Keep the staged mutation. Returns the end status; on success the txn is done.
    Acad::ErrorStatus commit()
    {
        if (mMgr == nullptr || mTxn == nullptr || mCommitted)
            return Acad::eOk;
        const Acad::ErrorStatus es = mMgr->endTransaction();
        if (es == Acad::eOk) {
            mCommitted = true;
            mTxn = nullptr;
        }
        return es;
    }
private:
    AcDbTransactionManager* mMgr;
    AcTransaction* mTxn;
    bool mCommitted;
    AriadneStagedWriteTransaction(const AriadneStagedWriteTransaction&);
    AriadneStagedWriteTransaction& operator=(const AriadneStagedWriteTransaction&);
};

// Handle resolver: hex-handle string -> AcDbObjectId (the inverse of handleOf()).
// Reusable factoring of the inline AcDbHandle/getAcDbObjectId pattern. Returns true
// + sets out on success; false (out = null) otherwise.
static bool resolveHandle(AcDbDatabase* pDb, const std::string& hexHandle, AcDbObjectId& out)
{
    out = AcDbObjectId::kNull;
    if (pDb == nullptr || hexHandle.empty())
        return false;
    const AcDbHandle h(asciiToWide(hexHandle).c_str());  // AcDbHandle ctor takes const ACHAR* (wide)
    return (pDb->getAcDbObjectId(out, false, h) == Acad::eOk) && !out.isNull();
}

class AriadneDocumentWriteLock
{
public:
    AriadneDocumentWriteLock()
        : mDoc(nullptr), mLocked(false)
    {
        if (acDocManager == nullptr)
            return;
        mDoc = acDocManager->curDocument();
        if (mDoc == nullptr)
            return;
        const Acad::ErrorStatus es =
            acDocManager->lockDocument(mDoc, AcAp::kWrite);
        mLocked = (es == Acad::eOk);
    }

    ~AriadneDocumentWriteLock()
    {
        if (mLocked && acDocManager != nullptr && mDoc != nullptr)
            acDocManager->unlockDocument(mDoc);
    }

private:
    AcApDocument* mDoc;
    bool mLocked;
};

//============================================================================
// M08B-T01: Native OperationSpec dispatch table + standard result/error envelope.
//
// kAriadneNativeOperationTable is the AUTHORITATIVE registry of the operations
// ARIADNE_NATIVE_JOB implements today. The dispatcher gates on it: an op_id absent
// from the table is not implemented in the native module and returns a structured
// OPERATION_NOT_IMPLEMENTED (the honest contract for the catalogued ops the M08
// family tickets will build). The implemented handler bodies are bridged unchanged
// in the dispatch chain below; the table drives the membership/dispatch decision.
// INVARIANT: the table op_ids and the `op == "..."` handler branches below are the
// same set (asserted source-side by tests/unit/test_m08b_dispatcher_table.py).
//============================================================================
struct AriadneOperationSpec
{
    const char* op_id;
    const char* family;   // mirrors operations.v2.json; native-only diagnostics carry a native family
};

static const AriadneOperationSpec kAriadneNativeOperationTable[] = {
    { "inspect.database.summary", "objectdbx_database" },
    { "inspect.database.graph", "inspect" },
    { "write.layer.create", "symbol_tables_dictionaries" },
    { "write.dimstyle.create", "symbol_tables_dictionaries" },
    { "write.ucs.create", "symbol_tables_dictionaries" },
    { "write.view.create", "symbol_tables_dictionaries" },
    { "write.vport.create", "symbol_tables_dictionaries" },
    { "write.linetype.create", "symbol_tables_dictionaries" },
    { "write.textstyle.create", "symbol_tables_dictionaries" },
    { "write.entity.line", "geometry_kernel" },
    { "write.entity.circle", "geometry_kernel" },
    { "inspect.entity.count", "inspect" },
    { "write.xrecord.set", "symbol_tables_dictionaries" },
    { "inspect.xrecord.get", "symbol_tables_dictionaries" },
    { "write.xdata.set", "write" },
    { "inspect.xdata.get", "inspect" },
    { "write.block.simple_create", "write" },
    { "write.block.insert", "write" },
    { "inspect.block.count", "inspect" },
    { "write.layout.create", "write" },
    { "inspect.layout.list", "inspect" },
    { "inspect.xref.list", "inspect" },
    { "inspect.layers", "inspect" },
    { "inspect.blocks", "inspect" },
    { "inspect.entities", "inspect" },
    { "inspect.runtime.capabilities", "inspect" },
    { "live.reactor.enable", "live" },
    { "inspect.reactor.registry", "inspect" },
    { "live.reactor.disable", "live" },
    { "live.selection.monitor.enable", "live" },
    { "live.selection.monitor.disable", "live" },
    { "inspect.selection.monitor.registry", "live" },
    { "inspect.probe.property_count", "inspect" },
    { "inspect.overrule.registry", "inspect" },
    { "live.overrule.enable", "live" },
    { "live.overrule.disable", "live" },
    { "inspect.jig.host_support", "inspect" },
    { "live.jig.point_probe", "live" },
    { "extend.deep_native.firing_selftest", "extend" },
    { "inspect.deep_native.firing_report", "inspect" },
    { "extend.customclass.create", "extend" },
    { "inspect.customclass.count", "inspect" },
    { "extend.customobject.create", "extend" },
    { "inspect.customobject.count", "inspect" },
    { "inspect.protocol.queryx", "inspect" },
};

static const size_t kAriadneNativeOperationCount =
    sizeof(kAriadneNativeOperationTable) / sizeof(kAriadneNativeOperationTable[0]);

static const AriadneOperationSpec* findAriadneNativeOp(const std::string& op)
{
    for (size_t i = 0; i < kAriadneNativeOperationCount; ++i) {
        if (op == kAriadneNativeOperationTable[i].op_id)
            return &kAriadneNativeOperationTable[i];
    }
    return nullptr;
}

// Standard structured error: the result `r` already carries the
// {schema, engine, operation,} prefix; this appends a machine-stable error_code
// plus the human error message and closes the JSON object. The additive error_code
// keeps the legacy `error` string for back-compat.
static void emitNativeError(std::ostringstream& r,
                            const char* errorCode,
                            const std::string& message)
{
    r << "\"status\":\"error\","
      << "\"error_code\":\"" << errorCode << "\","
      << "\"error\":\"" << jsonEscape(message) << "\"}";
}

//============================================================================
// M08C0: family handler seam. Each READ/family ticket lives in its own
// families/m08X_handlers.inc (#included below; compiled into .crx/.arx as part of
// this TU, so it sees every static helper: njsonStr / serializeObjectCommon /
// serializeEntityCommon, the transaction wrappers, resolveHandle, jsonFind*,
// handleOf / handleOfId, the resbuf serializers, AriadneOperationSpec). A family
// owns ONLY its .inc -> parallel teammates never touch a shared file -> conflict-
// free merges. Each .inc defines, for family X:
//     static bool m08xHasOp(const std::string& op);     // op in this family?
//     static bool m08xDispatch(op, const AriadneJobCtx&, std::ostringstream&);
// The dispatcher gate admits an op if any family claims it; the final else routes
// it to the owning family. Stubs return false until the family teammate fills them.
//============================================================================
struct AriadneJobCtx
{
    const std::string& job;       // raw job JSON (parse args with jsonFind*)
    AcDbDatabase* pDb;            // working database (a staged copy in the headless host)
    const std::string& hostMode;  // "coreconsole" | "full_autocad"
};

#include "families/m08c_handlers.inc"   // M08C — symbol tables / database metadata
#include "families/m08d_handlers.inc"   // M08D — entities / geometry / brep / annotation read
#include "families/m08e_handlers.inc"   // M08E — blocks / xrefs-layouts / dictionaries-xdata
#include "families/m08f_handlers.inc"   // M08F — SQLite rich IR / query DSL
#include "families/m08g_handlers.inc"   // M08G — entity-create + entity/geometry modify (staged-write)
#include "families/m08h_handlers.inc"   // M08H — dimensions / annotations / hatch (staged-write)
#include "families/m08l_handlers.inc"   // M08L — graphics system: worldDraw / overrules / grips (native)
#include "families/m08k_handlers.inc"   // M08K-T01 — custom object/entity lifecycle (native; reuses M08L collectors)
#include "families/m08kc_handlers.inc"  // M08K-T03 — constraints / associativity (native)
#include "families/m08m_handlers.inc"   // M08M — OPM properties + reactors (native)
#include "families/m08n_handlers.inc"   // M08N — editor/jig/selection/UI/command lifecycle (native)
#include "families/w6_layerstate_handlers.inc"  // w6-layerstate — AcDbLayerStateManager ops (native)
#include "families/w6_dynblk_handlers.inc"  // w6-dynblk — dynamic block reference property read/write (native)
#include "families/w6_section_handlers.inc"  // w6-section — AcDbSection read + create (wave 6 census P2)
#include "families/materials_read.inc"  // w7-materials — AcDbMaterial/AcDbVisualStyle dictionary reads (census P2-6)
#include "families/annoscale_read.inc"  // w7-annoscale — annotation scale context reads (census P3-10)

// op admitted by any family module? (gate admission for not-yet-legacy family ops)
static bool familyHasOp(const std::string& op)
{
    return m08cHasOp(op) || m08dHasOp(op) || m08eHasOp(op) || m08fHasOp(op)
        || m08gHasOp(op) || m08hHasOp(op)
        || m08kHasOp(op) || m08kcHasOp(op) || m08lHasOp(op) || m08mHasOp(op)
        || m08nHasOp(op)
        || w6LayerStateHasOp(op)   // w6-layerstate
        || w6dynblkHasOp(op)   // w6-dynblk
        || w6sectionHasOp(op)  // w6-section
        || materialsReadHasOp(op)  // w7-materials
        || annoscaleReadHasOp(op);  // w7-annoscale
}

// route op to its owning family module; true if handled (result appended to r)
static bool tryFamilyDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    return m08cDispatch(op, ctx, r) || m08dDispatch(op, ctx, r)
        || m08eDispatch(op, ctx, r) || m08fDispatch(op, ctx, r)
        || m08gDispatch(op, ctx, r) || m08hDispatch(op, ctx, r)
        || m08kDispatch(op, ctx, r) || m08kcDispatch(op, ctx, r)
        || m08lDispatch(op, ctx, r) || m08mDispatch(op, ctx, r)
        || m08nDispatch(op, ctx, r)
        || w6LayerStateDispatch(op, ctx, r)   // w6-layerstate
        || w6dynblkDispatch(op, ctx, r)   // w6-dynblk
        || w6sectionDispatch(op, ctx, r)  // w6-section
        || materialsReadDispatch(op, ctx, r)  // w7-materials
        || annoscaleReadDispatch(op, ctx, r);  // w7-annoscale
}

static void ariadneNativeJob()
{
    const std::wstring inPath = readJobPathSetting(L"ARIADNE_CAD_JOB_IN");
    const std::wstring outPath = readJobPathSetting(L"ARIADNE_CAD_JOB_OUT");
    std::string jobHostMode = wideToAscii(readJobPathSetting(L"ARIADNE_CAD_JOB_HOST_MODE"));
    if (jobHostMode.empty())
        jobHostMode = "coreconsole";

    AriadneDocumentWriteLock documentLock;
    const std::string job = (!inPath.empty()) ? readAllBytes(inPath.c_str()) : std::string();
    std::string op;
    jsonFindString(job, "operation", op);

    AcDbDatabase* pDb = acdbHostApplicationServices()->workingDatabase();

    std::ostringstream r; r.precision(kJsonDoublePrecision);
    r << "{\"schema\":\"ariadne.autocad_native_job_result.v1\","
      << "\"engine\":\"native_objectarx\","
      << "\"operation\":\"" << op << "\",";

    // M08B-T01: table-gated dispatch. An op_id absent from the native operation
    // table is not implemented in this module -> structured OPERATION_NOT_IMPLEMENTED
    // (reported even without a working database, since it is a contract fact, not a
    // DB error). This replaces the former generic unsupported-operation else and is
    // the honest contract the M08 family tickets convert into real handlers.
    if (findAriadneNativeOp(op) == nullptr && !familyHasOp(op)) {
        emitNativeError(r, "OPERATION_NOT_IMPLEMENTED",
                        "operation '" + op + "' is not implemented in the native module");
        writeResult(outPath.empty() ? nullptr : outPath.c_str(), r.str());
        return;
    }

    if (pDb == nullptr) {
        emitNativeError(r, "NO_WORKING_DATABASE", "no working database");
        writeResult(outPath.empty() ? nullptr : outPath.c_str(), r.str());
        return;
    }

    if (op == "inspect.database.summary") {
        const int layers = countSymbolTable(pDb->layerTableId());
        const int blocks = countSymbolTable(pDb->blockTableId());
        int total = 0, probes = 0;
        countModelSpace(pDb, total, probes);
        r << "\"result\":{\"layers\":" << layers
          << ",\"blocks\":" << blocks
          << ",\"modelspace_entities\":" << total
          << ",\"ariadne_probes\":" << probes << "},"
          << "\"status\":\"ok\"}";
    }
    else if (op == "inspect.database.graph") {
        // Pure DB read -> NO host gating (runs in coreconsole + full_autocad).
        // The enclosing AriadneDocumentWriteLock is kept as-is (harmless for a
        // read). modelspace_entities is the array length by construction, so the
        // emitted count and entities[] are internally consistent and (modulo the
        // same model-space walk) equal to inspect.database.summary's count.
        int total = 0;
        std::string entitiesJson;
        std::string extensionDictionariesJson;
        std::string extensionXrecordsJson;
        RichGraphCounters richCounters;
        const bool ok = collectModelSpaceGraph(
            pDb, total, entitiesJson, extensionDictionariesJson, extensionXrecordsJson, richCounters);
        if (!ok) {
            entitiesJson = "[]";
            extensionDictionariesJson = "[]";
            extensionXrecordsJson = "[]";
        }
        // M02: rich database graph (symbol tables, blocks, layouts, xrefs,
        // dictionaries, xrecords) spliced alongside the model-space entities[].
        // collectDatabaseGraph is a guarded pure read; coverage reports which
        // sections are real vs partial/skipped (no-fake-success).
        std::string coverageJson;
        const std::string richSections = collectDatabaseGraph(
            pDb, extensionDictionariesJson, extensionXrecordsJson, richCounters, coverageJson);
        r << "\"result\":{\"modelspace_entities\":" << total
          << ",\"entities\":" << entitiesJson
          << "," << richSections
          << ",\"coverage\":" << coverageJson << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "write.layer.create") {
        std::string name;
        if (!jsonFindString(job, "name", name) || name.empty())
            name = "ARIADNE_P2";

        // D-class TABLES tier (w3-tables): every property below is OPTIONAL --
        // hasX is only true when the caller's job args actually included that
        // key, so upsertLayerRecord never resets an existing layer's field the
        // caller didn't ask to change. Booleans travel as 0/1 numbers (the
        // jsonFindNumber convention this file already uses for e.g. "closed"/
        // "is_write" -- jsonFindNumber's strtod parse does not understand
        // JSON true/false tokens).
        LayerPropertyArgs props;
        double colorRaw = 0.0;
        props.hasColor = jsonFindNumber(job, "color_index", colorRaw);
        props.colorIndex = static_cast<int>(colorRaw);
        props.hasLinetype = jsonFindString(job, "linetype", props.linetype)
                             && !props.linetype.empty();
        double lwRaw = 0.0;
        props.hasLineweight = jsonFindNumber(job, "lineweight", lwRaw);
        props.lineweight = static_cast<int>(lwRaw);
        double flagRaw = 0.0;
        props.hasPlottable = jsonFindNumber(job, "plottable", flagRaw);
        props.plottable = (flagRaw != 0.0);
        props.hasFrozen = jsonFindNumber(job, "frozen", flagRaw);
        props.frozen = (flagRaw != 0.0);
        props.hasOff = jsonFindNumber(job, "off", flagRaw);
        props.off = (flagRaw != 0.0);
        props.hasLocked = jsonFindNumber(job, "locked", flagRaw);
        props.locked = (flagRaw != 0.0);

        bool created = false;
        std::string linetypeError;
        const Acad::ErrorStatus es = upsertLayerRecord(pDb, name, props, created, linetypeError);
        const int layers = countSymbolTable(pDb->layerTableId());
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"updated\":" << ((es == Acad::eOk && !created) ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"linetype_error\":\"" << jsonEscape(linetypeError) << "\""
          << ",\"layers_after\":" << layers << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "write.dimstyle.create") {
        std::string name;
        if (!jsonFindString(job, "name", name) || name.empty())
            name = "ARIADNE_DIMSTYLE";

        // D-class TABLES tier (w3-dimstyle): every property below is OPTIONAL,
        // same hasX upsert convention write.layer.create uses above -- an
        // absent field leaves an existing dimstyle's value untouched.
        // dimse1 travels as a 0/1 number (this file's existing jsonFindNumber
        // convention -- see "closed"/"is_write"/write.layer.create's flags).
        DimStylePropertyArgs props;
        double numRaw = 0.0;
        props.hasDimtxt = jsonFindNumber(job, "dimtxt", numRaw);
        props.dimtxt = numRaw;
        props.hasDimasz = jsonFindNumber(job, "dimasz", numRaw);
        props.dimasz = numRaw;
        props.hasDimexe = jsonFindNumber(job, "dimexe", numRaw);
        props.dimexe = numRaw;
        props.hasDimexo = jsonFindNumber(job, "dimexo", numRaw);
        props.dimexo = numRaw;
        props.hasDimdec = jsonFindNumber(job, "dimdec", numRaw);
        props.dimdec = static_cast<int>(numRaw);
        props.hasDimscale = jsonFindNumber(job, "dimscale", numRaw);
        props.dimscale = numRaw;
        props.hasDimclrd = jsonFindNumber(job, "dimclrd", numRaw);
        props.dimclrd = static_cast<int>(numRaw);
        props.hasDimclre = jsonFindNumber(job, "dimclre", numRaw);
        props.dimclre = static_cast<int>(numRaw);
        props.hasDimclrt = jsonFindNumber(job, "dimclrt", numRaw);
        props.dimclrt = static_cast<int>(numRaw);
        props.hasDimse1 = jsonFindNumber(job, "dimse1", numRaw);
        props.dimse1 = (numRaw != 0.0);

        // p1-dimvars: doubles
        props.hasDimaltf = jsonFindNumber(job, "dimaltf", numRaw);
        props.dimaltf = numRaw;
        props.hasDimaltrnd = jsonFindNumber(job, "dimaltrnd", numRaw);
        props.dimaltrnd = numRaw;
        props.hasDimcen = jsonFindNumber(job, "dimcen", numRaw);
        props.dimcen = numRaw;
        props.hasDimdle = jsonFindNumber(job, "dimdle", numRaw);
        props.dimdle = numRaw;
        props.hasDimdli = jsonFindNumber(job, "dimdli", numRaw);
        props.dimdli = numRaw;
        props.hasDimgap = jsonFindNumber(job, "dimgap", numRaw);
        props.dimgap = numRaw;
        props.hasDimjogang = jsonFindNumber(job, "dimjogang", numRaw);
        props.dimjogang = numRaw;
        props.hasDimlfac = jsonFindNumber(job, "dimlfac", numRaw);
        props.dimlfac = numRaw;
        props.hasDimrnd = jsonFindNumber(job, "dimrnd", numRaw);
        props.dimrnd = numRaw;
        props.hasDimtfac = jsonFindNumber(job, "dimtfac", numRaw);
        props.dimtfac = numRaw;
        props.hasDimtm = jsonFindNumber(job, "dimtm", numRaw);
        props.dimtm = numRaw;
        props.hasDimtp = jsonFindNumber(job, "dimtp", numRaw);
        props.dimtp = numRaw;
        props.hasDimtsz = jsonFindNumber(job, "dimtsz", numRaw);
        props.dimtsz = numRaw;
        props.hasDimtvp = jsonFindNumber(job, "dimtvp", numRaw);
        props.dimtvp = numRaw;
        props.hasDimfxlen = jsonFindNumber(job, "dimfxlen", numRaw);
        props.dimfxlen = numRaw;
        props.hasDimmzf = jsonFindNumber(job, "dimmzf", numRaw);
        props.dimmzf = numRaw;
        props.hasDimaltmzf = jsonFindNumber(job, "dimaltmzf", numRaw);
        props.dimaltmzf = numRaw;

        // p1-dimvars: ints
        props.hasDimadec = jsonFindNumber(job, "dimadec", numRaw);
        props.dimadec = static_cast<int>(numRaw);
        props.hasDimaltd = jsonFindNumber(job, "dimaltd", numRaw);
        props.dimaltd = static_cast<int>(numRaw);
        props.hasDimalttd = jsonFindNumber(job, "dimalttd", numRaw);
        props.dimalttd = static_cast<int>(numRaw);
        props.hasDimalttz = jsonFindNumber(job, "dimalttz", numRaw);
        props.dimalttz = static_cast<int>(numRaw);
        props.hasDimaltu = jsonFindNumber(job, "dimaltu", numRaw);
        props.dimaltu = static_cast<int>(numRaw);
        props.hasDimaltz = jsonFindNumber(job, "dimaltz", numRaw);
        props.dimaltz = static_cast<int>(numRaw);
        props.hasDimarcsym = jsonFindNumber(job, "dimarcsym", numRaw);
        props.dimarcsym = static_cast<int>(numRaw);
        props.hasDimatfit = jsonFindNumber(job, "dimatfit", numRaw);
        props.dimatfit = static_cast<int>(numRaw);
        props.hasDimaunit = jsonFindNumber(job, "dimaunit", numRaw);
        props.dimaunit = static_cast<int>(numRaw);
        props.hasDimazin = jsonFindNumber(job, "dimazin", numRaw);
        props.dimazin = static_cast<int>(numRaw);
        props.hasDimfrac = jsonFindNumber(job, "dimfrac", numRaw);
        props.dimfrac = static_cast<int>(numRaw);
        props.hasDimjust = jsonFindNumber(job, "dimjust", numRaw);
        props.dimjust = static_cast<int>(numRaw);
        props.hasDimlunit = jsonFindNumber(job, "dimlunit", numRaw);
        props.dimlunit = static_cast<int>(numRaw);
        props.hasDimtad = jsonFindNumber(job, "dimtad", numRaw);
        props.dimtad = static_cast<int>(numRaw);
        props.hasDimtdec = jsonFindNumber(job, "dimtdec", numRaw);
        props.dimtdec = static_cast<int>(numRaw);
        props.hasDimtfill = jsonFindNumber(job, "dimtfill", numRaw);
        props.dimtfill = static_cast<int>(numRaw);
        props.hasDimtmove = jsonFindNumber(job, "dimtmove", numRaw);
        props.dimtmove = static_cast<int>(numRaw);
        props.hasDimtolj = jsonFindNumber(job, "dimtolj", numRaw);
        props.dimtolj = static_cast<int>(numRaw);
        props.hasDimtzin = jsonFindNumber(job, "dimtzin", numRaw);
        props.dimtzin = static_cast<int>(numRaw);
        props.hasDimzin = jsonFindNumber(job, "dimzin", numRaw);
        props.dimzin = static_cast<int>(numRaw);

        // p1-dimvars: bools (0/1 number convention, matches dimse1 above)
        props.hasDimalt = jsonFindNumber(job, "dimalt", numRaw);
        props.dimalt = (numRaw != 0.0);
        props.hasDimlim = jsonFindNumber(job, "dimlim", numRaw);
        props.dimlim = (numRaw != 0.0);
        props.hasDimsah = jsonFindNumber(job, "dimsah", numRaw);
        props.dimsah = (numRaw != 0.0);
        props.hasDimsd1 = jsonFindNumber(job, "dimsd1", numRaw);
        props.dimsd1 = (numRaw != 0.0);
        props.hasDimsd2 = jsonFindNumber(job, "dimsd2", numRaw);
        props.dimsd2 = (numRaw != 0.0);
        props.hasDimse2 = jsonFindNumber(job, "dimse2", numRaw);
        props.dimse2 = (numRaw != 0.0);
        props.hasDimsoxd = jsonFindNumber(job, "dimsoxd", numRaw);
        props.dimsoxd = (numRaw != 0.0);
        props.hasDimtih = jsonFindNumber(job, "dimtih", numRaw);
        props.dimtih = (numRaw != 0.0);
        props.hasDimtix = jsonFindNumber(job, "dimtix", numRaw);
        props.dimtix = (numRaw != 0.0);
        props.hasDimtofl = jsonFindNumber(job, "dimtofl", numRaw);
        props.dimtofl = (numRaw != 0.0);
        props.hasDimtoh = jsonFindNumber(job, "dimtoh", numRaw);
        props.dimtoh = (numRaw != 0.0);
        props.hasDimtol = jsonFindNumber(job, "dimtol", numRaw);
        props.dimtol = (numRaw != 0.0);
        props.hasDimupt = jsonFindNumber(job, "dimupt", numRaw);
        props.dimupt = (numRaw != 0.0);
        props.hasDimfxlenOn = jsonFindNumber(job, "dimfxlenon", numRaw);
        props.dimfxlenOn = (numRaw != 0.0);
        props.hasDimtxtdirection = jsonFindNumber(job, "dimtxtdirection", numRaw);
        props.dimtxtdirection = (numRaw != 0.0);

        // p1-dimvars: content strings -- empty is a legitimate "clear"
        // value, so the has-flag is presence alone (unlike the
        // name-resolved fields below).
        props.hasDimapost = jsonFindString(job, "dimapost", props.dimapost);
        props.hasDimpost = jsonFindString(job, "dimpost", props.dimpost);
        props.hasDimmzs = jsonFindString(job, "dimmzs", props.dimmzs);
        props.hasDimaltmzs = jsonFindString(job, "dimaltmzs", props.dimaltmzs);

        // p1-dimvars: single-character decimal separator, travels as a
        // 1-character JSON string
        props.hasDimdsep = jsonFindString(job, "dimdsep", props.dimdsep);

        // p1-dimvars: fill color + lineweight
        props.hasDimtfillclr = jsonFindNumber(job, "dimtfillclr", numRaw);
        props.dimtfillclr = static_cast<int>(numRaw);
        props.hasDimlwd = jsonFindNumber(job, "dimlwd", numRaw);
        props.dimlwd = static_cast<int>(numRaw);
        props.hasDimlwe = jsonFindNumber(job, "dimlwe", numRaw);
        props.dimlwe = static_cast<int>(numRaw);

        // p1-dimvars: ObjectId-typed fields, resolved by NAME -- empty is
        // NOT a meaningful value here (mirrors write.layer.create's
        // "linetype" field exactly).
        props.hasDimblk = jsonFindString(job, "dimblk", props.dimblk) && !props.dimblk.empty();
        props.hasDimblk1 = jsonFindString(job, "dimblk1", props.dimblk1) && !props.dimblk1.empty();
        props.hasDimblk2 = jsonFindString(job, "dimblk2", props.dimblk2) && !props.dimblk2.empty();
        props.hasDimldrblk = jsonFindString(job, "dimldrblk", props.dimldrblk) && !props.dimldrblk.empty();
        props.hasDimltype = jsonFindString(job, "dimltype", props.dimltype) && !props.dimltype.empty();
        props.hasDimltex1 = jsonFindString(job, "dimltex1", props.dimltex1) && !props.dimltex1.empty();
        props.hasDimltex2 = jsonFindString(job, "dimltex2", props.dimltex2) && !props.dimltex2.empty();
        props.hasDimtxsty = jsonFindString(job, "dimtxsty", props.dimtxsty) && !props.dimtxsty.empty();

        bool created = false;
        std::string resolutionError;
        const Acad::ErrorStatus es = upsertDimStyleRecord(pDb, name, props, created, resolutionError);
        const int dimstylesAfter = countSymbolTable(pDb->dimStyleTableId());
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"updated\":" << ((es == Acad::eOk && !created) ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"resolution_error\":\"" << jsonEscape(resolutionError) << "\""
          << ",\"dimstyles_after\":" << dimstylesAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "write.linetype.create") {
        std::string name;
        if (!jsonFindString(job, "name", name) || name.empty())
            name = "ARIADNE_LINETYPE";

        // D-class TABLES tier (w3-ltts): both properties below are OPTIONAL,
        // same hasX upsert convention write.layer.create/write.dimstyle.create
        // use above -- an absent field leaves an existing linetype's value
        // untouched. dash_lengths is a plain [n1,n2,...] JSON number array
        // (jsonFindNumberArray) -- positive=dash, negative=gap, 0=dot (DXF/
        // AutoCAD LINETYPE semantics); supplying it always replaces the WHOLE
        // pattern (see LinetypePropertyArgs' own comment on the empty-array
        // simplification).
        LinetypePropertyArgs props;
        props.hasDescription = jsonFindString(job, "description", props.description);
        props.dashLengths = jsonFindNumberArray(job, "dash_lengths");
        props.hasDashLengths = !props.dashLengths.empty();

        bool created = false;
        const Acad::ErrorStatus es = upsertLinetypeRecord(pDb, name, props, created);
        const int linetypesAfter = countSymbolTable(pDb->linetypeTableId());
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"updated\":" << ((es == Acad::eOk && !created) ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"linetypes_after\":" << linetypesAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "write.textstyle.create") {
        std::string name;
        if (!jsonFindString(job, "name", name) || name.empty())
            name = "ARIADNE_TEXTSTYLE";

        // D-class TABLES tier (w3-ltts): every property below is OPTIONAL,
        // same hasX upsert convention every prior TABLES-tier op uses above --
        // an absent field leaves an existing textstyle's value untouched.
        // Field names match schemas/dwg_graph_ir.v1.schema.json's
        // text_style_record $def (font_file/big_font_file/height), not the
        // raw ObjectARX method names. is_shape_file/is_vertical travel as
        // 0/1 numbers (this file's existing jsonFindNumber convention -- see
        // "closed"/"is_write"/write.layer.create's flags).
        TextStylePropertyArgs props;
        props.hasFontFile = jsonFindString(job, "font_file", props.fontFile);
        props.hasBigFontFile = jsonFindString(job, "big_font_file", props.bigFontFile);
        double numRaw = 0.0;
        props.hasHeight = jsonFindNumber(job, "height", numRaw);
        props.height = numRaw;
        props.hasWidthFactor = jsonFindNumber(job, "width_factor", numRaw);
        props.widthFactor = numRaw;
        props.hasObliqueAngle = jsonFindNumber(job, "oblique_angle", numRaw);
        props.obliqueAngle = numRaw;
        props.hasIsShapeFile = jsonFindNumber(job, "is_shape_file", numRaw);
        props.isShapeFile = (numRaw != 0.0);
        props.hasIsVertical = jsonFindNumber(job, "is_vertical", numRaw);
        props.isVertical = (numRaw != 0.0);

        bool created = false;
        const Acad::ErrorStatus es = upsertTextStyleRecord(pDb, name, props, created);
        const int textstylesAfter = countSymbolTable(pDb->textStyleTableId());
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"updated\":" << ((es == Acad::eOk && !created) ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"textstyles_after\":" << textstylesAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "write.ucs.create") {
        std::string name;
        if (!jsonFindString(job, "name", name) || name.empty())
            name = "ARIADNE_UCS";

        // TABLES tier-2 (p9-tables2): every property below is OPTIONAL, same
        // hasX upsert convention write.layer.create/write.dimstyle.create use
        // -- an absent field leaves an existing UCS record's value untouched.
        // origin/x_axis/y_axis travel as nested {"x","y","z"} objects (this
        // file's first point/vector-valued job args -- see jsonFindPoint3).
        UcsPropertyArgs props;
        props.hasOrigin = jsonFindPoint3(job, "origin", props.originX, props.originY, props.originZ);
        props.hasXAxis = jsonFindPoint3(job, "x_axis", props.xAxisX, props.xAxisY, props.xAxisZ);
        props.hasYAxis = jsonFindPoint3(job, "y_axis", props.yAxisX, props.yAxisY, props.yAxisZ);

        bool created = false;
        const Acad::ErrorStatus es = upsertUcsRecord(pDb, name, props, created);
        const int ucsAfter = countSymbolTable(pDb->UCSTableId());
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"updated\":" << ((es == Acad::eOk && !created) ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"ucs_after\":" << ucsAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "write.view.create") {
        std::string name;
        if (!jsonFindString(job, "name", name) || name.empty())
            name = "ARIADNE_VIEW";

        // TABLES tier-2 (p9-tables2): every property below is OPTIONAL, same
        // hasX upsert convention write.layer.create/write.ucs.create use --
        // an absent field leaves an existing VIEW record's value untouched.
        // center is a 2-component {"x","y"} point; target/view_direction are
        // 3-component {"x","y","z"}. perspective_enabled/front_clip_enabled/
        // back_clip_enabled travel as 0/1 numbers (this file's existing
        // jsonFindNumber convention for boolean-shaped fields).
        ViewPropertyArgs props;
        double centerZUnused = 0.0;  // center is a 2D point; jsonFindPoint3 always fills 3
        props.hasCenter = jsonFindPoint3(job, "center", props.centerX, props.centerY, centerZUnused);
        double numRaw = 0.0;
        props.hasHeight = jsonFindNumber(job, "height", numRaw);
        props.height = numRaw;
        props.hasWidth = jsonFindNumber(job, "width", numRaw);
        props.width = numRaw;
        props.hasTarget = jsonFindPoint3(job, "target", props.targetX, props.targetY, props.targetZ);
        props.hasViewDir = jsonFindPoint3(job, "view_direction", props.viewDirX, props.viewDirY, props.viewDirZ);
        props.hasTwist = jsonFindNumber(job, "twist", numRaw);
        props.twist = numRaw;
        props.hasLensLength = jsonFindNumber(job, "lens_length", numRaw);
        props.lensLength = numRaw;
        double flagRaw = 0.0;
        props.hasPerspective = jsonFindNumber(job, "perspective_enabled", flagRaw);
        props.perspective = (flagRaw != 0.0);
        props.hasFrontClipDist = jsonFindNumber(job, "front_clip_distance", numRaw);
        props.frontClipDist = numRaw;
        props.hasFrontClipOn = jsonFindNumber(job, "front_clip_enabled", flagRaw);
        props.frontClipOn = (flagRaw != 0.0);
        props.hasBackClipDist = jsonFindNumber(job, "back_clip_distance", numRaw);
        props.backClipDist = numRaw;
        props.hasBackClipOn = jsonFindNumber(job, "back_clip_enabled", flagRaw);
        props.backClipOn = (flagRaw != 0.0);

        bool created = false;
        const Acad::ErrorStatus es = upsertViewRecord(pDb, name, props, created);
        const int viewsAfter = countSymbolTable(pDb->viewTableId());
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"updated\":" << ((es == Acad::eOk && !created) ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"views_after\":" << viewsAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "write.vport.create") {
        std::string name;
        if (!jsonFindString(job, "name", name) || name.empty())
            name = "ARIADNE_VPORT";

        // TABLES tier-2 (p9-tables2): every property below is OPTIONAL, same
        // hasX upsert convention write.ucs.create/write.view.create use --
        // an absent field leaves an existing VPORT record's value untouched.
        // lower_left/upper_right/center are 2-component {"x","y"} points;
        // target/view_direction are 3-component {"x","y","z"}. ucs_follow_
        // mode/grid_enabled/snap_enabled/ucs_per_viewport travel as 0/1
        // numbers (this file's existing jsonFindNumber convention for
        // boolean-shaped fields); circle_sides is an integer count.
        VportPropertyArgs props;
        double zUnused = 0.0;  // lower_left/upper_right/center are 2D points;
                               // jsonFindPoint3 always fills x/y/z (see VIEW's
                               // centerZUnused precedent above).
        props.hasLowerLeft = jsonFindPoint3(job, "lower_left", props.lowerLeftX, props.lowerLeftY, zUnused);
        props.hasUpperRight = jsonFindPoint3(job, "upper_right", props.upperRightX, props.upperRightY, zUnused);
        props.hasCenter = jsonFindPoint3(job, "center", props.centerX, props.centerY, zUnused);
        double numRaw = 0.0;
        props.hasHeight = jsonFindNumber(job, "height", numRaw);
        props.height = numRaw;
        props.hasWidth = jsonFindNumber(job, "width", numRaw);
        props.width = numRaw;
        props.hasTarget = jsonFindPoint3(job, "target", props.targetX, props.targetY, props.targetZ);
        props.hasViewDir = jsonFindPoint3(job, "view_direction", props.viewDirX, props.viewDirY, props.viewDirZ);
        props.hasTwist = jsonFindNumber(job, "twist", numRaw);
        props.twist = numRaw;
        double flagRaw = 0.0;
        props.hasUcsFollow = jsonFindNumber(job, "ucs_follow_mode", flagRaw);
        props.ucsFollow = (flagRaw != 0.0);
        props.hasCircleSides = jsonFindNumber(job, "circle_sides", numRaw);
        props.circleSides = static_cast<int>(numRaw);
        props.hasGridEnabled = jsonFindNumber(job, "grid_enabled", flagRaw);
        props.gridEnabled = (flagRaw != 0.0);
        props.hasSnapEnabled = jsonFindNumber(job, "snap_enabled", flagRaw);
        props.snapEnabled = (flagRaw != 0.0);
        props.hasSnapAngle = jsonFindNumber(job, "snap_angle", numRaw);
        props.snapAngle = numRaw;
        props.hasUcsPerViewport = jsonFindNumber(job, "ucs_per_viewport", flagRaw);
        props.ucsPerViewport = (flagRaw != 0.0);

        bool created = false;
        const Acad::ErrorStatus es = upsertVportRecord(pDb, name, props, created);
        const int vportsAfter = countSymbolTable(pDb->viewportTableId());
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"updated\":" << ((es == Acad::eOk && !created) ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"vports_after\":" << vportsAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "write.entity.line") {
        std::string layer;
        jsonFindString(job, "layer", layer);

        std::string startJson;
        std::string endJson;
        jsonFindObject(job, "start", startJson);
        jsonFindObject(job, "end", endJson);

        double sx = 0.0, sy = 0.0, sz = 0.0;
        double ex = 1.0, ey = 0.0, ez = 0.0;
        jsonFindNumber(startJson, "x", sx);
        jsonFindNumber(startJson, "y", sy);
        jsonFindNumber(startJson, "z", sz);
        jsonFindNumber(endJson, "x", ex);
        jsonFindNumber(endJson, "y", ey);
        jsonFindNumber(endJson, "z", ez);

        int modelspaceAfter = 0;
        const Acad::ErrorStatus es = appendLine(
            pDb,
            layer,
            AcGePoint3d(sx, sy, sz),
            AcGePoint3d(ex, ey, ez),
            modelspaceAfter);
        r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"layer\":\"" << jsonEscape(layer) << "\""
          << ",\"start\":[" << sx << "," << sy << "," << sz << "]"
          << ",\"end\":[" << ex << "," << ey << "," << ez << "]"
          << ",\"modelspace_entities_after\":" << modelspaceAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "write.entity.circle") {
        std::string layer;
        jsonFindString(job, "layer", layer);

        std::string centerJson;
        jsonFindObject(job, "center", centerJson);
        double cx = 0.0, cy = 0.0, cz = 0.0;
        jsonFindNumber(centerJson, "x", cx);
        jsonFindNumber(centerJson, "y", cy);
        jsonFindNumber(centerJson, "z", cz);
        double radius = 1.0;
        jsonFindNumber(job, "radius", radius);

        int modelspaceAfter = 0;
        const Acad::ErrorStatus es = appendCircle(
            pDb,
            layer,
            AcGePoint3d(cx, cy, cz),
            radius,
            modelspaceAfter);
        r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"layer\":\"" << jsonEscape(layer) << "\""
          << ",\"center\":[" << cx << "," << cy << "," << cz << "]"
          << ",\"radius\":" << radius
          << ",\"modelspace_entities_after\":" << modelspaceAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.entity.count") {
        std::string type;
        jsonFindString(job, "type", type);
        int total = 0;
        int matching = 0;
        const bool ok = countModelSpaceEntitiesByType(pDb, type, total, matching);
        r << "\"result\":{\"modelspace_entities\":" << total
          << ",\"type\":\"" << jsonEscape(type) << "\""
          << ",\"matching_entities\":" << matching << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "write.xrecord.set") {
        std::string key;
        std::string value;
        jsonFindString(job, "key", key);
        jsonFindString(job, "value", value);
        const Acad::ErrorStatus es = setXrecord(pDb, key, value);
        r << "\"result\":{\"written\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"dictionary\":\"ARIADNE_NATIVE\""
          << ",\"key\":\"" << jsonEscape(key) << "\""
          << ",\"value\":\"" << jsonEscape(value) << "\"},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.xrecord.get") {
        std::string key;
        jsonFindString(job, "key", key);
        std::string value;
        bool found = false;
        const bool ok = getXrecord(pDb, key, value, found);
        r << "\"result\":{\"found\":" << (found ? "true" : "false")
          << ",\"dictionary\":\"ARIADNE_NATIVE\""
          << ",\"key\":\"" << jsonEscape(key) << "\""
          << ",\"value\":\"" << jsonEscape(value) << "\"},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "write.xdata.set") {
        std::string app;
        std::string value;
        jsonFindString(job, "app", app);
        jsonFindString(job, "value", value);
        const Acad::ErrorStatus es = setDatabaseXdata(pDb, app, value);
        r << "\"result\":{\"written\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"app\":\"" << jsonEscape(app) << "\""
          << ",\"value\":\"" << jsonEscape(value) << "\"},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.xdata.get") {
        std::string app;
        jsonFindString(job, "app", app);
        std::string value;
        bool found = false;
        const bool ok = getDatabaseXdata(pDb, app, value, found);
        r << "\"result\":{\"found\":" << (found ? "true" : "false")
          << ",\"app\":\"" << jsonEscape(app) << "\""
          << ",\"value\":\"" << jsonEscape(value) << "\"},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "write.block.simple_create") {
        std::string name;
        jsonFindString(job, "name", name);
        double seedLineNum = 1.0;
        jsonFindNumber(job, "seed_line", seedLineNum);
        bool created = false;
        int definitionCount = 0;
        const Acad::ErrorStatus es = createSimpleBlock(
            pDb,
            name,
            created,
            definitionCount,
            seedLineNum != 0.0);
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"block_definitions_after\":" << definitionCount << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "write.block.insert") {
        std::string name;
        jsonFindString(job, "name", name);
        std::string positionJson;
        jsonFindObject(job, "position", positionJson);
        double x = 0.0, y = 0.0, z = 0.0;
        jsonFindNumber(positionJson, "x", x);
        jsonFindNumber(positionJson, "y", y);
        jsonFindNumber(positionJson, "z", z);
        int modelspaceAfter = 0;
        const Acad::ErrorStatus es = insertBlockReference(
            pDb,
            name,
            AcGePoint3d(x, y, z),
            modelspaceAfter);
        r << "\"result\":{\"inserted\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"position\":[" << x << "," << y << "," << z << "]"
          << ",\"modelspace_entities_after\":" << modelspaceAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.block.count") {
        std::string name;
        jsonFindString(job, "name", name);
        int definitionCount = 0;
        bool targetFound = false;
        std::string namesJson;
        const bool ok = countBlockDefinitions(
            pDb,
            name,
            definitionCount,
            targetFound,
            namesJson);
        r << "\"result\":{\"block_definitions\":" << definitionCount
          << ",\"target_found\":" << (targetFound ? "true" : "false")
          << ",\"target\":\"" << jsonEscape(name) << "\""
          << ",\"names\":" << namesJson << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "write.layout.create") {
        std::string name;
        jsonFindString(job, "name", name);
        bool created = false;
        int layoutCount = 0;
        const Acad::ErrorStatus es = createLayout(pDb, name, created, layoutCount);
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"layouts_after\":" << layoutCount << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.layout.list") {
        int layoutCount = 0;
        std::string namesJson;
        const bool ok = listLayouts(pDb, layoutCount, namesJson);
        r << "\"result\":{\"layouts\":" << layoutCount
          << ",\"names\":" << namesJson << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.xref.list") {
        int xrefCount = 0;
        std::string namesJson;
        const bool ok = listXrefs(pDb, xrefCount, namesJson);
        r << "\"result\":{\"xrefs\":" << xrefCount
          << ",\"names\":" << namesJson << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.layers") {
        int layerCount = 0;
        std::string layersJson;
        const bool ok = listLayerRecords(pDb, layerCount, layersJson);
        r << "\"result\":{\"layers\":" << layerCount
          << ",\"records\":" << layersJson << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.blocks") {
        int blockCount = 0;
        std::string blocksJson;
        const bool ok = listBlockDefinitionsDetailed(pDb, blockCount, blocksJson);
        r << "\"result\":{\"block_definitions\":" << blockCount
          << ",\"records\":" << blocksJson << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.entities") {
        std::string type;
        jsonFindString(job, "type", type);
        double limitN = 1000.0;
        jsonFindNumber(job, "limit", limitN);
        int limit = static_cast<int>(limitN);
        if (limit <= 0)
            limit = 1000;
        int total = 0, matching = 0, returned = 0;
        bool truncated = false;
        std::string entitiesJson;
        const bool ok = listModelSpaceEntities(
            pDb, type, limit, total, matching, returned, truncated, entitiesJson);
        r << "\"result\":{\"modelspace_entities\":" << total
          << ",\"type\":\"" << jsonEscape(type) << "\""
          << ",\"matching_entities\":" << matching
          << ",\"returned\":" << returned
          << ",\"truncated\":" << (truncated ? "true" : "false")
          << ",\"entities\":" << entitiesJson << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.runtime.capabilities") {
        r << "\"result\":" << runtimeCapabilitiesJson(jobHostMode) << ","
          << "\"status\":\"ok\"}";
    }
    else if (op == "live.reactor.enable") {
        bool created = false;
        const bool ok = enableEditorReactor(created);
        r << "\"result\":{\"registered\":" << (gAriadneEditorReactor != nullptr ? "true" : "false")
          << ",\"created\":" << (gAriadneEditorReactor != nullptr ? "true" : "false")
          << ",\"name\":\"AriadneEditorReactor\"},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.reactor.registry") {
        r << "\"result\":" << reactorRegistryJson(jobHostMode) << ","
          << "\"status\":\"ok\"}";
    }
    else if (op == "live.reactor.disable") {
        bool removed = false;
        const bool ok = disableEditorReactor(removed);
        r << "\"result\":{\"registered\":" << (gAriadneEditorReactor != nullptr ? "true" : "false")
          << ",\"removed\":" << (gAriadneEditorReactor == nullptr ? "true" : "false")
          << ",\"name\":\"AriadneEditorReactor\"},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "live.selection.monitor.enable") {
        bool created = false;
        const bool ok = enableSelectionMonitor(created);
        r << "\"result\":{\"registered\":" << (gAriadneSelectionMonitor != nullptr ? "true" : "false")
          << ",\"created\":" << (created ? "true" : "false")
          << ",\"name\":\"AriadneSelectionMonitor\"},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "live.selection.monitor.disable") {
        bool removed = false;
        const bool ok = disableSelectionMonitor(removed);
        r << "\"result\":{\"registered\":" << (gAriadneSelectionMonitor != nullptr ? "true" : "false")
          << ",\"removed\":" << (gAriadneSelectionMonitor == nullptr ? "true" : "false")
          << ",\"name\":\"AriadneSelectionMonitor\"},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.selection.monitor.registry") {
        r << "\"result\":" << selectionMonitorRegistryJson(jobHostMode) << ","
          << "\"status\":\"ok\"}";
    }
    else if (op == "inspect.probe.property_count") {
        // Headless proof of OPM AcRxProperty registration: counts the "Size"
        // member on AriadneProbe::desc() (registered via WITH_PROPERTIES macro).
        const int pc = ariadneProbePropertyCount();
        r << "\"result\":{\"property_count\":" << pc
          << ",\"property\":\"Size\",\"opm_registration\":" << (pc >= 1 ? "true" : "false")
          << ",\"panel_display\":\"attended_only\"},"
          << "\"status\":\"" << (pc >= 0 ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.overrule.registry") {
        r << "\"result\":" << overruleRegistryJson(jobHostMode) << ","
          << "\"status\":\"ok\"}";
    }
    else if (op == "live.overrule.enable") {
        bool created = false;
        const bool ok = enableObjectOverrule(created);
        r << "\"result\":{\"registered\":" << (gAriadneObjectOverrule != nullptr ? "true" : "false")
          << ",\"created\":" << (created ? "true" : "false")
          << ",\"name\":\"AriadneObjectOverrule\""
          << ",\"target\":\"AcDbEntity with AriadneProbe predicate\"},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "live.overrule.disable") {
        bool removed = false;
        const bool ok = disableObjectOverrule(removed);
        r << "\"result\":{\"registered\":" << (gAriadneObjectOverrule != nullptr ? "true" : "false")
          << ",\"removed\":" << (gAriadneObjectOverrule == nullptr ? "true" : "false")
          << ",\"name\":\"AriadneObjectOverrule\""
          << ",\"target\":\"AcDbEntity with AriadneProbe predicate\"},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.jig.host_support") {
        r << "\"result\":" << jigHostSupportJson(jobHostMode) << ","
          << "\"status\":\"ok\"}";
    }
    else if (op == "live.jig.point_probe") {
        r << "\"result\":" << runLineJigProbe(job, jobHostMode) << ","
          << "\"status\":\"ok\"}";
    }
    else if (op == "extend.deep_native.firing_selftest") {
        // M07B: deterministically FIRE the interactive deep-native surfaces with NO
        // acedCommand reentrancy. Enable reactor + overrule + selection monitor,
        // ensure a probe, then OPEN the probe (invokes AriadneObjectOverrule
        // open/close) and SSSetFirst it (invokes AriadneSelectionMonitor
        // pickfirstModified). The reactor's commandWillStart fires on the NEXT
        // command boundary; read it via inspect.deep_native.firing_report from a
        // SECOND command (e.g. the mailbox channel). overrule/selmon captured here.
        bool rc = false, oc = false, sc = false;
        enableEditorReactor(rc);
        enableObjectOverrule(oc);
        enableSelectionMonitor(sc);
        AcDbObjectId probeId;
        bool created = false;
        if (!findFirstProbe(pDb, probeId)) {
            if (appendProbe(pDb, AcGePoint3d(150000.0, 350000.0, 0.0), 3000.0) == Acad::eOk) {
                created = true;
                findFirstProbe(pDb, probeId);
            }
        }
        if (!probeId.isNull()) {                         // FIRE overrule open/close
            AcDbEntity* pE = nullptr;
            if (acdbOpenObject(pE, probeId, AcDb::kForRead) == Acad::eOk && pE != nullptr)
                pE->close();
        }
        bool selFired = false;                           // FIRE selection monitor
        if (!probeId.isNull()) {
            ads_name en;
            if (acdbGetAdsName(en, probeId) == Acad::eOk) {
                ads_name ss;
                if (acedSSAdd(en, NULL, ss) == RTNORM) {
                    if (acedSSSetFirst(NULL, ss) == RTNORM)
                        selFired = true;
                    acedSSFree(ss);
                }
            }
        }
        r << "\"result\":{"
          << "\"host_mode\":\"" << jsonEscape(jobHostMode) << "\""
          << ",\"reactor_registered\":" << (gAriadneEditorReactor != nullptr ? "true" : "false")
          << ",\"overrule_registered\":" << (gAriadneObjectOverrule != nullptr ? "true" : "false")
          << ",\"selection_monitor_registered\":" << (gAriadneSelectionMonitor != nullptr ? "true" : "false")
          << ",\"probe_found_or_created\":" << (!probeId.isNull() ? "true" : "false")
          << ",\"probe_created\":" << (created ? "true" : "false")
          << ",\"overrule_open_calls\":" << gOverruleOpenCalls
          << ",\"overrule_close_calls\":" << gOverruleCloseCalls
          << ",\"selmon_pickfirst_mods\":" << gSelMonPickfirstMods
          << ",\"selmon_command_ends\":" << gSelMonCommandEnds
          << ",\"sssetfirst_ok\":" << (selFired ? "true" : "false")
          << "},\"status\":\"ok\"}";
    }
    else if (op == "inspect.deep_native.firing_report") {
        // M07B: read all three firing registries together. When invoked as a SECOND
        // command after firing_selftest, the reactor's commandWillStart has fired on
        // THIS command's start, so reactor.command_starts >= 1 here.
        r << "\"result\":{"
          << "\"reactor\":" << reactorRegistryJson(jobHostMode) << ","
          << "\"overrule\":" << overruleRegistryJson(jobHostMode) << ","
          << "\"selection_monitor\":" << selectionMonitorRegistryJson(jobHostMode)
          << "},\"status\":\"ok\"}";
    }
    else if (op == "extend.customclass.create") {
        double cx = jsonFindNumberOr(job, "cx", "x", 0.0);
        double cy = jsonFindNumberOr(job, "cy", "y", 0.0);
        double cz = jsonFindNumberOr(job, "cz", "z", 0.0);
        double sz = 1.0;
        jsonFindNumber(job, "size", sz);
        if (sz <= 0.0) sz = 1.0;
        const Acad::ErrorStatus es = appendProbe(pDb, AcGePoint3d(cx, cy, cz), sz);
        int total = 0, probes = 0;
        countModelSpace(pDb, total, probes);
        r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"center\":[" << cx << "," << cy << "," << cz << "]"
          << ",\"size\":" << sz
          << ",\"ariadne_probes_after\":" << probes << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.customclass.count") {
        int total = 0, probes = 0;
        countModelSpace(pDb, total, probes);
        r << "\"result\":{\"ariadne_probes\":" << probes
          << ",\"modelspace_entities\":" << total << "},"
          << "\"status\":\"ok\"}";
    }
    else if (op == "extend.customobject.create") {
        std::string key;
        if (!jsonFindString(job, "key", key) || key.empty())
            key = "record1";
        double valueRaw = 0.0;
        jsonFindNumber(job, "value", valueRaw);
        int recordsAfter = 0;
        const Acad::ErrorStatus es = appendRecord(
            pDb,
            key,
            static_cast<int>(valueRaw),
            recordsAfter);
        r << "\"result\":{\"created\":" << (es == Acad::eOk ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"key\":\"" << key << "\""
          << ",\"value\":" << static_cast<int>(valueRaw)
          << ",\"ariadne_records_after\":" << recordsAfter << "},"
          << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.customobject.count") {
        int records = 0;
        const bool ok = countRecords(pDb, records);
        r << "\"result\":{\"ariadne_records\":" << records << "},"
          << "\"status\":\"" << (ok ? "ok" : "error") << "\"}";
    }
    else if (op == "inspect.protocol.queryx") {
        const bool available = ariadneProbeProtocolAvailable();
        r << "\"result\":{\"probe_protocol_available\":"
          << (available ? "true" : "false")
          << ",\"protocol\":\"AriadneProbeProtocol\"},"
          << "\"status\":\"" << (available ? "ok" : "error") << "\"}";
    }
    else {
        // Not a legacy table op -> it was admitted by a family module (familyHasOp).
        // Route to the owning family handler. If none claims it (HasOp/Dispatch drift),
        // surface OPERATION_DISPATCH_MISMATCH -- never silent.
        const AriadneJobCtx ctx{ job, pDb, jobHostMode };
        if (!tryFamilyDispatch(op, ctx, r)) {
            emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                            "operation '" + op + "' was admitted by a family module but no handler claimed it");
        }
    }

    writeResult(outPath.empty() ? nullptr : outPath.c_str(), r.str());
}

static bool readCommandArg(const ACHAR* prompt, std::wstring& value)
{
    ACHAR buffer[4096] = {};
    const int rc = acedGetString(Adesk::kTrue, prompt, buffer);
    if (rc != RTNORM || buffer[0] == 0)
        return false;
    value = buffer;
    return true;
}

static void clearJobPathOverrides()
{
    gJobInOverride.clear();
    gJobOutOverride.clear();
    gJobHostModeOverride.clear();
}

// M07B live-job-argument contract: the ARIADNE_NATIVE_JOB_ARGS env var points at a
// run-scoped JSON args file {"job_in":..,"job_out":..,"host_mode":..} whose paths
// are forward-slash + UTF-8. Both acedGetEnv (AutoCAD-scoped) and the process env
// are consulted. Returns the file path or empty.
static std::wstring readArgsFileSetting()
{
    wchar_t acadEnv[4096] = {};
    if (acedGetEnv(_T("ARIADNE_NATIVE_JOB_ARGS"), acadEnv, _countof(acadEnv)) == RTNORM &&
        acadEnv[0] != L'\0') {
        return std::wstring(acadEnv);
    }
    const wchar_t* p = _wgetenv(L"ARIADNE_NATIVE_JOB_ARGS");
    if (p != nullptr && p[0] != L'\0')
        return std::wstring(p);
    return std::wstring();
}

static void ariadneNativeJobArgs()
{
    std::wstring inPath;
    std::wstring outPath;
    std::wstring hostMode;

    // Preferred (non-interactive, reproducible): a run-scoped JSON args file named
    // by the ARIADNE_NATIVE_JOB_ARGS env var. Read once, NEVER prompts for keyboard
    // text -> drivable from a startup .scr in a dedicated attended acad.exe. This
    // is what the M07B attended harness uses to run custom ops (e.g.
    // inspect.probe.property_count / extend.customclass.create) without manual
    // input. host_mode defaults to full_autocad (this command path is attended).
    const std::wstring argsPath = readArgsFileSetting();
    if (!argsPath.empty()) {
        const std::string spec = readAllBytes(argsPath.c_str());
        std::string in, out, host;
        if (!jsonFindString(spec, "job_in", in)) jsonFindString(spec, "in", in);
        if (!jsonFindString(spec, "job_out", out)) jsonFindString(spec, "out", out);
        if (!jsonFindString(spec, "host_mode", host))
            host = "full_autocad";
        if (!in.empty()) {
            gJobInOverride = utf8ToWide(in);
            gJobOutOverride = utf8ToWide(out);
            gJobHostModeOverride = utf8ToWide(host);
            acutPrintf(_T("\nARIADNE_NATIVE_JOB_ARGS: args file %ls\n"), argsPath.c_str());
            ariadneNativeJob();
            clearJobPathOverrides();
            return;
        }
        acutPrintf(_T("\nARIADNE_NATIVE_JOB_ARGS: args file %ls missing job_in; falling back to prompts\n"),
                   argsPath.c_str());
    }

    // Documented fallback: interactive prompts (only when the env-file channel is
    // absent). Kept so an operator can still drive the job by hand.
    if (!readCommandArg(_T("\nARIADNE_CAD_JOB_IN: "), inPath) ||
        !readCommandArg(_T("\nARIADNE_CAD_JOB_OUT: "), outPath) ||
        !readCommandArg(_T("\nARIADNE_CAD_JOB_HOST_MODE: "), hostMode)) {
        acutPrintf(_T("\nARIADNE_NATIVE_JOB_ARGS cancelled or missing arguments\n"));
        return;
    }

    gJobInOverride = inPath;
    gJobOutOverride = outPath;
    gJobHostModeOverride = hostMode;
    ariadneNativeJob();
    clearJobPathOverrides();
}

static void ariadneNativeJobMailbox()
{
    gUseMailboxOverride = true;
    ariadneNativeJob();
    gUseMailboxOverride = false;
}

//============================================================================
// Live ARX named-pipe pump (CADAGENT_PUMP) — M02
//
// A single-threaded, MAIN-THREAD, blocking named-pipe server invoked AS an
// AutoCAD command. Running on the document/command thread keeps AcDb access
// safe (no worker-thread marshaling). Wire protocol: length-prefixed frames
// (4-byte little-endian uint32 + UTF-8 JSON body) in BOTH directions. Ops:
// live.echo / live.status / live.list_documents / live.stop. The connect and
// every read use OVERLAPPED I/O with a timeout, so the pump is self-terminating
// and can NEVER hang a headless accoreconsole session. The identical command
// works attended (when the .arx is loaded into a running AutoCAD) and headless
// (accoreconsole), which is how it is protocol-tested without touching a live
// user session. Pipe name + timeout come from ARIADNE_PUMP_PIPE /
// ARIADNE_PUMP_TIMEOUT (defaults: \\.\pipe\ariadne_cad_pump, 30s).
//
// §3 THREAD-SAFETY (worker thread never touches AcDb) — satisfied BY CONSTRUCTION:
//   * CADAGENT_PUMP is registered ACRX_CMD_MODAL and therefore runs on the
//     AutoCAD document/command thread. The named-pipe serve loop, pumpDispatch,
//     and every AcDb call it makes (workingDatabase, getBlockTable,
//     getAcDbObjectId, acdbOpenObject kForRead, countModelSpace) execute on
//     THAT thread.
//   * There is NO worker thread. The overlapped I/O (ReadFile/WriteFile/
//     ConnectNamedPipe + event + WaitForSingleObject timeout) gives async I/O
//     without a second thread, so the rule "worker thread never touches AcDb"
//     holds vacuously: nothing off the main thread ever touches AcDb.
//   * DllMain / acrxEntryPoint start no threads. A future background reader
//     would have to marshal requests to the document thread; the current design
//     avoids this entirely.
//
// §5 WRITE GUARD: the pump is read-only. live.apply_patch hard-returns
//   "disabled" and points at the M05 staged-patch governor (router apply_staged
//   on a staged copy); the pump never opens the db for write and never saves.
//
// CLEAN SHUTDOWN:
//   * In-band: a {"op":"live.stop"} frame sets stop=true; the while-loop exits;
//     FlushFileBuffers -> DisconnectNamedPipe -> CloseHandle(evt) -> CloseHandle(pipe).
//   * Timeout: any read/connect that exceeds ARIADNE_PUMP_TIMEOUT CancelIo's and
//     breaks into the same teardown -> the pump can never hang headless.
//   * gPumpServing is cleared on loop exit so CADAGENT_STATUS reports serving:false.
//============================================================================
static volatile LONG gPumpServing = 0;  // 1 while ariadneCadAgentPump serves a client

static std::wstring pumpPipeName()
{
    wchar_t buf[256] = {};
    const DWORD n = GetEnvironmentVariableW(L"ARIADNE_PUMP_PIPE", buf, 256);
    if (n > 0 && n < 256)
        return std::wstring(buf, n);
    return std::wstring(L"\\\\.\\pipe\\ariadne_cad_pump");
}

static DWORD pumpTimeoutMs()
{
    wchar_t buf[32] = {};
    const DWORD n = GetEnvironmentVariableW(L"ARIADNE_PUMP_TIMEOUT", buf, 32);
    if (n > 0 && n < 32) {
        const int v = _wtoi(buf);
        if (v > 0)
            return static_cast<DWORD>(v) * 1000u;
    }
    return 30000u;
}

static bool pumpReadExact(HANDLE pipe, char* out, DWORD len, HANDLE evt, DWORD timeoutMs)
{
    DWORD got = 0;
    while (got < len) {
        OVERLAPPED ov = {}; ov.hEvent = evt; ResetEvent(evt);
        DWORD chunk = 0;
        const BOOL ok = ReadFile(pipe, out + got, len - got, &chunk, &ov);
        if (!ok) {
            if (GetLastError() != ERROR_IO_PENDING) return false;
            if (WaitForSingleObject(evt, timeoutMs) != WAIT_OBJECT_0) { CancelIo(pipe); return false; }
            if (!GetOverlappedResult(pipe, &ov, &chunk, FALSE)) return false;
        }
        if (chunk == 0) return false;
        got += chunk;
    }
    return true;
}

static bool pumpWriteAll(HANDLE pipe, const char* data, DWORD len, HANDLE evt, DWORD timeoutMs)
{
    DWORD sent = 0;
    while (sent < len) {
        OVERLAPPED ov = {}; ov.hEvent = evt; ResetEvent(evt);
        DWORD chunk = 0;
        const BOOL ok = WriteFile(pipe, data + sent, len - sent, &chunk, &ov);
        if (!ok) {
            if (GetLastError() != ERROR_IO_PENDING) return false;
            if (WaitForSingleObject(evt, timeoutMs) != WAIT_OBJECT_0) { CancelIo(pipe); return false; }
            if (!GetOverlappedResult(pipe, &ov, &chunk, FALSE)) return false;
        }
        sent += chunk;
    }
    return true;
}

static bool pumpWriteFrame(HANDLE pipe, const std::string& body, HANDLE evt, DWORD timeoutMs)
{
    const unsigned int n = static_cast<unsigned int>(body.size());
    char hdr[4] = {
        static_cast<char>(n & 0xFF), static_cast<char>((n >> 8) & 0xFF),
        static_cast<char>((n >> 16) & 0xFF), static_cast<char>((n >> 24) & 0xFF)
    };
    if (!pumpWriteAll(pipe, hdr, 4, evt, timeoutMs)) return false;
    return pumpWriteAll(pipe, body.data(), n, evt, timeoutMs);
}

static std::string pumpDispatch(const std::string& req, bool& stop)
{
    stop = false;
    std::string op;
    jsonFindString(req, "op", op);
    // Host mode (same env-backed setting the job dispatcher uses) lets the pump
    // report honestly whether a full editor is present for attended_only ops.
    // M07B pump-gating: the formerly-stubbed "attended_only" ops execute FOR REAL
    // only in attended AutoCAD. Both the gate AND the reported host_mode derive
    // from the reliable host EXE discriminator (acad.exe vs accoreconsole.exe).
    // acedEditor is non-null in BOTH hosts so it cannot gate; the
    // ARIADNE_CAD_JOB_HOST_MODE env hint is not reliably propagated into the
    // attended process, so the pump does NOT consult it (that would make the
    // reported host_mode inconsistent with the gate). Headless accoreconsole keeps
    // the honest attended_only stub, so the 17/17 headless pump proof is preserved.
    // Command-free AcDb/ADS ops (selection set, highlight) are safe inside the
    // modal CADAGENT_PUMP command; ops that need an acedCommand context
    // (zoom/render) are honestly deferred (acedCommand cannot run reentrantly from
    // inside the pump command).
    const bool attendedHost = hostIsFullAutoCad();
    const std::string hostMode = attendedHost ? "full_autocad" : "coreconsole";
    AcDbDatabase* pDb = acdbHostApplicationServices()->workingDatabase();
    std::ostringstream r; r.precision(kJsonDoublePrecision);
    r << "{\"schema\":\"ariadne.cad_pump_frame.v1\",\"op\":\"" << jsonEscape(op) << "\",";
    if (op == "live.echo") {
        std::string msg;
        jsonFindString(req, "message", msg);
        r << "\"status\":\"ok\",\"echo\":\"" << jsonEscape(msg) << "\"}";
    }
    else if (op == "live.status") {
        int total = 0, probes = 0;
        if (pDb) countModelSpace(pDb, total, probes);
        r << "\"status\":\"ok\",\"pump\":\"running\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
          << ",\"has_database\":" << (pDb ? "true" : "false")
          << ",\"modelspace_entities\":" << total << "}";
    }
    else if (op == "live.list_documents") {
        int total = 0, probes = 0;
        if (pDb) countModelSpace(pDb, total, probes);
        r << "\"status\":\"ok\",\"documents\":[{\"working_database\":"
          << (pDb ? "true" : "false")
          << ",\"modelspace_entities\":" << total << "}]}";
    }
    else if (op == "live.active_document") {
        // Working-db dwg path + model-space handle + entity counts. All pure
        // reads on the document thread; no editor/graphics. originalFileName()
        // is empty for an unsaved headless db -> reported as null, never faked.
        if (pDb == nullptr) {
            r << "\"status\":\"error\",\"reason\":\"no working database\"}";
        } else {
            const ACHAR* fnRaw = pDb->originalFileName();
            const std::string dwgPath = (fnRaw != nullptr) ? acharToAscii(fnRaw) : std::string();
            // Model-space handle via the block table (same idiom as countModelSpace).
            std::string msHandle;
            AcDbBlockTable* pBT = nullptr;
            if (pDb->getBlockTable(pBT, AcDb::kForRead) == Acad::eOk) {
                AcDbBlockTableRecord* pMS = nullptr;
                if (pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForRead) == Acad::eOk) {
                    msHandle = handleOfId(pMS->objectId());
                    pMS->close();
                }
                pBT->close();
            }
            int total = 0, probes = 0;
            countModelSpace(pDb, total, probes);
            r << "\"status\":\"ok\""
              << ",\"dwg_path\":" << (dwgPath.empty() ? std::string("null")
                                       : std::string("\"") + jsonEscape(dwgPath) + "\"")
              << ",\"modelspace_handle\":" << (msHandle.empty() ? std::string("null")
                                       : std::string("\"") + jsonEscape(msHandle) + "\"")
              << ",\"modelspace_entities\":" << total
              << ",\"ariadne_probes\":" << probes << "}";
        }
    }
    else if (op == "live.inspect_entity") {
        // Read one entity by hex handle. Resolve handle -> objectId on the
        // working db, open kForRead, emit the SAME geometry shape as
        // collectModelSpaceGraph. Pure read; not_found is honest (no fake).
        std::string handleHex;
        jsonFindString(req, "handle", handleHex);
        if (pDb == nullptr) {
            r << "\"status\":\"error\",\"reason\":\"no working database\"}";
        } else if (handleHex.empty()) {
            r << "\"status\":\"error\",\"reason\":\"missing handle\"}";
        } else {
#ifdef _UNICODE
            const std::wstring wh(handleHex.begin(), handleHex.end());
            const AcDbHandle h(wh.c_str());
#else
            const AcDbHandle h(handleHex.c_str());
#endif
            AcDbObjectId id;
            if (pDb->getAcDbObjectId(id, false, h) != Acad::eOk || id.isNull()) {
                r << "\"status\":\"not_found\",\"handle\":\"" << jsonEscape(handleHex) << "\"}";
            } else {
                AcDbEntity* pEnt = nullptr;
                if (acdbOpenObject(pEnt, id, AcDb::kForRead) != Acad::eOk || pEnt == nullptr) {
                    r << "\"status\":\"not_found\",\"handle\":\"" << jsonEscape(handleHex)
                      << "\",\"reason\":\"handle resolves but entity open failed (non-entity or erased)\"}";
                } else {
                    const std::string dxfName = (pEnt->isA() != nullptr)
                        ? acharToAscii(pEnt->isA()->name()) : std::string();
                    const std::string layer = acharToAscii(pEnt->layer());
                    const std::string ownerStr = handleOfId(pEnt->ownerId());
                    std::ostringstream e; e.precision(kJsonDoublePrecision);
                    e << "{\"handle\":\"" << jsonEscape(handleHex) << "\""
                      << ",\"dxf_name\":\"" << jsonEscape(dxfName) << "\""
                      << ",\"layer\":\"" << jsonEscape(layer) << "\""
                      << ",\"owner_handle\":\"" << jsonEscape(ownerStr) << "\"";
                    if (AcDbLine* pLine = AcDbLine::cast(pEnt)) {
                        const AcGePoint3d s = pLine->startPoint();
                        const AcGePoint3d en = pLine->endPoint();
                        e << ",\"start\":[" << s.x << "," << s.y << "," << s.z << "]"
                          << ",\"end\":[" << en.x << "," << en.y << "," << en.z << "]";
                    } else if (AcDbArc* pArc = AcDbArc::cast(pEnt)) {
                        const AcGePoint3d c = pArc->center();
                        e << ",\"center\":[" << c.x << "," << c.y << "," << c.z << "]"
                          << ",\"radius\":" << pArc->radius()
                          << ",\"start_angle\":" << pArc->startAngle()
                          << ",\"end_angle\":" << pArc->endAngle();
                    } else if (AcDbCircle* pCir = AcDbCircle::cast(pEnt)) {
                        const AcGePoint3d c = pCir->center();
                        e << ",\"center\":[" << c.x << "," << c.y << "," << c.z << "]"
                          << ",\"radius\":" << pCir->radius();
                    } else if (AcDbBlockReference* pRef = AcDbBlockReference::cast(pEnt)) {
                        const AcGePoint3d p = pRef->position();
                        e << ",\"position\":[" << p.x << "," << p.y << "," << p.z << "]"
                          << ",\"block_record_handle\":\"" << jsonEscape(handleOfId(pRef->blockTableRecord())) << "\"";
                    } else if (AcDbText* pT = AcDbText::cast(pEnt)) {
                        const AcGePoint3d p = pT->position();
                        e << ",\"position\":[" << p.x << "," << p.y << "," << p.z << "]"
                          << ",\"text\":\"" << jsonEscape(acharToAscii(pT->textStringConst())) << "\"";
                    }
                    e << "}";
                    pEnt->close();
                    r << "\"status\":\"ok\",\"entity\":" << e.str() << "}";
                }
            }
        }
    }
    else if (op == "live.apply_patch") {
        // §5: ALWAYS disabled on the live pump. Mutation goes ONLY through the
        // M05 staged-patch governor (router apply_staged on a staged copy); the
        // original DWG is READ-ONLY and the pump never saves.
        r << "\"status\":\"disabled\""
          << ",\"reason\":\"live mutation is disabled; use the M05 staged-patch governor\""
          << ",\"governor\":\"autocad-router.ps1 apply_staged (staged_input.dwg -> staged_output.dwg)\""
          << ",\"original_dwg\":\"read_only\"}";
    }
    else if (op == "live.inspect_selection") {
        if (!attendedHost) {
            r << "\"status\":\"attended_only\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
              << ",\"interactive_editor_required\":true"
              << ",\"reason\":\"editor selection set (acedSSGet) requires a full AutoCAD editor; accoreconsole has no interactive editor\"}";
        } else {
            // Pickfirst (implied) selection set. acedSSGet does NOT start a command,
            // so it is safe to call inside the modal CADAGENT_PUMP command. Honest:
            // an empty pickfirst set returns count 0, never a fabricated selection.
            ads_name ss;
            const int rc = acedSSGet(_T("_I"), nullptr, nullptr, nullptr, ss);
            if (rc != RTNORM) {
                r << "\"status\":\"ok\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
                  << ",\"selection\":[],\"count\":0,\"note\":\"no pickfirst selection set\"}";
            } else {
                Adesk::Int32 len = 0;
                acedSSLength(ss, &len);
                std::ostringstream sel; sel.precision(kJsonDoublePrecision);
                sel << "[";
                bool firstSel = true;
                int emitted = 0;
                for (Adesk::Int32 i = 0; i < len; ++i) {
                    ads_name en;
                    if (acedSSName(ss, i, en) != RTNORM) continue;
                    AcDbObjectId id;
                    if (acdbGetObjectId(id, en) != Acad::eOk || id.isNull()) continue;
                    if (!firstSel) sel << ",";
                    firstSel = false;
                    sel << "\"" << jsonEscape(handleOfId(id)) << "\"";
                    ++emitted;
                }
                sel << "]";
                acedSSFree(ss);
                r << "\"status\":\"ok\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
                  << ",\"selection\":" << sel.str() << ",\"count\":" << emitted << "}";
            }
        }
    }
    else if (op == "live.highlight_handles") {
        if (!attendedHost) {
            r << "\"status\":\"attended_only\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
              << ",\"interactive_editor_required\":true"
              << ",\"reason\":\"entity highlight drives the graphics subsystem; accoreconsole has no graphics device\"}";
        } else {
            // AcDbEntity::highlight() is a const display call (no db write, no
            // command) -> safe inside the pump command. Handles that do not resolve
            // are counted as missed, not faked.
            const std::vector<std::string> handles = jsonFindStringArray(req, "handles");
            int hl = 0, miss = 0;
            for (const std::string& hx : handles) {
#ifdef _UNICODE
                const std::wstring wh(hx.begin(), hx.end());
                const AcDbHandle h(wh.c_str());
#else
                const AcDbHandle h(hx.c_str());
#endif
                AcDbObjectId id;
                if (pDb == nullptr || pDb->getAcDbObjectId(id, false, h) != Acad::eOk || id.isNull()) { ++miss; continue; }
                AcDbEntity* pEnt = nullptr;
                if (acdbOpenObject(pEnt, id, AcDb::kForRead) != Acad::eOk || pEnt == nullptr) { ++miss; continue; }
                if (pEnt->highlight() == Acad::eOk) ++hl; else ++miss;
                pEnt->close();
            }
            r << "\"status\":\"ok\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
              << ",\"requested\":" << static_cast<int>(handles.size())
              << ",\"highlighted\":" << hl << ",\"missed\":" << miss << "}";
        }
    }
    else if (op == "live.clear_highlight") {
        if (!attendedHost) {
            r << "\"status\":\"attended_only\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
              << ",\"interactive_editor_required\":true"
              << ",\"reason\":\"unhighlight/redraw requires the graphics subsystem absent in accoreconsole\"}";
        } else {
            const std::vector<std::string> handles = jsonFindStringArray(req, "handles");
            int cleared = 0, miss = 0;
            for (const std::string& hx : handles) {
#ifdef _UNICODE
                const std::wstring wh(hx.begin(), hx.end());
                const AcDbHandle h(wh.c_str());
#else
                const AcDbHandle h(hx.c_str());
#endif
                AcDbObjectId id;
                if (pDb == nullptr || pDb->getAcDbObjectId(id, false, h) != Acad::eOk || id.isNull()) { ++miss; continue; }
                AcDbEntity* pEnt = nullptr;
                if (acdbOpenObject(pEnt, id, AcDb::kForRead) != Acad::eOk || pEnt == nullptr) { ++miss; continue; }
                if (pEnt->unhighlight() == Acad::eOk) ++cleared; else ++miss;
                pEnt->close();
            }
            r << "\"status\":\"ok\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
              << ",\"requested\":" << static_cast<int>(handles.size())
              << ",\"cleared\":" << cleared << ",\"missed\":" << miss << "}";
        }
    }
    else if (op == "live.zoom_to_handles") {
        if (!attendedHost) {
            r << "\"status\":\"attended_only\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
              << ",\"interactive_editor_required\":true"
              << ",\"reason\":\"viewport zoom needs a live editor view; accoreconsole has no viewport/editor\"}";
        } else {
            // M08N-A3: implement zoom without raw command dispatch. Compute WCS extents
            // for the requested handles and call acedSetCurrentView() with a transient
            // AcDbViewTableRecord. This is safe inside CADAGENT_PUMP (no acedCommand
            // reentrancy, no DB write, no original DWG save).
            const std::vector<std::string> handles = jsonFindStringArray(req, "handles");
            AcDbExtents ext;
            bool haveExt = false;
            int used = 0, miss = 0;
            for (const std::string& hx : handles) {
#ifdef _UNICODE
                const std::wstring wh(hx.begin(), hx.end());
                const AcDbHandle h(wh.c_str());
#else
                const AcDbHandle h(hx.c_str());
#endif
                AcDbObjectId id;
                if (pDb == nullptr || pDb->getAcDbObjectId(id, false, h) != Acad::eOk || id.isNull()) { ++miss; continue; }
                AcDbEntity* pEnt = nullptr;
                if (acdbOpenObject(pEnt, id, AcDb::kForRead) != Acad::eOk || pEnt == nullptr) { ++miss; continue; }
                AcDbExtents one;
                if (pEnt->getGeomExtents(one) == Acad::eOk && one.isValid()) {
                    if (!haveExt) { ext = one; haveExt = true; }
                    else { ext.addExt(one); }
                    ++used;
                } else {
                    ++miss;
                }
                pEnt->close();
            }
            if (!haveExt) {
                r << "\"status\":\"not_found\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
                  << ",\"requested\":" << static_cast<int>(handles.size())
                  << ",\"reason\":\"no requested handle resolved to valid geometric extents\"}";
            } else {
                const AcGePoint3d mn = ext.minPoint();
                const AcGePoint3d mx = ext.maxPoint();
                const double cx = (mn.x + mx.x) * 0.5;
                const double cy = (mn.y + mx.y) * 0.5;
                const double cz = (mn.z + mx.z) * 0.5;
                double width = mx.x - mn.x;
                double height = mx.y - mn.y;
                if (width <= 1.0e-9) width = 1.0;
                if (height <= 1.0e-9) height = 1.0;
                const double pad = 1.15;
                AcDbViewTableRecord view;
                view.setViewDirection(AcGeVector3d(0.0, 0.0, 1.0));
                view.setTarget(AcGePoint3d(cx, cy, cz));
                view.setCenterPoint(AcGePoint2d(cx, cy));
                view.setWidth(width * pad);
                view.setHeight(height * pad);
                const Acad::ErrorStatus es = acedSetCurrentView(&view, nullptr);
                r << "\"status\":\"" << (es == Acad::eOk ? "ok" : "error") << "\""
                  << ",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
                  << ",\"requested\":" << static_cast<int>(handles.size())
                  << ",\"used\":" << used << ",\"missed\":" << miss
                  << ",\"set_current_view_status\":" << static_cast<int>(es)
                  << ",\"center\":[" << cx << "," << cy << "," << cz << "]"
                  << ",\"width\":" << (width * pad)
                  << ",\"height\":" << (height * pad)
                  << ",\"raw_command_dispatch\":false}";
            }
        }
    }
    else if (op == "live.render_view") {
        if (!attendedHost) {
            r << "\"status\":\"attended_only\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
              << ",\"interactive_editor_required\":true"
              << ",\"reason\":\"rendering needs a graphics/render pipeline and viewport; accoreconsole has neither\"}";
        } else {
            r << "\"status\":\"deferred\",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
              << ",\"editor_present\":true"
              << ",\"reason\":\"regen/render requires an acedCommand context; CADAGENT_PUMP is a modal command and acedCommand cannot be invoked reentrantly from the pump loop\""
              << ",\"alternative\":\"trigger REGEN/RENDER from a non-pump command context\"}";
        }
    }
    else if (op == "live.stop") {
        stop = true;
        r << "\"status\":\"ok\",\"stopped\":true}";
    }
    else {
        r << "\"status\":\"not_implemented\",\"reason\":\"unknown op ("
          << "read: live.echo/live.status/live.list_documents/live.active_document/live.inspect_entity; "
          << "write-disabled: live.apply_patch; "
          << "attended_only: live.inspect_selection/live.highlight_handles/live.clear_highlight/live.zoom_to_handles/live.render_view; "
          << "control: live.stop)\"}";
    }
    return r.str();
}

static void ariadneCadAgentPump()
{
    const std::wstring pipeName = pumpPipeName();
    const DWORD timeoutMs = pumpTimeoutMs();
    HANDLE pipe = CreateNamedPipeW(
        pipeName.c_str(),
        PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        1, 65536, 65536, 0, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) {
        acutPrintf(_T("\nCADAGENT_PUMP: CreateNamedPipe failed (%lu)\n"), GetLastError());
        return;
    }
    HANDLE evt = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    OVERLAPPED ov = {}; ov.hEvent = evt; ResetEvent(evt);
    bool ok = false;
    if (ConnectNamedPipe(pipe, &ov)) {
        ok = true;
    }
    else {
        const DWORD err = GetLastError();
        if (err == ERROR_PIPE_CONNECTED) ok = true;
        else if (err == ERROR_IO_PENDING) {
            if (WaitForSingleObject(evt, timeoutMs) == WAIT_OBJECT_0) ok = true;
            else CancelIo(pipe);
        }
    }
    if (!ok) {
        acutPrintf(_T("\nCADAGENT_PUMP: no client connected within timeout; exiting\n"));
        CloseHandle(evt); CloseHandle(pipe); return;
    }
    acutPrintf(_T("\nCADAGENT_PUMP: client connected; serving frames\n"));
    InterlockedExchange(&gPumpServing, 1);
    bool stop = false;
    while (!stop) {
        char hdr[4];
        if (!pumpReadExact(pipe, hdr, 4, evt, timeoutMs)) break;
        const unsigned int n =
            static_cast<unsigned char>(hdr[0]) |
            (static_cast<unsigned char>(hdr[1]) << 8) |
            (static_cast<unsigned char>(hdr[2]) << 16) |
            (static_cast<unsigned char>(hdr[3]) << 24);
        if (n == 0 || n > (1u << 20)) break;
        std::string body(n, '\0');
        if (!pumpReadExact(pipe, &body[0], n, evt, timeoutMs)) break;
        const std::string resp = pumpDispatch(body, stop);
        if (!pumpWriteFrame(pipe, resp, evt, timeoutMs)) break;
    }
    InterlockedExchange(&gPumpServing, 0);
    FlushFileBuffers(pipe);
    DisconnectNamedPipe(pipe);
    CloseHandle(evt);
    CloseHandle(pipe);
    acutPrintf(_T("\nCADAGENT_PUMP: stopped\n"));
}

// Build identifier: compile-time stamp of THIS translation unit. Honest and
// dependency-free; changes on every rebuild.
static std::string pumpBuildId()
{
    return std::string(__DATE__) + " " + std::string(__TIME__);
}

//============================================================================
// CADAGENT_STATUS: non-blocking config/health report. Unlike CADAGENT_PUMP it
// does NOT open a pipe or block; it prints the pump configuration so an operator
// (attended or headless) can verify wiring without starting a serve loop. For
// the single-threaded main-thread model: START == CADAGENT_PUMP (start+serve),
// STOP == sending a {"op":"live.stop"} frame to a serving pump.
//============================================================================
static void ariadneCadAgentStatus()
{
    const std::string pipe = wideToAscii(pumpPipeName());
    const DWORD timeoutMs = pumpTimeoutMs();
    std::string hostMode = wideToAscii(readJobPathSetting(L"ARIADNE_CAD_JOB_HOST_MODE"));
    if (hostMode.empty())
        hostMode = "coreconsole";
    const bool serving = (InterlockedCompareExchange(&gPumpServing, 0, 0) != 0);

    std::ostringstream r; r.precision(kJsonDoublePrecision);
    r << "{\"schema\":\"ariadne.cad_pump_status.v1\""
      << ",\"command\":\"CADAGENT_STATUS\""
      << ",\"build_id\":\"" << jsonEscape(pumpBuildId()) << "\""
      << ",\"pipe_name\":\"" << jsonEscape(pipe) << "\""
      << ",\"timeout_ms\":" << static_cast<unsigned long>(timeoutMs)
      << ",\"host_mode\":\"" << jsonEscape(hostMode) << "\""
      << ",\"serving\":" << (serving ? "true" : "false")
      << ",\"start_command\":\"CADAGENT_PUMP\""
      << ",\"stop_via\":\"frame:{op:live.stop}\""
      << ",\"supported_ops\":[\"live.echo\",\"live.status\",\"live.list_documents\",\"live.active_document\",\"live.inspect_entity\",\"live.apply_patch\",\"live.inspect_selection\",\"live.highlight_handles\",\"live.clear_highlight\",\"live.zoom_to_handles\",\"live.render_view\",\"live.stop\"]"
      << ",\"write_policy\":\"disabled_use_m05_staged_governor\"}";
    acutPrintf(_T("\nCADAGENT_STATUS: %hs\n"), r.str().c_str());
}

//============================================================================
// Module entry point
//============================================================================
extern "C" AcRx::AppRetCode __declspec(dllexport)
acrxEntryPoint(AcRx::AppMsgCode msg, void* pkt)
{
    switch (msg) {
    case AcRx::kInitAppMsg:
        acrxUnlockApplication(pkt);
        acrxRegisterAppMDIAware(pkt);
        if (!loadDbxCore()) {
            acutPrintf(_T("\nAriadne.AcadNative failed to load Ariadne.AcadNativeDbx.dbx\n"));
            return AcRx::kRetError;
        }
        acedRegCmds->addCommand(_T("ARIADNE_NATIVE"),
                                _T("ARIADNE_NATIVE_JOB"),
                                _T("ARIADNE_NATIVE_JOB"),
                                ACRX_CMD_MODAL | ACRX_CMD_SESSION,
                                &ariadneNativeJob);
        acedRegCmds->addCommand(_T("ARIADNE_NATIVE"),
                                _T("ARIADNE_NATIVE_JOB_ARGS"),
                                _T("ARIADNE_NATIVE_JOB_ARGS"),
                                ACRX_CMD_MODAL,
                                &ariadneNativeJobArgs);
        acedRegCmds->addCommand(_T("ARIADNE_NATIVE"),
                                _T("ARIADNE_NATIVE_JOB_MAILBOX"),
                                _T("ARIADNE_NATIVE_JOB_MAILBOX"),
                                ACRX_CMD_MODAL,
                                &ariadneNativeJobMailbox);
        acedRegCmds->addCommand(_T("ARIADNE_NATIVE"),
                                _T("CADAGENT_PUMP"),
                                _T("CADAGENT_PUMP"),
                                ACRX_CMD_MODAL,
                                &ariadneCadAgentPump);
        acedRegCmds->addCommand(_T("ARIADNE_NATIVE"),
                                _T("CADAGENT_STATUS"),
                                _T("CADAGENT_STATUS"),
                                ACRX_CMD_MODAL,
                                &ariadneCadAgentStatus);
#ifndef ARIADNE_NATIVE_CRX
        // Attended-only status UI command (ARIADNE_PALETTE), provided by
        // AriadnePalette.cpp which is in the .arx project ONLY. The headless .crx
        // (ARIADNE_NATIVE_CRX defined) neither links nor registers it.
        ariadneRegisterPaletteCommand();  // arx-only; declared extern "C" at file scope
        acutPrintf(_T("\nAriadne.AcadNative loaded. Commands: ARIADNE_NATIVE_JOB, ARIADNE_NATIVE_JOB_ARGS, ARIADNE_NATIVE_JOB_MAILBOX, CADAGENT_PUMP, CADAGENT_STATUS, ARIADNE_PALETTE\n"));
#else
        acutPrintf(_T("\nAriadne.AcadNative loaded. Commands: ARIADNE_NATIVE_JOB, ARIADNE_NATIVE_JOB_ARGS, ARIADNE_NATIVE_JOB_MAILBOX, CADAGENT_PUMP, CADAGENT_STATUS\n"));
#endif
        break;

    case AcRx::kUnloadAppMsg:
        {
            bool removed = false;
            disableEditorReactor(removed);
            disableSelectionMonitor(removed);
            disableObjectOverrule(removed);
            m08mDisableEditorMonitor(removed);
            m08mDisableDocManagerMonitor(removed);
            m08mDisableLongTransactionMonitor(removed);
        }
        acedRegCmds->removeGroup(_T("ARIADNE_NATIVE"));
        acrxUnloadModule(kAriadneDbxModule);
        break;

    default:
        break;
    }
    return AcRx::kRetOK;
}
