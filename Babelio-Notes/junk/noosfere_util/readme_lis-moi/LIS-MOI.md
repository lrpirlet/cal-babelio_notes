# Le site de nooSFere

Le URL de nooSFere est <https://https://www.noosfere.org/>.

Voici un site extrêmement riche consacré aux publications de
l’imaginaire.

On y trouve des références aux livres, aux auteurs, aux 4me de
couverture, pour ne nommer que quelques-uns des sujets présentés dans
l’encyclopédie : [Ce que contiennent les bases de données
(noosfere.org)](https://www.noosfere.org/noosfere/pro/stats_bases.asp))..

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

Le site nooSFere ne vend ni n’édite des livres. L’association propose a
ses membres (coût de 30€/an voire 10€/an en tarif réduit… on peut donner
plus 😊) des services vraiment superbes. Voir [Pourquoi
adhérer](https://www.noosfere.org/noosfere/assoc/pourquoi.asp).

Je ne fais PAS de pub, mais j’aime vraiment bien ce site… Attention, ce
site va changer dans le futur, c’est annoncé :

[nooSFere - Soutenir
l'association](https://www.noosfere.org/noosfere/assoc/don.asp)

## cal-noosfere

Mon idée est de me permettre de télécharger les informations relatives à un
volume du livre dans calibre

## cal-noosfere-util

Avant de télécharger de nouvelles informations à propos d'un volume, il 
peut être nécessaire de supprimer plusieurs champs existants tels que Série,
ISBN, éditeur, collection, coll_srl... en effet, calibre ne permet pas d'effacer
un champ à partir d'un metadata source plugin (Calibre combine les informations
dans ces champs)

L'intention de cal-noosfere-util est de pouvoir choisir le volume de l'ouvrage
et de préparer l'enregistrement de nouvelles informations.

ENsuite cal-noosfere peut être exécuté pour remplir calibre avec une information correcte.
