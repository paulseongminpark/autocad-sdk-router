using Autodesk.AutoCAD.Colors;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Ariadne.DwgGeometryExtractor;

public sealed class CadJobRunner
{
    public CadJobResult Run(Database db, string sourceName, CadJobRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Operation))
        {
            throw new InvalidOperationException("CAD job requires operation.");
        }

        var result = new CadJobResult
        {
            Operation = request.Operation,
            WriteMode = string.IsNullOrWhiteSpace(request.WriteMode) ? "read" : request.WriteMode,
        };
        result.Source["document"] = sourceName;
        result.Source["database_filename"] = db.Filename;

        switch (request.Operation)
        {
            case "inspect.database.summary":
                InspectDatabaseSummary(db, result);
                break;
            case "write.layer.create":
                CreateLayer(db, request.Args, result);
                break;
            case "write.entity.line":
                CreateLine(db, request.Args, result);
                break;
            case "write.xrecord.set":
                SetXRecord(db, request.Args, result);
                break;
            default:
                throw new NotSupportedException($"Unsupported CAD job operation: {request.Operation}");
        }

        return result;
    }

    private static void InspectDatabaseSummary(Database db, CadJobResult result)
    {
        using var tr = db.TransactionManager.StartTransaction();
        result.Result["layers"] = CountSymbolTable(tr, db.LayerTableId);
        result.Result["linetypes"] = CountSymbolTable(tr, db.LinetypeTableId);
        result.Result["blocks"] = CountSymbolTable(tr, db.BlockTableId);
        result.Result["dimstyles"] = CountSymbolTable(tr, db.DimStyleTableId);
        result.Result["textstyles"] = CountSymbolTable(tr, db.TextStyleTableId);
        result.Result["regapps"] = CountSymbolTable(tr, db.RegAppTableId);
        result.Result["layouts"] = CountDictionary(tr, db.LayoutDictionaryId);
        result.Result["named_objects"] = CountDictionary(tr, db.NamedObjectsDictionaryId);
        result.Result["tilemode"] = db.TileMode;
        result.Result["insunits"] = db.Insunits.ToString();
        result.Result["modelspace_entities"] = CountBlockEntities(tr, SymbolUtilityServices.GetBlockModelSpaceId(db));
        tr.Commit();
    }

    private static int CountSymbolTable(Transaction tr, ObjectId id)
    {
        var table = (SymbolTable)tr.GetObject(id, OpenMode.ForRead);
        return table.Cast<ObjectId>().Count();
    }

    private static int CountDictionary(Transaction tr, ObjectId id)
    {
        var dict = (DBDictionary)tr.GetObject(id, OpenMode.ForRead);
        return dict.Cast<DBDictionaryEntry>().Count();
    }

    private static int CountBlockEntities(Transaction tr, ObjectId id)
    {
        var btr = (BlockTableRecord)tr.GetObject(id, OpenMode.ForRead);
        return btr.Cast<ObjectId>().Count();
    }

    private static void CreateLayer(Database db, JObject args, CadJobResult result)
    {
        var name = RequiredString(args, "name");
        var colorIndex = OptionalShort(args, "color_index") ?? 7;
        using var tr = db.TransactionManager.StartTransaction();
        var table = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
        if (table.Has(name))
        {
            result.Result["created"] = false;
            result.Result["layer"] = name;
            tr.Commit();
            return;
        }

        table.UpgradeOpen();
        var record = new LayerTableRecord
        {
            Name = name,
            Color = Color.FromColorIndex(ColorMethod.ByAci, colorIndex),
        };
        var id = table.Add(record);
        tr.AddNewlyCreatedDBObject(record, true);
        result.Result["created"] = true;
        result.Result["layer"] = name;
        result.ChangedObjects.Add(ObjectChange("layer", name, id));
        tr.Commit();
    }

    private static void CreateLine(Database db, JObject args, CadJobResult result)
    {
        var start = RequiredPoint(args, "start");
        var end = RequiredPoint(args, "end");
        var layer = OptionalString(args, "layer");
        using var tr = db.TransactionManager.StartTransaction();
        var model = (BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db), OpenMode.ForWrite);
        var line = new Line(start, end);
        if (!string.IsNullOrWhiteSpace(layer))
        {
            EnsureLayerExists(db, tr, layer);
            line.Layer = layer;
        }

        var id = model.AppendEntity(line);
        tr.AddNewlyCreatedDBObject(line, true);
        result.Result["created"] = true;
        result.Result["handle"] = line.Handle.ToString();
        result.ChangedObjects.Add(ObjectChange("line", line.Handle.ToString(), id));
        tr.Commit();
    }

    private static void SetXRecord(Database db, JObject args, CadJobResult result)
    {
        var dictionaryName = OptionalString(args, "dictionary") ?? "ARIADNE";
        var key = RequiredString(args, "key");
        var valueToken = args["value"] ?? new JObject();
        var valueJson = valueToken.Type == JTokenType.String
            ? valueToken.Value<string>() ?? ""
            : valueToken.ToString(Formatting.None);

        using var tr = db.TransactionManager.StartTransaction();
        var nod = (DBDictionary)tr.GetObject(db.NamedObjectsDictionaryId, OpenMode.ForRead);
        DBDictionary dict;
        if (nod.Contains(dictionaryName))
        {
            dict = (DBDictionary)tr.GetObject(nod.GetAt(dictionaryName), OpenMode.ForWrite);
        }
        else
        {
            nod.UpgradeOpen();
            dict = new DBDictionary();
            nod.SetAt(dictionaryName, dict);
            tr.AddNewlyCreatedDBObject(dict, true);
        }

        Xrecord xrecord;
        var created = false;
        if (dict.Contains(key))
        {
            xrecord = (Xrecord)tr.GetObject(dict.GetAt(key), OpenMode.ForWrite);
        }
        else
        {
            xrecord = new Xrecord();
            dict.SetAt(key, xrecord);
            tr.AddNewlyCreatedDBObject(xrecord, true);
            created = true;
        }

        xrecord.Data = new ResultBuffer(new TypedValue((int)DxfCode.Text, valueJson));
        result.Result["dictionary"] = dictionaryName;
        result.Result["key"] = key;
        result.Result["created"] = created;
        result.ChangedObjects.Add(ObjectChange("xrecord", $"{dictionaryName}/{key}", xrecord.ObjectId));
        tr.Commit();
    }

    private static void EnsureLayerExists(Database db, Transaction tr, string name)
    {
        var table = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
        if (table.Has(name))
        {
            return;
        }

        table.UpgradeOpen();
        var record = new LayerTableRecord { Name = name };
        table.Add(record);
        tr.AddNewlyCreatedDBObject(record, true);
    }

    private static Dictionary<string, object?> ObjectChange(string type, string name, ObjectId id)
    {
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["type"] = type,
            ["name"] = name,
            ["object_id"] = id.ToString(),
        };
    }

    private static string RequiredString(JObject args, string name)
    {
        var value = OptionalString(args, name);
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException($"CAD job arg '{name}' is required.");
        }

        return value;
    }

    private static string? OptionalString(JObject args, string name)
    {
        return args[name]?.Value<string>();
    }

    private static short? OptionalShort(JObject args, string name)
    {
        var token = args[name];
        return token == null ? null : token.Value<short>();
    }

    private static Point3d RequiredPoint(JObject args, string name)
    {
        var token = args[name] as JObject;
        if (token == null)
        {
            throw new InvalidOperationException($"CAD job arg '{name}' must be a point object.");
        }

        return new Point3d(
            token["x"]?.Value<double>() ?? 0.0,
            token["y"]?.Value<double>() ?? 0.0,
            token["z"]?.Value<double>() ?? 0.0);
    }
}
