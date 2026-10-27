# Sofiles 1.1.0

La copie actuelle se lance avec **Sofiles.lnk** dans ce dossier. **Sofiles — réglages.lnk** ouvre le choix de langue FR/EN/DE, l’aide et les mises à jour. Le nouveau setup local est `dist/Sofiles-Setup-1.1.0.exe`.

Le contact est so.messaoudi@gmail.com ; le don PayPal proposé est facultatif, de 20 CHF. Le compte PayPal destinataire reste à confirmer. Les mises à jour signées sont préparées, mais aucun canal public n’est activé. Le dépôt privé de sources est [sofianerm/sofiles](https://github.com/sofianerm/sofiles). Les binaires historiques et la clé privée en sont exclus.

Fermer les autres copies de Sofiles avec leur menu **Quitter**, puis lancer cette version pour appliquer ses ressources et sa langue. Le setup a été compilé et son contenu extrait/vérifié ; l’installation et la désinstallation complètes sur ce PC ne sont pas validées. Les rares erreurs natives hors PAK restent en français. Les limites de sécurité de l’ancien moteur restent celles de l’audit.

Voir [le mode d’emploi actuel](README.md) et [la publication des mises à jour](docs/UPDATES.md).

## Historique de la version 1.0.0

Édition personnelle de **Sofiane Messaoudi**, créée le 25 octobre 2026.

Lancer [Sofiles.exe](builds/Sofiles-1.0.0/Sofiles.exe), ou utiliser [Sofiles.lnk](Sofiles.lnk) dans ce dossier. Conserver le lanceur, les DLL et les fichiers de langue ensemble.

## Identité de cette édition

Le nom, l’icône, les propriétés Windows, la version, les textes de l’interface et les erreurs d’application identifiées sont personnalisés. Le logo et les crédits ont été contrôlés dans la fenêtre À propos. Le lanceur réel s’appelle Sofiles.exe ; les composants portent également le nom Sofiles.

Les crédits indiquent « © 2026 Sofiane Messaoudi » pour les modifications de personnalisation. La base est Clover 3.0.406, créé par EJIE Technology, avec des composants Chromium et tiers. Leurs droits et mentions restent reconnus. [Crédits détaillés](builds/Sofiles-1.0.0/CREDITS.md) et [licence d’origine](builds/Sofiles-1.0.0/licenses/Clover-original.txt).

## Versions

- `1.0.0` : première édition Sofiles avec son identité complète.
- `1.0.1`, `1.0.2`… : corrections de cette édition.
- `1.1.0`, `1.2.0`… : nouvelles fonctions compatibles.
- `2.0.0` : évolution majeure entraînant des incompatibilités.

La version de fichier Windows comporte un quatrième nombre : `1.0.0.0`. Aucun service automatique de mise à jour Sofiles n’est configuré.

## Vérifications et limites

Le 25 octobre 2026, le programme a démarré avec l’Explorateur classique activé par l’utilisateur avec SwitchExplorer. La fenêtre À propos affichait Sofiles, 1.0.0, le nouveau logo et Sofiane Messaoudi ; le lien Crédits ouvrait la notice locale. La création et la fermeture d’un onglet par les boutons ont été observées.

Les quatre PE ont été reparsés et leurs changements natifs comparés aux seules références de texte et longueurs prévues. Les relocalisations, exports et protections DEP/ASLR existantes sont conservés. Les fichiers d’origine restent inchangés.

Les branches d’erreur ne sont pas toutes exécutées. Le message chinois d’intégration est remplacé en français à son point d’appel vérifié statiquement. Les messages de Windows ou d’un logiciel tiers ne sont pas remplacés. Les symboles techniques et les traces de compilation d’origine ne constituent pas des libellés d’interface et restent préservés.

La compatibilité avec l’Explorateur moderne de Windows 11 n’est pas validée. Le raccourci Ctrl+T n’a pas créé d’onglet lors de l’automatisation ; sa vérification reste distincte du contrôle des boutons. Les corrections de sécurité de la base restent à traiter selon [l’audit](AUDIT_VULNERABILITES.md).

Les liens locaux d’aide et de crédits sont générés pour l’emplacement de cette copie. Une copie déplacée doit être régénérée pour ces liens. Aucun installateur historique n’est inclus et la construction ne modifie pas la configuration de Windows.

## Sources de construction

- [Constructeur](tools/build_sofiles_full.py)
- [Icône éditable SVG](assets/sofiles/sofiles.svg)
- [Générateur d’icône](tools/create_sofiles_icon.py)
- [Vérification des fichiers natifs](tools/verify_sofiles_full.py)
- [Rapport de construction](analysis/branding/full-build/build-report.json)
- [Contrôles statiques](analysis/branding/full-build/static-verification.json)
