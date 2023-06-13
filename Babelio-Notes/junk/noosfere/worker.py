#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2021, Louis Richard Pirlet'
__docformat__ = 'restructuredtext en'

import datetime
from bs4 import BeautifulSoup as BS
from threading import Thread

from calibre.ebooks.metadata.book.base import Metadata

from calibre_plugins.noosfere import ret_soup, verify_isbn

class Worker(Thread):
    '''
    Get volume details, in a separate thread, from noosfere vol page from (book_url)s found in __init__
    '''

    def __init__(self, log, book_url, book_title, isbn, result_queue, browser, relevance, plugin, dbg_lvl, timeout=30):

        Thread.__init__(self)
        self.daemon = True
        self.log = log
        self.book_url = book_url
        self.nsfr_id = ""
        self.book_title = book_title
        self.isbn = isbn
        self.result_queue = result_queue
        self.br = browser.clone_browser()
        self.relevance = relevance
        self.plugin = plugin
        self.dbg_lvl = dbg_lvl
        self.timeout = timeout
        self.who = "[worker "+str(relevance)+"]"
        self.from_encoding = "windows-1252"
        self.extended_publisher = self.plugin.extended_publisher
        self.set_priority_handling = self.plugin.set_priority_handling
        self.with_isbn = self.plugin.with_isbn
        self.balanced = self.plugin.balanced
        self.must_be_editor = self.plugin.must_be_editor
        self.get_Prixobtenus = self.plugin.get_Prixobtenus
        self.get_Citédanslespagesthématiquessuivantes = self.plugin.get_Citédanslespagesthématiquessuivantes
        self.get_Citédansleslistesthématiquesdesoeuvressuivantes = self.plugin.get_Citédansleslistesthématiquesdesoeuvressuivantes
        self.get_CitédanslesConseilsdelecture = self.plugin.get_CitédanslesConseilsdelecture
        self.get_Adaptations = self.plugin.get_Adaptations

        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"Entering worker")
        if debug:
            self.log.info(self.who,"self                                                : ", self)
            self.log.info(self.who,"log                                                 : ", log)
            self.log.info(self.who,"book_url                                            : ", book_url)
            self.log.info(self.who,"book_title                                          : ", book_title)
            self.log.info(self.who,"isbn                                                : ", isbn)
            self.log.info(self.who,"result_queue                                        : ", result_queue)
            self.log.info(self.who,"browser, self.browser                               : ", browser, self.br)
            self.log.info(self.who,"relevance                                           : ", relevance)
            self.log.info(self.who,"plugin                                              : ", plugin)
            self.log.info(self.who,"dbg_lvl                                             : ", dbg_lvl)
            self.log.info(self.who,"timeout                                             : ", timeout)
            self.log.info(self.who,"extended_publisher                                  : ", self.extended_publisher)
            self.log.info(self.who,"with_isbn                                           : ", self.with_isbn)
            self.log.info(self.who,"balanced                                            : ", self.balanced)
            self.log.info(self.who,"set_priority_handling                               : ", self.set_priority_handling)
            self.log.info(self.who,"must_be_editor                                      : ", self.must_be_editor)
            self.log.info(self.who,"get_Prixobtenus                                     : ", self.get_Prixobtenus)
            self.log.info(self.who,"get_Citédanslespagesthématiquessuivantes            : ", self.get_Citédanslespagesthématiquessuivantes)
            self.log.info(self.who,"get_Citédansleslistesthématiquesdesoeuvressuivantes : ", self.get_Citédansleslistesthématiquesdesoeuvressuivantes)
            self.log.info(self.who,"get_CitédanslesConseilsdelecture                    : ", self.get_CitédanslesConseilsdelecture)
            self.log.info(self.who,"get_Adaptations                                     : ", self.get_Adaptations)


    def run(self):
        '''
        wrk from file __init__.py could be a URL to the book (several volumes) or to the unique volume.
        Sometimes we get a 'book' URL that is redirected to a 'volume' URL...
        OK, il faut se connecter sur wrk_url et remonter url_vrai...
        On décide sur url_vrai contenant niourf.asp (volume) ou ditionsLivre.asp (livre)
        '''
        debug=self.dbg_lvl & 2
        self.log.info(self.who,"Entering run(self)")

        wrk_url = self.book_url
        if "ditionsLivre" in wrk_url:
            self.log.info("\n",self.who,"several volumes exist for this book")
            book_url="https://www.noosfere.org"+self.book_url+"&Tri=3"
            if debug: self.log.info(self.who,"book_url : ",book_url)
            try:
                wrk_url = self.ret_top_vol_indx(book_url, self.book_title, self.isbn)
                if debug: self.log.info(self.who,"wrk_url               : ", wrk_url)
            except:
                self.log.exception("ERROR: ret_top_vol_indx failed for URL: ",book_url)

        if "niourf" in wrk_url:
            self.log.info("\n",self.who,"getting to THE volume for this book")
            vol_url="https://www.noosfere.org"+wrk_url.replace("./niourf","/livres/niourf")+"&Tri=3"
            if debug: self.log.info(self.who,"vol_url  : ",vol_url)
            try:
                self.extract_vol_details(vol_url)
            except:
                self.log.exception("ERROR: extract_vol_details failed for URL: ",vol_url)

    def ret_top_vol_indx(self, url, book_title, book_isbn):
        '''
        cette fonction reçoit l'URL du livre qui contient plusieurs volumes du même auteur,
        dont certains ont le même ISBN et généralement le même titres.

        Ces volumes diffèrent par l'éditeur, la date d'édition ou de réédition, l'image de couverture, le 4me de couverture, la critique.
        MON choix se base sur un système de points sur les indications du site
        résumé présent:                       r   1pt
        critique présente:                    c   1pt         # semble pas trop correct car CS n'existe pas même si, quand
        critique de la série                  cs  1pt         # une critique existe, elle est parfois reprise pour tous les volumes
        sommaire des nouvelles présentes:     s   1pt
        information vérifiée                  v   2pt
        titre identique                       t   5pt
        image présente                        p   1pt
        isbn présent                          i  50pt         fonction de with_isbn
        isbn présent et identique a calibre     100pt         fonction de with_isbn
        le nombre de point sera  augmenté de telle manière a choisir le volume chez l'éditeur le plus représenté... MON choix
        en cas d'égalité, le plus ancien reçoit la préférence sauf préférence

        This gets the book's URL, many volumes may be present with (or not) same ISBN, same title.
        if the book only has one volume, then we bypass ret_top_vol_indx

        the volumes are different by the publisher, edition's or re-edition's date, cover, resume, critic...
        MY choice is based on a point system based on the site's flag
        resume available:                     r   1pt
        critic available:                     c   1pt         # maybe incorrect as sometimes, when a critic exists
        series critic:                        cs  1pt         # it is distributed to all volume without indication
        summary of novel in the book:         s   1pt
        verified information                  v   2pt
        same title as requested               t   5pt
        cover available                       p   1pt
        isbn available                        i  50pt         depending on with_isbn
        isbn available and same as calibre      100pt         depending on with_isbn
        the score will be increased so that the volume will be chosen to the most present publisher ... MY choice
        in case of equality the oldest win
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In ret_top_vol_indx(self, url, title, isbn)")
        if debug:
            self.log.info(self.who, "url : ", url, ", book_title : ", book_title, "isbn : ", book_isbn)

        self.log.info(self.who,"calling ret_soup(log, dbg_lvl, br, url, rkt=None, who='[__init__]')")
        if debug:
            self.log.info(self.who,"url : ", url, "who : ", self.who)
        rsp = ret_soup(self.log, self.dbg_lvl, self.br, url, who=self.who)
        soup = rsp[0]
        url_vrai = rsp[1]
        if debug:
#            self.log.info(self.who,"ret_top_vol_indx soup :\n",soup)        # a bit long I guess
            self.log.info(self.who,"url_vrai  : ",url_vrai)

        if "niourf.asp" in url_vrai:
            self.log.info(self.who,"Bypassing to extract_vol_details, we have only one volume")
            return url_vrai.replace("https://www.noosfere.org","")                     #volume found return and set wrk_url to volume

        ts_vl_index={}
      # we prefer volumes with an identifier, but some are edited on a particular publisher without isbn
        push_isbn = self.with_isbn
        priority_balanced = self.balanced
        if debug:
            self.log.info(self.who,"priority pushes isbn  : ", push_isbn)
            self.log.info(self.who,"priority balanced : ", priority_balanced)

        nbr_of_vl=soup.select("td[class='item_bib']")
        for count in range(0,len(nbr_of_vl),2):
            subsoup=nbr_of_vl[count]
            point=1
            vl_index=vl_title=vl_cover_index=vl_editor=vl_isbn=vl_collection=""

            if subsoup.select("a[href*='numlivre']"): vl_index=subsoup.select("a[href*='numlivre']")[0]['href']

            if subsoup.select("a > img"): vl_title=subsoup.select("a > img")[0]['alt']
            if book_title.title()==vl_title.title():
                if priority_balanced: point+=5

            if subsoup.select("a > img"):
                vl_cover_index=subsoup.select("a > img")[0]['src']
                if priority_balanced: point+=1

            if subsoup.select("a[href*='numediteur']"): vl_editor=subsoup.select("a[href*='numediteur']")[0].text

            if subsoup.select("span[class='SousFicheNiourf']"):
                vl_isbn = subsoup.select("span[class='SousFicheNiourf']")[0].text.strip()
                vl_isbn = verify_isbn(self.log, self.dbg_lvl, vl_isbn, who=self.who)
                if vl_isbn:
                    if push_isbn:
                        if priority_balanced:
                            point+=50
                            if vl_isbn==book_isbn: point+=50

            if subsoup.select("a[href*='collection']"): vl_collection=subsoup.select("a[href*='collection']")[0].text

            if subsoup.select("img[src*='3dbullgreen']"):
                if priority_balanced: point+=2

            tmp_presence=subsoup.select("span[title*='Présence']")
            if priority_balanced:
                for i in range(len(tmp_presence)):
                    if "R" in tmp_presence[i].text: point+=1
                    elif "C" in tmp_presence[i].text: point+=1
                    elif "CS" in tmp_presence[i].text: point+=1
                    elif "S" in tmp_presence[i].text: point+=1

            ts_vl_index[int(count/2)]=(point,vl_index,vl_editor)

            self.log.info(self.who,"found",int(count/2+1),"volumes différents")
            self.log.info(self.who,"key                   : ",int(count/2))
            self.log.info(self.who,"vl_index             : ",vl_index)
            self.log.info(self.who,"vl_title             : ",vl_title)
            self.log.info(self.who,"vl_cover_index       : ",vl_cover_index)
            self.log.info(self.who,"vl_editor            : ",vl_editor)
            self.log.info(self.who,"vl_isbn              : ",vl_isbn)
            self.log.info(self.who,"vl_collection        : ",vl_collection)
            self.log.info(self.who,"point                 : ",point)

        top_vl_point = 0
        top_vl_index = ""
        serie_editeur = []
        reverse_it = True if "latest" in self.set_priority_handling else False
        if debug: self.log.info(self.who,"priority pushes latest : ", reverse_it)

      # in python 3 a dict keeps the order of introduction... In this case, as noosfere presents it in chronological order,
      # let's invert the dict by sorting reverse if the latest volume is asked
        ts_vl_index = dict(sorted(ts_vl_index.items(),reverse=reverse_it))

      # create a list of publisher
        for key,ref in ts_vl_index.items():
            serie_editeur.append(ts_vl_index[key][2])

      # find the publishers in the list
        top_vol_editor={}.fromkeys(set(serie_editeur),0)

      # and set a value to each publisher function of the count and (the value of) self.must_be_editor
        if debug:
            self.log.info(self.who,"if self.must_be_editor  : ", bool(self.must_be_editor))
        for editr in serie_editeur:
            top_vol_editor[editr]=1
            if self.must_be_editor:
                if self.must_be_editor == editr:
                    top_vol_editor[editr]+=10
                else:
                    top_vol_editor[editr]+=1

       # compute all that and the final result is the first entry with the top number of point...
        for key,ref in ts_vl_index.items():
            if debug:
                self.log.info(self.who,"pour la clé", key,"la valeur des points est", ts_vl_index[key][0]*top_vol_editor[ts_vl_index[key][2]],"l'URL est",ts_vl_index[key][1],"l'éditeur est",ts_vl_index[key][2])
            if ts_vl_index[key][0]*top_vol_editor[ts_vl_index[key][2]]>top_vl_point:
                top_vl_point=ts_vl_index[key][0]*top_vol_editor[ts_vl_index[key][2]]
                top_vl_index=ts_vl_index[key][1]

        return top_vl_index

    def get_Critique_de_la_serie(self, critic_url):
        '''
        La critique de la série peut être développée dans une autre page dont seul l'URL est d'intérêt
        cette fonction remplace le pointeur par le contenu.

        The critic for a series may be set apart in another page. The vol URL refers to that other location.
        I want to have it.
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In get_Critique_de_la_serie(self, critic_url)")
        if debug:
            self.log.info(self.who,"calling ret_soup(log, dbg_lvl, br, url, rkt=None, who='[__init__]')")
            self.log.info(self.who,"critic_url : ", critic_url, "who : ", self.who)
        soup = ret_soup(self.log, self.dbg_lvl, self.br, critic_url, who=self.who)[0]
        if soup.select_one('div[id="SerieCritique"]'):
            if debug:
