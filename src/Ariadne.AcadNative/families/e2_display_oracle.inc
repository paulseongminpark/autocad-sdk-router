//////////////////////////////////////////////////////////////////////////////
// E2 attended native-display probe (experiment-only).
//
// This is deliberately wired to the existing, publicly hard-blocked
// plot.engine.run operation.  Source presence is not capability proof: the
// registry must remain blocked until a dedicated full AutoCAD run shows that
// the publish and DMM callbacks fire on a staged drawing.
//
// The DWF Metadata Manager (DMM) observes entities while AutoCAD publishes a
// DWF.  Its callbacks expose the effective layer and enclosing block-reference
// path independently of the WorldIR XCLIP implementation under test.  The SDK
// also offers graphic IDs, but an empty ID array is not documented as proof
// that an entity was clipped.  This probe therefore records the raw IDs and
// never turns an empty array into a native visibility decision.
//////////////////////////////////////////////////////////////////////////////

#include <algorithm>
#include <map>
#include <set>

// Do not statically link AcPublish_crx.lib: that would make the shared .crx
// depend on attended-only AcPublish at module-load time and could break the
// existing accoreconsole inspection lane.  Resolve acplPublishExecute only
// after the attended handler has loaded AcPublish.crx.
typedef void (__cdecl *E2ACPLPUBLISHEXECUTE)(AcPlDSDData, AcPlPlotConfig*, bool);

static Acad::ErrorStatus e2EnsureFixtureLayer(
    AcDbDatabase* pDb,
    const ACHAR* name,
    Adesk::UInt16 colorIndex,
    AcDbObjectId& layerId)
{
    AcDbLayerTable* pLayers = nullptr;
    Acad::ErrorStatus es = pDb->getLayerTable(pLayers, AcDb::kForWrite);
    if (es != Acad::eOk || pLayers == nullptr)
        return es;
    if (pLayers->has(name)) {
        es = pLayers->getAt(name, layerId);
        pLayers->close();
        return es;
    }

    AcDbLayerTableRecord* pLayer = new AcDbLayerTableRecord();
    pLayer->setName(name);
    AcCmColor color;
    color.setColorIndex(colorIndex);
    pLayer->setColor(color);
    es = pLayers->add(layerId, pLayer);
    pLayers->close();
    if (es == Acad::eOk)
        pLayer->close();
    else
        delete pLayer;
    return es;
}

static Acad::ErrorStatus e2EraseModelSpace(
    AcDbDatabase* pDb,
    AcDbObjectId& modelSpaceId,
    int& erased)
{
    erased = 0;
    AcDbBlockTable* pBlocks = nullptr;
    Acad::ErrorStatus es = pDb->getBlockTable(pBlocks, AcDb::kForRead);
    if (es != Acad::eOk || pBlocks == nullptr)
        return es;
    es = pBlocks->getAt(ACDB_MODEL_SPACE, modelSpaceId);
    pBlocks->close();
    if (es != Acad::eOk)
        return es;

    AcDbBlockTableRecord* pModel = nullptr;
    es = acdbOpenObject(pModel, modelSpaceId, AcDb::kForWrite);
    if (es != Acad::eOk || pModel == nullptr)
        return es;
    AcDbBlockTableRecordIterator* pIt = nullptr;
    es = pModel->newIterator(pIt);
    if (es == Acad::eOk && pIt != nullptr) {
        for (; !pIt->done(); pIt->step()) {
            AcDbEntity* pEntity = nullptr;
            if (pIt->getEntity(pEntity, AcDb::kForWrite) == Acad::eOk &&
                pEntity != nullptr) {
                if (pEntity->erase() == Acad::eOk)
                    ++erased;
                pEntity->close();
            }
        }
        delete pIt;
    }
    pModel->close();
    return es;
}

static Acad::ErrorStatus e2AttachRectangularXclip(
    AcDbBlockReference* pReference,
    const AcGePoint2d& lowerLeft,
    const AcGePoint2d& upperRight,
    std::string& filterHandle)
{
    if (pReference == nullptr)
        return Acad::eNullObjectPointer;
    Acad::ErrorStatus es = pReference->createExtensionDictionary();
    if (es != Acad::eOk && es != Acad::eAlreadyInDb)
        return es;
    const AcDbObjectId extensionId = pReference->extensionDictionary();

    AcDbDictionary* pExtension = nullptr;
    es = acdbOpenObject(pExtension, extensionId, AcDb::kForWrite);
    if (es != Acad::eOk || pExtension == nullptr)
        return es;
    AcDbDictionary* pFilterDictionary = new AcDbDictionary();
    AcDbObjectId filterDictionaryId;
    es = pExtension->setAt(ACRX_T("ACAD_FILTER"), pFilterDictionary, filterDictionaryId);
    pExtension->close();
    if (es != Acad::eOk) {
        delete pFilterDictionary;
        return es;
    }

    AcGePoint2dArray boundary;
    boundary.append(lowerLeft);
    boundary.append(upperRight);
    // ObjectARX 2027's acdb26.lib exports the default constructor plus
    // setDefinition(), but not the public-looking convenience constructor that
    // takes the boundary.  Use the exported two-step path so the minimal repro
    // itself does not depend on an unresolved SDK symbol.
    AcDbSpatialFilter* pSpatialFilter = new AcDbSpatialFilter();
    es = pSpatialFilter->setDefinition(
        boundary,
        AcGeVector3d::kZAxis,
        0.0,
        0.0,
        0.0,
        Adesk::kTrue);
    if (es == Acad::eOk)
        es = pSpatialFilter->setInverted(false);
    if (es != Acad::eOk) {
        pFilterDictionary->close();
        delete pSpatialFilter;
        return es;
    }
    AcDbObjectId spatialFilterId;
    es = pFilterDictionary->setAt(
        ACRX_T("SPATIAL"), pSpatialFilter, spatialFilterId);
    pFilterDictionary->close();
    if (es != Acad::eOk) {
        delete pSpatialFilter;
        return es;
    }
    filterHandle = handleOf(pSpatialFilter);
    pSpatialFilter->close();
    return Acad::eOk;
}

