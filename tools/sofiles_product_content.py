"""Build local Sofiles FR/EN/DE documents and Chromium v4 resource packs.

No target executable is loaded. URI markers are intentionally left unresolved:
the product manager installs the selected content and local absolute URIs later.
"""
from __future__ import annotations

from collections import Counter
from html import escape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import struct
from urllib.parse import urlsplit, unquote


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "analysis/extracted"
CONTACT = "so.messaoudi@gmail.com"
DONATE_URL = ("https://www.paypal.com/cgi-bin/webscr?cmd=_donations"
              "&business=so.messaoudi%40gmail.com&item_name=Sofiles"
              "&amount=20.00&currency_code=CHF")
URI_MARKERS = {
    11329: "SOFILES_HOME_URI",
    11330: "SOFILES_HELP_URI",
    11332: "SOFILES_DONATE_URI",
    11333: "SOFILES_RELEASES_URI",
}
LANGUAGE_SOURCES = {"fr": "fr", "en": "en-US", "de": "de"}
PROVENANCE_IDS: set[int] = set()
LEGACY_IDENTITY = re.compile(r"Clover|E[N]?JIE|Sofiane\s*Messaoudi", re.IGNORECASE)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_pak(data: bytes) -> dict[int, bytes]:
    if len(data) < 15:
        raise ValueError("Truncated resource pack")
    version, count, encoding = struct.unpack_from("<IIB", data)
    if version != 4 or encoding != 1:
        raise ValueError("Only observed v4 UTF-8 resource packs are supported")
    table_end = 9 + 6 * (count + 1)
    if table_end > len(data):
        raise ValueError("Truncated resource table")
    rows = [struct.unpack_from("<HI", data, 9 + 6 * i)
            for i in range(count + 1)]
    if rows[0][1] != table_end or rows[-1] != (0, len(data)):
        raise ValueError("Invalid resource payload bounds")
    ids = [rid for rid, _ in rows[:-1]]
    if ids != sorted(set(ids)):
        raise ValueError("Resource IDs must be unique and ordered")
    if any(not table_end <= a[1] <= b[1] <= len(data)
           for a, b in zip(rows, rows[1:])):
        raise ValueError("Invalid resource offsets")
    return {rid: data[offset:rows[i + 1][1]]
            for i, (rid, offset) in enumerate(rows[:-1])}


def write_pak(items: dict[int, bytes]) -> bytes:
    offset = 9 + 6 * (len(items) + 1)
    entries, payloads = [], []
    for rid in sorted(items):
        payload = items[rid]
        if not 0 <= rid <= 0xFFFF:
            raise ValueError("Resource ID is outside WORD bounds")
        entries.append(struct.pack("<HI", rid, offset))
        payloads.append(payload)
        offset += len(payload)
    return (struct.pack("<IIB", 4, len(items), 1) + b"".join(entries)
            + struct.pack("<HI", 0, offset) + b"".join(payloads))


EN_OVERRIDES = {
    10003: "Sofiles, your tabbed file manager.",
    10005: "Instant search",
    10007: "Sofiles did not close correctly. Click Restore to reopen your previous tabs.",
    10011: "Sofiles",
    10012: "Sofiles tools and interface © 2026 Sofiles contributors. Licences and notices retained.",
    10013: "BEGIN_LINK_CHRSofiles helpEND_LINK_CHR · BEGIN_LINK_OSSOptional 20 CHF donationEND_LINK_OSS",
    10014: "<a target=\"_blank\" href=\"$1\">Sofiles help</a> · <a target=\"_blank\" href=\"$2\">Licences and notices</a>",
    10015: "Reserved Sofiles resource. Expected argument: $1.",
    10016: "Reserved Sofiles resource.",
    10017: "Reserved Sofiles resource.",
    10030: "The Sofiles New Tab page has changed. Click these labels to switch sections. Your choice will be remembered.",
    10038: "Optional: automatically send usage statistics and crash reports to Google.",
    10043: "Sofiles closed because of an error. Relaunch now?",
    10047: "The Frame component is already installed for all users. Uninstall that version with administrator assistance before creating a personal installation.",
    10050: "This version of the Frame component is running and cannot be reinstalled. Close the component and try again.",
    10058: "No installation of Sofiles or the Frame component was found to update.",
    10062: "An incompatible installation of Sofiles or the Frame component was found. Uninstall it and try again.",
    10063: "An incompatible installation of Sofiles or the Frame component was found. Uninstall it and try again.",
    10064: "Invalid arguments. The Frame component cannot be installed in ready mode without also installing Sofiles.",
    10070: "A new version of Sofiles is available.",
    10071: "A Sofiles update is available.",
    10073: "This feature opens the application associated with telephone links.",
    10075: "Do not show this message again",
    11133: "Send to a mobile device",
    11246: "Tabbed file manager",
    11331: "Optional donation: 20 CHF through PayPal",
}


