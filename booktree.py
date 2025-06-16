from pathlib import Path
from pprint import pprint
from datetime import datetime
from time import mktime
from glob import iglob, glob
import os, sys, subprocess, shlex, re
import myx_classes
import myx_audible
import myx_utilities
import myx_mam
import myx_args
import csv
import httpx

#Main Functions
def buildTreeFromLog(files, logfile, cfg):
    #Variables
    allFiles=[]
    matchedFiles=[]
    unmatchedFiles=[]

    #Config variables
    dryRun = bool(cfg.get("Config/flags/dry_run"))
    verbose = bool(cfg.get("Config/flags/verbose"))
    no_cache = bool(cfg.get("Config/flags/no_cache"))
    ebooks = bool(cfg.get("Config/flags/ebooks"))

    #read from the logfile - generate book files from there
    book={}
    inputFile=files
    if os.path.exists(inputFile):        
        with open(inputFile, newline="", errors='ignore', encoding='utf-8',) as csv_file:
            try:
                i = 1
                fields=myx_utilities.getLogHeaders()
                reader = csv.DictReader(csv_file, fieldnames=fields)
                for row in reader:
                    ##Create a new Book
                    #print (f"Reading row {i}")
                    if (i > 1):
                        f = str(row["file"])
                        fullpath=str(row["file"])
                        bf=myx_classes.BookFile(f, fullpath, str(row["sourcePath"]), str(row["mediaPath"]), isHardlinked=bool(row["isHardLinked"]))
                        
                        #parse authors and series
                        bf.ffprobeBook = myx_classes.Book(asin=str(row["id3-asin"]), title=str(row["id3-title"]), subtitle=row["id3-subtitle"], publisher=row["id3-publisher"], length=row["id3-length"], duration=row["id3-duration"], language=row["id3-language"])
                        bf.isMatched = bool(row["isMatched"])
                        bf.ffprobeBook.setAuthors(row["id3-authors"])
                        bf.ffprobeBook.setNarrators(row["id3-narrators"])
                        bf.ffprobeBook.setSeries(row["id3-seriesparts"])

                        #does this book exist?
                        hashKey=myx_utilities.getHash(f"{i}-{row['book']}")
                        if (hashKey in book):
                            #print (f"{str(row["book"])} exists, just adding the file {bf.file}")
                            book[hashKey].files.append(bf)
                        else:
                            book[hashKey]= myx_classes.MAMBook(str(row["book"]))
                            book[hashKey].metadata = (str(row["metadatasource"]))
                            book[hashKey].paths = (str(row["paths"]))
                            book[hashKey].isMatched = (str(row["isMatched"]).lower() == "true")
                            book[hashKey].files.append(bf)
                            book[hashKey].ffprobeBook = book[hashKey].files[0].ffprobeBook

                            if book[hashKey].isMatched:
                                if book[hashKey].metadata == "audible":
                                    book[hashKey].bestAudibleMatch = myx_classes.Book(asin=str(row["adb-asin"]), title=str(row["adb-title"]), subtitle=row["adb-subtitle"], publisher=row["adb-publisher"], length=row["adb-length"], duration=row["adb-duration"], language=row["adb-language"])
                                    book[hashKey].bestAudibleMatch.setAuthors(row["adb-authors"])
                                    book[hashKey].bestAudibleMatch.setNarrators(row["adb-narrators"])
                                    book[hashKey].bestAudibleMatch.setSeries(row["adb-seriesparts"])                                
                                elif book[hashKey].metadata == "mam":
                                    book[hashKey].bestMAMMatch = myx_classes.Book(asin=str(row["mam-asin"]), title=str(row["mam-title"]), subtitle=row["mam-subtitle"], publisher=row["mam-publisher"], length=row["mam-length"], duration=row["mam-duration"], language=row["mam-language"])
                                    book[hashKey].bestMAMMatch.setAuthors(row["mam-authors"])
                                    book[hashKey].bestMAMMatch.setNarrators(row["mam-narrators"])
                                    book[hashKey].bestMAMMatch.setSeries(row["mam-seriesparts"])                                

                    i += 1
            except csv.Error as e:
                print(f"file {inputFile}: {e}") 

        #Process the books, for the most part this is run, because id3 info is bad/empty
        for b in book.keys():
            #try and match again, the assumption, is that the log has the right information
            #TODO: Check if the file has been processed before, if so skip
            if ((no_cache) or (not book[b].isCached("book", cfg))):
                #file hasn't been processed, but do we need to do a metadata lookup?
                allFiles.append(book[b])
                if (book[b].isMatched):
                    print(f"Processing: {book[b].name}... already matched!")
                    #already matched, don't redo the search/matching
                    matchedFiles.append (book[b])
                else:
                    print(f"Processing: {book[b].name}... {book[b].metadata}")

                    #Search MAM record
                    bf = book[b].files[0]
                    
                    #Search Audible using the provided id3 metadata in the input file
                    if (not ebooks):
                        book[b].getAudibleBooks(httpx, book[b].ffprobeBook, cfg)
                        if (book[b].bestAudibleMatch is not None):
                            book[b].metadata = "audible"                    

                    print (f"Found {len(book[b].mamMatches)} MAM matches, {len(book[b].audibleMatches)} Audible Matches")
                    myx_utilities.printDivider()

                    #if matched, add to matchedFiles
                    if book[b].matchFound():
                        book[b].isMatched=True
                        matchedFiles.append(book[b])
                        
                    else:
                        unmatchedFiles.append(book[b])
            else:
                print (f"Skipping {book[b].name}, already processed...")

        # #Create Hardlinks
        print (f"\nCreating Hardlinks for {len(matchedFiles)} matched books")
        for mb in matchedFiles:
            mb.createHardLinks(cfg)       

            #cache this book - unless it's a dry run
            if (not dryRun):
                mb.cacheMe("book", str(book[b]), cfg)       

            myx_utilities.printDivider()      
        
        #Logging processed files
        print (f"\nLogging {len(allFiles)} processed books")
        myx_utilities.logBooks(logfile, allFiles, cfg)      

        print(f"\nCompleted processing {len(allFiles)} books. {len(matchedFiles)}/{len(unmatchedFiles)} match/unmatch ratio.", end=" ")                 
        print("\n\n")    
    else:
        print(f"Your input file {inputFile} is invalid. Please check and try again!")

    return    

