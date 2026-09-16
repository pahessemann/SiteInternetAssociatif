# Referencement de Jardin Vert-Tige

## Diagnostic du site public le 16 septembre 2026

Les verifications ont porte sur https://jardin-vert-tige.fr et le code local.
Elles ne remplacent pas les informations privees de Google Search Console.

- Accueil, programmation, articles, galerie, infos pratiques et contact : HTTP 200.
- `/robots.txt` autorise l'exploration publique et indique le bon sitemap.
- `/sitemap.xml` repond en XML et contient 10 URL sur le domaine HTTPS attendu.
- Les pages publiques examinees ont un titre, une description et une URL canonique correcte.
- Aucun `noindex` ni en-tete `X-Robots-Tag` bloquant sur ces pages publiques.
- Le contenu est present dans le HTML sans execution de JavaScript.
- HTTP redirige deja vers HTTPS.
- L'image principale pese environ 948 Ko et l'affiche de l'evenement 993 Ko.
  Une optimisation des images pourra ameliorer le chargement sur telephone ;
  ces seuls poids ne permettent pas de conclure sur les Core Web Vitals.
- Aucun resultat du domaine dans les recherches effectuees pendant l'audit.
  Ce constat ne prouve pas une absence totale de l'index Google.
- Search Console n'a pas encore ete configuree, selon le proprietaire.

Points corriges dans le code local, a deployer :

- Un article inexistant ou non publie renvoyait une page d'erreur avec HTTP 200.
  Il renvoie maintenant HTTP 404.
- `www.jardin-vert-tige.fr` servait un doublon du site. Nginx le redirige maintenant
  en 301 vers `https://jardin-vert-tige.fr`, en conservant le chemin et les parametres.
  La balise canonique indiquait deja ce domaine ; cette correction renforce sa coherence.
- Les donnees structurees publiaient l'adresse fictive `contact@vert-tige.local`.
  Les adresses locales et invalides sont maintenant omises de ces donnees.

Ces defauts ne permettent pas, a eux seuls, d'expliquer le classement du site.

## Activer Google Search Console

### Validation du domaine par DNS (methode choisie)

L'ecran "Valider la propriete du domaine via l'enregistrement DNS" concerne
une propriete **Domaine**. Cette validation se fait chez le gestionnaire DNS,
pas dans le code Python ni dans l'administration du site.

Dans la zone DNS de `jardin-vert-tige.fr`, ajouter un enregistrement :

| Champ | Valeur |
| --- | --- |
| Type | `TXT` |
| Nom / sous-domaine | `@`, ou vide selon le fournisseur (racine du domaine) |
| Valeur / contenu | La ligne complete `google-site-verification=...` fournie par Google |
| TTL | Valeur par defaut |

Conserver exactement les caracteres du code. Si le copier-coller contient
des antislashs avant les underscores (`\_`), enlever les antislashs et garder
les underscores (`_`). Ajouter ce TXT sans supprimer les enregistrements existants.

Enregistrer, puis revenir dans Search Console et cliquer sur **Valider**.
La propagation DNS peut prendre du temps : si Google ne trouve pas encore le
TXT, reessayer plus tard. Conserver cet enregistrement apres la validation.

Un `git pull`, une reconstruction Docker ou un champ HTML ne peuvent pas
remplacer cet ajout DNS. Le code de validation DNS n'est pas integre au site.

Une fois la propriete validee, ouvrir **Sitemaps** et envoyer
`https://jardin-vert-tige.fr/sitemap.xml`. Inspecter ensuite l'accueil avec
**Inspection de l'URL**, tester l'URL active puis demander son indexation.

### Alternative : validation d'un prefixe d'URL par balise HTML

Cette methode est utile sans acces au DNS. Elle valide une autre propriete,
de type prefixe d'URL, et ne valide pas l'ecran de propriete Domaine ci-dessus.

1. Ouvrir https://search.google.com/search-console avec le compte Google qui
   restera responsable du site.
