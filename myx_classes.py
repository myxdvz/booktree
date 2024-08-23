
from dataclasses import dataclass
from dataclasses import field
import os, sys, subprocess, shlex, re
from pprint import pprint
import json
import posixpath
import math
import httpx
import itertools
from itertools import permutations 
from pathvalidate import sanitize_filename
import myx_utilities
import myx_audible
import myx_args
import myx_mam

#Module variables
authMode="login"
verbose=False

#Author and Narrator Classes
@dataclass
class Contributor:
    name:str
    #books:list[int]= field(default_factory=list)

#Series Class
@dataclass
class Series:
    name:str=""
    part:str=""
    
    def getSeriesPart(self):
        if (len(self.part.strip()) > 0):
            return f"{self.name} #{str(self.part)}"
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
    duration:float=0
    matchRate=0
    language="english"
    snatched=False
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
        return myx_utilities.cleanseTitle(self.title, True, True)
    
    def getAuthors(self, delimiter=",", encloser="", stripaccents=True):
        if len(self.authors):
            return myx_utilities.getList(self.authors, delimiter, encloser, stripaccents=True)
        else:
            return ""
    
    def getSeries(self, delimiter=",", encloser="", stripaccents=True):
        if len(self.series):
            return myx_utilities.getList(self.series, delimiter, encloser, stripaccents=True)
        else:
            return ""
    
    def getNarrators(self, delimiter=",", encloser="", stripaccents=True):
        if len(self.narrators):
            return myx_utilities.getList(self.narrators, delimiter, encloser, stripaccents=True) 
        else:
            return ""
    
    def getSeriesParts(self, delimiter=",", encloser="", stripaccents=True):
        seriesparts = []
        for s in self.series:
            if len(s.name.strip()):
                seriesparts.append(Contributor(f"{s.name} #{s.part}")) 
            
        return myx_utilities.getList(seriesparts, delimiter, encloser, stripaccents=True) 
    
    def setAuthors(self, authors):
        #Given a csv of authors, convert it to a list
        if len(authors.strip()):
            for author in authors.split (","):
                self.authors.append(Contributor(author))

    def setSeries(self, series):
        #Given a csv of authors, convert it to a list
        #print (f"Parsing series {series}")
        if len(series.strip()):
            for s in list([series]):
                p = s.split("#")
                #print (f"Series: {s}\nSplit: {p}")
                if len(p) > 1: 
                    self.series.append(Series(str(p[0]).strip(), str(p[1]).strip()))
                else:
                    self.series.append(Series(str(p[0]).strip(), ""))
            
    def getDictionary(self, book, ns=""):
        book[f"{ns}matchRate"]=self.matchRate
        book[f"{ns}asin"]=self.asin
        book[f"{ns}title"]=self.title
        book[f"{ns}subtitle"]=self.subtitle
        book[f"{ns}publicationName"]=self.publicationName
        book[f"{ns}length"]=self.length
        book[f"{ns}duration"]=self.duration
        book[f"{ns}series"]=self.getSeries()
        book[f"{ns}authors"]=self.getAuthors()
        book[f"{ns}narrators"]=self.getNarrators()
        book[f"{ns}seriesparts"]=self.getSeriesParts()
        return book  
    
    def init(self):
        self.asin=""
        self.title=""
        self.subtitle=""
        self.publicationName=""
        self.duration=""
        self.series=[]
        self.authors=[]
        self.narrators=[]

    def getAllButTitle(self):
        book={}
        book=self.getDictionary(book)
        book["title"]=""
        return book
    
    def createOPF(self, path):
        #creates an OPF file for this book at the specified path
        myx_utilities.createOPF(self, path)

          
