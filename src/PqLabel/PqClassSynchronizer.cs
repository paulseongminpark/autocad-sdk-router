#nullable enable
using System.Collections.Generic;
using Autodesk.AutoCAD.DatabaseServices;

namespace PqLabel;

internal sealed record ClassSyncResult(int Updated, int Cleared, int Skipped);

internal static class PqClassSynchronizer
{
    internal static ClassSyncResult Synchronize(Database database, Transaction transaction)
    {
        var references = CollectHostBlockReferences(database, transaction);
        var cache = new Dictionary<ObjectId, ClassSummary>();
        var updated = 0;
        var cleared = 0;
        var skipped = 0;

        foreach (var referenceId in references)
        {
            try
            {
                var reference = (BlockReference)transaction.GetObject(
                    referenceId, OpenMode.ForRead, false);

                // Preserve a legacy/manual BlockReference label. New plug-in writes
                // always mark computed parent values with CLASS_SOURCE=DERIVED.
                var directClass = PqXData.ReadClass(reference);
                if (directClass is not null && !PqXData.IsDerivedClass(reference))
                    continue;

                var summary = PqClassResolver.Resolve(reference, transaction, cache);
                if (!reference.IsWriteEnabled)
                    reference.UpgradeOpen();

                if (summary.State == ClassState.Uniform && summary.ClassId is not null)
                {
                    if (PqXData.SetDerivedClass(
                            reference, summary.ClassId, summary.ClassKind))
                        updated++;
                }
                else if (PqXData.ClearDerivedClass(reference))
                {
                    cleared++;
                }
            }
            catch (Autodesk.AutoCAD.Runtime.Exception)
            {
                skipped++;
            }
        }

        return new ClassSyncResult(updated, cleared, skipped);
    }

    private static List<ObjectId> CollectHostBlockReferences(
        Database database,
        Transaction transaction)
    {
        var result = new List<ObjectId>();
        var blockTable = (BlockTable)transaction.GetObject(
            database.BlockTableId, OpenMode.ForRead);

        foreach (ObjectId recordId in blockTable)
        {
            var record = (BlockTableRecord)transaction.GetObject(recordId, OpenMode.ForRead);
            if (record.IsFromExternalReference || record.IsFromOverlayReference)
                continue;

            foreach (ObjectId entityId in record)
            {
                if (transaction.GetObject(entityId, OpenMode.ForRead, false) is BlockReference)
                    result.Add(entityId);
            }
        }

        return result;
    }
}
