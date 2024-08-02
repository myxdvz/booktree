import audible
import json
from pathlib import Path
import posixpath
import os, sys, subprocess, shlex, re
from subprocess import call

def getBookByAsin(client, asin):
    print ("getBookByASIN: %s", asin)
    try:
        book = client.get (
            path=f"catalog/products/{asin}",
            params={
                "response_groups": (
                    "sku, series, product_attrs, relationships, contributors,"
                    "product_extended_attrs, product_desc, product_plan_details"
                )
            },
        )
        return book["product"]
    except Exception as e:
        print(e)

def getBookByAuthorTitle(client, author, title):
    print ("getBookByAuthorTitle: {} {}", author, title)
    enBooks=[]
    try:
        books = client.get (
            path=f"catalog/products",
            params={
                "author": author,
                "title": title,
                "response_groups": (
                    "sku, series, product_attrs, relationships, contributors,"
                    "product_extended_attrs, product_desc, product_plan_details"
                )
            },
        )
        for book in books["products"]:
            #ignore non-english books
            if (book["language"] == "english"):
                enBooks.append(book)

        print("Found {} books", len(enBooks))
        return enBooks
    except Exception as e:
        print(e)

def getAuthors (authorList):
    authors=[]
    for author in authorList:
        authors.append(author["name"])
    return ",".join(authors)

def getSeries (relationshipList):
    series=[]
    for relationship in relationshipList:
        #if this relationship is a series
        if (relationship["relationship_type"] == "series"):
            series.append(relationship)
    return series

def printBookInfo(book):
    # print book info
    if (book is not None) :
        #print("Product: %s", book)
        if 'title' in book: print("Title: ", book["title"])
        if 'subtitle' in book: print("Subtitle: ", book["subtitle"])
        if 'runtime_length_min' in book: print("Length: ", book["runtime_length_min"])
        if 'authors' in book: print("Authors: ", getAuthors(book["authors"]))
        if 'publication_name' in book: print("Publication Name: ", book["publication_name"])
        if 'relationships' in book: print("Series: ", prettifySeries(getSeries(book["relationships"])))
    return

def prettifySeries (series):
    s=[]
    for item in series:
        s.append(dict([("series", item["title"]), ("part", item["sequence"]),("seriespart", item["title"] + " #" + item["sequence"])]))
    return s

def getPaths(book):
    paths=[]
    series=[]

    #Get Author, Series, Title
    if 'authors' in book: author=book["authors"][0]["name"]
    if 'title' in book: title=book["title"]
    if 'relationships' in book: series=prettifySeries(getSeries(book["relationships"]))

    #Does this book belong in a series?
    if (len(series) > 0):
        for s in series:
            paths.append("/{}/{}/{}".format(author, s["series"], "{} - {}".format(s["seriespart"], title)))
    else:
        paths.append("/{}/{}".format(author, title))   
    return paths    

def authenticateByFile(authFilename):
    auth = audible.Authenticator.from_file(authFilename)
    return auth

def authenticateByLogin(authFilename, username, password):
    auth = audible.Authenticator.from_login(username, password, locale="us")

    # store credentials to file
    auth.to_file(filename=authFilename, encryption="json", password=password)

    # save again
    auth.to_file()

    # load credentials from file
    auth = audible.Authenticator.from_file(filename=authFilename, password=password)
    return auth

def lookupBooks(books):
    for book in books:
        printBookInfo(book)
        print ("Paths: ", getPaths(book))
        print("\n", 40 * "-", "\n")
    return

def findFiles(path):
    files=[]
    for f in Path(path).rglob('*.m4b'):
        fullpath=f.absolute()
        #print(fullpath)
        files.append(fullpath) 
    return files   

def probe_file(filename):
    #ffprobe -loglevel error -show_entries format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer -of default=noprint_wrappers=1:nokey=0 -print_format compact "$file")
    cmnd = ['ffprobe','-loglevel','error','-show_entries','format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer', '-of', 'default=noprint_wrappers=1:nokey=0', '-print_format', 'json', filename]
    p = subprocess.Popen(cmnd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #print (filename)
    out, err =  p.communicate()
    return json.loads(out)
    
def main():
    # authenticate from saved profile
    print ("Authenticating...\r\n")
    filename="/config/code/myxrename/maried.json"
    #auth = authenticateByFile(filename)
    auth = authenticateByLogin(filename, "delunamarie@gmail.com", "##Abc123@m@z0n")
    client = audible.Client(auth)
 
    # look up a book
    # print ("Looking up Winter Lost: B0719RHHVM")
    # lookupBooks([getBookByAsin (client, "B0719RHHVM")])
    # print ("")
    # print ("Looking up Mr. Mercedes by Stephen King")
    # lookupBooks(getBookByAuthorTitle (client, "Stephen King", "Mr. Mercedes"))
    # print ("")
    # print ("Looking up The Dark Tower by Stephen King")
    # lookupBooks(getBookByAuthorTitle (client, "", "Death's Excellent Vacation"))

    files=findFiles ("/data/torrents/complete/audiobooks")

    for file in files:
        #ffprobe the file
        metadata=probe_file(file)
        tags={}
        for k in metadata["format"]["tags"]:
            tags[k]=metadata["format"]["tags"][k]
        tags["filename"]=file
        print (tags)

        #check Audible
        #is there an ASIN?
        if 'AUDIBLE_ASIN' in tags: 
            lookupBooks([getBookByAsin(client, tags["AUDIBLE_ASIN"])])
        else:
            lookupBooks(getBookByAuthorTitle(client, tags["artist"], tags["title"]))


    # deregister device when done
    auth.deregister_device()

if __name__ == "__main__":
    #start the program
    main()



