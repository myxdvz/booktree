import requests
import json
import os
import pickle
from pprint import pprint
import myx_classes
import myx_utilities


#MAM Functions
def searchMAM(cfg, titleFilename, authors, extension):
    #Config
    session = cfg.get("Config/session")
    log_path = cfg.get("Config/log_path")
    verbose = bool(cfg.get("Config/flags/verbose"))

    ebook = bool(cfg.get("Config/flags/ebooks"))
    audiobook = not (ebook)
    
    #put paren around authors and titleFilename
    if len(authors):
        authors = f"({authors})"

    if len(titleFilename):
        titleFilename = f'("{titleFilename}")'

    search = f'{authors} {titleFilename} {extension} @dummy mamDummy'

    #cache results for this search string
    cacheKey=myx_utilities.getHash(search)
    
    if myx_utilities.isCached(cacheKey, "mam", cfg):
        #this search has been done before, load results from cache
        results = myx_utilities.loadFromCache(cacheKey, "mam", cfg)
        return (results["data"])
    
    else:
        #save cookie for future use
        cookies_filepath = os.path.join(log_path, 'cookies.pkl')
        sess = requests.Session()

        #a cookie file exists, use that
        if os.path.exists(cookies_filepath):
            cookies = pickle.load(open(cookies_filepath, 'rb'))
            sess.cookies = cookies
        else:
            #assume a session ID is passed as a parameter
            sess.headers.update({"cookie": f"mam_id={session}"})

        #test session and cookie
        try:
            r = sess.get('https://www.myanonamouse.net/jsonLoad.php', timeout=5)  # test cookie
            if r.status_code != 200:
                raise Exception(f'Error communicating with API. status code {r.status_code} {r.text}')
            else:
                # save cookies for later
                with open(cookies_filepath, 'wb') as f:
                    pickle.dump(sess.cookies, f)
                    print (f"Cookie updated...")

                mam_categories = []
                if audiobook:
                    mam_categories.append(13) #audiobooks
                    mam_categories.append(16) #radio
                if ebook:
                    mam_categories.append(14)
                if not mam_categories:
                    return None
                
                params = {
                    "tor": {
                        "text": search,  # The search string.
                        "srchIn": {
                            "title": "true",
                            "author": "true",
                            "fileTypes": "true",
                            "filenames": "true"
                        },
                        "main_cat": mam_categories
                    },
                    "perpage":50
                }

                if (verbose):
                    print(f'Search: {search}')

                try:
                    r = sess.post('https://www.myanonamouse.net/tor/js/loadSearchJSONbasic.php', json=params)
                    if r.text == '{"error":"Nothing returned, out of 0"}':
                        return None

                    results = r.json()

                    #cache this result before returning it
                    if not results["data"] is None and len((results["data"])) > 0:
                        cacheResults = False
                        #parent calls filter to snatched for matching, so check that the result has at least one snatched
                        for book in results["data"]:
                            if not book['my_snatched'] is None and bool(book['my_snatched']):
                                cacheResults = True

                        if cacheResults:
                            myx_utilities.cacheMe(cacheKey, "mam", results, cfg)

                    return (results["data"])
            
                except Exception as e:
                    print(f'error searching MAM {e}')
        except Exception as e:
            print(f'error searching MAM {e}')
            
    return None

def getMAMBook(cfg, titleFilename="", authors="", extension=""):
    books=[]
    mamBook=searchMAM(cfg, titleFilename, authors, extension)
    if (mamBook is not None):
        for b in mamBook:
            #pprint(b)
            book=myx_classes.Book()
            book.init()
            if 'asin' in b: 
                book.asin=str(b["asin"])
            if 'title' in b: 
                book.title=str(b["title"])
            if 'author_info'in b:
                #format {id:author, id:author}
                if len(b["author_info"]):
                    authors = json.loads(b["author_info"])
                    for author in authors.values():
                        book.authors.append(myx_classes.Contributor(str(author)))
            if 'narrator_info'in b:
                #format {id:narrator, id:narrator}
                if ((not b["narrator_info"] is None) and len(b["narrator_info"])):
                    narrators = json.loads(b["narrator_info"])
                    for narrator in narrators.values():
                        book.narrators.append(myx_classes.Contributor(str(narrator)))
            if 'series_info'in b:
                #format {"35598": ["Kat Dubois", "5"]}
                if ((not b["series_info"] is None) and len(b["series_info"])):
                    series_info = json.loads(b["series_info"])
                    for series in series_info.values():
                        s=list(series)
                        seriesName = str(s[0])
                        seriesName = seriesName.replace("&#039;", "'")
                        book.series.append(myx_classes.Series(seriesName, s[1]))
            if 'lang_code' in b:
                book.language=myx_utilities.getLanguage((b["lang_code"]))
            if 'my_snatched' in b:
                book.snatched=bool((b["my_snatched"])) 
            
            if book.snatched:
                books.append(book)

    return books

def testSessionCookie(mySession):
    isSessionCookieValid = False

    #test session and cookie
    #print (f"Cookie: {mySession}")
    try:
        #Hit cookieCheck API, https://www.myanonamouse.net/json/checkCookie.php
        r = mySession.get('https://www.myanonamouse.net/json/checkCookie.php', timeout=5)  # test cookie    

        if r.status_code != 200:
            print(f'Error communicating with API. status code {r.status_code} {r.text}')
        else:
            print (f"Successfully checked cookie: {r.text}")
            isSessionCookieValid = True

    except Exception as e:
        print(f'Checking MAM Cookie {e}')

    return isSessionCookieValid

def checkMAMCookie(cfg):
    #Config
    session = cfg.get("Config/session")
    log_path = cfg.get("Config/log_path")

    isCookieValid = False
    useConfigSession = False
    cookies_filepath = os.path.join(log_path, 'cookies.pkl')
    sess = requests.Session()

    #Check if a cookie file exists
    if os.path.exists(cookies_filepath):
        print (f"Checking if current cookie file is still valid...")
        #If it does, create a session, using this cookie
        cookies = pickle.load(open(cookies_filepath, 'rb'))
        sess.cookies = cookies
        isCookieValid = testSessionCookie (sess)

        #if the session cookie is NOT Valid
        if (not isCookieValid):
            #delete the file
            os.remove(cookies_filepath)
            
            print (f"Found an existing cookie file, but it was invalid. Checking session ID from config...")
            useConfigSession = True
    else:
        #Cookie File not found, use the session ID from Config
        print (f"Cookie file not found, checking session ID from config...")
        useConfigSession = True

    if (useConfigSession):
        if (session is not None) and len(session):
            sess.headers.update({"cookie": f"mam_id={session}"})
            isCookieValid = testSessionCookie (sess)

        else:
            print (f"No session ID found in the config... Please go to MAM Preferences > Security to create a new session")
        

    return isCookieValid