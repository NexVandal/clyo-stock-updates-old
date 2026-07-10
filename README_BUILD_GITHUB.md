# Compilation et mises à jour GitHub

## Dépôt attendu
Le code et le manifeste public doivent être hébergés dans `NexVandal/clyo-stock-updates-2`, car `app.py` consulte :
`https://raw.githubusercontent.com/NexVandal/clyo-stock-updates-2/main/version.json`.

## Build de test
Dans GitHub : **Actions > Build Windows de test > Run workflow**. Saisir exactement la version contenue dans `app.py`, par exemple `8.3.11`. L'EXE est disponible dans les artefacts et ne modifie pas `version.json`.

## Publication officielle
1. Mettre à jour la version dans `app.py`, `CLYO_Stock_Updater.py`, `CLYO_Stock_Installer.iss`, les scripts et les exemples JSON.
2. Envoyer les changements sur `main`.
3. Créer et pousser un tag identique :

```bash
git tag v8.3.11
git push origin v8.3.11
```

Le workflow compile, valide, crée la Release et actualise `version.json` sur `main`.

## Réglages GitHub
Dans **Settings > Actions > General** :
- autoriser les actions GitHub utilisées ;
- choisir **Read and write permissions** pour le `GITHUB_TOKEN` ;
- autoriser GitHub Actions à créer et approuver les pull requests n'est pas nécessaire ici.

Le dépôt ou, au minimum, les Releases et `version.json` doivent être accessibles sans authentification par les postes clients.

## Règle de version du projet
- version actuelle préparée : `8.3.11` ;
- version suivante imposée : `9.0.0` ;
- `8.3.12` est volontairement refusée par `validate_release.py`.

## Données utilisateurs
L'installateur conserve les données métier placées dans `%ProgramData%\CLYO Stock Atelier`. Les fichiers du programme sont remplacés dans le dossier d'installation, sans supprimer le référentiel ni les documents utilisateurs.

## Correctif PyInstaller

Le script `build_installer_windows.ps1` installe et vérifie explicitement PyInstaller dans l'environnement virtuel `.venv`. Chaque commande externe est contrôlée : le build s'arrête immédiatement si l'installation d'une dépendance échoue.
