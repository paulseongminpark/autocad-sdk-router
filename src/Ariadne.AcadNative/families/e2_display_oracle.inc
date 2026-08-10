//////////////////////////////////////////////////////////////////////////////
// E2 native XCLIP membership oracle.
//
// This family contains only the AcDbSpatialFilter-based membership path used
// by e2.inspect.xclip_membership. It resolves XCLIP polygons and intersects
// them with LINE and straight LWPOLYLINE source segments in world space.
//////////////////////////////////////////////////////////////////////////////

#include <algorithm>
#include <map>
#include <set>

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
// AcDbSpatialFilter XCLIP membership oracle.
//
// The native operation reads XCLIP state from ObjectARX and applies an
// independent polygon/segment intersection algorithm to native LINE and
// straight LWPOLYLINE geometry. The Python shell shares only the stable
// lineage-id convention; it never decides visibility.
// ---------------------------------------------------------------------------

static const double kE2GeometryEpsilon = 1.0e-12;
static const char* kE2GeometryScopeStrictLayerEntities = "strict_layer_entities_v1";
static const char* kE2GeometryScopeLinearSegments = "linear_segments_v1";
static void e2EmitStringArray(
    std::ostringstream& r,
    const std::vector<std::string>& values)
{
    r << "[";
    for (size_t i = 0; i < values.size(); ++i) {
        if (i > 0) r << ",";
        r << "\"" << jsonEscape(values[i]) << "\"";
    }
    r << "]";
}

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
        const E2Segment2 local = {
            e2Point2(pLine->startPoint()),
            e2Point2(pLine->endPoint())
        };
        const E2Point2 localSpan = e2Subtract(local.p1, local.p0);
        if (e2Dot(localSpan, localSpan) <=
            kE2GeometryEpsilon * kE2GeometryEpsilon) {
            if (linearSegments) {
                ++stats.excludedDegenerateSourceSegments;
                return true;
            }
            state.fail(
                "DEGENERATE_TARGET_LINE",
                "target LINE has zero length");
            return false;
        }
        E2PrimitiveSegment segment = {
            local,
            0
        };
        output.push_back(segment);
        return true;
    }
    if (AcDbPolyline* pPolyline = AcDbPolyline::cast(pEntity)) {
        const unsigned int count = pPolyline->numVerts();
        if (count < 2) {
            if (linearSegments)
                return true;  // no source segment exists to account for
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
            if (e2Dot(localSpan, localSpan) <=
                kE2GeometryEpsilon * kE2GeometryEpsilon) {
                if (linearSegments) {
                    ++stats.excludedDegenerateSourceSegments;
                    continue;
                }
                state.fail(
                    "DEGENERATE_TARGET_POLYLINE",
                    "target LWPOLYLINE contains a zero-length segment");
                return false;
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
                if (state.geometryScope == kE2GeometryScopeLinearSegments) {
                    ++stats.excludedDegenerateSourceSegments;
                    continue;
                }
                pEntity->close();
                state.fail("DEGENERATE_WORLD_TARGET", "a target segment collapsed under INSERT transforms");
                return;
            }
            ++stats.expectedSourceSegments;
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
