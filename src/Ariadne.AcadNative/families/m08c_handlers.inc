// families/m08c_handlers.inc — M08C READ family: symbol tables / database metadata.
//
// Owned by the M08C teammate (PR-scoped). #included into AriadneNativeJob.cpp, so it
// sees every in-TU helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08cHasOp(op): true for every op id this family implements (gate admission).
//   - m08cDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"
//     (or emitNativeError-style error) to r and return true; else return false.
// Use the in-TU primitives: njsonStr / serializeObjectCommon / serializeEntityCommon,
// AriadneReadTransaction / AriadneStagedWriteTransaction, resolveHandle, jsonFind*,
// handleOf / handleOfId, the resbuf/xdata serializers. NO original DWG writes.
static bool m08cHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08C teammate: return true for this family's op ids
}
static bool m08cDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08C teammate: implement the family's read ops
}
