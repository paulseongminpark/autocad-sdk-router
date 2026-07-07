// families/annoscale_read.inc — annotation scale READ family.
//
// Self-contained native READ family for:
//   - inspect.annoscale.list
//   - inspect.entity.annoscale.contexts
//
// Contract reminder (M08 family seam):
//   - annoscaleReadHasOp(op): true for every op id this family exposes.
//   - dispatch: append a full result object and return true when op is
//     handled; return false for ops this family does not own (the guard on
//     HasOp is what lets tryFamilyDispatch fall through to later families).
//
// w7-native hardening: the original drop was a scaffold that returned
// hardcoded empty results while the registry said 'implemented' — the live
// verify gate rejected that as fake success. This version does the real
// reads: AcDbObjectContextManager / ACDB_ANNOTATIONSCALES_COLLECTION
// enumeration for the drawing, and AcDbObjectContextInterface (protocol
// extension) participation queries per entity.
// All reads here are kForRead only and never open in write mode.

static bool annoscaleReadHasOp(const std::string& op)
{
    return op == "inspect.annoscale.list"
        || op == "inspect.entity.annoscale.contexts";
}

// serialize ONE annotation-scale context. pCtx is a caller-owned COPY from
// AcDbObjectContextCollectionIterator::getContext (the caller deletes it).
static void annoscaleReadEmitScale(const AcDbObjectContext* pCtx, bool isCurrent,
                                   std::ostringstream& out)
{
    AcString name;
    pCtx->getName(name);
    double paperUnits = 0.0;
    double drawingUnits = 0.0;
    double scaleRatio = 0.0;
    bool haveUnits = false;
    const AcDbAnnotationScale* pScale = AcDbAnnotationScale::cast(pCtx);
    if (pScale != nullptr) {
        haveUnits = (pScale->getPaperUnits(paperUnits) == Acad::eOk)
                 && (pScale->getDrawingUnits(drawingUnits) == Acad::eOk)
                 && (pScale->getScale(scaleRatio) == Acad::eOk);
    }
    out << "{\"name\":" << njsonStr(acharToAscii(name.kACharPtr()))
        << ",\"unique_identifier\":" << static_cast<long long>(pCtx->uniqueIdentifier())
        << ",\"is_current\":" << (isCurrent ? "true" : "false");
    if (haveUnits) {
        out << ",\"paper_units\":" << paperUnits
            << ",\"drawing_units\":" << drawingUnits
            << ",\"scale\":" << scaleRatio;
    }
    out << "}";
}

static bool annoscaleReadListScales(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    // kForRead-only marker for contract/test assertions and source-level review.
    const AcDb::OpenMode mode = AcDb::kForRead;
    (void)mode;

    if (ctx.pDb == nullptr) {
        emitNativeError(r, "NO_DATABASE", "no working database for annotation scale read");
        return true;
    }
    AriadneReadTransaction rt(ctx.pDb);

    AcDbObjectContextManager* pMgr = ctx.pDb->objectContextManager();
    if (pMgr == nullptr) {
        emitNativeError(r, "CONTEXT_MANAGER_UNAVAILABLE",
                        "database has no object context manager");
        return true;
    }
    AcDbObjectContextCollection* pColl =
        pMgr->contextCollection(ACDB_ANNOTATIONSCALES_COLLECTION);
    if (pColl == nullptr) {
        emitNativeError(r, "ANNOSCALE_COLLECTION_MISSING",
                        "ACDB_ANNOTATIONSCALES context collection not present");
        return true;
    }

    // currentContext returns an internal pointer (ownership stays with the
    // collection — only read its id, never delete it).
    const AcDbObjectContext* pCurrent = pColl->currentContext(nullptr);
    const long long currentId =
        (pCurrent != nullptr) ? static_cast<long long>(pCurrent->uniqueIdentifier()) : 0;

    int count = 0;
    std::ostringstream scales;
    AcDbObjectContextCollectionIterator* pIter = pColl->newIterator();
    if (pIter != nullptr) {
        for (pIter->start(); !pIter->done(); pIter->next()) {
            AcDbObjectContext* pCtx = nullptr;  // getContext returns a COPY we own
            if (pIter->getContext(pCtx) != Acad::eOk || pCtx == nullptr)
                continue;
            if (count > 0)
                scales << ",";
            const bool isCurrent = (pCurrent != nullptr)
                && (static_cast<long long>(pCtx->uniqueIdentifier()) == currentId);
            annoscaleReadEmitScale(pCtx, isCurrent, scales);
            ++count;
            delete pCtx;
        }
        delete pIter;
    }

    r << "\"result\":{\"collection\":\"ACDB_ANNOTATIONSCALES\""
      << ",\"count\":" << count
      << ",\"annotation_scale_contexts\":[" << scales.str() << "]"
      << ",\"mode\":\"kForRead\"},\"status\":\"ok\"}";
    return true;
}

