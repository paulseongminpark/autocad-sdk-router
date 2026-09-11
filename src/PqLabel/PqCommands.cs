#nullable enable
using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;
using AcApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace PqLabel;

public sealed partial class PqCommands
{
    [CommandMethod("PQHELP")]
    public void Help()
    {
        var editor = ActiveEditor;
        editor.WriteMessage(
            "\nPQ Label commands:" +
            "\n  PQPALETTE      Open the dockable PQ Label window" +
            "\n  PQSETCLASS      Set CLASS_ID on selected leaf entities/block contents" +
            "\n  PQSETCLASSKIND  Set THING/STUFF kind for all records of one class" +
            "\n  PQUNSETCLASS    Remove CLASS_ID from selected leaf entities/block contents" +
            "\n  PQSETINSTANCE   Set one INSTANCE_ID on the selected objects/references" +
            "\n  PQNEWINSTANCE   Generate one UUID for the selected objects/references" +
            "\n  PQUNSETINSTANCE Remove INSTANCE_ID from selected objects/references" +
            "\n  PQSELECTCLASS   Select current-space objects of a class" +
            "\n  PQDESELECTCLASS Remove a class from the current selection" +
            "\n  PQSHOWCLASS     Isolate a class" +
            "\n  PQHIDECLASS     Hide a class" +
            "\n  PQSHOWALL       End object isolation" +
            "\n  PQSYNCCLASS     Materialize derived class on parent block references" +
            "\n  PQINFO          Show stored/derived class for one object" +
            "\n  PQINFONESTED    Inspect the picked nested entity and its container path" +
            "\n  PQAUDITCLASS    Count direct XData records for one class by entity type" +
            "\n  PQVALIDATE      Validate raw XData and semantic/instance integrity" +
            "\n  PQMIGRATERHINO  Convert legacy COMPANY_PQ XData to Rhino User Text XData" +
            "\nBlocks are classified from their leaf contents; mixed blocks are not matched.");
    }

    [CommandMethod("PQPALETTE", CommandFlags.Modal)]
    public void ShowPalette()
    {
        PqPaletteHost.Show();
    }

    [CommandMethod("PQSETCLASS", CommandFlags.Modal | CommandFlags.UsePickSet)]
    public void SetClass()
    {
        var document = ActiveDocument;
        var editor = document.Editor;
        var classId = PromptForClass(editor, "Class to set");
        if (classId is null)
            return;
        var classKind = PromptForClassKind(editor);
        if (classKind is null)
            return;

        var selection = GetSelection(editor, "\nSelect objects or blocks: ");
        if (selection is null)
            return;

        if (classKind == "STUFF")
        {
            var instanceCount = CountInstancesInSelection(document, selection);
            if (instanceCount > 0)
            {
                editor.WriteMessage(
                    $"\nClass assignment rejected: STUFF cannot have INSTANCE_ID. " +
                    $"Remove {instanceCount} instance record(s) from the selected scope first.");
                return;
            }
        }

        var overwrite = ScanExistingClassLabels(document, selection, classId);
        if (overwrite.Existing > 0 && !ConfirmClassOverwrite(editor, overwrite))
        {
            editor.WriteMessage("\nClass assignment cancelled; existing labels were not changed.");
            return;
        }

        using var transaction = document.Database.TransactionManager.StartTransaction();
        PqXData.EnsureRegistered(document.Database, transaction);

        var visitedDefinitions = new HashSet<ObjectId>();
        var stats = new MutationStats();
        foreach (SelectedObject selected in selection)
        {
            if (selected.ObjectId.IsNull)
                continue;
            ApplyClassRecursive(
                selected.ObjectId, classId, classKind, clear: false,
                transaction, visitedDefinitions, stats);
        }

        var sync = PqClassSynchronizer.Synchronize(document.Database, transaction);
        transaction.Commit();
        PqNestedVisibility.RefreshIfActive(document);
        editor.Regen();
        editor.WriteMessage(
            $"\nPQ class set on {stats.Changed} leaf object(s)." +
            FormatSkipped(stats) + FormatSync(sync));
    }

