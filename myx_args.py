import argparse
import os
from pprint import pprint

#Module Variables
params:any

def importArgs():
    appDescription = """Reorganize your audiobooks using ID3 or Audbile metadata.\nThe originals are untouched and will be hardlinked to their destination"""
    parser = argparse.ArgumentParser(prog="booktree", description=appDescription)
    #you want a specific file or pattern
    parser.add_argument("--file", default="", help="The file or files(s) you want to process.  Accepts * and ?. Defaults to *.m4b")
    #path to source files, e.g. /data/torrents/downloads
    parser.add_argument("--source_path", default=".", help="Where your unorganized files are")
    #path to media files, e.g. /data/media/abs
    parser.add_argument("--media_path", help="Where your organized files will be, i.e. your Audiobookshelf library", required=True)
    #path to log files, e.g. /data/media/abs
    parser.add_argument("--log_path", default="", help="Where your log files will be")
    #dry-run
    parser.add_argument("--dry-run", default=False, action="store_true", help="If provided, will only create log and not actually build the tree")
    #medata source (audible|id3|log)
    parser.add_argument("metadata", choices=["audible","mam","mam-audible"], default="mam-audible", help="Source of the metada: (audible, mam, mam-audible)")
    #if medata source=audible, you need to provide your username and password
    parser.add_argument("-auth", choices=["login","browser"], default="login", help="When you get the CFA prompts, switch to browser mode")
    parser.add_argument("-user", help="Your audible username", required=True)
    parser.add_argument("-pwd", help="Your audible password", required=True)
    parser.add_argument("--session", default="", help="Your session cookie")
    parser.add_argument("-match", type=int, default=35, help="The min acceptable ratio for the fuzzymatching algorithm. Defaults to 35")
    parser.add_argument("-log", help="The file path/name to be used as metadata input")
    #verbose
    parser.add_argument("--verbose", default=False, action="store_true", help="Level of prints on the screen")

    #get all arguments
    args = parser.parse_args()
    if (len(args.log_path)==0):
        args.log_path=os.path.join(os.getcwd(),"logs")    

    #set module variable to args
    return args
