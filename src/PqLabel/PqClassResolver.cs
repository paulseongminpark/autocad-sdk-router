#nullable enable
using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.AutoCAD.DatabaseServices;

namespace PqLabel;

internal enum ClassState
{
    Unlabeled,
    Uniform,
    Mixed
}

internal sealed record ClassSummary(ClassState State, string? ClassId, string? ClassKind)
{
    internal static readonly ClassSummary Unlabeled = new(ClassState.Unlabeled, null, null);
    internal static readonly ClassSummary Mixed = new(ClassState.Mixed, null, null);
    internal static ClassSummary Uniform(string classId, string? classKind = null) =>
        new(ClassState.Uniform, classId, classKind);
}

internal static class PqClassResolver
{
    internal static ClassSummary Resolve(
        Entity entity,
        Transaction transaction,
        Dictionary<ObjectId, ClassSummary> definitionCache)
    {
        // Read legacy/direct labels if present. New writes put class data on leaf entities.
        var directClass = PqXData.ReadClass(entity);
        if (!string.IsNullOrWhiteSpace(directClass) &&
            (entity is not BlockReference || !PqXData.IsDerivedClass(entity)))
            return ClassSummary.Uniform(directClass, PqXData.ReadClassKind(entity));

        if (entity is not BlockReference blockReference)
            return ClassSummary.Unlabeled;

        var definitionId = GetSemanticDefinitionId(blockReference);
        return ResolveDefinition(definitionId, transaction, definitionCache, new HashSet<ObjectId>());
    }

    internal static ObjectId GetSemanticDefinitionId(BlockReference blockReference)
    {
        return blockReference.IsDynamicBlock && !blockReference.DynamicBlockTableRecord.IsNull
            ? blockReference.DynamicBlockTableRecord
            : blockReference.BlockTableRecord;
    }

    private static ClassSummary ResolveDefinition(
        ObjectId definitionId,
        Transaction transaction,
        Dictionary<ObjectId, ClassSummary> cache,
        HashSet<ObjectId> recursionStack)
    {
        if (cache.TryGetValue(definitionId, out var cached))
            return cached;

        if (!recursionStack.Add(definitionId))
            return ClassSummary.Mixed;

        var classes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var kinds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var hasUnknownKind = false;
        var hasUnlabeled = false;

        try
        {
            var definition = (BlockTableRecord)transaction.GetObject(definitionId, OpenMode.ForRead);
            foreach (ObjectId childId in definition)
            {
                if (transaction.GetObject(childId, OpenMode.ForRead, false) is not Entity child)
                    continue;

                ClassSummary childSummary;
                var directClass = PqXData.ReadClass(child);
                if (!string.IsNullOrWhiteSpace(directClass) &&
                    (child is not BlockReference || !PqXData.IsDerivedClass(child)))
                {
                    childSummary = ClassSummary.Uniform(
                        directClass, PqXData.ReadClassKind(child));
                }
                else if (child is BlockReference nested)
                {
                    childSummary = ResolveDefinition(
                        GetSemanticDefinitionId(nested), transaction, cache, recursionStack);
                }
                else
                {
                    childSummary = ClassSummary.Unlabeled;
                }

                if (childSummary.State == ClassState.Mixed)
                {
                    classes.Add("__PQ_MIXED__");
                }
                else if (childSummary.State == ClassState.Uniform && childSummary.ClassId is not null)
                {
                    classes.Add(childSummary.ClassId);
                    if (childSummary.ClassKind is { } kind)
                        kinds.Add(kind);
                    else
                        hasUnknownKind = true;
                }
                else
                {
                    hasUnlabeled = true;
                }
            }
        }
        catch (Autodesk.AutoCAD.Runtime.Exception)
        {
            recursionStack.Remove(definitionId);
            return ClassSummary.Unlabeled;
        }

        recursionStack.Remove(definitionId);

        ClassSummary result;
        if (classes.Count == 1 && !hasUnlabeled && !classes.Contains("__PQ_MIXED__"))
            result = ClassSummary.Uniform(
                classes.First(),
                kinds.Count == 1 && !hasUnknownKind ? kinds.First() : null);
        else if (classes.Count == 0)
            result = ClassSummary.Unlabeled;
        else
            result = ClassSummary.Mixed;

        cache[definitionId] = result;
        return result;
    }
}
