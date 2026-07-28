# Resolve Timeline Tool

Petit outil local pour preparer une timeline EDL/FCPXML importable dans DaVinci Resolve.

Situation:
Vous rentrez de voyage avec des heures de rush vidéo (action camera, drone etc).
Il faut maintenant faire les cuts et préparer une vidéos qui met en avant les meilleurs moment du trip.
La motivation n'est pas à son comble devant les heures de travail que celà représente.
Resolve Timeline Tool vient résoudre le problème en préparant une timeline déjà pré-découpée et prête pour votre final touch.

## Apercu

![Apercu de l'interface Resolve Timeline Tool](docs/resolve-timeline-tool.png)

## Lancer

```bash
cd /Users/serverm4/VipeCoding/ResolveTimelineTool
python3 run.py
```

Sur macOS, le lanceur detecte automatiquement le Python systeme incompatible
avec Tkinter et redemarre l'application avec le Python Homebrew installe.
La commande explicite reste disponible :

```bash
/opt/homebrew/bin/python3.12 run.py
```

## Utilisation

1. Choisir le dossier source contenant les rushs.
2. Choisir le fichier `.md` qui decrit le style.
3. Regler la duree maximale d'un segment.
4. Regler la duree cible de la timeline en minutes.
5. Cliquer sur `Generer timeline`.
6. Modifier le `.md` si besoin, puis cliquer sur `Relancer apres modification .md`.

La duree maximale limite chaque plan, mais ne fixe pas la longueur du montage.
La duree cible selectionne des extraits chronologiques repartis entre les
journees pour produire une timeline de la longueur demandee.

Le traitement cree trois fichiers dans `_resolve_timeline_exports` ou le dossier choisi :

- `.edl` pour un import EDL simple.
- `.fcpxml` pour un import XML/FCPXML dans Resolve.
- `_report.md` avec le decoupage par jour, les roles et les avertissements.

## Notes sur le fichier style

Le style peut rester en langage naturel. Le parser reconnait aussi quelques lignes pratiques :

```md
fps: 25
mots-cles drone: drone, DJI, Mavic, aerial
transition drone: 3s
minimum segment: 2s
fenetre beat: 0.35s
```

Pour des durees exactes et la synchronisation approximative sur les beats, installer FFmpeg (`ffprobe` et `ffmpeg`) dans le `PATH`. Sans FFmpeg, l'outil reste utilisable mais il applique une duree par defaut aux clips dont la duree ne peut pas etre lue.