#Book File Class
@dataclass
class BookFile:
    file:posixpath
    fullPath:str
    sourcePath:str
    isMatched:bool=False
    isHardlinked:bool=False
    audibleMatch:Book=None
    ffprobeBook:Book=None
    #audibleMatches:dict=field(default_factory=dict)
    audibleMatches:list[Book]= field(default_factory=list)

    def getExtension(self):
        return os.path.splitext(self.file)[1].replace(".","")

    def hasNoParentFolder(self):
        return (len(self.getParentFolder())==0)
    
    def getParentFolder(self):
        parent = myx_utilities.getParentFolder(self.file, self.sourcePath)
        return parent

    def getFileName(self):
        return os.path.basename(self.file)
        
    def __probe_file__ (self):
        #ffprobe -loglevel error -show_entries format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer -of default=noprint_wrappers=1:nokey=0 -print_format compact "$file")
        cmnd = ['ffprobe','-loglevel','error','-show_entries','format_tags:format=duration', '-of', 'default=noprint_wrappers=1:nokey=0', '-print_format', 'json', self.fullPath]
        p = subprocess.Popen(cmnd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err =  p.communicate()
        #pprint(json.loads(out))
        return json.loads(out)

    def __getBookFromTag__ (self, id3Title, book):
        return myx_utilities.getBookFromTag (id3Title, book)
    
    def ffprobe(self, parent):
        #ffprobe the file
        duration=0
        try:
            r = self.__probe_file__()
            duration = float(r["format"]["duration"])
            metadata= r["format"]["tags"]
        except Exception as e:
            metadata=dict()
            if myx_args.params.verbose:
                print (f"ffprobe failed on {self.file}: {e}")

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
        if 'album' in metadata: book.series.append(Series(metadata["album"],""))
        #parse authors
        if 'artist' in metadata: 
            for author in metadata["artist"].split(","):
                book.authors.append((Contributor(myx_utilities.removeGA(author))))
        #parse narrators
        if 'composer' in metadata: 
            for narrator in metadata["composer"].split(","):
                book.narrators.append(Contributor(narrator))
        #duration in minutes
        book.duration = duration
        
        #return a book object created from  ffprobe
        self.ffprobeBook=book
        if verbose:
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
    
    def hardlinkFile(self, source, target):
        #add target to base Media folder
        destination = os.path.join(myx_args.params.media_path, target)
        #check if the target path exists
        if (not os.path.exists(destination)):
            #make dir path
            print (f"Creating target directory: {destination} ")
            os.makedirs(destination, exist_ok=True)
        
        #check if the file already exists in the target directory
        filename=os.path.join(destination, os.path.basename(source).split('/')[-1])
        if (not os.path.exists(filename)):
            try:
                print (f"Hardlinking {source} to {filename}")
                os.link(source, filename)
                self.isHardlinked=True
            except Exception as e:
                print (f"Failed to hardlink {source} to {filename} due to {e}")
        else:
            print (f"Skipped Hardlinking {source} to {filename} : exists")
                
        return self.isHardlinked
    
    def getTargetPaths(self, book):
        paths=[]
        if (book is not None):
            #Get primary author
            if ((book.authors is not None) and (len(book.authors) == 0)):
                author="Unknown"
            else:
                author=book.authors[0].name  

            #standardize author name (replace . with space, and then make sure that there's only single space)
            stdAuthor=sanitize_filename(myx_utilities.cleanseAuthor(author))

            #is this a MultiCd file?
            disc = self.getParentFolder()
            #print (f"File: {self.file}\nParent: {disc}")

            if (not myx_utilities.isMultiCD(disc)):
                disc = ""

            #Does this book belong in a series - only take the first series?
            sPath=""
            if (len(book.series) > 0):
                sPath=os.path.join(stdAuthor, sanitize_filename(myx_utilities.cleanseSeries(book.series[0].name)), 
                                        sanitize_filename(f"{myx_utilities.cleanseSeries(book.series[0].getSeriesPart())} - {myx_utilities.cleanseTitle(book.title)}"),
                                        sanitize_filename(disc))
            else:
                sPath=os.path.join(stdAuthor, sanitize_filename(myx_utilities.cleanseTitle(book.title), disc))

            paths.append(sPath)

            return paths  
    
    def getLogRecord(self, bookMatch:Book):
        #returns a dictionary of the record that gets logged
        book={
            "file":self.fullPath,
            "isMatched": self.isMatched,
            "isHardLinked": self.isHardlinked,
        }

        book=bookMatch.getDictionary(book)
        book["paths"]=",".join(self.getTargetPaths(bookMatch))

        return book
    
@dataclass
class MAMBook:
    name:str
    files:list= field(default_factory=list) 
    ffprobeBook:Book=None
    bestAudibleMatch:Book=None 
    bestMAMMatch:Book=None
    mamMatches:list[Book]= field(default_factory=list)    
    audibleMatches:list[Book]= field(default_factory=list)  
    isSingleFile:bool=False
    isMultiFileBook:bool=False
    isMultiBookCollection:bool=False
    metadata:str="id3"
    metadataBook:Book=None

    def getRunTimeLength(self):
        #add all the duration of the files in the book, and convert into minutes
        duration:float=0
        for f in self.files:
            duration += float(f.ffprobeBook.duration)

        return math.floor(duration/60)

    def ffprobe(self, file):
        #ffprobe the file
        metadata=None
        book=None
        
        try:
            metadata=myx_utilities.probe_file(file)["format"]["tags"]
        except Exception as e:
            if myx_args.params.verbose:
                print (f"ffprobe failed on {self.name}: {e}")

        if (metadata is not None):
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
            if 'album' in metadata: book.series.append(Series(metadata["album"],""))
            #parse authors
            if 'artist' in metadata: 
                for author in metadata["artist"].split(","):
                    book.authors.append(Contributor(myx_utilities.removeGA(author)))
            #parse narrators
            if 'composer' in metadata: 
                for narrator in metadata["composer"].split(","):
                    book.narrators.append(Contributor(narrator))
        
        #return a book object created from  ffprobe
        self.ffprobeBook=book
        if verbose:
            pprint (book)
        return book

    def getTargetPaths(self, authors, series, title, disc=""):
        paths=[]
        #Get primary author
        if ((authors is not None) and (len(authors) == 0)):
            author="Unknown"
        else:
            author=authors[0].name  

        #standardize author name (replace . with space, and then make sure that there's only single space)
        stdAuthor=sanitize_filename(myx_utilities.cleanseAuthor(author))

        #Does this book belong in a series - only take the first series?
        sPath=""
        if (len(series) > 0):
            sPath=os.path.join(stdAuthor, sanitize_filename(myx_utilities.cleanseSeries(series[0].name)), 
                                      sanitize_filename(f"{myx_utilities.cleanseSeries(series[0].getSeriesPart())} - {myx_utilities.cleanseTitle(title)}"),
                                      sanitize_filename(disc))
        else:
            sPath=os.path.join(stdAuthor, sanitize_filename(myx_utilities.cleanseTitle(title)), sanitize_filename(disc))

        paths.append(sPath)
        return paths  

    def getAudibleBooks(self, client, fixid3=False):

        books=[]
        language="english"
        #Search Audible using either MAM (better) or ffprobe metadata
        if (not myx_args.params.multibook) and (self.bestMAMMatch is not None):
            book = self.bestMAMMatch
            title = book.getCleanTitle()
            language = book.language
        else:
            # source is ID3 data
            book = self.ffprobeBook

            # if bad ffprobe data or fixid3, make it better?
            if (len(book.title) == 0) or (fixid3):
                book.title = myx_utilities.getAltTitle (self.name, book) 

            title = myx_utilities.cleanseTitle(book.title, stripUnabridged=True)

        #pprint(book)
        #sometimes Audible returns nothing if there's too much info in the keywords
        series=""
        if (len(book.series)==1):
            series = myx_utilities.cleanseTitle(book.getSeries(), stripUnabridged=True)
        elif len(book.series):
            series = myx_utilities.cleanseTitle(book.series[0].name, stripUnabridged=True)
        
        keywords=myx_utilities.optimizeKeys([myx_utilities.cleanseAuthor(book.getNarrators(delimiter=" ")),
                                            series,
                                            myx_utilities.cleanseTitle(title, stripUnabridged=True), 
                                            myx_utilities.cleanseAuthor(book.getAuthors(delimiter=" "))])
        #print(f"Searching Audible for\n\tasin:{book.asin}\n\ttitle:{title}\n\tauthors:{book.authors}\n\tnarrators:{book.narrators}\n\tkeywords:{keywords}")
        
        #generate author, narrator combo
        author_narrator=[]
        for i in range(len(book.authors)):
            if len(book.narrators):
                for j in range(len(book.narrators)):
                    author_narrator.append((book.authors[i].name, book.narrators[j].name))
            else:
                    author_narrator.append((book.authors[i].name, ""))

        #print (author_narrator)

        for an in author_narrator:
            #print (f"Author: {an[0]}\tNarrator: {an[1]}")
            sAuthor=myx_utilities.cleanseAuthor(an[0])
            sNarrator=myx_utilities.cleanseAuthor(an[1])
            books=myx_audible.getAudibleBook (client, asin=book.asin, title=title, authors=sAuthor, narrators=sNarrator, keywords=keywords, language=language)

            #book found, exit for loop
            if ((books is not None) and len(books)):
                break
            
            #print (f"Nothing was found so just doing a keyword search {keywords}")
            # too constraining?  try just a keywords search with all information
            books=myx_audible.getAudibleBook (client, keywords=keywords, language=language)

            #book found, exit for loop
            if ((books is not None) and len(books)):
                break

        self.audibleMatches=books
        # Because the Audible search is sorted by relevance, we assume that the top search is the best match  
        if not myx_args.params.multibook:
            mamBook = '|'.join([f"Duration:{self.getRunTimeLength()}min", book.getAuthors(), book.getNarrators(), book.getCleanTitle(), series])
        else:
            mamBook = '|'.join([book.getAuthors(), book.getNarrators(), book.getCleanTitle(), series])


        #process search results
        if (self.audibleMatches is not None):
            if (myx_args.params.verbose):
                print(f"Found {len(self.audibleMatches)} Audible match(es)\n\n")

            #if (len(self.audibleMatches) > 1):
                #find the best match
                #find an exact duration match
                #print (f"Finding exact duration match {self.getRunTimeLength()}")
                # for product in books:
                #     abook=myx_audible.product2Book(product)
                #     #print (f"\n\t{book.asin}: {book.length}")
                #     if (abs(self.getRunTimeLength() - abook.length) <= 3):
                #         #print (f"Exact Match Found, {book.asin} : {book.length}")
                #         found=True
                #         self.bestAudibleMatch=abook
                #         abook.matchRate=100

                # abook=myx_audible.product2Book(books[0])
                # audibleBook = '|'.join([f"Duration:{abook.length}min", abook.getAuthors(), abook.getCleanTitle(), abook.getSeriesParts()])
                # matchRate=myx_utilities.fuzzymatch(mamBook, audibleBook)
                # abook.matchRate=matchRate
                # self.bestAudibleMatch=abook
                            
            bestMatchRate=0
            #find the best match
            print(f"Finding the best Audible match out of {len(books)} results")
            for product in books:
                abook=myx_audible.product2Book(product)
                if myx_utilities.isThisMyAuthorsBook(book.authors, abook): #and myx_utilities.isThisMyBookTitle(title, abook, myx_args.params.matchrate):
                    #include this book in the comparison
                    if not myx_args.params.multibook:
                        audibleBook = '|'.join([f"Duration:{abook.length}min", abook.getAuthors(), abook.getNarrators(), abook.getCleanTitle(), abook.getSeriesParts()])
                    else:
                        audibleBook = '|'.join([abook.getAuthors(), abook.getNarrators(), abook.getCleanTitle(), abook.getSeriesParts()])
                    matchRate=myx_utilities.fuzzymatch(mamBook, audibleBook)
                    abook.matchRate=matchRate

                    print(f"\tMatch Rate: {matchRate}\n\tSearch: {mamBook}\n\tResult: {audibleBook}\n\tBest Match Rate: {bestMatchRate}\n")
                    
                    if (matchRate > bestMatchRate):
                        bestMatchRate=matchRate
                        self.bestAudibleMatch=abook

                    # #print (f"Fuzzy Match {str(book)}")
                    # audibleBook = '|'.join([f"Duration:{abook.length}min", abook.getAuthors(), abook.getNarrators(), abook.getCleanTitle(), abook.getSeriesParts()])
                    # matchRate=myx_utilities.fuzzymatch(mamBook, audibleBook)
                    # abook.matchRate=matchRate
                    # #print(f"Match Rate: {matchRate}\n\tSearch: {mamBook}\n\tResult: {audibleBook}")

                    # #is this better and the duration is within 3 minutes
                    # if (matchRate > bestMatchRate) and (matchRate >= myx_args.params.matchrate):
                    #     #default to the first record, because results are sorted by relevance
                    #     if (not found):
                    #         #if the first result is not even from this author, assume there are no results
                    #         bestMatchRate=matchRate
                    #         self.bestAudibleMatch=abook
                    #         found=True
                    #     else:
                    #         #something was found before, so only update it, if the match is better AND the duration is a better match
                    #         #note: this logic is flawed if the book is split into multiple files
                    #         if (not myx_args.params.multibook) and (abs(self.getRunTimeLength() - abook.length) <= 3):
                    #             bestMatchRate=matchRate
                    #             self.bestAudibleMatch=abook
                    #             found=True
            
            # else:
            #     if ((books is not None) and (len(books) == 1)):
            #         #the only match is the best match -- or not
            #         abook=myx_audible.product2Book(books[0])
            #         if myx_utilities.isThisMyAuthorsBook(book.authors, abook):
            #             self.bestAudibleMatch=abook

        #pprint(self.bestAudibleMatch)
        if (books is not None):             
            return len(books) 
        else: 
            return 0
        
    def createHardLinks(self, targetFolder, dryRun=False):

        if (self.metadata == "audible"):
            self.metadataBook=self.bestAudibleMatch
        elif (self.metadata == "mam"):
            self.metadataBook=self.bestMAMMatch
        else:
            self.metadataBook=self.ffprobeBook

        if (self.metadataBook is not None):
            if myx_args.params.verbose:
                print (f"Hardlinking files for {self.metadataBook.title}")

            if (dryRun):
                prefix = "[Dry Run] : "    
            else:
                prefix = ""    

            #for each file for this book                
            for f in self.files:
                #if a book belongs to multiple series, only use the first one                
                for p in f.getTargetPaths(self.metadataBook):
                    if (not dryRun):
                        #hardlink the file
                        p = os.path.join(targetFolder, p)
                        f.hardlinkFile(f.fullPath, p)                   

                    print (f"{prefix}Hardlinking {f.fullPath} to {p}")

                    #generate the OPF file
                    print (f"{prefix}Generating OPF file ...")

                    if ((not dryRun) and (not myx_args.params.no_opf)):
                        self.metadataBook.createOPF(p)
                
                if myx_args.params.verbose:
                    myx_utilities.printDivider()

    def isMatched(self):
        return bool(((self.bestMAMMatch is not None) or (self.bestAudibleMatch is not None)))
    
    def getLogRecord(self, bf):
        #MAMBook fields
        book={}
        book["book"]=self.name
        book["file"]=bf.fullPath
        book["isMatched"]=self.isMatched() 
        book["isHardLinked"]= bf.isHardlinked
        book["mamCount"]=len(self.mamMatches)
        book["audibleMatchCount"]=len(self.audibleMatches)
        book["metadatasource"]=self.metadata
        #check out the targetpath of the first bookfile
        book["paths"]=bf.getTargetPaths(self.metadataBook)

        #Get FFProbe Book
        if (bf.ffprobeBook is not None):
            book=bf.ffprobeBook.getDictionary(book, "id3-")

        #Get MAM Book
        if (self.bestMAMMatch is not None):
            book=self.bestMAMMatch.getDictionary(book, "mam-")

        #Get Audible Book
        if (self.bestAudibleMatch is not None):
            book=self.bestAudibleMatch.getDictionary(book, "adb-")

        return book    

    def getMAMBooks(self, session, bookFile:BookFile, ebooks=False, fixid3=False):
        #search MAM record for this book
        # title=" | ".join([f'"{myx_utilities.cleanseTitle(self.name, stripaccents=False, stripUnabridged=False)}"', 
        #                 f'"{myx_utilities.cleanseTitle(bookFile.ffprobeBook.title, stripaccents=False, stripUnabridged=False)}"',
        #                 f'"{bookFile.getFileName()}"'])
        title = f'"{bookFile.getFileName()}"'
        authors=self.ffprobeBook.getAuthors(delimiter="|", encloser='"', stripaccents=False)
        extension = f'"{bookFile.getExtension()}"'

        # REMOVED 8/22 after search API supported my_snatched
        # if there is no author, we can't just have the filename be the search
        # if (len(self.ffprobeBook.authors) == 0):
        #     #use the series as part of the search as well
        #     if (len(self.ffprobeBook.series)):
        #         title = " ".join([title, self.ffprobeBook.getSeries()])
        #     elif (len(self.ffprobeBook.title)):
        #         title = " ".join([title, self.ffprobeBook.title])
        
        #if this is a single or normal file, do a filename search
        # if (not self.isMultiBookCollection):
        #     titleFilename = f'"{bookFile.getFileName()}"'
        #     if (myx_args.params.metadata == "log"):
        #         #user must have cleaned the id3 tags, use that instead of the book.name
        #         titleFilename.join(f" {bookFile.ffprobeBook.title}")
        # else:
        #     #if this is a multi-file book, use book name and author
        #     titleFilename=title
    
        # Search using book key and authors (using or search in case the metadata is bad)
        print(f"Searching MAM for\n\tTitleFilename: {title}\n\tauthors:{authors}")
        self.mamMatches=myx_mam.getMAMBook(session, titleFilename=title, authors=authors, extension=extension, ebooks=ebooks)

        # was the author inaccurate? (Maybe it was LastName, FirstName or accented)
        # print (f"Trying again because Filename, Author = {len(self.mamMatches)}")
        if len(self.mamMatches) == 0:
            #try again, without author this time
            print(f"Widening MAM search using just\n\tTitleFilename: {title}")
            self.mamMatches=myx_mam.getMAMBook(session, titleFilename=title, extension=extension, ebooks=ebooks)

        # # print (f"Trying again because Filename = {len(self.mamMatches)}")
        # if len(self.mamMatches) == 0:
        #     #try again, with the parent folder and author
        #     titleFilename = title 
        #     print(f"Widening MAM search using\n\tTitle: {title}\n\tAuthors: {authors}")
        #     self.mamMatches=myx_mam.getMAMBook(session, titleFilename=title, authors=authors, extension=extension)

        if myx_args.params.verbose:
            print(f"Found {len(self.mamMatches)} MAM match(es)\n\n")
    
        #find the best match
        if (len(self.mamMatches) > 1):
            if (len(self.ffprobeBook.title) == 0) or (fixid3):
                self.ffprobeBook.title = myx_utilities.getAltTitle(self.name, self.ffprobeBook)

            self.bestMAMMatch=myx_utilities.findBestMatch(self.ffprobeBook, self.mamMatches)
        else:
            if (len(self.mamMatches)):
                self.bestMAMMatch=self.mamMatches[0]

        return len(self.mamMatches)
    
    def getHashKey(self):
        return myx_utilities.getHash(self.name)

    def isCached(self, category):
        return myx_utilities.isCached(self.getHashKey(),category)
    
        
    def cacheMe(self, category, content):
        return myx_utilities.cacheMe(self.getHashKey(),category, content)
         
        
    def loadFromCache(self, category):
        return myx_utilities.loadFromCache(self.getHashKey(), category)


