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


def test_native_job_wires_experiment_only_plot_oracle_without_registry_promotion():
    job = JOB_SOURCE.read_text(encoding="utf-8")
    registry = REGISTRY.read_text(encoding="utf-8-sig")

    assert '{ "plot.engine.run", "plot_publish" }' in job
    assert 'else if (op == "plot.engine.run")' in job
    assert "runE2NativeDisplayOracle(job, pDb, jobHostMode, r)" in job
    assert '{ "e2.fixture.create_xclip", "experiment_fixture" }' in job
    assert 'else if (op == "e2.fixture.create_xclip")' in job
    assert "runE2CreateXclipFixture(pDb, jobHostMode, r)" in job
    assert '#include "families/e2_display_oracle.inc"' in job

    # A source-level handler is not enough to promote the public operation.  The
    # registry stays hard-blocked until a real attended AutoCAD run proves it.
    plot_record = registry[registry.index('"id": "plot.engine.run"') :]
    plot_record = plot_record[: plot_record.index("\n    },")]
    assert '"status": "blocked"' in plot_record
    assert '"implementation_strategy": "hard_blocked"' in plot_record


def test_probe_records_raw_graphic_ids_without_claiming_visibility():
    source = ORACLE_SOURCE.read_text(encoding="utf-8")

    assert "class E2NativeDisplayDmmReactor : public AcDMMReactor" in source
    assert "void OnEndEntity(AcDMMEntityReactorInfo* pInfo) override" in source
    assert "pInfo->UniqueEntityId()" in source
    assert "pInfo->entity()->layerId()" in source
    assert "pInfo->effectiveBlockLayerId()" in source
    assert "mTargetLayers.find(sourceLayer)" in source
    assert "mTargetLayers.find(effectiveLayer)" in source
    assert "pInfo->getEntityBlockRefPath()" in source
    assert "pInfo->GetNextAvailableNodeId()" in source
    assert "pInfo->SetCurrentNode(nodeId, blockPath)" in source
    assert "pInfo->GetCurrentEntityNode(node, blockPath)" in source
    assert "pInfo->flush()" in source
    assert "pInfo->getGraphicIDs()" in source
    assert '"native_visibility_resolved\\\":false"' in source
    assert "inconclusive_all_graphic_ids_empty" in source
    assert '"visible\\\":"' not in source


def test_probe_keeps_official_metadata_recipe_as_a_separate_intervention_arm():
    source = ORACLE_SOURCE.read_text(encoding="utf-8")

    assert 'metadataMode != "set_current_node_only"' in source
    assert 'mMetadataMode == "official_metadata"' in source
    assert "pInfo->AddProperties(&properties)" in source
    assert "pInfo->AddNodeToMap(" in source
    assert "pInfo->AddPropertiesIds(&propertyIds, node)" in source
    assert 'metadataMode != "set_current_node_with_properties"' in source
    assert 'metadataMode != "official_metadata"' in source
    assert '"metadata_mode must be set_current_node_only, "' in source


def test_fixture_builds_one_visible_and_one_xclip_rejected_target_line():
    source = ORACLE_SOURCE.read_text(encoding="utf-8")

    assert "runE2CreateXclipFixture" in source
    assert 'ACRX_T("E2_DMM_VISIBLE")' in source
    assert 'ACRX_T("E2_DMM_CLIPPED")' in source
    assert "AcDbSpatialFilter* pSpatialFilter = new AcDbSpatialFilter();" in source
    assert "pSpatialFilter->setDefinition(" in source
    assert "visible_source_handle" in source
    assert "clipped_source_handle" in source


def test_oracle_uses_publish_lifecycle_and_fails_closed():
    source = ORACLE_SOURCE.read_text(encoding="utf-8")

    assert "OnAboutToBeginPublishing" in source
    assert "OnEndPublish" in source
    assert "OnCancelledOrFailedPublishing" in source
    assert "AcGlobAddDMMReactor" in source
    assert "AcGlobRemoveDMMReactor" in source
    assert "acplPublishExecute" in source
    assert 'GetProcAddress(publishModule, "acplPublishExecute")' in source
    assert "entry.setTitle(outputStem.c_str())" in source
    assert 'ctxHostMode != "full_autocad"' in source
    assert "DMM_REACTOR_NOT_FIRED" in source
    assert "target_layers" in source
    assert "output_path" in source


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
    registry = REGISTRY.read_text(encoding="utf-8-sig")

    assert '{ "e2.inspect.xclip_membership", "experiment_oracle" }' in job
    assert 'else if (op == "e2.inspect.xclip_membership")' in job
    assert "runE2NativeXclipMembership(job, pDb, jobHostMode, r)" in job
    assert "AcDbSpatialFilter" in source
    assert "getOriginalInverseBlockXform" in source
    assert "native_membership_resolved" in source
    assert "xclip_polygon_segment_intersection" in source
    # This remains an experiment-only high-level cadagent route. It must not be
    # silently promoted into the generic public operation registry by source
    # presence alone.
    assert '"id": "e2.inspect.xclip_membership"' not in registry


def test_native_membership_scope_keeps_strict_fail_closed_and_accounts_linear_exclusions():
    source = ORACLE_SOURCE.read_text(encoding="utf-8")

    assert 'kE2GeometryScopeStrictLayerEntities = "strict_layer_entities_v1"' in source
    assert 'kE2GeometryScopeLinearSegments = "linear_segments_v1"' in source
    assert '"GEOMETRY_SCOPE_INVALID"' in source
    assert 'state.geometryScope == kE2GeometryScopeLinearSegments' in source
    assert '"TARGET_BULGE_UNSUPPORTED"' in source
    assert '"TARGET_ENTITY_TYPE_UNSUPPORTED"' in source
    assert "excludedCurvedSourceSegments" in source
    assert "excludedDegenerateSourceSegments" in source
    assert "excludedUnsupportedEntityTemplates" in source
    assert '\\"excluded_curved_source_segments\\":' in source
    assert '\\"excluded_degenerate_source_segments\\":' in source
    assert '\\"excluded_unsupported_entity_templates\\":' in source
    assert '\\"geometry_scope\\":\\"' in source
    assert "E2PrimitiveSegment" in source
