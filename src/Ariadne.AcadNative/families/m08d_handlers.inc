// families/m08d_handlers.inc — M08D READ family: entities / geometry / brep / annotation read.
//
// Owned by the M08D teammate (PR-scoped). #included into AriadneNativeJob.cpp; sees every
// in-TU helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08dHasOp(op): true for every op id this family implements.
//   - m08dDispatch(op, ctx, r): handle it (append "result":{...},"status":"ok") and return true; else false.
// Use serializeEntityCommon for entity-common fields, AriadneReadTransaction for scoped reads,
// resolveHandle for hex->id, the resbuf serializers for xdata. NO original DWG writes.
static bool m08dHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08D teammate: return true for this family's op ids
}
static bool m08dDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08D teammate: implement the family's read ops
}