    [CommandMethod("PQSETCLASSKIND", CommandFlags.Modal)]
    public void SetClassKind()
    {
        var document = ActiveDocument;
        var editor = document.Editor;
        var classId = PromptForClass(editor, "Class whose kind will be set");
        if (classId is null)
            return;
        var classKind = PromptForClassKind(editor);
        if (classKind is null)
            return;

        try
        {
            var result = MutateAllLabels(false, classId, classKind);
            editor.Regen();
            editor.WriteMessage($"\nCLASS_KIND '{classKind}' set on {result.Changed} authored '{classId}' record(s)." + FormatSync(result.Sync));
        }
        catch (InvalidOperationException error) { editor.WriteMessage("\n" + error.Message); }
    }

    [CommandMethod("PQUNSETCLASS", CommandFlags.Modal | CommandFlags.UsePickSet)]
    public void UnsetClass()
    {
        var document = ActiveDocument;
        var editor = document.Editor;
        var selection = GetSelection(editor, "\nSelect objects or blocks: ");
        if (selection is null)
            return;

        using var transaction = document.Database.TransactionManager.StartTransaction();
        PqXData.EnsureRegistered(document.Database, transaction);

        var visitedDefinitions = new HashSet<ObjectId>();
        var stats = new MutationStats();
        foreach (SelectedObject selected in selection)
        {
            if (selected.ObjectId.IsNull)
                continue;
            ApplyClassRecursive(
                selected.ObjectId, classId: null, classKind: null, clear: true,
                transaction, visitedDefinitions, stats);
        }

        var sync = PqClassSynchronizer.Synchronize(document.Database, transaction);
        transaction.Commit();
        PqNestedVisibility.RefreshIfActive(document);
        editor.Regen();
        editor.WriteMessage(
            $"\nPQ class removed from {stats.Changed} object(s)." +
            FormatSkipped(stats) + FormatSync(sync));
    }

    [CommandMethod("PQSETINSTANCE", CommandFlags.Modal | CommandFlags.UsePickSet)]
    public void SetInstance()
    {
        var document = ActiveDocument;
        var instanceId = PromptForInstance(document.Editor, "Instance ID to set");
        if (instanceId is null)
            return;

        var selection = GetSelection(document.Editor, "\nSelect instance objects/references: ");
        if (selection is null)
            return;

        var mutation = MutateInstanceSelection(document, selection, instanceId, clear: false);
        if (mutation.StuffRejected > 0)
        {
            document.Editor.WriteMessage(
                $"\nINSTANCE_ID assignment rejected: {mutation.StuffRejected} selected " +
                "object(s) are STUFF. STUFF cannot have an instance ID.");
            return;
        }
        document.Editor.WriteMessage(
            $"\nINSTANCE_ID '{instanceId}' set on {mutation.Changed} object(s). " +
            "Block definitions were not changed.");
    }

    [CommandMethod("PQNEWINSTANCE", CommandFlags.Modal | CommandFlags.UsePickSet)]
    public void NewInstance()
    {
        var document = ActiveDocument;
        var selection = GetSelection(document.Editor, "\nSelect objects belonging to one instance: ");
        if (selection is null)
            return;

        var instanceId = Guid.NewGuid().ToString("D");
        var mutation = MutateInstanceSelection(document, selection, instanceId, clear: false);
        if (mutation.StuffRejected > 0)
        {
            document.Editor.WriteMessage(
                $"\nGenerated ID was not assigned: {mutation.StuffRejected} selected " +
                "object(s) are STUFF. STUFF cannot have an instance ID.");
            return;
        }
        document.Editor.WriteMessage(
            $"\nGenerated INSTANCE_ID '{instanceId}' on {mutation.Changed} object(s). " +
            "Block definitions were not changed.");
    }

    [CommandMethod("PQUNSETINSTANCE", CommandFlags.Modal | CommandFlags.UsePickSet)]
    public void UnsetInstance()
    {
        var document = ActiveDocument;
        var selection = GetSelection(document.Editor, "\nSelect objects/references: ");
        if (selection is null)
            return;

        var mutation = MutateInstanceSelection(document, selection, null, clear: true);
        document.Editor.WriteMessage(
            $"\nINSTANCE_ID removed from {mutation.Changed} object(s).");
    }

    [CommandMethod("PQSELECTCLASS", CommandFlags.Modal)]
    public void SelectClass()
    {
        var document = ActiveDocument;
        var classId = PromptForClass(document.Editor, "Class to select");
        if (classId is null)
            return;

        var result = FindCurrentSpaceMatches(document, classId);
        document.Editor.SetImpliedSelection(result.Ids);
        ReportQuery(document.Editor, "selected", classId, result);
    }

