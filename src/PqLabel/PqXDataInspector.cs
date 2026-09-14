#nullable enable
using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.AutoCAD.DatabaseServices;

namespace PqLabel;

internal sealed record PqXDataProblem(
    string Code,
    string Message,
    PqValidationSeverity Severity = PqValidationSeverity.Error);

internal sealed record PqXDataInspection(
    IReadOnlyList<PqXDataProblem> Problems,
    string? EffectiveClass);

internal sealed class PqParsedXData
{
    internal Dictionary<string, string> Values { get; } =
        new(StringComparer.OrdinalIgnoreCase);
    internal Dictionary<string, List<string>> AllValues { get; } =
        new(StringComparer.OrdinalIgnoreCase);
    internal List<PqXDataProblem> Problems { get; } = new();
    internal bool HasPairs => AllValues.Count > 0;

    internal void Add(string key, string value)
    {
        if (!AllValues.TryGetValue(key, out var values))
        {
            values = new List<string>();
            AllValues.Add(key, values);
        }
        values.Add(value);
        Values[key] = value;
    }

    internal void AddDuplicateProblems(string appName)
    {
        foreach (var pair in AllValues.Where(pair => pair.Value.Count > 1))
        {
            var distinct = pair.Value.Distinct(StringComparer.OrdinalIgnoreCase).Count();
            Problems.Add(new PqXDataProblem(
                distinct > 1 ? "XDATA_CONFLICTING_KEY" : "XDATA_DUPLICATE_KEY",
                $"{appName} XData contains {pair.Value.Count} '{pair.Key}' fields" +
                (distinct > 1 ? " with conflicting values." : ".")));
        }
    }
}

internal static class PqXDataInspector
{
    private static readonly HashSet<string> PqKeys = new(
        new[]
        {
            PqXData.SchemaKey,
            PqXData.ClassKey,
            PqXData.ClassKindKey,
            PqXData.ClassSourceKey,
            PqXData.InstanceKey
        },
        StringComparer.OrdinalIgnoreCase);

    internal static PqParsedXData ParseRhino(ResultBuffer? buffer)
    {
        var result = new PqParsedXData();
        if (buffer is null)
            return result;

        var strings = new List<string>();
        var inGroup = false;
        foreach (var item in buffer)
        {
            if (item.TypeCode == (int)DxfCode.ExtendedDataRegAppName)
                continue;

            if (item.TypeCode == (int)DxfCode.ExtendedDataControlString)
            {
                var control = item.Value as string;
                if (control == "{")
                {
                    if (inGroup)
                    {
                        result.Problems.Add(new PqXDataProblem(
                            "XDATA_NESTED_GROUP",
                            "Rhino XData contains a nested or overlapping group."));
                    }
                    strings.Clear();
                    inGroup = true;
                }
                else if (control == "}")
                {
                    if (!inGroup)
                    {
                        result.Problems.Add(new PqXDataProblem(
                            "XDATA_UNEXPECTED_CLOSE",
                            "Rhino XData contains a closing brace without an open group."));
                        continue;
                    }

                    AddRhinoGroup(strings, result);
                    strings.Clear();
                    inGroup = false;
                }
                continue;
            }

            if (!inGroup)
            {
                result.Problems.Add(new PqXDataProblem(
                    "XDATA_VALUE_OUTSIDE_GROUP",
                    "Rhino XData contains a value outside a { key, value } group."));
                continue;
            }

            if (item.TypeCode != (int)DxfCode.ExtendedDataAsciiString ||
                item.Value is not string text)
            {
                result.Problems.Add(new PqXDataProblem(
                    "XDATA_NON_STRING_VALUE",
                    "Rhino Attribute User Text groups must contain ASCII string values."));
                continue;
            }
            strings.Add(text);
        }

        if (inGroup)
        {
            result.Problems.Add(new PqXDataProblem(
                "XDATA_UNCLOSED_GROUP",
                "Rhino XData contains an unclosed group."));
        }
        result.AddDuplicateProblems(PqXData.AppName);
        return result;
    }

