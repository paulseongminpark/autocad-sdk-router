#nullable enable
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.Windows;
using AcApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace PqLabel;

internal static class PqPaletteHost
{
    private static readonly Guid PaletteId = new("9BF52CA7-B74A-4D8C-930A-D36F0F412BC5");
    private static PaletteSet? palette;
    private static PqPaletteControl? control;
    private static bool documentEventsAttached;
    private static Document? observedDocument;
    private static bool refreshQueued;
    private static readonly HashSet<string> InventoryChangingCommands = new(
        new[]
        {
            "PQSETCLASS",
            "PQSETCLASSKIND",
            "PQUNSETCLASS",
            "PQSETINSTANCE",
            "PQNEWINSTANCE",
            "PQUNSETINSTANCE",
            "PQSYNCCLASS",
            "PQMIGRATERHINO"
        },
        StringComparer.OrdinalIgnoreCase);

    internal static void Show()
    {
        if (palette is null)
        {
            control = new PqPaletteControl();
            palette = new PaletteSet("PQ Label", PaletteId)
            {
                DockEnabled = DockSides.Left | DockSides.Right,
                MinimumSize = new Size(360, 420),
                Size = new Size(440, 600),
                Style = PaletteSetStyles.ShowAutoHideButton |
                        PaletteSetStyles.ShowCloseButton |
                        PaletteSetStyles.ShowPropertiesMenu
            };
            palette.Add("Classes", control);
            AcApp.DocumentManager.DocumentActivated += OnDocumentActivated;
            documentEventsAttached = true;
        }

        ObserveDocument(AcApp.DocumentManager.MdiActiveDocument);
        palette.Visible = true;
        control!.RefreshInventory();
    }

    internal static void Shutdown()
    {
        if (documentEventsAttached)
        {
            AcApp.DocumentManager.DocumentActivated -= OnDocumentActivated;
            documentEventsAttached = false;
        }

        ObserveDocument(null);
    }

    private static void OnDocumentActivated(
        object sender,
        DocumentCollectionEventArgs eventArgs)
    {
        ObserveDocument(AcApp.DocumentManager.MdiActiveDocument);
        QueueRefresh();
    }

    private static void ObserveDocument(Document? document)
    {
        if (ReferenceEquals(observedDocument, document))
            return;

        if (observedDocument is not null)
            observedDocument.CommandEnded -= OnCommandEnded;

        observedDocument = document;
        if (observedDocument is not null)
            observedDocument.CommandEnded += OnCommandEnded;
    }

    private static void OnCommandEnded(object sender, CommandEventArgs eventArgs)
    {
        if (InventoryChangingCommands.Contains(eventArgs.GlobalCommandName))
            QueueRefresh();
    }

    private static void QueueRefresh()
    {
        if (refreshQueued || palette?.Visible != true ||
            control is null || !control.IsHandleCreated)
            return;

        refreshQueued = true;
        control.BeginInvoke((Action)(() =>
        {
            refreshQueued = false;
            if (palette?.Visible == true)
                control.RefreshInventory();
        }));
    }
}

internal sealed class PqPaletteControl : UserControl
{
    private readonly ComboBox classInput = new();
    private readonly ComboBox classKindInput = new();
    private readonly TextBox instanceInput = new();
    private readonly CheckBox autoGenerateInstanceId = new();
    private readonly ListView classList = new();
    private readonly Label status = new();

