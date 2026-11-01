# Contribuer à Sofiles

Les contributions portent sur les nouveaux outils C#, les scripts de construction, les traductions et la documentation. Le moteur binaire tiers conserve ses propres conditions de licence.

## Signaler un problème

Ouvrir une [issue](https://github.com/sofianerm/sofiles/issues) avec :

- la version de Sofiles et la version de Windows ;
- le mode de l’Explorateur, classique ou moderne ;
- la langue choisie ;
- les étapes pour reproduire le problème, le résultat attendu et le résultat obtenu ;
- le texte exact du message d’erreur ou sa référence de diagnostic.

Masquer les noms de fichiers personnels et les autres informations privées dans les captures et les journaux. Les vulnérabilités se signalent par courriel selon [SECURITY.md](SECURITY.md).

Pour une modification qui change le fonctionnement de l’application, décrire d’abord le besoin dans une issue. Une correction ciblée peut être proposée directement dans une pull request.

## Préparer une modification

Suivre [docs/BUILD.md](docs/BUILD.md) pour les dépendances et les fichiers d’origine nécessaires à une construction locale.

Garder chaque contribution centrée sur un problème. Expliquer dans la pull request ce qui change, comment le reproduire et les vérifications effectuées. Les changements de texte doivent rester cohérents entre les versions française, anglaise et allemande.

Après une modification du code ou de la construction, lancer depuis la racine du dépôt :

```powershell
python tools/build_sofiles_product.py
python tools/test_sofiles_product.py
```

Pour une modification de l’interface, vérifier les trois langues et joindre une capture de la surface concernée. Signaler les essais manuels restants, notamment les facteurs d’échelle Windows ou les modes de l’Explorateur qui n’ont pas été testés.

## Fichiers à conserver hors du dépôt

Les binaires du moteur, les distributions produites, les profils utilisateur et les clés privées de signature restent hors des commits. Une contribution ne doit contenir aucun identifiant d’accès ni secret. La configuration publique peut contenir la clé publique nécessaire à la vérification des mises à jour.

Les nouveaux outils et scripts sont sous licence MIT. En proposant du code original pour ces outils, le contributeur accepte sa distribution sous cette licence. Les dépendances tierces gardent leurs licences et doivent être accompagnées de leurs notices.
