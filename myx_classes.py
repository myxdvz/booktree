
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
    separator:str=""
    
    def getSeriesPart(self):
        if (len(self.part.strip()) > 0):
            return f"{self.name} {self.separator}{str(self.part)}"
        else:
            return self.name

#Book Class
@dataclass
class Book:
    asin:str=""
    title:str=""
    subtitle:str=""
    publisher:str=""
    length:int=0
    duration:float=0
    matchRate=0
    language:str="english"
    snatched:bool=False
    description:str=""
    publishYear:str=""
    series:list[Series]= field(default_factory=list)
    authors:list[Contributor]= field(default_factory=list)
    narrators:list[Contributor]= field(default_factory=list)
    files:list[str]= field(default_factory=list)
    genres:list[str]= field(default_factory=list)
    tags:list[str]= field(default_factory=list)
    metadata={}

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
        #remove author
        title = self.title
        for author in self.authors:
            title = re.sub (f"{re.escape(author.name)}", "", title, flags=re.IGNORECASE)

        # #remove series
        for s in self.series:
            title = re.sub (f"{re.escape(s.name)}", "", title, flags=re.IGNORECASE)

        #Remove the rest
        title = myx_utilities.cleanseTitle(title, True, True)
        
        return title
    
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
                seriesparts.append(Contributor(f"{s.name} {s.separator}{s.part}")) 
            
        return myx_utilities.getList(seriesparts, delimiter, encloser, stripaccents=True) 
    
    def setAuthors(self, authors):
        #Given a csv of authors, convert it to a list
        if len(authors.strip()):
            for author in authors.split (","):
                self.authors.append(Contributor(author))

    def setNarrators(self, narrators):
        #Given a csv of authors, convert it to a list
        if len(narrators.strip()):
            for narrator in narrators.split (","):
                self.narrators.append(Contributor(narrator))

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
        book[f"{ns}publisher"]=self.publisher
        book[f"{ns}length"]=self.length
        book[f"{ns}duration"]=self.duration
        book[f"{ns}series"]=self.getSeries()
        book[f"{ns}authors"]=self.getAuthors()
        book[f"{ns}narrators"]=self.getNarrators()
        book[f"{ns}seriesparts"]=self.getSeriesParts()
        book[f"{ns}language"]=self.language
        return book  
    
    def init(self):
        self.asin=""
        self.title=""
        self.subtitle=""
        self.publisher=""
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

    def initMetadataJSON(self, path):
        print (f"Creating a metadata.json file in {path}")
        myx_utilities.initMetadataJSON(self, path)

          
