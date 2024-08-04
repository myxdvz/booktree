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

#Global Vars
allFiles=[]
multiBookCollections=[]
multiFileCollections=[]
normalBooks=[]
matchedFiles=[]
unmatchedFiles=[]
audibleAuthFile=""

#Main Functions
def buildTreeFromLog(path, mediaPath, logfile, dryRun=False):
    #read from the logfile - generate book files from there

    #for each row, create hardlinks
    return    

def buildTreeFromData(path, mediaPath, logfile, dryRun=False):
    print (f"Building tree structure using Audible metadata:\nSource:{path}\nMedia:{mediaPath}\nLog:{logfile}")
    #if files were found, process them all
    if (len(allFiles)>0):
        auth, client = myx_audible.audibleConnect(myx_args.params.auth,audibleAuthFile)

        for f in allFiles:
            fullpath=os.path.join(myx_args.params.source_path, f)
            print ("Processing {}".format(fullpath))
            # create a Book File object and add it to the list of files to be processed
            bf=myx_classes.BookFile(f, fullpath, myx_args.params.source_path)
            
            # probe this file
            # print ("Performing ffprobe...")
            # bf.ffprobe()
            # do an audible match
            print ("Performing ffprobe and audible match...")
            bf.matchBook(client,myx_args.params.match)
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
        myx_audible.audibleDisconnect(auth)

    else:
        #Pattern yielded no files
        print ("No files found to process")

def buildTreeFromMAM (path, mediaPath, logfile, dryRun=False):
    print (f"Building tree structure using MAM metadata:\nSource:{path}\nMedia:{mediaPath}\nLog:{logfile}")
    for f in allFiles:
        fullpath=os.path.join(myx_args.params.source_path, f)
        print ("Processing {}".format(fullpath))
        bf=myx_classes.BookFile(f, fullpath, myx_args.params.source_path)
        bf.ffprobe()

        #search MAM by filename
        matchBook=myx_mam.getMAMBook(myx_args.params.session, os.path.basename(fullpath), bf.ffprobeBook.getAuthors())
        #pprint(matchBook)
        if (len(matchBook)==1):
            #Exact Match
            bf.isMatched=True
            bf.audibleMatch=matchBook[0]
            matchedFiles.append(bf)
            if myx_args.params.verbose:
                pprint(bf.audibleMatch)
        else:
            unmatchedFiles.append(bf)
            if (len(matchBook) > 1):
                bf.audibleMatches.extend(matchBook)

