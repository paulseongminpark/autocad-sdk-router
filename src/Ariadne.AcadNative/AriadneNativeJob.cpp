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
#include <tchar.h>
#include <windows.h>

#include "aced.h"
#include "rxregsvc.h"
#include "dbmain.h"
#include "dbdict.h"
#include "dbents.h"
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
static std::string readAllBytes(const wchar_t* path)
{
    std::ifstream f(path, std::ios::binary);
    if (!f.good())
        return std::string();
    std::ostringstream ss;
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

static std::wstring asciiToWide(const std::string& value)
{
    std::wstring out;
    out.reserve(value.size());
    for (char c : value)
        out.push_back(static_cast<unsigned char>(c));
    return out;
}

static bool moduleDirectory(std::wstring& outDir);

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
    if (text == nullptr)
        return std::string();
#ifdef _UNICODE
    const std::wstring wide(text);
    return wideToAscii(wide);
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
        + "\"base\":[" + std::to_string(x) + "," + std::to_string(y) + "," + std::to_string(z) + "],"
        + "\"point\":[" + std::to_string(ux) + "," + std::to_string(uy) + "," + std::to_string(uz) + "]}";
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
    std::ostringstream names;
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
    std::ostringstream names;
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
    std::ostringstream names;
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

    std::ostringstream r;
    r << "{\"schema\":\"ariadne.autocad_native_job_result.v1\","
      << "\"engine\":\"native_objectarx\","
      << "\"operation\":\"" << op << "\",";

    if (pDb == nullptr) {
        r << "\"status\":\"error\",\"error\":\"no working database\"}";
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
        r << "\"status\":\"error\",\"error\":\"unsupported operation\"}";
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

static void ariadneNativeJobArgs()
{
    std::wstring inPath;
    std::wstring outPath;
    std::wstring hostMode;
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
        acutPrintf(_T("\nAriadne.AcadNative loaded. Commands: ARIADNE_NATIVE_JOB, ARIADNE_NATIVE_JOB_ARGS, ARIADNE_NATIVE_JOB_MAILBOX\n"));
        break;

    case AcRx::kUnloadAppMsg:
        {
            bool removed = false;
            disableEditorReactor(removed);
            disableObjectOverrule(removed);
        }
        acedRegCmds->removeGroup(_T("ARIADNE_NATIVE"));
        acrxUnloadModule(kAriadneDbxModule);
        break;

    default:
        break;
    }
    return AcRx::kRetOK;
}
