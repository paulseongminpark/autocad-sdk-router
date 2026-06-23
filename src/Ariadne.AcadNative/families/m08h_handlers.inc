// families/m08h_handlers.inc — M08H WRITE family: dimensions / annotations / hatch (staged-write).
//
// Owned by the M08H teammate (PR-scoped). #included into AriadneNativeJob.cpp; sees every in-TU
// helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08hHasOp(op): true for every op id this family IMPLEMENTS (gate admission). Ops left out
//     keep returning the honest OPERATION_NOT_IMPLEMENTED. NO FAKES.
//   - m08hDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"  (or an
//     emitNativeError-style error) to r and return true; else return false.
//
// SAFETY (hard): staged-write ONLY. Operate on ctx.pDb (the router-staged in-memory copy).
//   Never call save()/saveAs() on the original. No acedCommand/acedCmd (compile-disabled in 2027).
//
// REFERENCE PATTERN (replicate per entity; see AriadneNativeJob.cpp appendLine / appendCircle):
//   ensureLayer(pDb, layer, 7, created);
//   AcDbBlockTable* pBT; pDb->getBlockTable(pBT, AcDb::kForRead);
//   AcDbBlockTableRecord* pMS; pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite); pBT->close();
//   AcDbXxx* pE = new AcDbXxx(...); if(!layer.empty()) pE->setLayer(asciiToWide(layer).c_str());
//   AcDbObjectId id; es = pMS->appendAcDbEntity(id, pE); pMS->close();
//   if (es==Acad::eOk) pE->close(); else delete pE;
//   int probes=0,after=0; countModelSpace(pDb, after, probes);
// In-TU helpers: ensureLayer, asciiToWide, countModelSpace, handleOf, jsonFindString/Number/Object,
//   jsonEscape, njsonStr, serializeEntityCommon, AriadneStagedWriteTransaction, resolveHandle.
// Text/MText carry UTF-8 content -> route strings through njsonStr; setTextString takes ACHAR* via
//   asciiToWide. Dimensions take a dimension-style id (use the db default if none requested).
//
// M08H-T01 dimensions+annotation (14): write.entity.dim.{aligned,angular2line,angular3pt,arc,
//   diametric,ordinate,radial,radiallarge,rotated}, write.entity.{leader,mleader,mtext,table,text}
// M08H-T02 hatch (1): write.entity.hatch
//
// Entities needing full-ARX context not feasible hostless (e.g. AcDbTable layout, AcDbMLeader
// content build, complex associative hatch) must be HONESTLY left out of HasOp with a blocker in
// reports/tickets/M08H.md — NOT faked. A simple solid-fill hatch + a plain mtext/text + an aligned/
// rotated/radial/diametric dimension are feasible hostless and are the priority targets.
static bool m08hHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08H teammate: return true for this family's implemented op ids
}
static bool m08hDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08H teammate: implement the family's staged-write ops
}