def buildTreeFromHybridSources(path, mediaPath, logfile, dryRun=False):
    print (f"Building tree from Hybrid Sources:\nSource:{path}\nMedia:{mediaPath}\nLog:{logfile}\n")
    book={}

    #Let's assume that all books are folders, so a file has a parent folder
    print(f"\nCategorizing books from {len(allFiles)} files, please wait...")
    for f in allFiles:
        #for each book file
        print(f"Categorizing: {f}...\r", end="\r")
        #create a bookFile
        fullpath=os.path.join(myx_args.params.source_path, f)
        bf=myx_classes.BookFile(f, fullpath, myx_args.params.source_path)
        bf.ffprobe()

        if myx_args.params.verbose:
            print ("Adding {}\nParent:{}".format(bf.fullPath,bf.getParentFolder()))

        #create dictionary using book (assumed to be the the parent Folder) as the key
        #if there's no parent folder, then the filename is the key
        if bf.hasNoParentFolder():
            key=bf.getFileName()
        else:
            key=bf.getParentFolder()
        
        #if the book exists, this must be multi-file book, append the files
        hashKey=str(hash(key))
        if hashKey in book:
            book[hashKey].files.append(bf)
        else:
            #New MAMBook file has a name, a file and a ffprobeBook
            book[hashKey]=myx_classes.MAMBook(key)
            book[hashKey].ffprobeBook=bf.ffprobeBook
            book[hashKey].isSingleFile=bf.hasNoParentFolder()
            book[hashKey].files.append(bf)

    for b in book.keys():
        #if this is a multifile book
        if len(book[b].files) > 1:
            newBooks, isMultiBookCollection = myx_utilities.isMultiBookCollection(book[b])
            if (isMultiBookCollection):
                book[b].isMultiBookCollection=True
                multiBookCollections.append(book)
                if myx_args.params.verbose:
                    print (f"{book[b].name} is a multi-BOOK collection: {len(newBooks)}")

                if myx_args.params.verbose:
                    for b in newBooks:
                        print(b.name)
                        for f in b.files:
                            print (f.file)
                    #pprint (newBooks)
            else:
                book[b].isMultiFileBook=True
                multiFileCollections.append(book)
                if myx_args.params.verbose:
                    print (f"{book[b].name} is a multi-FILE collection: {len(book[b].files)}")
        else:
            #single file books
            if myx_args.params.verbose:
                print (f"{book[b].name} is a single file book")


    #for multi-file folders/book - check if there are any multi-book collections
    normalCount = len(book) - len(multiFileCollections) - len(multiBookCollections)
    print(f"\n\nCategorized {len(allFiles)} files into {normalCount} normal books, {len(multiFileCollections)} multi-file books and {len(multiBookCollections)} multi-book collections")
    myx_utilities.printDivider()

    #OK, now that you have categorized the files, we can start processing them
    #At this point all Book files should have already been probed

    #login to Audible
    auth, client = myx_audible.audibleConnect(myx_args.params.auth, audibleAuthFile)

    #Find Book Matches from MAM and Audible
    for b in book.keys():    
        if (not book[b].isMultiBookCollection):
            #processed book
            print(f"Processing: {book[b].name}...")
            normalBooks.append(book[b])            
            #Process these books the same way, essentially based on the first book in the file list
            bf = book[b].files[0]

            #search MAM record
            book[b].getMAMBooks(myx_args.params.session, bf)
                
            #now, Search Audible using either MAM (better) or ffprobe metadata
            book[b].getAudibleBooks(client)

            print (f"Found {len(book[b].mamMatches)} MAM matches, {len(book[b].audibleMatches)} Audible Matches")
            myx_utilities.printDivider()

            #if matched, add to matchedFiles
            if book[b].isMatched():
                matchedFiles.append(book[b])
            else:
                unmatchedFiles.append(book[b])

            if myx_args.params.verbose:
                pprint(book[b])
        
    #disconnect
    myx_audible.audibleDisconnect(auth)

    #Create Hardlinks
    print (f"\nCreating Hardlinks for {len(matchedFiles)} matched books")
    for mb in matchedFiles:
        mb.createHardLinks(mediaPath,dryRun)

    #Logging processed files
    print (f"\nLogging {len(normalBooks)} processed books")
    myx_utilities.logBooks(logfile, normalBooks)  

    print(f"\nCompleted processing {len(normalBooks)} books. {len(matchedFiles)}/{len(normalBooks) - len(matchedFiles)} match/unmatch ratio.", end=" ")                 
    if (len(multiBookCollections)):
        print(f"{len(multiBookCollections)} multi-book collection skipped (future update!)")                 
    
    print("\n\n")
    return


def main():
    #create the logfile
    logfile=os.path.join(os.path.abspath(myx_args.params.log_path),"booktree_log_{}.csv".format(datetime.now().strftime("%Y%m%d%H%M%S")))

    #validate that source_path and media_path exists
    path=myx_args.params.source_path
    mediaPath=myx_args.params.media_path

    if (os.path.exists(path) and os.path.exists(mediaPath)):
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
        
        # for f in allFiles:
        #     fullpath=os.path.join(myx_args.params.source_path, f)
        #     print("f:{}, fp:{}\n\n".format(f, fullpath))
        match myx_args.params.metadata:
            case "mam":
                buildTreeFromMAM(path, mediaPath, logfile, myx_args.params.dry_run)

            case "audible":
                buildTreeFromData(path, mediaPath, logfile, myx_args.params.dry_run)
        
            case "hybrid":
                buildTreeFromHybridSources(path, mediaPath, logfile, myx_args.params.dry_run)

            case _:
                print ("This feature is coming soon! Right now, only audible and mam are supported")
    
        # #for files with matches, hardlink them
        # if (len(matchedFiles)):
        #     print ("Creating hard links for matched files...")
        #     myx_utilities.createHardLinks(matchedFiles, mediaPath, False)

        #     #log matched files
        #     print ("Logging matched books...")
        #     myx_utilities.logBookRecords(logfile, matchedFiles)

        # if (len(unmatchedFiles)):
        # #for files with matches, hardlink them
        #     print ("Creating hard links for unmatched files...")
        #     myx_utilities.createHardLinks(unmatchedFiles, mediaPath, False)

        #     #log unmatched files
        #     print ("Logging unmatched books...")
        #     myx_utilities.logBookRecords(logfile, unmatchedFiles)  

        #Completed
        #print(f"Completed processing {len(allFiles)} files. {len(matchedFiles)}/{len(allFiles) - len(unmatchedFiles)} match/unmatch ratio.")                 

    else:
        print(f"Your source and media paths are invalid. Please check and try again!\nSource:{path}\nMedia:{mediaPath}")

if __name__ == "__main__":
    
    #process commandline arguments
    myx_args.params = myx_args.importArgs()

    #add calculated parameters
    audibleAuthFile=os.path.join(myx_args.params.log_path, "booktree.json")

    #set
    #pprint(args)

    #start the program
    main()
 

    