DE_OVERRIDES = {
    10000: "Sofiles",
    10001: "Sofiles",
    10002: "Sofiles",
    10003: "Sofiles, Ihr Dateimanager mit Tabs.",
    10004: "Unbekannte Version",
    10005: "Sofortsuche",
    10006: "Sofiles stellt Ihre letzte Sitzung beim Start wieder her. Einige sitzungsbezogene Einstellungen, etwa das Löschen von Daten beim Beenden, werden dabei deaktiviert.",
    10007: "Sofiles wurde nicht ordnungsgemäß beendet. Klicken Sie auf „Wiederherstellen“, um Ihre letzten Tabs erneut zu öffnen.",
    10008: "$1 · Sofiles",
    10009: "$1",
    10010: "Hilfe zu Sofiles",
    10011: "Sofiles",
    10012: "Sofiles-Werkzeuge und Oberfläche © 2026 Sofiles contributors. Lizenzen und Hinweise bleiben erhalten.",
    10013: "BEGIN_LINK_CHRSofiles-HilfeEND_LINK_CHR · BEGIN_LINK_OSSFreiwillige Spende von 20 CHFEND_LINK_OSS",
    10014: "<a target=\"_blank\" href=\"$1\">Sofiles-Hilfe</a> · <a target=\"_blank\" href=\"$2\">Lizenzen und Hinweise</a>",
    10015: "Reservierte Sofiles-Ressource. Erwartetes Argument: $1.",
    10016: "Reservierte Sofiles-Ressource.",
    10017: "Reservierte Sofiles-Ressource.",
    10018: "Sofiles",
    10019: "Sofiles-Symbolleiste",
    10020: "Sofiles reagiert nicht. Jetzt neu starten?",
    10021: "Sofiles importiert die folgenden Elemente aus $1:",
    10022: "Die Einstellungen von Mozilla Firefox sind nicht verfügbar, solange der Browser geöffnet ist. Speichern Sie Ihre Arbeit, schließen Sie alle Firefox-Fenster und klicken Sie auf „Weiter“, um die Einstellungen in Sofiles zu importieren.",
    10023: "Über Sofiles",
    10024: "Schließen Sie alle Sofiles-Fenster und versuchen Sie es erneut.",
    10025: "Möchten Sie Sofiles deinstallieren?",
    10026: "Sofiles deinstallieren",
    10027: "Willkommen bei Sofiles",
    10028: "Sofiles starten",
    10029: "Willkommen bei Sofiles",
    10030: "Die Seite Neuer Tab in Sofiles wurde geändert. Klicken Sie auf diese Bezeichnungen, um zwischen den Bereichen zu wechseln. Ihre Auswahl wird gespeichert.",
    10031: "Sofiles muss eine externe Anwendung öffnen, um $1-Links zu verarbeiten. Angeforderter Link: $2.",
    10032: "Die Sofiles-Basis benötigt Windows XP oder neuer. Einige Funktionen sind möglicherweise nicht verfügbar.",
    10033: "Sofiles unterstützt $1 nicht.",
    10034: "Schließen Sie alle Sofiles-Fenster und starten Sie die Anwendung neu, um diese Änderung zu übernehmen.",
    10035: "Sofiles im Hintergrund ausführen lassen",
    10036: "Hintergrundanwendungen nach dem Schließen von Sofiles weiter ausführen",
    10037: "Sofiles kann das Datenverzeichnis nicht lesen oder beschreiben:\n\n$1",
    10038: "Optional: Nutzungsstatistiken und Absturzberichte automatisch an Google senden.",
    10039: "Dieses Profil stammt aus einer neueren Sofiles-Version und kann nicht verwendet werden.\n\nEinige Funktionen sind möglicherweise nicht verfügbar. Wählen Sie ein anderes Profilverzeichnis oder verwenden Sie eine kompatible Sofiles-Version.",
    10040: "Ihre Einstellungen können nicht gelesen werden.\n\nEinige Funktionen sind möglicherweise nicht verfügbar. Änderungen an Ihren Einstellungen werden nicht gespeichert.",
    10041: "Die Einstellungsdatei ist beschädigt oder ungültig.\n\nSofiles kann Ihre Einstellungen nicht wiederherstellen.",
    10042: "Sofiles",
    10043: "Sofiles wurde aufgrund eines Fehlers beendet. Jetzt neu starten?",
    10044: "Sofiles beenden",
    10045: "Ein Administrator hat Sofiles für alle Benutzer installiert. Diese Installation ersetzt nun Ihre persönliche Installation.",
    10046: "Auf diesem Computer ist bereits eine neuere Sofiles-Version vorhanden. Falls sie nicht funktioniert, deinstallieren Sie sie und versuchen Sie es erneut.",
    10047: "Die Frame-Komponente ist bereits für alle Benutzer installiert. Deinstallieren Sie diese Version mit Administratorrechten, bevor Sie eine persönliche Installation erstellen.",
    10048: "Die Installation ist aufgrund eines nicht näher angegebenen Fehlers fehlgeschlagen. Schließen Sie Sofiles, falls es geöffnet ist, und versuchen Sie es erneut.",
    10049: "Diese Sofiles-Version wird gerade ausgeführt und kann nicht erneut installiert werden. Schließen Sie Sofiles und versuchen Sie es erneut.",
    10050: "Diese Version der Frame-Komponente wird gerade ausgeführt und kann nicht erneut installiert werden. Schließen Sie die Komponente und versuchen Sie es erneut.",
    10051: "Die Installation ist aufgrund eines nicht näher angegebenen Fehlers fehlgeschlagen. Besorgen Sie das Sofiles-Installationspaket erneut.",
    10052: "Die Sofiles-Basis benötigt Windows Vista oder Windows XP mit Service Pack 2 oder neuer.",
    10053: "Während der Installation ist ein Windows-Fehler aufgetreten. Besorgen Sie das Sofiles-Installationspaket erneut.",
    10054: "Das Installationsprogramm kann kein temporäres Verzeichnis erstellen. Prüfen Sie den freien Speicherplatz und Ihre Installationsberechtigungen.",
    10055: "Das Installationsprogramm kann das Archiv nicht entpacken. Besorgen Sie das Sofiles-Installationspaket erneut.",
    10056: "Das Installationsarchiv ist beschädigt oder ungültig. Besorgen Sie das Sofiles-Installationspaket erneut.",
    10057: "Ihre Rechte reichen für eine Installation für alle Benutzer nicht aus. Starten Sie das Installationsprogramm als Administrator erneut.",
    10058: "Es wurde keine Installation von Sofiles oder der Frame-Komponente zum Aktualisieren gefunden.",
    10059: "Ein Konflikt mit einer anderen installierten Anwendung wurde erkannt.",
    10060: "Deinstallation abgeschlossen.",
    10061: "Das Sofiles-Installationsverzeichnis wird von einem anderen Programm verwendet. Starten Sie den Computer neu und versuchen Sie es erneut.",
    10062: "Eine inkompatible Installation von Sofiles oder der Frame-Komponente wurde gefunden. Deinstallieren Sie sie und versuchen Sie es erneut.",
    10063: "Eine inkompatible Installation von Sofiles oder der Frame-Komponente wurde gefunden. Deinstallieren Sie sie und versuchen Sie es erneut.",
    10064: "Ungültige Argumente. Die Frame-Komponente kann nicht im Bereitschaftsmodus installiert werden, ohne auch Sofiles zu installieren.",
    10065: "",
    10066: "Sofiles importiert Ihre Lesezeichen.",
    10067: "Auch Ihre Browserdaten löschen?",
    10068: "Deinstallieren",
    10069: "Eine neue Sofiles-Version ist verfügbar.",
    10070: "Eine neue Sofiles-Version ist verfügbar.",
    10071: "Eine Aktualisierung für Sofiles ist verfügbar.",
    10072: "Sofiles wurde seit Ihrer letzten Nutzung vor mindestens 30 Tagen aktualisiert.",
    10073: "Diese Funktion öffnet die Anwendung, die Telefonlinks zugeordnet ist.",
    10074: "Bereits installierte Version ausprobieren",
    10075: "Diese Meldung nicht mehr anzeigen",
    10076: "Warum wird diese Meldung angezeigt?",
    10077: "Sofiles wird automatisch bei Ihrer Windows-Anmeldung gestartet.",
    10078: "Für diese Windows-Version sind keine Sofiles-Aktualisierungen mehr verfügbar.",
    10079: "Sofiles wurde auf Version $1 aktualisiert.",
    10080: "Die Aktualisierung ist fast abgeschlossen. Starten Sie Sofiles neu, um sie abzuschließen.",
    10081: "Sofiles ist auf dem neuesten Stand.",
    10082: "Sofiles wird aktualisiert…",
    10083: "Sofiles neu starten, um die Aktualisierung abzuschließen",
    10084: "Sofiles ist auf dem neuesten Stand ($1).",
    10085: "Zu Sofiles hinzufügen",
    10086: "$1 wurde zu Sofiles hinzugefügt.",
    10087: "<b>Achtung:</b> Sofiles kann Erweiterungen nicht daran hindern, Ihren Browserverlauf aufzuzeichnen. Deaktivieren Sie diese Option, um die Erweiterung im Inkognitomodus auszuschalten.",
    10088: "Aus Sofiles entfernen",
    10089: "Über &Sofiles",
    10090: "&Sofiles aktualisieren",
    11028: "An die Startseite anheften",
    11133: "An ein Mobilgerät senden",
    11246: "Dateimanager mit Tabs",
    11325: "Ordner mit einem Mausradklick in einem neuen Tab öffnen",
    11326: "Mit einem Doppelklick auf eine freie Fläche zum übergeordneten Ordner wechseln",
    11327: "Tab durch Doppelklick auf seinen Titel schließen",
    11328: "Mit dem Mausrad über der Tableiste zwischen Tabs wechseln",
    11331: "Freiwillige Spende: 20 CHF über PayPal",
}


