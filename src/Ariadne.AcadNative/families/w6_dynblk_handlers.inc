// families/w6_dynblk_handlers.inc -- W6-DYNBLK family: dynamic block REFERENCE
// property read/write.
//
// Owned exclusively by the W6-DYNBLK lane. #included into AriadneNativeJob.cpp (before the
// ariadneNativeJob() dispatcher), so it sees every in-TU helper. Contract
// (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - w6dynblkHasOp(op): true for every op id this family implements (gate admission via
//     familyHasOp).
//   - w6dynblkDispatch(op, ctx, r): if op is yours, append "result":{...},"status":"ok" (or an
//     emitNativeError-style error) to r and return true; else return false.
//
// WHY (census: sdk_census_reaudit_20260706.md, dynamic block section, #1 P1 excellence
// candidate): the registry had only STATIC block ops (write.block.simple_create/insert,
// inspect.block(s)/.iterate, write.entity.blockref, transform.database.*) -- zero coverage of
// AcDbDynBlockReference / AcDbDynBlockReferenceProperty, i.e. reading/setting the visibility
// state, distance, flip, or lookup value actually configured on an INSERTED dynamic block
// reference (door/window/furniture families -- directly relevant to ALM/Sunapse drawing
// corpora). This is a real, buildable API gap, NOT the SDK-wide dynamic block AUTHORING wall
// (confirmed via live Autodesk docs/forums: no vendor, including Autodesk's own .NET/COM APIs,
// can construct a dynamic block's parameter/action graph from public ObjectARX -- correctly out
// of scope and NOT attempted here). AcDbDynBlockReference/AcDbDynBlockReferenceProperty are
// public, documented (dbdynblk.h) utility classes that read/set properties on an
// ALREADY-AUTHORED dynamic block reference; that is exactly this family's surface.
//
// Ops implemented:
//   inspect.dynblock.references -- enumerate block-reference entities in a BTR (model space by
//     default, or block_handle/block_name, mirroring inspect.block.iterate's target resolution),
//     each tagged is_dynamic_block plus (when dynamic) its full property array. dynamic_only
//     (default true) filters the references[] array to dynamic ones; block_reference_count /
//     dynamic_block_reference_count are always the true totals over the whole space regardless
//     of the filter.
//   inspect.dynblock.properties -- the full property array for ONE block reference by handle.
//   write.dynblock.property -- set ONE named property's value on ONE block reference by handle.
//     REAL, PERSISTING primitive (no AriadneStagedWriteTransaction wrapper) -- matches every
//     other real write handler in the codebase (write.entity.line/circle/arc/text/... in
//     m08g/m08h/AriadneNativeJob.cpp, write.block.append_entity in m08e_handlers.inc): mutates
//     ctx.pDb directly so the change survives to the staged-copy DWG the router job already
//     operates on. Still never touches the ORIGINAL file (write_mode policy layer, same as every
//     other write op). Honesty guards: refuses a read-only property (PROPERTY_READ_ONLY), a
//     type mismatch between the property's own AcDb::DwgDataType and the supplied job 'value'
//     (UNSUPPORTED_PROPERTY_TYPE), and a value outside a list-restricted property's
//     getAllowedValues() (VALUE_NOT_ALLOWED) -- the underlying SDK's own setValue() would
//     otherwise silently no-op on an invalid value without returning an error (dbdynblk.h's own
//     documented remark), which this handler treats as a fake-success surface to close, not
//     mimic. Reports value_before/value_after (read back from the SAME property handle instance
//     after setValue, not re-queried) plus bbox_before/bbox_after (AcDbExtents on the block
//     reference entity) and the post-set anonymous_block_handle, so a caller can verify the
//     dynamic block's evaluation graph actually re-ran (geometry changed), not just that the API
//     call returned eOk.
//
// Name resolution nuance this family gets right: AcDbBlockReference::blockTableRecord() on a
// dynamic block instance often points at an ANONYMOUS *U### block (the evaluated/current-state
// geometry), not the named definition a user thinks of (e.g. "Door"). Every op here reports
// BOTH: insert_block_name (blockTableRecord()'s name, verbatim) and block_name (the canonical
// name, resolved via AcDbDynBlockReference::dynamicBlockTableRecord() when is_dynamic_block).
//
// APIs (dbdynblk.h, public/documented):
//   AcDbDynBlockReference(AcDbObjectId) / isDynamicBlock() / dynamicBlockTableRecord() /
//   anonymousBlockTableRecord() / getBlockProperties(AcDbDynBlockReferencePropertyArray&).
//   AcDbDynBlockReferenceProperty::propertyName/propertyType/readOnly/show/
//   visibleInCurrentVisibilityState/description/unitsType/getAllowedValues/value/setValue.
// Concurrency note: every AcDbBlockReference entity this family opens directly (via
// acdbOpenObject, e.g. for the cast/name/position read or the iterator loop) is closed BEFORE
// constructing an AcDbDynBlockReference on the same AcDbObjectId -- AcDbDynBlockReference manages
// its own internal open of the referenced object, so this avoids any nested-open ambiguity on
// the same id. No AcTransaction (AriadneReadTransaction) call ever opens through the utility
// class; the transaction is a pure undo-scope bracket around this family's own acdbOpenObject
// calls, exactly like every other family .inc in this codebase.
//
// Reuses in-TU primitives only: njsonStr / jsonEscape, handleOf / handleOfId, resolveHandle,
// jsonFindString / jsonFindNumber, AriadneReadTransaction, emitNativeError, utf8ToWide /
// acharToAscii, kJsonDoublePrecision. NO original DWG writes (no save/saveAs/_QSAVE, no
// acedCommand/acedCmd) and NO dynamic block AUTHORING (no BlockRepresentationManager /
// EvaluationGraph construction -- out of scope per the census, confirmed SDK-wide impossible).
#include "dbdynblk.h"   // AcDbDynBlockReference / AcDbDynBlockReferenceProperty (also pulls dbeval.h -> AcDbEvalVariant, AcString.h)