static void runE2CreateXclipFixture(
    AcDbDatabase* pDb,
    const std::string& ctxHostMode,
    std::ostringstream& r)
{
    if (ctxHostMode != "full_autocad") {
        emitNativeError(
            r,
            "ATTENDED_HOST_REQUIRED",
            "the E2 XCLIP fixture is created only in a staged full AutoCAD document");
        return;
    }

    const ACHAR* visibleLayerName = ACRX_T("E2_DMM_VISIBLE");
    const ACHAR* clippedLayerName = ACRX_T("E2_DMM_CLIPPED");
    const ACHAR* frameLayerName = ACRX_T("E2_DMM_FRAME");
    const ACHAR* blockName = ACRX_T("E2_DMM_XCLIP_BLOCK");
    AcDbObjectId visibleLayerId;
    AcDbObjectId clippedLayerId;
    AcDbObjectId frameLayerId;
    Acad::ErrorStatus es = e2EnsureFixtureLayer(
        pDb, visibleLayerName, 1, visibleLayerId);
    if (es == Acad::eOk)
        es = e2EnsureFixtureLayer(pDb, clippedLayerName, 3, clippedLayerId);
    if (es == Acad::eOk)
        es = e2EnsureFixtureLayer(pDb, frameLayerName, 8, frameLayerId);
    if (es != Acad::eOk) {
        emitNativeError(r, "FIXTURE_LAYER_CREATE_FAILED", "could not create probe layers");
        return;
    }

    AcDbObjectId modelSpaceId;
    int erased = 0;
    es = e2EraseModelSpace(pDb, modelSpaceId, erased);
    if (es != Acad::eOk) {
        emitNativeError(r, "FIXTURE_MODELSPACE_CLEAR_FAILED", "could not clear staged model space");
        return;
    }

    AcDbBlockTable* pBlocks = nullptr;
    es = pDb->getBlockTable(pBlocks, AcDb::kForWrite);
    if (es != Acad::eOk || pBlocks == nullptr) {
        emitNativeError(r, "FIXTURE_BLOCK_TABLE_OPEN_FAILED", "could not open the block table");
        return;
    }
    if (pBlocks->has(blockName)) {
        pBlocks->close();
        emitNativeError(r, "FIXTURE_ALREADY_EXISTS", "the staged drawing already contains the probe block");
        return;
    }
    AcDbBlockTableRecord* pDefinition = new AcDbBlockTableRecord();
    pDefinition->setName(blockName);
    pDefinition->setOrigin(AcGePoint3d::kOrigin);
    AcDbObjectId definitionId;
    es = pBlocks->add(definitionId, pDefinition);
    pBlocks->close();
    if (es != Acad::eOk) {
        delete pDefinition;
        emitNativeError(r, "FIXTURE_BLOCK_CREATE_FAILED", "could not create the probe block definition");
        return;
    }

    AcDbLine* pVisible = new AcDbLine(
        AcGePoint3d(0.0, 0.0, 0.0), AcGePoint3d(10.0, 0.0, 0.0));
    pVisible->setLayer(visibleLayerId);
    AcDbObjectId visibleId;
    es = pDefinition->appendAcDbEntity(visibleId, pVisible);
    if (es != Acad::eOk) {
        delete pVisible;
        pDefinition->close();
        emitNativeError(r, "FIXTURE_VISIBLE_LINE_FAILED", "could not append the visible probe line");
        return;
    }
    const std::string visibleHandle = handleOf(pVisible);
    pVisible->close();

    AcDbLine* pClipped = new AcDbLine(
        AcGePoint3d(20.0, 0.0, 0.0), AcGePoint3d(30.0, 0.0, 0.0));
    pClipped->setLayer(clippedLayerId);
    AcDbObjectId clippedId;
    es = pDefinition->appendAcDbEntity(clippedId, pClipped);
    if (es != Acad::eOk) {
        delete pClipped;
        pDefinition->close();
        emitNativeError(r, "FIXTURE_CLIPPED_LINE_FAILED", "could not append the clipped probe line");
        return;
    }
    const std::string clippedHandle = handleOf(pClipped);
    pClipped->close();
    pDefinition->close();

    AcDbBlockTableRecord* pModel = nullptr;
    es = acdbOpenObject(pModel, modelSpaceId, AcDb::kForWrite);
    if (es != Acad::eOk || pModel == nullptr) {
        emitNativeError(r, "FIXTURE_MODELSPACE_OPEN_FAILED", "could not reopen staged model space");
        return;
    }
    AcDbLine* pFrame = new AcDbLine(
        AcGePoint3d(0.0, -1.0, 0.0), AcGePoint3d(0.0, 1.0, 0.0));
    pFrame->setLayer(frameLayerId);
    AcDbObjectId frameId;
    es = pModel->appendAcDbEntity(frameId, pFrame);
    if (es == Acad::eOk)
        pFrame->close();
    else
        delete pFrame;
    if (es != Acad::eOk) {
        pModel->close();
        emitNativeError(r, "FIXTURE_FRAME_LINE_FAILED", "could not append the frame line");
        return;
    }

    AcDbBlockReference* pReference = new AcDbBlockReference(
        AcGePoint3d::kOrigin, definitionId);
    AcDbObjectId referenceId;
    es = pModel->appendAcDbEntity(referenceId, pReference);
    pModel->close();
    if (es != Acad::eOk) {
        delete pReference;
        emitNativeError(r, "FIXTURE_INSERT_FAILED", "could not append the probe block reference");
        return;
    }
    const std::string referenceHandle = handleOf(pReference);
    std::string filterHandle;
    es = e2AttachRectangularXclip(
        pReference,
        AcGePoint2d(-1.0, -2.0),
        AcGePoint2d(11.0, 2.0),
        filterHandle);
    pReference->close();
    if (es != Acad::eOk) {
        emitNativeError(r, "FIXTURE_XCLIP_CREATE_FAILED", "could not attach the spatial filter");
        return;
    }

    AcDbBlockTableRecord* pModelForLayout = nullptr;
    if (acdbOpenObject(pModelForLayout, modelSpaceId, AcDb::kForRead) == Acad::eOk &&
        pModelForLayout != nullptr) {
        const AcDbObjectId layoutId = pModelForLayout->getLayoutId();
        pModelForLayout->close();
        AcDbLayout* pLayout = nullptr;
        if (acdbOpenObject(pLayout, layoutId, AcDb::kForWrite) == Acad::eOk &&
            pLayout != nullptr) {
            AcDbPlotSettingsValidator* pValidator =
                acdbHostApplicationServices()->plotSettingsValidator();
            if (pValidator != nullptr) {
                pValidator->setPlotType(pLayout, AcDbPlotSettings::kExtents);
                pValidator->setUseStandardScale(pLayout, Adesk::kTrue);
                pValidator->setStdScaleType(pLayout, AcDbPlotSettings::kScaleToFit);
                pValidator->setPlotCentered(pLayout, Adesk::kTrue);
            }
            pLayout->close();
        }
    }
    pDb->setExtmin(AcGePoint3d(-1.0, -2.0, 0.0));
    pDb->setExtmax(AcGePoint3d(11.0, 2.0, 0.0));

    r << "\"result\":{";
    r << "\"schema\":\"ariadne.e2.xclip_minimal_fixture.v1\"";
    r << ",\"modelspace_entities_erased\":" << erased;
    r << ",\"visible_layer\":\"E2_DMM_VISIBLE\"";
    r << ",\"clipped_layer\":\"E2_DMM_CLIPPED\"";
    r << ",\"visible_source_handle\":\"" << visibleHandle << "\"";
    r << ",\"clipped_source_handle\":\"" << clippedHandle << "\"";
    r << ",\"block_reference_handle\":\"" << referenceHandle << "\"";
    r << ",\"spatial_filter_handle\":\"" << filterHandle << "\"";
    r << ",\"clip_boundary_block\":[[-1,-2],[11,2]]";
    r << ",\"expected_native_display\":{";
    r << "\"E2_DMM_VISIBLE\":true,\"E2_DMM_CLIPPED\":false}";
    r << "},\"status\":\"ok\"}";
}

struct E2NativeDisplayRecord
{
    std::string uniqueEntityId;
    std::string sourceHandle;
    std::string entityClass;
    std::string sourceLayer;
    std::string effectiveLayer;
    std::string matchedTargetLayer;
    std::vector<std::string> blockRefPath;
    std::vector<long> graphicIds;
    int dmmNodeId;
    bool graphicIdObserved;
};

static std::string e2LayerName(const AcDbObjectId& layerId)
{
    if (layerId.isNull())
        return std::string();
    AcDbLayerTableRecord* pLayer = nullptr;
    if (acdbOpenObject(pLayer, layerId, AcDb::kForRead) != Acad::eOk || pLayer == nullptr)
        return std::string();
    const ACHAR* rawName = nullptr;
    std::string name;
    if (pLayer->getName(rawName) == Acad::eOk)
        name = acharToAscii(rawName);
    pLayer->close();
    return name;
}

// ---------------------------------------------------------------------------
// Independent XCLIP membership oracle.
//
// DMM callbacks are deliberately NOT used here: the controlled fixture proved
// that AutoCAD emits DMM entity callbacks for both a visible line and a line
// wholly rejected by XCLIP.  This arm instead reads AcDbSpatialFilter state from
// ObjectARX and applies an independent polygon/segment intersection algorithm to
// the native LINE/LWPOLYLINE geometry.  The Python shell shares only the stable
// lineage-id convention; it never decides visibility.
// ---------------------------------------------------------------------------

static const double kE2GeometryEpsilon = 1.0e-12;
static const char* kE2GeometryScopeStrictLayerEntities = "strict_layer_entities_v1";
static const char* kE2GeometryScopeLinearSegments = "linear_segments_v1";
static void e2EmitStringArray(
    std::ostringstream& r,
    const std::vector<std::string>& values);

struct E2Point2
{
    double x;
    double y;
};

struct E2Segment2
{
    E2Point2 p0;
    E2Point2 p1;
};

struct E2PrimitiveSegment
{
    E2Segment2 segment;
    int subentityOrdinal;
};

struct E2LineageStep
{
    std::string sourceDefHandle;
    std::string insertEntityHandle;
    std::string targetDefHandle;
};

struct E2ClipPolygon
{
    std::vector<E2Point2> polygon;
    bool inverted;
    std::string insertHandle;
};

struct E2VisibleSegment
{
    std::string rootDefHandle;
    std::string sourceDefHandle;
    std::string sourceEntityHandle;
    std::string sourceLayer;
    std::vector<E2LineageStep> lineage;
    std::vector<std::string> activeXclipHandles;
    int subentityOrdinal;
    int clipFragmentOrdinal;
    E2Segment2 world;
};

struct E2LayerMembershipStats
{
    std::set<std::string> sourceEntityTemplates;
    std::set<std::string> excludedUnsupportedEntityTemplates;
    long long expectedSourceSegments = 0;
    long long visibleSourceSegments = 0;
    long long clippedAwaySourceSegments = 0;
    long long excludedCurvedSourceSegments = 0;
    long long excludedDegenerateSourceSegments = 0;
};

struct E2MembershipState
{
    std::vector<std::string> targetLayerOrder;
    std::set<std::string> targetLayers;
    std::map<std::string, E2LayerMembershipStats> layerStats;
    std::map<std::string, int> reachabilityMemo;
    std::set<std::string> reachabilityStack;
    std::vector<E2VisibleSegment> visibleRecords;
    std::string rootDefHandle;
    std::string geometryScope;
    std::string errorCode;
    std::string error;

    bool failed() const { return !errorCode.empty(); }
    void fail(const char* code, const std::string& message)
    {
        if (!failed()) {
            errorCode = code;
            error = message;
        }
    }
};

static E2Point2 e2Point2(const AcGePoint3d& point)
{
    E2Point2 out = { point.x, point.y };
    return out;
}

static E2Point2 e2Subtract(const E2Point2& a, const E2Point2& b)
{
    E2Point2 out = { a.x - b.x, a.y - b.y };
    return out;
}

static E2Point2 e2AddScaled(const E2Point2& point, const E2Point2& direction, double t)
{
    E2Point2 out = { point.x + direction.x * t, point.y + direction.y * t };
    return out;
}

static double e2Cross(const E2Point2& a, const E2Point2& b)
{
    return a.x * b.y - a.y * b.x;
}

static double e2Dot(const E2Point2& a, const E2Point2& b)
{
    return a.x * b.x + a.y * b.y;
}

