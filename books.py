
import audible
from dataclasses import dataclass
from dataclasses import field
import json
import os, sys, subprocess, shlex, re
from subprocess import call
from pathlib import Path
from pprint import pprint

#MyAudible Functions
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

def audibleConnect(username, password) -> None:
    filename="/config/code/booktree/maried.json"
    auth = authenticateByLogin(filename, username, password)
    client = audible.Client(auth) 
    return (auth, client) 

def getBookByAsin(client, asin):
    print ("getBookByASIN: {}}", asin)
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
    print ("getBookByAuthorTitle: {}, {}", author, title)
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

def audibleDisconnect(auth):
    # deregister device when done
    auth.deregister_device()

#Author and Narrator Classes
@dataclass
class Contributor:
    name:str
    #books:list[int]= field(default_factory=list)

#Series Class
@dataclass
class Series:
    name:str
    part:int=0

    def getSeriesPart(self):
        if ((len(self.name) > 0) and (self.part > 0)):
            return ""
        else: 
            return "{} #{}".format(self.name, self.part)

#Book Class
@dataclass
class Book:
    asin:str=""
    title:str=""
    subtitle:str=""
    publicationName:str=""
    length:int=0
    duration:str=""
    series:list[Series]= field(default_factory=list)
    authors:list[Contributor]= field(default_factory=list)
    narrators:list[Contributor]= field(default_factory=list)
    files:list[str]= field(default_factory=list)

    def addFiles(self, file):
        self.files.append(file)

    def getFullTitle(self):
        return self.title + ": " + self.subtitle

