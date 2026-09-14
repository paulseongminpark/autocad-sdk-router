#nullable enable
using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.GraphicsInterface;
using Autodesk.AutoCAD.Runtime;

namespace PqLabel;

internal enum PqVisibilityMode
{
    HideMatching,
    IsolateMatching
}

internal sealed record PqVisibilityResult(int HiddenObjects, int MatchingObjects, int UnresolvedPaths);

internal static class PqNestedVisibility
{
    private static readonly object Gate = new();
    private static readonly Dictionary<Database, HashSet<ObjectId>> HiddenByDatabase = new();
    private static readonly Dictionary<Database, FilterSpec> FiltersByDatabase = new();
    private static readonly PqDrawableOverrule DrawableOverrule = new();
    private static bool installed;

    internal static PqVisibilityResult Apply(
        Document document,
        string classId,
        PqVisibilityMode mode)
    {
        var result = BuildHiddenSet(document, classId, mode, out var hidden);
        lock (Gate)
        {
            HiddenByDatabase[document.Database] = hidden;
            FiltersByDatabase[document.Database] = new FilterSpec(classId, mode);
            EnsureInstalled();
        }

        document.Editor.Regen();
        return result;
    }

    internal static void RefreshIfActive(Document document)
    {
        FilterSpec? filter;
        lock (Gate)
            FiltersByDatabase.TryGetValue(document.Database, out filter);

        if (filter is not null)
            Apply(document, filter.ClassId, filter.Mode);
    }

    internal static bool Clear(Document document)
    {
        bool removed;
        lock (Gate)
        {
            removed = HiddenByDatabase.Remove(document.Database);
            FiltersByDatabase.Remove(document.Database);
            RemoveIfUnused();
        }

        document.Editor.Regen();
        return removed;
    }

    internal static void Shutdown()
    {
        lock (Gate)
        {
            HiddenByDatabase.Clear();
            FiltersByDatabase.Clear();
            RemoveIfUnused();
        }
    }

    private static PqVisibilityResult BuildHiddenSet(
        Document document,
        string classId,
        PqVisibilityMode mode,
        out HashSet<ObjectId> hidden)
    {
        hidden = new HashSet<ObjectId>();
        var matching = 0;
        var unresolved = 0;

        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var currentSpace = (BlockTableRecord)transaction.GetObject(
            document.Database.CurrentSpaceId, OpenMode.ForRead);
        var cache = new Dictionary<ObjectId, ClassSummary>();

        foreach (ObjectId id in currentSpace)
        {
            if (transaction.GetObject(id, OpenMode.ForRead, false) is not Entity entity)
                continue;

            CollectHidden(
                entity,
                classId,
                mode,
                transaction,
                cache,
                hidden,
                new HashSet<ObjectId>(),
                ref matching,
                ref unresolved);
        }

        return new PqVisibilityResult(hidden.Count, matching, unresolved);
    }

    private static bool CollectHidden(
        Entity entity,
        string classId,
        PqVisibilityMode mode,
        Transaction transaction,
        Dictionary<ObjectId, ClassSummary> cache,
        HashSet<ObjectId> hidden,
        HashSet<ObjectId> recursionStack,
        ref int matching,
        ref int unresolved)
    {
        var summary = PqClassResolver.Resolve(entity, transaction, cache);
        var isUniform = summary.State == ClassState.Uniform && summary.ClassId is not null;
        var isMatch = isUniform && string.Equals(
            summary.ClassId, classId, StringComparison.OrdinalIgnoreCase);

        if (entity is not BlockReference blockReference || isUniform)
        {
            if (isMatch)
                matching++;

            var shouldHide = mode == PqVisibilityMode.HideMatching
                ? isMatch
                : !isMatch;
            if (shouldHide)
                hidden.Add(entity.ObjectId);
            return isMatch;
        }

        // A mixed/incomplete parent must remain drawable so matching descendants
        // can still be drawn. Visibility decisions move down to its children.
        var definitionId = PqClassResolver.GetSemanticDefinitionId(blockReference);
        if (!recursionStack.Add(definitionId))
        {
            unresolved++;
            return false;
        }

        var subtreeHasMatch = false;
        try
        {
            var definition = (BlockTableRecord)transaction.GetObject(
                definitionId, OpenMode.ForRead);
            foreach (ObjectId childId in definition)
            {
                if (transaction.GetObject(childId, OpenMode.ForRead, false) is not Entity child)
                    continue;

                subtreeHasMatch |= CollectHidden(
                    child,
                    classId,
                    mode,
                    transaction,
                    cache,
                    hidden,
                    recursionStack,
                    ref matching,
                    ref unresolved);
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

        // AutoCAD may draw a BlockReference from cached block graphics without
        // invoking leaf-level overrules. When an isolate filter finds no target
        // anywhere below this block, suppress the parent reference itself.
        if (mode == PqVisibilityMode.IsolateMatching && !subtreeHasMatch)
            hidden.Add(blockReference.ObjectId);

        return subtreeHasMatch;
    }

    private static bool IsHidden(Entity entity)
    {
        lock (Gate)
        {
            return HiddenByDatabase.TryGetValue(entity.Database, out var ids) &&
                   ids.Contains(entity.ObjectId);
        }
    }

    private static void EnsureInstalled()
    {
        if (installed)
            return;

        Overrule.AddOverrule(
            RXObject.GetClass(typeof(Entity)), DrawableOverrule, false);
        Overrule.Overruling = true;
        installed = true;
    }

    private static void RemoveIfUnused()
    {
        if (!installed || HiddenByDatabase.Count > 0)
            return;

        Overrule.RemoveOverrule(
            RXObject.GetClass(typeof(Entity)), DrawableOverrule);
        // Do not turn the global Overruling switch off: other plug-ins may have
        // independent overrules installed in this AutoCAD session.
        installed = false;
    }

    private sealed record FilterSpec(string ClassId, PqVisibilityMode Mode);

    private sealed class PqDrawableOverrule : DrawableOverrule
    {
        public override bool WorldDraw(Drawable drawable, WorldDraw worldDraw)
        {
            if (drawable is Entity entity && IsHidden(entity))
                return true;

            return base.WorldDraw(drawable, worldDraw);
        }
    }
}
