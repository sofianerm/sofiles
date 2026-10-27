# Sofiles

Personnalisation et nouveaux outils par **Sofiane Messaoudi**. Contact : [so.messaoudi@gmail.com](mailto:so.messaoudi@gmail.com).

Cette version ajoute un gestionnaire de langue français/anglais/allemand, une aide locale traduite, un installateur par utilisateur et un client de mise à jour avec contrôle de signature. Le don PayPal est facultatif, avec un montant proposé de 20 CHF. L’adresse destinataire doit être confirmée sur le compte PayPal ; aucun paiement n’est effectué par ces outils.

Le moteur historique est Clover 3.0.406, © EJIE Technology, avec des composants Chromium et tiers. **Ce dépôt ne contient aucun de leurs binaires.** Les modifications ne transfèrent pas la propriété du moteur. La licence accompagnant l’archive historique interdit sa redistribution modifiée. L’édition binaire est une copie personnelle locale ; aucune version téléchargeable n’est publiée ici.

## Utilisation de la copie locale

- `builds/Sofiles-1.1.0/SofilesSettings.exe` : langue, aide, contact et mises à jour.
- `SofilesSettings.exe --launch` : applique la langue et lance le moteur.
- `dist/Sofiles-Setup-1.1.0.exe` : installateur local, pour le compte Windows courant.

Fermer Sofiles avec son menu **Quitter** avant de changer de langue ou d’installer une version. Les dossiers et dialogues appartenant à Windows suivent la langue de Windows. Les quelques messages natifs hors des packs de langue restent en français. La configuration essayée utilise l’Explorateur classique ; l’interface moderne de Windows 11 n’est pas validée.

## Construction sous Windows

Prérequis : Python 3 avec Pillow et pefile, et le compilateur C# .NET Framework 4.x présent sous Windows. Les nouveaux outils ciblent .NET Framework 4.8. Les binaires d’origine doivent être fournis localement dans `analysis/extracted` ; leurs empreintes sont vérifiées avant construction. Les inventaires de modifications sont conservés pour rendre les changements contrôlables.

```powershell
python -m pip install Pillow pefile
python tools/build_sofiles_product.py
python tools/test_sofiles_product.py
```

La construction crée une copie séparée et un setup. Elle n’installe pas le programme, n’enregistre pas de DLL et ne change pas le mode de l’Explorateur. Les réglages sont stockés séparément des fichiers installés. La désinstallation conserve le profil et les favoris.

## Mises à jour

Le client est écrit ; **le canal en ligne reste désactivé**. La création d’un dépôt privé ne rend pas ses fichiers accessibles aux utilisateurs anonymes de l’application. Aucun jeton GitHub n’est embarqué dans Sofiles.

Voir [la procédure de publication](docs/UPDATES.md). Une version publiée doit fournir un setup et un manifeste signé décrivant sa version, son URL HTTPS, sa taille, son empreinte SHA-256 et ses changements dans les trois langues. Le client propose le téléchargement, vérifie les octets et demande à l’utilisateur avant d’ouvrir l’installateur.

Le client de mise à jour ne corrige pas les vulnérabilités de l’ancien moteur. La signature RSA du manifeste ne constitue pas une signature Authenticode de l’exécutable Windows. Les essais de signature et de paquets ne constituent pas un audit complet de sécurité.

## Fichiers

- `src/sofiles/` : nouveaux outils C# de réglages, installation, désinstallation et mises à jour.
- `tools/build_sofiles_product.py` : construction locale.
- `tools/sofiles_product_content.py` : ressources et documents FR/EN/DE.
- `config/product.json` : identité et configuration du canal ; clé publique uniquement.
- `tools/new_sofiles_signing_key.ps1` et `tools/sign_sofiles_release.ps1` : préparation des versions signées.

© 2026 Sofiane Messaoudi pour les nouveaux outils et modifications. Les droits des composants tiers restent applicables. Aucune licence de redistribution du moteur historique n’est accordée par ce dépôt.
