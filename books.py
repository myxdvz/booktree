
import audible
from dataclasses import dataclass
from dataclasses import field
import json
import os, sys, subprocess, shlex, re
from subprocess import call
from pathlib import Path
from pprint import pprint
import posixpath
import csv
from datetime import datetime
from thefuzz import fuzz

#Utilities
def getList(items, field="name", delimiter=","):
    return delimiter.join([str(item.name) for item in items])

def fuzzymatch(x:str, y:str):
    #remove .:_-, for fuzzymatch
    symbols=".:_-'[]"
    newX=x.replace(symbols, "")
    newY=y.replace(symbols, "")
    if (len(newX) and len(newY)):
        newZ=fuzz.token_sort_ratio(newX, newY)
        print ("{} Fuzzy Match {}={}".format(newZ, newX, newY))
        return newZ
    else:
        return 0
    
def optimizeKeys(keywords):
    #keywords is a list of stuff, we want to convert it in a comma delimited string
    kw=[]
    for k in keywords:
        print (k)
        k=k.replace("[","").replace("]","").replace("{","").replace("}","")
        #parse this item "-"
        for i in k.split("-"):
            #parse again on spaces
            for j in i.split():
                #if it's numeric like 02, make it an actual digit
                if (j.isdigit()):
                    kw.append(int(j))
                else:
                    kw.append(j)

    #now return comma delimited string
    return ' '.join(map(str, kw)) 

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

