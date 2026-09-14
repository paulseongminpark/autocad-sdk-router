using System.Reflection;
using Autodesk.AutoCAD.Runtime;

[assembly: AssemblyTitle("PQ Label")]
[assembly: AssemblyDescription("Class labeling and class-based visibility/selection for AutoCAD XData")]
[assembly: AssemblyCompany("PQ")]
[assembly: AssemblyProduct("PQ Label for AutoCAD")]
[assembly: AssemblyVersion("1.9.1.0")]
[assembly: AssemblyFileVersion("1.9.1.0")]
[assembly: ExtensionApplication(typeof(PqLabel.PqExtension))]
[assembly: CommandClass(typeof(PqLabel.PqCommands))]