// ---- op id constants (single source for HasOp + Dispatch; avoids string drift) -------------
static const char* const kW6dOpDynReferences  = "inspect.dynblock.references";
static const char* const kW6dOpDynProperties  = "inspect.dynblock.properties";
static const char* const kW6dOpDynSetProperty = "write.dynblock.property";

static bool w6dynblkHasOp(const std::string& op)
{
    return op == kW6dOpDynReferences
        || op == kW6dOpDynProperties
        || op == kW6dOpDynSetProperty;
}

// ---- shared helpers ----------------------------------------------------------------------

// DwgDataType -> a stable lowercase label (acdb.h's AcDb::DwgDataType enum). Only the subset
// dynamic block properties realistically carry (real/int16/int32/text, plus 3Real for a rare
// point-shaped property) has a getValue()/setValue() path below; anything else still gets a
// truthful type label even though its value serializes to null (no fabricated value).
static const char* w6dDwgDataTypeName(AcDb::DwgDataType t)
{
    switch (t) {
        case AcDb::kDwgNull:              return "null";
        case AcDb::kDwgReal:              return "real";
        case AcDb::kDwgInt32:             return "int32";
        case AcDb::kDwgInt16:             return "int16";
        case AcDb::kDwgInt8:              return "int8";
        case AcDb::kDwgText:              return "text";
        case AcDb::kDwgBChunk:            return "bchunk";
        case AcDb::kDwgHandle:            return "handle";
        case AcDb::kDwgHardOwnershipId:   return "hard_ownership_id";
        case AcDb::kDwgSoftOwnershipId:   return "soft_ownership_id";
        case AcDb::kDwgHardPointerId:     return "hard_pointer_id";
        case AcDb::kDwgSoftPointerId:     return "soft_pointer_id";
        case AcDb::kDwg3Real:             return "point3d";
        case AcDb::kDwgInt64:             return "int64";
        default:                          return "unrecognized";
    }
}

static const char* w6dUnitsTypeName(AcDbDynBlockReferenceProperty::UnitsType u)
{
    switch (u) {
        case AcDbDynBlockReferenceProperty::kNoUnits:  return "none";
        case AcDbDynBlockReferenceProperty::kAngular:  return "angular";
        case AcDbDynBlockReferenceProperty::kDistance: return "distance";
        case AcDbDynBlockReferenceProperty::kArea:     return "area";
        default:                                       return "unknown";
    }
}