#                self.log.info(self.who,"critique de la série extract:\n","""soup.select_one('div[id="SerieCritique"]')""",soup.select_one('div[id="SerieCritique"]'))        # a bit long I guess
                self.log.info(self.who,"critique de la série processed")
            return soup.select_one('div[id="SerieCritique"]')
        else:
            if debug:
#                self.log.info(self.who,"critique de la série extract:\n","""soup.select_one('div[id="critique"]')""",soup.select_one('div[id="critique"]'))        # a bit long I guess
                self.log.info(self.who,"critique de la série processed")
            return soup.select_one('div[id="critique"]')

    def get_decoupage(self, soup):
        '''
        certains cycles sont divisés suivant une autre serie de volume...
        ceci retourne le numero de la serie fonction du volume choisi (numitem)
        bk_decoup est l'adresse de la page de cette decoupe annexe
        cette fonction retourne un string qui represente la numero du volume dans la serie
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In get_decoupage(self, soup)")

        vol_serie_seq = "0"
        nmtm = None
        titre= None

      # isole le n° de ref du volume (numitem) et l'url du/des découpage/s (bk_decoup)
      # sans numitem, pas de flèche qui pointe vers le précédent ou le suivant de la série...
        try:
            nmtm = soup.select_one('a[href*="numitem"]')['href'].split("=")[-1]
        except:
            if debug: self.log.info(self.who, "OUPS, pas de numitem...")
            titre = self.isole_title(soup)
            if debug: self.log.info(self.who, "on essaye avec le titre : {}".format(titre))

        bk_decoup = "https://www.noosfere.org/livres/"+soup.select('a[href*="serie.asp"]')[0]['href']+"&Niveau=simple"
        if debug:
            if nmtm:
                self.log.info(self.who,"nmtm      : ", nmtm)
            else:
                self.log.info(self.who,"titre     : ", titre)
            self.log.info(self.who,"bk_decoup : ", bk_decoup)

        sp = ret_soup(self.log, self.dbg_lvl, self.br, bk_decoup, who=self.who)[0]
        bk_dcp = sp.select('a[href*=numitem]')

      # if titre exists, find nmtm from an exact match of the title with one of the titles in the list
      # (hope no exact same title in two alternate series)
        if titre:
            for i in range(len(bk_dcp)):
                # if debug: self.log.info(self.who, "bk_dcp[{}] : {}".format(i,bk_dcp[i]))     # a bit long I guess
                if titre.strip() == bk_dcp[i].get_text().strip():
                    nmtm =  bk_dcp[i]['href'].split("=")[-1]
                    break
            if debug:
                self.log.info(self.who,"nmtm      : ", nmtm)

      # extrait la numerotation fonction de nmtm
        for i in range(len(bk_dcp)):
            # if debug: self.log.info(self.who, "bk_dcp[{}] : {}".format(i,bk_dcp[i]))     # a bit long I guess
            if nmtm:
                if (nmtm == bk_dcp[i]['href'].split("=")[-1]):
                    vol_serie_seq = bk_dcp[i].get_text().split("/")[0].strip()
                    break

        if debug:
            self.log.info(self.who,"return vol_serie_seq : {}".format(vol_serie_seq))
        return vol_serie_seq

    def isole_lien_couverture(self,soup):
        '''
        retourne le lien vers la couverture du volume choisi, sera place dans les commentaires
        car la couverture choisie peut etre differente de la vraie couverture...
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In isole_lien_couverture(self, soup)")

        vol_cover_index=""

        try:
            vol_cover_index = soup.find(property="og:image").get("content")
        except:
          # og:image may be missing in the head ... revert searching cover in the body
            if not vol_cover_index:
                if soup.select("img[name='couverture']"):
                    for elemnt in repr(soup.select("img[name='couverture']")[0]).split('"'):
                        if "http" in elemnt:
                            vol_cover_index = elemnt

        if debug:
            self.log.info(self.who,"return vol_cover_index : {}".format(vol_cover_index))
        return vol_cover_index


    def isole_isbn(self, soup):
        '''
        return ISBN from sousFicheNiourf (used to be extrated together with genre and publication date)
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In isole_isbn(self, soup)")

        vol_isbn=""
        all_elemnt=[]

#        if debug: self.log.info(self.who,"sousFicheNiourf : \n", soup.select_one("span[class='sousFicheNiourf']").prettify())                          # a bit long I guess
        for elemnt in soup.select_one("span[class='sousFicheNiourf']").stripped_strings:
            all_elemnt.append(elemnt)
#        if debug: self.log.info(self.who,"all_elemnt : ", all_elemnt)                          # a bit long I guess

        for i in range(len(all_elemnt)):
            if not vol_isbn and "ISBN : " in all_elemnt[i]:
                vol_isbn = all_elemnt[i].replace("ISBN : ","").strip()
                if not vol_isbn[0].isnumeric(): vol_isbn=""

        if debug:
            self.log.info(self.who,"return ISBN : {}".format(vol_isbn))
        return vol_isbn


    def isole_genre_date(self,soup):
        '''
        sousFicheNiourf holds some information we want to extract: ISBN, Genre and publication date... However,
        publication date is largely ignored in noosfere, but we have the "dépot legal" date and I use it instead
        note that I 'calculate' the missing day of the month and even sometimes the missing month (somewhen in the middle)
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In isole_genre_date(self, soup)")

        vol_genre=""
        vol_dp_lgl=""
        period=""
        all_elemnt=[]