    internal static PqParsedXData ParseLegacy(ResultBuffer? buffer)
    {
        var result = new PqParsedXData();
        if (buffer is null)
            return result;

        var strings = buffer
            .Cast<TypedValue>()
            .Where(item => item.TypeCode == (int)DxfCode.ExtendedDataAsciiString)
            .Select(item => item.Value as string)
            .Where(value => value is not null)
            .Cast<string>()
            .ToArray();

        for (var index = 0; index + 1 < strings.Length; index += 2)
            result.Add(strings[index], strings[index + 1]);

        if (strings.Length % 2 != 0)
        {
            result.Problems.Add(new PqXDataProblem(
                "XDATA_ODD_LEGACY_VALUES",
                "Legacy COMPANY_PQ XData has a key without a paired value."));
        }
        result.AddDuplicateProblems(PqXData.LegacyAppName);
        return result;
    }

    internal static PqXDataInspection Inspect(Entity entity)
    {
        using var rhinoBuffer = entity.GetXDataForApplication(PqXData.AppName);
        using var legacyBuffer = entity.GetXDataForApplication(PqXData.LegacyAppName);
        var rhino = ParseRhino(rhinoBuffer);
        var legacy = ParseLegacy(legacyBuffer);
        var problems = new List<PqXDataProblem>();
        problems.AddRange(rhino.Problems);
        problems.AddRange(legacy.Problems);

        var hasPqData = rhino.AllValues.Keys.Any(PqKeys.Contains) ||
                        legacy.AllValues.Keys.Any(PqKeys.Contains);
        if (!hasPqData)
            return new PqXDataInspection(problems, null);

        if (legacy.HasPairs)
        {
            problems.Add(new PqXDataProblem(
                "XDATA_LEGACY_PRESENT",
                "Legacy COMPANY_PQ data remains; run PQMIGRATERHINO.",
                PqValidationSeverity.Warning));
        }

        foreach (var key in PqKeys)
        {
            if (!rhino.AllValues.TryGetValue(key, out var rhinoValues) ||
                !legacy.AllValues.TryGetValue(key, out var legacyValues))
                continue;

            if (rhinoValues.Concat(legacyValues)
                    .Distinct(StringComparer.OrdinalIgnoreCase).Count() > 1)
            {
                problems.Add(new PqXDataProblem(
                    "XDATA_RHINO_LEGACY_CONFLICT",
                    $"Rhino and COMPANY_PQ contain conflicting '{key}' values."));
            }
        }

        var effective = new Dictionary<string, string>(legacy.Values,
            StringComparer.OrdinalIgnoreCase);
        foreach (var pair in rhino.Values)
            effective[pair.Key] = pair.Value;

        ValidateFields(entity, effective, problems);
        return new PqXDataInspection(
            problems,
            GetNonBlank(effective, PqXData.ClassKey));
    }

    private static void AddRhinoGroup(
        IReadOnlyList<string> strings,
        PqParsedXData result)
    {
        if (strings.Count != 2)
        {
            result.Problems.Add(new PqXDataProblem(
                "XDATA_INVALID_GROUP_ARITY",
                $"Rhino XData group contains {strings.Count} strings; exactly key and value are required."));
            return;
        }

        if (string.IsNullOrWhiteSpace(strings[0]))
        {
            result.Problems.Add(new PqXDataProblem(
                "XDATA_EMPTY_KEY", "Rhino XData contains an empty key."));
            return;
        }
        result.Add(strings[0], strings[1]);
    }