// One AcDbEvalVariant -> a bare JSON token (number / quoted string / point array / null).
// Honest: an unsupported/unreadable type yields null rather than a fabricated value.
static std::string w6dEvalVariantValueJson(const AcDbEvalVariant& v)
{
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    switch (v.getType()) {
        case AcDb::kDwgReal: {
            double d = 0.0;
            if (v.getValue(d) == Acad::eOk) { o << d; return o.str(); }
            break;
        }
        case AcDb::kDwgInt32: {
            Adesk::Int32 i = 0;
            if (v.getValue(i) == Acad::eOk) { o << i; return o.str(); }
            break;
        }
        case AcDb::kDwgInt16: {
            short s = 0;
            if (v.getValue(s) == Acad::eOk) { o << s; return o.str(); }
            break;
        }
        case AcDb::kDwgText: {
            AcString s;
            if (v.getValue(s) == Acad::eOk) return njsonStr(s.kwszPtr());
            break;
        }
        case AcDb::kDwg3Real: {
            AcGePoint3d p;
            if (v.getValue(p) == Acad::eOk) {
                o << "[" << p.x << "," << p.y << "," << p.z << "]";
                return o.str();
            }
            break;
        }
        default:
            break;
    }
    return "null";
}

// Resolve a block-table record's name by id (used for both the raw insert_block_name and the
// dynamic canonical block_name). Standalone acdbOpenObject/close, same shape m08e's
// m08eResolveOptionalObject-adjacent helpers use; caller wraps in AriadneReadTransaction.
static std::string w6dBtrName(AcDbObjectId btrId)
{
    std::string name;
    if (btrId.isNull())
        return name;
    AcDbBlockTableRecord* pBTR = nullptr;
    if (acdbOpenObject(pBTR, btrId, AcDb::kForRead) == Acad::eOk && pBTR != nullptr) {
        const ACHAR* nameRaw = nullptr;
        if (pBTR->getName(nameRaw) == Acad::eOk)
            name = acharToAscii(nameRaw);
        pBTR->close();
    }
    return name;
}

// One AcDbDynBlockReferenceProperty -> a full JSON object (name/type/value/read_only/show/
// visible_in_current_visibility_state/description/units_type/allowed_values).
static std::string w6dSerializeDynProperty(AcDbDynBlockReferenceProperty& prop)
{
    const AcDb::DwgDataType type = prop.propertyType();
    AcDbEvalVariantArray allowed;
    prop.getAllowedValues(allowed);   // non-empty only for list-restricted properties (SDK contract)
    std::ostringstream allowedArr; allowedArr.precision(kJsonDoublePrecision);
    allowedArr << "[";
    for (int i = 0; i < allowed.length(); ++i) {
        if (i > 0) allowedArr << ",";
        allowedArr << w6dEvalVariantValueJson(allowed[i]);
    }
    allowedArr << "]";

    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << "{\"name\":" << njsonStr(prop.propertyName().kwszPtr())
      << ",\"type\":" << njsonStr(w6dDwgDataTypeName(type))
      << ",\"value\":" << w6dEvalVariantValueJson(prop.value())
      << ",\"read_only\":" << (prop.readOnly() ? "true" : "false")
      << ",\"show\":" << (prop.show() ? "true" : "false")
      << ",\"visible_in_current_visibility_state\":" << (prop.visibleInCurrentVisibilityState() ? "true" : "false")
      << ",\"description\":" << njsonStr(prop.description().kwszPtr())
      << ",\"units_type\":" << njsonStr(w6dUnitsTypeName(prop.unitsType()))
      << ",\"allowed_values\":" << allowedArr.str()
      << "}";
    return o.str();
}

// Bare [minx,miny,minz,maxx,maxy,maxz] token (or "null") -- a before/after PAIR needs two
// independently-keyed values, so this returns a value, unlike the existing bboxJsonField()
// (which returns a pre-keyed ",\"bbox\":[...]" fragment for a single-shot append and can't be
// reused twice in one object without a key collision).
static std::string w6dExtentsArrayJson(AcDbEntity* pEnt)
{
    if (pEnt == nullptr)
        return "null";
    AcDbExtents ext;
    if (pEnt->getGeomExtents(ext) != Acad::eOk || !ext.isValid())
        return "null";
    const AcGePoint3d mn = ext.minPoint();
    const AcGePoint3d mx = ext.maxPoint();
    std::ostringstream o; o.precision(kJsonDoublePrecision);
    o << "[" << mn.x << "," << mn.y << "," << mn.z << ","
      << mx.x << "," << mx.y << "," << mx.z << "]";
    return o.str();
}