    [CommandMethod("PQDESELECTCLASS", CommandFlags.Modal | CommandFlags.UsePickSet)]
    public void DeselectClass()
    {
        var document = ActiveDocument;
        var editor = document.Editor;
        var classId = PromptForClass(editor, "Class to deselect");
        if (classId is null)
            return;

        var implied = editor.SelectImplied();
        if (implied.Status != PromptStatus.OK || implied.Value.Count == 0)
        {
            editor.WriteMessage("\nThere is no current selection.");
            return;
        }

        var matches = FindCurrentSpaceMatches(document, classId);
        var remove = new HashSet<ObjectId>(matches.Ids);
        var remaining = implied.Value.GetObjectIds().Where(id => !remove.Contains(id)).ToArray();
        editor.SetImpliedSelection(remaining);
        editor.WriteMessage(
            $"\nDeselected {implied.Value.Count - remaining.Length} object(s) of class '{classId}'.");
    }

    [CommandMethod("PQSHOWCLASS", CommandFlags.Modal)]
    public void ShowClass()
    {
        RunNestedVisibility(PqVisibilityMode.IsolateMatching, "Class to show", "shown");
    }

    [CommandMethod("PQHIDECLASS", CommandFlags.Modal)]
    public void HideClass()
    {
        RunNestedVisibility(PqVisibilityMode.HideMatching, "Class to hide", "hidden");
    }

    [CommandMethod("PQSHOWALL", CommandFlags.Modal)]
    public void ShowAll()
    {
        var document = ActiveDocument;
        var restoredNested = PqNestedVisibility.Clear(document);
        try
        {
            document.Editor.Command("_.UNISOLATEOBJECTS");
        }
        catch (Autodesk.AutoCAD.Runtime.Exception)
        {
            // Native isolation may not have been active; nested state is still restored.
        }
        document.Editor.WriteMessage(
            restoredNested
                ? "\nPQ nested visibility and native object isolation ended."
                : "\nNative object isolation ended.");
    }

    [CommandMethod("PQSYNCCLASS", CommandFlags.Modal)]
    public void SyncClass()
    {
        var document = ActiveDocument;
        using var transaction = document.Database.TransactionManager.StartTransaction();
        PqXData.EnsureRegistered(document.Database, transaction);
        var result = PqClassSynchronizer.Synchronize(document.Database, transaction);
        transaction.Commit();
        document.Editor.Regen();
        document.Editor.WriteMessage(
            $"\nPQ parent class cache synchronized: {result.Updated} updated, " +
            $"{result.Cleared} cleared, {result.Skipped} skipped.");
    }

    [CommandMethod("PQINFO", CommandFlags.Modal)]
    public void Info()
    {
        var document = ActiveDocument;
        var editor = document.Editor;
        var prompt = editor.GetEntity("\nSelect an object: ");
        if (prompt.Status != PromptStatus.OK)
            return;

        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var entity = (Entity)transaction.GetObject(prompt.ObjectId, OpenMode.ForRead);
        WriteEntityInfo(editor, entity, transaction, "Selected object");
    }

    [CommandMethod("PQINFONESTED", CommandFlags.Modal)]
    public void InfoNested()
    {
        var document = ActiveDocument;
        var editor = document.Editor;
        var prompt = editor.GetNestedEntity(
            new PromptNestedEntityOptions("\nPick the exact nested entity: "));
        if (prompt.Status != PromptStatus.OK)
            return;

        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var picked = (Entity)transaction.GetObject(prompt.ObjectId, OpenMode.ForRead);
        WriteEntityInfo(editor, picked, transaction, "Picked nested entity");

        var containers = prompt.GetContainers();
        for (var index = 0; index < containers.Length; index++)
        {
            if (transaction.GetObject(containers[index], OpenMode.ForRead, false) is Entity container)
                WriteEntityInfo(editor, container, transaction, $"Container[{index}]");
        }
    }