    private static void ValidateFields(
        Entity entity,
        IReadOnlyDictionary<string, string> values,
        List<PqXDataProblem> problems)
    {
        var hasClass = values.ContainsKey(PqXData.ClassKey);
        var classId = GetNonBlank(values, PqXData.ClassKey);
        var instanceId = GetNonBlank(values, PqXData.InstanceKey);

        if (!values.TryGetValue(PqXData.SchemaKey, out var schema) ||
            string.IsNullOrWhiteSpace(schema))
        {
            problems.Add(new PqXDataProblem(
                "XDATA_MISSING_SCHEMA", "PQ XData has no non-empty SCHEMA field."));
        }
        else if (!schema.Equals(PqXData.SchemaVersion, StringComparison.OrdinalIgnoreCase))
        {
            problems.Add(new PqXDataProblem(
                "XDATA_SCHEMA_VERSION",
                $"SCHEMA is '{schema}', expected '{PqXData.SchemaVersion}'.",
                PqValidationSeverity.Warning));
        }

        if (hasClass && classId is null)
            problems.Add(new PqXDataProblem("XDATA_EMPTY_CLASS", "CLASS_ID is empty."));

        if (classId is not null && !values.ContainsKey(PqXData.ClassKindKey))
            problems.Add(new PqXDataProblem(
                "XDATA_MISSING_CLASS_KIND", "CLASS_ID exists without CLASS_KIND."));

        if (classId is not null && !IsSafeToken(classId))
            problems.Add(new PqXDataProblem(
                "XDATA_INVALID_CLASS_ID",
                "CLASS_ID contains whitespace, a control character, a quote, or a semicolon."));

        if (values.TryGetValue(PqXData.ClassKindKey, out var rawKind))
        {
            if (classId is null)
                problems.Add(new PqXDataProblem(
                    "XDATA_ORPHAN_CLASS_KIND", "CLASS_KIND exists without CLASS_ID."));
            if (PqXData.NormalizeClassKind(rawKind) is null)
                problems.Add(new PqXDataProblem(
                    "XDATA_INVALID_CLASS_KIND",
                    $"CLASS_KIND '{rawKind}' must be THING or STUFF."));
        }

        if (values.TryGetValue(PqXData.InstanceKey, out _) && instanceId is null)
            problems.Add(new PqXDataProblem("XDATA_EMPTY_INSTANCE", "INSTANCE_ID is empty."));
        if (instanceId is not null && classId is null)
            problems.Add(new PqXDataProblem(
                "XDATA_INSTANCE_WITHOUT_CLASS",
                "INSTANCE_ID exists without CLASS_ID; it cannot be exported as a labeled instance.",
                PqValidationSeverity.Warning));
        if (instanceId is not null && !IsSafeToken(instanceId))
            problems.Add(new PqXDataProblem(
                "XDATA_INVALID_INSTANCE_ID",
                "INSTANCE_ID contains whitespace, a control character, a quote, or a semicolon."));
        if (instanceId is not null &&
            PqXData.NormalizeClassKind(values.GetValueOrDefault(PqXData.ClassKindKey)) == "STUFF")
        {
            problems.Add(new PqXDataProblem(
                "XDATA_STUFF_HAS_INSTANCE",
                "STUFF must not carry an INSTANCE_ID."));
        }

        if (values.TryGetValue(PqXData.ClassSourceKey, out var source))
        {
            if (classId is null)
                problems.Add(new PqXDataProblem(
                    "XDATA_ORPHAN_CLASS_SOURCE", "CLASS_SOURCE exists without CLASS_ID."));
            if (!source.Equals(PqXData.DerivedClassSource, StringComparison.OrdinalIgnoreCase))
                problems.Add(new PqXDataProblem(
                    "XDATA_INVALID_CLASS_SOURCE",
                    $"CLASS_SOURCE '{source}' is not supported."));
            if (entity is not BlockReference)
                problems.Add(new PqXDataProblem(
                    "XDATA_DERIVED_ON_NON_BLOCK",
                    "CLASS_SOURCE=DERIVED is valid only on a BlockReference."));
        }
    }

    private static string? GetNonBlank(
        IReadOnlyDictionary<string, string> values,
        string key)
    {
        return values.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value.Trim()
            : null;
    }

    private static bool IsSafeToken(string value)
    {
        return value.Length > 0 && !value.Any(character =>
            char.IsWhiteSpace(character) ||
            char.IsControl(character) ||
            character is '\"' or ';');
    }
}
