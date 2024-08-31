import argparse
import os
import json
from pprint import pprint

#Module Variables
params:any

def importArgs():
    appDescription = """Reorganize your audiobooks using ID3 or Audbile metadata.\nThe originals are untouched and will be hardlinked to their destination"""
    parser = argparse.ArgumentParser(prog="booktree", description=appDescription)
    parser.add_argument ("config_file", help="Your Config File")
    parser.add_argument ("-dc","--default_config_file", help="Default Config File")
    parser.add_argument ("--dry-run", default=None, action="store_true", help="If provided, will override dryRun in config")

    # #you want a specific file or pattern
    # parser.add_argument("--file", default="", help="The file or files(s) you want to process.  Accepts * and ?. Defaults to *.m4b/*.mp3")
    # #path to source files, e.g. /data/torrents/downloads
    # parser.add_argument("--source_path", default=".", help="Where your unorganized files are")
    # #path to media files, e.g. /data/media/abs
    # parser.add_argument("--media_path", help="Where your organized files will be, i.e. your Audiobookshelf library", required=True)
    # #path to log files, e.g. /data/media/abs
    # parser.add_argument("--log_path", default="", help="Where your log files will be")
    # #medata source (audible|mam|mam-audible|id3|log)
    # parser.add_argument("metadata", choices=["audible","mam","mam-audible","log"], default="mam-audible", help="Source of the metada: (audible, mam, mam-audible)")
    # parser.add_argument("--session", default="", help="Your session cookie")
    # parser.add_argument("--matchrate", default=60, help="Minimum acceptable fuzzy match rate. Defaults to 60")
    # #debug flags
    # parser.add_argument("--dry-run", default=False, action="store_true", help="If provided, will only create log and not actually build the tree")
    # parser.add_argument("--verbose", default=False, action="store_true", help="If provided, will print additional info")
    # #Advanced flags
    # parser.add_argument("--no-opf", default=False, action="store_true", help="If provided, skips OPF file")
    # parser.add_argument("--no-cache", default=False, action="store_true", help="If provided, processes books that have been processed/cached before")
    # parser.add_argument("--multibook", default=False, action="store_true", help="If provided, will process books at file level")
    # parser.add_argument("--fixid3", default=False, action="store_true", help="If provided, will attempt to fix id3 metadata")
    # parser.add_argument("--ebooks", default=False, action="store_true", help="If provided, will look for ebooks and skip audible")
    # parser.add_argument("--add-narrators", default=False, action="store_true", help="If provided,include the narrators in the path")

    #get all arguments
    args = parser.parse_args()

    # if (len(args.log_path)==0):
    #     args.log_path=os.path.join(os.getcwd(),"logs")    

    #set module variable to args
    return args

def merge_dictionaries_recursively (dict1, dict2):
    """ Update two config dictionaries recursively.
        Args:
            dict1 (dict): first dictionary to be updated
            dict2 (dict): second dictionary which entries should be preferred
    """
    if dict2 is None: return

    for k, v in dict2.items():
        if k not in dict1:
            dict1[k] = dict()
        if isinstance(v, dict):
            merge_dictionaries_recursively (dict1[k], v)
        else:
            dict1[k] = v    

class Config(object):  
    """ Simple dict wrapper that adds a thin API allowing for slash-based retrieval of
        nested elements, e.g. cfg.get_config("meta/dataset_name")
    """
    def __init__(self, config_path, default_path=None, dryRun=None):
        with open(config_path) as cf_file:
            cfg = json.loads (cf_file.read())

        if default_path is not None:
            with open(default_path) as def_cf_file:
                default_cfg = json.loads (def_cf_file.read())
                
            merge_dictionaries_recursively(default_cfg, cfg)

        #override dryRun with command line param
        if dryRun is not None:
            cfg["Config"]["flags"]["dry_run"] = bool(dryRun)

        self._data = cfg            

    def get(self, path=None, default=None):
        # we need to deep-copy self._data to avoid over-writing its data
        sub_dict = dict(self._data)

        if path is None:
            return sub_dict

        path_items = path.split("/")[:-1]
        data_item = path.split("/")[-1]

        try:
            for path_item in path_items:
                sub_dict = sub_dict.get(path_item)

            value = sub_dict.get(data_item, default)

            return value
        except (TypeError, AttributeError):
            return default
