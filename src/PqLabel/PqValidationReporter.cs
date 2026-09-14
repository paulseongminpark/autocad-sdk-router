#nullable enable
using System.Linq;
using Autodesk.AutoCAD.EditorInput;

namespace PqLabel;

internal static class PqValidationReporter
{
    internal static void Write(Editor editor, PqValidationResult result)
    {
        editor.WriteMessage(
            $"\nPQ integrity validation: {result.Errors} error(s), " +
            $"{result.Warnings} warning(s)." +
            $"\n  Raw XData integrity issues: {result.XDataIntegrityIssues}" +
            $"\n  Semantic objects: {result.SemanticObjects} " +
            $"({result.ThingObjects} thing, {result.StuffObjects} stuff)" +
            $"\n  Missing thing instances: {result.MissingInstances}" +
            $"\n  Instance IDs spanning multiple classes: {result.MultiClassInstances}" +
            $"\n  Missing/inconsistent CLASS_KIND: {result.UnknownKinds}" +
            $"\n  Unresolved nested paths: {result.UnresolvedPaths}");

        foreach (var issue in result.Issues.Take(100))
        {
            editor.WriteMessage(
                $"\n  [{issue.Severity.ToString().ToUpperInvariant()}]" +
                $" [{issue.Code}] {issue.ClassId} @ {issue.Path}: {issue.Message}");
        }
        if (result.Issues.Count > 100)
            editor.WriteMessage($"\n  ... {result.Issues.Count - 100} additional issue(s) omitted.");

        var invalidTopLevel = result.Issues
            .Select(issue => issue.TopLevelId)
            .Where(id => !id.IsNull && id.IsValid)
            .Distinct()
            .ToArray();
        editor.SetImpliedSelection(invalidTopLevel);

        if (result.Errors == 0 && result.Warnings == 0 && result.UnresolvedPaths == 0)
        {
            editor.WriteMessage("\nValidation passed.");
            return;
        }

        editor.WriteMessage(
            $"\n{invalidTopLevel.Length} current-space top-level object(s) " +
            "containing issues were selected. Definition-only issues remain listed by BTR path.");
    }
}