static bool e2PointOnSegment(
    const E2Point2& point,
    const E2Point2& a,
    const E2Point2& b)
{
    const E2Point2 edge = e2Subtract(b, a);
    const E2Point2 offset = e2Subtract(point, a);
    const double edgeLength = std::sqrt(e2Dot(edge, edge));
    if (std::fabs(e2Cross(edge, offset)) >
        kE2GeometryEpsilon * (std::max)(1.0, edgeLength))
        return false;
    const double projection = e2Dot(offset, edge);
    return projection >= -kE2GeometryEpsilon &&
           projection <= e2Dot(edge, edge) + kE2GeometryEpsilon;
}

static bool e2PointInPolygon(
    const E2Point2& point,
    const std::vector<E2Point2>& polygon)
{
    bool inside = false;
    for (size_t i = 0; i < polygon.size(); ++i) {
        const E2Point2& a = polygon[i];
        const E2Point2& b = polygon[(i + 1) % polygon.size()];
        if (e2PointOnSegment(point, a, b))
            return true;
        if ((a.y > point.y) == (b.y > point.y))
            continue;
        const double crossingX = a.x +
            (point.y - a.y) * (b.x - a.x) / (b.y - a.y);
        if (point.x < crossingX)
            inside = !inside;
    }
    return inside;
}

static std::vector<std::pair<double, double>> e2InsideIntervals(
    const E2Segment2& segment,
    const std::vector<E2Point2>& polygon)
{
    const E2Point2 direction = e2Subtract(segment.p1, segment.p0);
    const double denominator = e2Dot(direction, direction);
    std::vector<std::pair<double, double>> intervals;
    if (denominator <= kE2GeometryEpsilon)
        return intervals;

    std::vector<double> breaks;
    breaks.push_back(0.0);
    breaks.push_back(1.0);
    for (size_t i = 0; i < polygon.size(); ++i) {
        const E2Point2& a = polygon[i];
        const E2Point2& b = polygon[(i + 1) % polygon.size()];
        const E2Point2 edge = e2Subtract(b, a);
        const E2Point2 delta = e2Subtract(a, segment.p0);
        const double cross = e2Cross(direction, edge);
        if (std::fabs(cross) > kE2GeometryEpsilon) {
            const double t = e2Cross(delta, edge) / cross;
            const double u = e2Cross(delta, direction) / cross;
            if (t >= -kE2GeometryEpsilon && t <= 1.0 + kE2GeometryEpsilon &&
                u >= -kE2GeometryEpsilon && u <= 1.0 + kE2GeometryEpsilon) {
                breaks.push_back((std::min)(1.0, (std::max)(0.0, t)));
            }
        }
        else if (std::fabs(e2Cross(delta, direction)) <= kE2GeometryEpsilon) {
            const E2Point2 endpoints[2] = { a, b };
            for (int endpoint = 0; endpoint < 2; ++endpoint) {
                const double t = e2Dot(
                    e2Subtract(endpoints[endpoint], segment.p0), direction) / denominator;
                if (t >= -kE2GeometryEpsilon && t <= 1.0 + kE2GeometryEpsilon)
                    breaks.push_back((std::min)(1.0, (std::max)(0.0, t)));
            }
        }
    }

    std::sort(breaks.begin(), breaks.end());
    std::vector<double> ordered;
    for (double value : breaks) {
        if (ordered.empty() || value - ordered.back() > kE2GeometryEpsilon)
            ordered.push_back(value);
    }
    for (size_t i = 0; i + 1 < ordered.size(); ++i) {
        const double start = ordered[i];
        const double end = ordered[i + 1];
        if (end - start <= kE2GeometryEpsilon)
            continue;
        const E2Point2 midpoint = e2AddScaled(
            segment.p0, direction, (start + end) / 2.0);
        if (e2PointInPolygon(midpoint, polygon))
            intervals.push_back(std::make_pair(start, end));
    }
    return intervals;
}

static std::vector<E2Segment2> e2ApplyClip(
    const std::vector<E2Segment2>& fragments,
    const E2ClipPolygon& clip)
{
    std::vector<E2Segment2> output;
    for (const E2Segment2& fragment : fragments) {
        const E2Point2 direction = e2Subtract(fragment.p1, fragment.p0);
        std::vector<std::pair<double, double>> selected =
            e2InsideIntervals(fragment, clip.polygon);
        if (clip.inverted) {
            std::vector<std::pair<double, double>> complement;
            double cursor = 0.0;
            for (const std::pair<double, double>& interval : selected) {
                if (interval.first - cursor > kE2GeometryEpsilon)
                    complement.push_back(std::make_pair(cursor, interval.first));
                cursor = (std::max)(cursor, interval.second);
            }
            if (1.0 - cursor > kE2GeometryEpsilon)
                complement.push_back(std::make_pair(cursor, 1.0));
            selected.swap(complement);
        }
        for (const std::pair<double, double>& interval : selected) {
            E2Segment2 clipped = {
                e2AddScaled(fragment.p0, direction, interval.first),
                e2AddScaled(fragment.p0, direction, interval.second)
            };
            output.push_back(clipped);
        }
    }
    return output;
}

static int e2ReadBlockReferenceClip(
    AcDbBlockReference* pReference,
    const AcGeMatrix3d& childWorld,
    E2ClipPolygon& output,
    E2MembershipState& state)
{
    if (pReference == nullptr || pReference->extensionDictionary().isNull())
        return 0;
    AcDbDictionary* pExtension = nullptr;
    Acad::ErrorStatus es = acdbOpenObject(
        pExtension, pReference->extensionDictionary(), AcDb::kForRead);
    if (es != Acad::eOk || pExtension == nullptr) {
        state.fail("XCLIP_EXTENSION_OPEN_FAILED", "could not open an INSERT extension dictionary");
        return -1;
    }
    AcDbObjectId filterDictionaryId;
    es = pExtension->getAt(ACRX_T("ACAD_FILTER"), filterDictionaryId);
    pExtension->close();
    if (es != Acad::eOk || filterDictionaryId.isNull())
        return 0;

    AcDbDictionary* pFilterDictionary = nullptr;
    es = acdbOpenObject(pFilterDictionary, filterDictionaryId, AcDb::kForRead);
    if (es != Acad::eOk || pFilterDictionary == nullptr) {
        state.fail("XCLIP_FILTER_DICTIONARY_OPEN_FAILED", "could not open ACAD_FILTER");
        return -1;
    }
    AcDbObjectId spatialFilterId;
    es = pFilterDictionary->getAt(ACRX_T("SPATIAL"), spatialFilterId);
    pFilterDictionary->close();
    if (es != Acad::eOk || spatialFilterId.isNull())
        return 0;

    AcDbSpatialFilter* pFilter = nullptr;
    es = acdbOpenObject(pFilter, spatialFilterId, AcDb::kForRead);
    if (es != Acad::eOk || pFilter == nullptr) {
        state.fail("XCLIP_SPATIAL_FILTER_OPEN_FAILED", "could not open AcDbSpatialFilter");
        return -1;
    }
    AcGePoint2dArray points;
    AcGeVector3d normal;
    double elevation = 0.0;
    double frontClip = 0.0;
    double backClip = 0.0;
    Adesk::Boolean enabled = Adesk::kFalse;
    es = pFilter->getDefinition(
        points, normal, elevation, frontClip, backClip, enabled);
    const bool inverted = pFilter->isInverted();
    AcGeMatrix3d inverseBlockTransform;
    pFilter->getOriginalInverseBlockXform(inverseBlockTransform);
    pFilter->close();
    if (es != Acad::eOk) {
        state.fail("XCLIP_DEFINITION_READ_FAILED", "AcDbSpatialFilter::getDefinition failed");
        return -1;
    }
    if (enabled != Adesk::kTrue)
        return 0;
    if (points.length() < 2) {
        state.fail("XCLIP_BOUNDARY_INVALID", "enabled XCLIP has fewer than two points");
        return -1;
    }

    AcGePoint2dArray polygon;
    if (points.length() == 2) {
        polygon.append(AcGePoint2d(points[0].x, points[0].y));
        polygon.append(AcGePoint2d(points[1].x, points[0].y));
        polygon.append(AcGePoint2d(points[1].x, points[1].y));
        polygon.append(AcGePoint2d(points[0].x, points[1].y));
    }
    else {
        for (int i = 0; i < points.length(); ++i)
            polygon.append(points[i]);
    }

    output.polygon.clear();
    output.inverted = inverted;
    output.insertHandle = handleOf(pReference);
    for (int i = 0; i < polygon.length(); ++i) {
        AcGePoint3d point(polygon[i].x, polygon[i].y, 0.0);
        point.transformBy(inverseBlockTransform);
        point.transformBy(childWorld);
        output.polygon.push_back(e2Point2(point));
    }
    double twiceArea = 0.0;
    for (size_t i = 0; i < output.polygon.size(); ++i) {
        twiceArea += e2Cross(
            output.polygon[i], output.polygon[(i + 1) % output.polygon.size()]);
    }
    if (std::fabs(twiceArea) <= kE2GeometryEpsilon) {
        state.fail("XCLIP_BOUNDARY_DEGENERATE", "enabled XCLIP polygon has zero area");
        return -1;
    }
    return 1;
}

