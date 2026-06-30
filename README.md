# Resolve Timeline Tool

Petit outil local pour preparer une timeline EDL/FCPXML importable dans DaVinci Resolve.

## Apercu

![Apercu de l'interface Resolve Timeline Tool](docs/resolve-timeline-tool.png)

## Lancer

```bash
cd /Users/serverm4/VipeCoding/ResolveTimelineTool
python3 run.py
```

Sur macOS, si le Python systeme refuse de charger Tkinter, utiliser le Python Homebrew avec Tk :

```bash
/opt/homebrew/bin/python3.12 run.py
```

## Utilisation

1. Choisir le dossier source contenant les rushs.
2. Choisir le fichier `.md` qui decrit le style.
3. Regler la duree maximale des segments.
4. Cliquer sur `Generer timeline`.
5. Modifier le `.md` si besoin, puis cliquer sur `Relancer apres modification .md`.

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