def buildTreeFromHybridSources(path, mediaPath, files, logfile, cfg):
    #Variables
    allFiles=[]
    multiBookCollections=[]
    normalBooks=[]
    matchedFiles=[]
    unmatchedFiles=[]

    #config variables
    format = files
    metadata = cfg.get("Config/metadata")
    dryRun = bool(cfg.get("Config/flags/dry_run"))
    ebooks = bool(cfg.get("Config/flags/ebooks"))
    multibook = bool(cfg.get("Config/flags/multibook"))
    verbose = bool(cfg.get("Config/flags/verbose"))
    no_cache = bool(cfg.get("Config/flags/no_cache"))
    last_scan = cfg.get("Config/last_scan", "")
    last_run = 0

    #if last_scan exists, get the gmtime
    if os.path.exists(last_scan):
        last_run = os.path.getmtime (last_scan)

    #grab all files and put it in allFiles
    #if there were no patters provided, grab ALL known audiobooks, currently these are M4B and MP3 files
    #find all files that fit the pattern
    for f in format:
        pattern = f.translate({ord('['):'[[]', ord(']'):'[]]'})
        print (f"Looking for {f} from {path}")
        allFiles.extend(iglob(f, root_dir=path, recursive=True))

    #Print how many files were found...
    #print (f"Found {len(allFiles)} files to process...\n\n")

    print (f"Building tree from Hybrid Sources:\nSource:{path}\nMedia:{mediaPath}\nLog:{logfile}\n")
    book={}

    #Let's assume that all books are folders, so a file has a parent folder
    print (f"Scanning {len(allFiles)} downloaded since {datetime.fromtimestamp(last_run)}, please wait...")
    #print(f"\nCategorizing books from {len(allFiles)} files, please wait...\n")
    for f in allFiles:
        #only process files downloaded after last_scan
        
        #check the last modtime of this file
        fullpath = os.path.join(path, f)
        if os.path.getmtime(fullpath) > last_run:        
            #for each book file
            print(f"Categorizing: {f}")

            #create a bookFile
            bf=myx_classes.BookFile(f, fullpath, path, mediaPath)

            #create dictionary using book (assumed to be the the parent Folder) as the key
            #if there's no parent folder or if multibook is on, then the filename is the key
            if ((multibook) or (bf.hasNoParentFolder())):
                key=bf.getFileName()
            else:
                key=bf.getParentFolder()

            #read metadata
            bf.ffprobe(key)

            #at this point, the books is either at the root, or under a book folder
            #print (f"Adding {bf.fullPath}\nParent:{bf.getParentFolder()}", end="\r")

            #if the book exists, this must be multi-file book, append the files
            hashKey=myx_utilities.getHash(str(key))
            #print (f"Book: {key}\nHashKey: {hashKey}")
            if hashKey in book:
                book[hashKey].files.append(bf)
            else:
                #New MAMBook file has a name, a file and a ffprobeBook
                book[hashKey]=myx_classes.MAMBook(key)
                book[hashKey].ffprobeBook=bf.ffprobeBook
                book[hashKey].isSingleFile=(multibook) or (bf.hasNoParentFolder())
                book[hashKey].files.append(bf)
                book[hashKey].metadata = "id3"

            #add books from multi-book collections
            for mbc in multiBookCollections:
                #print (f"NewBook: {mbc.name}  Files: {len(mbc.files)}", end="\r")
                #for multi-book collection, each file IS a book
                for f in mbc.files:
                    print (f"Adding {f.file} as a new book", end="\r")
                    key=str(os.path.basename(f.file)) 
                    hashKey=myx_utilities.getHash(key)
                    book[hashKey]=myx_classes.MAMBook(key)
                    #multi book collection titles are almost always bad, so don't even try to use it for search
                    f.ffprobeBook.title=""
                    book[hashKey].ffprobeBook=f.ffprobeBook
                    book[hashKey].isSingleFile=True
                    book[hashKey].files.append(f)

    #for multi-file folders/book - check if there are any multi-book collections
    if multibook:
        print(f"\nCategorized {len(allFiles)} files into books - multibook is on")
    else:
        normalCount = len(book) - len(multiBookCollections)
        print(f"\nCategorized {len(allFiles)} files into {normalCount} normal books, and {len(multiBookCollections)} multi-book collections")
        myx_utilities.printDivider()

    #OK, now that you have categorized the files, we can start processing them
    #At this point all Book files should have already been probed

    #Find Book Matches from MAM and Audible
    print(f"\nPreparing to process {len(book)} books...\n")
    for b in book.keys():    
        #if this book has not been processed before AND it is not a multibook collection
        #print (f"Book: {b} isCached: {book[b].isCached('book')}")
        if ((no_cache) or (not book[b].isCached("book", cfg))):
            #process the book
            print(f"Processing: {book[b].name}...")
            normalBooks.append(book[b])            
            #Process these books the same way, essentially based on the first book in the file list
            bf = book[b].files[0]

            #get MAM first, check if it's a foreign book
            isForeignBook = False
            if ((metadata == "mam") or (metadata == "mam-audible")):
                book[b].getMAMBooks(cfg, bf)
                if (book[b].bestMAMMatch is not None):
                    book[b].metadata = "mam"
                    isForeignBook = (book[b].bestMAMMatch.language.lower() !=  "english")
            
            #Audible search only if this is not ebooks/multibook and metadatasource includes audible, otherwise MAM search is enough
            if (not ebooks) and ((metadata == "audible") or (metadata == "mam-audible")):
                if isForeignBook:
                    #if bestMAMMatch is a foreign book, getAudible using MAM Metadata
                    book[b].getAudibleBooks(httpx, book[b].bestMAMMatch, cfg)
                    if (book[b].bestAudibleMatch is not None):
                        book[b].metadata = "audible"
                else:
                    if (metadata == "mam-audible") and ((not multibook) and (not myx_utilities.isMultiBookCollection(book[b].files[0].file))):
                        mamBestMatch = book[b].getAudibleBooks(httpx, book[b].bestMAMMatch, cfg)
                    else:
                        #This is not a foreign book, do an Audible Search using id3 values first   
                        id3BestMatch = book[b].getAudibleBooks(httpx, book[b].ffprobeBook, cfg)

                    if (mamBestMatch is not None) or (id3BestMatch is not None):
                        book[b].metadata = "audible" 
                                
                    #if this book is NOT a multibook, try MAM metadata search, if this is a collection, ignore MAM
                    # if (not multibook) and (not myx_utilities.isMultiBookCollection(book[b].files[0].file)):
                    #     if (id3BestMatch is None):
                    #         #A match was not found, so try and perform a match based on MAM metadata
                    #         mamBestMatch = book[b].getAudibleBooks(httpx, book[b].bestMAMMatch, cfg)

                    #         if (mamBestMatch is not None):
                    #             book[b].metadata = "audible" 
                    #             # #Override mamBest match if id3 has higher match rate, or if MAM didn't match
                    #             # if (id3BestMatch is not None) and (mamBestMatch is not None):
                    #             #     #A match was found using either metadata
                    #             #     if id3BestMatch.matchRate > mamBestMatch.matchRate:
                    #             #         #Replace bestAudibleMatch with the better matchrate
                    #             #         book[b].bestAudibleMatch = id3BestMatch
                    #             #     else:
                    #             #         book[b].bestAudibleMatch = mamBestMatch
                    #             # elif (id3BestMatch is not None) and (mamBestMatch is None):
                    #             #     #Replace bestAudibleMatch with the better matchrate
                    #             #     book[b].bestAudibleMatch = id3BestMatch
                    #     else:
                    #         book[b].metadata = "audible" 
                    # else:
                    #     #this is multibook so audible only
                    #     if id3BestMatch is not None:
                    #         book[b].metadata = "audible" 

            print (f"Found {len(book[b].mamMatches)} MAM matches, {len(book[b].audibleMatches)} Audible Matches")
            myx_utilities.printDivider()
                
            #if matched, add to matchedFiles
            if book[b].matchFound():
                book[b].isMatched=True
                matchedFiles.append(book[b])
            else:
                unmatchedFiles.append(book[b])

        else:
            print(f"Skipping: {book[b].name}...")
        
    #Create Hardlinks
    print (f"\nCreating Hardlinks for {len(matchedFiles)} matched books\n")
    for mb in matchedFiles:
        mb.createHardLinks(cfg)
        #cache this book - unless it's a dry run
        if (not dryRun):
            mb.cacheMe("book", str(book[b]), cfg)

        myx_utilities.printDivider()

    #Logging processed files
    print (f"\nLogging {len(normalBooks)} processed books")
    myx_utilities.logBooks(logfile, normalBooks, cfg)  

    print(f"Completed processing {len(normalBooks)} books. {len(matchedFiles)}/{len(normalBooks) - len(matchedFiles)} match/unmatch ratio.")
    myx_utilities.printDivider()


    return