def _overrides(language: str) -> dict[int, str]:
    if language == "fr":
        path = ROOT / "analysis/branding/full-locales/fr-overrides.json"
        changes = {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
        changes[10011] = "Sofiles"
        changes[10012] = "Outils et interface Sofiles © 2026 Sofiles contributors. Licences et notices conservées."
        changes[10013] = "BEGIN_LINK_CHRAide SofilesEND_LINK_CHR · BEGIN_LINK_OSSDon facultatif de 20 CHFEND_LINK_OSS"
        changes[10014] = '<a target="_blank" href="$1">Aide Sofiles</a> · <a target="_blank" href="$2">Licences et notices</a>'
        changes[11246] = "Gestionnaire de fichiers à onglets"
        changes[11331] = "Don facultatif : 20 CHF via PayPal"
        return changes
    return EN_OVERRIDES if language == "en" else DE_OVERRIDES


def _placeholders(text: str) -> Counter:
    # Excludes monetary amounts such as the original "$10.00 suggested".
    return Counter(re.findall(r"\$[1-9]\d*(?!\d|\.\d)|(?:BEGIN|END)_LINK_(?:CHR|OSS)", text))


def _localised_pack(original: dict[int, bytes], language: str) -> dict[int, bytes]:
    changes = _overrides(language)
    if set(changes) - original.keys():
        raise ValueError("An override ID is missing from the original pack")
    result = dict(original)
    for rid, raw in original.items():
        if rid < 9500:
            continue
        before = raw.decode("utf-8")
        after = changes.get(rid, before.replace("Clover", "Sofiles"))
        after = after.replace("\u2014", ":").replace("\u2013", "-")
        if rid == 11168:
            # The retired native updater's error argument is intentionally unused.
            after = {"fr": "Les mises à jour se gèrent dans les réglages Sofiles.",
                     "en": "Manage updates in Sofiles settings.",
                     "de": "Updates werden in den Sofiles-Einstellungen verwaltet."}[language]
        if rid != 11168 and _placeholders(after) != _placeholders(before):
            raise ValueError(f"Placeholder mismatch in {language}/{rid}")
        result[rid] = after.encode("utf-8")
    for rid, marker in URI_MARKERS.items():
        result[rid] = marker.encode("ascii")
    result[11334] = b""
    for rid, payload in result.items():
        if LEGACY_IDENTITY.search(payload.decode("utf-8")):
            raise ValueError(f"Legacy or personal identity in {language}/{rid}")
    return result


COPY = {
    "fr": {
        "language": "Français", "help": "Aide", "credits": "À propos", "changelog": "Versions", "support": "Contact et soutien",
        "intro": "Sofiles ajoute des onglets et une barre de favoris à vos dossiers Windows.",
        "help_title": "Bien démarrer avec Sofiles",
        "help_body": "<h2>Onglets et favoris</h2><p>Utilisez les onglets pour garder plusieurs dossiers ouverts. Le menu des onglets permet de les fermer, de les épingler et de rouvrir un onglet fermé. La barre de favoris donne accès à vos dossiers enregistrés.</p><h2>Langue</h2><p>Choisissez Français, English ou Deutsch dans le gestionnaire Sofiles, puis relancez Sofiles pour appliquer la langue. Les fenêtres affichées par Windows suivent les paramètres de Windows.</p><h2>Explorateur classique</h2><p>La base historique de Sofiles peut nécessiter l'interface classique de l'Explorateur. Le fonctionnement avec l'interface moderne de Windows 11 n'est pas garanti. La personnalisation ne change pas automatiquement ce réglage Windows.</p>",
        "contact_label": "Contacter Sofiles",
        "contact_note": "Décrivez le problème, la version de Sofiles et celle de Windows. Joignez une capture si elle est utile, en masquant vos données personnelles. Aucun rapport n'est envoyé automatiquement par ces pages.",
        "donate_title": "Soutien facultatif",
        "donate_note": "Vous pouvez soutenir Sofiles par un don de 20 CHF via PayPal. L'application reste utilisable sans don. Celui-ci n'achète aucune fonction ni garantie de support.",
        "paypal_note": "Le lien propose so.messaoudi@gmail.com comme bénéficiaire. Ce compte PayPal reste à confirmer avant diffusion. Vérifiez le bénéficiaire et le montant dans PayPal avant de payer.",
        "donate_button": "Ouvrir PayPal pour un don facultatif de 20 CHF",
        "payment_note": "Ouvrir ce lien ne confirme aucun paiement. Vous choisissez ensuite si vous souhaitez continuer dans PayPal.",
        "credit_title": "À propos de Sofiles",
        "credit_body": "<p>Sofiles est un gestionnaire de fichiers à onglets pour Windows. Il propose une barre de favoris et une interface en français, anglais ou allemand.</p><p>Outils, interface et documentation Sofiles : © 2026 Sofiles contributors. La portée de ce crédit et les droits des composants fournis sont détaillés dans les licences et notices.</p>",
        "license": "Licences et notices",
        "changes_title": "Historique des versions",
        "changes_body": "<h2>{version}</h2><ul><li>Nouvel assistant d'installation basé sur NSIS 3.13.</li><li>Versions publiques distribuées sur GitHub Releases.</li><li>Interface et aide en français, anglais et allemand.</li><li>Identité Sofiles dans les écrans ; licences et notices regroupées dans un dossier dédié.</li></ul><h2>1.1.0</h2><p>Gestion des langues, aide locale et contact Sofiles. Ajout d'un don PayPal facultatif de 20 CHF.</p><h2>1.0.0</h2><p>Première édition Sofiles avec onglets et favoris.</p>",
        "limit": "Les fenêtres fournies par Windows peuvent suivre une autre langue que Sofiles. Consultez l'aide pour les réglages de compatibilité.",
        "local": "Documentation locale", "version": "Version", "license_missing": "La licence originale est conservée dans le dossier de l'application.",
    },
    "en": {
        "language": "English", "help": "Help", "credits": "About", "changelog": "Versions", "support": "Contact and support",
        "intro": "Sofiles adds tabs and a bookmarks bar to your Windows folders.",
        "help_title": "Getting started with Sofiles",
        "help_body": "<h2>Tabs and bookmarks</h2><p>Use tabs to keep several folders open. The tab menu lets you close or pin tabs and reopen a closed tab. The bookmarks bar gives you access to saved folders.</p><h2>Language</h2><p>Select Français, English or Deutsch in the Sofiles manager, then relaunch Sofiles to apply the language. Windows dialogs follow your Windows language settings.</p><h2>Classic Explorer</h2><p>The historical Sofiles base may require the classic File Explorer interface. Compatibility with the modern Windows 11 interface is not guaranteed. This personal edition does not automatically change that Windows setting.</p>",
        "contact_label": "Contact Sofiles",
        "contact_note": "Describe the issue and include your Sofiles and Windows versions. Add a screenshot if useful, after hiding personal information. These pages do not automatically send any report.",
        "donate_title": "Optional support",
        "donate_note": "You can support Sofiles with a 20 CHF donation through PayPal. You can use the application without donating. A donation does not purchase features or guaranteed support.",
        "paypal_note": "The link proposes so.messaoudi@gmail.com as the recipient. This PayPal account still needs confirmation before distribution. Check the recipient and amount in PayPal before paying.",
        "donate_button": "Open PayPal for an optional 20 CHF donation",
        "payment_note": "Opening this link does not confirm a payment. You then decide whether to continue in PayPal.",
        "credit_title": "About Sofiles",
        "credit_body": "<p>Sofiles is a tabbed file manager for Windows. It includes a bookmarks bar and an interface in French, English or German.</p><p>Sofiles tools, interface and documentation: © 2026 Sofiles contributors. The scope of this credit and the rights covering the supplied components are detailed in the licences and notices.</p>",
        "license": "Licences and notices",
        "changes_title": "Version history",
        "changes_body": "<h2>{version}</h2><ul><li>New installation wizard based on NSIS 3.13.</li><li>Public versions distributed through GitHub Releases.</li><li>Interface and help in French, English and German.</li><li>Sofiles identity throughout the screens, with licences and notices in a dedicated folder.</li></ul><h2>1.1.0</h2><p>Language selection, local help and Sofiles contact details. Added an optional 20 CHF PayPal donation.</p><h2>1.0.0</h2><p>First Sofiles edition with tabs and bookmarks.</p>",
        "limit": "Dialogs supplied by Windows may use a different language from Sofiles. See the help page for compatibility settings.",
        "local": "Local documentation", "version": "Version", "license_missing": "The original licence is retained in the application folder.",
    },
    "de": {
        "language": "Deutsch", "help": "Hilfe", "credits": "Über Sofiles", "changelog": "Versionen", "support": "Kontakt und Unterstützung",
        "intro": "Sofiles ergänzt Ihre Windows-Ordner um Tabs und eine Lesezeichenleiste.",
        "help_title": "Erste Schritte mit Sofiles",
        "help_body": "<h2>Tabs und Lesezeichen</h2><p>Mit Tabs können Sie mehrere Ordner geöffnet halten. Über das Tabmenü können Sie Tabs schließen oder anheften und geschlossene Tabs wieder öffnen. Die Lesezeichenleiste bietet Zugriff auf gespeicherte Ordner.</p><h2>Sprache</h2><p>Wählen Sie Français, English oder Deutsch im Sofiles-Manager und starten Sie Sofiles neu, um die Sprache zu übernehmen. Windows-Dialoge verwenden die Windows-Spracheinstellungen.</p><h2>Klassischer Explorer</h2><p>Die historische Sofiles-Basis benötigt möglicherweise die klassische Explorer-Oberfläche. Die Kompatibilität mit der modernen Oberfläche von Windows 11 ist nicht garantiert. Diese persönliche Edition ändert die Windows-Einstellung nicht automatisch.</p>",
        "contact_label": "Sofiles kontaktieren",
        "contact_note": "Beschreiben Sie das Problem und nennen Sie Ihre Sofiles- und Windows-Version. Fügen Sie bei Bedarf einen Screenshot hinzu und blenden Sie persönliche Daten vorher aus. Diese Seiten versenden keine automatischen Berichte.",
        "donate_title": "Freiwillige Unterstützung",
        "donate_note": "Sie können Sofiles mit einer Spende von 20 CHF über PayPal unterstützen. Die Anwendung ist auch ohne Spende nutzbar. Eine Spende kauft keine Funktionen und keinen garantierten Support.",
        "paypal_note": "Der Link schlägt so.messaoudi@gmail.com als Empfänger vor. Dieses PayPal-Konto muss vor der Weitergabe noch bestätigt werden. Prüfen Sie den Empfänger und den Betrag in PayPal, bevor Sie zahlen.",
        "donate_button": "PayPal für eine freiwillige Spende von 20 CHF öffnen",
        "payment_note": "Das Öffnen dieses Links bestätigt keine Zahlung. Anschließend entscheiden Sie selbst, ob Sie in PayPal fortfahren möchten.",
        "credit_title": "Über Sofiles",
        "credit_body": "<p>Sofiles ist ein Dateimanager mit Tabs für Windows. Er enthält eine Lesezeichenleiste und eine Oberfläche auf Französisch, Englisch oder Deutsch.</p><p>Sofiles-Werkzeuge, Oberfläche und Dokumentation: © 2026 Sofiles contributors. Der Umfang dieser Angabe und die Rechte an den mitgelieferten Komponenten sind in den Lizenzen und Hinweisen beschrieben.</p>",
        "license": "Lizenzen und Hinweise",
        "changes_title": "Versionsverlauf",
        "changes_body": "<h2>{version}</h2><ul><li>Neuer Installationsassistent auf Basis von NSIS 3.13.</li><li>Öffentliche Versionen werden über GitHub Releases verteilt.</li><li>Oberfläche und Hilfe auf Französisch, Englisch und Deutsch.</li><li>Sofiles-Identität in den Dialogen sowie Lizenzen und Hinweise in einem eigenen Ordner.</li></ul><h2>1.1.0</h2><p>Sprachauswahl, lokale Hilfe und Sofiles-Kontakt. Freiwillige PayPal-Spende von 20 CHF ergänzt.</p><h2>1.0.0</h2><p>Erste Sofiles-Edition mit Tabs und Lesezeichen.</p>",
        "limit": "Windows-Dialoge können eine andere Sprache als Sofiles verwenden. Einstellungen zur Kompatibilität finden Sie in der Hilfe.",
        "local": "Lokale Dokumentation", "version": "Version", "license_missing": "Die ursprüngliche Lizenz bleibt im Anwendungsordner erhalten.",
    },
}


STYLE = """body{max-width:780px;margin:48px auto;padding:0 24px;font:16px/1.65 'Segoe UI',sans-serif;color:#172c3b;background:#f7f9fb}header,footer{color:#536677}nav{display:flex;flex-wrap:wrap;gap:10px 20px;margin:18px 0}a{color:#155ca2}a:focus{outline:3px solid #c48c17;outline-offset:3px}h1,h2{line-height:1.25}h1{font-size:2rem}h2{margin-top:28px;font-size:1.2rem}.note{padding:14px 18px;border-left:3px solid #869bad;background:#eaf0f5}.button{display:inline-block;padding:10px 16px;background:#155ca2;color:white;border-radius:6px;text-decoration:none}footer{border-top:1px solid #d3dde6;margin-top:36px;padding-top:18px;font-size:.9rem}@media(max-width:560px){body{margin:24px auto}h1{font-size:1.65rem}}"""


def _document(language: str, page: str, version: str) -> str:
    text = COPY[language]
    nav = "".join(f'<a href="{name}.html"'
                  + (' aria-current="page"' if page == name else '')
                  + f'>{escape(text[name])}</a>'
                  for name in ["help", "credits", "changelog", "support"])
    languages = " · ".join(
        f'<a href="../{code}/{page}.html" lang="{code}" hreflang="{code}">{escape(COPY[code]["language"])}</a>'
        for code in LANGUAGE_SOURCES)
    support = (f'<p><a href="mailto:{CONTACT}">{escape(text["contact_label"])} : {CONTACT}</a></p>'
               f'<p>{escape(text["contact_note"])}</p>')
    if page == "help":
        title, body = text["help_title"], text["help_body"] + support
    elif page == "credits":
        title = text["credit_title"]
        body = text["credit_body"] + f'<p><a href="../../licenses/NOTICE.md">{escape(text["license"])}</a></p>'
    elif page == "changelog":
        title = text["changes_title"]
        body = text["changes_body"].format(version=escape(version))
    else:
        title = text["support"]
        body = (support + f'<h2>{escape(text["donate_title"])}</h2>'
                f'<p>{escape(text["donate_note"])}</p>'
                f'<p class="note">{escape(text["paypal_note"])}</p>'
                f'<p><a class="button" href="{escape(DONATE_URL, quote=True)}" rel="noopener noreferrer">{escape(text["donate_button"])}</a></p>'
                f'<p>{escape(text["payment_note"])}</p>')
    return (f'<!doctype html>\n<html lang="{language}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>{escape(title)} | Sofiles {escape(version)}</title><style>{STYLE}</style></head>'
            f'<body><header><strong>Sofiles {escape(version)}</strong><p>{escape(text["intro"])}</p>'
            f'<nav aria-label="Sofiles">{nav}</nav><p>{languages}</p></header>'
            f'<main><h1>{escape(title)}</h1>{body}</main>'
            f'<footer><p>{escape(text["limit"])}</p><p>{escape(text["local"])} · '
            f'{escape(text["version"])} {escape(version)} · © 2026 Sofiles contributors</p></footer></body></html>\n')


class _DocumentLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.forbidden: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and "href" in values:
            self.links.append(values["href"])
        if tag in {"script", "iframe", "form", "img", "link"}:
            self.forbidden.append(tag)


def build_content(output: Path, version: str) -> dict:
    """Create local documents, 3 language packs, and 53 preserved templates.

    The caller owns staging/atomic installation. The returned report and the
    saved JSON report describe this build, not runtime application behavior.
    """
    output = Path(output).resolve()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", version):
        raise ValueError("Expected a semantic version, for example 1.2.0")
    if output == SOURCE.resolve() or output.is_relative_to(SOURCE.resolve()):
        raise ValueError("The output must not overwrite the source artifacts")
    sources = sorted((SOURCE / "locales").glob("*.pak"))
    if len(sources) != 53:
        raise ValueError("Expected the 53 observed source locale packs")
    originals = {}
    for path in sources:
        raw = path.read_bytes()
        parsed = read_pak(raw)
        if write_pak(parsed) != raw:
            raise ValueError(f"Source pack round trip failed: {path.name}")
        originals[path.stem] = (raw, parsed)
    expected_ids = originals["fr"][1].keys()
    if any(pack.keys() != expected_ids for _, pack in originals.values()):
        raise ValueError("The source locale ID sets differ")
    for folder in ["language-packs", "locale-templates", "locales", "docs", "licenses"]:
        (output / folder).mkdir(parents=True, exist_ok=True)

    canonical, language_report = {}, []
    for language, source_name in LANGUAGE_SOURCES.items():
        original = originals[source_name][1]
        updated = _localised_pack(original, language)
        payload = write_pak(updated)
        if read_pak(payload) != updated:
            raise ValueError("Canonical pack output validation failed")
        if any(updated[rid] != raw for rid, raw in original.items() if rid < 9500):
            raise ValueError("Canonical pack language metadata changed")
        (output / "language-packs" / f"{language}.pak").write_bytes(payload)
        canonical[language] = updated
        language_report.append({"language": language, "source": source_name + ".pak",
                                "resource_count": len(updated),
                                "changed_ids": [rid for rid in original if original[rid] != updated[rid]],
                                "metadata_below_9500_unchanged": True,
                                "placeholders_preserved": True,
                                "sha256": _sha(payload)})

    locale_report = []
    french = canonical["fr"]
    for path in sources:
        raw, original = originals[path.stem]
        updated = {rid: french[rid] if rid >= 9500 else value
                   for rid, value in original.items()}
        payload = write_pak(updated)
        if read_pak(payload) != updated:
            raise ValueError(f"Merged pack output validation failed: {path.name}")
        # The manager only needs each template's locale-specific parameters.
        # Ship neutral Sofiles captions instead of retaining legacy identities.
        (output / "locale-templates" / path.name).write_bytes(payload)
        (output / "locales" / path.name).write_bytes(payload)
        locale_report.append({"file": path.name, "source_sha256": _sha(raw),
                              "template_sha256": _sha(payload),
                              "output_sha256": _sha(payload),
                              "template_contains_only_sofiles_identity": all(not LEGACY_IDENTITY.search(value.decode("utf-8")) for value in updated.values()),
                              "metadata_below_9500_unchanged": all(updated[rid] == value for rid, value in original.items() if rid < 9500),
                              "french_content_from_9500": all(updated[rid] == french[rid] for rid in original if rid >= 9500)})

    original_license = (SOURCE / "License.txt").read_bytes()
    license_path = output / "licenses/Clover-original.txt"
    license_path.write_bytes(original_license)
    notice = (
        "# Sofiles licences and notices\n\n"
        "## Sofiles additions\n\n"
        "Sofiles tools, interface and documentation: © 2026 Sofiles contributors. "
        "This credit covers the additions made for Sofiles. It does not claim "
        "authorship or ownership of the supplied engine or its third-party components.\n\n"
        "## Original application\n\n"
        "Sofiles uses the Clover 3.0.406 base from EJIE Technology / EJIE Soft Studio, "
        "© 2014 EJIE Technology. Its original licence is preserved byte for byte in "
        "[Clover-original.txt](Clover-original.txt). Rebranding leaves the original "
        "rights and licence terms in place. The engine is not represented as open source.\n\n"
        "## Third-party components\n\n"
        "The supplied application contains components derived from Chromium. "
        "Their respective authors retain their rights. Original component notices "
        "and any licence terms contained in the supplied artifacts remain applicable. "
        "This notice does not relicense those components or create rights in their code.\n"
    )
    (output / "licenses/NOTICE.md").write_text(notice, encoding="utf-8")
    root_license = output / "License.txt"
    if root_license.exists():
        if root_license.is_symlink() or root_license.read_bytes() != original_license:
            raise ValueError("Unexpected root licence; refusing to remove unrelated content")
        root_license.unlink()
    document_paths = []
    for language in LANGUAGE_SOURCES:
        directory = output / "docs" / language
        directory.mkdir(exist_ok=True)
        for page in ["help", "credits", "changelog", "support"]:
            path = directory / (page + ".html")
            path.write_text(_document(language, page, version), encoding="utf-8")
            document_paths.append(path)
    document_report = []
    for path in document_paths:
        parser = _DocumentLinks()
        text = path.read_text(encoding="utf-8")
        parser.feed(text)
        if parser.forbidden:
            raise ValueError(f"Active/external document content found: {path}")
        local_count = 0
        for href in parser.links:
            uri = urlsplit(href)
            if not uri.scheme:
                target = (path.parent / unquote(uri.path)).resolve()
                if not target.is_relative_to(output) or not target.is_file():
                    raise ValueError(f"Invalid local documentation link: {href}")
                local_count += 1
            elif uri.scheme == "mailto":
                if href != f"mailto:{CONTACT}":
                    raise ValueError("Unexpected contact recipient")
            elif href != DONATE_URL:
                raise ValueError(f"Unexpected external document URL: {href}")
        if "\ufffd" in text:
            raise ValueError("Invalid replacement character in document")
        if LEGACY_IDENTITY.search(text):
            raise ValueError(f"Legacy or personal identity in document: {path}")
        if "\u2014" in text or "\u2013" in text:
            raise ValueError(f"Long dash in document prose: {path}")
        document_report.append({"file": str(path.relative_to(output)),
                                "local_links_checked": local_count,
                                "no_scripts_forms_or_remote_assets": True,
                                "sha256": _sha(path.read_bytes())})

    report = {"version": version, "output": str(output), "languages": language_report,
              "uri_resource_markers": {str(k): v for k, v in URI_MARKERS.items()},
              "legacy_update_endpoint_11334": "empty",
              "default_language": "fr", "original_templates": len(locale_report),
              "template_policy": "Original metadata below 9500; neutral Sofiles French text from 9500.",
              "locale_merges": locale_report, "documents": document_report,
              "contact": CONTACT, "donation_url": DONATE_URL,
              "donation_optional": True, "suggested_amount": "20.00", "currency": "CHF",
              "paypal_recipient_confirmation_required": True,
              "paypal_account_verified": False, "payment_initiated": False,
              "source_license_preserved": license_path.read_bytes() == original_license,
              "source_license_path": "licenses/Clover-original.txt",
              "source_license_sha256": _sha(original_license),
              "root_legacy_license_absent": not root_license.exists(),
              "provenance_confined_to_license_folder": True,
              "ordinary_documents_have_no_legacy_or_personal_identity": True,
              "ordinary_documents_have_no_long_dashes": True,
              "native_dialogs_outside_pak": "Not changed; inherited native strings and Windows dialogs may use another language.",
              "runtime_uri_resolution": "Required by manager before activating the selected packs.",
              "security_guarantee": False, "target_execution": False,
              "source_files_unchanged": all(path.read_bytes() == originals[path.stem][0] for path in sources)}
    report_path = ROOT / "analysis/product-content/validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", default="1.2.0")
    args = parser.parse_args()
    result = build_content(args.output, args.version)
    print(json.dumps({"output": result["output"], "version": result["version"],
                      "language_packs": len(result["languages"]),
                      "templates": result["original_templates"],
                      "documents": len(result["documents"]),
                      "paypal_recipient_confirmation_required": True}, ensure_ascii=False))
