
import unicodedata
from thefuzz import fuzz
from pprint import pprint
import os, sys, subprocess, shlex, re
from glob import iglob, glob
import mimetypes
import csv
import json
import hashlib
from langcodes import *
import myx_classes
import myx_args

##ffprobe
def probe_file(filename):
    #ffprobe -loglevel error -show_entries format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer -of default=noprint_wrappers=1:nokey=0 -print_format compact "$file")
    cmnd = ['ffprobe','-loglevel','error','-show_entries','format_tags:format=duration', '-show_format', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=0', '-print_format', 'json', self.fullPath]
    p = subprocess.Popen(cmnd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err =  p.communicate()
    print(json.loads(out))
    return json.loads(out)

#Utilities
def getList(items, delimiter=",", encloser="", stripaccents=True):
    enclosedItems=[]
    for item in items:
        if type(item) == myx_classes.Contributor:
            enclosedItems.append(f"{encloser}{cleanseAuthor(item.name)}{encloser}")
        else:
            if type(item) == myx_classes.Series:
                enclosedItems.append(f"{encloser}{cleanseSeries(item.name)}{encloser}")
            else:
                enclosedItems.append(f"{encloser}{item.name}{encloser}")

    return delimiter.join(enclosedItems)

def cleanseAuthor(author):
    #remove some characters we don't want on the author name
    stdAuthor=strip_accents(author)

    #remove some characters we don't want on the author name
    for c in ["- editor", "- contributor", " - ", "'"]:
        stdAuthor=stdAuthor.replace(c,"")

    #replace . with space, and then make sure that there's only single space between words)
    stdAuthor=" ".join(stdAuthor.replace("."," ").split())
    return stdAuthor

def cleanseTitle(title="", stripaccents=True, stripUnabridged=False):
    #remove (Unabridged) and strip accents
    stdTitle=str(title)

    for w in [" (Unabridged)", "m4b", "mp3", ",", "- "]:
        stdTitle=stdTitle.replace(w," ")
    
    if stripaccents:
        stdTitle = strip_accents(stdTitle)

    #remove Book X
    stdTitle = re.sub (r"\bBook(\s)?(\d)+\b", "", stdTitle, flags=re.IGNORECASE)

    # remove any subtitle that goes after a :
    stdTitle = re.sub (r"(:(\s)?([a-zA-Z0-9_'\.\s]{2,})*)", "", stdTitle, flags=re.IGNORECASE)

    return stdTitle

def standardizeAuthors(mediaPath, dryRun=False):
    #get all authors from the source path
    for f in iglob(os.path.join(mediaPath,"*"), recursive=False):
        #ignore @eaDir
        if (f != os.path.join(mediaPath,"@eaDir")):
            oldAuthor=os.path.basename(f)
            newAuthor=cleanseAuthor(oldAuthor)
            if (oldAuthor != newAuthor):
                print(f"Renaming: {f} >> {os.path.join(os.path.dirname(f), newAuthor)}")
                if (not dryRun):
                    try:
                        os.path(f).rename(os.path.join(os.path.dirname(f), newAuthor))
                    except Exception as e:
                        print (f"Can't rename {f}: {e}")

def fuzzymatch(x:str, y:str):
    newX = x
    newY = y
    newZ = {"partial" : 0, "token_sort" : 0, "ratio" : 0}
    #remove .:_-, for fuzzymatch
    for c in [".", ":", "_", "-", "[", "]", "'"]:
        newX = newX.replace (c, "")
        newY = newY.replace (c, "")

    if (len(newX) and len(newY)):
        newZ["partial"]=fuzz.partial_ratio(newX, newY)
        newZ["token_sort"]=fuzz.token_sort_ratio(newX, newY)
        newZ["ratio"]=fuzz._ratio(newX, newY)

    return newZ
    
def optimizeKeys(keywords, delim=" "):
    #keywords is a list of stuff, we want to convert it in a comma delimited string
    kw=[]
    for k in keywords:
        for c in [".", ":", "_", "[", "]", "{", "}", ",", ";", "(", ")"]:
            k = k.replace(c, " ")

        #print(k)
        #parse this item "-"
        for i in k.split("-"):
            #parse again on spaces
            #print(i)
            for j in i.split():
                #print(j)
                #if it's numeric like 02, make it an actual digit
                if (len(j) > 1):
                    lcj = j.lower()
                    #if not an article, or a word in the ignore list
                    if lcj not in ["the","and","m4b","mp3","series","audiobook","audiobooks", "book", "part", "track", "novel"]:
                        #if not CD or DISC XX"
                        if not (re.search ("cd\s?\d+", j, re.IGNORECASE) or  re.search ("disc\s?\d+", j, re.IGNORECASE)):
                            #if not a number
                            if not (re.search ("\d+", j, re.IGNORECASE)):
                                #if it's not already in the list
                                if lcj not in kw:
                                    kw.append(j.lower())

    #now return comma delimited string
    return delim.join(kw)

def getParentFolder(file, source):
    #We normally assume that the file is in a folder, but some files are NOT in a subfolder
    # relPath = os.path.relpath(file, source).split("/")
    parent=os.path.dirname(file)
    #check if the parent folder matches the source folder
    if (parent == source):
        #this file is bad and has no parent folder, use the filename as the parent folder
        return os.path.basename(file)
    else:
        return (parent.split(os.sep)[-1])

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                    if unicodedata.category(c) != 'Mn')

def createHardLinks(bookFiles, targetFolder="", dryRun=False):
    #hard link all the books in the list
    for f in bookFiles:
        #use Audible metadata or ID3 metadata
        if f.isMatched:
            book=f.audibleMatch
        else:
            book=f.ffprobeBook

        #if there is a book
        if (book is not None):
            #if a book belongs to multiple series, hardlink them to tall series
            for p in f.getTargetPaths(book):
                prefix=""
                if (not dryRun):
                    f.hardlinkFile(f.sourcePath, os.path.join(targetFolder, p))
                else:
                    prefix = "[Dry Run] : "
                print (f"{prefix}Hardlinking {f.sourcePath} to {os.path.join(targetFolder,p)}")
            print("\n", 40 * "-", "\n")

def logBookRecords(logFilePath, bookFiles):

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
                row["matches"]=len(f.audibleMatches)
                fields=row.keys()

                #create a writer
                writer = csv.DictWriter(csv_file, fieldnames=fields)
                if write_headers:
                    writer.writeheader()
                    write_headers=False
                writer.writerow(row)

        except csv.Error as e:
            print(f"file {logFilePath}: {e}")

def logBooks(logFilePath, books):
    if len(books):
        write_headers = not os.path.exists(logFilePath)
        with open(logFilePath, mode="a", newline="", errors='ignore') as csv_file:
            try:
                fields=getLogHeaders()
                for book in books:
                    for file in book.files:
                        row=book.getLogRecord(file)

                        #create a writer
                        writer = csv.DictWriter(csv_file, fieldnames=fields)
                        if write_headers:
                            writer.writeheader()
                            write_headers=False
                        writer.writerow(row)

            except csv.Error as e:
                print(f"file {logFilePath}: {e}")

def isCollection (bookFile):
    #we assume that most books are formatted this way /Book/Files.m4b
    #we assume that this is a collection, if the file is 3 levels deep, /Book/Another Book or CD/Files.m4b

    relPath = os.path.relpath(bookFile, myx_args.params.source_path).split(os.sep)
    return (len(relPath) > 2)

def findBestMatch(targetBook, books):
    #set the baseline book
    targetString = '|'.join([targetBook.title, targetBook.getAuthors(), targetBook.getSeriesParts()])
    bestMatchRate=0
    bestMatchedBook=None
    #for each matched book, calculate the fuzzymatch rate
    print(f"Finding the best MAM match out of {len(books)} results")
    for book in books:
        #if this book is in my Snatched, perform the fuzzy match
        if (book.snatched):
            #create the same string
            bookString = '|'.join([book.title, book.getAuthors(), book.getSeriesParts()])
            matchRate=fuzzymatch(targetString, bookString)
            book.matchRate=matchRate

            print(f"\tMatch Rate: {matchRate}\n\tSearch: {targetString}\n\tResult: {bookString}\n\tBest Match Rate: {bestMatchRate}\n")

            #is this better?
            if (matchRate["token_sort"] > bestMatchRate):
                bestMatchRate=matchRate["token_sort"]
                bestMatchedBook=book   
    
    return bestMatchedBook

def printDivider (char="-", length=40):
    print("\n", length * char, "\n")
    
def removeGA (author:str):
    #remove Graphic Audio and special characters like ()[]
    cleanAuthor = author.replace("GraphicAudio","").replace("[","").replace("]","")
    return cleanAuthor.strip()

def cleanseSeries(series):
    #remove colons
    cleanSeries = series
    for c in [":", "'"]:
        cleanSeries = cleanSeries.replace (c, "")

    return cleanSeries.strip()


def readLog(logFilePath, books):
    if os.path.exists(logFilePath):
        with open(logFilePath, newline="", errors='ignore', encoding='utf-8',) as csv_file:
            try:
                reader = csv.reader(csv_file,)
                for row in reader:
                    ##Create a new Book
                    print(row)
                    print(reader.fieldnames)

            except csv.Error as e:
                print(f"file {logFilePath}: {e}")


def getLogHeaders():
    headers=['book', 'file', 'isMatched', 'isHardLinked', 'mamCount', 'audibleMatchCount', 'metadatasource', 'paths', 'id3-matchRate', 'id3-asin', 'id3-title', 'id3-subtitle', 'id3-publicationName', 'id3-length', 'id3-duration', 'id3-series', 'id3-authors', 'id3-narrators', 'id3-seriesparts', 'mam-matchRate', 'mam-asin', 'mam-title', 'mam-subtitle', 'mam-publicationName', 'mam-length', 'mam-duration', 'mam-series', 'mam-authors', 'mam-narrators', 'mam-seriesparts', 'adb-matchRate', 'adb-asin', 'adb-title', 'adb-subtitle', 'adb-publicationName', 'adb-length', 'adb-duration', 'adb-series', 'adb-authors', 'adb-narrators', 'adb-seriesparts']
                    
    return dict.fromkeys(headers)

def createOPF(book, path):
    # --- Generate .opf Metadata file ---
    opfTemplate=os.path.join(os.getcwd(), "booktemplate.opf") 
    with open(opfTemplate, mode='r') as file:
        template = file.read()

    # - Author -
    authors=""
    for author in book.authors:
        authors += f"\t<dc:creator opf:role='aut'>{author.name}</dc:creator>\n"
    template = re.sub(r"__AUTHORS__", authors, template)

    # - Title -
    template = re.sub(r"__TITLE__", book.title, template)

    # - Subtitle -
    template = re.sub(r"__SUBTITLE__", book.subtitle, template)

    # - Description -
    template = re.sub(r"__DESCRIPTION__", book.description, template)

    # - Narrator -
    narrators=""
    for narrator in book.narrators:
        narrators += f"\t<dc:creator opf:role='nrt'>{narrator.name}</dc:creator>\n"
    template = re.sub(r"__NARRATORS__", narrators, template)

    # - ASIN -
    template = re.sub(r"__ASIN__", book.asin, template)

    # - Series -
    series=""
    for s in book.series:
        series += f"\t<ns0:meta name='calibre:series' content='{s.name}' />\n"
        series += f"\t<ns0:meta name='calibre:series_index' content='{s.part}' />\n"
    template = re.sub(r"__SERIES__", series, template)

    # - Language -
    template = re.sub(r"__LANGUAGE__", book.language, template)

    
    # if len(book.series) and len(book.series[0].name):
    #     template = re.sub(r"__SERIES__", book.series[0].name, template)
    #     template = re.sub(r"__SERIESPART__", book.series[0].part, template)
    # else:
    #     template = re.sub(r"__SERIES__", "", template)
    #     template = re.sub(r"__SERIESPART__", "", template)

    opfFile=os.path.join(path, "metadata.opf")
    with open(opfFile, mode='w', encoding='utf-8') as file:
        file.write(template)

    return

def getHash(key):
    return hashlib.sha256(key.encode(encoding="utf-8")).hexdigest()

def isCached(key, category):
    if myx_args.params.verbose:
        print (f"Checking cache: {category}/{key}...")
    
    #Check if this book's hashkey exists in the cache, if so - it's been processed
    bookFile = os.path.join(os.getcwd(), "__cache__", category, key)
    found = os.path.exists(bookFile)  
    return found      
    
def cacheMe(key, category, content):
    #create the cache file
    bookFile = os.path.join(os.getcwd(), "__cache__", category, key)
    with open(bookFile, mode="w", encoding='utf-8', errors='ignore') as file:
        file.write(json.dumps(content))

    if myx_args.params.verbose:
        print(f"Caching {key} in File: {bookFile}")
    return os.path.exists(bookFile)        

def loadFromCache(key, category):
    #return the content from the cache file
    bookFile = os.path.join(os.getcwd(), "__cache__", category, key)
    with open(bookFile, mode='r', encoding='utf-8') as file:
        f = file.read()
    
    return json.loads(f)
    
def isMultiCD(parent):
    return re.search("disc\s?\d+", parent.lower()) or re.search("cd\s?\d+", parent.lower())

def isGraphicAudio(author):
    m = re.search("graphic[\s]?audio[\s]?(llc[.]?)*", author.lower())
    #print (f"Is {author} = 'Graphic Audio LLC.'? {m}")
    return (m is not None)

def isThisMyAuthorsBook (authors, book):
    found=False
    for author in authors:
        if isGraphicAudio(author.name): 
            continue
        else:
            for bauthor in book.authors:
                if isGraphicAudio(bauthor.name): 
                    continue
                else:
                    if myx_args.params.verbose:
                        print (f"Checking if {book.title} is {authors}'s book: {book.authors}")

                    #print (f"Author: {author.name} = {bauthor.name}? {(author.name.replace(' ', '') == bauthor.name.replace(' ', ''))}")
                    if (cleanseAuthor(author.name).replace(" ", "") == cleanseAuthor(bauthor.name).replace(" ", "")):
                        #print ("found\n")
                        found=True
                        break
        
        if found: break

    return found

def isThisMyBookTitle (title, book, matchrate=0):
    mytitle = cleanseTitle(title)
    thisTitle = cleanseTitle(book.title)
    thisSeriesTitle = thisTitle

    if len(book.series):
        thisSeries = cleanseSeries(book.series[0].name)
        thisSeriesTitle = " - ".join([thisSeries, thisTitle])
    
    matchname = fuzzymatch(mytitle, thisTitle)
    matchseriesname = fuzzymatch(mytitle, thisSeriesTitle)
    if myx_args.params.verbose:
        print (f"Checking if {thisTitle} or {thisSeriesTitle} matches my book {mytitle}: {matchname} or {matchseriesname}")

    #see if any of the fuzzy match scores are within guidance
    match=False
    for k in matchname.keys():
        if matchname[k] >= matchrate:
            match=True
            break

    if not match:
        for k in matchseriesname.keys():
            if matchseriesname[k] >= matchrate:
                match=True
                break

    return match
    
def getAltTitle(parent, book):
    stop = False
    words = []
    skipSeries = False

    #start with title
    altTitle = cleanseTitle(book.title).lower()

    #if title is blank, use series?
    if (len(altTitle) == 0) and (len(book.series)):
        altTitle = cleanseTitle(book.series[0].name)
        if len(altTitle) : skipSeries = True

    while True:
        #print (f"Getting alternate title for {altTitle}")

        #remove extra characters (there really should'nt be : here) 
        for c in ["-", ".", "part", "track", "of", "(", ")", "_", "[", "]", "m4b", "book", ","]:
            altTitle = altTitle.replace (c, " ")

        for c in ["'"]:
            altTitle = altTitle.replace (c, "")
        #print (f"remove symbols >> {altTitle}")

        #remove authors name in title
        for a in book.authors:
            altTitle = re.sub(f"{a.name}", " ", altTitle, flags=re.IGNORECASE)

        #print (f"remove {book.authors} >> {altTitle}")

        #remove series name in title
        if (not skipSeries):
            for s in book.series:
                altTitle = re.sub(f"{s.name}", " ", altTitle, flags=re.IGNORECASE)

            #print (f"remove {book.series} >> {altTitle}")

        #split in spaces, remove the numbers
        altTitle = re.sub(r"\b\d*\b", "", altTitle, flags=re.IGNORECASE)
        #print (f"remove digits >> {altTitle}")

        for w in altTitle.split():
            if w not in words:
                words.append(w)

        #print (f"remove spaces >> {' '.join(words)}")

        if (len(words)) or (stop):
            altTitle = ' '.join(words)
            book.title = altTitle

            if myx_args.params.verbose:
                print (f"Found alternative title: {altTitle}")

            break
        else:
            altTitle = cleanseTitle(parent).lower()
            stop = True

    #join the title back
    if len (words):
        return book.title
    else:
        return ""

def getLanguage(code):
    lang = "english"
    try: 
        lang = Language.get(code).display_name()

    except:
        print ("Unable to get display name for Language: {code}, defaulting to English")
    
    return lang.lower()

def isMultiBookCollection(filePath):
    #Is this MAM result a collection
    isMBC = False
    #if the # of paths from source path is 3 or more
    path, file = os.path.split(filePath)    
    #how deep is it from the source?
    filedepth = len(path.split(os.sep)) + 1
    print (f"File depth of {filePath} is {filedepth}")
    # if the filedepth from source is 3 levels down, assume it's a multibook collection
    isMBC = (filedepth >= 3)
    return isMBC