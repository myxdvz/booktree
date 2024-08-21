import argparse
import os
from pprint import pprint

#Module Variables
params:any

def importArgs():
    appDescription = """Reorganize your audiobooks using ID3 or Audbile metadata.\nThe originals are untouched and will be hardlinked to their destination"""
    parser = argparse.ArgumentParser(prog="booktree", description=appDescription)
    #you want a specific file or pattern
    parser.add_argument("--file", default="", help="The file or files(s) you want to process.  Accepts * and ?. Defaults to *.m4b/*.mp3")
    #path to source files, e.g. /data/torrents/downloads
    parser.add_argument("--source_path", default=".", help="Where your unorganized files are")
    #path to media files, e.g. /data/media/abs
    parser.add_argument("--media_path", help="Where your organized files will be, i.e. your Audiobookshelf library", required=True)
    #path to log files, e.g. /data/media/abs
    parser.add_argument("--log_path", default="", help="Where your log files will be")
    #medata source (audible|mam|mam-audible|id3|log)
    parser.add_argument("metadata", choices=["audible","mam","mam-audible","log"], default="mam-audible", help="Source of the metada: (audible, mam, mam-audible)")
    parser.add_argument("--session", default="", help="Your session cookie")
    parser.add_argument("--matchrate", default=60, help="Minimum acceptable fuzzy match rate. Defaults to 60")
    #debug flags
    parser.add_argument("--dry-run", default=False, action="store_true", help="If provided, will only create log and not actually build the tree")
    parser.add_argument("--verbose", default=False, action="store_true", help="If provided, will print additional info")
    #Advanced flags
    parser.add_argument("--no-opf", default=False, action="store_true", help="If provided, skips OPF file")
    parser.add_argument("--no-cache", default=False, action="store_true", help="If provided, skips caching")
    parser.add_argument("--multibook", default=False, action="store_true", help="If provided, will process books at file level")
    parser.add_argument("--fixid3", default=False, action="store_true", help="If provided, will attempt to fix id3 metadata")
    parser.add_argument("--ebooks", default=False, action="store_true", help="If provided, will look for ebooks and skip audible")

    #get all arguments
    args = parser.parse_args()
    if (len(args.log_path)==0):
        args.log_path=os.path.join(os.getcwd(),"logs")    

    #set module variable to args
    return args
