// families/m08f_handlers.inc — M08F READ family: SQLite rich IR schema / query DSL + spatial graph queries.
//
// Owned by the M08F teammate (PR-scoped). #included into AriadneNativeJob.cpp; sees every
// in-TU helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08fHasOp(op): true for every op id this family implements.
//   - m08fDispatch(op, ctx, r): handle it (append "result":{...},"status":"ok") and return true; else false.
// F is read/query-shaped (no DWG mutation). Prefer the existing rich-graph collectors +
// the SQLite IR store (tools/sqlite_ir_store*.py side) where the contract spans planes.
// Use njsonStr for UTF-8 output. NO original DWG writes.
static bool m08fHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08F teammate: return true for this family's op ids
}
static bool m08fDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08F teammate: implement the family's read ops
}
