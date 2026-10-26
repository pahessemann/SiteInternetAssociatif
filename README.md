# Vert-Tige

Base de travail pour le site de l'association de jardin partage Vert-Tige, a Paris 14.

## Ce que contient cette version

- un serveur Python simple, sans dependances web externes ;
- une base SQLite locale dans `data/vert_tige.sqlite3` ;
- une page d'accueil administrable ;
- un logo de site modifiable depuis l'administration ;
- une image de page d'accueil modifiable depuis l'administration ;
- des liens Facebook et Instagram configurables avec icones dans le bandeau bas ;
- un calendrier avec creation, modification et suppression d'evenements, horaires et adresse ;
- une banque de photos avec albums, ajout d'images et choix de visibilite : galerie, articles ou les deux ;
- un formulaire de contact qui enregistre les messages en base ;
- un editeur d'articles avec image de couverture depuis la banque de photos ou par envoi direct ;
- un outil de format et recadrage d'image pour les articles ;
- un calendrier de l'Avent annuel qui revele progressivement une image, avec 24 contenus personnalisables ;
- des comptes administrateurs nominatifs avec un role referent ;
- une page mentions legales configurable ;
- une preparation Google Ads avec tag et conversion contact configurables ;
- une interface publique moderne et responsive.

## Lancement

Avec Python 3.11 ou plus :

```powershell
python app.py
```

Sur Windows, tu peux aussi double-cliquer sur :

```text
lancer_serveur_windows.bat
```

Le fichier ouvre le site dans le navigateur et garde une fenetre de terminal ouverte pour le serveur.

Si `make` est disponible :

```powershell
make run
```

Le site demarre par defaut sur :

```text
http://127.0.0.1:8000
```

Si la commande `python` n'est pas disponible sous Windows, installe Python depuis python.org ou lance le fichier avec le chemin complet de ton installation Python.

## Administration

Adresse :

```text
http://127.0.0.1:8000/admin
```

Compte referent local de depart :

```text
identifiant : admin
mot de passe : jardin
```

Le compte `admin` est le compte referent : il peut creer et gerer les autres comptes administrateurs depuis l'onglet `Comptes`.

Les comptes administrateurs peuvent modifier les contenus du site. Le compte referent peut aussi gerer les roles, desactiver des comptes et reinitialiser les mots de passe.

### Module Noel

Le menu `Administration > Noel` permet de gerer le calendrier de l'Avent sans
modifier le code :

- creer une edition pour une nouvelle annee ou dupliquer une edition precedente ;
- choisir le titre, l'introduction, la couleur, l'image mystere et l'une des 12 dispositions de puzzle ;
- afficher les 24 numeros dans un ordre melange, stable pour chaque edition ;
- decouper automatiquement l'image mystere en 24 vraies pieces imbriquees, avec un gabarit numerote visible et telechargeable dans l'administration ;
- publier ou conserver l'edition en brouillon et choisir sa presence dans le menu ;
- modifier, illustrer ou masquer chacune des 24 cases ;
- classer les contenus (recette, jardinage, nature, atelier, ecogeste, histoire ou surprise) ;
- personnaliser le message de felicitation du 24 decembre et, si besoin, les modalites ou le lien d'un cadeau de l'association ;
- simuler n'importe quelle date ou deverrouiller les 24 cases pour un test complet avant publication.

Le bouton `Mode d'emploi` ouvre le tutoriel integre a l'administration :
`/admin/noel/guide`. Il explique les six etapes de preparation et propose une
FAQ sur la visibilite, les cases bloquees, les cookies et le message final.
Il est accessible depuis la liste des editions, leurs reglages et chaque case.

Une seule nouvelle case publique se deverrouille chaque jour du 1er au 24
decembre. Les cases deja ouvertes restent consultables et, a partir du 25,
les 24 cases sont disponibles pour rattraper les jours oublies. Le lien et la
page publique restent disponibles jusqu'au 31 decembre inclus. Avec le
consentement du visiteur, les cases decouvertes
sont memorisees dans un cookie client ; supprimer les cookies efface cette
progression. Les editions publiees des annees precedentes restent consultables
depuis les archives du module en decembre. Une edition dupliquee est toujours
creee en brouillon afin d'eviter une publication accidentelle.

Avant une mise en ligne publique, definir au minimum :

```powershell
$env:VERT_TIGE_ADMIN_PASSWORD="un-mot-de-passe-solide"
$env:VERT_TIGE_SECRET="une-longue-valeur-aleatoire"
python app.py
```

## Photos en reserve

