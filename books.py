
from dataclasses import dataclass
from dataclasses import field
import audible
import json
import os, sys, subprocess, shlex, re
from subprocess import call
from pathlib import Path

#Audible Functions
class Audible:
    auth=None
    client=None 
    isAuthenticated=False
    
    @staticmethod
    def connect(username, password) -> None:
        if (Audible.isAuthenticated == True):
            #authenticate
            return Audible.authenticateByLogin(username, password)
        else:
            return Audible.auth

    @staticmethod
    def getBookByAsin(asin):
        print ("getBookByASIN: {}}", asin)
        try:
            book = Audible.client.get (
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

    @staticmethod
    def getBookByAuthorTitle(author, title):
        print ("getBookByAuthorTitle: {} {}", author, title)
        enBooks=[]
        try:
            books = Audible.client.get (
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

    @staticmethod
    def authenticateByLogin(username, password):
        Audible.auth = audible.Authenticator.from_login(username, password, locale="us")
        return Audible.auth

    @staticmethod
    def disconnect(self):
        # deregister device when done
        Audible.auth.deregister_device()

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
    asin:str
    title:str
    subtitle:str
    publicationName:str
    length:int
    duration:str
    series:list[Series]= field(default_factory=list)
    authors:list[Contributor]= field(default_factory=list)
    narrators:list[Contributor]= field(default_factory=list)
    files:list[str]= field(default_factory=list)

    def addFiles(self, file):
        self.files.append(file)

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
        metadata=self.__probe_file()
        #parse and create a book object
        # format|tag:title=In the Likely Event (Unabridged)|tag:artist=Rebecca Yarros|tag:album=In the Likely Event (Unabridged)|tag:AUDIBLE_ASIN=B0BXM2N523
        #{'format': {'tags': {'title': 'MatchUp', 'artist': 'Lee Child - editor, Val McDermid, Charlaine Harris, John Sandford, Kathy Reichs', 'composer': 'Laura Benanti, Dennis Boutsikaris, Gerard Doyle, Linda Emond, January LaVoy, Robert Petkoff, Lee Child', 'album': 'MatchUp'}}}
        book=Book()
        book.asin=metadata["format"]["tags"]["ADUIBLE_ASIN"]
        book.title=metadata["format"]["tags"]["title"]
        book.subtitle=metadata["format"]["tags"]["title"]
        #series and part, if provided
        book.series.append(Series(metadata["format"]["tags"]["SERIES"],metadata["format"]["tags"]["PART"]))
        #parse album, assume it's a series
        book.series.append(Series(metadata["format"]["tags"]["album"],0))
        #parse authors
        for author in list(metadata["format"]["tags"]["artist"]):
            book.authors.append(Contributor(author,[]))
        #parse narrators
        for narrator in list(metadata["format"]["tags"]["composer"]):
            book.narrators.append(Contributor(author,[]))
        #return a book object created from  ffprobe
        self.ffprobeBook=book
        return book
    
    def __getAudibleBook(self, product):
        #product is an Audible product json
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
        return book

    def matchBook(self):
        #given book file, ffprobe and audiblematches, return the best match
        
        #first, read the ID tags
        ffprobeBook=self.ffprobe()

        #if asin is provided, get Audible by ASIN
        Audible.connect("delunamarie@gmail.com", "##Abc123@m@z0n")
        if len(ffprobeBook.asin) > 0:
            self.audibleMatch=self.__getAudibleBook(Audible.getBookByAsin(ffprobeBook.asin))
            self.isMatched=(len(self.audibleMatch.title) > 0)
        else:
            # find book by author or title
            for book in Audible.getBookByAuthorTitle(ffprobeBook.authors, ffprobeBook.title):
                self.audibleMatches.append(self.__getAudibleBook(book))

            # check if there's an actual Match from Audible
            for book in self.audibleMatches:
                # 1) Check if the titles match
                if (ffprobeBook.title == book.title):
                    self.isMatched=True
                    self.audibleMatch=book
        Audible.disconnect()

    def hardlinkFile(self):
        return self.isHardlinked
    
    def getTargetPaths(self):
        paths=[]
        #Does this book belong in a series?
        if (len(self.audibleMatch.series) > 0):
            for s in self.audibleMatch.series:
                paths.append("/{}/{}/{}".format(self.audibleMatch.author, s.name, "{} - {}".format(s.part, self.audibleMatch.title)))
        else:
            paths.append("/{}/{}".format(self.audibleMatch.author, self.audibleMatch.title))   
        return paths  
    
def findFiles(path):
    files=list[BookFile]
    for f in Path(path).rglob('*.m4b'):
        fullpath=f.absolute()
        files.append(BookFile(f, fullpath)) 
    return files  

def main():
    path="/data/torrents/complete/audiobooks"

    matchedFiles=list[BookFile]
    unmatchedFiles=list[BookFile]

    #find all m4b files and attempt to get metadata
    for f in Path(path).rglob('*.m4b'):
        fullpath=f.absolute()
        # create a Book File object and add it to the list of files to be processed
        bf=BookFile(f, fullpath)
        # probe this file
        bf.ffprobe()
        # do an audible match
        bf.matchBook()
        # if there is match, put it in the to be hardlinked pile
        if bf.isMatched:
            matchedFiles.append(bf)
        else:
            unmatchedFiles.append(bf)
 
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