// Open `id` for read, verify it's an AcDbBlockReference, and return its instance BTR name +
// position + rotation. Closes the entity before returning (caller then constructs
// AcDbDynBlockReference on the same id -- see the file header's concurrency note).
static bool w6dOpenBlockRef(AcDbObjectId id, std::string& instNameOut,
                            AcGePoint3d& posOut, double& rotOut,
                            std::string& errCodeOut, std::string& errMsgOut)
{
    AcDbObject* pObj = nullptr;
    if (acdbOpenObject(pObj, id, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
        errCodeOut = "OBJECT_OPEN_FAILED";
        errMsgOut = "could not open object '" + handleOfId(id) + "' for read";
        return false;
    }
    AcDbBlockReference* pBref = AcDbBlockReference::cast(pObj);
    if (pBref == nullptr) {
        pObj->close();
        errCodeOut = "NOT_A_BLOCK_REFERENCE";
        errMsgOut = "object '" + handleOfId(id) + "' is not an AcDbBlockReference";
        return false;
    }
    instNameOut = w6dBtrName(pBref->blockTableRecord());
    posOut = pBref->position();
    rotOut = pBref->rotation();
    pObj->close();
    return true;
}

// ---- inspect.dynblock.references: enumerate block refs in a BTR (model space by default) ---
static bool w6dHandleDynReferences(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    double dynamicOnlyRaw = 1.0;   // default true: this op's whole point is the dynamic subset
    jsonFindNumber(ctx.job, "dynamic_only", dynamicOnlyRaw);
    const bool dynamicOnly = dynamicOnlyRaw != 0.0;

    AriadneReadTransaction rt(ctx.pDb);

    // Resolve the target BTR -- identical shape to m08eHandleBlockIterate (model space default,
    // or block_handle, or block_name).
    std::string blockHandleArg;
    const bool hasBlockHandle = jsonFindString(ctx.job, "block_handle", blockHandleArg) && !blockHandleArg.empty();
    std::string blockNameArg;
    const bool hasBlockName = jsonFindString(ctx.job, "block_name", blockNameArg) && !blockNameArg.empty();

    AcDbBlockTableRecord* pBTR = nullptr;
    if (hasBlockHandle) {
        AcDbObjectId btrId;
        if (!resolveHandle(ctx.pDb, blockHandleArg, btrId)) {
            emitNativeError(r, "BLOCK_NOT_FOUND", "no object for block_handle '" + blockHandleArg + "'");
            return true;
        }
        AcDbObject* pObj = nullptr;
        if (acdbOpenObject(pObj, btrId, AcDb::kForRead) != Acad::eOk || pObj == nullptr) {
            emitNativeError(r, "BTR_OPEN_FAILED", "could not open block_handle '" + blockHandleArg + "'");
            return true;
        }
        pBTR = AcDbBlockTableRecord::cast(pObj);
        if (pBTR == nullptr) {
            pObj->close();
            emitNativeError(r, "BLOCK_NOT_FOUND", "object '" + blockHandleArg + "' is not a block-table record");
            return true;
        }
    }
    else {
        AcDbBlockTable* pBT = nullptr;
        if (ctx.pDb->getBlockTable(pBT, AcDb::kForRead) != Acad::eOk || pBT == nullptr) {
            emitNativeError(r, "BLOCK_TABLE_OPEN_FAILED", "could not open the block table");
            return true;
        }
        const Acad::ErrorStatus es = hasBlockName
            ? pBT->getAt(asciiToWide(blockNameArg).c_str(), pBTR, AcDb::kForRead)
            : pBT->getAt(ACDB_MODEL_SPACE, pBTR, AcDb::kForRead);
        pBT->close();
        if (es != Acad::eOk || pBTR == nullptr) {
            emitNativeError(r, "BLOCK_NOT_FOUND",
                            hasBlockName ? ("no block named '" + blockNameArg + "'")
                                         : std::string("model space block record not found"));
            return true;
        }
    }

    const std::string btrHandle = handleOf(pBTR);

    AcDbBlockTableRecordIterator* pIt = nullptr;
    if (pBTR->newIterator(pIt) != Acad::eOk) {
        pBTR->close();
        emitNativeError(r, "BTR_ITER_FAILED", "could not iterate block record '" + btrHandle + "'");
        return true;
    }

    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    bool first = true;
    int totalRefs = 0;
    int dynamicRefs = 0;
    for (pIt->start(); !pIt->done(); pIt->step()) {
        AcDbEntity* pEnt = nullptr;
        if (pIt->getEntity(pEnt, AcDb::kForRead) != Acad::eOk || pEnt == nullptr)
            continue;
        AcDbBlockReference* pBref = AcDbBlockReference::cast(pEnt);
        if (pBref == nullptr) {
            pEnt->close();
            continue;
        }
        ++totalRefs;
        const std::string entHandle = handleOf(pEnt);
        const AcDbObjectId entId = pEnt->objectId();
        const AcGePoint3d pos = pBref->position();
        const double rot = pBref->rotation();
        const std::string instName = w6dBtrName(pBref->blockTableRecord());
        pEnt->close();   // close before AcDbDynBlockReference re-opens the same id (see header note)

        AcDbDynBlockReference dynRef(entId);
        const bool isDyn = dynRef.isDynamicBlock();
        if (isDyn)
            ++dynamicRefs;
        if (dynamicOnly && !isDyn)
            continue;

        std::string canonicalName = instName;
        int propCount = 0;
        std::string propsJson = "[]";
        if (isDyn) {
            const AcDbObjectId dynBtrId = dynRef.dynamicBlockTableRecord();
            if (!dynBtrId.isNull()) {
                const std::string dn = w6dBtrName(dynBtrId);
                if (!dn.empty())
                    canonicalName = dn;
            }
            AcDbDynBlockReferencePropertyArray props;
            dynRef.getBlockProperties(props);
            propCount = props.length();
            std::ostringstream parr; parr.precision(kJsonDoublePrecision);
            parr << "[";
            for (int i = 0; i < props.length(); ++i) {
                if (i > 0) parr << ",";
                parr << w6dSerializeDynProperty(props[i]);
            }
            parr << "]";
            propsJson = parr.str();
        }

        if (!first) arr << ",";
        first = false;
        arr << "{\"handle\":" << njsonStr(entHandle)
            << ",\"block_name\":" << njsonStr(canonicalName)
            << ",\"insert_block_name\":" << njsonStr(instName)
            << ",\"is_dynamic_block\":" << (isDyn ? "true" : "false")
            << ",\"position\":[" << pos.x << "," << pos.y << "," << pos.z << "]"
            << ",\"rotation\":" << rot
            << ",\"property_count\":" << propCount
            << ",\"properties\":" << propsJson
            << "}";
    }
    delete pIt;
    pBTR->close();
    arr << "]";

    r << "\"result\":{\"block_handle\":" << njsonStr(btrHandle)
      << ",\"block_reference_count\":" << totalRefs
      << ",\"dynamic_block_reference_count\":" << dynamicRefs
      << ",\"dynamic_only\":" << (dynamicOnly ? "true" : "false")
      << ",\"references\":" << arr.str()
      << "},\"status\":\"ok\"}";
    return true;
}

// ---- inspect.dynblock.properties: full property array for ONE block ref by handle ----------
static bool w6dHandleDynProperties(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string handleHex;
    if (!jsonFindString(ctx.job, "handle", handleHex) || handleHex.empty()) {
        emitNativeError(r, "MISSING_HANDLE", "inspect.dynblock.properties requires a 'handle'");
        return true;
    }

    AriadneReadTransaction rt(ctx.pDb);

    AcDbObjectId id;
    if (!resolveHandle(ctx.pDb, handleHex, id)) {
        emitNativeError(r, "HANDLE_NOT_FOUND", "no object for handle '" + handleHex + "'");
        return true;
    }

    std::string instName, errCode, errMsg;
    AcGePoint3d pos; double rot = 0.0;
    if (!w6dOpenBlockRef(id, instName, pos, rot, errCode, errMsg)) {
        emitNativeError(r, errCode.c_str(), errMsg);
        return true;
    }

    AcDbDynBlockReference dynRef(id);
    const bool isDyn = dynRef.isDynamicBlock();
    std::string canonicalName = instName;
    AcDbDynBlockReferencePropertyArray props;
    if (isDyn) {
        const AcDbObjectId dynBtrId = dynRef.dynamicBlockTableRecord();
        if (!dynBtrId.isNull()) {
            const std::string dn = w6dBtrName(dynBtrId);
            if (!dn.empty())
                canonicalName = dn;
        }
        dynRef.getBlockProperties(props);
    }

    std::ostringstream arr; arr.precision(kJsonDoublePrecision);
    arr << "[";
    for (int i = 0; i < props.length(); ++i) {
        if (i > 0) arr << ",";
        arr << w6dSerializeDynProperty(props[i]);
    }
    arr << "]";

    r << "\"result\":{\"handle\":" << njsonStr(handleOfId(id))
      << ",\"block_name\":" << njsonStr(canonicalName)
      << ",\"insert_block_name\":" << njsonStr(instName)
      << ",\"is_dynamic_block\":" << (isDyn ? "true" : "false")
      << ",\"position\":[" << pos.x << "," << pos.y << "," << pos.z << "]"
      << ",\"rotation\":" << rot
      << ",\"property_count\":" << props.length()
      << ",\"properties\":" << arr.str()
      << "},\"status\":\"ok\"}";
    return true;
}

// ---- write.dynblock.property: set ONE named property on ONE block ref by handle ------------
// REAL, PERSISTING write (no AriadneStagedWriteTransaction) -- see file header. Job args:
// {"handle": "<hex>", "property_name": "<name>", "value": <number|string>}.
static bool w6dHandleSetDynProperty(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string handleHex;
    if (!jsonFindString(ctx.job, "handle", handleHex) || handleHex.empty()) {
        emitNativeError(r, "MISSING_HANDLE", "write.dynblock.property requires a 'handle'");
        return true;
    }
    std::string propName;
    if (!jsonFindString(ctx.job, "property_name", propName) || propName.empty()) {
        emitNativeError(r, "MISSING_PROPERTY_NAME", "write.dynblock.property requires a 'property_name'");
        return true;
    }
    std::string valueStr;
    const bool hasValueStr = jsonFindString(ctx.job, "value", valueStr);
    double valueNum = 0.0;
    const bool hasValueNum = jsonFindNumber(ctx.job, "value", valueNum);
    if (!hasValueStr && !hasValueNum) {
        emitNativeError(r, "MISSING_VALUE", "write.dynblock.property requires a 'value'");
        return true;
    }

    AcDbObjectId id;
    if (!resolveHandle(ctx.pDb, handleHex, id)) {
        emitNativeError(r, "HANDLE_NOT_FOUND", "no object for handle '" + handleHex + "'");
        return true;
    }

    std::string instName, errCode, errMsg;
    AcGePoint3d pos; double rot = 0.0;
    if (!w6dOpenBlockRef(id, instName, pos, rot, errCode, errMsg)) {
        emitNativeError(r, errCode.c_str(), errMsg);
        return true;
    }

    AcDbDynBlockReference dynRef(id);
    if (!dynRef.isDynamicBlock()) {
        emitNativeError(r, "NOT_A_DYNAMIC_BLOCK",
                        "block reference '" + handleHex + "' has no dynamic block properties");
        return true;
    }

    AcDbDynBlockReferencePropertyArray props;
    dynRef.getBlockProperties(props);
    int targetIdx = -1;
    for (int i = 0; i < props.length(); ++i) {
        if (acharToAscii(props[i].propertyName().kwszPtr()) == propName) { targetIdx = i; break; }
    }
    if (targetIdx < 0) {
        emitNativeError(r, "PROPERTY_NOT_FOUND",
                        "no dynamic property named '" + propName + "' on '" + handleHex + "'");
        return true;
    }

    AcDbDynBlockReferenceProperty& target = props[targetIdx];
    if (target.readOnly()) {
        emitNativeError(r, "PROPERTY_READ_ONLY", "dynamic property '" + propName + "' is read-only");
        return true;
    }

    const AcDb::DwgDataType ptype = target.propertyType();
    AcDbEvalVariant newVal;
    bool built = false;
    switch (ptype) {
        case AcDb::kDwgReal:
            if (hasValueNum) { newVal = AcDbEvalVariant(valueNum); built = true; }
            break;
        case AcDb::kDwgInt32:
            if (hasValueNum) { newVal = AcDbEvalVariant(static_cast<Adesk::Int32>(valueNum)); built = true; }
            break;
        case AcDb::kDwgInt16:
            if (hasValueNum) { newVal = AcDbEvalVariant(static_cast<short>(valueNum)); built = true; }
            break;
        case AcDb::kDwgText:
            if (hasValueStr) { newVal = AcDbEvalVariant(utf8ToWide(valueStr).c_str()); built = true; }
            break;
        default:
            break;
    }
    if (!built) {
        emitNativeError(r, "UNSUPPORTED_PROPERTY_TYPE",
                        "dynamic property '" + propName + "' has type " + w6dDwgDataTypeName(ptype) +
                        "; write.dynblock.property supports real/int16/int32/text, and the supplied "
                        "'value' JSON kind must match (number for real/int16/int32, string for text)");
        return true;
    }

    // Respect a list-restricted property's declared allowed values -- setValue() itself would
    // otherwise silently no-op on an invalid value without an error (dbdynblk.h's own documented
    // remark); reject up front instead of reporting a fake success.
    AcDbEvalVariantArray allowed;
    target.getAllowedValues(allowed);
    if (allowed.length() > 0) {
        bool matches = false;
        for (int i = 0; i < allowed.length(); ++i) {
            if (allowed[i] == newVal) { matches = true; break; }
        }
        if (!matches) {
            emitNativeError(r, "VALUE_NOT_ALLOWED",
                            "requested value for '" + propName + "' is not among the " +
                            std::to_string(allowed.length()) + " allowed values");
            return true;
        }
    }

    AcDbEntity* pEntBefore = nullptr;
    std::string bboxBefore = "null";
    if (acdbOpenObject(pEntBefore, id, AcDb::kForRead) == Acad::eOk && pEntBefore != nullptr) {
        bboxBefore = w6dExtentsArrayJson(pEntBefore);
        pEntBefore->close();
    }

    const std::string valueBeforeJson = w6dEvalVariantValueJson(target.value());
    const Acad::ErrorStatus setEs = target.setValue(newVal);
    const std::string valueAfterJson = w6dEvalVariantValueJson(target.value());

    std::string bboxAfter = "null";
    AcDbEntity* pEntAfter = nullptr;
    if (acdbOpenObject(pEntAfter, id, AcDb::kForRead) == Acad::eOk && pEntAfter != nullptr) {
        bboxAfter = w6dExtentsArrayJson(pEntAfter);
        pEntAfter->close();
    }

    const AcDbObjectId anonId = dynRef.anonymousBlockTableRecord();

    r << "\"result\":{\"handle\":" << njsonStr(handleOfId(id))
      << ",\"property_name\":" << njsonStr(propName)
      << ",\"property_type\":" << njsonStr(w6dDwgDataTypeName(ptype))
      << ",\"requested_value\":" << w6dEvalVariantValueJson(newVal)
      << ",\"value_before\":" << valueBeforeJson
      << ",\"value_after\":" << valueAfterJson
      << ",\"changed\":" << (valueBeforeJson != valueAfterJson ? "true" : "false")
      << ",\"bbox_before\":" << bboxBefore
      << ",\"bbox_after\":" << bboxAfter
      << ",\"anonymous_block_handle\":" << (anonId.isNull() ? std::string("null") : njsonStr(handleOfId(anonId)))
      << ",\"staged_rolled_back\":false"
      << ",\"errorstatus\":" << static_cast<int>(setEs)
      << "},\"status\":\"" << (setEs == Acad::eOk ? "ok" : "error") << "\"}";
    return true;
}

static bool w6dynblkDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (op == kW6dOpDynReferences)
        return w6dHandleDynReferences(ctx, r);
    if (op == kW6dOpDynProperties)
        return w6dHandleDynProperties(ctx, r);
    if (op == kW6dOpDynSetProperty)
        return w6dHandleSetDynProperty(ctx, r);
    return false;
}
