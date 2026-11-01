using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Security.Principal;
using System.Web.Script.Serialization;
using System.Xml;

namespace Sofiles {
    public sealed class Preferences {
        public string Language = "fr";
        public bool AutomaticUpdates = false;
        public string LastCheckUtc = "";
        public static Preferences Load() {
            string path = Path.Combine(Paths.Profile, "settings.json");
            if (!File.Exists(path)) return new Preferences();
            try { return Parse(File.ReadAllText(path, Encoding.UTF8)); }
            catch (IOException) { return new Preferences(); }
            catch (UnauthorizedAccessException) { return new Preferences(); }
        }
        public static Preferences Parse(string json) {
            try {
                var value = new JavaScriptSerializer().Deserialize<Preferences>(json);
                if (value == null) return new Preferences();
                if (!I18n.Languages.Contains(value.Language)) value.Language = "fr";
                return value;
            } catch (ArgumentException) { return new Preferences(); }
            catch (InvalidOperationException) { return new Preferences(); }
        }
        public void Save() {
            Directory.CreateDirectory(Paths.Profile);
            Json.Write(Path.Combine(Paths.Profile, "settings.json"), this);
        }
    }
    public sealed class OperationLock : IDisposable {
        Mutex mutex;
        OperationLock(Mutex value) { mutex = value; }
        public static OperationLock Acquire(bool installerHelper = false) {
            if (!installerHelper) {
                Mutex setup;
                if (Mutex.TryOpenExisting(@"Local\SofilesSetup", out setup)) { setup.Dispose(); throw new IOException("SF-OPERATION-BUSY"); }
            }
            var mutex = new Mutex(false, @"Local\Sofiles-" + WindowsIdentity.GetCurrent().User.Value);
            bool acquired;
            try { acquired = mutex.WaitOne(0); } catch (AbandonedMutexException) { acquired = true; }
            if (!acquired) { mutex.Dispose(); throw new IOException("SF-OPERATION-BUSY"); }
            return new OperationLock(mutex);
        }
        public void Dispose() { if (mutex != null) { mutex.ReleaseMutex(); mutex.Dispose(); mutex = null; } }
    }
    public static class Paths {
        public static string Profile { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Sofiles"); } }
        public static string Install { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Sofiles"); } }
        public static string Here { get { return AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar); } }
        public static string Inside(string root, string relative) {
            if (String.IsNullOrWhiteSpace(relative) || Path.IsPathRooted(relative) || relative.Contains(":"))
                throw new InvalidDataException("SF-PATH-001");
            string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string full = Path.GetFullPath(Path.Combine(fullRoot, relative));
            if (!full.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("SF-PATH-002");
            for (var parent = new DirectoryInfo(Path.GetDirectoryName(full)); parent != null; parent = parent.Parent) {
                if (parent.Exists && (parent.Attributes & FileAttributes.ReparsePoint) != 0) throw new IOException("SF-PATH-003");
            }
            if ((File.Exists(full) || Directory.Exists(full)) && (File.GetAttributes(full) & FileAttributes.ReparsePoint) != 0) throw new IOException("SF-PATH-004");
            return full;
        }
        public static bool NativeRunning() { return Process.GetProcessesByName("Sofiles").Length != 0; }
        public static void Atomic(string path, byte[] bytes) {
            string temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try {
                File.WriteAllBytes(temp, bytes);
                for (int attempt = 0; ; attempt++) {
                    try {
                        if (File.Exists(path)) File.Replace(temp, path, null); else File.Move(temp, path);
                        break;
                    } catch (IOException error) {
                        int code = error.HResult & 0xffff;
                        if (attempt >= 7 || (code != 32 && code != 33 && code != 1176)) throw new IOException("SF-WRITE: " + Path.GetFileName(path) + ": " + error.Message,error);
                        Thread.Sleep(50 * (attempt + 1));
                    }
                }
            } finally { if (File.Exists(temp)) File.Delete(temp); }
        }
    }
    public static class Json {
        public static T Read<T>(string path) { return new JavaScriptSerializer().Deserialize<T>(File.ReadAllText(path, Encoding.UTF8)); }
        public static void Write(string path, object value) { Paths.Atomic(path, new UTF8Encoding(false).GetBytes(new JavaScriptSerializer().Serialize(value))); }
    }
    public static class I18n {
        public static readonly string[] Languages = { "fr", "en", "de" };
        public static string Language = "fr";
        public static string T(string fr, string en, string de) { return Language == "de" ? de : Language == "en" ? en : fr; }
    }
    public static class Product {
        public static string Help(string root, string language) { return Path.Combine(root, "docs", language, "help.html"); }
        public static void Open(string target) { Process.Start(new ProcessStartInfo(target) { UseShellExecute = true }); }
        public static void Contact() { Open("mailto:" + ProductConfig.Email + "?subject=Sofiles%20" + ProductConfig.Version); }
        public static string Sha(byte[] bytes) { using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant(); }
        public static byte[] Resource(string name) {
            using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name)) {
                if (stream == null) throw new InvalidDataException("SF-RESOURCE-001: " + name);
                using (var output = new MemoryStream()) { stream.CopyTo(output); return output.ToArray(); }
            }
        }
        public static void Extract(byte[] zip, string target) {
            if (Directory.Exists(target) && Directory.EnumerateFileSystemEntries(target).Any()) throw new IOException("SF-ZIP-001");
            Directory.CreateDirectory(target);
            using (var input = new MemoryStream(zip)) using (var archive = new ZipArchive(input, ZipArchiveMode.Read)) {
                if (archive.Entries.Count > 2000) throw new InvalidDataException("SF-ZIP-002");
                long total = 0; var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (var entry in archive.Entries) {
                    if (entry.FullName.EndsWith("/")) continue;
                    string file = Paths.Inside(target, entry.FullName.Replace('/', Path.DirectorySeparatorChar));
                    total = checked(total + entry.Length);
                    if (entry.Length > 100 * 1024 * 1024 || total > 256 * 1024 * 1024 || !paths.Add(file)) throw new InvalidDataException("SF-ZIP-003");
                    Directory.CreateDirectory(Path.GetDirectoryName(file));
                    using (var source = entry.Open()) using (var dest = new FileStream(file, FileMode.CreateNew, FileAccess.Write, FileShare.None)) {
                        byte[] buffer = new byte[81920]; int count; long copied = 0;
                        while ((count = source.Read(buffer, 0, buffer.Length)) > 0) {
                            copied += count;
                            if (copied > entry.Length) throw new InvalidDataException("SF-ZIP-004");
                            dest.Write(buffer, 0, count);
                        }
                        if (copied != entry.Length) throw new InvalidDataException("SF-ZIP-005");
                    }
                }
            }
        }
    }
    public static class Pak {
        public static SortedDictionary<ushort, byte[]> Read(byte[] input) {
            using (var reader = new BinaryReader(new MemoryStream(input))) {
                if (input.Length < 15 || reader.ReadUInt32() != 4) throw new InvalidDataException("SF-PAK-001");
                uint count = reader.ReadUInt32();
                if (reader.ReadByte() != 1 || count > 4096 || 9L + 6L * (count + 1) > input.Length) throw new InvalidDataException("SF-PAK-002");
                var ids = new ushort[count + 1]; var offsets = new uint[count + 1];
                for (int i = 0; i <= count; i++) { ids[i] = reader.ReadUInt16(); offsets[i] = reader.ReadUInt32(); }
                if (offsets[0] < 9 + 6 * (count + 1) || offsets[count] != input.Length || ids[count] != 0) throw new InvalidDataException("SF-PAK-003");
                var result = new SortedDictionary<ushort, byte[]>();
                for (int i = 0; i < count; i++) {
                    if (offsets[i] > offsets[i + 1] || offsets[i + 1] > input.Length || (i > 0 && ids[i - 1] >= ids[i])) throw new InvalidDataException("SF-PAK-004");
                    byte[] bytes = new byte[offsets[i + 1] - offsets[i]]; Array.Copy(input, offsets[i], bytes, 0, bytes.Length); result.Add(ids[i], bytes);
                }
                return result;
            }
        }
        public static byte[] Write(SortedDictionary<ushort, byte[]> entries) {
            using (var stream = new MemoryStream()) using (var writer = new BinaryWriter(stream)) {
                writer.Write((uint)4); writer.Write((uint)entries.Count); writer.Write((byte)1);
                uint offset = (uint)(9 + (entries.Count + 1) * 6);
                foreach (var entry in entries) { writer.Write(entry.Key); writer.Write(offset); offset = checked(offset + (uint)entry.Value.Length); }
                writer.Write((ushort)0); writer.Write(offset);
                foreach (var entry in entries) writer.Write(entry.Value);
                return stream.ToArray();
            }
        }
        public static void Apply(string root, string language, string linksRoot = null) {
            if (!I18n.Languages.Contains(language)) throw new ArgumentException("SF-LANG-001");
            var selected = Read(File.ReadAllBytes(Path.Combine(root, "language-packs", language + ".pak")));
            linksRoot = linksRoot ?? root;
            var urls = new Dictionary<string, string> {
                { "SOFILES_HOME_URI", new Uri(Path.Combine(linksRoot, "docs", language, "credits.html")).AbsoluteUri },
                { "SOFILES_HELP_URI", new Uri(Product.Help(linksRoot, language)).AbsoluteUri },
                { "SOFILES_DONATE_URI", new Uri(Path.Combine(linksRoot, "docs", language, "support.html")).AbsoluteUri },
                { "SOFILES_RELEASES_URI", String.IsNullOrEmpty(ProductConfig.ReleasesUrl) ? new Uri(Path.Combine(linksRoot,"docs",language,"changelog.html")).AbsoluteUri : ProductConfig.ReleasesUrl }
            };
            var pending = new Dictionary<string, byte[]>();
            foreach (string template in Directory.GetFiles(Path.Combine(root, "locale-templates"), "*.pak")) {
                var entries = Read(File.ReadAllBytes(template));
                foreach (var pair in selected) if (pair.Key >= 9500) {
                    string text = Encoding.UTF8.GetString(pair.Value);
                    foreach (var url in urls) text = text.Replace(url.Key, url.Value);
                    entries[pair.Key] = Encoding.UTF8.GetBytes(text);
                }
                pending.Add(Path.Combine(root, "locales", Path.GetFileName(template)), Write(entries));
            }
            if (pending.Count == 0) throw new InvalidDataException("SF-LANG-002");
            Directory.CreateDirectory(Path.Combine(root, "locales"));
            foreach (var item in pending) Paths.Atomic(item.Key, item.Value);
            Json.Write(Path.Combine(root, "runtime-language.json"), new RuntimeLanguage { Language = language, Root = linksRoot });
        }
    }
    public sealed class RuntimeLanguage { public string Language; public string Root; }
    public sealed class ReleaseInfo {
        public Version Version; public string Url; public string Sha256; public long Size; public string Notes;
    }
    public static class Updates {
        public static bool Configured { get { return !String.IsNullOrEmpty(ProductConfig.ManifestUrl) && !String.IsNullOrEmpty(ProductConfig.PublicKey); } }
        public static Version ParseVersion(string value) {
            if (!Regex.IsMatch(value ?? "", @"^(0|[1-9]\d{0,4})\.(0|[1-9]\d{0,4})\.(0|[1-9]\d{0,4})$")) throw new InvalidDataException("SF-UPDATE-001");
            return new Version(value);
        }
        public static ReleaseInfo Verify(byte[] bytes, byte[] signature, string key, Version current, string language) {
            if (bytes.Length > 131072 || signature.Length > 1024 || String.IsNullOrEmpty(key)) throw new InvalidDataException("SF-UPDATE-002");
            using (var rsa = new RSACryptoServiceProvider()) {
                rsa.PersistKeyInCsp = false; rsa.FromXmlString(key);
                if (rsa.KeySize < 3072 || !rsa.VerifyData(bytes, CryptoConfig.MapNameToOID("SHA256"), signature)) throw new CryptographicException("SF-UPDATE-003");
            }
            var document = new XmlDocument { XmlResolver = null };
            using (var reader = XmlReader.Create(new MemoryStream(bytes), new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null, MaxCharactersInDocument = 131072 })) document.Load(reader);
            var root = document.DocumentElement;
            if (root == null || root.Name != "SofilesRelease" || root.GetAttribute("schema") != "1" || root.GetAttribute("product") != "Sofiles" || root.GetAttribute("channel") != "stable") throw new InvalidDataException("SF-UPDATE-004");
            Version version = ParseVersion(root.GetAttribute("version"));
            if (version <= current) return null;
            string url = root.GetAttribute("url"); EnsureHttps(url);
            string hash = root.GetAttribute("sha256"); long size;
            if (!Regex.IsMatch(hash, "^[0-9a-f]{64}$") || !Int64.TryParse(root.GetAttribute("size"), NumberStyles.None, CultureInfo.InvariantCulture, out size) || size < 1 || size > 200L * 1024 * 1024) throw new InvalidDataException("SF-UPDATE-005");
            var notes = root.SelectSingleNode("Notes[@lang='" + (I18n.Languages.Contains(language) ? language : "fr") + "']");
            return new ReleaseInfo { Version = version, Url = url, Sha256 = hash, Size = size, Notes = notes == null ? "" : notes.InnerText };
        }
        public static void EnsureHttps(string value) {
            Uri uri;
            if (!Uri.TryCreate(value, UriKind.Absolute, out uri) || uri.Scheme != "https" || !String.IsNullOrEmpty(uri.UserInfo) || !String.IsNullOrEmpty(uri.Fragment)) throw new InvalidDataException("SF-UPDATE-006");
        }
        public static byte[] Download(string url, int limit) {
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            for (int redirects = 0; redirects <= 5; redirects++) {
                EnsureHttps(url);
                var request = (HttpWebRequest)WebRequest.Create(url);
                request.AllowAutoRedirect = false; request.Timeout = 15000; request.ReadWriteTimeout = 15000;
                request.UserAgent = "Sofiles/" + ProductConfig.Version; request.UseDefaultCredentials = false;
                using (var response = (HttpWebResponse)request.GetResponse()) {
                    int status = (int)response.StatusCode;
                    if (status >= 300 && status <= 399) {
                        string location = response.Headers["Location"];
                        if (String.IsNullOrEmpty(location)) throw new InvalidDataException("SF-UPDATE-007");
                        url = new Uri(new Uri(url), location).AbsoluteUri; continue;
                    }
                    if (status != 200 || response.ContentLength > limit) throw new InvalidDataException("SF-UPDATE-008");
                    using (var input = response.GetResponseStream()) using (var output = new MemoryStream()) {
                        byte[] buffer = new byte[81920]; int count;
                        while ((count = input.Read(buffer, 0, buffer.Length)) > 0) {
                            if (output.Length + count > limit) throw new InvalidDataException("SF-UPDATE-009");
                            output.Write(buffer, 0, count);
                        }
                        return output.ToArray();
                    }
                }
            }
            throw new InvalidDataException("SF-UPDATE-010");
        }
        public static ReleaseInfo Check(string language) {
            if (!Configured) throw new InvalidOperationException("SF-UPDATE-CHANNEL");
            byte[] manifest = Download(ProductConfig.ManifestUrl, 131072);
            byte[] signature = Convert.FromBase64String(Encoding.ASCII.GetString(Download(ProductConfig.ManifestUrl + ".sig", 4096)).Trim());
            return Verify(manifest, signature, ProductConfig.PublicKey, ParseVersion(ProductConfig.Version), language);
        }
        public static string Fetch(ReleaseInfo release) {
            byte[] bytes = Download(release.Url, checked((int)release.Size));
            if (bytes.LongLength != release.Size || Product.Sha(bytes) != release.Sha256) throw new CryptographicException("SF-UPDATE-011");
            string cache = Path.Combine(Paths.Profile, "Updates", release.Version.ToString(), Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(cache);
            string file = Path.Combine(cache, "Sofiles-Setup.exe");
            using (var stream = new FileStream(file, FileMode.CreateNew, FileAccess.Write, FileShare.None)) stream.Write(bytes, 0, bytes.Length);
            return file;
        }
        public static FileStream LockVerified(string file, ReleaseInfo release) {
            var stream = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.Read);
            try {
                using (var hash = SHA256.Create()) {
                    string actual = BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
                    if (stream.Length != release.Size || actual != release.Sha256) throw new CryptographicException("SF-UPDATE-012");
                }
                stream.Position = 0; return stream;
            } catch { stream.Dispose(); throw; }
        }
        public static void StartVerified(string file, ReleaseInfo release) {
            using (var guard = LockVerified(file, release)) Process.Start(new ProcessStartInfo(file) { UseShellExecute = false });
        }
    }
}
