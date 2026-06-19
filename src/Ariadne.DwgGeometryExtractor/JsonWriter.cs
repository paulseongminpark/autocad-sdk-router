using System.Text;
using Newtonsoft.Json;

namespace Ariadne.DwgGeometryExtractor;

public static class JsonWriter
{
    public static void Write(string path, object payload)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path) ?? ".");
        var settings = new JsonSerializerSettings
        {
            Formatting = Formatting.Indented,
            NullValueHandling = NullValueHandling.Ignore,
        };
        var json = JsonConvert.SerializeObject(payload, settings);
        File.WriteAllText(path, json + Environment.NewLine, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
    }
}
