using Autodesk.AutoCAD.ApplicationServices.Core;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
using Newtonsoft.Json;

[assembly: CommandClass(typeof(Ariadne.DwgGeometryExtractor.Commands))]

namespace Ariadne.DwgGeometryExtractor;

public sealed class Commands : IExtensionApplication
{
    public void Initialize()
    {
    }

    public void Terminate()
    {
    }

    [CommandMethod("ARIADNE_DWG_GEOM_EXTRACT", CommandFlags.Session)]
    public void Extract()
    {
        var outPath = Environment.GetEnvironmentVariable("ARIADNE_DWG_GEOM_OUT");
        if (string.IsNullOrWhiteSpace(outPath))
        {
            outPath = Path.Combine(Environment.CurrentDirectory, "geometry_extract.json");
        }

        try
        {
            var document = Application.DocumentManager.MdiActiveDocument;
            if (document == null)
            {
                throw new InvalidOperationException("No active AutoCAD document is available.");
            }

            Database db = document.Database;
            var extractor = new GeometryExtractor();
            var payload = extractor.Extract(db, document.Name);
            payload.Engine = "objectarx_active_document";
            JsonWriter.Write(outPath, payload);
            document.Editor.WriteMessage($"\nARIADNE_DWG_GEOM_EXTRACT wrote {outPath}\n");
        }
        catch (System.Exception ex)
        {
            JsonWriter.Write(
                outPath,
                new
                {
                    schema = "ariadne.dwg_geometry_extract.v1",
                    route = "dwg_truth_autocad",
                    extractor = "Ariadne.DwgGeometryExtractor",
                    status = "error",
                    error_type = ex.GetType().FullName,
                    error = ex.Message,
                    stack = ex.ToString(),
                });
            throw;
        }
    }

    [CommandMethod("ARIADNE_DWG_DBX_EXTRACT", CommandFlags.Session)]
    public void ExtractDbx()
    {
        var inPath = Environment.GetEnvironmentVariable("ARIADNE_DWG_DBX_IN");
        var outPath = Environment.GetEnvironmentVariable("ARIADNE_DWG_GEOM_OUT");
        if (string.IsNullOrWhiteSpace(outPath))
        {
            outPath = Path.Combine(Environment.CurrentDirectory, "geometry_extract.json");
        }

        try
        {
            if (string.IsNullOrWhiteSpace(inPath) || !File.Exists(inPath))
            {
                throw new InvalidOperationException($"ARIADNE_DWG_DBX_IN not set or file missing: {inPath}");
            }

            // ObjectDBX-style side database: read the DWG WITHOUT making it the active
            // document. Same GeometryExtractor logic, host-less read path. This is the
            // 2nd-priority fallback under the active-document ObjectARX path.
            using var db = new Database(false, true);
            db.ReadDwgFile(inPath, FileShare.Read, true, null);
            db.CloseInput(true);

            var extractor = new GeometryExtractor();
            var payload = extractor.Extract(db, inPath);
            payload.Engine = "objectdbx_sidedb";
            JsonWriter.Write(outPath, payload);
        }
        catch (System.Exception ex)
        {
            JsonWriter.Write(
                outPath,
                new
                {
                    schema = "ariadne.dwg_geometry_extract.v1",
                    route = "dwg_truth_autocad",
                    engine = "objectdbx_sidedb",
                    extractor = "Ariadne.DwgGeometryExtractor",
                    status = "error",
                    error_type = ex.GetType().FullName,
                    error = ex.Message,
                    stack = ex.ToString(),
                });
            throw;
        }
    }

    [CommandMethod("ARIADNE_CAD_JOB", CommandFlags.Session)]
    public void RunCadJob()
    {
        var jobPath = Environment.GetEnvironmentVariable("ARIADNE_CAD_JOB_IN");
        var outPath = Environment.GetEnvironmentVariable("ARIADNE_CAD_JOB_OUT");
        if (string.IsNullOrWhiteSpace(outPath))
        {
            outPath = Path.Combine(Environment.CurrentDirectory, "cad_job_result.json");
        }

        try
        {
            if (string.IsNullOrWhiteSpace(jobPath) || !File.Exists(jobPath))
            {
                throw new InvalidOperationException($"ARIADNE_CAD_JOB_IN not set or file missing: {jobPath}");
            }

            var jobJson = File.ReadAllText(jobPath);
            var request = JsonConvert.DeserializeObject<CadJobRequest>(jobJson)
                ?? throw new InvalidOperationException("Failed to parse CAD job request.");
            var writeModeOverride = Environment.GetEnvironmentVariable("ARIADNE_CAD_JOB_WRITE_MODE");
            if (!string.IsNullOrWhiteSpace(writeModeOverride))
            {
                request.WriteMode = writeModeOverride;
            }

            var document = Application.DocumentManager.MdiActiveDocument;
            if (document == null)
            {
                throw new InvalidOperationException("No active AutoCAD document is available.");
            }

            CadJobResult result;
            using (document.LockDocument())
            {
                var runner = new CadJobRunner();
                result = runner.Run(document.Database, document.Name, request);
                if (request.ShouldSaveOriginal())
                {
                    result.Result["save_requested"] = true;
                }
            }

            JsonWriter.Write(outPath, result);
            document.Editor.WriteMessage($"\nARIADNE_CAD_JOB wrote {outPath}\n");
        }
        catch (System.Exception ex)
        {
            JsonWriter.Write(
                outPath,
                new
                {
                    schema = "ariadne.autocad_sdk_job_result.v1",
                    route = "dwg_truth_autocad",
                    engine = "managed_objectarx_active_document",
                    status = "error",
                    error_type = ex.GetType().FullName,
                    error = ex.Message,
                    stack = ex.ToString(),
                });
            throw;
        }
    }
}
