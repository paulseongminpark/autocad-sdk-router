#nullable enable
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Runtime;

namespace PqLabel;

public sealed class PqExtension : IExtensionApplication
{
    public void Initialize()
    {
        Application.DocumentManager.MdiActiveDocument?.Editor.WriteMessage(
            "\nPQ Label loaded. Run PQPALETTE to open the window or PQHELP for commands.");
    }

    public void Terminate()
    {
        PqNestedVisibility.Shutdown();
        PqPaletteHost.Shutdown();
    }
}
