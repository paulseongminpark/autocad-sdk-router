// families/m08kc_handlers.inc — M08K-T03 NATIVE: constraints / associativity (58 ops).
// AcDbAssoc* network: assoc actions, 2D constraint groups, geometry/dimensional constraints,
// dependencies, variables. Mostly DB-resident objectdbx_capable -> hostless read+create feasible.
// #included into AriadneNativeJob.cpp; sees all in-TU helpers. m08kcHasOp/m08kcDispatch lockstep.
// staged-write only on ctx.pDb; no save/saveAs; no acedCommand. Honest-defer attended/eval-bound ops
// (those needing the constraint solver in a live app) with a blocker — NO FAKES. See PLAN_M08KC.md.
static bool m08kcHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08KC teammate: return true for this family's implemented op ids
}
static bool m08kcDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08KC teammate: implement constraints/associativity ops
}