#Book File Class
@dataclass
class BookFile:
    filename:str
    sourcePath:str
    isMatched:bool=False
    isHardlinked:bool=False
    audibleMatch:Book=None
    ffprobeBook:Book=None
    audibleMatches:list[Book]=field(default_factory=list)

    def __probe_file(self):
        #ffprobe -loglevel error -show_entries format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer -of default=noprint_wrappers=1:nokey=0 -print_format compact "$file")
        cmnd = ['ffprobe','-loglevel','error','-show_entries','format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer', '-of', 'default=noprint_wrappers=1:nokey=0', '-print_format', 'json', self.filename]
        p = subprocess.Popen(cmnd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err =  p.communicate()
        return json.loads(out)
    
    def ffprobe(self):
        #ffprobe the file
        metadata=self.__probe_file()["format"]["tags"]
        #parse and create a book object
        # format|tag:title=In the Likely Event (Unabridged)|tag:artist=Rebecca Yarros|tag:album=In the Likely Event (Unabridged)|tag:AUDIBLE_ASIN=B0BXM2N523
        #{'format': {'tags': {'title': 'MatchUp', 'artist': 'Lee Child - editor, Val McDermid, Charlaine Harris, John Sandford, Kathy Reichs', 'composer': 'Laura Benanti, Dennis Boutsikaris, Gerard Doyle, Linda Emond, January LaVoy, Robert Petkoff, Lee Child', 'album': 'MatchUp'}}}
        book=Book()
        if 'AUDIBLE_ASIN' in metadata: book.asin=metadata["AUDIBLE_ASIN"]
        if 'title' in metadata: book.title=metadata["title"]
        if 'subtitle' in metadata: book.subtitle=metadata["subtitle"]
        #series and part, if provided
        if (('SERIES' in metadata) and ('PART' in metadata)): 
            book.series.append(Series(metadata["SERIES"],metadata["PART"]))
        #parse album, assume it's a series
        if 'album' in metadata: book.series.append(Series(metadata["album"],0))
        #parse authors
        if 'artist' in metadata: 
            for author in metadata["artist"].split(","):
                book.authors.append(Contributor(author))
        #parse narrators
        if 'composer' in metadata: 
            for narrator in metadata["composer"].split(","):
                book.narrators.append(Contributor(narrator))
        #return a book object created from  ffprobe
        self.ffprobeBook=book
        pprint (book)
        return book
    
    def __getAudibleBook(self, product):
        #product is an Audible product json
        print ("Creating a book object for ", product)
        if product is not None:
            book=Book()
            if 'asin' in product: book.asin=product["asin"]
            if 'title' in product: book.title=product["title"]
            if 'subtitle' in product: book.subtitle=product["subtitle"]
            if 'runtime_length_min' in product: book.length=product["runtime_length_min"]
            if 'authors' in product: 
                for author in product["authors"]:
                    book.authors.append(Contributor(author["name"]))
            if 'narrators' in product: 
                for narrator in product["narrators"]:
                    book.narrators.append(Contributor(narrator["name"]))
            if 'publication_name' in product: book.publicationName=product["publication_name"]
            if 'relationships' in product: 
                for relationship in product["relationships"]:
                    #if this relationship is a series
                    if (relationship["relationship_type"] == "series"):
                        book.series.append(Series(relationship["title"], relationship["sequence"]))
            pprint (book)
            return book
        else:
            return None

    def matchBook(self, client):
        #given book file, ffprobe and audiblematches, return the best match
        
        #first, read the ID tags
        ffprobeBook=self.ffprobe()

        #if asin is provided, get Audible by ASIN
        # auth, client = audibleConnect("delunamarie@gmail.com", "##Abc123@m@z0n")
        if len(ffprobeBook.asin) > 0:
            print ("Getting Book by ASIN ", ffprobeBook.asin)
            book=self.__getAudibleBook(getBookByAsin(client, ffprobeBook.asin))
            if book is not None:
                self.audibleMatch=book
                self.isMatched=True
        else:
            # find book by author or title
            print ("Getting Book by Title: {}, {}", ffprobeBook.authors[0].name, ffprobeBook.title )
            books=getBookByAuthorTitle(client, ffprobeBook.authors[0].name, ffprobeBook.title)
            if books is not None:
                print ("Found {} books", len(books))
                for book in books:
                    self.audibleMatches.append(self.__getAudibleBook(book))

            # check if there's an actual Match from Audible
            if (len(self.audibleMatches) > 0):
                for book in self.audibleMatches:
                    # 1) Check if the titles match
                    # print ("Probe: {} and Audible: {}")
                    if ((ffprobeBook.title == book.title) or (ffprobeBook.getFullTitle() == book.getFullTitle())):
                        self.isMatched=True
                        self.audibleMatch=book
        #audibleDisconnect(auth)

    def hardlinkFile(self):
        return self.isHardlinked
    
    def getTargetPaths(self):
        paths=[]
        #Does this book belong in a series?
        if (len(self.audibleMatch.series) > 0):
            for s in self.audibleMatch.series:
                paths.append("/{}/{}/{}".format(self.audibleMatch.authors[0].name, s.name, "{} - {}".format(s.part, self.audibleMatch.title)))
        else:
            paths.append("/{}/{}".format(self.audibleMatch.author[0].name, self.audibleMatch.title))   
        return paths  
    

    
def findFiles(path):
    files=list[BookFile]
    for f in Path(path).rglob('*.m4b'):
        fullpath=f.absolute()
        files.append(BookFile(f, fullpath)) 
    return files  

def main():
    path="/data/torrents/complete/audiobooks"

    matchedFiles=[]
    unmatchedFiles=[]

    print ("Authenticating...\r\n")
    filename="/config/code/myxrename/maried.json"
    #auth = authenticateByFile(filename)
    auth = authenticateByLogin(filename, "delunamarie@gmail.com", "##Abc123@m@z0n")
    client = audible.Client(auth)

    #find all m4b files and attempt to get metadata
    for f in Path(path).rglob('*.m4b'):
        fullpath=f.absolute()
        print ("Processing {} {}", fullpath, f)
        # create a Book File object and add it to the list of files to be processed
        bf=BookFile(f, fullpath)
        # probe this file
        # print ("Performing ffprobe...")
        # bf.ffprobe()
        # do an audible match
        print ("Performing ffprobe and audible match...")
        bf.matchBook(client)
        # if there is match, put it in the to be hardlinked pile
        if bf.isMatched:
            print ("Match found")
            pprint(bf.audibleMatch)
            matchedFiles.append(bf)
        else:
            print ("No Match found")
            pprint(bf.ffprobeBook)
            unmatchedFiles.append(bf)
 
    # deregister device when done
    auth.deregister_device()

    #for files with matches, hardlink them
    for f in matchedFiles:
        bf.hardlinkFile()
        print ("Hardlinking {} to {}", bf.sourcePath, bf.getTargetPaths())

    #for files that didn't match, log them
    for f in unmatchedFiles:
        print ("No matches found for {}", f)

if __name__ == "__main__":
        #start the program
        main()


