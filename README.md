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

Avant une mise en ligne publique, definir au minimum :

```powershell
$env:VERT_TIGE_ADMIN_PASSWORD="un-mot-de-passe-solide"
$env:VERT_TIGE_SECRET="une-longue-valeur-aleatoire"
python app.py
```

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

## Suite

- brancher un hebergement et un nom de domaine ;
- ajouter une sauvegarde automatique de la base et des photos ;
- ajouter une journalisation des actions admin ;
- renforcer encore les controles avant production avec CSRF et limitation des tentatives de connexion.