    internal PqPaletteControl()
    {
        Dock = DockStyle.Fill;
        Padding = new Padding(8);
        BackColor = SystemColors.Control;

        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 7
        };
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        var fields = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            ColumnCount = 2,
            RowCount = 4,
            Margin = new Padding(0, 0, 0, 8)
        };
        fields.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        var classLabel = new Label { Text = "CLASS_ID", AutoSize = true, Anchor = AnchorStyles.Left };
        var instanceLabel = new Label { Text = "INSTANCE_ID", AutoSize = true, Anchor = AnchorStyles.Left };
        var classKindLabel = new Label { Text = "CLASS_KIND", AutoSize = true, Anchor = AnchorStyles.Left };

        classInput.Dock = DockStyle.Fill;
        classInput.DropDownStyle = ComboBoxStyle.DropDown;
        classInput.AutoCompleteMode = AutoCompleteMode.SuggestAppend;
        classInput.AutoCompleteSource = AutoCompleteSource.ListItems;
        classKindInput.Dock = DockStyle.Fill;
        classKindInput.DropDownStyle = ComboBoxStyle.DropDownList;
        classKindInput.Items.AddRange(new object[] { "THING", "STUFF" });
        classKindInput.SelectedIndex = 0;
        instanceInput.Dock = DockStyle.Fill;
        autoGenerateInstanceId.Text = "ID 지정 시 UUID 자동 생성";
        autoGenerateInstanceId.AutoSize = true;
        autoGenerateInstanceId.Checked = true;
        autoGenerateInstanceId.Anchor = AnchorStyles.Left;
        autoGenerateInstanceId.CheckedChanged += (_, _) =>
        {
            instanceInput.Enabled = !autoGenerateInstanceId.Checked;
        };
        instanceInput.Enabled = false;

        fields.Controls.Add(classLabel, 0, 0);
        fields.Controls.Add(classInput, 1, 0);
        fields.Controls.Add(classKindLabel, 0, 1);
        fields.Controls.Add(classKindInput, 1, 1);
        fields.Controls.Add(instanceLabel, 0, 2);
        fields.Controls.Add(instanceInput, 1, 2);
        fields.Controls.Add(autoGenerateInstanceId, 1, 3);

        classList.Dock = DockStyle.Fill;
        classList.View = View.Details;
        classList.FullRowSelect = true;
        classList.HideSelection = false;
        classList.MultiSelect = false;
        classList.Columns.Add("CLASS_ID", 145);
        classList.Columns.Add("Kind", 62);
        classList.Columns.Add("Objects", 58, HorizontalAlignment.Right);
        classList.Columns.Add("Instances", 68, HorizontalAlignment.Right);
        classList.Columns.Add("Blocks", 54, HorizontalAlignment.Right);
        classList.Columns.Add("Entities", 58, HorizontalAlignment.Right);
        classList.SelectedIndexChanged += (_, _) => CopySelectedClassToInput();
        classList.DoubleClick += (_, _) => ExecuteClassCommand("PQSELECTCLASS");

        var editButtons = MakeButtonRow(
            ("Class 지정(DEF)", ExecuteClassAssignment),
            ("종류 저장", ExecuteClassKindAssignment),
            ("Class 해제", () => ExecuteCommand("PQUNSETCLASS")),
            ("Nested 정보", () => ExecuteCommand("PQINFONESTED")));

        var instanceButtons = MakeButtonRow(
            ("ID 지정", ExecuteInstanceAssignment),
            ("ID 해제", () => ExecuteCommand("PQUNSETINSTANCE")));

        var queryButtons = MakeButtonRow(
            ("선택", () => ExecuteClassCommand("PQSELECTCLASS")),
            ("선택 해제", () => ExecuteClassCommand("PQDESELECTCLASS")),
            ("동기화", () => ExecuteCommand("PQSYNCCLASS")),
            ("무결성 검증", () => ExecuteCommand("PQVALIDATE")),
            ("새로고침", RefreshInventory));

        var visibilityButtons = MakeButtonRow(
            ("표시", () => ExecuteClassCommand("PQSHOWCLASS")),
            ("숨김", () => ExecuteClassCommand("PQHIDECLASS")),
            ("전체 표시", () => ExecuteCommand("PQSHOWALL")));

        status.AutoSize = true;
        status.MaximumSize = new Size(410, 0);
        status.ForeColor = SystemColors.GrayText;
        status.Margin = new Padding(0, 8, 0, 0);

        root.Controls.Add(fields, 0, 0);
        root.Controls.Add(classList, 0, 1);
        root.Controls.Add(editButtons, 0, 2);
        root.Controls.Add(instanceButtons, 0, 3);
        root.Controls.Add(queryButtons, 0, 4);
        root.Controls.Add(visibilityButtons, 0, 5);
        root.Controls.Add(status, 0, 6);
        Controls.Add(root);
    }

    internal void RefreshInventory()
    {
        var document = AcApp.DocumentManager.MdiActiveDocument;
        if (document is null)
        {
            SetStatus("활성 DWG가 없습니다.");
            return;
        }

        try
        {
            var inventory = PqClassInventory.ScanCurrentSpace(document);

            var selectedClass = CurrentClass;
            classList.BeginUpdate();
            classList.Items.Clear();
            classInput.Items.Clear();

            foreach (var row in inventory.Rows)
            {
                var item = new ListViewItem(row.ClassId);
                item.SubItems.Add(row.ClassKind);
                item.SubItems.Add(row.Objects.ToString());
                item.SubItems.Add(row.Instances.ToString());
                item.SubItems.Add(row.BlockInstances.ToString());
                item.SubItems.Add(row.StandaloneEntities.ToString());
                classList.Items.Add(item);
                classInput.Items.Add(row.ClassId);
            }

            classList.EndUpdate();
            classInput.Text = selectedClass;
            SetStatus(
                $"현재 공간: {inventory.Rows.Count} class · " +
                $"mixed/incomplete 경로 {inventory.MixedOrIncompleteBlocks}개 · " +
                $"미해결 경로 {inventory.UnresolvedPaths}개\n" +
                "Instances = BlockRef 또는 명시적 INSTANCE_ID의 고유 개수");
        }
        catch (System.Exception exception)
        {
            classList.EndUpdate();
            SetStatus($"새로고침 실패: {exception.Message}");
        }
    }

    private string CurrentClass => classInput.Text.Trim();
    private string CurrentClassKind => classKindInput.SelectedItem?.ToString() ?? "THING";
    private string CurrentInstance => instanceInput.Text.Trim();

    private void CopySelectedClassToInput()
    {
        if (classList.SelectedItems.Count > 0)
        {
            classInput.Text = classList.SelectedItems[0].Text;
            var kind = classList.SelectedItems[0].SubItems[1].Text;
            if (kind is "THING" or "STUFF")
                classKindInput.SelectedItem = kind;
        }
    }

    private void ExecuteClassAssignment()
    {
        if (!ValidateClassInput())
            return;
        ExecuteCommand($"PQSETCLASS {CurrentClass} {CurrentClassKind}");
    }

    private void ExecuteClassKindAssignment()
    {
        if (!ValidateClassInput())
            return;
        ExecuteCommand($"PQSETCLASSKIND {CurrentClass} {CurrentClassKind}");
    }

    private void ExecuteClassCommand(string command)
    {
        if (!ValidateClassInput())
            return;

        ExecuteCommand($"{command} {CurrentClass}");
    }

    private bool ValidateClassInput()
    {
        if (IsSafeClassToken(CurrentClass))
            return true;
        SetStatus("CLASS_ID는 비어 있지 않아야 하며 공백, 따옴표, 세미콜론을 포함할 수 없습니다.");
        return false;
    }

    private void ExecuteInstanceAssignment()
    {
        if (autoGenerateInstanceId.Checked)
        {
            var generatedId = Guid.NewGuid().ToString("D");
            instanceInput.Text = generatedId;
            ExecuteCommand($"PQSETINSTANCE {generatedId}");
            return;
        }

        var instanceId = CurrentInstance;
        if (instanceId.Length == 0)
        {
            WarnInstanceInput("UUID 자동 생성을 사용하지 않을 때는 INSTANCE_ID를 입력해야 합니다.");
            return;
        }

        if (!IsSafeClassToken(instanceId))
        {
            WarnInstanceInput("INSTANCE_ID에는 공백, 따옴표, 세미콜론을 사용할 수 없습니다.");
            return;
        }

        ExecuteCommand($"PQSETINSTANCE {instanceId}");
    }

    private void WarnInstanceInput(string message)
    {
        SetStatus(message);
        MessageBox.Show(
            this,
            message,
            "PQ Label",
            MessageBoxButtons.OK,
            MessageBoxIcon.Warning);
    }

    private void ExecuteCommand(string command)
    {
        var document = AcApp.DocumentManager.MdiActiveDocument;
        if (document is null)
        {
            SetStatus("활성 DWG가 없습니다.");
            return;
        }

        document.SendStringToExecute(command + "\n", true, false, false);
        SetStatus($"{command.Split(' ')[0]} 실행됨. 완료 후 자동 새로고침됩니다.");
    }

    private static bool IsSafeClassToken(string value)
    {
        return value.Length > 0 &&
               !value.Any(character =>
                   char.IsWhiteSpace(character) ||
                   char.IsControl(character) ||
                   character is '\"' or ';');
    }

    private void SetStatus(string message) => status.Text = message;

    private static FlowLayoutPanel MakeButtonRow(
        params (string Text, Action Click)[] definitions)
    {
        var panel = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            WrapContents = true,
            Margin = new Padding(0, 6, 0, 0)
        };

        foreach (var definition in definitions)
        {
            var button = new Button
            {
                Text = definition.Text,
                AutoSize = true,
                MinimumSize = new Size(92, 30),
                Margin = new Padding(0, 0, 6, 4)
            };
            button.Click += (_, _) => definition.Click();
            panel.Controls.Add(button);
        }

        return panel;
    }
}
