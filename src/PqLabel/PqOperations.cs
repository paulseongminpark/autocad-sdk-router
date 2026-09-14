#nullable enable
using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;

namespace PqLabel;

// Shared by palette/commands and the structured router job adapter.
public sealed partial class PqCommands
{
    private static void ApplyClassRecursive(
        ObjectId entityId,
        string? classId,
        string? classKind,
        bool clear,
        Transaction transaction,
        HashSet<ObjectId> visitedDefinitions,
        MutationStats stats)
    {
        Entity entity;
        try
        {
            entity = (Entity)transaction.GetObject(entityId, OpenMode.ForRead, false);
        }
        catch (Autodesk.AutoCAD.Runtime.Exception)
        {
            stats.SkippedReadOnly++;
            return;
        }

        if (entity is BlockReference blockReference)
        {
            // A block reference derives its class from its contents. Remove any
            // older reference-level label so it cannot override that inference.
            MutateLeaf(entityId, null, null, true, transaction, stats);

            var definitionId = PqClassResolver.GetSemanticDefinitionId(blockReference);
            if (!visitedDefinitions.Add(definitionId))
                return;

            BlockTableRecord definition;
            try
            {
                definition = (BlockTableRecord)transaction.GetObject(definitionId, OpenMode.ForRead);
            }
            catch (Autodesk.AutoCAD.Runtime.Exception)
            {
                stats.SkippedReadOnly++;
                return;
            }

            if (definition.IsFromExternalReference || definition.IsFromOverlayReference)
            {
                stats.SkippedXrefs++;
                return;
            }

            foreach (ObjectId childId in definition)
                ApplyClassRecursive(
                    childId, classId, classKind, clear,
                    transaction, visitedDefinitions, stats);
            return;
        }

        MutateLeaf(entityId, classId, classKind, clear, transaction, stats);
    }

    private static void MutateLeaf(
        ObjectId entityId,
        string? classId,
        string? classKind,
        bool clear,
        Transaction transaction,
        MutationStats stats)
    {
        try
        {
            var entity = (Entity)transaction.GetObject(
                entityId, OpenMode.ForWrite, false, true);
            var changed = clear
                ? PqXData.ClearClass(entity)
                : PqXData.SetClass(entity, classId!, classKind);
            if (changed)
                stats.Changed++;
        }
        catch (Autodesk.AutoCAD.Runtime.Exception)
        {
            stats.SkippedReadOnly++;
        }
    }

    private static InstanceMutationResult MutateInstanceSelection(
        Document document,
        SelectionSet selection,
        string? instanceId,
        bool clear)
    {
        var changed = 0;
        using var transaction = document.Database.TransactionManager.StartTransaction();
        PqXData.EnsureRegistered(document.Database, transaction);

        if (!clear)
        {
            var cache = new Dictionary<ObjectId, ClassSummary>();
            var stuff = selection.GetObjectIds().Count(id =>
            {
                if (id.IsNull ||
                    transaction.GetObject(id, OpenMode.ForRead, false) is not Entity entity)
                    return false;
                return PqClassResolver.Resolve(entity, transaction, cache).ClassKind == "STUFF";
            });
            if (stuff > 0)
                return new InstanceMutationResult(0, stuff);
        }

        foreach (SelectedObject selected in selection)
        {
            if (selected.ObjectId.IsNull)
                continue;

            try
            {
                var entity = (Entity)transaction.GetObject(
                    selected.ObjectId, OpenMode.ForWrite, false, true);
                var didChange = clear
                    ? PqXData.ClearInstance(entity)
                    : PqXData.SetInstance(entity, instanceId!);
                if (didChange)
                    changed++;
            }
            catch (Autodesk.AutoCAD.Runtime.Exception)
            {
                // Read-only objects such as entities inside an attached Xref are skipped.
            }
        }

        transaction.Commit();
        document.Editor.Regen();
        return new InstanceMutationResult(changed, 0);
    }


    private static ExistingClassStats ScanExistingClassLabels(
        Document document,
        SelectionSet selection,
        string requestedClass)
    {
        var labels = new List<string>();
        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var visited = new HashSet<ObjectId>();
        foreach (SelectedObject selected in selection)
        {
            if (!selected.ObjectId.IsNull)
                CollectExistingLabels(selected.ObjectId, transaction, visited, labels);
        }

        return new ExistingClassStats(
            labels.Count,
            labels.Count(value => !value.Equals(requestedClass,
                StringComparison.OrdinalIgnoreCase)));
    }