Dans `Administration > Photos`, la visibilite `Bibliotheque uniquement` permet
de conserver des images dans la bibliotheque commune aux administrateurs.
Ce choix est disponible a l'import et sur les photos deja ajoutees.

Ces photos ne sont pas listees dans la galerie publique, l'apercu de l'accueil
ou la recherche. Les albums sans photo publique ne sont pas proposes dans la
galerie ni dans le sitemap. Pour afficher une photo dans la galerie, choisir
`Galerie uniquement` ou `Galerie + articles`, puis cliquer sur `Changer`.

Les images en reserve restent disponibles dans les selecteurs des articles,
des evenements et de l'accueil. Les utiliser dans un contenu publie les rend
visibles dans ce contenu, sans les ajouter automatiquement a la galerie.
Ce statut controle l'affichage : il ne protege pas l'acces direct au fichier
via son URL et ne constitue donc pas un stockage confidentiel.

## Envoi d'emails

Le formulaire de contact enregistre toujours les messages dans l'administration.

Pour configurer l'envoi par email, ouvrir `Administration > Messages`, puis
renseigner la section `Configuration de la messagerie`.

Pour l'envoi d'email, activer l'envoi depuis le formulaire de contact, puis
renseigner :

- l'adresse destinataire ;
- l'adresse expediteur ;
- le serveur SMTP ;
- le port SMTP ;
- le mode de securite, generalement `STARTTLS (port 587)` ou `SSL/TLS (port 465)` ;
- l'identifiant et le mot de passe SMTP.

Sur un serveur, ces variables peuvent aussi etre utilisees en priorite sur les
reglages saisis dans l'administration :

```powershell
$env:VERT_TIGE_CONTACT_EMAIL="contact@exemple.fr"
$env:VERT_TIGE_SMTP_HOST="smtp.exemple.fr"
$env:VERT_TIGE_SMTP_PORT="587"
$env:VERT_TIGE_SMTP_SECURITY="starttls"
$env:VERT_TIGE_SMTP_USER="utilisateur"
$env:VERT_TIGE_SMTP_PASSWORD="mot-de-passe"
$env:VERT_TIGE_SMTP_FROM="site@exemple.fr"
python app.py
```

## Deploiement HTTPS avec Docker, Traefik et Let's Encrypt

Prerequis sur le serveur :

- Docker et Docker Compose installes ;
- le nom de domaine pointe vers l'adresse IP publique du serveur ;
- les ports `80` et `443` sont ouverts depuis Internet.

La configuration est separee en deux parties :

- `infra/traefik/docker.compose.yaml` gere Traefik, la redirection `80` vers
  `443`, les certificats Let's Encrypt et leur renouvellement ;
- `docker.compose.yaml` gere le site : un frontend Nginx sur le port interne
  `80` pour `/static/`, et le backend Python derriere lui.

Preparer la configuration :

```bash
cp .env.example .env
```

Modifier ensuite `.env` avec le domaine reel, l'email Let's Encrypt, un mot de
passe administrateur fort et une valeur aleatoire longue pour
`VERT_TIGE_SECRET`.

Exemple pour generer un secret :

```bash
openssl rand -hex 32
```

Demarrer d'abord l'infrastructure HTTPS :

```bash
docker compose --env-file .env -f infra/traefik/docker.compose.yaml up -d
```

Demarrer ensuite le site :

```bash
docker compose --env-file .env -f docker.compose.yaml up -d --build
```

Traefik ecoute sur `80` et `443`, redirige HTTP vers HTTPS, demande
automatiquement un certificat Let's Encrypt pour `DOMAIN`, puis relaie le trafic
HTTPS vers le frontend Nginx. Les certificats sont conserves dans le volume
Docker `traefik-letsencrypt`, separe du volume applicatif.

Commandes utiles :

```bash
docker compose --env-file .env -f infra/traefik/docker.compose.yaml logs -f traefik
docker compose --env-file .env -f docker.compose.yaml logs -f frontend
docker compose --env-file .env -f docker.compose.yaml logs -f backend
docker compose --env-file .env -f docker.compose.yaml ps
```

Les donnees persistantes restent dans :

- `data/` pour la base SQLite ;
- `static/uploads/` pour les images envoyees depuis l'administration.

## Suite

Le diagnostic SEO et la procedure Google Search Console sont disponibles dans
[REFERENCEMENT.md](REFERENCEMENT.md).

- brancher un hebergement et un nom de domaine ;
- ajouter une sauvegarde automatique de la base et des photos ;
- ajouter une journalisation des actions admin ;
- renforcer encore les controles avant production avec CSRF et limitation des tentatives de connexion.
