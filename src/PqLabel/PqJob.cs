#nullable enable
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;

namespace PqLabel;

// Uses the same mutation/traversal helpers as the interactive commands. No prompts.
public sealed partial class PqCommands
{
    [CommandMethod("PQ_LABEL_JOB", CommandFlags.Modal)]
    public void RunLabelJob()
    {
        var output = Environment.GetEnvironmentVariable("ARIADNE_CAD_JOB_OUT")
            ?? throw new InvalidOperationException("Missing job output path.");
        var operation = "";
        var mode = Environment.GetEnvironmentVariable("ARIADNE_CAD_JOB_WRITE_MODE") ?? "read";
        var envelope = new Dictionary<string, object?> {
            ["schema"] = "ariadne.autocad_sdk_job_result.v1",
            ["engine"] = "managed_objectarx_active_document",
            ["write_mode"] = mode, ["status"] = "error"
        };
        try
        {
            using var json = JsonDocument.Parse(File.ReadAllText(
                Environment.GetEnvironmentVariable("ARIADNE_CAD_JOB_IN")
                ?? throw new InvalidOperationException("Missing job input path.")));
            var root = json.RootElement;
            operation = Required(root, "operation");
            var args = root.TryGetProperty("args", out var nested) ? nested : root;
            ValidateJobKeys(operation, args);
            var read = operation is "pq_label.inspect" or "pq_label.inventory" or "pq_label.validate";
            if (mode != (read ? "read" : "write_copy"))
                throw new InvalidOperationException("PQ jobs permit only read or staged write_copy as appropriate.");
            envelope["result"] = new { data = ExecuteLabelJob(operation, args) };
            envelope["status"] = "ok";
        }
        catch (System.Exception error)
        {
            envelope["errors"] = new[] { error.Message };
        }
        envelope["operation"] = operation;
        File.WriteAllText(output, JsonSerializer.Serialize(envelope));
    }

    private static string Required(JsonElement args, string name)
    {
        if (!args.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.String ||
            string.IsNullOrWhiteSpace(value.GetString()))
            throw new ArgumentException($"{name} must be a nonempty string.");
        var text = value.GetString()!;
        if (text.Length > 255) throw new ArgumentException($"{name} exceeds 255 characters.");
        return text;
    }

