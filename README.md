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

Pour chaque jour : courbe de marée avec la nuit grisée et les périodes où le soleil et la lune sont levés,
tableau mensuel avec lever et coucher du soleil et phase de la Lune, vives-eaux et mortes-eaux, et un
calendrier lunaire du mois.

## Contenu

| Fichier | Rôle |
|---|---|
| `index.html` | L'application (marée actuelle, courbe du jour, soleil, lune, phase, calendrier lunaire, tableau mensuel) |
| `astro.js` | Calcul astronomique de secours : lever et coucher du soleil et de la lune, phases |
| `data/tides.json` | Les prédictions de marées, mises à jour automatiquement |
| `data/sun_moon.json` | Lever et coucher du soleil et de la lune, heures des phases, mis à jour automatiquement |
| `sw.js` | Service worker : hors ligne + récupération des nouvelles données |
| `manifest.webmanifest`, `icons/` | Installation sur l'écran d'accueil |
| `scripts/update_tides.py` | Lit la page des marées de Météo Maurice et met à jour `data/tides.json` |
| `scripts/update_sun_moon.py` | Lit les pages soleil, lune et phases et met à jour `data/sun_moon.json` |
| `.github/workflows/update-tides.yml` | Lance les deux scripts le 1er et le 15 de chaque mois |

## Installer sur le téléphone

- **iPhone (Safari)** : ouvrir l'adresse → bouton Partager → *Sur l'écran d'accueil*.
- **Android (Chrome)** : ouvrir l'adresse → menu ⋮ → *Installer l'application*.

## Comment se fait la mise à jour

- Le **1er et le 15 de chaque mois à 7 h (heure de Maurice)**, GitHub Actions lit les pages de Météo Maurice
  (marées, soleil, lune, phases), extrait les tableaux et les ajoute à `data/tides.json` et
  `data/sun_moon.json` (12 mois d'historique conservés). Les valeurs lues sont contrôlées (jours complets,
  heures plausibles, suite des phases) : une page mal lue ne remplace jamais des données correctes.
- GitHub Pages republie le site ; à la prochaine ouverture, l'application télécharge les nouvelles
  données (et les garde en cache pour le mode hors ligne).
- Météo Maurice publie par période de deux mois. Si la nouvelle période n'est pas encore en ligne le 1er,
  le passage du 15 la récupère ; vous pouvez aussi relancer la mise à jour à la main via
  **Actions → Run workflow**. En attendant, l'application affiche un bandeau pour les marées, et calcule
  elle-même le soleil, la lune et les phases (voir ci-dessous).
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

## Calculs faits par l'application

- **Soleil, lune et phases hors de la période publiée** : `astro.js` calcule lever, coucher et phases
  (algorithmes de Meeus et de Montenbruck et Pfleger), avec le point de référence et les arrondis de
  Météo Maurice. Comparé aux 248 valeurs publiées d'octobre et novembre 2026 : phases identiques ; levers et
  couchers à une minute près, sauf un lever de lune (30 novembre) publié à 23:49 que le calcul place à 00:05
  le lendemain. Ces valeurs sont signalées « calculé » ou en italique.
- **Pourcentage de Lune éclairée** : estimé à partir des heures des phases (interpolation, à environ 2 % près).
- **Vives-eaux** : les trois jours consécutifs de plus fort marnage autour de chaque nouvelle et pleine lune
  (de l'avant-veille au surlendemain). **Mortes-eaux** : la veille, le jour et le lendemain de chaque quartier.