static bool e2EntityLayerVisible(AcDbEntity* pEntity, E2MembershipState& state)
{
    if (pEntity == nullptr)
        return false;
    if (pEntity->visibility() != AcDb::kVisible)
        return false;
    AcDbLayerTableRecord* pLayer = nullptr;
    const Acad::ErrorStatus es = acdbOpenObject(
        pLayer, pEntity->layerId(), AcDb::kForRead);
    if (es != Acad::eOk || pLayer == nullptr) {
        state.fail("LAYER_STATE_UNRESOLVED", "could not open an entity layer record");
        return false;
    }
    const bool visible = !pLayer->isOff() && !pLayer->isFrozen();
    pLayer->close();
    return visible;
}

static std::vector<AcDbObjectId> e2OrderedEntityIds(
    AcDbBlockTableRecord* pDefinition,
    E2MembershipState& state)
{
    std::vector<AcDbObjectId> ids;
    AcDbBlockTableRecordIterator* pIterator = nullptr;
    const Acad::ErrorStatus es = pDefinition->newIterator(pIterator);
    if (es != Acad::eOk || pIterator == nullptr) {
        state.fail("BLOCK_ITERATOR_CREATE_FAILED", "could not iterate a block definition");
        return ids;
    }
    for (; !pIterator->done(); pIterator->step()) {
        AcDbEntity* pEntity = nullptr;
        if (pIterator->getEntity(pEntity, AcDb::kForRead) != Acad::eOk ||
            pEntity == nullptr) {
            state.fail("ENTITY_OPEN_FAILED", "could not open an entity while traversing a block");
            break;
        }
        ids.push_back(pEntity->objectId());
        pEntity->close();
    }
    delete pIterator;
    std::sort(ids.begin(), ids.end(), [](const AcDbObjectId& left, const AcDbObjectId& right) {
        return handleOfId(left) < handleOfId(right);
    });
    return ids;
}

static bool e2DefinitionHasTarget(
    const AcDbObjectId& definitionId,
    E2MembershipState& state)
{
    const std::string definitionHandle = handleOfId(definitionId);
    const auto memo = state.reachabilityMemo.find(definitionHandle);
    if (memo != state.reachabilityMemo.end())
        return memo->second == 1;
    if (!state.reachabilityStack.insert(definitionHandle).second) {
        state.fail("BLOCK_GRAPH_CYCLE", "cycle detected while resolving target reachability");
        return false;
    }

    AcDbBlockTableRecord* pDefinition = nullptr;
    if (acdbOpenObject(pDefinition, definitionId, AcDb::kForRead) != Acad::eOk ||
        pDefinition == nullptr) {
        state.fail("BLOCK_DEFINITION_OPEN_FAILED", "could not open a referenced block definition");
        state.reachabilityStack.erase(definitionHandle);
        return false;
    }
    const std::vector<AcDbObjectId> ids = e2OrderedEntityIds(pDefinition, state);
    pDefinition->close();
    bool containsTarget = false;
    for (const AcDbObjectId& id : ids) {
        if (state.failed())
            break;
        AcDbEntity* pEntity = nullptr;
        if (acdbOpenObject(pEntity, id, AcDb::kForRead) != Acad::eOk || pEntity == nullptr) {
            state.fail("ENTITY_OPEN_FAILED", "could not inspect target reachability");
            break;
        }
        AcDbBlockReference* pReference = AcDbBlockReference::cast(pEntity);
        if (pReference != nullptr) {
            const AcDbObjectId targetId = pReference->blockTableRecord();
            pEntity->close();
            if (!targetId.isNull() && e2DefinitionHasTarget(targetId, state))
                containsTarget = true;
            continue;
        }
        const std::string layer = e2LayerName(pEntity->layerId());
        if (state.targetLayers.find(layer) != state.targetLayers.end()) {
            state.layerStats[layer].sourceEntityTemplates.insert(handleOf(pEntity));
            containsTarget = true;
        }
        pEntity->close();
    }
    state.reachabilityStack.erase(definitionHandle);
    state.reachabilityMemo[definitionHandle] = containsTarget ? 1 : 0;
    return containsTarget;
}

static bool e2PrimitiveSegments(
    AcDbEntity* pEntity,
    std::vector<E2PrimitiveSegment>& output,
    E2LayerMembershipStats& stats,
    E2MembershipState& state)
{
    output.clear();
    const bool linearSegments =
        state.geometryScope == kE2GeometryScopeLinearSegments;
    if (AcDbLine* pLine = AcDbLine::cast(pEntity)) {
        E2PrimitiveSegment segment = {
            {
                e2Point2(pLine->startPoint()),
                e2Point2(pLine->endPoint())
            },
            0
        };
        output.push_back(segment);
        return true;
    }
    if (AcDbPolyline* pPolyline = AcDbPolyline::cast(pEntity)) {
        const unsigned int count = pPolyline->numVerts();
        if (count < 2) {
            state.fail("DEGENERATE_TARGET_POLYLINE", "target LWPOLYLINE has fewer than two vertices");
            return false;
        }
        std::vector<AcGePoint3d> vertices;
        std::vector<double> bulges;
        vertices.reserve(count);
        bulges.reserve(count);
        for (unsigned int i = 0; i < count; ++i) {
            double bulge = 0.0;
            AcGePoint3d point;
            if (pPolyline->getPointAt(i, point) != Acad::eOk ||
                pPolyline->getBulgeAt(i, bulge) != Acad::eOk) {
                state.fail("TARGET_POLYLINE_READ_FAILED", "could not read an LWPOLYLINE vertex");
                return false;
            }
            if (!linearSegments && std::fabs(bulge) > kE2GeometryEpsilon) {
                state.fail(
                    "TARGET_BULGE_UNSUPPORTED",
                    "v1 native membership refuses curved LWPOLYLINE segments instead of approximating them");
                return false;
            }
            vertices.push_back(point);
            bulges.push_back(bulge);
        }
        const unsigned int segmentCount =
            (pPolyline->isClosed() && count > 2) ? count : count - 1;
        for (unsigned int i = 0; i < segmentCount; ++i) {
            const unsigned int next = (i + 1) % count;
            const E2Segment2 local = {
                e2Point2(vertices[i]), e2Point2(vertices[next])
            };
            const E2Point2 localSpan = e2Subtract(local.p1, local.p0);
            if (linearSegments &&
                e2Dot(localSpan, localSpan) <=
                    kE2GeometryEpsilon * kE2GeometryEpsilon) {
                ++stats.excludedDegenerateSourceSegments;
                continue;
            }
            if (linearSegments && std::fabs(bulges[i]) > kE2GeometryEpsilon) {
                ++stats.excludedCurvedSourceSegments;
                continue;
            }
            E2PrimitiveSegment segment = {
                local,
                static_cast<int>(i)
            };
            output.push_back(segment);
        }
        return true;
    }
    if (linearSegments) {
        stats.excludedUnsupportedEntityTemplates.insert(handleOf(pEntity));
        return true;
    }
    state.fail(
        "TARGET_ENTITY_TYPE_UNSUPPORTED",
        "v1 native membership supports only LINE and straight-segment LWPOLYLINE targets");
    return false;
}

