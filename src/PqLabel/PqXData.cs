#nullable enable
using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.AutoCAD.DatabaseServices;

namespace PqLabel;

internal static class PqXData
{
    // Rhino's DWG importer recognizes Attribute User Text only under this
    // registered application name and with one brace group per key/value pair.
    internal const string AppName = "Rhino";
    internal const string LegacyAppName = "COMPANY_PQ";
    internal const string SchemaVersion = "1.1";
    internal const string SchemaKey = "SCHEMA";
    internal const string ClassKey = "CLASS_ID";
    internal const string ClassKindKey = "CLASS_KIND";
    internal const string ClassSourceKey = "CLASS_SOURCE";
    internal const string DerivedClassSource = "DERIVED";
    internal const string InstanceKey = "INSTANCE_ID";

    internal static void EnsureRegistered(Database database, Transaction transaction)
    {
        var table = (RegAppTable)transaction.GetObject(database.RegAppTableId, OpenMode.ForRead);
        if (table.Has(AppName))
            return;

        table.UpgradeOpen();
        using var record = new RegAppTableRecord { Name = AppName };
        table.Add(record);
        transaction.AddNewlyCreatedDBObject(record, true);
    }

    internal static string? ReadClass(Entity entity)
    {
        var values = ReadValues(entity);
        return values.TryGetValue(ClassKey, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value.Trim()
            : null;
    }

    internal static string? ReadClassKind(Entity entity)
    {
        var values = ReadValues(entity);
        if (!values.TryGetValue(ClassKindKey, out var value))
            return null;

        return NormalizeClassKind(value);
    }

    internal static bool IsDerivedClass(Entity entity)
    {
        var values = ReadValues(entity);
        return values.TryGetValue(ClassSourceKey, out var source) &&
               source.Equals(DerivedClassSource, StringComparison.OrdinalIgnoreCase);
    }

    internal static string? ReadInstance(Entity entity)
    {
        var values = ReadValues(entity);
        return values.TryGetValue(InstanceKey, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value.Trim()
            : null;
    }

    internal static bool SetClass(Entity entity, string classId, string? classKind = null)
    {
        var values = ReadValues(entity);
        var normalized = classId.Trim();

        if (values.TryGetValue(ClassKey, out var current) &&
            string.Equals(current, normalized, StringComparison.OrdinalIgnoreCase) &&
            !values.ContainsKey(ClassSourceKey) &&
            (classKind is null || string.Equals(
                values.GetValueOrDefault(ClassKindKey), NormalizeClassKind(classKind),
                StringComparison.OrdinalIgnoreCase)))
            return MigrateLegacyToRhino(entity);

        values[SchemaKey] = SchemaVersion;
        values[ClassKey] = normalized;
        if (NormalizeClassKind(classKind) is { } normalizedKind)
            values[ClassKindKey] = normalizedKind;
        values.Remove(ClassSourceKey);
        WriteValues(entity, values);
        return true;
    }

    internal static bool SetDerivedClass(Entity entity, string classId, string? classKind = null)
    {
        var values = ReadValues(entity);
        var normalized = classId.Trim();
        if (values.TryGetValue(ClassKey, out var current) &&
            string.Equals(current, normalized, StringComparison.OrdinalIgnoreCase) &&
            values.TryGetValue(ClassSourceKey, out var source) &&
            source.Equals(DerivedClassSource, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(values.GetValueOrDefault(ClassKindKey), NormalizeClassKind(classKind),
                StringComparison.OrdinalIgnoreCase))
            return MigrateLegacyToRhino(entity);

        values[SchemaKey] = SchemaVersion;
        values[ClassKey] = normalized;
        if (NormalizeClassKind(classKind) is { } normalizedKind)
            values[ClassKindKey] = normalizedKind;
        else
            values.Remove(ClassKindKey);
        values[ClassSourceKey] = DerivedClassSource;
        WriteValues(entity, values);
        return true;
    }

    internal static bool ClearClass(Entity entity)
    {
        var values = ReadValues(entity);
        var changed = values.Remove(ClassKey);
        changed |= values.Remove(ClassKindKey);
        changed |= values.Remove(ClassSourceKey);
        if (!changed)
            return false;

        // Keep this application's other fields, including INSTANCE_ID.
        // A schema-only record is harmless and makes future migration explicit.
        values[SchemaKey] = SchemaVersion;
        WriteValues(entity, values);
        return true;
    }

    internal static bool ClearDerivedClass(Entity entity)
    {
        var values = ReadValues(entity);
        if (!values.TryGetValue(ClassSourceKey, out var source) ||
            !source.Equals(DerivedClassSource, StringComparison.OrdinalIgnoreCase))
            return false;

        values.Remove(ClassKey);
        values.Remove(ClassKindKey);
        values.Remove(ClassSourceKey);
        values[SchemaKey] = SchemaVersion;
        WriteValues(entity, values);
        return true;
    }

    internal static bool SetInstance(Entity entity, string instanceId)
    {
        var values = ReadValues(entity);
        var normalized = instanceId.Trim();
        if (values.TryGetValue(InstanceKey, out var current) &&
            string.Equals(current, normalized, StringComparison.OrdinalIgnoreCase))
            return MigrateLegacyToRhino(entity);

        values[SchemaKey] = SchemaVersion;
        values[InstanceKey] = normalized;
        WriteValues(entity, values);
        return true;
    }

    internal static bool ClearInstance(Entity entity)
    {
        var values = ReadValues(entity);
        if (!values.Remove(InstanceKey))
            return false;

        values[SchemaKey] = SchemaVersion;
        WriteValues(entity, values);
        return true;
    }

    private static Dictionary<string, string> ReadValues(Entity entity)
    {
        var result = ReadRhinoValues(entity);
        var legacy = ReadLegacyValues(entity);
        foreach (var pair in legacy)
        {
            if (!result.ContainsKey(pair.Key))
                result[pair.Key] = pair.Value;
        }
        return result;
    }

    internal static bool MigrateLegacyToRhino(Entity entity)
    {
        var legacy = ReadLegacyValues(entity);
        if (legacy.Count == 0)
            return false;

        var merged = ReadRhinoValues(entity);
        foreach (var pair in legacy)
        {
            if (!merged.ContainsKey(pair.Key))
                merged[pair.Key] = pair.Value;
        }

        WriteRhinoValues(entity, merged);
        ClearLegacy(entity);
        return true;
    }

    private static Dictionary<string, string> ReadLegacyValues(Entity entity)
    {
        using var buffer = entity.GetXDataForApplication(LegacyAppName);
        return PqXDataInspector.ParseLegacy(buffer).Values;
    }

    private static Dictionary<string, string> ReadRhinoValues(Entity entity)
    {
        using var buffer = entity.GetXDataForApplication(AppName);
        return PqXDataInspector.ParseRhino(buffer).Values;
    }

    private static void WriteValues(Entity entity, IReadOnlyDictionary<string, string> values)
    {
        WriteRhinoValues(entity, OrderValues(values));
        ClearLegacy(entity);
    }

    private static void WriteRhinoValues(
        Entity entity,
        IEnumerable<KeyValuePair<string, string>> values)
    {
        var typedValues = new List<TypedValue>
        {
            new((int)DxfCode.ExtendedDataRegAppName, AppName)
        };

        foreach (var pair in values)
        {
            typedValues.Add(new TypedValue((int)DxfCode.ExtendedDataControlString, "{"));
            typedValues.Add(new TypedValue((int)DxfCode.ExtendedDataAsciiString, pair.Key));
            typedValues.Add(new TypedValue((int)DxfCode.ExtendedDataAsciiString, pair.Value));
            typedValues.Add(new TypedValue((int)DxfCode.ExtendedDataControlString, "}"));
        }

        using var buffer = new ResultBuffer(typedValues.ToArray());
        entity.XData = buffer;
    }

    private static void ClearLegacy(Entity entity)
    {
        using var existing = entity.GetXDataForApplication(LegacyAppName);
        if (existing is null)
            return;

        using var empty = new ResultBuffer(
            new TypedValue((int)DxfCode.ExtendedDataRegAppName, LegacyAppName));
        entity.XData = empty;
    }

    private static List<KeyValuePair<string, string>> OrderValues(
        IReadOnlyDictionary<string, string> values)
    {
        var ordered = new List<KeyValuePair<string, string>>();
        void AddIfPresent(string key)
        {
            if (values.TryGetValue(key, out var value))
                ordered.Add(new KeyValuePair<string, string>(key, value));
        }

        AddIfPresent(SchemaKey);
        AddIfPresent(ClassKey);
        AddIfPresent(ClassKindKey);
        AddIfPresent(ClassSourceKey);
        AddIfPresent(InstanceKey);

        foreach (var pair in values.OrderBy(pair => pair.Key, StringComparer.OrdinalIgnoreCase))
        {
            if (pair.Key.Equals(SchemaKey, StringComparison.OrdinalIgnoreCase) ||
                pair.Key.Equals(ClassKey, StringComparison.OrdinalIgnoreCase) ||
                pair.Key.Equals(ClassKindKey, StringComparison.OrdinalIgnoreCase) ||
                pair.Key.Equals(ClassSourceKey, StringComparison.OrdinalIgnoreCase) ||
                pair.Key.Equals(InstanceKey, StringComparison.OrdinalIgnoreCase))
                continue;
            ordered.Add(pair);
        }

        return ordered;
    }

    internal static string? NormalizeClassKind(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            return null;

        if (value.Equals("THING", StringComparison.OrdinalIgnoreCase))
            return "THING";
        if (value.Equals("STUFF", StringComparison.OrdinalIgnoreCase))
            return "STUFF";
        return null;
    }
}
