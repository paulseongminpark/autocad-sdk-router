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
#include "dbelipse.h"  // T3a: AcDbEllipse (collectModelSpaceGraph read branch)
#include "dbdim.h"     // T3a: AcDbRotatedDimension (collectModelSpaceGraph read branch)
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

static std::wstring asciiToWide(const std::string& value)
{
    std::wstring out;
    out.reserve(value.size());
    for (char c : value)
        out.push_back(static_cast<unsigned char>(c));
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

static std::string jsonEscape(const std::string& value)
{
    std::string out;
    for (char c : value) {
        if (c == '"' || c == '\\')
            out.push_back('\\');
        out.push_back(c);
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
        o << ",\"value_kind\":\"binary\",\"byte_count\":" << rb->resval.rbinary.clen;
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
        Adesk::Int32 loopType = 0;
        AcGePoint2dArray vertices;
        AcGeDoubleArray bulges;
        const Acad::ErrorStatus es = pHatch->getLoopAt(li, loopType, vertices, bulges);
        if (!firstLoop)
            arr << ",";
        firstLoop = false;
        arr << "{\"index\":" << li
            << ",\"loop_type\":" << loopType
            << ",\"status\":\"" << (es == Acad::eOk ? "ok" : "unavailable") << "\""
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

//----------------------------------------------------------------------------
// collectModelSpaceGraph
//
// Pure read: walk ACDB_MODEL_SPACE and emit ONE IR record per entity into a
// nested JSON array (entitiesJson), and the total entity count (total). Modeled
// directly on countModelSpace / countModelSpaceEntitiesByType (BlockTable ->
// ACDB_MODEL_SPACE BTR opened kForRead -> AcDbBlockTableRecordIterator), and it
// uses the same comma-first appendJsonString / jsonEscape idiom as the other
// emitters in this file. Floats use the default ostringstream precision, exactly
// like the existing write.entity.* emitters.
//
// KNOWN FIDELITY LIMITATION (documented M02 follow-up, NOT fixed this session):
// every string field (dxf_name from isA()->name(), layer from pEnt->layer(),
// block reference target name) is funneled through acharToAscii(), which maps any
// code point > 127 to '?'. So a non-ASCII layer/type name -- e.g. the Korean
// layer "설비OPEN" present in the workitem drawings -- is emitted as "????????".
// Widening the ASCII funnel (UTF-8) / vendoring a real JSON library is the
// explicit M02 follow-up; it is deliberately out of this additive lane.
//----------------------------------------------------------------------------
static bool collectModelSpaceGraph(AcDbDatabase* pDb, int& total,
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
            << ",\"space\":\"model\"";

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
        else if (AcDb2dPolyline* p2d = AcDb2dPolyline::cast(pEnt)) {
            arr << ",\"closed\":" << (p2d->isClosed() ? "true" : "false")
                << ",\"vertices\":[";
            AcDbObjectIterator* pVi = p2d->vertexIterator();
            bool vfirst = true;
            for (; pVi != nullptr && !pVi->done(); pVi->step()) {
                AcDb2dVertex* pV = nullptr;
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
        else if (AcDbHatch* pHatch = AcDbHatch::cast(pEnt)) {
            int loopCount = 0, vertexCount = 0;
            const std::string loopsJson = hatchLoopsJson(pHatch, loopCount, vertexCount);
            arr << ",\"pattern_name\":\"" << jsonEscape(acharToAscii(pHatch->patternName())) << "\""
                << ",\"loop_count\":" << loopCount
                << ",\"loops\":" << loopsJson;
            richCounters.hatchLoops += loopCount;
            richCounters.hatchLoopVertices += vertexCount;
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

        arr << "}";
        pEnt->close();
    }

    delete pIt;
    pMS->close();
    arr << "]";
    extensionDictionaries << "]";
    extensionXrecords << "]";
    entitiesJson = arr.str();
    extensionDictionariesJson = extensionDictionaries.str();
    extensionXrecordsJson = extensionXrecords.str();
    return true;
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
            const std::string handle = handleOf(pRec);
            if (!first)
                arr << ",";
            first = false;
            arr << "{\"handle\":\"" << jsonEscape(handle) << "\""
                << ",\"name\":\"" << jsonEscape(name) << "\""
                << ",\"color_index\":" << colorIndex
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

// Block table records + the user-block-definition projection (def geometry is
// referenced from entities[] by owner_handle, not inlined).
static std::string blockTableRecordsJson(AcDbDatabase* pDb, int& btrCount,
                                         int& userBlockDefs,
                                         std::string& blockDefsJson)
{
    btrCount = 0;
    userBlockDefs = 0;
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
            int entityCount = 0;
            AcDbBlockTableRecordIterator* pEIt = nullptr;
            if (pBTR->newIterator(pEIt) == Acad::eOk) {
                for (pEIt->start(); !pEIt->done(); pEIt->step())
                    ++entityCount;
                delete pEIt;
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
            if (!isLayout && !isAnon && !isXref) {
                ++userBlockDefs;
                if (!dfirst)
                    defs << ",";
                dfirst = false;
                defs << "{\"handle\":\"" << jsonEscape(handle) << "\""
                     << ",\"name\":\"" << jsonEscape(name) << "\""
                     << ",\"entity_count\":" << entityCount << "}";
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

    int layerCount = 0, ltCount = 0, tsCount = 0, dsCount = 0, vpCount = 0, raCount = 0;
    const std::string layersJson = layersRichJson(pDb, layerCount);
    const std::string linetypesJson = symbolTableRecordsJson(pDb->linetypeTableId(), ltCount);
    const std::string textStylesJson = symbolTableRecordsJson(pDb->textStyleTableId(), tsCount);
    const std::string dimStylesJson = symbolTableRecordsJson(pDb->dimStyleTableId(), dsCount);
    const std::string viewportsJson = symbolTableRecordsJson(pDb->viewportTableId(), vpCount);
    const std::string appIdsJson = symbolTableRecordsJson(pDb->regAppTableId(), raCount);
    sec << ",\"symbol_tables\":{\"layers\":" << layersJson
        << ",\"linetypes\":" << linetypesJson
        << ",\"text_styles\":" << textStylesJson
        << ",\"dim_styles\":" << dimStylesJson
        << ",\"viewports\":" << viewportsJson
        << ",\"app_ids\":" << appIdsJson << "}";
    addPresent("symbol_tables");

    int btrCount = 0, userBlockDefs = 0;
    std::string blockDefsJson;
    const std::string btrJson = blockTableRecordsJson(pDb, btrCount, userBlockDefs, blockDefsJson);
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
        << ",\"block_table_records\":" << btrCount
        << ",\"block_definitions\":" << userBlockDefs
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
                                           int& definitionCount)
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

// op admitted by any family module? (gate admission for not-yet-legacy family ops)
static bool familyHasOp(const std::string& op)
{
    return m08cHasOp(op) || m08dHasOp(op) || m08eHasOp(op) || m08fHasOp(op)
        || m08gHasOp(op) || m08hHasOp(op)
        || m08kHasOp(op) || m08kcHasOp(op) || m08lHasOp(op) || m08mHasOp(op)
        || m08nHasOp(op);
}

// route op to its owning family module; true if handled (result appended to r)
static bool tryFamilyDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    return m08cDispatch(op, ctx, r) || m08dDispatch(op, ctx, r)
        || m08eDispatch(op, ctx, r) || m08fDispatch(op, ctx, r)
        || m08gDispatch(op, ctx, r) || m08hDispatch(op, ctx, r)
        || m08kDispatch(op, ctx, r) || m08kcDispatch(op, ctx, r)
        || m08lDispatch(op, ctx, r) || m08mDispatch(op, ctx, r)
        || m08nDispatch(op, ctx, r);
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
        double colorRaw = 7.0;
        jsonFindNumber(job, "color_index", colorRaw);
        bool created = false;
        const Acad::ErrorStatus es = ensureLayer(
            pDb,
            name,
            static_cast<int>(colorRaw),
            created);
        const int layers = countSymbolTable(pDb->layerTableId());
        r << "\"result\":{\"created\":" << (created ? "true" : "false")
          << ",\"errorstatus\":" << static_cast<int>(es)
          << ",\"name\":\"" << jsonEscape(name) << "\""
          << ",\"color_index\":" << static_cast<int>(colorRaw)
          << ",\"layers_after\":" << layers << "},"
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
        bool created = false;
        int definitionCount = 0;
        const Acad::ErrorStatus es = createSimpleBlock(
            pDb,
            name,
            created,
            definitionCount);
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
