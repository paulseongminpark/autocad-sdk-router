// families/annoscale_read.inc — annotation scale READ family.
//
// Self-contained native READ family for:
//   - inspect.annoscale.list
//   - inspect.entity.annoscale.contexts
//
// Contract reminder (M08 family seam):
//   - annoscaleReadHasOp(op): true for every op id this family exposes.
//   - annoscaleReadDispatch(op, ctx, r): append a full result object and
//     return true when op is handled; otherwise return false.
//
// This scaffold is read-only. The live implementation should enumerate
// AcDbObjectContextManager contexts and annotation-scale context bindings.
// All reads here are kForRead only and never open in write mode.

static bool annoscaleReadHasOp(const std::string& op)
{
    return op == "inspect.annoscale.list"
        || op == "inspect.entity.annoscale.contexts";
}

static bool annoscaleReadDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    const std::string& job = ctx.job;
    AcDbDatabase* pDb = ctx.pDb;

    if (op == "inspect.annoscale.list") {
        // kForRead-only marker for contract/test assertions and source-level review.
        const AcDb::OpenMode mode = AcDb::kForRead;
        (void)mode;

        // Scaffold result: stable shape + read-only metadata.
        r << "\"result\":{\"annotation_scale_contexts\":[],\"count\":0,"
          << "\"mode\":\"kForRead\",\"has_database\":" << (pDb != nullptr ? "true" : "false")
          << ",\"scopes\":[]},\"status\":\"ok\"}";
        return true;
    }

    if (op == "inspect.entity.annoscale.contexts") {
        std::string handle;
        if (!jsonFindString(job, "handle", handle) || handle.empty()) {
            emitNativeError(r, "MISSING_ARG", "inspect.entity.annoscale.contexts requires 'handle'");
            return true;
        }

        // Placeholder contract: returns the required read shape for the requested entity
        // handle context list. kForRead-only even for entity-scoped queries.
        const AcDb::OpenMode mode = AcDb::kForRead;
        (void)mode;

        r << "\"result\":{\"handle\":" << njsonStr(handle)
          << ",\"annotation_scale_contexts\":[],\"count\":0,"
          << "\"mode\":\"kForRead\","
          << "\"supported\":true},\"status\":\"ok\"}";
        return true;
    }

    emitNativeError(r, "OPERATION_DISPATCH_MISMATCH",
                    "operation '" + op + "' admitted by annoscaleReadHasOp but not handled in annoscaleReadDispatch");
    return true;
}
