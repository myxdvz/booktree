from pathlib import Path
from pprint import pprint
from datetime import datetime
from glob import iglob, glob
import os, sys, subprocess, shlex, re
import myx_classes
import myx_audible
import myx_utilities
import myx_mam
import myx_args
import csv
import httpx

#Global Vars
allFiles=[]
collections=[]
multiBookCollections=[]
multiFileCollections=[]
normalBooks=[]
matchedFiles=[]
unmatchedFiles=[]
audibleAuthFile=""

#Main Functions
def buildTreeFromLog(path, mediaPath, logfile, dryRun=False):
    #read from the logfile - generate book files from there
    book={}
    inputFile=myx_args.params.file
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
                        #file, path
                        f = str(row["file"])
                        fullpath=os.path.join(path, f)
                        bf=myx_classes.BookFile(f, fullpath, path, isHardlinked=bool(row["isHardLinked"]))
                        
                        #parse authors and series
                        bf.ffprobeBook = myx_classes.Book(asin=str(row["id3-asin"]), title=str(row["id3-title"]), subtitle=row["id3-subtitle"], publicationName=row["id3-publicationName"], length=row["id3-length"], duration=row["id3-duration"])
                        bf.ffprobeBook.setAuthors(row["id3-authors"])
                        bf.ffprobeBook.setSeries(row["id3-seriesparts"])

                        #does this book exist?
                        hashKey=myx_utilities.getHash(row["book"])
                        if (hashKey in book):
                            #print (f"{str(row["book"])} exists, just adding the file {bf.file}")
                            book[hashKey].files.append(bf)
                        else:
                            #print (f"{str(row['book'])} is new, adding the book")
                            book[hashKey]= myx_classes.MAMBook(str(row["book"]))
                            book[hashKey].metadata = (row["metadatasource"])
                            book[hashKey].files.append(bf)
                            book[hashKey].ffprobeBook = book[hashKey].files[0].ffprobeBook    

                            # if bool(row["isMatched"]):
                            #     book[hashKey].bestMAMMatch = myx_classes.Book(asin=row["mam-asin"], title=row["mam-title"], subtitle=row["mam-subtitle"], publicationName=row["mam-publicationName"], length=row["mam-length"], duration=row["mam-duration"], series=row["mam-series"], authors=row["mam-authors"], narrators=row["mam-narrators"] )
                            #     book[hashKey].bestAudibleMatch = myx_classes.Book(asin=row["adb-asin"], title=row["adb-title"], subtitle=row["adb-subtitle"], publicationName=row["adb-publicationName"], length=row["adb-length"], duration=row["adb-duration"], series=row["adb-series"], authors=row["adb-authors"], narrators=row["adb-narrators"] )
                            # else:
                            book[hashKey].bestMAMMatch = None
                            book[hashKey].bestAudibleMatch = None

                    i += 1
            except csv.Error as e:
                print(f"file {inputFile}: {e}") 

        #Process the books, for the most part this is run, because id3 info is bad/empty
        for b in book.keys():
            #try and match again, the assumption, is that the log has the right information
            #TODO: Check if the file has been processed before, if so skip
            if (book[b].isCached("book")):
                #Skipping
                print (f"Skipping {book[b].name}, already processed...")
            else:
                #file hasn't been processed, but do we need to do a metadata lookup?
                allFiles.append(book[hashKey])
                if (book[b].metadata != "as-is"):
                    print(f"Processing: {book[b].name}... {book[b].metadata}")
                    #if it's not Matched, match it
                    if ((book[b].bestMAMMatch is None) and (book[b].bestAudibleMatch is None)):
                        #Search MAM record
                        bf = book[b].files[0]
                        
                        #log mode bypasses MAM because the user is already fixing the id3 directly
                        #book[b].getMAMBooks(myx_args.params.session, bf)

                        #Search Audible using the provided id3 metadata in the input file
                        book[b].getAudibleBooks(httpx)

                        print (f"Found {len(book[b].mamMatches)} MAM matches, {len(book[b].audibleMatches)} Audible Matches")
                        myx_utilities.printDivider()

                        #set the best metadata source: Audible > MAM > ID3
                        if (book[b].bestAudibleMatch is not None):
                            book[b].metadata = "audible"
                        elif (book[b].bestMAMMatch is not None):
                            book[b].metadata = "mam"
                        else:
                            book[b].metadata = "id3"
                        
                        #if matched, add to matchedFiles
                        if book[b].isMatched():
                            matchedFiles.append(book[b])
                            
                        else:
                            unmatchedFiles.append(book[b])
                else:
                    #if metadata == as is, use the id3 tag as is
                    matchedFiles.append(book[b])

        # #Create Hardlinks
        print (f"\nCreating Hardlinks for {len(matchedFiles)} matched books")
        for mb in matchedFiles:
            mb.createHardLinks(mediaPath,dryRun)       

            #cache this book - unless it's a dry run
            if (not dryRun):
                mb.cacheMe("book", str(book[b]))             
        
        #Logging processed files
        print (f"\nLogging {len(allFiles)} processed books")
        myx_utilities.logBooks(logfile, allFiles)      

        print(f"\nCompleted processing {len(allFiles)} books. {len(matchedFiles)}/{len(unmatchedFiles)} match/unmatch ratio.", end=" ")                 
        print("\n\n")    
    else:
        print(f"Your input file {inputFile} is invalid. Please check and try again!")

    return    

