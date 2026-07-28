# Test rando et alpinisme - 4 jours

Ce fichier est a selectionner dans le champ `Style .md` de Resolve Timeline
Tool. Il est prevu pour un premier test avec les videos de deux amis partis
quatre jours en randonnee et en alpinisme.

## Reglages lus par l'outil

fps: 25

mots-cles drone: drone, DJI, Mavic, aerial, aerien, FPV

transition drone: 4s

minimum segment: 5s

fenetre beat: 0.45s

defaut clip: 8s

ignorer: proxy, optimized media, cache, export, rendu

## Intention de montage

Le montage doit raconter le voyage dans l'ordre chronologique, en conservant
une separation claire entre les quatre journees.

Chaque journee peut suivre ce rythme :

1. Depart et preparation : sac, chaussures, materiel, carte et meteo.
2. Progression : marche, denivele, passages techniques et efforts.
3. Respiration : paysages, details de la montagne et moments entre amis.
4. Point fort : sommet, crete, passage d'alpinisme ou panorama.
5. Fin de journee : descente, refuge, bivouac ou retour.

Les sequences d'action peuvent etre coupees sur les beats detectes. Les plans
de paysage doivent garder un rythme plus calme. Les plans drone servent de
respiration et de transition entre deux moments, lieux ou journees.

Eviter les plans manifestement rates, les fichiers proxy, les exports deja
montes et les medias de cache.

## Reglage conseille dans la fenetre

Dans `Duree max segment`, saisir `8` secondes. Cela donnera principalement des
segments de 5 a 8 secondes, avec certains cuts ajustes sur un beat proche.

Dans `Duree cible timeline`, saisir `5` minutes pour le premier montage.

Pour un montage plus dynamique, relancer avec `5` ou `6` secondes.
Pour un montage plus contemplatif, relancer avec `10` secondes.

## Procedure du premier test

1. Placer tous les rushs des quatre jours dans un meme dossier source.
2. Conserver les dates originales des fichiers pour separer les journees.
3. Verifier que les noms des plans drone contiennent `DJI`, `drone` ou `Mavic`.
4. Lancer `python3 run.py`.
5. Choisir le dossier de rushs.
6. Choisir ce fichier `STYLE_TEST_RANDO_ALPINISME.md`.
7. Regler la duree maximale sur `8` secondes.
8. Regler la duree cible sur `5` minutes.
9. Cliquer sur `Generer timeline`.
10. Importer en priorite le fichier `.fcpxml` genere dans DaVinci Resolve.
11. Consulter le fichier `_report.md` si un rush est ignore ou mal analyse.

Les fichiers de sortie sont crees par defaut dans le sous-dossier
`_resolve_timeline_exports` du dossier contenant les rushs.
