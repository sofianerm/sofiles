using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using Microsoft.Win32;

namespace Sofiles {
    public sealed class InstallRecord {
        public string Product = "Sofiles";
        public int Schema = 1;
        public string Version;
        public List<string> Files = new List<string>();
        public bool DesktopShortcut;
    }
    public static class InstallOps {
        const string RegistryKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles";
        static string Menu { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Sofiles"); } }
        static string DesktopLink { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Sofiles.lnk"); } }
        public static void CheckRoot(string root) {
            if (!String.Equals(Path.GetFullPath(root).TrimEnd('\\'), Path.GetFullPath(Paths.Install).TrimEnd('\\'), StringComparison.OrdinalIgnoreCase)) throw new IOException("SF-INSTALL-ROOT");
            Paths.Inside(root, "install-record.json");
            if (Directory.Exists(root) && Directory.EnumerateFileSystemEntries(root).Any() && !File.Exists(Path.Combine(root, "install-record.json"))) throw new IOException("SF-INSTALL-FOREIGN");
        }
        static void Shortcut(string path, string target, string arguments, string icon) {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            object shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell"));
            object link = null;
            try {
                dynamic d = shell; link = d.CreateShortcut(path); dynamic s = link;
                s.TargetPath = target; s.Arguments = arguments; s.WorkingDirectory = Path.GetDirectoryName(target);
                s.IconLocation = icon; s.Description = "Sofiles"; s.Save();
            } finally { if (link != null) Marshal.FinalReleaseComObject(link); Marshal.FinalReleaseComObject(shell); }
        }
        public static void DeleteOwnedFiles(string root, IEnumerable<string> relativeFiles) {
            string fullRoot = Path.GetFullPath(root).TrimEnd('\\');
            var files = relativeFiles.Select(p => Paths.Inside(fullRoot, p)).ToArray();
            var directories = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (string file in files) {
                for (string directory = Path.GetDirectoryName(file); directory.StartsWith(fullRoot + "\\", StringComparison.OrdinalIgnoreCase); directory = Path.GetDirectoryName(directory)) directories.Add(directory);
            }
            foreach (string file in files) if (File.Exists(file)) File.Delete(file);
            foreach (string directory in directories.OrderByDescending(d => d.Length)) if (Directory.Exists(directory) && !Directory.EnumerateFileSystemEntries(directory).Any()) Directory.Delete(directory);
        }
        static byte[] Snapshot(string path) { return File.Exists(path) ? File.ReadAllBytes(path) : null; }
        static void Restore(string path, byte[] bytes) { if (bytes == null) { if (File.Exists(path)) File.Delete(path); } else { Directory.CreateDirectory(Path.GetDirectoryName(path)); Paths.Atomic(path, bytes); } }
        public static string Install(byte[] payload, string language, bool desktop, bool automatic) {
            using (var guard = OperationLock.Acquire()) return InstallLocked(payload, language, desktop, automatic);
        }
        static string InstallLocked(byte[] payload, string language, bool desktop, bool automatic) {
            string root = Paths.Install; CheckRoot(root);
            if (Paths.NativeRunning()) throw new IOException("SF-INSTALL-CLOSE");
            Directory.CreateDirectory(root);
            string recordPath = Path.Combine(root, "install-record.json");
            InstallRecord record = File.Exists(recordPath) ? Json.Read<InstallRecord>(recordPath) : new InstallRecord();
            if (record.Product != "Sofiles" || record.Schema != 1) throw new IOException("SF-INSTALL-RECORD");
            if (record.Version != null && Updates.ParseVersion(record.Version) > Updates.ParseVersion(ProductConfig.Version)) throw new IOException("SF-INSTALL-DOWNGRADE");
            string relative = "versions/" + ProductConfig.Version;
            string final = Paths.Inside(root, relative);
            if (Directory.Exists(final)) throw new IOException("SF-INSTALL-EXISTS");
            string stage = Paths.Inside(root, ".staging-" + Guid.NewGuid().ToString("N"));
            var snapshots = new Dictionary<string, byte[]>();
            foreach (string path in new[] { recordPath, Path.Combine(root,"SofilesUninstall.exe"), Path.Combine(Paths.Profile,"settings.json"), DesktopLink,
                Path.Combine(Menu,"Sofiles.lnk"), Path.Combine(Menu,"Sofiles — réglages.lnk"), Path.Combine(Menu,"Désinstaller Sofiles.lnk") }) snapshots[path] = Snapshot(path);
            var registryValues = new Dictionary<string, object>(); var registryKinds = new Dictionary<string, RegistryValueKind>(); bool hadRegistry;
            using (var key = Registry.CurrentUser.OpenSubKey(RegistryKey)) {
                hadRegistry = key != null;
                if (key != null) foreach (string name in key.GetValueNames()) { registryValues[name] = key.GetValue(name); registryKinds[name] = key.GetValueKind(name); }
            }
            string[] stagedFiles = new string[0]; bool moved = false;
            try {
                Product.Extract(payload, stage);
                // Build final URLs before moving; the source templates remain unchanged.
                Pak.Apply(stage, language, final);
                stagedFiles = Directory.GetFiles(stage,"*",SearchOption.AllDirectories).Select(p => p.Substring(stage.Length + 1)).ToArray();
                Directory.CreateDirectory(Path.GetDirectoryName(final));
                Directory.Move(stage, final); moved = true;
                string manager = Path.Combine(final, "SofilesSettings.exe");
                string uninstall = Paths.Inside(root, "SofilesUninstall.exe");
                Paths.Atomic(uninstall, File.ReadAllBytes(manager));
                foreach (string file in Directory.GetFiles(final, "*", SearchOption.AllDirectories)) {
                    string name = file.Substring(root.Length + 1).Replace('\\', '/');
                    if (!record.Files.Contains(name)) record.Files.Add(name);
                }
                if (!record.Files.Contains("SofilesUninstall.exe")) record.Files.Add("SofilesUninstall.exe");
                var preferences = Preferences.Load(); preferences.Language = language; preferences.AutomaticUpdates = automatic && Updates.Configured; preferences.Save();
                Shortcut(Path.Combine(Menu, "Sofiles.lnk"), manager, "--launch", Path.Combine(final, "assets", "sofiles.ico"));
                Shortcut(Path.Combine(Menu, "Sofiles — réglages.lnk"), manager, "", Path.Combine(final, "assets", "sofiles.ico"));
                Shortcut(Path.Combine(Menu, "Désinstaller Sofiles.lnk"), uninstall, "--uninstall", Path.Combine(final, "assets", "sofiles.ico"));
                if (desktop) Shortcut(DesktopLink, manager, "--launch", Path.Combine(final, "assets", "sofiles.ico"));
                record.DesktopShortcut = record.DesktopShortcut || desktop; record.Version = ProductConfig.Version;
                Json.Write(recordPath, record);
                using (var key = Registry.CurrentUser.CreateSubKey(RegistryKey)) {
                    key.SetValue("DisplayName", "Sofiles"); key.SetValue("DisplayVersion", ProductConfig.Version);
                    key.SetValue("Publisher", "Sofiles"); key.SetValue("InstallLocation", root);
                    key.SetValue("DisplayIcon", Path.Combine(final, "Sofiles.exe"));
                    key.SetValue("UninstallString", "\"" + uninstall + "\" --uninstall");
                    key.SetValue("HelpLink", "mailto:" + ProductConfig.Email); key.SetValue("NoModify", 1); key.SetValue("NoRepair", 1);
                }
                return manager;
            } catch (Exception original) {
                try {
                    foreach (var item in snapshots) Restore(item.Key, item.Value);
                    Registry.CurrentUser.DeleteSubKeyTree(RegistryKey, false);
                    if (hadRegistry) using (var key = Registry.CurrentUser.CreateSubKey(RegistryKey)) foreach (var item in registryValues) key.SetValue(item.Key, item.Value, registryKinds[item.Key]);
                    string owned = moved ? final : stage;
                    if (Directory.Exists(owned)) {
                        if (!moved) stagedFiles = Directory.GetFiles(owned,"*",SearchOption.AllDirectories).Select(p => p.Substring(owned.Length + 1)).ToArray();
                        DeleteOwnedFiles(owned, stagedFiles);
                        if (!Directory.EnumerateFileSystemEntries(owned).Any()) Directory.Delete(owned);
                    }
                    string versions = Path.GetDirectoryName(final);
                    if (Directory.Exists(versions) && !Directory.EnumerateFileSystemEntries(versions).Any()) Directory.Delete(versions);
                    if (Directory.Exists(root) && !Directory.EnumerateFileSystemEntries(root).Any()) Directory.Delete(root);
                } catch (Exception rollback) { throw new IOException("SF-INSTALL-ROLLBACK: " + original.Message + " / " + rollback.Message, original); }
                throw;
            }
        }
        public static void BeginUninstall() {
            CheckRoot(Paths.Install);
            string temp = Path.Combine(Path.GetTempPath(), "Sofiles-uninstall-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(temp);
            string worker = Path.Combine(temp, "SofilesUninstall.exe");
            File.Copy(System.Reflection.Assembly.GetExecutingAssembly().Location, worker);
            Process.Start(new ProcessStartInfo(worker, "--remove " + Process.GetCurrentProcess().Id) { UseShellExecute = false, WorkingDirectory = temp });
        }
        public static void Remove(int parent) {
            try { using (var process = Process.GetProcessById(parent)) { if (!process.WaitForExit(10000)) throw new IOException("SF-UNINSTALL-WAIT"); } } catch (ArgumentException) { }
            using (var guard = OperationLock.Acquire()) RemoveLocked();
        }
        static void RemoveLocked() {
            string root = Paths.Install; CheckRoot(root);
            if (Paths.NativeRunning()) throw new IOException("SF-INSTALL-CLOSE");
            var record = Json.Read<InstallRecord>(Path.Combine(root, "install-record.json"));
            if (record.Product != "Sofiles" || record.Schema != 1) throw new IOException("SF-INSTALL-RECORD");
            DeleteOwnedFiles(root, record.Files);
            string versions = Paths.Inside(root, "versions/placeholder");
            string versionRoot = Path.GetDirectoryName(versions);
            if (Directory.Exists(versionRoot) && !Directory.EnumerateFileSystemEntries(versionRoot).Any()) Directory.Delete(versionRoot);
            foreach (string name in new[] { "Sofiles.lnk", "Sofiles — réglages.lnk", "Désinstaller Sofiles.lnk" }) {
                string path = Path.Combine(Menu, name); if (File.Exists(path)) File.Delete(path);
            }
            if (Directory.Exists(Menu) && !Directory.EnumerateFileSystemEntries(Menu).Any()) Directory.Delete(Menu);
            if (record.DesktopShortcut && File.Exists(DesktopLink)) File.Delete(DesktopLink);
            Registry.CurrentUser.DeleteSubKeyTree(RegistryKey, false);
            // Keep the inventory until every operation succeeded, so a retry can resume.
            File.Delete(Path.Combine(root, "install-record.json"));
            if (Directory.EnumerateFileSystemEntries(root).Any()) {
                // Unknown user files remain; keep an empty ownership marker for a future install.
                record.Files.Clear(); record.Version = null; record.DesktopShortcut = false;
                Json.Write(Path.Combine(root,"install-record.json"), record);
            }
            if (!Directory.EnumerateFileSystemEntries(root).Any()) Directory.Delete(root);
            // Settings, favourites and the native profile under LocalAppData\Sofiles are retained.
        }
    }
}