static void e2VisitDefinition(
    const AcDbObjectId& definitionId,
    const AcGeMatrix3d& parentWorld,
    const std::vector<E2LineageStep>& lineage,
    const std::vector<E2ClipPolygon>& activeClips,
    const std::set<std::string>& activeDefinitions,
    bool ancestorsVisible,
    E2MembershipState& state)
{
    if (state.failed())
        return;
    const std::string definitionHandle = handleOfId(definitionId);
    if (activeDefinitions.find(definitionHandle) != activeDefinitions.end()) {
        state.fail("BLOCK_GRAPH_CYCLE", "cycle detected while expanding target placements");
        return;
    }
    std::set<std::string> nextActive = activeDefinitions;
    nextActive.insert(definitionHandle);

    AcDbBlockTableRecord* pDefinition = nullptr;
    if (acdbOpenObject(pDefinition, definitionId, AcDb::kForRead) != Acad::eOk ||
        pDefinition == nullptr) {
        state.fail("BLOCK_DEFINITION_OPEN_FAILED", "could not open a target block definition");
        return;
    }
    const std::vector<AcDbObjectId> ids = e2OrderedEntityIds(pDefinition, state);
    pDefinition->close();
    for (const AcDbObjectId& id : ids) {
        if (state.failed())
            return;
        AcDbEntity* pEntity = nullptr;
        if (acdbOpenObject(pEntity, id, AcDb::kForRead) != Acad::eOk || pEntity == nullptr) {
            state.fail("ENTITY_OPEN_FAILED", "could not open a target-path entity");
            return;
        }
        AcDbBlockReference* pReference = AcDbBlockReference::cast(pEntity);
        if (pReference != nullptr) {
            const AcDbObjectId targetId = pReference->blockTableRecord();
            if (targetId.isNull() || !e2DefinitionHasTarget(targetId, state)) {
                pEntity->close();
                continue;
            }
            if (AcDbMInsertBlock* pMInsert = AcDbMInsertBlock::cast(pEntity)) {
                if (pMInsert->rows() != 1 || pMInsert->columns() != 1) {
                    pEntity->close();
                    state.fail(
                        "TARGET_ARRAY_INSERT_UNSUPPORTED",
                        "v1 native membership refuses target paths through multi-cell MINSERT arrays");
                    return;
                }
            }
            const std::string insertHandle = handleOf(pReference);
            const std::string targetHandle = handleOfId(targetId);
            AcGeMatrix3d childWorld = pReference->blockTransform();
            childWorld.preMultBy(parentWorld);
            const bool childVisible = ancestorsVisible && e2EntityLayerVisible(pEntity, state);
            std::vector<E2ClipPolygon> childClips = activeClips;
            E2ClipPolygon clip;
            const int clipStatus = e2ReadBlockReferenceClip(
                pReference, childWorld, clip, state);
            if (clipStatus > 0)
                childClips.push_back(clip);
            E2LineageStep step = {
                definitionHandle,
                insertHandle,
                targetHandle
            };
            std::vector<E2LineageStep> childLineage = lineage;
            childLineage.push_back(step);
            pEntity->close();
            if (clipStatus < 0 || state.failed())
                return;
            e2VisitDefinition(
                targetId,
                childWorld,
                childLineage,
                childClips,
                nextActive,
                childVisible,
                state);
            continue;
        }

        const std::string layer = e2LayerName(pEntity->layerId());
        if (state.targetLayers.find(layer) == state.targetLayers.end()) {
            pEntity->close();
            continue;
        }
        const std::string entityHandle = handleOf(pEntity);
        E2LayerMembershipStats& stats = state.layerStats[layer];
        std::vector<E2PrimitiveSegment> localSegments;
        if (!e2PrimitiveSegments(pEntity, localSegments, stats, state)) {
            pEntity->close();
            return;
        }
        if (localSegments.empty()) {
            pEntity->close();
            continue;
        }
        const bool primitiveVisible = ancestorsVisible && e2EntityLayerVisible(pEntity, state);
        for (const E2PrimitiveSegment& sourceSegment : localSegments) {
            ++stats.expectedSourceSegments;
            E2Segment2 world = sourceSegment.segment;
            AcGePoint3d p0(world.p0.x, world.p0.y, 0.0);
            AcGePoint3d p1(world.p1.x, world.p1.y, 0.0);
            p0.transformBy(parentWorld);
            p1.transformBy(parentWorld);
            world.p0 = e2Point2(p0);
            world.p1 = e2Point2(p1);
            const E2Point2 span = e2Subtract(world.p1, world.p0);
            if (e2Dot(span, span) <=
                kE2GeometryEpsilon * kE2GeometryEpsilon) {
                pEntity->close();
                state.fail("DEGENERATE_WORLD_TARGET", "a target segment collapsed under INSERT transforms");
                return;
            }
            std::vector<E2Segment2> fragments;
            if (primitiveVisible)
                fragments.push_back(world);
            for (const E2ClipPolygon& activeClip : activeClips) {
                fragments = e2ApplyClip(fragments, activeClip);
                if (fragments.empty())
                    break;
            }
            if (fragments.empty()) {
                ++stats.clippedAwaySourceSegments;
                continue;
            }
            if (fragments.size() != 1) {
                pEntity->close();
                state.fail(
                    "SPLIT_TARGET_SEGMENT_UNSUPPORTED",
                    "v1 oracle refuses a clip that splits one source segment into multiple fragments");
                return;
            }
            ++stats.visibleSourceSegments;
            E2VisibleSegment record;
            record.rootDefHandle = state.rootDefHandle;
            record.sourceDefHandle = definitionHandle;
            record.sourceEntityHandle = entityHandle;
            record.sourceLayer = layer;
            record.lineage = lineage;
            record.subentityOrdinal = sourceSegment.subentityOrdinal;
            record.clipFragmentOrdinal = 0;
            record.world = fragments[0];
            for (const E2ClipPolygon& activeClip : activeClips)
                record.activeXclipHandles.push_back(activeClip.insertHandle);
            state.visibleRecords.push_back(record);
        }
        pEntity->close();
    }
}

static void e2EmitLineage(
    std::ostringstream& r,
    const std::vector<E2LineageStep>& lineage)
{
    r << "[";
    for (size_t i = 0; i < lineage.size(); ++i) {
        if (i > 0) r << ",";
        const E2LineageStep& step = lineage[i];
        r << "{\"source_def_handle\":\"" << jsonEscape(step.sourceDefHandle) << "\""
          << ",\"insert_entity_handle\":\"" << jsonEscape(step.insertEntityHandle) << "\""
          << ",\"target_def_handle\":\"" << jsonEscape(step.targetDefHandle) << "\""
          << ",\"array_row_index\":0,\"array_col_index\":0}";
    }
    r << "]";
}

static void runE2NativeXclipMembership(
    const std::string& job,
    AcDbDatabase* pDb,
    const std::string& ctxHostMode,
    std::ostringstream& r)
{
    if (ctxHostMode != "full_autocad") {
        emitNativeError(
            r,
            "ATTENDED_HOST_REQUIRED",
            "native XCLIP membership is permitted only in a dedicated full AutoCAD host");
        return;
    }
    if (pDb == nullptr) {
        emitNativeError(r, "NO_WORKING_DATABASE", "native XCLIP membership has no working database");
        return;
    }
    const std::vector<std::string> targetLayers = jsonFindStringArray(job, "target_layers");
    if (targetLayers.empty()) {
        emitNativeError(r, "TARGET_LAYERS_REQUIRED", "target_layers must contain at least one layer");
        return;
    }
    const std::set<std::string> uniqueLayers(targetLayers.begin(), targetLayers.end());
    if (uniqueLayers.size() != targetLayers.size()) {
        emitNativeError(r, "DUPLICATE_TARGET_LAYER", "target_layers must be unique");
        return;
    }
    std::string geometryScope = kE2GeometryScopeStrictLayerEntities;
    std::string requestedGeometryScope;
    if (jsonFindString(job, "geometry_scope", requestedGeometryScope))
        geometryScope = requestedGeometryScope;
    if (geometryScope != kE2GeometryScopeStrictLayerEntities &&
        geometryScope != kE2GeometryScopeLinearSegments) {
        emitNativeError(
            r,
            "GEOMETRY_SCOPE_INVALID",
            "geometry_scope must be strict_layer_entities_v1 or linear_segments_v1");
        return;
    }

    AcDbBlockTable* pBlocks = nullptr;
    AcDbObjectId modelSpaceId;
    Acad::ErrorStatus es = pDb->getBlockTable(pBlocks, AcDb::kForRead);
    if (es == Acad::eOk && pBlocks != nullptr) {
        es = pBlocks->getAt(ACDB_MODEL_SPACE, modelSpaceId);
        pBlocks->close();
    }
    if (es != Acad::eOk || modelSpaceId.isNull()) {
        emitNativeError(r, "MODELSPACE_UNRESOLVED", "could not resolve model space");
        return;
    }

    E2MembershipState state;
    state.targetLayerOrder = targetLayers;
    state.targetLayers = uniqueLayers;
    state.rootDefHandle = handleOfId(modelSpaceId);
    state.geometryScope = geometryScope;
    for (const std::string& layer : targetLayers)
        state.layerStats[layer] = E2LayerMembershipStats();

    const bool rootHasTarget = e2DefinitionHasTarget(modelSpaceId, state);
    if (!state.failed() && rootHasTarget) {
        AcGeMatrix3d identity;
        e2VisitDefinition(
            modelSpaceId,
            identity,
            std::vector<E2LineageStep>(),
            std::vector<E2ClipPolygon>(),
            std::set<std::string>(),
            true,
            state);
    }
    if (state.failed()) {
        emitNativeError(r, state.errorCode.c_str(), state.error);
        return;
    }

    for (const std::string& layer : targetLayers) {
        const E2LayerMembershipStats& stats = state.layerStats[layer];
        if (stats.expectedSourceSegments !=
            stats.visibleSourceSegments + stats.clippedAwaySourceSegments) {
            emitNativeError(
                r,
                "NATIVE_CONSERVATION_FAILED",
                "expected target segments do not equal visible plus non-visible segments");
            return;
        }
    }
    std::sort(
        state.visibleRecords.begin(),
        state.visibleRecords.end(),
        [](const E2VisibleSegment& left, const E2VisibleSegment& right) {
            if (left.sourceLayer != right.sourceLayer)
                return left.sourceLayer < right.sourceLayer;
            if (left.sourceDefHandle != right.sourceDefHandle)
                return left.sourceDefHandle < right.sourceDefHandle;
            if (left.sourceEntityHandle != right.sourceEntityHandle)
                return left.sourceEntityHandle < right.sourceEntityHandle;
            if (left.lineage.size() != right.lineage.size())
                return left.lineage.size() < right.lineage.size();
            for (size_t i = 0; i < left.lineage.size(); ++i) {
                if (left.lineage[i].insertEntityHandle != right.lineage[i].insertEntityHandle)
                    return left.lineage[i].insertEntityHandle < right.lineage[i].insertEntityHandle;
            }
            return left.subentityOrdinal < right.subentityOrdinal;
        });

    const ACHAR* rawDrawingPath = nullptr;
    pDb->getFilename(rawDrawingPath);
    r << "\"result\":{";
    r << "\"schema\":\"ariadne.e2.native_xclip_membership_raw.v1\"";
    r << ",\"oracle_method\":\"xclip_polygon_segment_intersection\"";
    r << ",\"geometry_scope\":\"" << jsonEscape(state.geometryScope) << "\"";
    r << ",\"host_mode\":\"full_autocad\"";
    r << ",\"native_membership_resolved\":true";
    r << ",\"measurement_granularity\":\"source_segment_instance\"";
    r << ",\"camera_extent_applied\":false";
    r << ",\"layer_visibility_applied\":true";
    r << ",\"entity_visibility_applied\":true";
    r << ",\"dwf_dmm_used_for_membership\":false";
    r << ",\"drawing_path\":\""
      << jsonEscape(rawDrawingPath != nullptr ? acharToAscii(rawDrawingPath) : std::string())
      << "\"";
    r << ",\"root_def_handle\":\"" << jsonEscape(state.rootDefHandle) << "\"";
    r << ",\"target_layers\":";
    e2EmitStringArray(r, targetLayers);
    r << ",\"layer_summary\":[";
    for (size_t i = 0; i < targetLayers.size(); ++i) {
        if (i > 0) r << ",";
        const std::string& layer = targetLayers[i];
        const E2LayerMembershipStats& stats = state.layerStats[layer];
        r << "{\"layer\":\"" << jsonEscape(layer) << "\""
          << ",\"native_source_entity_templates\":" << stats.sourceEntityTemplates.size()
          << ",\"expected_source_segments\":" << stats.expectedSourceSegments
          << ",\"native_visible_source_segments\":" << stats.visibleSourceSegments
          << ",\"clipped_away_source_segments\":" << stats.clippedAwaySourceSegments
          << ",\"excluded_curved_source_segments\":" << stats.excludedCurvedSourceSegments
          << ",\"excluded_degenerate_source_segments\":" << stats.excludedDegenerateSourceSegments
          << ",\"excluded_unsupported_entity_templates\":"
          << stats.excludedUnsupportedEntityTemplates.size()
          << "}";
    }
    r << "]";
    r << ",\"records\":[";
    for (size_t i = 0; i < state.visibleRecords.size(); ++i) {
        if (i > 0) r << ",";
        const E2VisibleSegment& record = state.visibleRecords[i];
        r << "{\"root_def_handle\":\"" << jsonEscape(record.rootDefHandle) << "\""
          << ",\"source_def_handle\":\"" << jsonEscape(record.sourceDefHandle) << "\""
          << ",\"source_entity_handle\":\"" << jsonEscape(record.sourceEntityHandle) << "\""
          << ",\"source_layer\":\"" << jsonEscape(record.sourceLayer) << "\""
          << ",\"lineage_path\":";
        e2EmitLineage(r, record.lineage);
        r << ",\"active_xclip_handles\":";
        e2EmitStringArray(r, record.activeXclipHandles);
        r << ",\"subentity_ordinal\":" << record.subentityOrdinal
          << ",\"clip_fragment_ordinal\":" << record.clipFragmentOrdinal
          << ",\"p0_world\":[" << record.world.p0.x << "," << record.world.p0.y << "]"
          << ",\"p1_world\":[" << record.world.p1.x << "," << record.world.p1.y << "]}";
    }
    r << "]},\"status\":\"ok\"}";
}

