# Marées à Maurice — application web (PWA)

Horaires et hauteurs des marées à l'île Maurice d'après les prédictions officielles de
[Météo Maurice (MMS)](https://metservice.intnet.mu/sun-moon-and-tides-tides-mauritius.php).
L'application s'installe sur l'écran d'accueil, fonctionne hors ligne et se met à jour seule.

## Contenu

| Fichier | Rôle |
|---|---|
| `index.html` | L'application (état actuel, courbe du jour, tableau mensuel) |
| `data/tides.json` | Les prédictions, mises à jour automatiquement |
| `sw.js` | Service worker : hors ligne + récupération des nouvelles données |
| `manifest.webmanifest`, `icons/` | Installation sur l'écran d'accueil |
| `scripts/update_tides.py` | Lit la page de Météo Maurice et met à jour `data/tides.json` |
| `.github/workflows/update-tides.yml` | Lance le script le 1er de chaque mois |

## Installer sur le téléphone

- **iPhone (Safari)** : ouvrir l'adresse → bouton Partager → *Sur l'écran d'accueil*.
- **Android (Chrome)** : ouvrir l'adresse → menu ⋮ → *Installer l'application*.

## Comment se fait la mise à jour

- Le **1er de chaque mois à 7 h (heure de Maurice)**, GitHub Actions lit la page de Météo Maurice,
  extrait les tableaux et les ajoute à `data/tides.json` (12 mois d'historique conservés).
- GitHub Pages republie le site ; à la prochaine ouverture, l'application télécharge les nouvelles
  données (et les garde en cache pour le mode hors ligne).
- Météo Maurice publie par période de deux mois. Si la nouvelle période n'est pas encore en ligne le 1er,
  l'application affiche un bandeau ; vous pouvez relancer la mise à jour à la main via
  **Actions → Run workflow**, ou ajouter une seconde date dans le fichier du workflow
  (ex. `cron: "0 3 1,15 * *"` pour le 1er et le 15).
- Si la page de Météo Maurice change de format, le workflow échoue (GitHub vous envoie un e-mail)
  et les données existantes restent intactes.

## Mettre à jour à la main (optionnel)

```bash
python3 scripts/update_tides.py            # lit la page en ligne
python3 scripts/update_tides.py page.html  # ou une copie enregistrée de la page
```

Les hauteurs sont en centimètres au-dessus du zéro hydrographique, heures locales (UTC+4).
