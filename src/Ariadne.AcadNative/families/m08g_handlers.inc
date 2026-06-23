// families/m08g_handlers.inc — M08G WRITE family: entity creation + entity/geometry modify (staged-write).
//
// Owned by the M08G teammate (PR-scoped). #included into AriadneNativeJob.cpp; sees every in-TU
// helper. Contract (docs/M08_FAMILY_HANDLER_CONTRACT.md):
//   - m08gHasOp(op): true for every op id this family IMPLEMENTS (gate admission). Ops left out
//     keep returning the honest OPERATION_NOT_IMPLEMENTED. NO FAKES.
//   - m08gDispatch(op, ctx, r): if op is yours, append  "result":{...},"status":"ok"  (or an
//     emitNativeError-style error) to r and return true; else return false.
//
// SAFETY (hard): staged-write ONLY. Operate on ctx.pDb (the router-staged in-memory copy).
//   Never call save()/saveAs() on the original. No acedCommand/acedCmd (compile-disabled in 2027).
//   Original DWG bytes must stay unchanged.
//
// REFERENCE PATTERN (replicate per entity; see AriadneNativeJob.cpp appendLine / appendCircle):
//   ensureLayer(pDb, layer, 7, created)  // if layer non-empty
//   AcDbBlockTable* pBT; pDb->getBlockTable(pBT, AcDb::kForRead);
//   AcDbBlockTableRecord* pMS; pBT->getAt(ACDB_MODEL_SPACE, pMS, AcDb::kForWrite); pBT->close();
//   AcDbXxx* pE = new AcDbXxx(...); if(!layer.empty()) pE->setLayer(asciiToWide(layer).c_str());
//   AcDbObjectId id; es = pMS->appendAcDbEntity(id, pE); pMS->close();
//   if (es==Acad::eOk) pE->close(); else delete pE;
//   int probes=0,after=0; countModelSpace(pDb, after, probes);
//   r << "\"result\":{\"created\":...,\"handle\":\"" << handleOf(id) << "\",\"modelspace_entities_after\":" << after << "},\"status\":\"ok\"}";
// In-TU helpers available: ensureLayer, asciiToWide, countModelSpace, handleOf, jsonFindString/
//   Number/Object, jsonEscape, njsonStr, serializeEntityCommon, AriadneStagedWriteTransaction,
//   resolveHandle. Use AriadneStagedWriteTransaction(ctx.pDb) for multi-object modify ops.
//
// M08G-T02 entity-create (34): write.entity.{arc,attribdef,attribute,blockref,body,ellipse,face,
//   minsert,mline,mpolygon,nurbsurface,polyfacemesh,polygonmesh,polyline2d,polyline3d,rasterimage,
//   ray,region,shape,solid2d,solid3d.extrude,solid3d.loft,solid3d.primitive,solid3d.revolve,
//   solid3d.sweep,spline,subdmesh,surface,trace,wipeout,xline,point,polyline,tolerance}
// M08G-T03 modify/edit (11): edit.subentity.{add_paths,delete_paths,transform}, modify.curve.{offset,
//   split,to_spline}, modify.entity.{common,copy_transformed,explode,solid3d.boolean,transform}
//
// Ops needing the ASM modeler or external resources that are NOT feasible hostless (e.g. some
// solid3d.* boolean/loft/sweep/revolve, rasterimage needing an image def) must be HONESTLY left
// out of HasOp with a blocker recorded in reports/tickets/M08G.md — NOT faked.
static bool m08gHasOp(const std::string& op)
{
    (void)op;
    return false;   // M08G teammate: return true for this family's implemented op ids
}
static bool m08gDispatch(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r)
{
    (void)op; (void)ctx; (void)r;
    return false;   // M08G teammate: implement the family's staged-write ops
}
