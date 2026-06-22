// families/m08e_handlers.inc — M08E READ family: blocks / xrefs-layouts-paperspace / dictionaries-xdata-xrecords.
//
// Owned by the M08E teammate (PR-scoped). #included into AriadneNativeJob.cpp; sees every
// in-TU helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08eHasOp(op): true for every op id this family implements.
//   - m08eDispatch(op, ctx, r): handle it (append "result":{...},"status":"ok") and return true; else false.
// Use handleOf/handleOfId for block/dict references, the resbuf/xdata serializers for
// xrecords/xdata, AriadneReadTransaction for scoped reads. NO original DWG writes.
static bool m08eHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08E teammate: return true for this family's op ids
}
static bool m08eDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08E teammate: implement the family's read ops
}
