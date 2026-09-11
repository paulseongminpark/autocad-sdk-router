#nullable enable
using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;

namespace PqLabel;

internal enum PqValidationSeverity
{
    Error,
    Warning
}

internal sealed record PqValidationIssue(
    string Code,
    string Path,
    string ClassId,
    string Message,
    ObjectId TopLevelId,
    PqValidationSeverity Severity = PqValidationSeverity.Error);

internal sealed record PqValidationResult(
    IReadOnlyList<PqValidationIssue> Issues,
    int SemanticObjects,
    int ThingObjects,
    int StuffObjects,
    int UnresolvedPaths)
{
    internal int Errors => Issues.Count(issue => issue.Severity == PqValidationSeverity.Error);
    internal int Warnings => Issues.Count(issue => issue.Severity == PqValidationSeverity.Warning);
    internal int XDataIntegrityIssues => Issues.Count(issue => issue.Code.StartsWith(
        "XDATA_", StringComparison.OrdinalIgnoreCase));
    internal int MissingInstances => Issues.Count(issue => issue.Code == "MISSING_INSTANCE");
    internal int MultiClassInstances => Issues.Count(issue => issue.Code == "MULTI_CLASS_INSTANCE");
    internal int UnknownKinds => Issues.Count(issue => issue.Code == "UNKNOWN_CLASS_KIND");
}

internal static class PqValidation
{
    internal static PqValidationResult ScanCurrentSpace(Document document)
    {
        var issues = new List<PqValidationIssue>();
        var explicitInstances = new Dictionary<string, ExplicitInstance>(
            StringComparer.OrdinalIgnoreCase);
        var semanticObjects = 0;
        var thingObjects = 0;
        var stuffObjects = 0;
        var unresolved = 0;

        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var currentSpace = (BlockTableRecord)transaction.GetObject(
            document.Database.CurrentSpaceId, OpenMode.ForRead);
        ScanPhysicalXData(document.Database, currentSpace.ObjectId, transaction, issues);
        var cache = new Dictionary<ObjectId, ClassSummary>();
        var spaceScope = "SPACE:" + currentSpace.Handle;

        foreach (ObjectId id in currentSpace)
        {
            if (transaction.GetObject(id, OpenMode.ForRead, false) is not Entity entity)
                continue;

            Traverse(
                entity,
                topLevelId: id,
                parentScope: spaceScope,
                path: spaceScope + "/" + entity.Handle,
                transaction,
                cache,
                new HashSet<ObjectId>(),
                explicitInstances,
                issues,
                ref semanticObjects,
                ref thingObjects,
                ref stuffObjects,
                ref unresolved);
        }

        foreach (var observation in explicitInstances.Values)
        {
            if (observation.Classes.Count <= 1)
                continue;

            issues.Add(new PqValidationIssue(
                "MULTI_CLASS_INSTANCE",
                observation.FirstPath,
                string.Join(", ", observation.Classes.OrderBy(value => value)),
                $"INSTANCE_ID '{observation.InstanceId}' is used by multiple classes in one occurrence scope.",
                observation.TopLevelId));
        }

        return new PqValidationResult(
            issues, semanticObjects, thingObjects, stuffObjects, unresolved);
    }

    private static void ScanPhysicalXData(
        Database database,
        ObjectId currentSpaceId,
        Transaction transaction,
        List<PqValidationIssue> issues)
    {
        var blockTable = (BlockTable)transaction.GetObject(
            database.BlockTableId, OpenMode.ForRead);
        foreach (ObjectId recordId in blockTable)
        {
            var record = (BlockTableRecord)transaction.GetObject(recordId, OpenMode.ForRead);
            if (record.IsFromExternalReference || record.IsFromOverlayReference)
                continue;

            foreach (ObjectId entityId in record)
            {
                if (transaction.GetObject(entityId, OpenMode.ForRead, false) is not Entity entity)
                    continue;

                var inspection = PqXDataInspector.Inspect(entity);
                var path = $"BTR:{record.Name}/{entity.Handle}";
                var selectionId = recordId == currentSpaceId ? entityId : ObjectId.Null;
                foreach (var problem in inspection.Problems)
                {
                    issues.Add(new PqValidationIssue(
                        problem.Code,
                        path,
                        inspection.EffectiveClass ?? "<none>",
                        problem.Message,
                        selectionId,
                        problem.Severity));
                }
            }
        }
    }

