// families/m08l_handlers.inc — M08L NATIVE: graphics system (27 ops).
// T01 WorldDraw/viewportDraw (8): drive AcGiWorldDraw via a hostless collector to capture an entity's
//   graphics primitives (feasible). T02 overrules/grips/graphics-invalidation (19): AcDbObjectOverrule/
//   AcDbGripOverrule register hostless but FIRE in-app; grips need the editor (attended).
// #included into AriadneNativeJob.cpp; sees all in-TU helpers. m08lHasOp/m08lDispatch lockstep.
// staged-write only; no save/saveAs; no acedCommand. Honest-defer the attended graphics/grip ops
// (out of HasOp + blocker) — NO FAKES. See PLAN_M08L.md.
static bool m08lHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08L teammate: return true for this family's implemented op ids
}
static bool m08lDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08L teammate: implement graphics-system ops
}