    private static void ValidateJobKeys(string operation, JsonElement args)
    {
        var keys = operation switch {
            "pq_label.inspect" => new[] { "handles" },
            "pq_label.class.set" => new[] { "handles", "class_id", "class_kind", "overwrite", "allow_shared_definitions" },
            "pq_label.class.clear" => new[] { "handles", "allow_shared_definitions" },
            "pq_label.class.set_kind" => new[] { "class_id", "class_kind" },
            "pq_label.instance.set" => new[] { "handles", "instance_id" },
            "pq_label.instance.new" or "pq_label.instance.clear" => new[] { "handles" },
            "pq_label.inventory" or "pq_label.validate" or "pq_label.sync" or "pq_label.migrate" => Array.Empty<string>(),
            _ => throw new ArgumentException("Unknown PQ operation.")
        };
        foreach (var property in args.EnumerateObject())
        {
            // The router can carry a flat payload with these transport fields.
            if (property.Name is "operation" or "input_path" or "schema" or "write_mode") continue;
            if (!keys.Contains(property.Name)) throw new ArgumentException($"Unknown argument: {property.Name}");
            if (property.Name is "overwrite" or "allow_shared_definitions" &&
                property.Value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                throw new ArgumentException($"{property.Name} must be a boolean.");
        }
    }

    private static bool Flag(JsonElement args, string name) =>
        args.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.True;

    private static ObjectId[] ResolveTargets(JsonElement args)
    {
        var db = ActiveDocument.Database;
        if (!args.TryGetProperty("handles", out var handles) || handles.ValueKind != JsonValueKind.Array ||
            handles.GetArrayLength() == 0)
            throw new ArgumentException("Nonempty handles required; use cad.query_entities to find targets.");
        using var tr = db.TransactionManager.StartOpenCloseTransaction();
        return handles.EnumerateArray().Select(value => {
            var handle = long.Parse(value.GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
            var id = db.GetObjectId(false, new Handle(handle), 0);
            if (id.IsNull || id.IsErased || tr.GetObject(id, OpenMode.ForRead) is not Entity entity)
                throw new ArgumentException("Every handle must resolve to a live entity.");
            var owner = (BlockTableRecord)tr.GetObject(entity.OwnerId, OpenMode.ForRead);
            if (owner.IsFromExternalReference || owner.IsFromOverlayReference)
                throw new ArgumentException("Xref-owned targets are read-only.");
            return id;
        }).Distinct().ToArray();
    }

    private static object ExecuteLabelJob(string operation, JsonElement args)
    {
        var doc = ActiveDocument;
        var db = doc.Database;
        if (operation == "pq_label.inventory") return PqClassInventory.ScanCurrentSpace(doc);
        if (operation == "pq_label.validate")
        {
            var scan = PqValidation.ScanCurrentSpace(doc);
            return new { scope = "physical_all_host_records_and_current_space_occurrences",
                scan.Errors, scan.Warnings, scan.SemanticObjects, scan.UnresolvedPaths,
                issues = scan.Issues.Select(i => new { i.Code, i.Path, i.ClassId, i.Message,
                    severity = i.Severity.ToString() }).ToArray() };
        }
        if (operation == "pq_label.sync")
        {
            using var tr = db.TransactionManager.StartTransaction();
            PqXData.EnsureRegistered(db, tr);
            var sync = PqClassSynchronizer.Synchronize(db, tr);
            tr.Commit();
            return sync;
        }
        if (operation is "pq_label.class.set_kind" or "pq_label.migrate")
            return MutateWholeDrawing(operation, args);
        if (operation is not ("pq_label.inspect" or "pq_label.class.set" or "pq_label.class.clear" or
            "pq_label.instance.set" or "pq_label.instance.new" or "pq_label.instance.clear"))
            throw new ArgumentException("Unknown PQ operation.");
        var ids = ResolveTargets(args);
        if (operation == "pq_label.inspect")
        {
            using var tr = db.TransactionManager.StartOpenCloseTransaction();
            var cache = new Dictionary<ObjectId, ClassSummary>();
            return ids.Select(id => {
                var entity = (Entity)tr.GetObject(id, OpenMode.ForRead);
                var summary = PqClassResolver.Resolve(entity, tr, cache);
                return new { handle = entity.Handle.ToString(), class_id = PqXData.ReadClass(entity),
                    class_kind = PqXData.ReadClassKind(entity), instance_id = PqXData.ReadInstance(entity),
                    derived = PqXData.IsDerivedClass(entity), effective_class = summary.ClassId,
                    effective_kind = summary.ClassKind, state = summary.State.ToString() };
            }).ToArray();
        }
        using var selection = SelectionSet.FromObjectIds(ids);
        if (operation.StartsWith("pq_label.instance.", StringComparison.Ordinal))
        {
            var clear = operation == "pq_label.instance.clear";
            var instance = clear ? null : operation == "pq_label.instance.new"
                ? Guid.NewGuid().ToString() : Required(args, "instance_id");
            var result = MutateInstanceSelection(doc, selection, instance, clear);
            if (result.StuffRejected > 0) throw new InvalidOperationException("STUFF cannot carry INSTANCE_ID.");
            return new { changed = result.Changed, unchanged_or_skipped = ids.Length - result.Changed,
                instance_id = instance };
        }
        // Shared definitions are a semantic consequence, never an implicit expansion by the LLM.
        using (var tr = db.TransactionManager.StartOpenCloseTransaction())
        {
            if (!Flag(args, "allow_shared_definitions") && ids.Any(id => {
                var entity = (Entity)tr.GetObject(id, OpenMode.ForRead);
                return entity is BlockReference || !((BlockTableRecord)tr.GetObject(entity.OwnerId, OpenMode.ForRead)).IsLayout;
            })) throw new InvalidOperationException("Block edits require allow_shared_definitions=true; other placements may change.");
        }
        var isClear = operation == "pq_label.class.clear";
        var classId = isClear ? null : Required(args, "class_id");
        var kind = isClear ? null : Required(args, "class_kind");
        if (!isClear && kind is not ("THING" or "STUFF")) throw new ArgumentException("Invalid class_kind.");
        if (kind == "STUFF" && CountInstancesInSelection(doc, selection) > 0)
            throw new InvalidOperationException("Remove instance records before assigning STUFF.");
        if (!isClear && !Flag(args, "overwrite") && ScanExistingClassLabels(doc, selection, classId!).Existing > 0)
            throw new InvalidOperationException("Existing labels found; explicit overwrite=true required.");
        using (var tr = db.TransactionManager.StartTransaction())
        {
            PqXData.EnsureRegistered(db, tr);
            var visited = new HashSet<ObjectId>();
            var stats = new MutationStats();
            foreach (var id in ids) ApplyClassRecursive(id, classId, kind, isClear, tr, visited, stats);
            var sync = PqClassSynchronizer.Synchronize(db, tr);
            tr.Commit();
            return new { changed = stats.Changed, skipped_xrefs = stats.SkippedXrefs,
                skipped_read_only = stats.SkippedReadOnly, shared_definitions = visited.Count, sync };
        }
    }

    private static object MutateWholeDrawing(string operation, JsonElement args)
    {
        var migrate = operation == "pq_label.migrate";
        var result = MutateAllLabels(migrate, migrate ? null : Required(args, "class_id"),
            migrate ? null : Required(args, "class_kind"));
        return new { changed = result.Changed, sync = result.Sync, scope = "all_host_block_records" };
    }
}
