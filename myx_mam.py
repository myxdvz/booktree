import requests
import json
import os
import pickle
from pprint import pprint
import myx_classes
import myx_args


#MAM Functions
def searchMAM(session, titleFilename, authors, extension, lang_code=None, audiobook=False, ebook=False, searchIn="myReseed"):
    # fill in mam_id for first run
    headers = {"cookie": f"mam_id={session}"}

    #save cookie for future use
    cookies_filepath = os.path.join(myx_args.params.log_path, 'cookies.pkl')
    sess = requests.Session()

    #test session and cookie
    r = sess.get('https://www.myanonamouse.net/jsonLoad.php', headers=headers, timeout=5)  # test cookie
    if r.status_code != 200:
        raise Exception(f'Error communicating with API. status code {r.status_code} {r.text}')
    else:
        # if os.path.exists(cookies_filepath):
        #     cookies = pickle.load(open(cookies_filepath, 'rb'))
        #     sess.cookies = cookies

        mam_categories = []
        if audiobook:
            mam_categories.append(13) #audiobooks
            mam_categories.append(16) #radio
        if ebook:
            mam_categories.append(14)
        if not mam_categories:
            return None
        
        #put paren around authors and titleFilename
        if len(authors):
            authors = f"({authors})"

        if len(titleFilename):
            titleFilename = f"({titleFilename})"
    
        params = {
            "tor": {
                "text": f'{authors} {titleFilename} {extension} @dummy mamDummy',  # The search string.
                "srchIn": {
                    "title": "true",
                    "author": "true",
                    "fileTypes": "true",
                    "filenames": "true"
                },
                "main_cat": mam_categories,
                "browse_lang": [lang_code] if lang_code else []
            },
        }

        try:
            r = sess.post('https://www.myanonamouse.net/tor/js/loadSearchJSONbasic.php', json=params)

            #print(r.text)
            if r.text == '{"error":"Nothing returned, out of 0"}':
                return None
            
            if myx_args.params.verbose:
                pprint (r.json())

            return (r.json()["data"])
    
        except Exception as e:
            print(f'error searching MAM {e}')

        # save cookies for later
        with open(cookies_filepath, 'wb') as f:
            pickle.dump(sess.cookies, f)

    return None

def getMAMBook(session, titleFilename="", authors="", extension=""):
    books=[]
    mamBook=searchMAM(session, titleFilename, authors, extension, 1, True, False)
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
            if 'series_info'in b:
                #format {"35598": ["Kat Dubois", "5"]}
                if len(b["series_info"]):
                    series_info = json.loads(b["series_info"])
                    for series in series_info.values():
                        s=list(series)
                        book.series.append(myx_classes.Series(str(s[0]), s[1]))    

            if myx_args.params.verbose:
                pprint(b)   
            books.append(book)

    return books

#MAM Functions
def getUser(session, userID):
    # fill in mam_id for first run
    headers = {"cookie": f"mam_id={session}"}

    #save cookie for future use
    cookies_filepath = os.path.join(myx_args.params.log_path, 'cookies.pkl')
    sess = requests.Session()

    #test session and cookie
    r = sess.get('https://www.myanonamouse.net/jsonLoad.php', headers=headers, timeout=5)  # test cookie
    if r.status_code != 200:
        raise Exception(f'Error communicating with API. status code {r.status_code} {r.text}')
    else:
        # if os.path.exists(cookies_filepath):
        #     cookies = pickle.load(open(cookies_filepath, 'rb'))
        #     sess.cookies = cookies

        params = {
            "id": userID,
            "notif": None,
            "pretty": True,
            "snatch_summary": None
        }

        try:
            r = sess.get('https://www.myanonamouse.net/jsonLoad.php', json=params)

            if myx_args.params.verbose:
                print(r.text)
            if r.text == '{"error":"Nothing returned, out of 0"}':
                return None
            
            if myx_args.params.verbose:
                pprint(r.json())

            return (r.json())
    
        except Exception as e:
            print(f'error searching MAM {e}')

        # save cookies for later
        with open(cookies_filepath, 'wb') as f:
            pickle.dump(sess.cookies, f)

    return None

def searchMAMByHash(session, hash=""):
    # fill in mam_id for first run
    headers = {"cookie": f"mam_id={session}"}

    #save cookie for future use
    cookies_filepath = os.path.join(myx_args.params.log_path, 'cookies.pkl')
    sess = requests.Session()

    #test session and cookie
    r = sess.get('https://www.myanonamouse.net/jsonLoad.php', headers=headers, timeout=5)  # test cookie
    if r.status_code != 200:
        raise Exception(f'Error communicating with API. status code {r.status_code} {r.text}')
    else:
        # if os.path.exists(cookies_filepath):
        #     cookies = pickle.load(open(cookies_filepath, 'rb'))
        #     sess.cookies = cookies

        params = {
            "tor": {
                "hash": hash,
                "main_cat": ["0"],
                "browse_lang": []
            },
        }

        try:
            r = sess.post('https://www.myanonamouse.net/tor/js/loadSearchJSONbasic.php', json=params)

            #print(r.text)
            if r.text == '{"error":"Nothing returned, out of 0"}':
                return None
            
            if myx_args.params.verbose:
                pprint (r.json())

            return (r.json()["data"])
    
        except Exception as e:
            print(f'error searching MAM {e}')

        # save cookies for later
        with open(cookies_filepath, 'wb') as f:
            pickle.dump(sess.cookies, f)

    return None


def getMAMBookByHash(session, hash):
    books=[]
    mamBook=searchMAMByHash(session, hash)
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
            if 'series_info'in b:
                #format {"35598": ["Kat Dubois", "5"]}
                if len(b["series_info"]):
                    series_info = json.loads(b["series_info"])
                    for series in series_info.values():
                        s=list(series)
                        book.series.append(myx_classes.Series(str(s[0]), s[1]))    

            if myx_args.params.verbose:
                pprint(b)   
            books.append(book)

    return books
