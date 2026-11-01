using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;

namespace Sofiles {
    public sealed class SetupLedger {
        public string Product = "Sofiles";
        public int Schema = 3;
        public string Root;
        public string Version;
        public bool TestMode;
        public bool ControlFilesOwned;
        public List<string> Files = new List<string>();
    }
    public static class SetupHelper {
        static string LedgerPath(string root) { return Paths.Inside(root,"sofiles-install.json"); }
        static string Root(string value) {
            string root = Path.GetFullPath(value).TrimEnd('\\');
            if (root.Length < Path.GetPathRoot(root).Length + 3) throw new IOException("SF-SETUP-ROOT");
            Paths.Inside(root,"sofiles-install.json");
            return root;
        }
        static SetupLedger ReadLedger(string root, bool requireExisting = false) {
            string path = LedgerPath(root);
            if (requireExisting && !File.Exists(path)) throw new IOException("SF-SETUP-LEDGER-MISSING");
            var ledger = File.Exists(path) ? Json.Read<SetupLedger>(path) : new SetupLedger { Root = root };
            if (ledger == null || ledger.Product != "Sofiles" || ledger.Schema != 3 || !String.Equals(ledger.Root,root,StringComparison.OrdinalIgnoreCase) || (requireExisting && !ledger.ControlFilesOwned)) throw new IOException("SF-SETUP-LEDGER");
            foreach (string file in ledger.Files) CheckNamespace(root,file);
            return ledger;
        }
        static void CheckNamespace(string root, string file) {
            if (!file.StartsWith("versions/",StringComparison.Ordinal) || file.Contains("\\") || file.Split('/').Any(p => p == "" || p == "." || p == "..")) throw new IOException("SF-SETUP-NAMESPACE");
            Paths.Inside(Path.Combine(root,"versions"),file.Substring("versions/".Length));
        }
        static void TestRoot(string root) {
            for (var parent = new DirectoryInfo(root); parent != null; parent = parent.Parent) {
                if (File.Exists(Path.Combine(parent.FullName,"src","sofiles","Common.cs")) && File.Exists(Path.Combine(parent.FullName,"config","product.json"))) {
                    string prefix = Path.Combine(parent.FullName,"analysis","installer-tests") + Path.DirectorySeparatorChar;
                    if (root.StartsWith(prefix,StringComparison.OrdinalIgnoreCase)) return;
                }
            }
            throw new IOException("SF-SETUP-TEST-ROOT");
        }
        static void CheckProcesses(bool test) {
            if (test) return;
            if (Paths.NativeRunning() || Process.GetProcessesByName("SofilesSettings").Length != 0) throw new IOException("SF-SETUP-CLOSE");
        }
        public static void Plan(string rootValue, string manifest, string language, bool test) {
            using (var guard = OperationLock.Acquire(true)) {
                string root = Root(rootValue); if (test) TestRoot(root); CheckProcesses(test);
                if (!I18n.Languages.Contains(language)) throw new IOException("SF-SETUP-LANGUAGE");
                if (!File.Exists(LedgerPath(root)) && Directory.Exists(root) && Directory.EnumerateFileSystemEntries(root).Any()) throw new IOException("SF-SETUP-FOREIGN-ROOT");
                var ledger = ReadLedger(root);
                if (File.Exists(LedgerPath(root)) && ledger.TestMode != test) throw new IOException("SF-SETUP-MODE");
                if (!String.IsNullOrEmpty(ledger.Version) && Updates.ParseVersion(ledger.Version) > Updates.ParseVersion(ProductConfig.Version)) throw new IOException("SF-SETUP-DOWNGRADE");
                string prefix = "versions/" + ProductConfig.Version + "/";
                var files = File.ReadAllLines(manifest,Encoding.UTF8).Where(s => !String.IsNullOrWhiteSpace(s)).ToList();
                if (files.Count < 5 || files.Count > 2000 || files.Distinct(StringComparer.OrdinalIgnoreCase).Count() != files.Count) throw new IOException("SF-SETUP-MANIFEST");
                foreach (string file in files) {
                    if (!file.StartsWith(prefix,StringComparison.Ordinal)) throw new IOException("SF-SETUP-NAMESPACE");
                    CheckNamespace(root,file);
                    string path = Paths.Inside(root,file);
                    if (File.Exists(path) && !ledger.Files.Contains(file)) throw new IOException("SF-SETUP-FOREIGN-FILE");
                }
                Directory.CreateDirectory(root);
                foreach (string file in files) if (!ledger.Files.Contains(file)) ledger.Files.Add(file);
                string state = prefix + "runtime-language.json";
                if (!ledger.Files.Contains(state)) ledger.Files.Add(state);
                ledger.TestMode = test;
                ledger.ControlFilesOwned = true;
                // Journal ownership before NSIS writes any product file. A failed
                // installation can be retried and its partial files are known.
                Json.Write(LedgerPath(root),ledger);
            }
        }
        public static void Configure(string rootValue, string language, bool test) {
            using (var guard = OperationLock.Acquire(true)) {
                string root = Root(rootValue); var ledger = ReadLedger(root,true); CheckProcesses(ledger.TestMode);
                if (ledger.TestMode != test) throw new IOException("SF-SETUP-MODE");
                string runtime = Paths.Inside(root,"versions/" + ProductConfig.Version + "/Sofiles.exe");
                runtime = Path.GetDirectoryName(runtime);
                Pak.Apply(runtime,language);
                string profile = ledger.TestMode ? Paths.Inside(root,"test-user-data/settings.json") : Path.Combine(Paths.Profile,"settings.json");
                var preferences = File.Exists(profile) ? Preferences.Parse(File.ReadAllText(profile,Encoding.UTF8)) : new Preferences();
                preferences.Language = language;
                Directory.CreateDirectory(Path.GetDirectoryName(profile)); Json.Write(profile,preferences);
                ledger.Version = ProductConfig.Version; Json.Write(LedgerPath(root),ledger);
            }
        }
        public static void Uninstall(string rootValue, bool test) {
            using (var guard = OperationLock.Acquire(true)) {
                string root = Root(rootValue); var ledger = ReadLedger(root,true); CheckProcesses(ledger.TestMode);
                if (ledger.TestMode != test) throw new IOException("SF-SETUP-MODE");
                if (ledger.Files.Any(p => !p.StartsWith("versions/",StringComparison.Ordinal))) throw new IOException("SF-SETUP-NAMESPACE");
                InstallOps.DeleteOwnedFiles(root,ledger.Files);
                ledger.Files.Clear(); ledger.Version = null; Json.Write(LedgerPath(root),ledger);
            }
        }
        [STAThread] public static int Main(string[] args) {
            try {
                if (args.Length == 5 && args[0] == "--plan") Plan(args[1],args[2],args[3],args[4] == "1");
                else if (args.Length == 4 && args[0] == "--configure") Configure(args[1],args[2],args[3] == "1");
                else if (args.Length == 3 && args[0] == "--uninstall") Uninstall(args[1],args[2] == "1");
                else throw new ArgumentException("SF-SETUP-ARGUMENTS");
                return 0;
            } catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
        }
    }
}
