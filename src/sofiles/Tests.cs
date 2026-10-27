using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using System.Xml;

namespace Sofiles {
    // Standalone console regression suite. Never calls installation, the network,
    // process launch, Preferences.Load/Save, or the user's installed application.
    public static class Tests {
        public sealed class CheckResult {
            public string name;
            public bool passed;
            public string detail;
        }

        static readonly List<CheckResult> checks = new List<CheckResult>();
        static readonly UTF8Encoding utf8 = new UTF8Encoding(false);
        static string runRoot;

        public static int Main(string[] args) {
            try {
                Require(args.Length == 2, "Expected fixture workspace directory and built product directory.");
                string productRoot = Path.GetFullPath(args[1]).TrimEnd('\\', '/');
                string workspace = FindWorkspace(productRoot);
                string fixtureRoot = Path.GetFullPath(args[0]).TrimEnd('\\', '/');
                Require(IsInside(workspace, fixtureRoot), "Fixture directory must be inside this workspace.");
                // Inspect every existing ancestor before creating anything.
                Paths.Inside(workspace, fixtureRoot.Substring(workspace.Length + 1));
                Paths.Inside(workspace, productRoot.Substring(workspace.Length + 1));
                Directory.CreateDirectory(fixtureRoot);
                runRoot = Paths.Inside(fixtureRoot, "tests-" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(runRoot);
                Run("fixture_isolation", delegate {
                    Require(IsInside(fixtureRoot, runRoot), "Run escaped fixture directory.");
                    Require(!String.Equals(runRoot, productRoot, StringComparison.OrdinalIgnoreCase), "Fixture equals product directory.");
                });

                SignatureChecks();
                CacheChecks();
                ZipChecks();
                CleanupChecks();
                PreferenceChecks();
                foreach (string language in I18n.Languages) LanguageChecks(productRoot, language);

                Console.WriteLine(new JavaScriptSerializer().Serialize(checks));
                return 0;
            } catch {
                Console.WriteLine(new JavaScriptSerializer().Serialize(checks));
                throw;
            }
        }

        static void Require(bool condition, string message) {
            if (!condition) throw new InvalidOperationException(message);
        }
        static void Run(string name, Action test) {
            try {
                test();
                checks.Add(new CheckResult { name = name, passed = true, detail = "ok" });
            } catch (Exception error) {
                checks.Add(new CheckResult { name = name, passed = false, detail = error.GetType().Name + ": " + error.Message });
                throw new InvalidOperationException("Check failed: " + name, error);
            }
        }
        static void Expect<T>(Action action, string code = null) where T : Exception {
            try { action(); }
            catch (T error) {
                if (code != null) Require(error.Message == code, "Unexpected error code: " + error.Message);
                return;
            }
            throw new InvalidOperationException("Expected " + typeof(T).Name + " was not thrown.");
        }
        static bool IsInside(string root, string path) {
            string prefix = Path.GetFullPath(root).TrimEnd('\\', '/') + Path.DirectorySeparatorChar;
            return Path.GetFullPath(path).StartsWith(prefix, StringComparison.OrdinalIgnoreCase);
        }
        static string FindWorkspace(string productRoot) {
            for (var item = new DirectoryInfo(productRoot); item != null; item = item.Parent) {
                if (File.Exists(Path.Combine(item.FullName, "src", "sofiles", "Common.cs")) && File.Exists(Path.Combine(item.FullName, "config", "product.json")))
                    return item.FullName.TrimEnd('\\', '/');
            }
            throw new InvalidOperationException("Built product must be below the Clover workspace.");
        }
        static string Fixture(string relative) { return Paths.Inside(runRoot, relative); }
        static void WriteFixture(string relative, byte[] bytes) {
            string file = Fixture(relative);
            Directory.CreateDirectory(Path.GetDirectoryName(file));
            using (var stream = new FileStream(file, FileMode.CreateNew, FileAccess.Write, FileShare.None)) stream.Write(bytes, 0, bytes.Length);
        }

        static byte[] Manifest(string version, string url, byte[] payload, string prefix = "") {
            string xml = prefix + "<SofilesRelease schema=\"1\" product=\"Sofiles\" channel=\"stable\" version=\"" + version +
                "\" url=\"" + url + "\" sha256=\"" + Product.Sha(payload) + "\" size=\"" + payload.LongLength.ToString(CultureInfo.InvariantCulture) +
                "\"><Notes lang=\"fr\">Texte FR</Notes><Notes lang=\"en\">Text EN</Notes><Notes lang=\"de\">Text DE</Notes></SofilesRelease>";
            return utf8.GetBytes(xml);
        }
        static RSACryptoServiceProvider EphemeralRsa() {
            // Explicit ephemeral CSP flags prevent persistent test key files.
            var parameters = new CspParameters { ProviderType = 24, Flags = CspProviderFlags.CreateEphemeralKey };
            var rsa = new RSACryptoServiceProvider(3072, parameters);
            rsa.PersistKeyInCsp = false;
            return rsa;
        }
        static byte[] Sign(RSACryptoServiceProvider rsa, byte[] manifest) {
            return rsa.SignData(manifest, CryptoConfig.MapNameToOID("SHA256"));
        }
        static void SignatureChecks() {
            byte[] payload = utf8.GetBytes("inert signed fixture payload");
            byte[] valid = Manifest("1.10.0", "https://updates.example.invalid/Sofiles-Setup.exe", payload);
            using (var rsa = EphemeralRsa()) {
                string key = rsa.ToXmlString(false);
                byte[] signature = Sign(rsa, valid);
                Run("rsa3072_signed_manifest_valid", delegate {
                    Require(rsa.KeySize == 3072, "Test key is not RSA-3072.");
                    ReleaseInfo release = Updates.Verify(valid, signature, key, new Version(1, 9, 9), "fr");
                    Require(release != null && release.Version == new Version(1, 10, 0), "Wrong release version.");
                    Require(release.Sha256 == Product.Sha(payload) && release.Size == payload.Length && release.Notes == "Texte FR", "Wrong authenticated metadata.");
                });
                Run("rsa_manifest_altered_rejected", delegate {
                    byte[] altered = (byte[])valid.Clone();
                    int offset = utf8.GetString(valid).IndexOf("Texte FR", StringComparison.Ordinal);
                    Require(offset >= 0, "Fixture note is missing.");
                    altered[offset] ^= 1;
                    Expect<CryptographicException>(delegate { Updates.Verify(altered, signature, key, new Version(1, 9, 9), "fr"); }, "SF-UPDATE-003");
                });
                using (var wrong = EphemeralRsa()) {
                    Run("rsa_wrong_public_key_rejected", delegate {
                        Expect<CryptographicException>(delegate { Updates.Verify(valid, signature, wrong.ToXmlString(false), new Version(1, 9, 9), "fr"); }, "SF-UPDATE-003");
                    });
                }
                Run("signed_equal_release_replay_ignored", delegate {
                    Require(Updates.Verify(valid, signature, key, new Version(1, 10, 0), "en") == null, "Equal version was offered again.");
                });
                Run("signed_older_release_replay_ignored", delegate {
                    Require(Updates.Verify(valid, signature, key, new Version(1, 11, 0), "de") == null, "Older version was offered.");
                });
                Run("signed_http_url_rejected", delegate {
                    byte[] http = Manifest("1.10.0", "http://updates.example.invalid/fixture.exe", payload);
                    Expect<InvalidDataException>(delegate { Updates.Verify(http, Sign(rsa, http), key, new Version(1, 9, 9), "fr"); }, "SF-UPDATE-006");
                });
                Run("signed_manifest_dtd_rejected", delegate {
                    byte[] dtd = Manifest("1.10.0", "https://updates.example.invalid/fixture.exe", payload, "<!DOCTYPE SofilesRelease [<!ENTITY fixture 'local-only'>]>");
                    Expect<XmlException>(delegate { Updates.Verify(dtd, Sign(rsa, dtd), key, new Version(1, 9, 9), "fr"); });
                });
            }
            Run("numeric_version_1_10_above_1_9", delegate {
                Require(Updates.ParseVersion("1.10.0") > Updates.ParseVersion("1.9.99"), "Versions compared lexically.");
            });
            Run("ambiguous_version_format_rejected", delegate {
                foreach (string invalid in new[] { "01.2.3", "1.2", "1.2.3.4", "1.2.3-beta", "-1.2.3" })
                    Expect<InvalidDataException>(delegate { Updates.ParseVersion(invalid); }, "SF-UPDATE-001");
            });
        }

        static void CacheChecks() {
            byte[] original = utf8.GetBytes("inert-cache-fixture-original");
            WriteFixture("cache/setup.bin", original);
            string file = Fixture("cache/setup.bin");
            var release = new ReleaseInfo { Version = new Version(1, 10, 0), Size = original.Length, Sha256 = Product.Sha(original) };
            Run("cache_verified_lock_returns_original_bytes", delegate {
                using (var guard = Updates.LockVerified(file, release)) {
                    Require(guard.Position == 0 && guard.ReadByte() == original[0], "Verified stream was not rewound.");
                }
            });
            Run("cache_verified_lock_blocks_write", delegate {
                using (var guard = Updates.LockVerified(file, release)) {
                    Expect<IOException>(delegate {
                        using (var writer = new FileStream(file, FileMode.Open, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete)) { }
                    });
                    Require(Product.Sha(File.ReadAllBytes(file)) == release.Sha256, "Fixture changed during lock.");
                }
            });
            Run("cache_verified_lock_blocks_delete", delegate {
                using (var guard = Updates.LockVerified(file, release)) Expect<IOException>(delegate { File.Delete(file); });
                Require(File.Exists(file), "Locked fixture was deleted.");
            });
            Run("cache_same_size_substitution_rejected", delegate {
                byte[] changed = (byte[])original.Clone(); changed[0] ^= 1;
                File.WriteAllBytes(file, changed);
                Expect<CryptographicException>(delegate { using (var guard = Updates.LockVerified(file, release)) { } }, "SF-UPDATE-012");
            });
            Run("cache_wrong_size_rejected", delegate {
                File.WriteAllBytes(file, original);
                var wrongSize = new ReleaseInfo { Size = original.Length + 1, Sha256 = release.Sha256 };
                Expect<CryptographicException>(delegate { using (var guard = Updates.LockVerified(file, wrongSize)) { } }, "SF-UPDATE-012");
            });
        }

        static byte[] Zip(params string[] names) {
            using (var bytes = new MemoryStream()) {
                using (var archive = new ZipArchive(bytes, ZipArchiveMode.Create, true)) {
                    foreach (string name in names) {
                        ZipArchiveEntry entry = archive.CreateEntry(name);
                        using (var stream = entry.Open()) {
                            byte[] data = utf8.GetBytes("fixture:" + name); stream.Write(data, 0, data.Length);
                        }
                    }
                }
                return bytes.ToArray();
            }
        }
        static void ZipChecks() {
            Run("zip_valid_nested_file_extracted", delegate {
                string target = Fixture("zip-valid");
                Product.Extract(Zip("nested/test.txt"), target);
                Require(File.ReadAllText(Fixture("zip-valid/nested/test.txt"), utf8) == "fixture:nested/test.txt", "Valid ZIP fixture differs.");
            });
            Run("zip_parent_traversal_rejected", delegate {
                // Even a regression would escape only into the enclosing fixture.
                string target = Fixture("zip-traversal/target");
                Expect<InvalidDataException>(delegate { Product.Extract(Zip("../escaped.txt"), target); }, "SF-PATH-002");
                Require(!File.Exists(Fixture("zip-traversal/escaped.txt")), "Traversal escaped ZIP target.");
            });
            Run("zip_alternate_data_stream_rejected", delegate {
                Expect<InvalidDataException>(delegate { Product.Extract(Zip("file.txt:hidden"), Fixture("zip-ads")); }, "SF-PATH-001");
            });
            Run("zip_case_insensitive_duplicate_rejected", delegate {
                Expect<InvalidDataException>(delegate { Product.Extract(Zip("duplicate.txt", "DUPLICATE.TXT"), Fixture("zip-duplicate")); }, "SF-ZIP-003");
                Require(File.ReadAllText(Fixture("zip-duplicate/duplicate.txt"), utf8) == "fixture:duplicate.txt", "First entry was overwritten.");
            });
        }

        static void CleanupChecks() {
            string[] owned = {
                "versions/1.2.3/docs/fr/help.html",
                "versions/1.2.3/locales/fr.pak",
                "versions/1.2.3/assets/icons/app.ico"
            };
            Run("cleanup_removes_all_empty_ancestors", delegate {
                foreach (string path in owned) WriteFixture("cleanup-empty/" + path, utf8.GetBytes("owned"));
                string root = Fixture("cleanup-empty");
                InstallOps.DeleteOwnedFiles(root, owned);
                Require(Directory.Exists(root) && !Directory.EnumerateFileSystemEntries(root).Any(), "Empty ancestor directories were left behind.");
            });
            Run("cleanup_preserves_unknown_nested_file", delegate {
                foreach (string path in owned) WriteFixture("cleanup-preserve/" + path, utf8.GetBytes("owned"));
                string unknown = "cleanup-preserve/versions/1.2.3/docs/fr/user-note.txt";
                WriteFixture(unknown, utf8.GetBytes("preserve this user file"));
                InstallOps.DeleteOwnedFiles(Fixture("cleanup-preserve"), owned);
                Require(File.ReadAllText(Fixture(unknown), utf8) == "preserve this user file", "Unknown file was modified/deleted.");
                Require(!Directory.Exists(Fixture("cleanup-preserve/versions/1.2.3/assets")), "Unrelated empty owned ancestors remain.");
                Require(!Directory.Exists(Fixture("cleanup-preserve/versions/1.2.3/locales")), "Empty locale directory remains.");
                foreach (string path in owned) Require(!File.Exists(Fixture("cleanup-preserve/" + path)), "Owned file remains.");
            });
            Run("cleanup_rejects_path_outside_ownership_root", delegate {
                WriteFixture("cleanup-boundary/sentinel.txt", utf8.GetBytes("keep"));
                string root = Fixture("cleanup-boundary/owned"); Directory.CreateDirectory(root);
                Expect<InvalidDataException>(delegate { InstallOps.DeleteOwnedFiles(root, new[] { "../sentinel.txt" }); }, "SF-PATH-002");
                Require(File.ReadAllText(Fixture("cleanup-boundary/sentinel.txt"), utf8) == "keep", "Boundary sentinel changed.");
            });
        }

        static void PreferenceChecks() {
            Run("preferences_invalid_json_recovers_defaults", delegate {
                Preferences value = Preferences.Parse("{broken-json");
                Require(value != null && value.Language == "fr" && !value.AutomaticUpdates, "Invalid JSON did not recover defaults.");
            });
            Run("preferences_json_null_recovers_defaults", delegate {
                Preferences value = Preferences.Parse("null");
                Require(value != null && value.Language == "fr" && !value.AutomaticUpdates, "JSON null did not recover defaults.");
            });
            Run("preferences_unknown_language_falls_back", delegate {
                Preferences value = Preferences.Parse("{\"Language\":\"xx\",\"AutomaticUpdates\":true}");
                Require(value.Language == "fr" && value.AutomaticUpdates, "Language fallback discarded unrelated preference.");
            });
            Run("preferences_valid_values_retained", delegate {
                Preferences value = Preferences.Parse("{\"Language\":\"de\",\"AutomaticUpdates\":true,\"LastCheckUtc\":\"2026-10-27T12:00:00Z\"}");
                Require(value.Language == "de" && value.AutomaticUpdates && value.LastCheckUtc == "2026-10-27T12:00:00Z", "Valid preference values changed.");
            });
        }

        static void CopyTree(string source, string destination) {
            Require(IsInside(runRoot, destination), "Copy destination escaped fixtures.");
            Require((File.GetAttributes(source) & FileAttributes.ReparsePoint) == 0, "Product content contains a reparse directory.");
            Paths.Inside(runRoot, destination.Substring(runRoot.Length + 1));
            Directory.CreateDirectory(destination);
            foreach (string entry in Directory.GetFileSystemEntries(source)) {
                FileAttributes attributes = File.GetAttributes(entry);
                Require((attributes & FileAttributes.ReparsePoint) == 0, "Product content contains a reparse entry.");
                string target = Paths.Inside(destination, Path.GetFileName(entry));
                if ((attributes & FileAttributes.Directory) != 0) CopyTree(entry, target);
                else File.Copy(entry, target, false);
            }
        }
        static void LanguageChecks(string productRoot, string language) {
            Run("pak_" + language + "_all_53_preserve_metadata_and_replace_urls", delegate {
                string root = Fixture("languages/" + language);
                Directory.CreateDirectory(root);
                foreach (string directory in new[] { "locale-templates", "language-packs", "docs" })
                    CopyTree(Path.Combine(productRoot, directory), Path.Combine(root, directory));

                string[] templates = Directory.GetFiles(Path.Combine(root, "locale-templates"), "*.pak");
                Require(templates.Length == 53, "Expected exactly 53 locale templates, got " + templates.Length + ".");
                var originalHashes = templates.ToDictionary(p => p, p => Product.Sha(File.ReadAllBytes(p)));
                string pack = Path.Combine(root, "language-packs", language + ".pak");
                string originalPackHash = Product.Sha(File.ReadAllBytes(pack));
                var selected = Pak.Read(File.ReadAllBytes(pack));
                // Distinct future location verifies staging embeds final paths.
                string linksRoot = Fixture("published/" + language);
                var urls = new Dictionary<string, string> {
                    { "SOFILES_HOME_URI", new Uri(Path.Combine(linksRoot, "docs", language, "credits.html")).AbsoluteUri },
                    { "SOFILES_HELP_URI", new Uri(Path.Combine(linksRoot, "docs", language, "help.html")).AbsoluteUri },
                    { "SOFILES_DONATE_URI", new Uri(Path.Combine(linksRoot, "docs", language, "support.html")).AbsoluteUri },
                    { "SOFILES_RELEASES_URI", String.IsNullOrEmpty(ProductConfig.ReleasesUrl) ? new Uri(Path.Combine(linksRoot, "docs", language, "changelog.html")).AbsoluteUri : ProductConfig.ReleasesUrl }
                };
                string customText = String.Join("\n", selected.Where(pair => pair.Key >= 9500).Select(pair => utf8.GetString(pair.Value)));
                foreach (string marker in urls.Keys) Require(customText.Contains(marker), "Fixture language pack lacks URL marker " + marker + ".");

                Pak.Apply(root, language, linksRoot);
                Require(Directory.GetFiles(Path.Combine(root, "locales"), "*.pak").Length == 53, "Did not produce all 53 locales.");
                foreach (string template in templates) {
                    var before = Pak.Read(File.ReadAllBytes(template));
                    var after = Pak.Read(File.ReadAllBytes(Path.Combine(root, "locales", Path.GetFileName(template))));
                    ushort[] metadataBefore = before.Keys.Where(id => id < 9500).ToArray();
                    ushort[] metadataAfter = after.Keys.Where(id => id < 9500).ToArray();
                    Require(metadataBefore.SequenceEqual(metadataAfter), "Metadata IDs changed in " + Path.GetFileName(template) + ".");
                    foreach (ushort id in metadataBefore)
                        Require(before[id].SequenceEqual(after[id]), "Metadata bytes changed: " + Path.GetFileName(template) + "/" + id + ".");
                    foreach (var pair in selected.Where(pair => pair.Key >= 9500)) {
                        string expected = utf8.GetString(pair.Value);
                        foreach (var url in urls) expected = expected.Replace(url.Key, url.Value);
                        Require(after.ContainsKey(pair.Key) && after[pair.Key].SequenceEqual(utf8.GetBytes(expected)), "Wrong selected language entry: " + Path.GetFileName(template) + "/" + pair.Key + ".");
                    }
                    foreach (var pair in after.Where(pair => pair.Key >= 9500)) {
                        string text = utf8.GetString(pair.Value);
                        foreach (string marker in urls.Keys) Require(!text.Contains(marker), "Unresolved URL marker remains in " + Path.GetFileName(template) + ".");
                    }
                    Require(Product.Sha(File.ReadAllBytes(template)) == originalHashes[template], "Source locale template was modified.");
                }
                Require(Product.Sha(File.ReadAllBytes(pack)) == originalPackHash, "Source language pack was modified.");
            });
        }
    }
}
