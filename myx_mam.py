
import requests
import json
import os
import pickle
from pprint import pprint
import myx_classes
import myx_args


#MAM Functions
def searchMAM(session, title, authors, filename, lang_code=None, audiobook=False, ebook=False):
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
            mam_categories.append(13)
        if ebook:
            mam_categories.append(14)
        if not mam_categories:
            return None
        params = {
            "tor": {
                "text": f'({authors}) "{filename}"',  # The search string.
                "srchIn": {
                    "title": "true",
                    "author": "true",
                    "filenames": "true"
                },
                "main_cat": mam_categories,
                "browse_lang": [lang_code] if lang_code else []
            },
        }

        try:
            r = sess.post('https://www.myanonamouse.net/tor/js/loadSearchJSONbasic.php', json=params)

            if r.text == '{"error":"Nothing returned, out of 0"}':
                return None
            
            return (r.json()['total'], r.json()["data"])
    
        except Exception as e:
            print(f'error searching MAM {e}')

        # save cookies for later
        with open(cookies_filepath, 'wb') as f:
            pickle.dump(sess.cookies, f)

    return None

def getMAMBook(session, title="", authors="", filename=""):
    books=[]
    total, mamBook=searchMAM(session, title, authors, filename, 1, True, False)
    if (mamBook is not None):
        for b in mamBook:
            #pprint(b)
            book=myx_classes.Book()
            book.init()
            if 'asin' in b: 
                book.asin=b["asin"]
            if 'title' in b: 
                book.title=b["title"]
            if 'author_info'in b:
                #format {id:author, id:author}
                if len(b["author_info"]):
                    authors = json.loads(b["author_info"])
                    for author in authors.values():
                        book.authors.append(myx_classes.Contributor(author))
            if 'series_info'in b:
                #format {"35598": ["Kat Dubois", "5"]}
                if len(b["series_info"]):
                    series_info = json.loads(b["series_info"])
                    for series in series_info.values():
                        s=list(series)
                        book.series.append(myx_classes.Series(s[0], s[1]))    

            if myx_args.params.verbose:
                pprint(b)   
            books.append(book)

    return books