class E2NativeDisplayDmmReactor : public AcDMMReactor
{
public:
    E2NativeDisplayDmmReactor(
        const std::vector<std::string>& targetLayers,
        const std::string& metadataMode)
        : mTargetLayers(targetLayers.begin(), targetLayers.end()),
          mMetadataMode(metadataMode),
          mBeginSheets(0), mEndSheets(0), mBeginEntities(0), mEndEntities(0),
          mTargetCallbacks(0), mGraphicIdCallbacks(0), mNodesAssigned(0),
          mNodeAssignmentFailures(0), mPropertiesAdded(0),
          mPropertyAssociationFailures(0)
    {
    }

    void OnBeginSheet(AcDMMSheetReactorInfo*) override
    {
        ++mBeginSheets;
    }

    void OnEndSheet(AcDMMSheetReactorInfo*) override
    {
        ++mEndSheets;
    }

    void OnBeginEntity(AcDMMEntityReactorInfo* pInfo) override
    {
        ++mBeginEntities;
        if (pInfo == nullptr || pInfo->entity() == nullptr)
            return;
        const std::string sourceLayer = e2LayerName(pInfo->entity()->layerId());
        const std::string effectiveLayer = e2LayerName(pInfo->effectiveBlockLayerId());
        if (mTargetLayers.find(sourceLayer) == mTargetLayers.end() &&
            mTargetLayers.find(effectiveLayer) == mTargetLayers.end())
            return;

        // Autodesk's documented metadata recipe is stronger than merely
        // assigning a node: AddProperties -> AddNodeToMap -> AddPropertiesIds.
        // Keep explicit arms so the live probe can distinguish our former
        // node-only use from the documented path one variable at a time.
        const int nodeId = pInfo->GetNextAvailableNodeId();
        AcDbObjectIdArray blockPath = pInfo->getEntityBlockRefPath();
        bool propertyAdded = true;
        std::wstring propertyId;
        if (mMetadataMode != "set_current_node_only") {
            const wchar_t* uniqueId = pInfo->UniqueEntityId();
            propertyId = L"ARIADNE_E2_";
            propertyId += uniqueId != nullptr
                ? uniqueId : std::to_wstring(nodeId);
            AcDMMEPlotProperties properties;
            properties.SetId(propertyId.c_str());
            AcDMMEPlotProperty property(
                L"ARIADNE_E2_UNIQUE_ENTITY_ID",
                uniqueId != nullptr ? uniqueId : L"");
            property.SetCategory(L"hidden");
            properties.AddProperty(&property);
            propertyAdded = pInfo->AddProperties(&properties);
            if (propertyAdded)
                ++mPropertiesAdded;
        }

        bool nodeAssigned = false;
        if (nodeId > 0 && mMetadataMode == "official_metadata")
            nodeAssigned = pInfo->AddNodeToMap(
                pInfo->entity()->objectId(), blockPath, nodeId);
        else if (nodeId > 0)
            nodeAssigned = pInfo->SetCurrentNode(nodeId, blockPath);

        if (nodeAssigned)
            ++mNodesAssigned;
        else
            ++mNodeAssignmentFailures;

        if (mMetadataMode != "set_current_node_only") {
            AcDMMNode node;
            AcDMMStringVec propertyIds;
            propertyIds.append(AcDMMWideString(propertyId.c_str()));
            const bool associated = propertyAdded && nodeAssigned &&
                pInfo->GetCurrentEntityNode(node, blockPath) &&
                pInfo->AddPropertiesIds(&propertyIds, node);
            if (!associated)
                ++mPropertyAssociationFailures;
        }
    }

    void OnEndEntity(AcDMMEntityReactorInfo* pInfo) override
    {
        ++mEndEntities;
        if (pInfo == nullptr)
            return;

        AcDbEntity* pEntity = pInfo->entity();
        if (pEntity == nullptr)
            return;

        const std::string sourceLayer = e2LayerName(pEntity->layerId());
        const std::string effectiveLayer = e2LayerName(pInfo->effectiveBlockLayerId());
        std::string matchedTargetLayer;
        if (mTargetLayers.find(sourceLayer) != mTargetLayers.end())
            matchedTargetLayer = sourceLayer;
        else if (mTargetLayers.find(effectiveLayer) != mTargetLayers.end())
            matchedTargetLayer = effectiveLayer;
        if (matchedTargetLayer.empty())
            return;

        E2NativeDisplayRecord record;
        const wchar_t* uniqueId = pInfo->UniqueEntityId();
        record.uniqueEntityId = uniqueId != nullptr
            ? wideToUtf8(std::wstring(uniqueId)) : std::string();
        record.sourceHandle = handleOf(pEntity);
        record.entityClass = pEntity->isA() != nullptr
            ? acharToAscii(pEntity->isA()->name()) : std::string();
        record.sourceLayer = sourceLayer;
        record.effectiveLayer = effectiveLayer;
        record.matchedTargetLayer = matchedTargetLayer;

        const AcDbObjectIdArray& blockPath = pInfo->getEntityBlockRefPath();
        for (int i = 0; i < blockPath.length(); ++i)
            record.blockRefPath.push_back(handleOfId(blockPath.at(i)));

        AcDMMNode node;
        record.dmmNodeId = pInfo->GetCurrentEntityNode(node, blockPath)
            ? node.nodeNumber() : 0;

        // The SDK explicitly exposes flush() to synchronize the entity callback
        // with the plot driver.  Read graphics only after that barrier; an empty
        // array then remains honest evidence rather than a timing artefact.
        pInfo->flush();
        const AcArray<long>& graphicIds = pInfo->getGraphicIDs();
        for (int i = 0; i < graphicIds.length(); ++i)
            record.graphicIds.push_back(graphicIds.at(i));
        record.graphicIdObserved = graphicIds.length() > 0;

        ++mTargetCallbacks;
        if (record.graphicIdObserved)
            ++mGraphicIdCallbacks;
        mRecords.push_back(record);
    }

    int beginSheets() const { return mBeginSheets; }
    int endSheets() const { return mEndSheets; }
    int beginEntities() const { return mBeginEntities; }
    int endEntities() const { return mEndEntities; }
    int targetCallbacks() const { return mTargetCallbacks; }
    int graphicIdCallbacks() const { return mGraphicIdCallbacks; }
    int nodesAssigned() const { return mNodesAssigned; }
    int nodeAssignmentFailures() const { return mNodeAssignmentFailures; }
    int propertiesAdded() const { return mPropertiesAdded; }
    int propertyAssociationFailures() const { return mPropertyAssociationFailures; }
    const std::string& metadataMode() const { return mMetadataMode; }
    const std::vector<E2NativeDisplayRecord>& records() const { return mRecords; }

private:
    std::set<std::string> mTargetLayers;
    std::string mMetadataMode;
    std::vector<E2NativeDisplayRecord> mRecords;
    int mBeginSheets;
    int mEndSheets;
    int mBeginEntities;
    int mEndEntities;
    int mTargetCallbacks;
    int mGraphicIdCallbacks;
    int mNodesAssigned;
    int mNodeAssignmentFailures;
    int mPropertiesAdded;
    int mPropertyAssociationFailures;
};

