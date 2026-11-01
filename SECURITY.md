# Sécurité de Sofiles

Sofiles 1.2.0 est une préversion publique de test. Le moteur historique est ancien et son examen de sécurité reste à compléter. Les contrôles des nouveaux outils ne constituent pas un audit du moteur ni une garantie de sécurité de l’ensemble de l’application.

## Signaler une vulnérabilité

Envoyer les signalements à [so.messaoudi@gmail.com](mailto:so.messaoudi@gmail.com) avec l’objet `Sofiles security`.

Inclure la version de Sofiles, la version de Windows, les étapes de reproduction et l’impact observé. Joindre le message d’erreur ou les journaux utiles après avoir retiré les données personnelles et les secrets. Préciser si le problème concerne les réglages, l’installation, les mises à jour ou le moteur natif.

Garder les détails d’exploitation dans ce signalement privé pendant l’analyse. Les bugs sans conséquence de sécurité peuvent être signalés dans les [issues publiques](https://github.com/sofianerm/sofiles/issues).

## Mises à jour et fichiers téléchargés

Le client de mise à jour vérifie un manifeste signé et l’empreinte SHA-256 du programme d’installation. Ces contrôles servent à vérifier l’origine et l’intégrité du téléchargement. Ils ne corrigent pas les vulnérabilités du moteur tiers.

La signature du manifeste est distincte d’une signature Authenticode de l’exécutable Windows. La clé privée de publication reste hors du dépôt et des fichiers distribués ; seule la clé publique appartient à la configuration du client.

Utiliser les fichiers de la [page de préversion officielle](https://github.com/sofianerm/sofiles/releases/tag/v1.2.0) et conserver les notices des composants livrés avec l’application.

## Périmètre de validation

La configuration testée sous Windows 11 utilise l’Explorateur classique activé avec SwitchExplorer. Le fonctionnement avec l’Explorateur moderne n’est pas validé. Les tests des outils et les essais d’installation, de réparation et de désinstallation sont décrits dans [docs/BUILD.md](docs/BUILD.md).
