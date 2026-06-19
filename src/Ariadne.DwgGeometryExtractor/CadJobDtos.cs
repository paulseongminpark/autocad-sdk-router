using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Ariadne.DwgGeometryExtractor;

public sealed class CadJobRequest
{
    [JsonProperty("schema")]
    public string Schema { get; set; } = "ariadne.autocad_sdk_job.v1";

    [JsonProperty("operation")]
    public string Operation { get; set; } = "";

    [JsonProperty("write_mode")]
    public string WriteMode { get; set; } = "read";

    [JsonProperty("save")]
    public bool? Save { get; set; }

    [JsonProperty("args")]
    public JObject Args { get; set; } = new();

    public bool ShouldSaveOriginal()
    {
        if (Save.HasValue)
        {
            return Save.Value;
        }

        return string.Equals(WriteMode, "write_original", StringComparison.OrdinalIgnoreCase);
    }
}

public sealed class CadJobResult
{
    [JsonProperty("schema")]
    public string Schema { get; set; } = "ariadne.autocad_sdk_job_result.v1";

    [JsonProperty("route")]
    public string Route { get; set; } = "dwg_truth_autocad";

    [JsonProperty("engine")]
    public string Engine { get; set; } = "managed_objectarx_active_document";

    [JsonProperty("status")]
    public string Status { get; set; } = "ok";

    [JsonProperty("operation")]
    public string Operation { get; set; } = "";

    [JsonProperty("write_mode")]
    public string WriteMode { get; set; } = "read";

    [JsonProperty("source")]
    public Dictionary<string, object?> Source { get; set; } = new(StringComparer.Ordinal);

    [JsonProperty("result")]
    public Dictionary<string, object?> Result { get; set; } = new(StringComparer.Ordinal);

    [JsonProperty("changed_objects")]
    public List<Dictionary<string, object?>> ChangedObjects { get; set; } = [];

    [JsonProperty("errors")]
    public List<string> Errors { get; set; } = [];
}
