#!/usr/bin/env python3
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = 'Louis Richard Pirlet'
__docformat__ = 'restructuredtext en'

from calibre import prints
from calibre.constants import DEBUG

from calibre.gui2.actions import menu_action_unique_name
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.sources.search_engines import rate_limit
from calibre_plugins.babelio_notes.config import prefs

import urllib                                   # to access the web
from bs4 import BeautifulSoup as BS             # to dismantle and manipulate HTTP (HyperText Markup Language) a text formated utf-8
import time, datetime

TIME_INTERVAL = 1.2      # this is the minimum interval between 2 access to the web (with decorator on ret_soup())

class Un_par_un(object):
    '''
    This is a class decorator, cause I am too lazy to rewrite that plugin... :),
    beside I want to learn creating one. Well, granted, dedicated to ret_soup()

    Purpose: execute the decorated function with a minimum of x seconds
    between each execution, and collect all access time information...

    rate_limit() from calibre.ebooks.metadata.sources.search_engines provides the delay
    using a locked file containing the access time... maintenance of this resource
    is hidden in a context manager implementation.

    @contextmanager
    def rate_limit(name='test', time_between_visits=2, max_wait_seconds=5 * 60, sleep_time=0.2):

    I assume that calibre will wait long enough for babelio plugin (I pushed to 45 sec after first match)
    '''
    def __init__(self,fnctn):
        self.function = fnctn
        self._memory = []

    def __call__(self, *args, **kwargs):
        # note : name='Babelio_db' so we interleave with babelio_db would this plugin be used at the same time
        with rate_limit(name='Babelio_db', time_between_visits=TIME_INTERVAL):
          # call decorated function: "ret_soup" whose result is (soup,url)
            result = self.function(*args, **kwargs)
            self._memory.append((result[1], time.asctime()))
            return result

    def get_memory(self):
        mmry = self._memory
        self._memory = []
        return mmry

@Un_par_un
def ret_soup(br, url, rkt=None):
    '''
    Function to return the soup for beautifullsoup to work on. with:
    br the mechanize browser, url the request address, rkt the
    arguments for a POST request, if rkt is None, the request is GET...
    Un_par_un introduce a wait time to avoid DoS attack detection,
    soup is the response from the URL, formatted utf-8 (no decode needed).
    url_ret is the URL address of soup as reported by br.
    return (soup, url_ret)
    '''
    if DEBUG:
        prints("DEBUG In ret_soup(log, dbg_lvl, br, url, rkt=none, who=''\n")
        prints("DEBUG URL request time : ", datetime.datetime.now().strftime("%H:%M:%S"))
    start = time.time()
    if DEBUG:
        prints("DEBUG br                : ", br)
        prints("DEBUG url               : ", url)
        prints("DEBUG rkt               : ", rkt)

    prints("Accessing url     : ", url)
    if rkt :
        prints("search parameters : ",rkt)
        rkt=urllib.parse.urlencode(rkt).encode('ascii')
        if DEBUG: prints("DEBUG formated parameters : ", rkt)

    try:
        sr = br.open(url,data=rkt,timeout=30)
        prints("(ret_soup) sr.getcode()  : ", sr.getcode())
        if DEBUG:
            prints("DEBUG url_vrai      : ", sr.geturl())
            prints("DEBUG sr.info()     : ", sr.info())
        url_ret = sr.geturl()
    except urllib.error.URLError as e:
        prints("exception occured...")
        prints("code : ",e.code,"reason : ",e.reason)
        raise Exception('(urlopen_with_retry) Failed while acessing url : ',url)
    soup = BS(sr, "html5lib")

    # if DEBUG: prints("DEBUG soup.prettify() :\n",soup.prettify())               # hide_it # très utile parfois, mais que c'est long...
    return (soup, url_ret)

def create_menu_action_unique(ia, parent_menu, menu_text, image=None, tooltip=None,
                       shortcut=None, triggered=None, is_checked=None, shortcut_name=None,
                       unique_name=None, favourites_menu_unique_name=None):
    '''
    Create a menu action with the specified criteria and action, using the new
    InterfaceAction.create_menu_action() function which ensures that regardless of
    whether a shortcut is specified it will appear in Preferences->Keyboard
    '''

    # extracted from common_utils.py, found in many plugins ... header as follow:
    #
    # __license__   = 'GPL v3'
    # __copyright__ = '2011, Grant Drake <grant.drake@gmail.com>
    # __docformat__ = 'restructuredtext en'
    #
    # change to notice is the use of get_icons instead of get_icon in:
    #    ac.setIcon(get_icons(image))
    # ok, to be honest I could make this one work... I had lots of
    # difficulties with the many common_utils.py files that have the same name
    # but different content...

    orig_shortcut = shortcut
    kb = ia.gui.keyboard
    if unique_name is None:
        unique_name = menu_text
    if not shortcut is False:
        full_unique_name = menu_action_unique_name(ia, unique_name)
        if full_unique_name in kb.shortcuts:
            shortcut = False
        else:
            if shortcut is not None and not shortcut is False:
                if len(shortcut) == 0:
                    shortcut = None
                else:
                    shortcut = _(shortcut)

    if shortcut_name is None:
        shortcut_name = menu_text.replace('&','')

    ac = ia.create_menu_action(parent_menu, unique_name, menu_text, icon=None, shortcut=shortcut,
        description=tooltip, triggered=triggered, shortcut_name=shortcut_name)
    if shortcut is False and not orig_shortcut is False:
        if ac.calibre_shortcut_unique_name in ia.gui.keyboard.shortcuts:
            kb.replace_action(ac.calibre_shortcut_unique_name, ac)
    if image:
        ac.setIcon(get_icons(image))
    if is_checked is not None:
        ac.setCheckable(True)
        if is_checked:
            ac.setChecked(True)
    return ac
