using System;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Sofiles {
    static class Setup {
        [STAThread] static int Main(string[] args) {
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            try {
                if (args.Length == 2 && args[0] == "--extract-payload") { Product.Extract(Payload(), Path.GetFullPath(args[1])); return 0; }
                I18n.Language = Preferences.Load().Language; Application.Run(new SetupForm()); return 0;
            } catch (Exception e) { MessageBox.Show(e.Message, "Sofiles", MessageBoxButtons.OK, MessageBoxIcon.Error); return 1; }
        }
        internal static byte[] Payload() {
            byte[] data = Product.Resource("Sofiles.Payload");
            if (Product.Sha(data) != ProductConfig.PayloadSha256) throw new System.Security.Cryptography.CryptographicException("SF-INSTALL-HASH");
            return data;
        }
    }
    sealed class SetupForm : Form {
        ComboBox languages; Label heading, description, explanation; Button install, close; CheckBox desktop, launch, automatic; ProgressBar progress;
        public SetupForm() {
            Font = new Font("Segoe UI", 10); Text = "Sofiles " + ProductConfig.Version; AutoScaleMode = AutoScaleMode.Dpi;
            ClientSize = new Size(760, 570); MinimumSize = new Size(700, 540); StartPosition = FormStartPosition.CenterScreen;
            Icon = Icon.ExtractAssociatedIcon(System.Reflection.Assembly.GetExecutingAssembly().Location);
            var flow = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(28), AutoScroll = true, FlowDirection = FlowDirection.TopDown, WrapContents = false };
            heading = new Label { AutoSize = true, Font = new Font("Segoe UI", 23, FontStyle.Bold), Margin = new Padding(0,0,0,16) }; flow.Controls.Add(heading);
            languages = new ComboBox { Width = 300, DropDownStyle = ComboBoxStyle.DropDownList, Margin = new Padding(0,0,0,14) };
            languages.Items.AddRange(new object[] { "Français", "English", "Deutsch" }); languages.SelectedIndex = Array.IndexOf(I18n.Languages, I18n.Language);
            languages.SelectedIndexChanged += delegate { I18n.Language = I18n.Languages[languages.SelectedIndex]; Translate(); }; flow.Controls.Add(languages);
            description = new Label { AutoSize = true, MaximumSize = new Size(665, 0), Margin = new Padding(0,0,0,12) }; flow.Controls.Add(description);
            flow.Controls.Add(new TextBox { ReadOnly = true, Width = 655, Text = Paths.Install, Margin = new Padding(0,0,0,12) });
            desktop = new CheckBox { AutoSize = true, Checked = true, Margin = new Padding(0,4,0,4) }; launch = new CheckBox { AutoSize = true, Checked = true, Margin = new Padding(0,4,0,4) };
            automatic = new CheckBox { AutoSize = true, Enabled = Updates.Configured, Checked = false, Margin = new Padding(0,4,0,14) }; flow.Controls.Add(desktop); flow.Controls.Add(launch); flow.Controls.Add(automatic);
            explanation = new Label { AutoSize = true, MaximumSize = new Size(665, 0), Margin = new Padding(0,0,0,16) }; flow.Controls.Add(explanation);
            progress = new ProgressBar { Width = 655, Visible = false, Style = ProgressBarStyle.Marquee }; flow.Controls.Add(progress);
            var buttons = new FlowLayoutPanel { AutoSize = true, FlowDirection = FlowDirection.LeftToRight, Margin = new Padding(0) };
            install = new Button { AutoSize = true, MinimumSize = new Size(160,38), Margin = new Padding(0,0,12,0) }; close = new Button { AutoSize = true, MinimumSize = new Size(130,38) };
            install.Click += async delegate { await Install(); }; close.Click += delegate { Close(); }; buttons.Controls.Add(install); buttons.Controls.Add(close); flow.Controls.Add(buttons);
            Controls.Add(flow); AcceptButton = install; CancelButton = close; Translate();
        }
        void Translate() {
            heading.Text = I18n.T("Installer Sofiles ", "Install Sofiles ", "Sofiles installieren ") + ProductConfig.Version;
            description.Text = I18n.T("Installation pour ton compte Windows. Le menu Démarrer contiendra Sofiles, les réglages et la désinstallation.", "Install for your Windows account. The Start menu will contain Sofiles, settings and the uninstaller.", "Installation für dein Windows-Konto. Sofiles, Einstellungen und Deinstallation werden dem Startmenü hinzugefügt.");
            desktop.Text = I18n.T("Créer un raccourci sur le bureau", "Create a desktop shortcut", "Desktop-Verknüpfung erstellen");
            launch.Text = I18n.T("Lancer Sofiles après l’installation", "Launch Sofiles after installation", "Sofiles nach der Installation starten");
            automatic.Text = I18n.T("Vérifier les mises à jour au lancement", "Check for updates on launch", "Beim Start nach Updates suchen");
            explanation.Text = I18n.T("Ferme les fenêtres Sofiles avant de continuer. La configuration essayée utilise l’Explorateur classique.\n\nPersonnalisation : Sofiane Messaoudi. Base : Clover, EJIE Technology. Les licences sont conservées. Don PayPal facultatif : 20 CHF.\n\n", "Close the Sofiles windows before continuing. The tested configuration uses classic Explorer.\n\nCustomisation: Sofiane Messaoudi. Base: Clover, EJIE Technology. Licences are preserved. Optional PayPal donation: CHF 20.\n\n", "Schließe die Sofiles-Fenster, bevor du fortfährst. Die getestete Konfiguration verwendet den klassischen Explorer.\n\nAnpassungen: Sofiane Messaoudi. Basis: Clover, EJIE Technology. Lizenzen bleiben erhalten. Freiwillige PayPal-Spende: 20 CHF.\n\n") + (Updates.Configured ? "" : I18n.T("Le canal de mise à jour n’est pas encore publié.", "The update channel has not been published yet.", "Der Updatekanal wurde noch nicht veröffentlicht."));
            install.Text = I18n.T("&Installer", "&Install", "&Installieren"); close.Text = I18n.T("&Annuler", "&Cancel", "&Abbrechen");
        }
        async Task Install() {
            if (Paths.NativeRunning()) { MessageBox.Show(I18n.T("Ferme toutes les fenêtres Sofiles avec son menu Quitter, puis réessaie.", "Close all Sofiles windows using its Quit menu, then try again.", "Schließe alle Sofiles-Fenster über das Menü Beenden und versuche es erneut."), "Sofiles"); return; }
            install.Enabled = close.Enabled = languages.Enabled = false; progress.Visible = true;
            FormClosingEventHandler preventClose = delegate(object sender, FormClosingEventArgs e) { e.Cancel = true; }; FormClosing += preventClose;
            try {
                string lang = I18n.Language; bool createDesktop = desktop.Checked, auto = automatic.Checked;
                string manager = await Task.Run(() => InstallOps.Install(Setup.Payload(), lang, createDesktop, auto));
                FormClosing -= preventClose;
                if (launch.Checked) System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(manager, "--launch") { UseShellExecute = false });
                MessageBox.Show(I18n.T("Sofiles est installé.", "Sofiles is installed.", "Sofiles wurde installiert."), "Sofiles"); Close();
            } catch (Exception e) {
                FormClosing -= preventClose;
                MessageBox.Show(I18n.T("Installation interrompue. Ferme Sofiles puis réessaie.\n\n", "Installation stopped. Close Sofiles and try again.\n\n", "Installation abgebrochen. Schließe Sofiles und versuche es erneut.\n\n") + e.Message + "\n" + ProductConfig.Email, "Sofiles", MessageBoxButtons.OK, MessageBoxIcon.Error);
                install.Enabled = close.Enabled = languages.Enabled = true; progress.Visible = false;
            }
        }
    }
}