static bool annoscaleReadEntityContexts(const AriadneJobCtx& ctx, std::ostringstream& r)
{
    std::string handleHex;
    if (!jsonFindString(ctx.job, "handle", handleHex) || handleHex.empty()) {
        emitNativeError(r, "MISSING_ARG",
                        "inspect.entity.annoscale.contexts requires 'handle'");
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
        emitNativeError(r, "HANDLE_OPEN_FAILED",
                        "could not open handle '" + handleHex + "' for read");
        return true;
    }
    const ACHAR* clsWide = (pObj->isA() != nullptr) ? pObj->isA()->name() : nullptr;
    const std::string cls = (clsWide != nullptr) ? acharToAscii(clsWide) : std::string();

    // annotative participation is exposed through a class-level protocol
    // extension; queryX returns null when the class is not annotative-capable.
    AcDbObjectContextInterface* pIface =
        AcDbObjectContextInterface::cast(pObj->queryX(AcDbObjectContextInterface::desc()));
    const bool supports = (pIface != nullptr)
        && pIface->supportsCollection(pObj, ACDB_ANNOTATIONSCALES_COLLECTION);

    int count = 0;
    std::ostringstream names;
    if (supports) {
        AcDbObjectContextManager* pMgr = ctx.pDb->objectContextManager();
        AcDbObjectContextCollection* pColl =
            (pMgr != nullptr) ? pMgr->contextCollection(ACDB_ANNOTATIONSCALES_COLLECTION)
                              : nullptr;
        AcDbObjectContextCollectionIterator* pIter =
            (pColl != nullptr) ? pColl->newIterator() : nullptr;
        if (pIter != nullptr) {
            for (pIter->start(); !pIter->done(); pIter->next()) {
                AcDbObjectContext* pCtx = nullptr;  // owned copy (see list handler)
                if (pIter->getContext(pCtx) != Acad::eOk || pCtx == nullptr)
                    continue;
                if (pIface->hasContext(pObj, *pCtx)) {
                    AcString name;
                    pCtx->getName(name);
                    if (count > 0)
                        names << ",";
                    names << njsonStr(acharToAscii(name.kACharPtr()));
                    ++count;
                }
                delete pCtx;
            }
            delete pIter;
        }
    }

    r << "\"result\":{\"handle\":" << njsonStr(handleHex)
      << ",\"class_name\":" << njsonStr(cls)
      << ",\"supports_annotation_scales\":" << (supports ? "true" : "false")
      << ",\"annotation_scale_contexts\":[" << names.str() << "]"
      << ",\"count\":" << count
      << ",\"mode\":\"kForRead\"},\"status\":\"ok\"}";
    pObj->close();
    return true;
}

static bool annoscaleReadDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    if (!annoscaleReadHasOp(op))
        return false;

    if (op == "inspect.annoscale.list")
        return annoscaleReadListScales(ctx, r);
    if (op == "inspect.entity.annoscale.contexts")
        return annoscaleReadEntityContexts(ctx, r);

    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "operation '" + op + "' admitted by annoscaleReadHasOp but not handled in annoscaleReadDispatch");
    return true;
}
