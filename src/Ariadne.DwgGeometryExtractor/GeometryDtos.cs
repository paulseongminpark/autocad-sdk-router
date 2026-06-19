using Newtonsoft.Json;

namespace Ariadne.DwgGeometryExtractor;

public sealed class DwgGeometryDocument
{
    [JsonProperty("schema")]
    public string Schema { get; set; } = "ariadne.dwg_geometry_extract.v1";

    [JsonProperty("route")]
    public string Route { get; set; } = "dwg_truth_autocad";

    [JsonProperty("engine")]
    public string Engine { get; set; } = "objectarx_active_document";

    [JsonProperty("extractor")]
    public string Extractor { get; set; } = "Ariadne.DwgGeometryExtractor";

    [JsonProperty("extractor_version")]
    public string ExtractorVersion { get; set; } = "0.1.0";

    [JsonProperty("status")]
    public string Status { get; set; } = "ok";

    [JsonProperty("source")]
    public SourceInfo Source { get; set; } = new();

    [JsonProperty("summary")]
    public SummaryInfo Summary { get; set; } = new();

    [JsonProperty("entities")]
    public List<EntityRecord> Entities { get; set; } = [];

    [JsonProperty("errors")]
    public List<string> Errors { get; set; } = [];
}

public sealed class SourceInfo
{
    [JsonProperty("dwg_name")]
    public string? DwgName { get; set; }

    [JsonProperty("dwg_path")]
    public string? DwgPath { get; set; }

    [JsonProperty("database_filename")]
    public string? DatabaseFilename { get; set; }

    [JsonProperty("units")]
    public string? Units { get; set; }

    [JsonProperty("tilemode")]
    public bool TileMode { get; set; }
}

public sealed class SummaryInfo
{
    [JsonProperty("space")]
    public string Space { get; set; } = "Model";

    [JsonProperty("modelspace_count")]
    public int ModelspaceCount { get; set; }

    [JsonProperty("entities_by_type")]
    public SortedDictionary<string, int> EntitiesByType { get; set; } = new(StringComparer.Ordinal);

    [JsonProperty("supported_geometry_count")]
    public int SupportedGeometryCount { get; set; }

    [JsonProperty("unsupported_geometry_count")]
    public int UnsupportedGeometryCount { get; set; }
}

public sealed class EntityRecord
{
    [JsonProperty("handle")]
    public string Handle { get; set; } = "";

    [JsonProperty("object_id")]
    public string ObjectId { get; set; } = "";

    [JsonProperty("type")]
    public string Type { get; set; } = "";

    [JsonProperty("runtime_type")]
    public string RuntimeType { get; set; } = "";

    [JsonProperty("layer")]
    public string Layer { get; set; } = "";

    [JsonProperty("layout")]
    public string Layout { get; set; } = "Model";

    [JsonProperty("color_index")]
    public short? ColorIndex { get; set; }

    [JsonProperty("linetype")]
    public string? Linetype { get; set; }

    [JsonProperty("visible")]
    public bool? Visible { get; set; }

    [JsonProperty("bbox")]
    public BoundingBoxDto? BBox { get; set; }

    [JsonProperty("xdata")]
    public List<XDataValue> XData { get; set; } = [];

    [JsonProperty("geometry")]
    public GeometryPayload Geometry { get; set; } = new();

    [JsonProperty("extraction_error")]
    public string? ExtractionError { get; set; }
}

public sealed class BoundingBoxDto
{
    [JsonProperty("min")]
    public PointDto Min { get; set; } = new();

    [JsonProperty("max")]
    public PointDto Max { get; set; } = new();
}

public sealed class PointDto
{
    [JsonProperty("x")]
    public double X { get; set; }

    [JsonProperty("y")]
    public double Y { get; set; }

    [JsonProperty("z")]
    public double Z { get; set; }
}

public sealed class VertexDto
{
    [JsonProperty("point")]
    public PointDto Point { get; set; } = new();

    [JsonProperty("bulge")]
    public double? Bulge { get; set; }

    [JsonProperty("start_width")]
    public double? StartWidth { get; set; }

    [JsonProperty("end_width")]
    public double? EndWidth { get; set; }
}

public sealed class XDataValue
{
    [JsonProperty("type_code")]
    public int TypeCode { get; set; }

    [JsonProperty("value")]
    public string? Value { get; set; }
}

public sealed class AttributeDto
{
    [JsonProperty("tag")]
    public string? Tag { get; set; }

    [JsonProperty("text")]
    public string? Text { get; set; }

    [JsonProperty("position")]
    public PointDto? Position { get; set; }
}

public sealed class GeometryPayload
{
    [JsonProperty("kind")]
    public string Kind { get; set; } = "unsupported";

    [JsonProperty("start")]
    public PointDto? Start { get; set; }

    [JsonProperty("end")]
    public PointDto? End { get; set; }

    [JsonProperty("center")]
    public PointDto? Center { get; set; }

    [JsonProperty("radius")]
    public double? Radius { get; set; }

    [JsonProperty("start_angle")]
    public double? StartAngle { get; set; }

    [JsonProperty("end_angle")]
    public double? EndAngle { get; set; }

    [JsonProperty("closed")]
    public bool? Closed { get; set; }

    [JsonProperty("vertices")]
    public List<VertexDto>? Vertices { get; set; }

    [JsonProperty("position")]
    public PointDto? Position { get; set; }

    [JsonProperty("block_name")]
    public string? BlockName { get; set; }

    [JsonProperty("effective_name")]
    public string? EffectiveName { get; set; }

    [JsonProperty("scale")]
    public PointDto? Scale { get; set; }

    [JsonProperty("rotation")]
    public double? Rotation { get; set; }

    [JsonProperty("transform")]
    public double[]? Transform { get; set; }

    [JsonProperty("attributes")]
    public List<AttributeDto>? Attributes { get; set; }

    [JsonProperty("text")]
    public string? Text { get; set; }

    [JsonProperty("height")]
    public double? Height { get; set; }

    [JsonProperty("loop_count")]
    public int? LoopCount { get; set; }
}
