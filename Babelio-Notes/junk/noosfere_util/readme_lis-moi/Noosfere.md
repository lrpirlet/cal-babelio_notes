# Le site de nooSFere

Le URL de nooSFere est <https://www.noosfere.org/>.

Voici un site extrêmement riche consacré aux publications à propos de
l’imaginaire.

On y trouve des références aux livres, aux auteurs, aux 4me de
couverture, pour ne nommer que quelques-uns des sujets présentés dans
l’encyclopédie : [Ce que contiennent les bases de données
(noosfere.org)](file:///C:\Users\Papa\AppData\Roaming\Microsoft\Word\Ce%20que%20contiennent%20les%20bases%20de%20données%20(noosfere.org))…

nooSFere héberge des sites amateurs : [nooSFere - Sites
d'adherents](https://www.noosfere.org/noosfere/heberges.asp)

nooSFere héberge des sites d’auteurs et d’illustrateurs : [nooSFere -
Sites d'auteurs](https://www.noosfere.org/noosfere/sites_auteurs.asp)

Je ne veux pas reproduire ici ce que le site dit bien mieux que moi…

Voir :

[nooSFere :
Qu'est-ce](https://www.noosfere.org/noosfere/assoc/qu_estce.asp) en bref

[nooSFere - Presentation de
l'association](https://www.noosfere.org/noosfere/assoc/statuts.asp) en
détail

[Questions à la
nooSFere](https://www.noosfere.org/icarus/articles/article.asp?numarticle=463)

[nooSFere - Plan du site](https://www.noosfere.org/actu/news.asp)

Le site nooSFere ne vend ni n’édite des livres. L’association propose à
ses membres (cout de 30€/an voire 10€/an en tarif réduit… on peut donner
plus 😊) des services vraiment superbes. Voir [Pourquoi
adhérer](https://www.noosfere.org/noosfere/assoc/pourquoi.asp).

Je ne fais PAS de pub, mais j’aime vraiment bien ce site… Attention, ce
site va changer dans le futur, c’est annoncé :

[nooSFere - Soutenir
l'association](https://www.noosfere.org/noosfere/assoc/don.asp)

Mon idée est de me permettre de télécharger les infos relatives à un
livre dans calibre. 

Ce que je cherche, en fait, est de présenter à travers le catalogue de calibre un maximum d'information a propos d'un livre, d'un cycle, d'un auteur, d'un genre... 

Outre les information de base telles que le titre exact, l'auteur, la date de depot legal, l'editeur, la serie, la sequence dans la serie, la collection de l'editeur et le numero d'ordre dans la collection, je cherche a presenter des  informations telles que un pointeur sur noosfere du volume, un resumé, une critique, une critique du cycle dont fait partie le volume, le titre original, l'illustrateur, le traducteur...

La beauté de calibre est que l'on a pas besoin d'avoir le livre. Ainsi, j'ai des cycles incomplets mais j'ai les metadonnées de toute la série...

## L’API (actuel) de ce site, ou plutôt de l’encyclopédie de ce site

### Une recherche simple par [nooSFere - Recherche](https://www.noosfere.org/noosearch_simple.asp)…

Il suffit de remplir la case recherche et envoyer par « enter » ou par
&lt;CR&gt;. Le site répond tout ce qui correspond aux ‘Mots’ écrits dans
la case avec interprétation libre (essayez « riCH » pour voir).

Bien sûr c’est magnifique, mais pour filtrer ce que tu veux, il faut un
humain ou une IA… (non je ne peux pas programmer une IA)

### Une recherche avancée par [nooSFere - Recherche dans les bases de nooSFere](https://www.noosfere.org/livres/noosearch.asp)

On a aussi une case pour y écrire les ‘Mots’ rechercher, mais on peut
sélectionner le sujet (auteur, livres, série, etc.). De plus on peut
préciser si on veut tous les mots, n’importe quel mot ou les mots
proches l’un de l’autre. On peut exiger la correspondance exacte des
mots plutôt que des phrases et des mots approchants…

## Recherche simple par programme

On envoie une requête, méthode « post »
vers :<https://www.noosfere.org/noosearch_simple.asp> avec pour
arguments : "Mots" : "&lt;entrée dans la boite&gt;"
Notez que cette methode de recherche est limitée et retoourne le plus souvent trop d'informations

## Recherche avancée par programme

On envoie une requête, méthode « post »
vers :<https://www.noosfere.org/noosearch_simple.asp> avec

- Arguments obligatoires sous la forme :"key":"value"

  - "Mots":"&lt;entrée dans la boite&gt;"

  - "ModeMoteur":"LITTERAL" (phrase et mots approchants) 
        "ModeMoteur":"MOTSCLEFS" (correspondance exacte des mots) (beaucoup trop restrictif, rate une fois sur deux, se plante de temps en temps sur les titres)

  - "ModeRecherche":"AND"  (défaut)
    "ModeRecherche":"OR"  
    "ModeRecherche":"NEAR"

  - "recherche":"1"

  - "Envoyer":"Envoyer"

- Un ou plusieurs des arguments suivant sous la forme "key":"value". On peut, classiquement, rechercher des références par ISBN, par titre et par Auteurs.
Mais on peut aussi chercher des références liées à un cycle (série), ou a un illustrateur ou a un traducteur, ou a un editeur...

  - "auteurs":"auteurs" (Auteurs, traducteurs, illustrateurs...)

  - "livres":"livres" (Livres ou ISBN)

  - "series":"series" (Séries)

  - "sommaires":"sommaires" (Sommaires (nouvelles, préfaces...))

  - "editeurs":"editeurs" (Editeurs)

  - "collections":"collections" (Collections)

  - "resumes":"resumes" (4èmes de couverture)

  - "critiques":"critiques" (Critiques)

  - "CritiquesLivresAuteur":"CritiquesLivresAuteur" (Auteur de
        critiques livres)

  - "prix":"prix" (Prix littéraires)

  - "articles":"articles" (Articles du fonds documentaire)

  - "ArticlesMotsClefs":"ArticlesMotsClefs" (Limiter aux mots-clefs)

  - "ArticlesAuteur":"ArticlesAuteur" (Auteur des articles du fonds
        documentaire)

  - "adaptations":"adaptations" (Adaptations)

  - "CritiquesCinema":"CritiquesCinema" (Critiques des adaptations)

## Recherche par ISBN

En principe un ISBN est attribué par livre. C'est vrai la plupart du temps mais un même ouvrage peut être connu sous plusieurs ISBN, à tout le moins après que l'usage d'un ISBN se soit répandu. Le format d'un ISBN est relativement libre, en outre l'ISBN à 10 chiffres a été remplacé par l'ISBN à 13 chiffres.

Le premier essais sera d'interroger le site avec un ISBN que l'on vérifie correct.
Le retour du site est une SERIE de références que je qualifie de volumes.

A chacun de volumes, triés par ordre de parution, j'associe une série de paramètres qui me permettront de choisir ce que je considère le meilleur candidat.

Ces volumes diffèrent par l'éditeur, la date d'édition ou de réédition, l'image de couverture, le 4me de couverture, la critique.

- MON choix se base sur un système de points:
- résumé présent:                       r   1pt
- critique présente:                    c   1pt         ne semble pas trop correct car CS n'existe pas même si, quand une critique existe, elle est reprise pour tous les volumes
- critique de la série                  cs  1pt
- sommaire des nouvelles présentes:     s   1pt
- information vérifiée                  v   1pt
- titre identique                       t   1pt
- image presente                        p   1pt
- isbn present                          i   2pt
- le nombre de point sera  augmenté de telle manière a choisir le livre chez l'éditeur le plus représenté... MON choix
- en cas d'egalité, le plus ancien reçoit la préférence

## Recherche par titre

Tout a fait similaire à la recherche par ISBN, mais en plus, le nombre de livres pointés par noosfere comme ressemblant est souvent énorme.

Comme pour l'ISBN, noosfere renvoie pour chaque ouvrage (livre) une série de volume... La recherche devient énorme et je ne vois pas comment faire un tri efficace  pour retrouver ce que je veux...

A éviter

## Recherche par auteur

Qu'on ne s'y trompe pas, l'auteur doit être suffisamment bien défini pour que noosfere retourne UNE seule référence... pour le fun, entre un prénom 

Ici, au contraire du titre, l'usage de "ModeMoteur":"MOTSCLEFS" (correspondance exacte des mots) semble efficace même pour un nom tronque (essaye voGt pour VAN VOGT Alfred Elton).

Au pointeur de l'auteur, le site noosfere retourne par defaut la bibliographie de l'auteur de la quelle on peut extraire le pointeur titre que l'on recherche. ce pointeur retourne une série de pointeur de volumes dont je choisi celui qui me semble le mieux...

## couvertures

Noosfere ne donne pas toujours de grandes et belles couverture, mais, sauf quand elle manque (rare), elle retourne la couverture associée avec le volume. Je récupère cette couverture, SANS laisser le choix d'une autre. Libre à l'utilisateur de rechercher une meilleure image ou même une autre (si la cohérence du volume n'importe pas).