    private static void Traverse(
        Entity entity,
        ObjectId topLevelId,
        string parentScope,
        string path,
        Transaction transaction,
        Dictionary<ObjectId, ClassSummary> cache,
        HashSet<ObjectId> recursionStack,
        Dictionary<string, ExplicitInstance> explicitInstances,
        List<PqValidationIssue> issues,
        ref int semanticObjects,
        ref int thingObjects,
        ref int stuffObjects,
        ref int unresolved)
    {
        var summary = PqClassResolver.Resolve(entity, transaction, cache);

        if (entity is BlockReference blockReference &&
            summary.State == ClassState.Uniform && summary.ClassId is { } blockClass)
        {
            semanticObjects++;
            CountKind(summary.ClassKind, ref thingObjects, ref stuffObjects);
            ValidateKind(summary.ClassKind, path, blockClass, topLevelId, issues);
            ObserveExplicitInstance(
                PqXData.ReadInstance(blockReference), parentScope, blockClass,
                path, topLevelId, explicitInstances);
            // A homogeneous BlockReference occurrence is an implicit instance,
            // therefore THING does not require a stored INSTANCE_ID here.
            return;
        }

        if (entity is not BlockReference)
        {
            if (summary.State != ClassState.Uniform || summary.ClassId is not { } leafClass)
                return;

            semanticObjects++;
            CountKind(summary.ClassKind, ref thingObjects, ref stuffObjects);
            ValidateKind(summary.ClassKind, path, leafClass, topLevelId, issues);

            var instanceId = PqXData.ReadInstance(entity);
            if (summary.ClassKind == "THING" && instanceId is null)
            {
                issues.Add(new PqValidationIssue(
                    "MISSING_INSTANCE", path, leafClass,
                    "THING leaf is not inside a homogeneous block and has no INSTANCE_ID.",
                    topLevelId));
            }

            ObserveExplicitInstance(
                instanceId, parentScope, leafClass, path, topLevelId, explicitInstances);
            return;
        }

        var unresolvedBlock = (BlockReference)entity;
        var definitionId = PqClassResolver.GetSemanticDefinitionId(unresolvedBlock);
        if (!recursionStack.Add(definitionId))
        {
            unresolved++;
            return;
        }

        try
        {
            var definition = (BlockTableRecord)transaction.GetObject(
                definitionId, OpenMode.ForRead);
            foreach (ObjectId childId in definition)
            {
                if (transaction.GetObject(childId, OpenMode.ForRead, false) is not Entity child)
                    continue;

                Traverse(
                    child, topLevelId, path, path + "/" + child.Handle,
                    transaction, cache, recursionStack, explicitInstances, issues,
                    ref semanticObjects, ref thingObjects, ref stuffObjects, ref unresolved);
            }
        }
        catch (Autodesk.AutoCAD.Runtime.Exception)
        {
            unresolved++;
        }
        finally
        {
            recursionStack.Remove(definitionId);
        }
    }

    private static void ValidateKind(
        string? kind,
        string path,
        string classId,
        ObjectId topLevelId,
        List<PqValidationIssue> issues)
    {
        if (kind is not null)
            return;

        issues.Add(new PqValidationIssue(
            "UNKNOWN_CLASS_KIND", path, classId,
            "CLASS_KIND is missing or inconsistent; THING instance validation is not possible.",
            topLevelId));
    }

    private static void CountKind(string? kind, ref int things, ref int stuff)
    {
        if (kind == "THING")
            things++;
        else if (kind == "STUFF")
            stuff++;
    }

    private static void ObserveExplicitInstance(
        string? instanceId,
        string scope,
        string classId,
        string path,
        ObjectId topLevelId,
        Dictionary<string, ExplicitInstance> observations)
    {
        if (instanceId is null)
            return;

        var key = scope + "\u001f" + instanceId;
        if (!observations.TryGetValue(key, out var observation))
        {
            observation = new ExplicitInstance(instanceId, path, topLevelId);
            observations.Add(key, observation);
        }
        observation.Classes.Add(classId);
    }

    private sealed class ExplicitInstance
    {
        internal ExplicitInstance(string instanceId, string firstPath, ObjectId topLevelId)
        {
            InstanceId = instanceId;
            FirstPath = firstPath;
            TopLevelId = topLevelId;
        }

        internal string InstanceId { get; }
        internal string FirstPath { get; }
        internal ObjectId TopLevelId { get; }
        internal HashSet<string> Classes { get; } = new(StringComparer.OrdinalIgnoreCase);
    }
}