    [CommandMethod("PQAUDITCLASS", CommandFlags.Modal)]
    public void AuditClass()
    {
        var document = ActiveDocument;
        var editor = document.Editor;
        var classId = PromptForClass(editor, "Class to audit");
        if (classId is null)
            return;

        var byType = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        var direct = 0;
        var derived = 0;

        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var blockTable = (BlockTable)transaction.GetObject(
            document.Database.BlockTableId, OpenMode.ForRead);
        foreach (ObjectId recordId in blockTable)
        {
            var record = (BlockTableRecord)transaction.GetObject(recordId, OpenMode.ForRead);
            foreach (ObjectId entityId in record)
            {
                if (transaction.GetObject(entityId, OpenMode.ForRead, false) is not Entity entity ||
                    !string.Equals(PqXData.ReadClass(entity), classId, StringComparison.OrdinalIgnoreCase))
                    continue;

                var typeName = entity.GetRXClass().Name;
                byType[typeName] = byType.TryGetValue(typeName, out var count) ? count + 1 : 1;
                if (entity is BlockReference && PqXData.IsDerivedClass(entity))
                    derived++;
                else
                    direct++;
            }
        }

        editor.WriteMessage(
            $"\nPQ audit '{classId}': {direct} authored/direct, {derived} derived cache record(s).");
        foreach (var pair in byType.OrderBy(pair => pair.Key, StringComparer.OrdinalIgnoreCase))
            editor.WriteMessage($"\n  {pair.Key}: {pair.Value}");
    }

    [CommandMethod("PQVALIDATE", CommandFlags.Modal)]
    public void ValidateLabels()
    {
        var document = ActiveDocument;
        var result = PqValidation.ScanCurrentSpace(document);
        PqValidationReporter.Write(document.Editor, result);
    }

    [CommandMethod("PQMIGRATERHINO", CommandFlags.Modal)]
    public void MigrateRhinoXData()
    {
        var result = MutateAllLabels(true, null, null);
        ActiveEditor.Regen();
        ActiveEditor.WriteMessage($"\nRhino-compatible XData migration complete: {result.Changed} object(s). Existing Rhino User Text was preserved." + FormatSync(result.Sync));
    }

    private static void WriteEntityInfo(
        Editor editor,
        Entity entity,
        Transaction transaction,
        string label)
    {
        var stored = PqXData.ReadClass(entity);
        var instanceId = PqXData.ReadInstance(entity);
        var summary = PqClassResolver.Resolve(
            entity, transaction, new Dictionary<ObjectId, ClassSummary>());

        editor.WriteMessage($"\n[{label}] {entity.GetRXClass().Name}, handle {entity.Handle}");
        editor.WriteMessage($"\n  Stored CLASS_ID: {stored ?? "<none>"}");
        editor.WriteMessage($"\n  Stored CLASS_KIND: {PqXData.ReadClassKind(entity) ?? "<none>"}");
        if (entity is BlockReference && PqXData.IsDerivedClass(entity))
            editor.WriteMessage(" (derived cache)");
        editor.WriteMessage($"\n  Stored INSTANCE_ID: {instanceId ?? "<none>"}");
        editor.WriteMessage(
            summary.State == ClassState.Uniform
                ? $"\n  Effective class: {summary.ClassId}"
                : $"\n  Effective class state: {summary.State.ToString().ToUpperInvariant()}");
    }

    private static Document ActiveDocument =>
        AcApp.DocumentManager.MdiActiveDocument ??
        throw new InvalidOperationException("No active AutoCAD document.");

    private static Editor ActiveEditor => ActiveDocument.Editor;

    private static string? PromptForClass(Editor editor, string message)
    {
        var options = new PromptStringOptions($"\n{message}: ")
        {
            AllowSpaces = false
        };
        var result = editor.GetString(options);
        if (result.Status != PromptStatus.OK)
            return null;

        var value = result.StringResult.Trim();
        if (value.Length == 0)
        {
            editor.WriteMessage("\nClass cannot be empty.");
            return null;
        }

        return value;
    }

    private static string? PromptForInstance(Editor editor, string message)
    {
        var options = new PromptStringOptions($"\n{message}: ")
        {
            AllowSpaces = false
        };
        var result = editor.GetString(options);
        if (result.Status != PromptStatus.OK)
            return null;

        var value = result.StringResult.Trim();
        if (value.Length == 0)
        {
            editor.WriteMessage("\nInstance ID cannot be empty.");
            return null;
        }

        return value;
    }