#        if debug: self.log.info(self.who,"sousFicheNiourf : \n", soup.select_one("span[class='sousFicheNiourf']").prettify())                          # a bit long I guess
        ms=("janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre")
        for elemnt in soup.select_one("span[class='sousFicheNiourf']").stripped_strings:
            all_elemnt.append(elemnt)
#        if debug: self.log.info(self.who,"all_elemnt : ", all_elemnt)                          # a bit long I guess

        for i in range(len(all_elemnt)):
            for dt in ("Dépôt légal :","Date de parution :"):                                  # if "Dépôt légal :" absent try "Date de parution :"
                if not period and dt in all_elemnt[i]:
                    substr=all_elemnt[i].replace(dt,"").strip()
                    if len(substr):
                        period=substr.replace(","," ")
                        if substr.isnumeric():
                            dom = substr
                            substr = all_elemnt[i+1]
                            period = dom + " " + substr
                    else:
                        substr=all_elemnt[i+1]
                        period=substr.replace(","," ")

        if period:
            if period.isnumeric() and len(period) == 4:
                vol_dp_lgl=datetime.datetime.strptime("175 "+period,"%j %Y")
            elif "semestre" in period:
                ele=period.split()
                vol_dp_lgl=datetime.datetime.strptime(("000"+str((int(ele[0][0])-1)*175+97))[-3:]+" "+ele[2],"%j %Y")
            elif "trimestre" in period:
                ele=period.split()
                vol_dp_lgl=datetime.datetime.strptime(("000"+str((int(ele[0][0])-1)*91+47))[-3:]+" "+ele[2],"%j %Y")
            else:
                for i in range(len(ms)):
                    if ms[i] in period:
                        ele=period.split()
                        if len(ele)==3:
                            vol_dp_lgl=datetime.datetime.strptime(("00"+ele[0])[-2:]+" "+("00"+str(i+1))[-2:]+" "+ele[2],"%d %m %Y")
                        else:
                            vol_dp_lgl=datetime.datetime.strptime(("000"+str(10+31*i))[-3:]+" "+ele[1],"%j %Y")

        for i in range(len(all_elemnt)):
            if "Genre : " in all_elemnt[i]:
                vol_genre = all_elemnt[i].replace("Genre : ","").strip()

        if debug:
            self.log.info(self.who,"return genre : {}, date : {}".format(vol_genre, vol_dp_lgl))
        return vol_genre, vol_dp_lgl


    def isole_editeur_and_co(self, soup):
        '''
        returns publisher, publisher collection and publisher collection index
        the collection and related index will be added to the publisher field
        if so desired
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In isole_editeur_and_co(self, soup)")

        tmp_lst=[]
        vol_editor=""
        vol_coll=""
        vol_coll_srl=""

        if soup.select("a[href*='editeur.asp']"): vol_editor = soup.select("a[href*='editeur.asp']")[0].text
        if soup.select("a[href*='collection.asp']"): vol_coll = soup.select("a[href*='collection.asp']")[0].text
        for i in soup.select("span[class='ficheNiourf']")[0].stripped_strings:
            tmp_lst.append(str(i))
        vol_coll_srl = tmp_lst[len(tmp_lst)-1]
        if "n°" in vol_coll_srl:
            for k in ["n°","(",")"]:
                if k in vol_coll_srl:
                    vol_coll_srl=vol_coll_srl.replace(k,"")
            vol_coll_srl = vol_coll_srl.strip()
            if vol_coll_srl.isnumeric(): vol_coll_srl=("0"*5+vol_coll_srl)[-6:]
        else:
            vol_coll_srl = ""

        if debug:
            self.log.info(self.who,"return publisher : {}, pub_coll : {}, pub_coll_srl : {}".format(vol_editor, vol_coll, vol_coll_srl))
        return vol_editor, vol_coll, vol_coll_srl


    def isole_serie_serie_seq(self, soup):
        '''
        will return series and associated sequence.
        series and series_seq will be formatted for use
        vol_title maybe needed in some occasion
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In isole_serie_serie_seq(self, soup)")

        vol_serie=""
        vol_serie_seq=""

        if soup.select("a[href*='serie.asp']"):
            if soup.select("a[href*='serie.asp']")[0].find_parent("span", {"class":"ficheNiourf"}):
