# Mises à jour

Le client consulte le manifeste signé `https://raw.githubusercontent.com/sofianerm/sofiles/main/updates/latest.xml`.

La vérification automatique est désactivée par défaut. L’utilisateur peut l’activer dans les réglages ; Sofiles vérifie alors au lancement, au maximum une fois par jour. Une nouvelle version affiche ses changements avant de proposer le téléchargement et l’ouverture du setup.

## Publier une version

1. Modifier la version dans `config/product.json` et les notes FR/EN/DE.
2. Construire avec `python tools/build_sofiles_product.py` et lancer `python tools/test_sofiles_product.py`.
3. Vérifier l’assistant et le démarrage, puis créer une release GitHub en brouillon avec le tag de version.
4. Téléverser le setup avec un nom contenant sa version. Ne pas remplacer les octets d’un fichier déjà publié.
5. Utiliser `tools/sign_sofiles_release.ps1` avec le setup, son URL définitive et le fichier de notes pour créer `updates.xml` et `updates.xml.sig`.
6. Publier la release. Copier le manifeste et sa signature dans `updates/latest.xml` et `updates/latest.xml.sig`, puis pousser le commit.
7. Vérifier les téléchargements sans authentification, leur empreinte et la réponse du client depuis la version précédente.

La première distribution publique est une préversion de test. Le champ de canal du manifeste reste `stable`, l’identifiant vérifié par ce client. Ce nom ne constitue pas une validation de stabilité du moteur.

## Signature et installation

La clé publique est compilée dans le client. La clé privée reste protégée par DPAPI dans `.private/`, hors de Git. Elle ne doit jamais figurer dans une release. Sauvegarder sa capacité de signature avant une migration de PC et ne pas régénérer la clé à chaque version.

Le manifeste utilise RSA de 3072 bits et SHA-256. Le client refuse les DTD et les téléchargements sans HTTPS. Il contrôle la signature, la taille et l’empreinte du setup, puis refait le contrôle sous verrou avant son ouverture. Cette signature est distincte d’Authenticode et ne supprime pas les avertissements Windows liés à l’absence de certificat de publication.

NSIS installe pour le compte courant et inscrit Sofiles dans les applications Windows. Les versions sont rangées sous `versions/`. L’inventaire est écrit avant la copie pour permettre une réparation après interruption. La désinstallation supprime les fichiers de cet inventaire et conserve les fichiers inconnus, les préférences et les favoris.

Les tests automatiques du setup utilisent des dossiers isolés du projet et ne modifient pas le registre ni le profil réels. Un essai distinct a validé l’intégration Windows sur le compte courant. Ces essais ne couvrent pas toutes les configurations ni les interruptions possibles. Voir [SECURITY.md](../SECURITY.md) pour les limites du moteur.