def main(cfg):
    #make sure log_path and cache path exists
    log_path=myx_utilities.getLogPath(cfg)

    #create the logfile
    logfile=os.path.join(os.path.abspath(log_path),f"booktree_log_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv")

    for paths in cfg.get("Config/paths"):
        #validate that source_path and media_path exists
        files=paths["files"]
        path=paths["source_path"]
        mediaPath=paths["media_path"]

        if (os.path.exists(path) and os.path.exists(mediaPath)):
            #build tree from identified sources
            if (cfg.get("Config/metadata") == "log"):
                buildTreeFromLog(files, logfile, cfg)
            else:
                buildTreeFromHybridSources(path, mediaPath, files, logfile, cfg)            
        else:
            print(f"Your source and media paths are invalid. Please check and try again!\nSource:{path}\nMedia:{mediaPath}")

if __name__ == "__main__":
    
    if not sys.version_info > (3, 10):
        print ("booktree requires python 3.10 or higher. Please upgrade your version")
    else:
        #process commandline arguments
        myx_args.params = myx_args.importArgs()

        #check if config files are present
        if ((myx_args.params.config_file is not None) and os.path.exists(myx_args.params.config_file)):
            try:
                #import config
                cfg = myx_args.Config(myx_args.params)

            except Exception as e:
                raise Exception(f"\nThere was a problem reading your config file {myx_args.params.config_file}: {e}\n")
            
            #start the program
            main(cfg)

        else:
            print(f"\nYour config path is invalid. Please check and try again!\n\tConfig file path:{myx_args.params.config_file}\n")






        






        
        


 


