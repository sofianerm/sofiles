# Publier une mise à jour Sofiles

Le dépôt de travail est privé. Il sauvegarde les nouveaux outils ; il n’est pas encore un canal de téléchargement pour l’application. Les binaires Clover modifiés restent locaux compte tenu de la licence fournie et des problèmes de sécurité encore ouverts.

## Ce que l’utilisateur verra

Dans les réglages, l’utilisateur peut demander une vérification et, une fois un canal publié, activer une vérification au lancement, au maximum une fois par jour. Une nouvelle version affiche son numéro et ses changements. L’utilisateur accepte le téléchargement puis l’ouverture de l’installateur. Le setup lui demande de fermer Sofiles. L’installation ajoute un nouveau dossier de version et conserve le précédent.

La langue, les favoris et le profil sont conservés. Les erreurs de réseau ne forcent pas de mise à jour et ne téléchargent pas un programme alternatif. Les mises à jour antérieures ou égales sont ignorées.

## Hébergement

Un hébergement HTTPS statique suffit. GitHub Releases peut héberger des fichiers joints ; un serveur exécutant une API n’est pas obligatoire. Pour une application accessible à tous, les fichiers doivent être téléchargeables sans secret embarqué dans le client. Un dépôt privé exige une authentification et ne répond pas à cette contrainte.

Lorsque la distribution des binaires sera autorisée et la version prête à être diffusée, choisir un emplacement public pour :

- `updates.xml` ;
- `updates.xml.sig`, signature détachée du manifeste ;
- `Sofiles-Setup-X.Y.Z.exe`, fichier de version immuable.

GitHub documente les [liens directs vers les fichiers d’une release](https://github.com/github/docs/blob/main/content/repositories/releasing-projects-on-github/linking-to-releases.md).

## Clés et configuration initiale

La clé publique est compilée dans le client. La clé privée ne doit jamais être ajoutée au dépôt, à une release ou au setup. Le dossier `.private/` est exclu de Git. La clé actuelle est protégée avec DPAPI pour le compte Windows qui l’a créée : sauvegarder de manière sûre sa capacité de signature avant toute publication ; la simple copie du fichier chiffré ne garantit pas sa récupération sur un autre PC.

Si aucune clé n’existe encore :

```powershell
.\tools\new_sofiles_signing_key.ps1
```

Renseigner ensuite `manifest_url` et `releases_url` dans `config/product.json`. La clé publique du même fichier doit correspondre à la clé privée de signature. Reconstruire le client initial après cette configuration : une application déjà distribuée avec un canal vide ne découvrira pas spontanément une nouvelle adresse.

Une rotation de clé nécessite un plan de migration et une version du client qui connaît la nouvelle clé. Ne pas régénérer une clé pour une simple montée de version.

## Chaque nouvelle version

1. Monter `version` dans `config/product.json` : correctif `1.1.1`, nouvelle fonction compatible `1.2.0`, changement incompatible `2.0.0`.
2. Mettre à jour les notes FR/EN/DE dans un fichier JSON ayant les propriétés `fr`, `en`, `de`.
3. Construire et tester le setup localement. Ne pas écraser un fichier de release déjà publié.
4. Signer le manifeste avec l’URL définitive du setup :

```powershell
.\tools\sign_sofiles_release.ps1 `
  -Setup .\dist\Sofiles-Setup-1.2.0.exe `
  -DownloadUrl 'https://HEBERGEMENT-A-CHOISIR/Sofiles-Setup-1.2.0.exe' `
  -NotesJson .\release-notes\1.2.0.json `
  -Output .\dist\1.2.0\updates.xml
```

L’URL ci-dessus est un exemple à remplacer, pas un service existant.

5. Téléverser d’abord le setup, puis `updates.xml.sig` et enfin `updates.xml`. Les fichiers sont vérifiés ensemble : une publication momentanément incohérente produit une erreur de vérification, jamais une installation sans signature.
6. Depuis la version précédente, vérifier la notification, les notes, le téléchargement, le refus d’un fichier modifié et l’installation après fermeture du moteur.

## Contrôles et limites

Le manifeste est signé avec RSA de 3072 bits ou plus et SHA-256, sur ses octets exacts. Le XML refuse les DTD. La vérification exige le produit Sofiles, le canal stable et une version supérieure. Le téléchargement accepte HTTPS uniquement, y compris les redirections, avec des limites de temps et de taille. L’empreinte et la taille du setup sont vérifiées, puis revérifiées sous verrou immédiatement avant exécution.

Le setup s’exécute sans élévation et déploie dans `%LOCALAPPDATA%\Programs\Sofiles`. Une exclusion par mutex protège les transitions effectuées par les nouveaux outils. Un lancement direct de l’ancien moteur peut contourner ce mécanisme ; les courses entre processus malveillants du même compte ne sont pas entièrement éliminées par des contrôles de chemin en espace utilisateur.

La compensation traite les erreurs remontées pendant l’installation. Une coupure de courant à une étape précise n’équivaut pas à une exception gérée ; la résistance à toutes les coupures n’est pas validée. Le retour à une ancienne version reste manuel par son gestionnaire conservé : aucun bouton de restauration automatique n’est promis.
