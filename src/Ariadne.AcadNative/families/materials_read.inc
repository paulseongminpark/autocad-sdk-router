// families/materials_read.inc — MATERIALS/VISUAL-STYLES family:
// dictionary reads for AcDbMaterial and AcDbVisualStyle from NAMED OBJECT DICTIONARIES.
//
// Owned by the materials-read wave.
// #included into AriadneNativeJob.cpp (before ariadneNativeJob() dispatch),
// so it sees every in-TU helper (njsonStr / jsonFind* / serializeObjectCommon /
// dictionaryEntriesJson / xdataBlocksJson / resolveHandle / AriadneReadTransaction).
// Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - materialsReadHasOp(op): true for every op id this family implements.
//   - materialsReadDispatch(op, ctx, r): append "result":{...},"status":"ok"
//     or emitNativeError(...), return true; else return false.
//
// HIGHEST-LEVEL HARD CONSTRAINT (NO WRITE):
//   READ-only family only: always AcDb::kForRead, no save/saveAs/_QSAVE.
//   This family is dictionary inspection only: ACAD_MATERIAL and ACAD_VISUALSTYLE.
static const char* const kMaterialsReadOpMaterialEnumerate = "inspect.material.enumerate";
static const char* const kMaterialsReadOpMaterialProperties = "inspect.material.properties";
static const char* const kMaterialsReadOpVisualStyleEnumerate = "inspect.visualstyle.enumerate";
static const char* const kMaterialsReadDictMaterial = "ACAD_MATERIAL";
static const char* const kMaterialsReadDictVisualStyle = "ACAD_VISUALSTYLE";
static const char* const kMaterialsClassMaterial = "AcDbMaterial";
static const char* const kMaterialsClassVisualStyle = "AcDbVisualStyle";