#                 if debug: self.log.info(soup.select("a[href*='serie.asp']")[0].find_parent("span", {"class":"ficheNiourf"}).prettify())              # a bit long I guess
                vol_serie = soup.select_one("a[href*='serie.asp']").text
                tmp_vss = [x for x in soup.select("a[href*='serie.asp']")[0].parent.stripped_strings]
                for i in range(len(tmp_vss)):
                    if "vol." in tmp_vss[i]:
                        if not vol_serie_seq:
                            vol_serie_seq=tmp_vss[i].replace("vol.","").strip()
                            break
                    elif "découpage" in tmp_vss[i]:
                        vol_serie_seq = self.get_decoupage(soup)
                        break
                    elif "omnibus" in tmp_vss[i]:
                        vol_serie_seq = self.get_decoupage(soup)
                        break

        if vol_serie:
            vol_serie_seq = vol_serie_seq.replace("bis","")         # damn I can't differentiate a 'bis' numerotation
            if vol_serie_seq.isnumeric():
                vol_serie_seq = float(vol_serie_seq)
            else:
                if vol_serie_seq and vol_serie_seq[0:-1].isnumeric():   # return vol_serie_seq : 2a ==> 2.01
                    try: subseq=("abcdefghijklmnopqrstuvwxyz".index(vol_serie_seq[-1])+1)/100
                    except: subseq=0.99
                    vol_serie_seq = float(vol_serie_seq[0:-1])+subseq
                elif "(omn" in vol_serie_seq:                           # return vol_serie_seq : (omn1)  ==> 0.1
                    vol_serie_seq = vol_serie_seq.replace("(omn","").replace(")","")
                    if vol_serie_seq and vol_serie_seq.isnumeric():
                        vol_serie_seq = float(vol_serie_seq)/10
                    else:
                        if debug: self.log.info(self.who,"vol_serie_seq is {}, will be set to 0.0 (line1)".format(vol_serie_seq))
                        vol_serie_seq = 0.0
                else:
                    if debug: self.log.info(self.who,"vol_serie_seq is {}, will be set to 0.0 (line2)".format(vol_serie_seq))
                    vol_serie_seq = 0.0

        if debug: self.log.info(self.who,"return vol_serie, vol_serie_seq : ",vol_serie,",",vol_serie_seq)
        return vol_serie, vol_serie_seq

    def isole_authors(self, soup):
        '''
        returns authors as a string of the form
        First_name_0 Familly_name_0 & First_name_1 Familly_name_1 ...
        needs to be modified as to return a list of the form
        [First_name_0 Familly_name_0, First_name_1 Familly_name_1, ...]
        or maybe (check what is best)
        ['Familly_name_0,First_name_0', 'Familly_name_1,First_name_1',  ...]
        needs to be modified later to reflect list instead of string
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In isole_authors(self, soup)")

        vol_auteur=""
        vol_auteur_prenom=""
        vol_auteur_nom=""

        if soup.select("span[class='AuteurNiourf']"): vol_auteur = soup.select("span[class='AuteurNiourf']")[0].text.replace("\n","").strip()

        for i in range(len(vol_auteur.split())):
            if not vol_auteur.split()[i].isupper():
                vol_auteur_prenom += " "+vol_auteur.split()[i]
            else:
                vol_auteur_nom += " "+vol_auteur.split()[i].title()
        vol_auteur = vol_auteur.title()
        vol_auteur_prenom = vol_auteur_prenom.strip()
        if debug: self.log.info(self.who,"vol_auteur_prenom processed : ",vol_auteur_prenom)
        vol_auteur_nom = vol_auteur_nom.strip()
        if debug: self.log.info(self.who,"vol_auteur_nom processed : ",vol_auteur_nom)

        if debug: self.log.info(self.who,"return vol_auteur : ",vol_auteur)
        return vol_auteur

    def isole_title(self, soup):
        '''
        isole title de la soup...
        '''
        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In isole_title(self, soup)")

        vol_title=""

        vol_title = soup.select("span[class='TitreNiourf']")[0].text.strip()

        if debug: self.log.info(self.who,"return vol_title : ",vol_title)
        return vol_title


    def extract_vol_details(self, vol_url):
        '''
        Here we extract and format the information from the choosen volume.
        - The first name and last name to populate author and author sort : vol_auteur_prenom  and vol_auteur_nom
        - The title of the volume                                         : vol_title
        - The series name the volume is part of                           : vol_serie
        - The sequence number in the serie                                : vol_serie_seq                         # missing
        - The editor of this volume                                       : vol_editor
        - The editor's collection of this volume                          : vol_coll
        - The collection serial code of this volume                       : vol_coll_srl
        - The "dépot légal" date (the publication date is vastly unknown) : vol_dp_lgl                            # date format to be computed
        - The ISBN number associated with the volume                      : vol_isbn
        - The volume tags                                                 : vol_genre
        - The URL pointer to the volume cover image                       : vol_cover_index
        - The comments includes various info about the book               : vol_comment_soup
          . reference, an URL pointer to noosfere
          . couverture, an URL pointer to noosfere, cover may be real small, but is accurate to the volume
          . first edition information
          . series (cycle) name and number
          . this volume editor info
          . Resume (quatrième de couverture)
          . Critiques
          . Sommaire detailing what novels are in the volume when it is an anthology
          . Critiques about the series and/or about another volume of the book
        '''

        debug=self.dbg_lvl & 2
        self.log.info("\n",self.who,"In extract_vol_details(soup)")
        if debug:
            self.log.info(self.who,"vol_url       : ",vol_url)

        if debug:
            self.log.info(self.who,"calling ret_soup(log, dbg_lvl, br, url, rkt=None, who='[__init__]')")
            self.log.info(self.who,"vol_url : ", vol_url, "who : ", self.who)
        rsp = ret_soup(self.log, self.dbg_lvl, self.br, vol_url, who=self.who)
        soup = rsp[0]
        url_vrai = rsp[1].replace("&Tri=3","")
#         if debug: self.log.info(self.who,"extract_vol_details soup :\n",soup.prettify())              # a bit long I guess

        self.nsfr_id = "vl$"+url_vrai.replace('?','&').replace('=','&').split('&')[2]
        if debug:
            self.log.info(self.who,"self.nsfr_id, type() : ", self.nsfr_id, type(self.nsfr_id))

      # get title
        try:
            vol_title = self.isole_title(soup)
        except:
            self.log.exception("ERROR: isole_title(soup) failed")

      # get authors
        try:
            vol_auteur = self.isole_authors(soup)
        except:
            self.log.exception("ERROR: isole_authors(soup) failed")

      # get series and series seq
        try:
            vol_serie, vol_serie_seq = self.isole_serie_serie_seq(soup)
        except:
            self.log.exception("ERROR: isole_serie_serie_seq(soup) failed")

      # get publisher, publisher collection and publisher collection serial
        try:
            vol_editor, vol_coll, vol_coll_srl = self.isole_editeur_and_co(soup)
        except:
            self.log.exception("ERROR: isole_editeur_and_co(soup) failed")

      # get ISBN
        try:
            vol_isbn = self.isole_isbn(soup)
        except:
            self.log.exception("ERROR: isole_isbn(soup) failed")

      # get Genre and publication date
        try:
            vol_genre, vol_dp_lgl = self.isole_genre_date(soup)
        except:
            self.log.exception("ERROR: isole_genre_date(soup) failed")

      # get link to cover
        try:
            vol_cover_index = self.isole_lien_couverture(soup)
        except:
            self.log.exception("ERROR: isole_lien_couverture(soup) failed")

        self.log.info("\n",self.who,"Fetch and format various info to create HTML comments")

      # first line of comment is volume address as a reference in the comment (noosfere URL)
        vol_comment_soup=BS('<div><p>Référence: <a href="' + url_vrai + '">' + url_vrai + '</a></p></div>',"lxml")
        if debug: self.log.info(self.who,"reference url_vrai processed")

      # add cover image address as a reference in the comment
        comment_cover=None
        if vol_cover_index:
            comment_cover = BS('<div><p>Couverture: <a href="' + vol_cover_index + '">'+ vol_cover_index +'</a></p></div>',"lxml")
        if debug: self.log.info(self.who,"comment_cover processed")

      # get other editions
        comment_AutresEdition=None
        if soup.select_one("#AutresEdition"):
            comment_AutresEdition = soup.select_one("#AutresEdition")
        if debug: self.log.info(self.who,"comment_AutresEdition processed : ")
#        if debug: self.log.info(self.who,"comment_AutresEdition soup :\n", type(comment_AutresEdition),"\n", comment_AutresEdition)              # a bit long I guess

      # get generic comments
        comment_generic=None
        comment_generic = soup.select_one("span[class='ficheNiourf']")   #[0]
        new_div=soup.new_tag('div')
        comment_generic = comment_generic.wrap(new_div)
        if debug: self.log.info(self.who,"comment_generic processed")
#        if debug: self.log.info(self.who,"comment_generic : \n", comment_generic.prettify())                          # a bit long I guess

      # select the fields I want... More exist such as film adaptations or references to advises to read
      # but that is not quite consistent around all the books (noosfere is a common database from many people)
      # and beside I have enough info like that AND I do NOT want to take out the noosfere's business

        comment_resume=None
        comment_Critiques=None
        comment_Sommaire=None
        comment_AutresCritique=None
        comment_Prixobtenus=None
        comment_Citédanslespagesthématiquessuivantes=None
        comment_Citédansleslistesthématiquesdesoeuvressuivantes=None
        comment_CitédanslesConseilsdelecture=None
        comment_Adaptations=None

        tmp_comm_lst=soup.select("span[class='AuteurNiourf']")
#        if debug: self.log.info(self.who,"tmp_comm_lst\n",tmp_comm_lst)                                     # a bit long I guess

        for i in range(len(tmp_comm_lst)):
            if "Quatrième de couverture" in str(tmp_comm_lst[i]):
                comment_resume = tmp_comm_lst[i].find_parents("div",{'class':'sousbloc'})[0]
                if debug: self.log.info(self.who,"comment_resume processed")
#                if debug: self.log.info(self.who,"comment_resume\n",comment_resume)                         # a bit long I guess

            if "Critiques" in str(tmp_comm_lst[i]):
                if not "autres" in str(tmp_comm_lst[i]):
                    comment_Critiques = tmp_comm_lst[i].find_parents("div",{'class':'sousbloc'})[0]
                    if debug: self.log.info(self.who,"comment_Critiques processed")
#                    if debug: self.log.info(self.who,"comment_Critiques\n",comment_Critiques)               # a bit long I guess

            if "Sommaire" in str(tmp_comm_lst[i]):
                comment_Sommaire = tmp_comm_lst[i].find_parents("div",{'class':'sousbloc'})[0]
                if debug: self.log.info(self.who,"comment_Sommaire processed")
#                if debug: self.log.info(self.who,"comment_Sommaire\n",comment_Sommaire)                     # a bit long I guess

            if "Critiques des autres" in str(tmp_comm_lst[i]):
                comment_AutresCritique = tmp_comm_lst[i].find_parents("div",{'class':'sousbloc'})[0]
                if comment_AutresCritique.select('a[href*="serie.asp"]') and ("Critique de la série" in comment_AutresCritique.select('a[href*="serie.asp"]')[0].text):
                    critic_url = "https://www.noosfere.org/livres/"+comment_AutresCritique.select('a[href*="serie.asp"]')[0]['href']
                    try:
                        more_comment_AutresCritique=self.get_Critique_de_la_serie(critic_url)
                        comment_AutresCritique.append(more_comment_AutresCritique)
                    except:
                        self.log.exception("ERROR: get_Critique_de_la_serie failed for url: ",critic_url)
                if debug: self.log.info(self.who,"comment_AutresCritique processed")
#                if debug: self.log.info(self.who,"comment_AutresCritique\n",comment_AutresCritique)         # a bit long I guess

          # Note: Both "Prix obtenus" and "Prix obtenus par des textes du sommaire" are covered by the following code...
            if self.get_Prixobtenus and ("Prix obtenus" in str(tmp_comm_lst[i])):
                comment_Prixobtenus = tmp_comm_lst[i].find_parents("div",{'class':'sousbloc'})[0]
                if debug: self.log.info(self.who,"comment_Prixobtenus processed")
#                if debug: self.log.info(self.who,"comment_Prixobtenus\n",comment_Prixobtenus)              # a bit long I guess

            if self.get_Citédanslespagesthématiquessuivantes and ("Cité dans les pages thématiques suivantes" in str(tmp_comm_lst[i])):
                comment_Citédanslespagesthématiquessuivantes = tmp_comm_lst[i].find_parents("div",{'class':'sousbloc'})[0]
                if debug: self.log.info(self.who,"comment_Citédanslespagesthématiquessuivantes processed")
#                if debug: self.log.info(self.who,"comment_Citédanslespagesthématiquessuivantes\n",comment_Citédanslespagesthématiquessuivantes)              # a bit long I guess

            if self.get_Citédansleslistesthématiquesdesoeuvressuivantes and ("Cité dans les listes thématiques des oeuvres suivantes" in str(tmp_comm_lst[i])):
                comment_Citédansleslistesthématiquesdesoeuvressuivantes = tmp_comm_lst[i].find_parents("div",{'class':'sousbloc'})[0]
                if debug: self.log.info(self.who,"comment_Citédansleslistesthématiquesdesoeuvressuivantes processed")
#                if debug: self.log.info(self.who,"comment_Citédansleslistesthématiquesdesoeuvressuivantes\n",comment_Citédansleslistesthématiquesdesoeuvressuivantes)              # a bit long I guess

            if self.get_CitédanslesConseilsdelecture and ("Cité dans les Conseils de lecture" in str(tmp_comm_lst[i])):
                comment_CitédanslesConseilsdelecture = tmp_comm_lst[i].find_parents("div",{'class':'sousbloc'})[0]
                if debug: self.log.info(self.who,"comment_CitédanslesConseilsdelecture processed")
#                if debug: self.log.info(self.who,"comment_CitédanslesConseilsdelecture\n",comment_CitédanslesConseilsdelecture)              # a bit long I guess

            if self.get_Adaptations and ("Adaptations" in str(tmp_comm_lst[i])):
                comment_Adaptations = tmp_comm_lst[i].find_parents("div",{'class':'sousbloc'})[0]
                if debug: self.log.info(self.who,"comment_Adaptations processed")
#                if debug: self.log.info(self.who,"comment_Adaptations\n",comment_Adaptations)               # a bit long I guess

      # group in a big bundle all the fields I think I want... (It is difficult not to include more... :-))
        if comment_cover:
            vol_comment_soup.append(comment_cover)
        if comment_generic:
            vol_comment_soup.append(comment_generic)
        if comment_AutresEdition:                                       # NOT optional... seems that this is important info about the book as it gives all the volumes
            vol_comment_soup.append(comment_AutresEdition)
        if comment_resume:
            vol_comment_soup.append(comment_resume)
        if comment_Critiques:
            vol_comment_soup.append(comment_Critiques)
        if comment_Sommaire:
            vol_comment_soup.append(comment_Sommaire)
        if comment_AutresCritique:
            vol_comment_soup.append(comment_AutresCritique)
        if comment_Prixobtenus:                                                   # optionnal
            vol_comment_soup.append(comment_Prixobtenus)
        if comment_Citédanslespagesthématiquessuivantes:                          # optionnal
            vol_comment_soup.append(comment_Citédanslespagesthématiquessuivantes)
        if comment_Citédansleslistesthématiquesdesoeuvressuivantes:               # optionnal
            vol_comment_soup.append(comment_Citédansleslistesthématiquesdesoeuvressuivantes)
        if comment_CitédanslesConseilsdelecture:                                  # optionnal
            vol_comment_soup.append(comment_CitédanslesConseilsdelecture)
        if comment_Adaptations:                                                   # optionnal
            vol_comment_soup.append(comment_Adaptations)

#        if debug: self.log.info(self.who,"vol_comment_soup\n",vol_comment_soup.prettify())                             # a bit long I guess

        self.log.info("\n",self.who,"Correct HTML comments for design and complete functionality in calibre catalog")

      # ouais, et alors, si je modifie le comment_<n'importe quoi> immediatement APRES l'avoir ajouté à vol_comment_soup
      # et avant d'avoir tout intégré, comme il n'y a qu'une seule version en mémoire... ça fait un big mess
      # donc vol_comment_soup est modifié... APRES integration de toutes les parties
      #
      # Make a minimum of "repair" over vol_comment_soup so that it displays correctly (how I like it) in the comments and in my catalogs
      # - I hate justify when it makes margin "float" around the correct position (in fact when space are used instead of absolute positioning)
      # - I like to have functional url when they exist
      # - I like to find out the next and/or previous books in a series (simulated arrows are link :-) )

        for elemnt in vol_comment_soup.select('[align="justify"]'):
            del elemnt['align']

      # remove all double or triple 'br' to improve presentation.
      # Note: tmp1 and tmp2 must contain a different value from any possible first element. (yes, I am lrp and I am unique :-) )

        tmp1=tmp2="lrp_the_unique"
        for elemnt in vol_comment_soup.findAll():
            tmp1,tmp2=tmp2,elemnt
            if tmp1==tmp2:
                elemnt.extract()

      # merge sequential bold text and sequential italic text
      # so <b>I</b><b>saac<\b> displayed as "I saac" in calibre becomes
      # <b>Isaac<\b> displayed as "Isaac" in calibre

        x=[b"</b><b>",b"</i><i>",b"</em><em>",b"</strong><strong>"]
        for i in range(len(x)):
            vol_comment_soup=BS(vol_comment_soup.encode("utf-8").replace(x[i],b""),"html5lib")
#        if debug: self.log.info(self.who,"vol_comment_soup\n",vol_comment_soup.prettify())                             # a bit long I guess

      # insert style for title
      # then wrap div around span and next span if its exist
      # (Ca s'évanouit tout seul dans calibre du probablement à une construction non acceptée par calibre)
        for elemnt in vol_comment_soup.select('span'):
            if ("class" in elemnt.attrs) and ('AuteurNiourf' in elemnt.attrs['class'][0]):         #elemnt.select('.AuteurNiourf'):
                hr = vol_comment_soup.new_tag('hr')
                hr["style"]="color:CCC;"
                elemnt.insert_before(hr)
                elemnt["style"]="font-weight: 600; font-size: 18px"
                new_div=vol_comment_soup.new_tag('div')
                elemnt.wrap(new_div)
                if (elemnt.find_next("span")) and ("class" in elemnt.find_next("span").attrs):
                    if (not ('AuteurNiourf' in elemnt.find_next("span").attrs['class'][0])):
                        new_div=vol_comment_soup.new_tag('div')
                        elemnt.find_next("span").wrap(new_div)

      # repair comment_AutresEdition in vol_comment_soup by removing id=AutresEdition if it exists....
      # this should make the whole word "AutresEdition" click-able instead of only the first letter 'A'

        if vol_comment_soup.select("div[id='AutresEdition']"):
            tmptag=vol_comment_soup.select_one("div[id='AutresEdition']")
            del tmptag['id']

      # repair url's so it does NOT depend on being in noosfere space

        if debug:
            for elemnt in vol_comment_soup.select("a[href]"):
                if 'http' not in elemnt.get('href'):
                    self.log.info(self.who,"url incomplet avant correction: ", elemnt)

        for elemnt in vol_comment_soup.select("a[href*='/livres/auteur.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("/livres/auteur.asp","https://www.noosfere.org/livres/auteur.asp")
        for elemnt in vol_comment_soup.select("a[href*='/livres/niourf.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("/livres/niourf.asp","https://www.noosfere.org/livres/niourf.asp")
        for elemnt in vol_comment_soup.select("a[href*='/heberg/']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("/heberg/","https://www.noosfere.org/heberg/")
        for elemnt in vol_comment_soup.select("a[href*='prix.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("prix.asp","https://www.noosfere.org/livres/prix.asp")
        for elemnt in vol_comment_soup.select("a[href*='./prix.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("./prix.asp","https://www.noosfere.org/livres/prix.asp")
        for elemnt in vol_comment_soup.select("a[href*='./EditionsLivre.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("./EditionsLivre.asp","https://www.noosfere.org/livres/EditionsLivre.asp")
        for elemnt in vol_comment_soup.select("a[href*='./niourf.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("./niourf.asp","https://www.noosfere.org/livres/niourf.asp")
        for elemnt in vol_comment_soup.select("a[href*='heberg']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("../../heberg","https://www.noosfere.org/heberg")
        for elemnt in vol_comment_soup.select("a[href*='../bd']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("../bd","https://www.noosfere.org/bd")
        for elemnt in vol_comment_soup.select("a[href*='auteur.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("auteur.asp","https://www.noosfere.org/livres/auteur.asp")
        for elemnt in vol_comment_soup.select("a[href*='collection.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("collection.asp","https://www.noosfere.org/livres/collection.asp")
        for elemnt in vol_comment_soup.select("a[href*='critsign.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("critsign.asp","https://www.noosfere.org/livres/critsign.asp")
        for elemnt in vol_comment_soup.select("a[href*='EditionsLivre.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("EditionsLivre.asp","https://www.noosfere.org/livres/EditionsLivre.asp")
        for elemnt in vol_comment_soup.select("a[href*='nouvelle.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("nouvelle.asp","https://www.noosfere.org/livres/nouvelle.asp")
        for elemnt in vol_comment_soup.select("a[href*='editeur.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("editeur.asp","https://www.noosfere.org/livres/editeur.asp")
        for elemnt in vol_comment_soup.select("a[href*='editionslivre.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("editionslivre.asp","https://www.noosfere.org/livres/editionslivre.asp")
        for elemnt in vol_comment_soup.select("a[href*='editionsLivre.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("editionsLivre.asp","https://www.noosfere.org/livres/editionsLivre.asp")
        for elemnt in vol_comment_soup.select("a[href*='niourf.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("niourf.asp","https://www.noosfere.org/livres/niourf.asp")
        for elemnt in vol_comment_soup.select("a[href*='serie.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("serie.asp","https://www.noosfere.org/livres/serie.asp")
        for elemnt in vol_comment_soup.select("a[href*='/articles/article.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("/articles/article.asp","https://www.noosfere.org/articles/article.asp")
        for elemnt in vol_comment_soup.select("a[href*='/articles/theme.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("/articles/theme.asp","https://www.noosfere.org/articles/theme.asp")
        for elemnt in vol_comment_soup.select("a[href*='/articles/listeoeuvres.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("/articles/listeoeuvres.asp","https://www.noosfere.org/articles/listeoeuvres.asp")
        for elemnt in vol_comment_soup.select("a[href*='FicheFilm.asp']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("FicheFilm.asp","https://www.noosfere.org/livres/FicheFilm.asp")
        for elemnt in vol_comment_soup.select("a[href*='?numlivre']"):
            if 'http' not in elemnt.get('href'): elemnt["href"]=elemnt["href"].replace("?numlivre","https://www.noosfere.org/livres/niourf.asp?numlivre")

        if debug:
            for elemnt in vol_comment_soup.select("a[href*='.asp']"):
                if 'http' not in elemnt.get('href'):
                    self.log.info(self.who,"url incomplet apres correction: ", elemnt)

      # I could design from UFT_8 character set a set of right and left arrows but I fake if with ==>>

        fg,fd="<<==","==>>" #chr(0x21D0),chr(0x21D2)   #chr(0x27f8),chr(0x27f9)
        for elemnt in vol_comment_soup.select("img[src*='arrow_left']"): elemnt.replace_with(fg)
        for elemnt in vol_comment_soup.select("img[src*='arrow_right']"): elemnt.replace_with(fd)

      # depending on the tick box, make a fat publisher using separators that have a very low probability to pop up (§ and €)
      # only set vol_coll_srl if vol_coll exists
      # the idea is to use search and replace in the edit Metadata in bulk window.

        if self.extended_publisher:
            if debug:
                self.log.info("\n",self.who,""""Ajoute collection et son numéro d'ordre au champ éditeur" is set""")
            if vol_coll:
                if debug: self.log.info(self.who,'add collection')
                vol_editor = vol_editor+('§')+vol_coll
                if vol_coll_srl:
                    if debug: self.log.info(self.who,'add collection number')
                    vol_editor = vol_editor+('€')+vol_coll_srl

      # UTF-8 characters may be serialized different ways, only xmlcharrefreplace produces xml compatible strings
      # any other non ascii character with another utf-8 byte representation will make calibre behave with the messsage:
      # ValueError: All strings must be XML compatible: Unicode or ASCII, no NULL bytes or control characters
      # Side note:
      # This produce no very good URL structure (I once got html 3 times and div as a sibling of html...), but calibre does not seems to care (nice :-) )
      #
      # Ça m'a pris un temps fou pour trouver, par hasard, que encode('ascii','xmlcharrefreplace') aidait bien...
      # (enfin, quasi par hasard, j' ai essayé tout ce qui pouvait améliorer la compatibilité avec xml... mais je
      # lisais mal et je pensais à une incompatibilité avec la structure xml),
      #
        vol_comment_soup = vol_comment_soup.encode('ascii','xmlcharrefreplace')

        if debug:
            self.log.info("\n",self.who,"+++"*25)
            self.log.info(self.who,"nsfr_id, type()                : ",self.nsfr_id, type(self.nsfr_id))                # must be <class 'str'>
            self.log.info(self.who,"relevance, type()              : ",self.relevance, type(self.relevance))            # must be <class 'float'>
            self.log.info(self.who,"vol_title, type()              : ",vol_title, type(vol_title))                      # must be <class 'str'>
            self.log.info(self.who,"vol_auteur, type()             : ",vol_auteur, type(vol_auteur))                    # must be <class 'list'> of <class 'str'>
            self.log.info(self.who,"vol_serie, type()              : ",vol_serie, type(vol_serie))                      # must be <class 'str'>
            if vol_serie:
                self.log.info(self.who,"vol_serie_seq, type()          : ",vol_serie_seq, type(vol_serie_seq))          # must be <class 'float'>
            self.log.info(self.who,"vol_editor, type()             : ",vol_editor, type(vol_editor))                    # must be <class 'str'>
            self.log.info(self.who,"vol_coll, type()               : ",vol_coll, type(vol_coll))                        # must be <class 'str'>
            self.log.info(self.who,"vol_coll_srl, type()           : ",vol_coll_srl, type(vol_coll_srl))                # must be <class 'str'>
            self.log.info(self.who,"vol_dp_lgl, type()             : ",vol_dp_lgl, type(vol_dp_lgl))                    # must be <class 'datetime.datetime'> ('renderer=isoformat')
            self.log.info(self.who,"vol_isbn, type()               : ",vol_isbn, type(vol_isbn))                        # must be <class 'str'>
            self.log.info(self.who,"vol_genre, type()              : ",vol_genre, type(vol_genre))                      # must be <class 'list'> of <class 'str'>
            self.log.info(self.who,"vol_cover_index, type()        : ",vol_cover_index, type(vol_cover_index))          # must be
     #        self.log.info(self.who,"vol_comment_soup               :\n",vol_comment_soup)                               # a bit long I guess

        if vol_cover_index:
            self.plugin.cache_identifier_to_cover_url(self.nsfr_id, vol_cover_index)

        if vol_isbn:
            self.plugin.cache_isbn_to_identifier(vol_isbn, self.nsfr_id)

        mi = Metadata(vol_title, [vol_auteur])
        mi.set_identifier('nsfr_id', self.nsfr_id)
        mi.publisher = vol_editor
        mi.isbn = vol_isbn
        mi.tags = [vol_genre]
        mi.source_relevance = self.relevance
        mi.has_cover = bool(vol_cover_index)
        if vol_dp_lgl:
            mi.pubdate = vol_dp_lgl
        mi.series = vol_serie
        if vol_serie:
            mi.series_index = vol_serie_seq
        mi.language = "fra"

        mi.comments = vol_comment_soup

#         if debug: self.log.info("\n",self.who,"mi\n",mi,"\n")                     # a bit long I guess
        self.plugin.clean_downloaded_metadata(mi)

        self.result_queue.put(mi)