class E2NativeDisplayPublishReactor : public AcPublishReactor
{
public:
    E2NativeDisplayPublishReactor(
        E2NativeDisplayDmmReactor& dmm,
        ACGLOBADDDMMREACTOR addDmm,
        ACGLOBREMOVEDMMREACTOR removeDmm)
        : mDmm(dmm), mAddDmm(addDmm), mRemoveDmm(removeDmm),
          mDmmRegistered(false), mPublishStarted(false), mPublishEnded(false),
          mPublishFailed(false)
    {
    }

    void OnAboutToBeginPublishing(AcPublishBeginJobInfo*) override
    {
        mPublishStarted = true;
        if (!mDmmRegistered && mAddDmm != nullptr) {
            // Export resolved from aceplotx.crx: AcGlobAddDMMReactor.
            mAddDmm(&mDmm);
            mDmmRegistered = true;
        }
    }

    void OnEndPublish(AcPublishReactorInfo*) override
    {
        mPublishEnded = true;
        detachDmm();
    }

    void OnCancelledOrFailedPublishing(AcPublishReactorInfo*) override
    {
        mPublishFailed = true;
        detachDmm();
    }

    void detachDmm()
    {
        if (mDmmRegistered && mRemoveDmm != nullptr) {
            // Export resolved from aceplotx.crx: AcGlobRemoveDMMReactor.
            mRemoveDmm(&mDmm);
            mDmmRegistered = false;
        }
    }

    bool publishStarted() const { return mPublishStarted; }
    bool publishEnded() const { return mPublishEnded; }
    bool publishFailed() const { return mPublishFailed; }
    bool dmmRegistered() const { return mDmmRegistered; }

private:
    E2NativeDisplayDmmReactor& mDmm;
    ACGLOBADDDMMREACTOR mAddDmm;
    ACGLOBREMOVEDMMREACTOR mRemoveDmm;
    bool mDmmRegistered;
    bool mPublishStarted;
    bool mPublishEnded;
    bool mPublishFailed;
};

static std::wstring e2NormalizedPath(const std::wstring& value)
{
    std::wstring out(value);
    std::replace(out.begin(), out.end(), L'/', L'\\');
    std::transform(out.begin(), out.end(), out.begin(), towlower);
    return out;
}

static bool e2AllowedOutputPath(const std::wstring& path)
{
    const std::wstring normalized = e2NormalizedPath(path);
    if (normalized.size() < 5 || normalized.substr(normalized.size() - 4) != L".dwf")
        return false;
    if (normalized.rfind(L"d:\\runs\\", 0) == 0)
        return true;
    if (normalized.find(L"\\runs\\") != std::wstring::npos ||
        normalized.find(L"\\staging\\") != std::wstring::npos)
        return true;
    wchar_t tempPath[MAX_PATH] = {};
    const DWORD tempLength = GetTempPathW(MAX_PATH, tempPath);
    if (tempLength > 0 && tempLength < MAX_PATH) {
        const std::wstring normalizedTemp = e2NormalizedPath(std::wstring(tempPath));
        if (normalized.rfind(normalizedTemp, 0) == 0)
            return true;
    }
    return false;
}

static HMODULE e2LoadAcadModule(const wchar_t* moduleName)
{
    HMODULE module = GetModuleHandleW(moduleName);
    if (module != nullptr)
        return module;
    if (!acrxLoadModule(moduleName, 0))
        return nullptr;
    return GetModuleHandleW(moduleName);
}

static void e2EmitStringArray(std::ostringstream& r, const std::vector<std::string>& values)
{
    r << "[";
    for (size_t i = 0; i < values.size(); ++i) {
        if (i > 0) r << ",";
        r << "\"" << jsonEscape(values[i]) << "\"";
    }
    r << "]";
}

static void e2EmitLongArray(std::ostringstream& r, const std::vector<long>& values)
{
    r << "[";
    for (size_t i = 0; i < values.size(); ++i) {
        if (i > 0) r << ",";
        r << values[i];
    }
    r << "]";
}

static void e2EmitDisplayResult(
    std::ostringstream& r,
    const std::string& drawingPath,
    const std::string& outputPath,
    const std::vector<std::string>& targetLayers,
    const E2NativeDisplayDmmReactor& dmm,
    const E2NativeDisplayPublishReactor& publish)
{
    std::map<std::string, int> callbackCount;
    std::map<std::string, int> graphicIdCount;
    std::set<std::string> seenPlacementKeys;
    int duplicatePlacementRecords = 0;
    int compoundGraphicIdRecords = 0;

    for (const E2NativeDisplayRecord& record : dmm.records()) {
        ++callbackCount[record.matchedTargetLayer];
        if (record.graphicIdObserved) {
            ++graphicIdCount[record.matchedTargetLayer];
            if (record.entityClass != "AcDbLine")
                ++compoundGraphicIdRecords;
        }
        std::ostringstream key;
        key << record.uniqueEntityId << "|" << record.sourceHandle;
        for (const std::string& step : record.blockRefPath)
            key << "|" << step;
        if (!seenPlacementKeys.insert(key.str()).second)
            ++duplicatePlacementRecords;
    }

    r << "\"result\":{";
    r << "\"schema\":\"ariadne.e2.native_display_probe_raw.v1\"";
    r << ",\"probe\":\"autocad.dwf_dmm_graphic_id.v1\"";
    r << ",\"measurement_granularity\":\"entity_instance\"";
    r << ",\"metadata_mode\":\"" << jsonEscape(dmm.metadataMode()) << "\"";
    r << ",\"native_visibility_resolved\":false";
    r << ",\"membership_status\":\""
      << (dmm.graphicIdCallbacks() > 0 ? "entity_graphic_ids_observed" : "inconclusive_all_graphic_ids_empty")
      << "\"";
    r << ",\"compound_entity_subsegments_resolved\":false";
    r << ",\"drawing_path\":\"" << jsonEscape(drawingPath) << "\"";
    r << ",\"output_path\":\"" << jsonEscape(outputPath) << "\"";
    r << ",\"publish_started\":" << (publish.publishStarted() ? "true" : "false");
    r << ",\"publish_ended\":" << (publish.publishEnded() ? "true" : "false");
    r << ",\"publish_failed\":" << (publish.publishFailed() ? "true" : "false");
    r << ",\"begin_sheet_callbacks\":" << dmm.beginSheets();
    r << ",\"end_sheet_callbacks\":" << dmm.endSheets();
    r << ",\"begin_entity_callbacks\":" << dmm.beginEntities();
    r << ",\"end_entity_callbacks\":" << dmm.endEntities();
    r << ",\"target_entity_callbacks\":" << dmm.targetCallbacks();
    r << ",\"target_callbacks_with_graphic_ids\":" << dmm.graphicIdCallbacks();
    r << ",\"graphic_id_probe_all_empty\":"
      << (dmm.targetCallbacks() > 0 && dmm.graphicIdCallbacks() == 0 ? "true" : "false");
    r << ",\"dmm_nodes_assigned\":" << dmm.nodesAssigned();
    r << ",\"dmm_node_assignment_failures\":" << dmm.nodeAssignmentFailures();
    r << ",\"dmm_properties_added\":" << dmm.propertiesAdded();
    r << ",\"dmm_property_association_failures\":"
      << dmm.propertyAssociationFailures();
    r << ",\"duplicate_placement_records\":" << duplicatePlacementRecords;
    r << ",\"compound_callbacks_with_graphic_ids\":" << compoundGraphicIdRecords;
    r << ",\"target_layers\":";
    e2EmitStringArray(r, targetLayers);
    r << ",\"layer_summary\":[";
    for (size_t i = 0; i < targetLayers.size(); ++i) {
        if (i > 0) r << ",";
        const std::string& layer = targetLayers[i];
        r << "{\"layer\":\"" << jsonEscape(layer) << "\"";
        r << ",\"entity_callbacks\":" << callbackCount[layer];
        r << ",\"callbacks_with_graphic_ids\":" << graphicIdCount[layer] << "}";
    }
    r << "]";
    r << ",\"records\":[";
    const std::vector<E2NativeDisplayRecord>& records = dmm.records();
    for (size_t i = 0; i < records.size(); ++i) {
        if (i > 0) r << ",";
        const E2NativeDisplayRecord& record = records[i];
        r << "{\"unique_entity_id\":\"" << jsonEscape(record.uniqueEntityId) << "\"";
        r << ",\"source_handle\":\"" << jsonEscape(record.sourceHandle) << "\"";
        r << ",\"entity_class\":\"" << jsonEscape(record.entityClass) << "\"";
        r << ",\"source_layer\":\"" << jsonEscape(record.sourceLayer) << "\"";
        r << ",\"effective_layer\":\"" << jsonEscape(record.effectiveLayer) << "\"";
        r << ",\"matched_target_layer\":\""
          << jsonEscape(record.matchedTargetLayer) << "\"";
        r << ",\"block_ref_path\":";
        e2EmitStringArray(r, record.blockRefPath);
        r << ",\"dmm_node_id\":" << record.dmmNodeId;
        r << ",\"graphic_ids\":";
        e2EmitLongArray(r, record.graphicIds);
        r << ",\"graphic_id_observed\":"
          << (record.graphicIdObserved ? "true" : "false") << "}";
    }
    r << "]},\"status\":\"ok\"}";
}

