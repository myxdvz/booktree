
import unicodedata
from thefuzz import fuzz
from pprint import pprint
import os, sys, subprocess, shlex, re
from glob import iglob, glob
import csv
import json
import myx_classes
import myx_args

##ffprobe
def probe_file(filename):
    #ffprobe -loglevel error -show_entries format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer -of default=noprint_wrappers=1:nokey=0 -print_format compact "$file")
    cmnd = ['ffprobe','-loglevel','error','-show_entries','format_tags=artist,album,title,series,part,series-part,isbn,asin,audible_asin,composer', '-of', 'default=noprint_wrappers=1:nokey=0', '-print_format', 'json', filename]
    p = subprocess.Popen(cmnd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err =  p.communicate()
    return json.loads(out)

#Utilities
def getList(items, delimiter=",", encloser="", stripaccents=True):
    enclosedItems=[]
    for item in items:
        if strip_accents:
            enclosedItems.append("{}{}{}".format(encloser, strip_accents(item.name), encloser))
        else:
            enclosedItems.append("{}{}{}".format(encloser, item.name, encloser))
        
    return delimiter.join(enclosedItems)

def cleanseAuthor(author):
    #remove some characters we don't want on the author name
    stdAuthor=strip_accents(author)

    #remove some characters we don't want on the author name
    for c in ["- editor", " - ", "'"]:
        stdAuthor=stdAuthor.replace(c,"")

    #replace . with space, and then make sure that there's only single space between words)
    stdAuthor=" ".join(stdAuthor.replace("."," ").split())
    return stdAuthor

def cleanseTitle(title="", stripaccents=True):
    #remove (Unabridged) and strip accents
    if stripaccents:
        stdTitle = strip_accents(title.replace(" (Unabridged)", "").replace("m4b",""))
    else:
        stdTitle = title.replace(" (Unabridged)", "").replace("m4b","")
        

    return stdTitle

def standardizeAuthors(mediaPath, dryRun=False):
    #get all authors from the source path
    for f in iglob(os.path.join(mediaPath,"*"), recursive=False):
        #ignore @eaDir
        if (f != os.path.join(mediaPath,"@eaDir")):
            oldAuthor=os.path.basename(f)
            newAuthor=cleanseAuthor(oldAuthor)
            if (oldAuthor != newAuthor):
                print("Renaming: {} >> {}".format(f, os.path.join(os.path.dirname(f), newAuthor)))
                if (not dryRun):
                    try:
                        Path(f).rename(os.path.join(os.path.dirname(f), newAuthor))
                    except Exception as e:
                        print ("Can't rename {}: {}".format(f, e))

def fuzzymatch(x:str, y:str):
    #remove .:_-, for fuzzymatch
    symbols=".:_-'[]"
    newX=x.replace(symbols, "")
    newY=y.replace(symbols, "")
    if (len(newX) and len(newY)):
        newZ=fuzz.token_sort_ratio(newX, newY)
        #print ("{} Fuzzy Match {}={}".format(newZ, newX, newY))
        return newZ
    else:
        return 0
    
def optimizeKeys(keywords, delim=" "):
    #keywords is a list of stuff, we want to convert it in a comma delimited string
    kw=[]
    for k in keywords:
        k=k.replace("["," ").replace("]"," ").replace("{"," ").replace("}"," ").replace(".", " ").replace("_", " ").replace("("," ").replace(")"," ").replace(":"," ").replace(","," ").replace(";", " ")
        print(k)
        #parse this item "-"
        for i in k.split("-"):
            #parse again on spaces
            print(i)
            for j in i.split():
                print(j)
                #if it's numeric like 02, make it an actual digit
                if (not j.isdigit()):
                    #remove any articles like a, i, the
                    if ((len(j) > 1) and (j.lower() not in ["the","and","m4b","series","audiobook","audiobooks"])):
                        print(f"Adding {j.lower()}")
                        kw.append(j.lower())

    #now return comma delimited string
    return delim.join(kw)

def getParentFolder(file, source):
    #We normally assume that the file is in a folder, but some files are NOT in a subfolder
    parent=os.path.dirname(file)
    #check if the parent folder matches the source folder
    if (parent == source):
        #this file is bad and has no parent folder, use the filename as the parent folder
        return os.path.basename(file)
    else:
        return (parent.split("/")[-1])

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
                if (not dryRun):
                    f.hardlinkFile(f.sourcePath, os.path.join(targetFolder,p))
                print ("Hardlinking {} to {}".format(f.sourcePath, os.path.join(targetFolder,p)))
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
            print("file {}: {}".format(logFilePath, e))

def logBooks(logFilePath, books):
    write_headers = not os.path.exists(logFilePath)
    with open(logFilePath, mode="a", newline="", errors='ignore') as csv_file:
        try:
            for book in books:
                for file in book.files:
                    row=book.getLogRecord(file)
                    fields=row.keys()

                    #create a writer
                    writer = csv.DictWriter(csv_file, fieldnames=fields)
                    if write_headers:
                        writer.writeheader()
                        write_headers=False
                    writer.writerow(row)

        except csv.Error as e:
            print("file {}: {}".format(logFilePath, e))    

def findBookFiles (baseFileList, filegrouping):
    
    updatedFileList=[]
    if (len(baseFileList)==0):
        #All files have been matched to a book, nothing else to process
        return filegrouping
    else:
        #find all books from the bookfile list that matches the base book
        if myx_args.params.verbose:
            print (f"Checking files that match - {baseFileList[0].file}")

        #create a new MAM Book based on the base Book file
        baseBook = baseFileList[0].ffprobe()
        mamBook = myx_classes.MAMBook(baseBook.title)
        mamBook.ffprobeBook = baseBook
        filegrouping.append (mamBook)

        for i in range(1,len(baseFileList)-1):
            f = baseFileList[i]
            #read the id3 tags 
            if (f.ffprobeBook is not None):
                f.ffprobe()
    
            #check if the hash matches the value of the baseBook file - if not, it's probably it's own book
            match = fuzzymatch(str(baseBook.getAllButTitle()), str(f.ffprobeBook.getAllButTitle()))

            if (match == 100):
                #add this file under mamBooks files
                mamBook.files.append(f)
            else:
                #this file needs to be reprocessed, and tested with the other books
                updatedFileList.append(f)

    return findBookFiles(updatedFileList, filegrouping)

def isMultiBookCollection (mamBook):
    if myx_args.params.verbose:
        print (f"Checking {mamBook.name} file {range(len(mamBook.files))} files")
    
    filegrouping=[]
    if len(mamBook.files) > 1:
        #for i in range(len(mamBook.files)-1):
        filegrouping = findBookFiles(mamBook.files, filegrouping)

    #pprint(filegrouping)

    return filegrouping, len(filegrouping) > 1

def findBestMatch(targetBook, books):
    
    #set the baseline book
    targetString = '|'.join([targetBook.title, targetBook.getAuthors(), targetBook.getSeriesParts()])
    bestMatchRate=0
    bestMatchedBook=None
    #for each matched book, calculate the fuzzymatch rate
    for book in books:
        #create the same string
        bookString = '|'.join([book.title, book.getAuthors(), book.getSeriesParts()])
        matchRate=fuzzymatch(targetString, bookString)
        book.matchRate=matchRate

        #is this better?
        if (matchRate > bestMatchRate):
            bestMatchRate=matchRate
            bestMatchedBook=book   
    
    return bestMatchedBook

def printDivider (char="-", length=40):
    print("\n", length * char, "\n")
    
def removeGA (author:str):
    #remove Graphic Audio and special characters like ()[]
    cleanAuthor = author.replace("GraphicAudio","").replace("[","").replace("]","")
    return cleanAuthor.strip()
