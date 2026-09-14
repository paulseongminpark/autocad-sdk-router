#nullable enable
using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;

namespace PqLabel;

internal sealed record ClassInventoryRow(
    string ClassId,
    string ClassKind,
    int Objects,
    int Instances,
    int BlockInstances,
    int StandaloneEntities);

internal sealed record ClassInventoryResult(
    IReadOnlyList<ClassInventoryRow> Rows,
    int MixedOrIncompleteBlocks,
    int UnresolvedPaths);

internal static class PqClassInventory
{
    internal static ClassInventoryResult ScanCurrentSpace(Document document)
    {
        var counts = new Dictionary<string, MutableCount>(StringComparer.OrdinalIgnoreCase);
        var mixed = 0;
        var unresolved = 0;

        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var currentSpace = (BlockTableRecord)transaction.GetObject(
            document.Database.CurrentSpaceId, OpenMode.ForRead);
        var cache = new Dictionary<ObjectId, ClassSummary>();
        var spaceScope = "SPACE:" + currentSpace.Handle;

        foreach (ObjectId id in currentSpace)
        {
            if (transaction.GetObject(id, OpenMode.ForRead, false) is not Entity entity)
                continue;

            TraverseOccurrence(
                entity,
                parentScope: spaceScope,
                occurrencePath: spaceScope + "/" + entity.Handle,
                transaction,
                cache,
                counts,
                new HashSet<ObjectId>(),
                ref mixed,
                ref unresolved);
        }

        var rows = counts.Values
            .OrderBy(value => value.ClassId, StringComparer.OrdinalIgnoreCase)
            .Select(value => new ClassInventoryRow(
                value.ClassId,
                value.ClassKind,
                value.Objects,
                value.InstanceKeys.Count,
                value.BlockInstances,
                value.StandaloneEntities))
            .ToArray();

        return new ClassInventoryResult(rows, mixed, unresolved);
    }

    private static void TraverseOccurrence(
        Entity entity,
        string parentScope,
        string occurrencePath,
        Transaction transaction,
        Dictionary<ObjectId, ClassSummary> cache,
        Dictionary<string, MutableCount> counts,
        HashSet<ObjectId> recursionStack,
        ref int mixed,
        ref int unresolved)
    {
        var summary = PqClassResolver.Resolve(entity, transaction, cache);

        if (entity is not BlockReference blockReference)
        {
            if (summary.State == ClassState.Uniform && summary.ClassId is not null)
                AddLeaf(entity, summary.ClassId, summary.ClassKind, parentScope, counts);
            return;
        }

        // A homogeneous block is one semantic occurrence. Do not count its leaf
        // geometry again; each outer placement gets its own occurrence path.
        if (summary.State == ClassState.Uniform && summary.ClassId is not null)
        {
            AddBlock(
                blockReference, summary.ClassId, summary.ClassKind,
                parentScope, occurrencePath, counts);
            return;
        }

        if (summary.State == ClassState.Mixed)
            mixed++;

        var definitionId = PqClassResolver.GetSemanticDefinitionId(blockReference);
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

                TraverseOccurrence(
                    child,
                    parentScope: occurrencePath,
                    occurrencePath: occurrencePath + "/" + child.Handle,
                    transaction,
                    cache,
                    counts,
                    recursionStack,
                    ref mixed,
                    ref unresolved);
            }
        }
        catch (Autodesk.AutoCAD.Runtime.Exception)
        {
            // Unloaded/unresolved Xrefs and unreadable definitions cannot be walked.
            unresolved++;
        }
        finally
        {
            recursionStack.Remove(definitionId);
        }
    }

    private static void AddBlock(
        BlockReference blockReference,
        string classId,
        string? classKind,
        string parentScope,
        string occurrencePath,
        Dictionary<string, MutableCount> counts)
    {
        var count = GetCount(classId, counts);
        count.AddKind(classKind);
        count.Objects++;
        count.BlockInstances++;
        count.InstanceKeys.Add(
            PqXData.ReadInstance(blockReference) is { } explicitId
                ? "ID:" + parentScope + ":" + explicitId
                : "BLOCK:" + occurrencePath);
    }

    private static void AddLeaf(
        Entity entity,
        string classId,
        string? classKind,
        string parentScope,
        Dictionary<string, MutableCount> counts)
    {
        var count = GetCount(classId, counts);
        count.AddKind(classKind);
        count.Objects++;
        count.StandaloneEntities++;
        if (PqXData.ReadInstance(entity) is { } explicitId)
            count.InstanceKeys.Add("ID:" + parentScope + ":" + explicitId);
    }

    private static MutableCount GetCount(
        string classId,
        Dictionary<string, MutableCount> counts)
    {
        if (!counts.TryGetValue(classId, out var count))
        {
            count = new MutableCount(classId);
            counts.Add(classId, count);
        }

        return count;
    }

    private sealed class MutableCount
    {
        internal MutableCount(string classId) => ClassId = classId;
        internal string ClassId { get; }
        internal HashSet<string> Kinds { get; } = new(StringComparer.OrdinalIgnoreCase);
        internal bool HasUnknownKind { get; private set; }
        internal string ClassKind =>
            Kinds.Count == 1 && !HasUnknownKind ? Kinds.First() : "UNKNOWN";
        internal int Objects { get; set; }
        internal HashSet<string> InstanceKeys { get; } = new(StringComparer.OrdinalIgnoreCase);
        internal int BlockInstances { get; set; }
        internal int StandaloneEntities { get; set; }

        internal void AddKind(string? kind)
        {
            if (kind is null)
                HasUnknownKind = true;
            else
                Kinds.Add(kind);
        }
    }
}