static bool materialsReadEnumerateDictionary(const AriadneJobCtx& ctx,
                                            const char* dictName,
                                            std::ostringstream& r)
{
    AriadneReadTransaction rt(ctx.pDb);

    AcDbDictionary* pNOD = nullptr;
    if (ctx.pDb->getNamedObjectsDictionary(pNOD, AcDb::kForRead) != Acad::eOk || pNOD == nullptr) {
        emitNativeError(r, "NOD_OPEN_FAILED", "could not open the named objects dictionary");
        return true;
    }

    AcDbObjectId dictId;
    const Acad::ErrorStatus getAtEs =
        pNOD->getAt(asciiToWide(dictName).c_str(), dictId);
    pNOD->close();
    if (getAtEs != Acad::eOk || dictId.isNull()) {
        emitNativeError(r, "DICT_NOT_FOUND",
                        "named dictionary '" + std::string(dictName) + "' not present in NOD");
        return true;
    }

    AcDbObject* pObj = nullptr;
    if (acdbOpenObject(pObj, dictId, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
        emitNativeError(r, "DICT_OPEN_FAILED",
                        "could not open dictionary '" + std::string(dictName) + "'");
        return true;
    }
    AcDbDictionary* pDict = AcDbDictionary::cast(pObj);
    if (pDict == nullptr) {
        pObj->close();
        emitNativeError(r, "DICT_OPEN_FAILED",
                        "object '" + std::string(dictName) + "' is not a dictionary");
        return true;
    }

    const std::string dictHandle = handleOf(pDict);
    std::ostringstream xrecords;
    xrecords.precision(kJsonDoublePrecision);
    xrecords << "[";
    bool xrecordFirst = true;
    RichGraphCounters counters;
    const std::string entries = dictionaryEntriesJson(pDict, dictHandle, xrecords, xrecordFirst, counters);
    xrecords << "]";
    pDict->close();

    r << "\"result\":{\"dictionary\":" << njsonStr(dictName)
      << ",\"handle\":" << njsonStr(dictHandle)
      << ",\"entry_count\":" << counters.extensionDictionaryEntries
      << ",\"xrecord_count\":" << counters.extensionXrecords
      << ",\"entries\":" << entries
      << ",\"xrecords\":" << xrecords.str()
      << "},\"status\":\"ok\"}";
    return true;
}

// serialize one AcGiMaterialColor: inherit/override method, blend factor, and
// the RGB triple when the color carries an explicit true-color value.
static void materialsReadColorJson(const AcGiMaterialColor& c, std::ostringstream& out)
{
    out << "{\"method\":"
        << (c.method() == AcGiMaterialColor::kOverride ? "\"override\"" : "\"inherit\"")
        << ",\"factor\":" << c.factor();
    const AcCmEntityColor& ec = c.color();
    if (ec.colorMethod() == AcCmEntityColor::kByColor) {
        out << ",\"rgb\":[" << static_cast<int>(ec.red())
            << "," << static_cast<int>(ec.green())
            << "," << static_cast<int>(ec.blue()) << "]";
    }
    out << "}";
}

static bool materialsReadHandleProperties(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string handleHex;
    if (!jsonFindString(ctx.job, "handle", handleHex) || handleHex.empty()) {
        emitNativeError(r, "MISSING_HANDLE", "inspect.material.properties requires a 'handle'");
        return true;
    }

    AcDbObjectId id;
    if (!resolveHandle(ctx.pDb, handleHex, id)) {
        emitNativeError(r, "HANDLE_NOT_FOUND", "no object for handle '" + handleHex + "'");
        return true;
    }

    AriadneReadTransaction rt(ctx.pDb);

    AcDbObject* pObj = nullptr;
    if (acdbOpenObject(pObj, id, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
        emitNativeError(r, "HANDLE_OPEN_FAILED", "could not open handle '" + handleHex + "' for read");
        return true;
    }

    const ACHAR* clsWide = (pObj->isA() != nullptr) ? pObj->isA()->name() : nullptr;
    const std::string cls = (clsWide != nullptr) ? acharToAscii(clsWide) : std::string();
    if (cls != kMaterialsClassMaterial && cls != kMaterialsClassVisualStyle) {
        emitNativeError(r, "INVALID_CLASS",
                        "inspect.material.properties requires AcDbMaterial or AcDbVisualStyle; got '"
                        + cls + "'");
        pObj->close();
        return true;
    }

    resbuf* xd = pObj->xData(nullptr);
    int blockCount = 0;
    int itemCount = 0;
    std::string xdataJson = "[]";
    if (xd != nullptr) {
        xdataJson = xdataBlocksJson(xd, blockCount, itemCount);
        acutRelRb(xd);
    }

    // material-specific rendering properties (the catalog-facing payload this
    // op exists for); visual styles fall back to common object data + xdata.
    std::ostringstream matProps;
    if (cls == kMaterialsClassMaterial) {
        const AcDbMaterial* pMat = AcDbMaterial::cast(pObj);
        if (pMat != nullptr) {
            AcGiMaterialColor ambientColor;
            AcGiMaterialColor diffuseColor;
            AcGiMaterialColor specularColor;
            AcGiMaterialMap diffuseMap;
            AcGiMaterialMap specularMap;
            AcGiMaterialMap opacityMap;
            double gloss = 0.0;
            double opacityPct = 1.0;
            pMat->ambient(ambientColor);
            pMat->diffuse(diffuseColor, diffuseMap);
            pMat->specular(specularColor, specularMap, gloss);
            pMat->opacity(opacityPct, opacityMap);
            const ACHAR* nameW = pMat->name();
            const ACHAR* descW = pMat->description();
            matProps << ",\"name\":" << njsonStr(nameW != nullptr ? acharToAscii(nameW) : std::string())
                     << ",\"description\":" << njsonStr(descW != nullptr ? acharToAscii(descW) : std::string())
                     << ",\"ambient\":";
            materialsReadColorJson(ambientColor, matProps);
            matProps << ",\"diffuse\":";
            materialsReadColorJson(diffuseColor, matProps);
            matProps << ",\"specular\":";
            materialsReadColorJson(specularColor, matProps);
            matProps << ",\"gloss\":" << gloss
                     << ",\"opacity\":" << opacityPct
                     << ",\"mode\":" << static_cast<int>(pMat->mode())
                     << ",\"channel_flags\":" << static_cast<int>(pMat->channelFlags())
                     << ",\"illumination_model\":" << static_cast<int>(pMat->illuminationModel());
        }
    }

    r << "\"result\":{" << serializeObjectCommon(pObj)
      << ",\"kind\":" << (cls == kMaterialsClassMaterial ? njsonStr("material") : njsonStr("visual_style"))
      << matProps.str()
      << ",\"xdata_present\":" << (blockCount > 0 ? "true" : "false")
      << ",\"xdata_block_count\":" << blockCount
      << ",\"xdata_item_count\":" << itemCount
      << ",\"xdata\":" << xdataJson
      << "},\"status\":\"ok\"}";
    pObj->close();
    return true;
}

static bool materialsReadHasOp(const std::string& op)
{
    return op == kMaterialsReadOpMaterialEnumerate
        || op == kMaterialsReadOpMaterialProperties
        || op == kMaterialsReadOpVisualStyleEnumerate;
}

static bool materialsReadDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!materialsReadHasOp(op))
        return false;

    if (op == kMaterialsReadOpMaterialEnumerate) {
        return materialsReadEnumerateDictionary(ctx, kMaterialsReadDictMaterial, r);
    }
    if (op == kMaterialsReadOpVisualStyleEnumerate) {
        return materialsReadEnumerateDictionary(ctx, kMaterialsReadDictVisualStyle, r);
    }
    if (op == kMaterialsReadOpMaterialProperties) {
        return materialsReadHandleProperties(ctx, r);
    }
    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "materialsReadHasOp admitted '" + op + "' but no handler branch matched");
    return true;
}