def getAudibleBook(client, asin="", title="", authors="", narrators="", keywords=""):
    print ("getAudibleBook >> asin:{}, authors:{}, parent:{}, narrators:{}, keywords:{} ".format(asin, authors, title.replace(" (Unabridged)",""), narrators, keywords))
    enBooks=[]
    try:
        books = client.get (
            path=f"catalog/products",
            params={
                "asin": asin,
                "title": title.replace(" (Unabridged)",""),
                "author": authors,
                "narrator": narrators,
                "keywords": keywords,
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

        print("Found ", len(enBooks), " books")
        return enBooks
    except Exception as e:
        print(e)

def getBookByAsin(client, asin):
    print ("getBookByASIN: ", asin)
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
    print ("getBookByAuthorTitle: ", author, ", ", title)
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

        print("Found ", len(enBooks), " books")
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
        if (str(self.part) != "0"):
            return "{} #{}".format(self.name, str(self.part))
        else:
            return self.name

#Book Class
@dataclass
class Book:
    asin:str=""
    title:str=""
    subtitle:str=""
    publicationName:str=""
    length:int=0
    duration:str=""
    matchRate=0
    series:list[Series]= field(default_factory=list)
    authors:list[Contributor]= field(default_factory=list)
    narrators:list[Contributor]= field(default_factory=list)
    files:list[str]= field(default_factory=list)

    def addFiles(self, file):
        self.files.append(file)

    def getFullTitle(self, field="subtitle"):
        title=""
        if field == "series":
            if (len(self.series) > 0):
                title= self.title + ": " + self.series[0].getSeriesPart()
        else:
            title=self.title + ": " + self.subtitle
        
        return title
    
    def getCleanTitle(self):
        #Removes (Unabdridged from the title)
        return self.title.replace (" (Unabridged)","")
    
    def getAuthors(self, delimiter=","):
        return getList(self.authors)
    
    def getSeries(self, delimiter=","):
        return getList(self.series)
    
    def getNarrators(self, delimiter=","):
        return getList(self.narrators) 
    
    def getSeriesParts(self, delimiter=","):
        return delimiter.join([str(s.getSeriesPart()) for s in self.series])

    def getDictionary(self, book):
        book["matchRate"]=self.matchRate
        book["asin"]=self.asin
        book["title"]=self.title
        book["subtitle"]=self.subtitle
        book["publicationName"]=self.publicationName
        book["length"]=self.length
        book["duration"]=self.duration
        book["series"]=self.getSeries()
        book["authors"]=self.getAuthors()
        book["narrators"]=self.getNarrators()
        book["seriesparts"]=self.getSeriesParts()
        return book  
    
#Book File Class
@dataclass
class BookFile:
    file:posixpath
    sourcePath:str
    isMatched:bool=False
    isHardlinked:bool=False
    audibleMatch:Book=None
    ffprobeBook:Book=None
    audibleMatches:dict=field(default_factory=dict)

    def getParentFolder(self):
        return (os.path.dirname(self.sourcePath).split("/")[-1])

    def __probe_file(self):
        #ffprobe -loglevel error -show_entries format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer -of default=noprint_wrappers=1:nokey=0 -print_format compact "$file")
        cmnd = ['ffprobe','-loglevel','error','-show_entries','format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer', '-of', 'default=noprint_wrappers=1:nokey=0', '-print_format', 'json', self.sourcePath]
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
        
    def matchBook(self, client, matchRate=75):
        #given book file, ffprobe and audiblematches, return the best match
        parent = self.getParentFolder().replace(" (Unabridged)", "")

        #first, read the ID tags
        ffprobeBook=self.ffprobe()
        asin=ffprobeBook.asin
        keywords=optimizeKeys([parent])

        #catalog/products asin, author, title, keywords
        # books=getAudibleBook(client, asin, ffprobeBook.getAuthors(), parent, keywords)
        # if books is not None:
        #     print ("Found {} books".format(len(books)))
        #     for book in books:
        #         self.audibleMatches[book["asin"]]=self.__getAudibleBook(book)

        # Strategy#1:  If an ASIN was in the ID Tag, search by ASIN
        if len(ffprobeBook.asin) > 0:
            print ("Getting Book by ASIN ", ffprobeBook.asin)
            book=self.__getAudibleBook(getBookByAsin(client, ffprobeBook.asin))
            if ((book is not None) and (fuzzymatch(ffprobeBook.title, book.title) > matchRate)):
                self.audibleMatch=book
                self.isMatched=True

        # Strategy #2:  ASIN search was a bust, try a wider search (Author, Title, Keywords)
        #asin might be available but a match wasn't found, try Author/Title Search        
        if (not self.isMatched):
            fBook=""

            #check if an author was found
            if (len(ffprobeBook.authors) == 0):
                author=""
            else:
                author=ffprobeBook.authors[0].name

            #Use Case:  Bad ID3 tags, Use Parent Folder, assume it's the title and/or the author
            if ((len(author)==0) and len(ffprobeBook.title) ==0):
                # Option #1: find book by artist or title (using parent folder)
                print ("Getting Book by Keyword: {}".format(keywords))
                books=getAudibleBook(client, keywords=keywords)
                if books is not None:
                    print ("Found {} books".format(len(books)))
                    for book in books:
                        self.audibleMatches[book["asin"]]=self.__getAudibleBook(book)
                        #self.audibleMatches.append(self.__getAudibleBook(book))
                # For Fuzzy Match, just use Keywords
                fBook=keywords
            else:
                #there's at least some metadata available
                fBook="{},{},{},{},{}".format(ffprobeBook.title,ffprobeBook.subtitle, ffprobeBook.getAuthors("|"), ffprobeBook.getNarrators("|"),ffprobeBook.getSeriesParts())

                #Use Case : Clean ID3, there's an author, a title, a narrator
                if (len(ffprobeBook.title) and (len(ffprobeBook.getAuthors()) or len(ffprobeBook.getNarrators()))):
                    print ("Getting Book by Author: {}, Title: {}, Narrator: {}".format(ffprobeBook.getAuthors(), ffprobeBook.title, ffprobeBook.getNarrators()))
                    books=getAudibleBook(client, authors=ffprobeBook.getAuthors(), title=ffprobeBook.title, narrators=ffprobeBook.getNarrators())
                    if books is not None:
                        print ("Found {} books".format(len(books)))
                        for book in books:
                            self.audibleMatches[book["asin"]]=self.__getAudibleBook(book)
                            #self.audibleMatches.append(self.__getAudibleBook(book))             

                if (len(self.audibleMatches) == 0):
                    #Use Case: Author, Title, Narrator is too narrow - we're putting these values as keywords
                    if (len(ffprobeBook.title) and (len(ffprobeBook.getAuthors()))):
                        keywords=optimizeKeys([ffprobeBook.title,ffprobeBook.getAuthors()])
                        print ("Getting Book by Keyword using Author/Title as keywords {}".format(keywords))
                        books=getAudibleBook(client, keywords=keywords)
                        if books is not None:
                            print ("Found {} books".format(len(books)))
                            for book in books:
                                self.audibleMatches[book["asin"]]=self.__getAudibleBook(book)
                                #self.audibleMatches.append(self.__getAudibleBook(book))             

                    #Use Case: Clean ID3, but didn't find a match, try a wider search - normally because it's a multi-file book and the parent folder is the title
                    if (len(self.audibleMatches) == 0):
                        print ("Performing wider search...")

                        # Use Case: ID3 has the author, the parent folder is ONLY the title
                        print ("Getting Book by Parent Folder Title: {}, {}".format(author, parent))
                        books=getBookByAuthorTitle(client, author, parent)
                        if books is not None:
                            print ("Found {} books".format(len(books)))
                            for book in books:
                                self.audibleMatches[book["asin"]]=self.__getAudibleBook(book)
                                #self.audibleMatches.append(self.__getAudibleBook(book))

                        # Use Case:  ID3 has the author, and the album is the title
                        if (len(ffprobeBook.series) > 0):
                            print ("Getting Book by Album Title: {}, {}".format(author, ffprobeBook.series[0].name))
                            if (len(ffprobeBook.series) > 0):
                                books=getBookByAuthorTitle(client, author, ffprobeBook.series[0].name)
                                if books is not None:
                                    print ("Found {} books".format(len(books)))
                                    for book in books:
                                        self.audibleMatches[book["asin"]]=self.__getAudibleBook(book)
                                        #self.audibleMatches.append(self.__getAudibleBook(book)) 

            # check if there's an actual Match from Audible
            # if there's exactly 1 match, assume it's good
            if (len(self.audibleMatches) == 1):
                for i in self.audibleMatches.values():
                    self.audibleMatch=i
                    self.isMatched=True
            else:
                print ("Finding the best match out of {}".format(len(self.audibleMatches)))
                if (len(self.audibleMatches) > 1):
                    #find the highest match, start with 0
                    bestMatchRatio=0
                    bestMatchedBook=None
                    for book in self.audibleMatches.values():
                        #do fuzzymatch with all these combos, get the highest value
                        aBook="{},{},{},{},{}".format(book.title, book.subtitle, book.getAuthors("|"), book.getNarrators("|"), book.getSeriesParts("|"))
                        matchRatio=fuzzymatch(fBook,aBook)

                        #set this books matchRatio
                        book.matchRate=matchRatio
                        
                        if (matchRatio > bestMatchRatio):
                            print("Found a better match!{} > {}", matchRatio, bestMatchRatio)
                            #this is the new best
                            bestMatchRatio = matchRatio
                            bestMatchedBook = book

                        if (bestMatchRatio > matchRate):
                            self.isMatched=True
                            self.audibleMatch=bestMatchedBook
                            print ("{} Match found: {}".format(bestMatchRatio, bestMatchedBook.title))
 
    def hardlinkFile(self, source, target):
        #add target to base Media folder
        destination = os.path.join("/data/media/audiobooks/mam", target)
        print ("Destination {}-{}".format(destination, os.path.join("/data/media/audiobooks/test", target)))
        #check if the target path exists
        if (not os.path.exists(destination)):
            #make dir path
            print ("Creating target directory ", destination)
            os.makedirs(destination)
        
        #check if the file already exists in the target directory
        filename=os.path.join(destination, os.path.basename(source).split('/')[-1])
        if (not os.path.exists(filename)):
            print ("Hardlinking {} to {}", source, filename)
            os.link(source, filename)
            self.isHardlinked=True
        return self.isHardlinked
    
    def getTargetPaths(self, book):
        paths=[]
        #Get primary author
        if (len(book.authors) == 0):
            author="Unknown"
        else:
            author=book.authors[0].name  

        #Does this book belong in a series?
        if (len(book.series) > 0):
            for s in book.series:
                paths.append("{}/{}/{} #{} - {}/".format(author, s.name, s.name, s.part, book.title))
        else:
            paths.append("{}/{}/".format(author, book.title))   
        return paths  
    
    def getLogRecord(self, bookMatch:Book):
        #returns a dictionary of the record that gets logged
        book={
            "file":self.sourcePath,
            "isMatched": self.isMatched,
            "isHardLinked": self.isHardlinked,
        }

        book=bookMatch.getDictionary(book)
        book["paths"]=",".join(self.getTargetPaths(bookMatch))

        return book
    
def createHardLinks(bookFiles:list[BookFile], targetFolder="", dryRun=False):
    #hard link all the books in the list
    for f in bookFiles:
        #use Audible metadata or ID3 metadata
        if f.isMatched:
            book=f.audibleMatch
        else:
            book=f.ffprobeBook
        #if a book belongs to multiple series, hardlink them to tall series
        for p in f.getTargetPaths(f.audibleMatch):
            if (not dryRun):
                f.hardlinkFile(f.sourcePath, os.path.join(targetFolder,p))
            print ("Hardlinking {} to {}".format(f.sourcePath, os.path.join(targetFolder,p)))
        print("\n", 40 * "-", "\n")

def logBookRecords(logFilePath, bookFiles:list[BookFile]):

    write_headers = not os.path.exists(logFilePath)
    with open(logFilePath, mode="a", newline="", errors='ignore') as csv_file:
        try:
            for f in bookFiles:
                #get book records to log
                if (f.isMatched):
                    row=f.getLogRecord(f.audibleMatch)
                else:
                    row=f.getLogRecord(f.ffprobeBook)
                #get fieldnames
                row["audiblematches"]=len(f.audibleMatches)
                fields=row.keys()

                #create a writer
                writer = csv.DictWriter(csv_file, fieldnames=fields)
                if write_headers:
                    writer.writeheader()
                    write_headers=False
                writer.writerow(row)

                #if there was no match, log the Audible Matches found
                #if (not f.isMatched):
                    #pprint (f)
                    # for m in f.audibleMatches.values():
                    #     row=f.getLogRecord(m)
                    #     row["isMatched"]="Maybe"
                    #     writer.writerow(row)

        except csv.Error as e:
            print("file {}: {}".format(logFilePath, e))

def main():
    path="/data/torrents/complete/seeding/abs"
    mediaPath="/data/media/audiobooks/mam"
    logfile="/config/code/myxrename/booktree_log_{}.csv".format(datetime.now().strftime("%Y%m%d%H%M%S"))
    
    matchedFiles=[]
    unmatchedFiles=[]

    print ("Authenticating...\r\n")
    filename="/config/code/myxrename/maried.json"
    #auth = authenticateByFile(filename)
    auth = authenticateByLogin(filename, "delunamarie@gmail.com", "##Abc123@m@z0n")
    #auth = audible.Authenticator.from_login_external(locale="us")
    client = audible.Client(auth)

    #find all m4b files and attempt to get metadata
    for f in Path(path).rglob('*.m4b'):
        fullpath=f.absolute()
        print ("Processing {}".format(fullpath))
        # create a Book File object and add it to the list of files to be processed
        bf=BookFile(f, fullpath)
        # probe this file
        # print ("Performing ffprobe...")
        # bf.ffprobe()
        # do an audible match
        print ("Performing ffprobe and audible match...")
        bf.matchBook(client,50)
        # if there is match, put it in the to be hardlinked pile
        if bf.isMatched:
            print ("Match found")
            pprint(bf.audibleMatch)
            matchedFiles.append(bf)
        else:
            print ("No Match found")
            pprint(bf.ffprobeBook)
            unmatchedFiles.append(bf)
        print("\n", 40 * "-", "\n")
 
    # deregister device when done
    auth.deregister_device()

    #for files with matches, hardlink them
    #print ("Creating hard links for matched files...")
    #createHardLinks(matchedFiles, mediaPath)

    #log matched files
    print ("Logging matched books...")
    logBookRecords(logfile, matchedFiles)

    #for files with matches, hardlink them
    print ("Creating hard links for matched files...")
    createHardLinks(unmatchedFiles, mediaPath)

    #log unmatched files
    print ("Logging unmatched books...")
    logBookRecords(logfile, unmatchedFiles)


if __name__ == "__main__":

    #start the program
    main()