def buildTreeFromHybridSources(path, mediaPath, logfile, dryRun=False):
    #grab all files and put it in allFiles
    #if there were no patters provided, grab ALL known audiobooks, currently these are M4B and MP3 files
    if (len(myx_args.params.file)==0):
        for f in ("**/*.m4b","**/*.mp3"):
            print (f"Looking for {f} from {path}")
            allFiles.extend(iglob(f, root_dir=myx_args.params.source_path, recursive=True))
    else:
        #find all files that fit the input pattern - escape [] for glob to work
        pattern = myx_args.params.file.translate({ord('['):'[[]', ord(']'):'[]]'})
        #find all files that fit the input pattern
        print (f"Looking for {pattern} from {path}")
        allFiles.extend(iglob(pattern, root_dir=path, recursive=True))

    #Print how many files were found...
    print (f"Found {len(allFiles)} files to process...\n\n")

    print (f"Building tree from Hybrid Sources:\nSource:{path}\nMedia:{mediaPath}\nLog:{logfile}\n")
    book={}

    #Let's assume that all books are folders, so a file has a parent folder
    print(f"\nCategorizing books from {len(allFiles)} files, please wait...")
    for f in allFiles:
        #for each book file
        print(f"Categorizing: {f}\r", end="\r")

        #create a bookFile
        fullpath=os.path.join(myx_args.params.source_path, f)
        bf=myx_classes.BookFile(f, fullpath, myx_args.params.source_path)

        #create dictionary using book (assumed to be the the parent Folder) as the key
        #if there's no parent folder or if multibook is on, then the filename is the key
        if ((myx_args.params.multibook) or (bf.hasNoParentFolder())):
            key=bf.getFileName()
        else:
            key=bf.getParentFolder()

        #read metadata
        bf.ffprobe(key)

        #if bad ffprobe data or fixid3
        if (len(bf.ffprobeBook.title) == 0) or (myx_args.params.fixid3):
            bf.ffprobeBook.title = myx_utilities.getAltTitle (key, bf.ffprobeBook)        

        #at this point, the books is either at the root, or under a book folder
        if myx_args.params.verbose:
            print (f"Adding {bf.fullPath}\nParent:{bf.getParentFolder()}")

        #if the book exists, this must be multi-file book, append the files
        hashKey=myx_utilities.getHash(str(key))
        #print (f"Book: {key}\nHashKey: {hashKey}")
        if hashKey in book:
            book[hashKey].files.append(bf)
        else:
            #New MAMBook file has a name, a file and a ffprobeBook
            book[hashKey]=myx_classes.MAMBook(key)
            book[hashKey].ffprobeBook=bf.ffprobeBook
            book[hashKey].isSingleFile=(myx_args.params.multibook) or (bf.hasNoParentFolder())
            book[hashKey].files.append(bf)

    #we don't know this is multi-book, make this determination (will be slow)
    # if (not myx_args.params.multibook):
    #     for b in book.keys():
    #         #if this is a multifile book
    #         if len(book[b].files) > 1:
    #             #For performance purposes, assume that all multifile books are multi-book
    #             book[b].isMultiBookCollection=True
    #             multiBookCollections.append(book[b])
    #             if myx_args.params.verbose:
    #                 print (f"{book[b].name} could be a multi-BOOK collection: {len(book[b].files)}")

    #             # newBooks, isMultiBookCollection = myx_utilities.isMultiBookCollection(book[b])
    #             # if (isMultiBookCollection):
    #             #     book[b].isMultiBookCollection=True
    #             #     multiBookCollections.append(book[b])
    #             #     if myx_args.params.verbose:
    #             #         print (f"{book[b].name} is a multi-BOOK collection: {len(newBooks)}")
    #             # else:
    #             #     book[b].isMultiFileBook=True
    #             #     multiFileCollections.append(book[b])
    #             #     if myx_args.params.verbose:
    #             #         print (f"{book[b].name} is a multi-FILE collection: {len(book[b].files)}")
    #         else:
    #             #single file books
    #             if myx_args.params.verbose:
    #                 print (f"{book[b].name} is a single file book")

        #add books from multi-book collections
        for mbc in multiBookCollections:
            print (f"NewBook: {mbc.name}  Files: {len(mbc.files)}")
            #for multi-book collection, each file IS a book
            for f in mbc.files:
                print (f"Adding {f.file} as a new book")
                key=str(os.path.basename(f.file)) 
                hashKey=myx_utilities.getHash(key)
                book[hashKey]=myx_classes.MAMBook(key)
                #multi book collection titles are almost always bad, so don't even try to use it for search
                f.ffprobeBook.title=""
                book[hashKey].ffprobeBook=f.ffprobeBook
                book[hashKey].isSingleFile=True
                book[hashKey].files.append(f)

    #for multi-file folders/book - check if there are any multi-book collections
    if myx_args.params.multibook:
        print(f"\n\nCategorized {len(allFiles)} files into books - multibook is on")
    else:
        normalCount = len(book) - len(multiFileCollections) - len(multiBookCollections)
        print(f"\n\nCategorized {len(allFiles)} files into {normalCount} normal books, {len(multiFileCollections)} multi-file books and {len(multiBookCollections)} multi-book collections")
        myx_utilities.printDivider()

    #OK, now that you have categorized the files, we can start processing them
    #At this point all Book files should have already been probed

    #login to Audible
    # auth, client = myx_audible.audibleConnect(myx_args.params.auth, audibleAuthFile)

    #Find Book Matches from MAM and Audible
    print(f"\n\nPreparing to process {len(book)} books...")
    for b in book.keys():    
        #if this book has not been processed before AND it is not a multibook collection
        #print (f"Book: {b} isCached: {book[b].isCached('book')}")
        if (not book[b].isCached("book")) and (not book[b].isMultiBookCollection):
            #process the book
            print(f"Processing: {book[b].name}...")
            normalBooks.append(book[b])            
            #Process these books the same way, essentially based on the first book in the file list
            bf = book[b].files[0]

            #if bad metatag or if the title follows a specific pattern, derive from the book name/filename
            # if myx_args.params.fixid3:
            #     bf.__getBookFromTag__(book[b].name, bf.ffprobeBook)

            #search MAM record
            if (myx_args.params.metadata == "mam") or (myx_args.params.metadata == "mam-audible"):
                book[b].getMAMBooks(myx_args.params.session, bf)
                
            #now, Search Audible using either MAM (better) or ffprobe metadata
            if (myx_args.params.metadata == "audible") or (myx_args.params.metadata == "mam-audible"):
                book[b].getAudibleBooks(httpx)
                
            print (f"Found {len(book[b].mamMatches)} MAM matches, {len(book[b].audibleMatches)} Audible Matches")
            myx_utilities.printDivider()

            #set the best metadata source: Audible > MAM > ID3
            if (book[b].bestAudibleMatch is not None):
                book[b].metadata = "audible"
            elif (book[b].bestMAMMatch is not None):
                book[b].metadata = "mam"
            else:
                book[b].metadata = "id3"
                
            #if matched, add to matchedFiles
            if book[b].isMatched():
                matchedFiles.append(book[b])
            else:
                unmatchedFiles.append(book[b])

        else:
            print(f"Skipping: {book[b].name}...")
        
    #Create Hardlinks
    print (f"\nCreating Hardlinks for {len(matchedFiles)} matched books")
    for mb in matchedFiles:
        mb.createHardLinks(mediaPath,dryRun)

        #cache this book - unless it's a dry run
        if (not dryRun):
            mb.cacheMe("book", str(book[b]))

    #Logging processed files
    print (f"\nLogging {len(normalBooks)} processed books")
    myx_utilities.logBooks(logfile, normalBooks)  

    print(f"\nCompleted processing {len(normalBooks)} books. {len(matchedFiles)}/{len(normalBooks) - len(matchedFiles)} match/unmatch ratio.", end=" ")                              
    
    print("\n\n")
    return