#Book File Class
@dataclass
class BookFile:
    file:posixpath
    fullPath:str
    sourcePath:str
    mediaPath:str
    isMatched:bool=False
    isHardlinked:bool=False
    audibleMatch:Book=None
    ffprobeBook:Book=None
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

    def ffprobe(self, parent):
        #ffprobe the file
        duration=0
        try:
            r = self.__probe_file__()
            duration = float(r["format"]["duration"])
            metadata= r["format"]["tags"]
        except Exception as e:
            metadata=dict()
            #print (f"ffprobe failed on {self.file}: {e}")

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
            #remove everything in parentheses firstm before parsing
            artist = re.sub(r"\(.+\)", "", metadata["artist"], flags=re.IGNORECASE)
            for author in artist.split(","):
                book.authors.append(Contributor(myx_utilities.removeGA(author)))
        #parse narrators
        if 'composer' in metadata: 
            composer = re.sub(r"\(.+\)", "", metadata["composer"], flags=re.IGNORECASE)
            for narrator in composer.split(","):
                book.narrators.append(Contributor(narrator))
        #duration in minutes
        book.duration = duration
        
        #return a book object created from  ffprobe
        self.ffprobeBook=book

        return book
    
    def hardlinkFile(self, source, target):

        #check if the target path exists
        if (not os.path.exists(target)):
            #make dir path
            print (f"\tCreating target directory: {target} ")
            os.makedirs(target, exist_ok=True)
        
        #check if the file already exists in the target directory
        filename=os.path.join(target, os.path.basename(source).split(os.sep)[-1])
        if (not os.path.exists(filename)):
            try:
                #print (f"Hardlinking {source} to {filename}")
                os.link(source, filename)
                self.isHardlinked=True
            except Exception as e:
                print (f"\tFailed due to {e}")
        else:
            print (f"\tSkipped : {filename} exists")
                
        return self.isHardlinked
    
    def getConfigTargetPath(self, cfg, book):
        #Config
        media_path = self.mediaPath
        multi_author = cfg.get("Config/target_path/multi_author")
        in_series = cfg.get("Config/target_path/in_series")
        no_series = cfg.get("Config/target_path/no_series")
        disc_folder = cfg.get("Config/target_path/disc_folder")

        if (book is not None):
            #Get primary author
            if ((book.authors is not None) and (len(book.authors) == 0)):
                author="Unknown"
            elif ((book.authors is not None) and (len(book.authors) > 1) and (multi_author is not None)):
                    match multi_author:
                        case "first_author": 
                            author=book.authors[0].name  
                        
                        case "authors":
                            author=book.getAuthors()

                        case _: 
                            author=multi_author
            else:
                author=book.authors[0].name

            #standardize author name (replace . with space, and then make sure that there's only single space)
            if len(author):
                author=myx_utilities.cleanseAuthor(author)

            #Get primary narrator
            if ((book.narrators is not None) and (len(book.narrators) == 1)):
                narrator=book.getNarrators()
            else:
                narrator=""

            #is this a MultiCd file?
            disc = self.getParentFolder()
            if (not myx_utilities.isMultiCD(disc)):
                disc = ""

            #Does this book belong in a series - only take the first series?
            series=""
            part=""
            if (len(book.series) > 0):
                series = f"{myx_utilities.cleanseSeries(book.series[0].name)}"
                part = str(book.series[0].part)

            title = f"{myx_utilities.cleanseTitle(book.title)}"

            tokens = {}
            tokens["author"] = sanitize_filename(author)
            tokens["series"] = sanitize_filename(series)
            tokens["part"] = sanitize_filename(part)
            tokens["title"] = sanitize_filename(book.title)
            tokens["cleanTitle"] = sanitize_filename(title)
            tokens["disc"] = sanitize_filename(disc)

            if len(narrator):
                tokens["narrator"] = f"{{{sanitize_filename(narrator)}}}"
            else:
                tokens["narrator"] = ""

            sPath = ""
            if len(book.series):
                x = in_series.format (**tokens)
                #use in_series format
                for p in x.split ("/"):
                    sPath=os.path.join (sPath, p)
            else:
                y = no_series.format (**tokens)
                #use no_series format
                for p in y.split ("/"):
                    sPath=os.path.join (sPath, p)

            #add disc for multidisc
            if len(disc):
                z = disc_folder.format (**tokens)
                sPath=os.path.join(sPath, z)

            return os.path.join(media_path, sPath)  
    
    def getTargetPaths(self, book, cfg):
        return self.getConfigTargetPath(cfg, book)
    
    def getLogRecord(self, bookMatch:Book, cfg):
        #returns a dictionary of the record that gets logged
        book={
            "file":self.fullPath,
            "isMatched": self.isMatched,
            "isHardLinked": self.isHardlinked,
        }

        book=bookMatch.getDictionary(book)

        if cfg.get("Config/metadata") != "log":
            book["paths"]=self.getConfigTargetPath(cfg, bookMatch)

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
    paths:str=""
    isMatched:bool=False
    mamIDs:list[str]= field(default_factory=list)

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
            #ignore errors
            print ("", end="")
            #print (f"\nffprobe failed on {self.name}: {e}")

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
                #remove everything in parentheses firstm before parsing
                artist = metadata["artist"]
                for author in re.split(",", artist):
                    author = re.sub(r"\([.]+\)", "", author, flags=re.IGNORECASE)  
                    author = myx_utilities.removeGA(author)
                    if len(author): book.authors.append(Contributor())
            #parse narrators
            if 'composer' in metadata: 
                composer = metadata["composer"]
                for narrator in re.split(",", composer):
                    #remove any occurrence of (Narrator)
                    narrator = re.sub(r"\([.]+\)", "", narrator, flags=re.IGNORECASE)       
                    book.narrators.append(Contributor(narrator))
        
        #return a book object created from  ffprobe
        self.ffprobeBook=book

        return book

    def getAudibleBooks(self, client, book, cfg):
        #Config variables
        minMatchRate = int(cfg.get("Config/matchrate"))
        fixid3 = bool(cfg.get("Config/flags/fixid3"))
        verbose = bool(cfg.get("Config/flags/verbose"))
        add_narrators = bool(cfg.get("Config/flags/add_narrators"))
        fuzzy_match = cfg.get("Config/fuzzy_match")

        books=[]
        if (book is not None):
            language=book.language
            # book = self.ffprobeBook
            if (len(book.title) == 0) or (fixid3):
                book.title = myx_utilities.getAltTitle (self.name, book, cfg) 
                
            title = myx_utilities.cleanseTitle(book.title, stripUnabridged=True)

            #sometimes Audible returns nothing if there's too much info in the keywords
            series=""
            if (len(book.series)==1):
                series = myx_utilities.cleanseTitle(book.getSeries(), stripUnabridged=True)
            elif len(book.series):
                series = myx_utilities.cleanseTitle(book.series[0].name, stripUnabridged=True)
            
            if add_narrators:
                keywords=myx_utilities.optimizeKeys(cfg, [myx_utilities.cleanseTitle(title, stripUnabridged=True), 
                                                    series,
                                                    myx_utilities.cleanseAuthor(book.getAuthors(delimiter=" ")), 
                                                    myx_utilities.cleanseAuthor(book.getNarrators(delimiter=" "))])
            else:
                keywords=myx_utilities.optimizeKeys(cfg, [myx_utilities.cleanseTitle(title, stripUnabridged=True), 
                                                    series,
                                                    myx_utilities.cleanseAuthor(book.getAuthors(delimiter=" "))])

            #print(f"Searching Audible for\n\tasin:{book.asin}\n\ttitle:{title}\n\tauthors:{book.authors}\n\tnarrators:{book.narrators}\n\tkeywords:{keywords}")
            
            #generate author, narrator combo
            author_narrator=[]
            for i in range(len(book.authors)):
                if add_narrators and len(book.narrators):
                    for j in range(len(book.narrators)):
                        author_narrator.append((book.authors[i].name, book.narrators[j].name))
                else:
                        author_narrator.append((book.authors[i].name, ""))

            #print (author_narrator)

            for an in author_narrator:
                #print (f"Author: {an[0]}\tNarrator: {an[1]}")
                sAuthor=myx_utilities.cleanseAuthor(an[0])
                sNarrator=myx_utilities.cleanseAuthor(an[1])
                books=myx_audible.getAudibleBook (client, cfg, asin=book.asin, title=title, authors=sAuthor, narrators=sNarrator, keywords=keywords, language=language)

                #book found, exit for loop
                if ((books is not None) and len(books)):
                    break
                
            #too constraining?  try just a keywords search with all information
            if ((books is None) or ((books is not None) and (len(books) == 0))):
                #print (f"Nothing was found so just doing a keyword search {keywords}")
                books=myx_audible.getAudibleBook (client, cfg, keywords=keywords, language=language)

            mamBook = '|'.join([f"Duration:{self.getRunTimeLength()}min", book.getAuthors(), book.getCleanTitle(), series])
            if add_narrators:
                mamBook = '|'.join([mamBook, book.getNarrators()])

            #process search results
            self.audibleMatches=books
            if (self.audibleMatches is not None):
                if (verbose):
                    print(f"Found {len(self.audibleMatches)} Audible match(es)\n\n")

                bestMatchRate=0
                #find the best match
                print(f"Finding the best Audible match out of {len(books)} results")
                for product in books:
                    abook=myx_audible.product2Book(product)
                    #the author is known, check if this book is this authors book
                    #otherwise, if maybe this title is close enough
                    #print (f"{abook.title} by {abook.authors}...")
                    if len(book.authors) and myx_utilities.isThisMyAuthorsBook(book.authors, abook, cfg):
                        audibleBook = '|'.join([f"Duration:{abook.length}min", abook.getAuthors(), abook.getCleanTitle(), abook.getSeriesParts()])
                        if add_narrators:
                            audibleBook = '|'.join([audibleBook, abook.getNarrators()])
                    elif myx_utilities.isThisMyBookTitle(title, abook, cfg): 
                        audibleBook = '|'.join([f"Duration:{abook.length}min", abook.getAuthors(), abook.getCleanTitle(), abook.getSeriesParts()])
                        if add_narrators:
                            audibleBook = '|'.join([audibleBook, abook.getNarrators()])
                    else:
                        print (f"This book doesn't have a matching title or author, checking the next book...")
                        continue        

                    #include this book in the comparison
                    matchRate=myx_utilities.fuzzymatch(mamBook, audibleBook)
                    abook.matchRate=matchRate[fuzzy_match]

                    print(f"\tMatch Rate: {matchRate}\n\tSearch: {mamBook}\n\tResult: {audibleBook}\n\tBest Match Rate: {bestMatchRate}\n")
                    
                    if (matchRate[fuzzy_match] > bestMatchRate) and (matchRate[fuzzy_match] >= minMatchRate):
                        bestMatchRate=matchRate[fuzzy_match]
                        self.bestAudibleMatch=abook
        #end if

        #pprint(self.bestAudibleMatch)
        if (books is not None): 
            #pprint (books)            
            return self.bestAudibleMatch
        else: 
            return None
        
    def createHardLinks(self, cfg):
        #Config variables
        dryRun = bool (cfg.get("Config/flags/dry_run"))
        verbose = bool (cfg.get("Config/flags/verbose"))
        no_opf = bool (cfg.get("Config/flags/no_opf"))
        metadata = cfg.get("Config/metadata")

        if (self.metadata == "audible"):
            self.metadataBook=self.bestAudibleMatch
        elif (self.metadata == "mam"):
            self.metadataBook=self.bestMAMMatch
        else:
            self.metadataBook=self.ffprobeBook

        if (self.metadataBook is not None):
            if (dryRun):
                prefix = "[Dry Run] : "    
            else:
                prefix = ""    

            #for each file for this book                
            for f in self.files:
                #UPDATED 8/30 to allow users to customize target_path formats  
                if metadata == "log":
                    p = self.paths
                else:
                    p = f.getConfigTargetPath(cfg, self.metadataBook)

                print (f"{prefix}Hardlinking files for {self.metadataBook.title}")
                print (f"\t\t\tfrom {f.fullPath}\n\t\t\t  to {p}")

                if (not dryRun):
                    #hardlink the file
                    f.hardlinkFile(f.fullPath, p)                   

                    #generate the OPF file
                    print (f"\tGenerating OPF file ...")
                    if (not no_opf):
                        self.metadataBook.createOPF(p)

    def matchFound(self):
        return bool(((self.bestMAMMatch is not None) or (self.bestAudibleMatch is not None)))
    
    def getLogRecord(self, bf, cfg):
        #MAMBook fields
        book={}
        book["book"]=self.name
        book["file"]=bf.fullPath
        book["sourcePath"]=bf.sourcePath
        book["mediaPath"]=bf.mediaPath
        book["isMatched"]=self.isMatched
        book["isHardLinked"]= bf.isHardlinked
        book["mamCount"]=len(self.mamMatches)
        book["audibleMatchCount"]=len(self.audibleMatches)
        book["metadatasource"]=self.metadata

        #check out the targetpath of the bookfile
        if book["metadatasource"] != "as-is":
            book["paths"]=bf.getConfigTargetPath(cfg, self.metadataBook)

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

    def isMyBookInMAM (self, cfg, bookFile:BookFile):
        #Config variables
        verbose = bool(cfg.get("Config/flags/verbose"))
        ebooks = bool(cfg.get("Config/flags/ebooks"))
        fuzzy_match = cfg.get("Config/fuzzy_match")
        add_narrators = True

        #search MAM record for this book
        title = f'"{self.bestAudibleMatch.title}"'
        authors=self.bestAudibleMatch.getAuthors(delimiter="|", encloser='"', stripaccents=False)
        extension = f'"{bookFile.getExtension()}"'
    
        # Search using book key and authors (using or search in case the metadata is bad)
        print(f"Searching MAM for\n\tTitle: {title}\n\tauthors:{authors}")
        books = myx_mam.searchMAM(cfg, title, authors, extension)

        if (books is not None):
            #search results found
            for b in books:
                #get torrent links
                self.mamIDs.append(str(b["id"]))

        return len(self.mamIDs)

    def getMAMBooks(self, cfg, bookFile:BookFile):
        #Config variables
        verbose = bool(cfg.get("Config/flags/verbose"))
        ebooks = bool(cfg.get("Config/flags/ebooks"))
        add_narrators = bool(cfg.get("Config/flags/add_narrators"))
        fuzzy_match = cfg.get("Config/fuzzy_match")

        #search MAM record for this book
        title = f'"{bookFile.getFileName()}"'
        authors=self.ffprobeBook.getAuthors(delimiter="|", encloser='"', stripaccents=False)
        extension = f'"{bookFile.getExtension()}"'
    
        # Search using book key and authors (using or search in case the metadata is bad)
        print(f"Searching MAM for\n\tTitleFilename: {title}\n\tauthors:{authors}")
        books=myx_mam.getMAMBook(cfg, titleFilename=title, authors=authors, extension=extension)

        # was the author inaccurate? (Maybe it was LastName, FirstName or accented)
        # print (f"Trying again because Filename, Author = {len(self.mamMatches)}")
        if len(books) == 0:
            #try again, without author this time
            print(f"Widening MAM search using just\n\tTitleFilename: {title}")
            books=myx_mam.getMAMBook(cfg, titleFilename=title, extension=extension)

        #Find the best match
        self.mamMatches = books
        book = self.ffprobeBook

        if (not ebooks) and (self.mamMatches is not None) and (book is not None):
            if (verbose):
                print(f"Found {len(self.mamMatches)} MAM match(es)\n\n")

            bestMatchRate=0
            #find the best match
            print(f"Finding the best MAM match out of {len(books)} results")
            targetBook = '|'.join([self.ffprobeBook.title, self.ffprobeBook.getAuthors(), self.ffprobeBook.getSeriesParts()])
    
            for abook in books:
                #if this book is snatched, include in the match
                if abook.snatched:
                    #the author is known, check if this book is this authors book
                    #otherwise, if maybe this title is close enough
                    #print (f"{abook.title} by {abook.authors}...")
                    if len(book.authors) and myx_utilities.isThisMyAuthorsBook(book.authors, abook, cfg):
                        mamBook = '|'.join([abook.getAuthors(), abook.getCleanTitle(), abook.getSeriesParts()])
                        if add_narrators:
                            mamBook = '|'.join([mamBook, abook.getNarrators()])
                    elif myx_utilities.isThisMyBookTitle(title, abook, cfg): 
                        mamBook = '|'.join([abook.getAuthors(), abook.getCleanTitle(), abook.getSeriesParts()])
                        if add_narrators:
                            mamBook = '|'.join([mamBook, abook.getNarrators()])
                    else:
                        print (f"This book doesn't have a matching title or author, checking the next book...")
                        continue        

                    #include this book in the comparison
                    matchRate=myx_utilities.fuzzymatch(targetBook, mamBook)
                    abook.matchRate=matchRate[fuzzy_match]

                    print(f"\tMatch Rate: {matchRate}\n\tSearch: {targetBook}\n\tResult: {mamBook}\n\tBest Match Rate: {bestMatchRate}\n")
                    
                    if (matchRate[fuzzy_match] > bestMatchRate):
                        bestMatchRate=matchRate[fuzzy_match]
                        self.bestMAMMatch=abook
        else:
            #no metadata, get the first match?
            if len(self.mamMatches):
                self.bestMAMMatch = books[0]


        #pprint(self.bestMAMMatch)
        if (books is not None): 
            return self.bestMAMMatch
        else: 
            return None
    
    def getHashKey(self):
        return myx_utilities.getHash(self.name)

    def isCached(self, category, cfg):
        return myx_utilities.isCached(self.getHashKey(),category, cfg)
        
    def cacheMe(self, category, content, cfg):
        return myx_utilities.cacheMe(self.getHashKey(),category, content, cfg) 
        
    def loadFromCache(self, category):
        return myx_utilities.loadFromCache(self.getHashKey(), category)


