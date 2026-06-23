// families/m08m_handlers.inc — M08M NATIVE: OPM properties + reactors (55 ops).
// T01 OPM properties (33): the dynamic property protocol (AcRxProperty / AcRxMemberCollection over an
//   object) is queryable hostless; the Properties PALETTE is attended. T02 reactors (22): AcDbDatabase/
//   AcDbObject reactors attach+fire hostless (in-transaction modify/erase callbacks); AcEditorReactor
//   needs the editor (attended).
// #included into AriadneNativeJob.cpp; sees all in-TU helpers. m08mHasOp/m08mDispatch lockstep.
// staged-write only; no save/saveAs; no acedCommand. Honest-defer attended (palette/editor-reactor)
// ops with blocker — NO FAKES. See PLAN_M08M.md.
static bool m08mHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08M teammate: return true for this family's implemented op ids
}
static bool m08mDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08M teammate: implement OPM-property + reactor ops
}