def main():
    #create the logfile
    logfile=os.path.join(os.path.abspath(myx_args.params.log_path),f"booktree_log_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv")

    #validate that source_path and media_path exists
    path=myx_args.params.source_path
    mediaPath=myx_args.params.media_path

    if (os.path.exists(path) and os.path.exists(mediaPath)):
        #build tree from identified sources
        if (myx_args.params.metadata == "log"):
            buildTreeFromLog(path, mediaPath, logfile, myx_args.params.dry_run)
        else:
            buildTreeFromHybridSources(path, mediaPath, logfile, myx_args.params.dry_run)
        
    else:
        print(f"Your source and media paths are invalid. Please check and try again!\nSource:{path}\nMedia:{mediaPath}")

if __name__ == "__main__":
    
    if not sys.version_info > (3, 10):
        print ("booktree requires python 3.10 or higher. Please upgrade your version")
    else:
        #process commandline arguments
        myx_args.params = myx_args.importArgs()

        #build __cache__ folders if they don't exist
        os.makedirs(os.path.join(os.getcwd(), "__cache__", "book"), exist_ok=True)
        os.makedirs(os.path.join(os.getcwd(), "__cache__", "mam"), exist_ok=True)
        os.makedirs(os.path.join(os.getcwd(), "__cache__", "audible"), exist_ok=True)

        # test RE titles
        # book=myx_classes.Book()
        # myx_utilities.getBookFromTag("The Seeress of Kell (Malloreon 5), Part 2", book)
        # print ("\n\n")

        # myx_utilities.getBookFromTag("Polgara the Sorceress, Part 1", book)
        # print ("\n\n")

        # myx_utilities.getBookFromTag("Dark-Hunter 23 - Styxx - Part 3", book)
        # print ("\n\n")

        #set
        #pprint(myx_args.params)
        #myx_args.params.verbose=True

        #start the program
        main()



        






        
        


 


