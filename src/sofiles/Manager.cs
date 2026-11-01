using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Sofiles {
    static class Manager {
        [STAThread] static int Main(string[] args) {
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            try {
                var preferences = Preferences.Load(); I18n.Language = preferences.Language;
                if (args.Length == 3 && args[0] == "--apply-language") {
                    Pak.Apply(Path.GetFullPath(args[1]), args[2]); return 0;
                }
                if (args.Length == 2 && args[0] == "--remove") {
                    InstallOps.Remove(Int32.Parse(args[1]));
                    MessageBox.Show(I18n.T("Sofiles a été désinstallé. Tes favoris et réglages sont conservés.", "Sofiles was uninstalled. Your favourites and settings were kept.", "Sofiles wurde deinstalliert. Favoriten und Einstellungen bleiben erhalten."), "Sofiles"); return 0;
                }
                if (args.Length == 1 && args[0] == "--uninstall") {
                    if (MessageBox.Show(I18n.T("Désinstaller Sofiles ? Les favoris et réglages seront conservés.", "Uninstall Sofiles? Favourites and settings will be kept.", "Sofiles deinstallieren? Favoriten und Einstellungen bleiben erhalten."), "Sofiles", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes) InstallOps.BeginUninstall();
                    return 0;
                }
                bool launching = args.Length == 1 && args[0] == "--launch";
                if (launching) {
                    Launch(preferences);
                    DateTime last;
                    if (!preferences.AutomaticUpdates || !Updates.Configured || (DateTime.TryParse(preferences.LastCheckUtc, null, System.Globalization.DateTimeStyles.RoundtripKind, out last) && DateTime.UtcNow - last.ToUniversalTime() < TimeSpan.FromDays(1))) return 0;
                }
                Application.Run(new SettingsForm(preferences, launching)); return 0;
            } catch (Exception error) { MessageBox.Show(Error(error), "Sofiles", MessageBoxButtons.OK, MessageBoxIcon.Error); return 1; }
        }
        internal static string Error(Exception error) {
            return I18n.T("L’action n’a pas abouti. Ferme les fenêtres Sofiles, puis réessaie. Si le problème persiste, contacte ", "The action could not be completed. Close the Sofiles windows and try again. If the problem continues, contact ", "Die Aktion konnte nicht abgeschlossen werden. Schließe die Sofiles-Fenster und versuche es erneut. Wenn das Problem weiter besteht, kontaktiere ") + ProductConfig.Email + "\n\n" + error.Message;
        }
        internal static void Launch(Preferences preferences) {
            using (var guard = OperationLock.Acquire()) {
                if (!Paths.NativeRunning()) Pak.Apply(Paths.Here, preferences.Language);
                else {
                    bool sameRuntime = false;
                    try {
                        var applied = Json.Read<RuntimeLanguage>(Path.Combine(Paths.Here,"runtime-language.json"));
                        sameRuntime = applied != null && applied.Language == preferences.Language && String.Equals(applied.Root, Paths.Here, StringComparison.OrdinalIgnoreCase);
                        foreach (var process in Process.GetProcessesByName("Sofiles")) using (process)
                            sameRuntime = sameRuntime && String.Equals(process.MainModule.FileName, Path.Combine(Paths.Here,"Sofiles.exe"), StringComparison.OrdinalIgnoreCase);
                    } catch { sameRuntime = false; }
                    if (!sameRuntime) throw new IOException("SF-LAUNCH-CLOSE: " + I18n.T("Ferme l’autre copie de Sofiles avec son menu Quitter, puis relance cette version.", "Close the other Sofiles copy using its Quit menu, then relaunch this version.", "Schließe die andere Sofiles-Kopie über das Menü Beenden und starte diese Version erneut."));
                }
                Process.Start(new ProcessStartInfo(Path.Combine(Paths.Here, "Sofiles.exe")) { WorkingDirectory = Paths.Here, UseShellExecute = false });
            }
        }
    }
    sealed class SettingsForm : Form {
        Preferences preferences; bool background; Label status; Button check; CheckBox automatic; ComboBox languages;
        public SettingsForm(Preferences value, bool backgroundCheck) {
            preferences = value; background = backgroundCheck;
            Text = "Sofiles"; Font = new Font("Segoe UI", 10); AutoScaleMode = AutoScaleMode.Dpi;
            ClientSize = new Size(760, 570); MinimumSize = new Size(680, 520); StartPosition = FormStartPosition.CenterScreen;
            Icon = Icon.ExtractAssociatedIcon(System.Reflection.Assembly.GetExecutingAssembly().Location);
            Build();
            Shown += async delegate { if (background) { Hide(); await CheckUpdates(true); Close(); } };
        }
        Label LabelText(string value) { return new Label { Text = value, AutoSize = true, MaximumSize = new Size(650, 0), Margin = new Padding(0, 4, 0, 12) }; }
        Button Action(string text, EventHandler handler) { var b = new Button { Text = text, AutoSize = true, MinimumSize = new Size(125, 34), Margin = new Padding(0, 6, 12, 6) }; b.Click += handler; return b; }
        FlowLayoutPanel Page(TabControl tabs, string name) {
            var page = new TabPage(name) { Padding = new Padding(20), AutoScroll = true };
            var flow = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown, WrapContents = false, AutoScroll = true };
            page.Controls.Add(flow); tabs.TabPages.Add(page); return flow;
        }
        void Build() {
            Controls.Clear();
            var main = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(20), ColumnCount = 1, RowCount = 3 };
            main.RowStyles.Add(new RowStyle(SizeType.AutoSize)); main.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); main.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            var heading = LabelText(I18n.T("Réglages Sofiles", "Sofiles settings", "Sofiles-Einstellungen")); heading.Font = new Font("Segoe UI", 21, FontStyle.Bold); main.Controls.Add(heading);
            var tabs = new TabControl { Dock = DockStyle.Fill }; main.Controls.Add(tabs);
            var language = Page(tabs, I18n.T("Langue", "Language", "Sprache"));
            language.Controls.Add(LabelText(I18n.T("Choisis la langue des menus et de l’aide.", "Choose the language for menus and help.", "Wähle die Sprache für Menüs und Hilfe.")));
            languages = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 300 };
            languages.Items.AddRange(new object[] { "Français", "English", "Deutsch" }); languages.SelectedIndex = Array.IndexOf(I18n.Languages, preferences.Language); language.Controls.Add(languages);
            language.Controls.Add(LabelText(I18n.T("Ferme toutes les fenêtres Sofiles, puis relance l’application pour appliquer la langue. Les noms de dossiers et les dialogues Windows suivent Windows.", "Close all Sofiles windows, then relaunch the app to apply the language. Folder names and Windows dialogs follow Windows.", "Schließe alle Sofiles-Fenster und starte die App neu, um die Sprache anzuwenden. Ordnernamen und Windows-Dialoge richten sich nach Windows.")));
            language.Controls.Add(Action(I18n.T("&Enregistrer la langue", "&Save language", "Sprache &speichern"), delegate {
                preferences.Language = I18n.Languages[languages.SelectedIndex]; preferences.Save(); I18n.Language = preferences.Language; Build();
                MessageBox.Show(I18n.T("Langue enregistrée. Ferme Sofiles puis relance-le avec le raccourci Sofiles.", "Language saved. Close Sofiles and relaunch it using the Sofiles shortcut.", "Sprache gespeichert. Schließe Sofiles und starte es über die Sofiles-Verknüpfung neu."), "Sofiles");
            }));
            var updates = Page(tabs, I18n.T("Mises à jour", "Updates", "Updates"));
            updates.Controls.Add(LabelText(I18n.T("Version installée : ", "Installed version: ", "Installierte Version: ") + ProductConfig.Version));
            status = LabelText(Updates.Configured ? I18n.T("Prêt à vérifier les mises à jour.", "Ready to check for updates.", "Bereit zur Updateprüfung.") : I18n.T("Le canal de mise à jour n’est pas encore publié. Cette copie utilise les mises à jour manuelles.", "The update channel has not been published yet. This copy uses manual updates.", "Der Updatekanal wurde noch nicht veröffentlicht. Diese Kopie wird manuell aktualisiert.")); updates.Controls.Add(status);
            automatic = new CheckBox { Text = I18n.T("Vérifier au lancement, au maximum une fois par jour", "Check on launch, at most once a day", "Beim Start prüfen, höchstens einmal täglich"), AutoSize = true, Checked = preferences.AutomaticUpdates, Enabled = Updates.Configured, Margin = new Padding(0, 8, 0, 12) };
            automatic.CheckedChanged += delegate { preferences.AutomaticUpdates = automatic.Checked; preferences.Save(); }; updates.Controls.Add(automatic);
            check = Action(I18n.T("&Vérifier maintenant", "&Check now", "Jetzt &prüfen"), async delegate { await CheckUpdates(false); }); check.Enabled = Updates.Configured; updates.Controls.Add(check);
            updates.Controls.Add(LabelText(I18n.T("Chaque téléchargement est contrôlé par signature et empreinte SHA-256. Tu choisis quand installer ; l’ancienne version est conservée.", "Downloads are checked using a signature and SHA-256 hash. You choose when to install; the previous version is kept.", "Downloads werden mit Signatur und SHA-256-Prüfsumme geprüft. Du bestimmst den Installationszeitpunkt; die vorherige Version bleibt erhalten.")));
            updates.Controls.Add(Action(I18n.T("Historique des versions", "Version history", "Versionsverlauf"), delegate { Product.Open(Path.Combine(Paths.Here,"docs",preferences.Language,"changelog.html")); }));
            var help = Page(tabs, I18n.T("Aide et crédits", "Help and credits", "Hilfe und Danksagungen"));
            help.Controls.Add(LabelText("Sofiles " + ProductConfig.Version + "\n" + ProductConfig.Email));
            help.Controls.Add(Action(I18n.T("&Ouvrir l’aide", "&Open help", "Hilfe &öffnen"), delegate { Product.Open(Product.Help(Paths.Here, preferences.Language)); }));
            help.Controls.Add(Action(I18n.T("&Contacter le support", "&Contact support", "Support &kontaktieren"), delegate { Product.Contact(); }));
            help.Controls.Add(Action(I18n.T("Don facultatif : 20 CHF", "Optional donation: CHF 20", "Freiwillige Spende: 20 CHF"), delegate { Product.Open(ProductConfig.DonationUrl); }));
            help.Controls.Add(Action(I18n.T("Crédits et licences", "Credits and licences", "Danksagungen und Lizenzen"), delegate { Product.Open(Path.Combine(Paths.Here,"docs",preferences.Language,"credits.html")); }));
            help.Controls.Add(LabelText(I18n.T("Onglets et favoris pour l’Explorateur Windows. Cette version utilise l’Explorateur classique. Les notices des composants sont incluses dans le dossier licences.", "Tabs and bookmarks for Windows File Explorer. This version uses classic Explorer. Component notices are included in the licences folder.", "Tabs und Lesezeichen für den Windows-Explorer. Diese Version verwendet den klassischen Explorer. Komponentenhinweise stehen im Lizenzordner.")));
            var footer = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight };
            footer.Controls.Add(Action(I18n.T("&Lancer Sofiles", "&Launch Sofiles", "Sofiles &starten"), delegate { try { Manager.Launch(preferences); } catch (Exception e) { MessageBox.Show(Manager.Error(e), "Sofiles"); } }));
            footer.Controls.Add(Action(I18n.T("&Fermer", "&Close", "S&chließen"), delegate { Close(); })); main.Controls.Add(footer); Controls.Add(main);
        }
        async Task CheckUpdates(bool quiet) {
            check.Enabled = false; status.Text = I18n.T("Vérification en cours…", "Checking…", "Prüfung läuft…");
            try {
                var release = await Task.Run(() => Updates.Check(preferences.Language));
                preferences.LastCheckUtc = DateTime.UtcNow.ToString("o"); preferences.Save();
                if (release == null) { status.Text = I18n.T("Sofiles est à jour.", "Sofiles is up to date.", "Sofiles ist aktuell."); return; }
                string message = I18n.T("Sofiles ", "Sofiles ", "Sofiles ") + release.Version + I18n.T(" est disponible.\n\n", " is available.\n\n", " ist verfügbar.\n\n") + release.Notes + "\n\n" + I18n.T("Télécharger le programme d’installation ? Tu devras fermer Sofiles avant de l’installer.", "Download the installer? You will need to close Sofiles before installing.", "Installationsprogramm herunterladen? Vor der Installation musst du Sofiles schließen.");
                if (MessageBox.Show(message, "Sofiles", MessageBoxButtons.YesNo, MessageBoxIcon.Information) != DialogResult.Yes) return;
                status.Text = I18n.T("Téléchargement et vérification…", "Downloading and verifying…", "Download und Prüfung…");
                string setup = await Task.Run(() => Updates.Fetch(release));
                if (MessageBox.Show(I18n.T("Téléchargement vérifié. Ouvrir le programme d’installation ?", "Download verified. Open the installer?", "Download geprüft. Installationsprogramm öffnen?"), "Sofiles", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes) Updates.StartVerified(setup, release);
                status.Text = I18n.T("Téléchargement vérifié.", "Download verified.", "Download geprüft.");
            } catch (Exception e) { status.Text = I18n.T("La vérification a échoué. Réessaie plus tard.", "The check failed. Try again later.", "Die Prüfung ist fehlgeschlagen. Versuche es später erneut."); if (!quiet) MessageBox.Show(Manager.Error(e), "Sofiles", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
            finally { check.Enabled = Updates.Configured; }
        }
    }
}
