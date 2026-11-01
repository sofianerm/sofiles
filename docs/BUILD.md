# Compiler Sofiles sous Windows

La construction prépare les nouveaux outils .NET Framework 4.8, les ressources localisées et le programme d’installation NSIS 3.13. Elle utilise des fichiers binaires tiers fournis séparément. Les sources de ces composants ne font pas partie du dépôt.

## Prérequis

- Windows avec le compilateur C# de .NET Framework et .NET Framework 4.8.
- Python 3 avec les paquets Pillow et pefile.
- NSIS 3.13 portable, avec `makensis.exe` à l’emplacement `tools/nsis/nsis-3.13/makensis.exe`.
- Les fichiers d’origine attendus dans `analysis/extracted`, avec leurs ressources, packs de langue et licences.

Les scripts vérifient les empreintes des fichiers d’origine avant de préparer les binaires. Les inventaires nécessaires se trouvent dans `analysis/branding`. Une autre version des fichiers d’entrée nécessite un nouvel inventaire et une revue des modifications.

Depuis la racine du dépôt :

```powershell
python -m pip install Pillow pefile
```

Vérifier la version de NSIS :

```powershell
.\tools\nsis\nsis-3.13\makensis.exe /VERSION
```

Le dossier NSIS portable et les binaires d’entrée restent locaux.

## Construire

La version et la configuration du produit se trouvent dans `config/product.json`. La configuration du client contient une clé publique ; la clé privée de publication reste hors du dépôt.

```powershell
python tools/build_sofiles_product.py
```

Pour la version 1.2.0, les sorties attendues sont :

- `builds/Sofiles-1.2.0/`, le dossier de l’application et ses notices ;
- `dist/Sofiles-Setup-1.2.0.exe`, le programme d’installation ;
- `analysis/product-build/`, les rapports de construction et journaux du compilateur.

Le dossier de l’application contient un fichier `SHA256SUMS.txt`. La construction n’installe pas Sofiles et ne change pas le mode de l’Explorateur Windows.

## Tester

```powershell
python tools/test_sofiles_product.py
```

Les contrôles portent sur les empreintes des fichiers, les modifications des ressources natives et le comportement des nouveaux outils. Les rapports sont écrits dans `analysis/product-build/`.

La version 1.2.0 a passé les 29 contrôles automatisés des nouveaux outils et la vérification des 135 fichiers du paquet. Le véritable setup NSIS a aussi été exécuté dans des dossiers de test avec espaces dans leurs noms : installation, réparation et désinstallation en français, anglais et allemand. Ces essais conservent les préférences et les fichiers inconnus, sans modifier le registre ni le profil réels.

Un essai distinct sur le compte Windows courant a validé l’installation, les empreintes des fichiers, les raccourcis du menu Démarrer et du bureau, l’entrée de désinstallation Windows, la réparation, la désinstallation et la réinstallation. Les préférences ont été conservées. Le démarrage du moteur a été observé avec l’Explorateur classique.

Ces vérifications ne couvrent pas toutes les configurations Windows, les coupures pendant l’installation ni les risques du moteur tiers.

Pour une validation manuelle, utiliser une session de test avec l’Explorateur classique. La configuration testée sous Windows 11 l’active avec SwitchExplorer. Vérifier les réglages et l’installation en français, en anglais et en allemand, puis consigner la version de Windows et le facteur d’échelle utilisés.

Les limites connues comprennent l’Explorateur moderne de Windows 11 non validé, le raccourci Ctrl+T non vérifié dans le moteur natif et quelques messages d’erreur natifs encore en français.

## Préparer une distribution

Conserver les notices et licences des composants tiers avec les fichiers distribués. La licence MIT des nouveaux outils ne s’étend pas au moteur propriétaire ; consulter [licenses/NOTICE.md](../licenses/NOTICE.md).

Les fichiers du moteur, les dossiers `builds/` et `dist/`, les profils utilisateur et les clés privées restent hors de Git. Une préversion de test doit être publiée comme préversion dans GitHub Releases. Les contrôles de signature et d’intégrité des mises à jour sont décrits dans [SECURITY.md](../SECURITY.md).