    private static void CollectExistingLabels(
        ObjectId entityId,
        Transaction transaction,
        HashSet<ObjectId> visitedDefinitions,
        List<string> labels)
    {
        if (transaction.GetObject(entityId, OpenMode.ForRead, false) is not Entity entity)
            return;

        if (entity is not BlockReference blockReference)
        {
            if (PqXData.ReadClass(entity) is { } classId)
                labels.Add(classId);
            return;
        }

        if (PqXData.ReadClass(blockReference) is { } directClass &&
            !PqXData.IsDerivedClass(blockReference))
            labels.Add(directClass);

        var definitionId = PqClassResolver.GetSemanticDefinitionId(blockReference);
        if (!visitedDefinitions.Add(definitionId))
            return;
        var definition = (BlockTableRecord)transaction.GetObject(definitionId, OpenMode.ForRead);
        if (definition.IsFromExternalReference || definition.IsFromOverlayReference)
            return;
        foreach (ObjectId childId in definition)
            CollectExistingLabels(childId, transaction, visitedDefinitions, labels);
    }


    private static int CountInstancesInSelection(
        Document document,
        SelectionSet selection)
    {
        var count = 0;
        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var visitedDefinitions = new HashSet<ObjectId>();
        foreach (SelectedObject selected in selection)
        {
            if (!selected.ObjectId.IsNull)
                count += CountInstancesRecursive(
                    selected.ObjectId, transaction, visitedDefinitions);
        }
        return count;
    }

    private static int CountInstancesRecursive(
        ObjectId entityId,
        Transaction transaction,
        HashSet<ObjectId> visitedDefinitions)
    {
        if (transaction.GetObject(entityId, OpenMode.ForRead, false) is not Entity entity)
            return 0;

        var count = PqXData.ReadInstance(entity) is null ? 0 : 1;
        if (entity is not BlockReference blockReference)
            return count;

        var definitionId = PqClassResolver.GetSemanticDefinitionId(blockReference);
        if (!visitedDefinitions.Add(definitionId))
            return count;
        var definition = (BlockTableRecord)transaction.GetObject(definitionId, OpenMode.ForRead);
        if (definition.IsFromExternalReference || definition.IsFromOverlayReference)
            return count;
        foreach (ObjectId childId in definition)
            count += CountInstancesRecursive(childId, transaction, visitedDefinitions);
        return count;
    }

    private static int CountInstancesForClass(Document document, string classId)
    {
        var count = 0;
        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var blockTable = (BlockTable)transaction.GetObject(
            document.Database.BlockTableId, OpenMode.ForRead);
        var cache = new Dictionary<ObjectId, ClassSummary>();
        foreach (ObjectId recordId in blockTable)
        {
            var record = (BlockTableRecord)transaction.GetObject(recordId, OpenMode.ForRead);
            if (record.IsFromExternalReference || record.IsFromOverlayReference)
                continue;
            foreach (ObjectId entityId in record)
            {
                if (transaction.GetObject(entityId, OpenMode.ForRead, false) is not Entity entity ||
                    PqXData.ReadInstance(entity) is null)
                    continue;
                var summary = PqClassResolver.Resolve(entity, transaction, cache);
                if (summary.State == ClassState.Uniform &&
                    string.Equals(summary.ClassId, classId, StringComparison.OrdinalIgnoreCase))
                    count++;
            }
        }
        return count;
    }

    private sealed class MutationStats
    {
        internal int Changed { get; set; }
        internal int SkippedXrefs { get; set; }
        internal int SkippedReadOnly { get; set; }
    }

    private sealed record QueryResult(ObjectId[] Ids, int MixedOrIncompleteBlocks);
    private sealed record ExistingClassStats(int Existing, int Different);
    private sealed record InstanceMutationResult(int Changed, int StuffRejected);
    private sealed record WholeDrawingMutation(int Changed, ClassSyncResult Sync);

    private static WholeDrawingMutation MutateAllLabels(bool migrate, string? classId, string? kind)
    {
        var doc = ActiveDocument;
        if (!migrate && kind is not ("THING" or "STUFF")) throw new ArgumentException("Invalid class_kind.");
        if (kind == "STUFF" && CountInstancesForClass(doc, classId!) > 0)
            throw new InvalidOperationException("Remove instance records before changing class kind to STUFF.");
        using var tr = doc.Database.TransactionManager.StartTransaction();
        PqXData.EnsureRegistered(doc.Database, tr);
        var changed = 0;
        foreach (ObjectId recordId in (BlockTable)tr.GetObject(doc.Database.BlockTableId, OpenMode.ForRead))
        {
            var record = (BlockTableRecord)tr.GetObject(recordId, OpenMode.ForRead);
            if (record.IsFromExternalReference || record.IsFromOverlayReference) continue;
            foreach (ObjectId id in record)
            {
                if (tr.GetObject(id, OpenMode.ForRead) is not Entity entity) continue;
                if (!migrate && (PqXData.IsDerivedClass(entity) ||
                    !string.Equals(PqXData.ReadClass(entity), classId, StringComparison.OrdinalIgnoreCase))) continue;
                entity.UpgradeOpen();
                if (migrate ? PqXData.MigrateLegacyToRhino(entity) : PqXData.SetClass(entity, classId!, kind)) changed++;
            }
        }
        var sync = PqClassSynchronizer.Synchronize(doc.Database, tr);
        tr.Commit();
        return new WholeDrawingMutation(changed, sync);
    }
}
