// families/m08k_handlers.inc — M08K-T01 NATIVE: custom object/entity lifecycle (45 ops).
// custom AcDbObject/AcDbEntity create/read/roundtrip, class registration (AcRxClass/rxInit), unload.
// Mostly hostless native_arx (DBX-resident). #included into AriadneNativeJob.cpp; sees all in-TU helpers.
// Contract: m08kHasOp(op) admits implemented ops (lockstep w/ dispatch); m08kDispatch handles them.
// staged-write only on ctx.pDb; no save/saveAs; no acedCommand. Honest-defer (out of HasOp) the
// attended-only ops (those needing a running editor/app) with a blocker — NO FAKES. See PLAN_M08K.md.
static bool m08kHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08K teammate: return true for this family's implemented op ids
}
static bool m08kDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08K teammate: implement custom-object lifecycle ops
}
