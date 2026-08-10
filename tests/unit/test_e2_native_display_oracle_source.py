from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
JOB_SOURCE = REPO / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
ORACLE_SOURCE = (
    REPO
    / "src"
    / "Ariadne.AcadNative"
    / "families"
    / "e2_display_oracle.inc"
)
REGISTRY = REPO / "config" / "operations.v2.json"
ATTENDED_RUNNER = REPO / "tools" / "attended" / "run_attended_job.ps1"


def test_native_job_keeps_only_spatial_filter_membership_for_e2():
    job = JOB_SOURCE.read_text(encoding="utf-8")
    registry = REGISTRY.read_text(encoding="utf-8-sig")

    assert '{ "e2.inspect.xclip_membership", "experiment_oracle" }' in job
    assert 'else if (op == "e2.inspect.xclip_membership")' in job
    assert "runE2NativeXclipMembership(job, pDb, jobHostMode, r)" in job
    assert '#include "families/e2_display_oracle.inc"' in job

    # The public CADAgent route owns this attended operation.  Native source
    # presence alone must not promote it into the generic operation registry.
    assert '"id": "e2.inspect.xclip_membership"' not in registry

    removed_operations = (
        '{ "e2.fixture.create_xclip", "experiment_fixture" }',
        'else if (op == "e2.fixture.create_xclip")',
        '{ "plot.engine.run", "plot_publish" }',
        'else if (op == "plot.engine.run")',
    )
    for operation in removed_operations:
        assert operation not in job


def test_native_membership_source_has_no_fixture_or_dwf_dmm_publish_arm():
    job = JOB_SOURCE.read_text(encoding="utf-8")
    source = ORACLE_SOURCE.read_text(encoding="utf-8")

    removed_symbols = (
        "runE2CreateXclipFixture",
        "runE2NativeDisplayOracle",
        "E2NativeDisplayDmmReactor",
        "E2NativeDisplayPublishReactor",
        "AcDMMReactor",
        "AcPublishReactor",
        "AcGlobAddDMMReactor",
        "acplPublishExecute",
        "AcPublish",
        "AcPl",
        "E2ACPLPUBLISHEXECUTE",
        "E2_DMM_",
        "DWF",
        "DMM",
    )
    for symbol in removed_symbols:
        assert symbol not in source

    removed_includes = (
        '"dbplotsettings.h"',
        '"dbplotsetval.h"',
        '"acdmmapi.h"',
        '"AcPublishReactors.h"',
        '"AcPlPlotConfigMgr.h"',
        '"AcPlPlotConfig.h"',
        '"AcPlDSDData.h"',
        '"AcPlDSDEntry.h"',
        '"acplmisc.h"',
    )
    for include in removed_includes:
        assert include not in job


def test_attended_runner_can_load_an_isolated_proof_build():
    source = ATTENDED_RUNNER.read_text(encoding="utf-8-sig")

    assert "[string]$NativeBinDir = ''" in source
    assert "Join-Path $NativeBinDir 'Ariadne.AcadNativeDbx.dbx'" in source
    assert "Join-Path $NativeBinDir 'Ariadne.AcadNative.arx'" in source
    assert '$launchArgs = "`"$StagedDwg`" /nologo /b `"$scr`""' in source
    assert "-ArgumentList $launchArgs" in source


def test_native_job_wires_spatial_filter_membership_as_a_distinct_experiment_op():
    job = JOB_SOURCE.read_text(encoding="utf-8")
    source = ORACLE_SOURCE.read_text(encoding="utf-8")

    assert "AcDbSpatialFilter" in source
    assert "getOriginalInverseBlockXform" in source
    assert "native_membership_resolved" in source
    assert "xclip_polygon_segment_intersection" in source
    assert "e2ReadBlockReferenceClip" in source
    assert "static void e2EmitStringArray(" in source
    assert "runE2NativeXclipMembership" in source
    assert "e2.inspect.xclip_membership" in job


def test_linear_segments_exclude_degenerate_source_and_world_collapses():
    source = ORACLE_SOURCE.read_text(encoding="utf-8")

    assert 'kE2GeometryScopeStrictLayerEntities = "strict_layer_entities_v1"' in source
    assert 'kE2GeometryScopeLinearSegments = "linear_segments_v1"' in source
    assert '"DEGENERATE_TARGET_LINE"' in source
    assert '"DEGENERATE_TARGET_POLYLINE"' in source
    assert '"DEGENERATE_WORLD_TARGET"' in source
    assert "excludedDegenerateSourceSegments" in source
    assert '\\"excluded_degenerate_source_segments\\":' in source

    primitive_segments = source[source.index("static bool e2PrimitiveSegments") :]
    line_branch = primitive_segments[
        primitive_segments.index("if (AcDbLine* pLine") : primitive_segments.index(
            "if (AcDbPolyline* pPolyline"
        )
    ]
    assert "if (linearSegments)" in line_branch
    assert "++stats.excludedDegenerateSourceSegments;" in line_branch
    assert line_branch.index("++stats.excludedDegenerateSourceSegments;") < line_branch.index(
        '"DEGENERATE_TARGET_LINE"'
    )

    world_collapse = source[source.index("p0.transformBy(parentWorld)") :]
    world_collapse = world_collapse[: world_collapse.index("std::vector<E2Segment2> fragments")]
    assert "if (state.geometryScope == kE2GeometryScopeLinearSegments)" in world_collapse
    assert "++stats.excludedDegenerateSourceSegments;" in world_collapse
    assert "continue;" in world_collapse
    assert world_collapse.index("++stats.expectedSourceSegments;") > world_collapse.index(
        "++stats.excludedDegenerateSourceSegments;"
    )
    assert (
        "stats.expectedSourceSegments !=\n"
        "            stats.visibleSourceSegments + stats.clippedAwaySourceSegments"
    ) in source


def test_linear_scope_preserves_curved_and_unsupported_exclusion_accounting():
    source = ORACLE_SOURCE.read_text(encoding="utf-8")

    assert '"TARGET_BULGE_UNSUPPORTED"' in source
    assert '"TARGET_ENTITY_TYPE_UNSUPPORTED"' in source
    assert "excludedCurvedSourceSegments" in source
    assert "excludedUnsupportedEntityTemplates" in source
    assert '\\"excluded_curved_source_segments\\":' in source
    assert '\\"excluded_unsupported_entity_templates\\":' in source
    assert "E2PrimitiveSegment" in source


def test_xclip_membership_does_not_change_unrelated_block_record_origin_json():
    job = JOB_SOURCE.read_text(encoding="utf-8")
    block_record_function = job[job.index("static std::string blockTableRecordsJson") :]
    block_record_function = block_record_function[
        : block_record_function.index("static std::string layoutsRichJson")
    ]

    assert "pBTR->origin()" not in block_record_function
    assert '\\"origin\\":[' not in block_record_function
