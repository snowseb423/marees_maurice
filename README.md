# Marées à Maurice — application web (PWA)

Horaires et hauteurs des marées à l'île Maurice d'après les prédictions officielles de
[Météo Maurice (MMS)](https://metservice.intnet.mu/sun-moon-and-tides-tides-mauritius.php),
avec le lever et le coucher du [soleil](https://metservice.intnet.mu/sun-moon-and-tides-sunrise-sunset-mauritius.php)
et de la [lune](https://metservice.intnet.mu/sun-moon-and-tides-moonrise-moonset-mauritius.php), et les
[phases de la Lune](https://metservice.intnet.mu/sun-moon-and-tides-moon-phase.php).
L'application s'installe sur l'écran d'accueil, fonctionne hors ligne et se met à jour seule.

En temps réel : marée montante ou descendante et hauteur estimée ; temps écoulé depuis le lever et
temps restant avant le coucher du soleil et de la lune ; pourcentage de la Lune éclairée ; temps
écoulé depuis la dernière nouvelle lune et la dernière pleine lune, et temps restant avant les prochaines.

## Contenu

| Fichier | Rôle |
|---|---|
| `index.html` | L'application (marée actuelle, courbe du jour, soleil, lune, phase, tableau mensuel) |
| `data/tides.json` | Les prédictions de marées, mises à jour automatiquement |
| `data/sun_moon.json` | Lever et coucher du soleil et de la lune, heures des phases, mis à jour automatiquement |
| `sw.js` | Service worker : hors ligne + récupération des nouvelles données |
| `manifest.webmanifest`, `icons/` | Installation sur l'écran d'accueil |
| `scripts/update_tides.py` | Lit la page des marées de Météo Maurice et met à jour `data/tides.json` |
| `scripts/update_sun_moon.py` | Lit les pages soleil, lune et phases et met à jour `data/sun_moon.json` |
| `.github/workflows/update-tides.yml` | Lance les deux scripts le 1er de chaque mois |

## Installer sur le téléphone

- **iPhone (Safari)** : ouvrir l'adresse → bouton Partager → *Sur l'écran d'accueil*.
- **Android (Chrome)** : ouvrir l'adresse → menu ⋮ → *Installer l'application*.

## Comment se fait la mise à jour

- Le **1er de chaque mois à 7 h (heure de Maurice)**, GitHub Actions lit les pages de Météo Maurice
  (marées, soleil, lune, phases), extrait les tableaux et les ajoute à `data/tides.json` et
  `data/sun_moon.json` (12 mois d'historique conservés). Les valeurs lues sont contrôlées (jours complets,
  heures plausibles, suite des phases) : une page mal lue ne remplace jamais des données correctes.
- GitHub Pages republie le site ; à la prochaine ouverture, l'application télécharge les nouvelles
  données (et les garde en cache pour le mode hors ligne).
- Météo Maurice publie par période de deux mois. Si la nouvelle période n'est pas encore en ligne le 1er,
  l'application affiche un bandeau ; vous pouvez relancer la mise à jour à la main via
  **Actions → Run workflow**, ou ajouter une seconde date dans le fichier du workflow
  (ex. `cron: "0 3 1,15 * *"` pour le 1er et le 15).
- Si une page de Météo Maurice change de format, le workflow échoue (GitHub vous envoie un e-mail)
  et les données existantes restent intactes. Pour le soleil et la lune, le journal de l'étape affiche
  les tableaux lus, ce qui aide à adapter le script.

## Mettre à jour à la main (optionnel)

```bash
python3 scripts/update_tides.py            # lit la page en ligne
python3 scripts/update_tides.py page.html  # ou une copie enregistrée de la page
python3 scripts/update_sun_moon.py         # soleil, lune et phases (en ligne)
python3 scripts/update_sun_moon.py --sun soleil.html --moon lune.html --phases phases.html  # copies enregistrées
```

Les hauteurs sont en centimètres au-dessus du zéro hydrographique, heures locales (UTC+4).
Le pourcentage de Lune éclairée est estimé par l'application à partir des heures des phases
(interpolation, à environ 2 % près).