2. Ajouter une propriete de type **Prefixe de l'URL**, exactement
   `https://jardin-vert-tige.fr/`.
3. Choisir la methode **Balise HTML**. Google fournit une balise de la forme
   `<meta name="google-site-verification" content="CODE_FOURNI_PAR_GOOGLE">`.
4. Dans l'administration **du site en ligne**, ouvrir **Accueil > Referencement / legal**.
   Coller seulement la valeur de `content` dans **Validation Google Search Console (balise HTML)**,
   puis enregistrer. Ne pas coller la balise HTML complete.
5. Revenir dans Search Console et cliquer sur **Valider**. Conserver ce code
   dans l'administration apres validation.
6. Ouvrir **Sitemaps**, envoyer `sitemap.xml` et verifier que Google peut le lire.
7. Dans **Inspection de l'URL**, inspecter `https://jardin-vert-tige.fr/`, lancer
   le test de l'URL active et demander son indexation si elle est autorisee.
   Faire de meme pour `/infos-pratiques` et les articles importants.
8. Consulter ensuite **Indexation > Pages** pour les motifs d'exclusion et
   **Performances** pour les recherches, impressions et clics.

La propriete Domaine validee par DNS couvre aussi HTTP et www. Le prefixe
`https://jardin-vert-tige.fr/` ne couvre que cette variante.

La configuration en base du site public est distincte de la base locale : un
commit Git ne publie pas le code de validation saisi dans l'administration locale.
Search Console est gratuite. Google Ads n'est pas necessaire pour le referencement naturel.
Une demande d'indexation ne garantit ni une presence immediate ni une position.

## Ameliorer la pertinence locale

L'audit public ne trouve qu'un article publie, une courte introduction au jardin.
Completer les contenus avec des informations reelles et utiles : presentation
de l'association, acces rue de Coulmiers a Paris 14, activites et comptes rendus.
Pour les evenements passes, publier un article durable lorsque le sujet le merite.
Les rendez-vous n'ont actuellement pas de page individuelle indexable.

Employer naturellement "jardin partage Vert-Tige a Paris 14" dans les titres
et les textes pertinents, sans repetitions artificielles. Le titre de l'accueil
mentionne deja le jardin partage et Paris 14 : ce point n'est pas un blocage.

La Ville de Paris pointe deja vers le site depuis sa page Fete des jardins.
Verifier aussi que les profils sociaux et partenaires utilisent l'adresse HTTPS
officielle. Ne pas acheter des liens ni publier de faux avis.

## Deploiement et verification des corrections

Dans le dossier du projet sur le serveur :

```sh
git pull --ff-only origin main
docker compose --env-file .env -f docker.compose.yaml up -d --build
docker compose --env-file .env -f docker.compose.yaml exec frontend nginx -t
docker compose --env-file .env -f docker.compose.yaml exec frontend nginx -s reload
```

Ne recharger Nginx que si `nginx -t` reussit. Le rechargement est necessaire car
son fichier de configuration est monte en volume.

Verifier avec des requetes GET : `www` doit renvoyer 301 vers le domaine sans
`www`, un article inexistant 404 et un article publie 200. La requete HEAD n'est
pas implementee par le serveur Python actuel : `curl -I` ne convient pas a ce controle.

Tests locaux : `python -m unittest discover -s tools -p test_seo.py -v`.
L'environnement de l'audit ne dispose pas de Docker/Nginx ; la nouvelle
configuration Nginx doit donc encore etre validee avec la commande ci-dessus.

## Sources

- [Validation Search Console](https://support.google.com/webmasters/answer/9008080?hl=fr)
- [Sitemap et soumission](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [Demander une exploration](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl)
- [URL canoniques et redirections](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
- [Limites des recherches site:](https://developers.google.com/search/docs/monitor-debug/search-operators/all-search-site)
- [Lien existant depuis la Ville de Paris](https://www.paris.fr/evenements/fete-des-jardins-le-14e-celebre-la-nature-en-ville-117874)