static void runE2NativeDisplayOracle(
    const std::string& job,
    AcDbDatabase* pDb,
    const std::string& ctxHostMode,
    std::ostringstream& r)
{
    if (ctxHostMode != "full_autocad") {
        emitNativeError(r, "ATTENDED_HOST_REQUIRED",
                        "DWF/DMM display membership requires a dedicated full AutoCAD host");
        return;
    }

    const std::vector<std::string> targetLayers = jsonFindStringArray(job, "target_layers");
    if (targetLayers.empty()) {
        emitNativeError(r, "TARGET_LAYERS_REQUIRED", "target_layers must contain at least one layer");
        return;
    }
    std::set<std::string> uniqueLayers(targetLayers.begin(), targetLayers.end());
    if (uniqueLayers.size() != targetLayers.size()) {
        emitNativeError(r, "DUPLICATE_TARGET_LAYER", "target_layers must be unique");
        return;
    }

    std::string metadataMode = "set_current_node_only";
    jsonFindString(job, "metadata_mode", metadataMode);
    if (metadataMode != "set_current_node_only" &&
        metadataMode != "set_current_node_with_properties" &&
        metadataMode != "official_metadata") {
        emitNativeError(
            r,
            "METADATA_MODE_INVALID",
            "metadata_mode must be set_current_node_only, "
            "set_current_node_with_properties, or official_metadata");
        return;
    }

    std::string outputPathUtf8;
    if (!jsonFindString(job, "output_path", outputPathUtf8) || outputPathUtf8.empty()) {
        emitNativeError(r, "OUTPUT_PATH_REQUIRED", "output_path is required");
        return;
    }
    const std::wstring outputPath = utf8ToWide(outputPathUtf8);
    if (!e2AllowedOutputPath(outputPath)) {
        emitNativeError(r, "OUTPUT_PATH_NOT_ALLOWED",
                        "output_path must be a new .dwf under runs, staging, or the temporary directory");
        return;
    }
    if (GetFileAttributesW(outputPath.c_str()) != INVALID_FILE_ATTRIBUTES) {
        emitNativeError(r, "OUTPUT_ALREADY_EXISTS", "refusing to overwrite an existing DWF artifact");
        return;
    }

    const ACHAR* rawDrawingPath = nullptr;
    if (pDb == nullptr || pDb->getFilename(rawDrawingPath) != Acad::eOk ||
        rawDrawingPath == nullptr || rawDrawingPath[0] == 0) {
        emitNativeError(r, "DRAWING_PATH_UNRESOLVED", "working database has no file-backed drawing path");
        return;
    }
    const std::wstring drawingPath(rawDrawingPath);
    if (e2NormalizedPath(drawingPath) == e2NormalizedPath(outputPath)) {
        emitNativeError(r, "OUTPUT_EQUALS_DRAWING", "DWF output must not replace the staged DWG");
        return;
    }
    const size_t outputSlash = outputPath.find_last_of(L"\\/");
    const size_t outputDot = outputPath.find_last_of(L'.');
    const size_t outputStemStart = outputSlash == std::wstring::npos ? 0 : outputSlash + 1;
    const size_t outputStemLength =
        outputDot != std::wstring::npos && outputDot > outputStemStart
        ? outputDot - outputStemStart : std::wstring::npos;
    const std::wstring outputStem = outputPath.substr(outputStemStart, outputStemLength);
    if (outputStem.empty()) {
        emitNativeError(r, "OUTPUT_NAME_INVALID", "output_path must contain a DWF file name");
        return;
    }

    HMODULE publishModule = e2LoadAcadModule(L"AcPublish.crx");
    HMODULE dmmModule = e2LoadAcadModule(L"AcEPlotX.crx");
    if (publishModule == nullptr || dmmModule == nullptr) {
        emitNativeError(r, "PUBLISH_MODULE_LOAD_FAILED",
                        "AcPublish.crx and AcEPlotX.crx must both load in the attended host");
        return;
    }

    ACGLOBADDPUBLISHREACTOR addPublish = reinterpret_cast<ACGLOBADDPUBLISHREACTOR>(
        GetProcAddress(publishModule, "AcGlobAddPublishReactor"));
    ACGLOBREMOVEPUBLISHREACTOR removePublish = reinterpret_cast<ACGLOBREMOVEPUBLISHREACTOR>(
        GetProcAddress(publishModule, "AcGlobRemovePublishReactor"));
    ACGLOBADDDMMREACTOR addDmm = reinterpret_cast<ACGLOBADDDMMREACTOR>(
        GetProcAddress(dmmModule, "AcGlobAddDMMReactor"));
    ACGLOBREMOVEDMMREACTOR removeDmm = reinterpret_cast<ACGLOBREMOVEDMMREACTOR>(
        GetProcAddress(dmmModule, "AcGlobRemoveDMMReactor"));
    E2ACPLPUBLISHEXECUTE publishExecute = reinterpret_cast<E2ACPLPUBLISHEXECUTE>(
        GetProcAddress(publishModule, "acplPublishExecute"));
    if (addPublish == nullptr || removePublish == nullptr || addDmm == nullptr ||
        removeDmm == nullptr || publishExecute == nullptr) {
        emitNativeError(r, "PUBLISH_REACTOR_EXPORT_MISSING",
                        "required AcPublish or AcEPlotX reactor exports are unavailable");
        return;
    }

    AcDbLayoutManager* layoutManager = acdbHostApplicationServices()->layoutManager();
    AcString layoutName;
    if (layoutManager == nullptr ||
        layoutManager->getActiveLayoutName(layoutName, true, pDb) != Acad::eOk ||
        layoutName.isEmpty()) {
        emitNativeError(r, "ACTIVE_LAYOUT_UNRESOLVED", "could not resolve the active layout");
        return;
    }

    AcPlPlotConfig* plotConfig = nullptr;
    AcPlPlotConfigManager* configManager = acplPlotConfigManager;
    const ACHAR* deviceName = configManager != nullptr
        ? configManager->getStdConfigName(AcPlPlotConfigManager::kDWF6ePlot) : nullptr;
    if (configManager == nullptr || deviceName == nullptr ||
        configManager->setCurrentConfig(plotConfig, deviceName) != Acad::eOk ||
        plotConfig == nullptr) {
        emitNativeError(r, "DWF_PLOT_CONFIG_UNAVAILABLE", "DWF6 ePlot configuration is unavailable");
        return;
    }
    plotConfig->setPlotToFile(true);

    AcPlDSDEntry entry;
    entry.setDwgName(drawingPath.c_str());
    entry.setLayout(layoutName.constPtr());
    // kSingleDWF derives the produced leaf from the sheet title even when
    // destinationName is populated.  Bind the title to the requested output
    // stem so the artifact path and the hash-bound receipt cannot diverge.
    entry.setTitle(outputStem.c_str());
    entry.setSetupType(AcPlDSDEntry::kOriginalPS);

    AcPlDSDEntries entries;
    entries.append(entry);
    AcPlDSDData dsd;
    dsd.setDSDEntries(entries);
    dsd.setDestinationName(outputPath.c_str());
    if (outputSlash != std::wstring::npos)
        dsd.setProjectPath(outputPath.substr(0, outputSlash).c_str());
    dsd.setSheetType(AcPlDSDEntry::kSingleDWF);
    dsd.setIsHomogeneous(true);
    dsd.setNoOfCopies(1);
    dsd.setViewFile(false);
    dsd.setPlotStampOn(false);
    dsd.setPromptForDwfName(false);
    dsd.setInitializeLayouts(false);

    E2NativeDisplayDmmReactor dmm(targetLayers, metadataMode);
    E2NativeDisplayPublishReactor publish(dmm, addDmm, removeDmm);
    addPublish(&publish);
    bool publishCallReturned = false;
    try {
        publishExecute(dsd, plotConfig, false);
        publishCallReturned = true;
    }
    catch (...) {
        publish.detachDmm();
        removePublish(&publish);
        delete plotConfig;
        emitNativeError(r, "PUBLISH_EXECUTION_EXCEPTION", "acplPublishExecute raised an exception");
        return;
    }
    publish.detachDmm();
    removePublish(&publish);
    delete plotConfig;

    if (!publishCallReturned || !publish.publishStarted() ||
        dmm.beginSheets() <= 0 || dmm.endSheets() <= 0 || dmm.endEntities() <= 0) {
        emitNativeError(r, "DMM_REACTOR_NOT_FIRED",
                        "publish returned without a complete DMM sheet/entity callback trace");
        return;
    }
    if (publish.publishFailed()) {
        emitNativeError(r, "PUBLISH_FAILED", "AutoCAD reported cancelled or failed publishing");
        return;
    }
    if (GetFileAttributesW(outputPath.c_str()) == INVALID_FILE_ATTRIBUTES) {
        emitNativeError(r, "DWF_OUTPUT_MISSING", "publish callbacks fired but the DWF artifact is missing");
        return;
    }

    e2EmitDisplayResult(
        r,
        wideToUtf8(drawingPath),
        outputPathUtf8,
        targetLayers,
        dmm,
        publish);
}