    private static string? PromptForClassKind(Editor editor)
    {
        var options = new PromptKeywordOptions(
            "\nClass kind [Thing/Stuff] <Thing>: ", "Thing Stuff")
        {
            AllowNone = true
        };
        var result = editor.GetKeywords(options);
        if (result.Status == PromptStatus.None)
            return "THING";
        if (result.Status != PromptStatus.OK)
            return null;
        return result.StringResult.Equals("Stuff", StringComparison.OrdinalIgnoreCase)
            ? "STUFF"
            : "THING";
    }

    private static SelectionSet? GetSelection(Editor editor, string message)
    {
        var implied = editor.SelectImplied();
        if (implied.Status == PromptStatus.OK && implied.Value.Count > 0)
            return implied.Value;

        var result = editor.GetSelection(new PromptSelectionOptions { MessageForAdding = message });
        return result.Status == PromptStatus.OK ? result.Value : null;
    }

    private static QueryResult FindCurrentSpaceMatches(Document document, string classId)
    {
        var ids = new List<ObjectId>();
        var mixedOrIncompleteBlocks = 0;

        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var currentSpace = (BlockTableRecord)transaction.GetObject(
            document.Database.CurrentSpaceId, OpenMode.ForRead);
        var cache = new Dictionary<ObjectId, ClassSummary>();

        foreach (ObjectId id in currentSpace)
        {
            if (transaction.GetObject(id, OpenMode.ForRead, false) is not Entity entity)
                continue;

            var summary = PqClassResolver.Resolve(entity, transaction, cache);
            if (summary.State == ClassState.Uniform &&
                string.Equals(summary.ClassId, classId, StringComparison.OrdinalIgnoreCase))
            {
                ids.Add(id);
            }
            else if (entity is BlockReference && summary.State != ClassState.Uniform)
            {
                mixedOrIncompleteBlocks++;
            }
        }

        return new QueryResult(ids.ToArray(), mixedOrIncompleteBlocks);
    }

    private void RunNestedVisibility(PqVisibilityMode mode, string prompt, string verb)
    {
        var document = ActiveDocument;
        var classId = PromptForClass(document.Editor, prompt);
        if (classId is null)
            return;

        var result = PqNestedVisibility.Apply(document, classId, mode);
        document.Editor.WriteMessage(
            $"\nClass '{classId}' {verb} with nested-path visibility: " +
            $"{result.MatchingObjects} matching semantic object(s), " +
            $"{result.HiddenObjects} drawable object(s) suppressed.");
        if (result.UnresolvedPaths > 0)
            document.Editor.WriteMessage($" {result.UnresolvedPaths} path(s) unresolved.");
    }

    private static void ReportQuery(Editor editor, string verb, string classId, QueryResult result)
    {
        editor.WriteMessage($"\n{result.Ids.Length} object(s) {verb} for class '{classId}'.");
        if (result.MixedOrIncompleteBlocks > 0)
        {
            editor.WriteMessage(
                $" {result.MixedOrIncompleteBlocks} mixed/incomplete block(s) were skipped;" +
                " their nested contents cannot be safely hidden as top-level objects.");
        }
    }

    private static string FormatSkipped(MutationStats stats)
    {
        var parts = new List<string>();
        if (stats.SkippedXrefs > 0)
            parts.Add($"{stats.SkippedXrefs} xref definition(s) skipped");
        if (stats.SkippedReadOnly > 0)
            parts.Add($"{stats.SkippedReadOnly} read-only/unsupported object(s) skipped");
        return parts.Count == 0 ? string.Empty : " " + string.Join("; ", parts) + ".";
    }

    private static string FormatSync(ClassSyncResult sync)
    {
        return $" Parent cache: {sync.Updated} updated, {sync.Cleared} cleared" +
               (sync.Skipped > 0 ? $", {sync.Skipped} skipped." : ".");
    }

    private static bool ConfirmClassOverwrite(Editor editor, ExistingClassStats stats)
    {
        var options = new PromptKeywordOptions(
            $"\nWarning: {stats.Existing} existing class label(s) found" +
            $" ({stats.Different} use a different class). Overwrite? [Yes/No] <No>: ",
            "Yes No")
        {
            AllowNone = true
        };
        var result = editor.GetKeywords(options);
        return result.Status == PromptStatus.OK &&
               result.StringResult.Equals("Yes", StringComparison.OrdinalIgnoreCase);
    }

}
