# booktree Configuration

A copy of default_config.cfg can be found under the /templates folder.  It is recommended that you create a config file for each scenario that you want to run.  I personally have 4:  audiobooks, ebooks, log mode and multi-book

### Default Config File
~~~
{
    "Config": {
        "metadata": "mam-audible",
        "matchrate": 60,
        "fuzzy_match": "token_sort",
        "log_path": "/logs",    
        "cache_path": "/config",    
        "session": "",
        "paths": [{
            "files": ["**/*.m4b", "**/*.mp3", "**/*.m4a"],
            "source_path": "/path/to/downloads",
            "media_path": "/path/to/media/library"
        }],
        "flags": {
            "dry_run": 0,
            "verbose": 1,
            "multibook": 0,
            "ebooks": 0,
            "no_opf": 0,
            "no_cache": 0,
            "fixid3": 0,
            "add_narrators": 0 
        },
        "target_path": {
            "multi_author": "first_author",
            "in_series": "{author}/{series}/{series} #{part} - {title}",
            "no_series": "{author}/{title}",
            "disc_folder": "{title} {disc}"
        },
        "tokens":{
            "skip_series": 0,
            "kw_ignore": [".", ":", "_", "[", "]", "{", "}", ",", ";", "(", ")"],
            "kw_ignore_words": ["the","and","m4b","mp3","series","audiobook","audiobooks", "book", "part", "track", "novel", "disc"],
            "title_patterns": ["-end", "\bpart\b", "\btrack\b", "\bof\b",  "\bbook\b", "m4b", "\\(", "\\)", "_", "\\[", "\\]", "\\.", "\\s?-\\s?"]
        }  
    }
}
~~~

| Config Path | Subpath | Description   | Suggested Value |
| ----------- | ------- | -----------   | --------------- |
| metadata    |         | Source of the metada: (audible, mam, mam-audible) | mam-audible    |
| matchrate   |         | Minimum acceptable fuzzy match rate. <br/>To increase match rate, check the matchrate values from the log, and lower this value | 60     |
| fuzzy_match |         | Fuzzy match algorithm: (partial, token_sort, ratio) | token_sort |
| log_path    |         | Where your log files will be saved. If not set, will default to "logs" | /logs (for docker), logs (for local)   |
| cache_path  |         | Where your log files will be saved. If not set, will default to "logs" | /config   |
| session     |         | MAM Session ID (can be removed once one has been saved) |    |
| paths       |         | This is a *list* of folders and files to be processed              |
| | files               | File patterns to be searched | ["\*\*/\*.m4b", "\*\*/\*.mp3", "\*\*/\*.m4a"]    |
| | source_path         | Unorganized folder location | /path/to/downloads   |
| | media_path          | Organized media folder location | /path/to/ABS/library |
| flags       |         | These flags can be overriden via command line arguments |     |
| | dry_run             | --dry-run, Dry run only, files are not actually hardlinked  | 0    |
| | verbose             | --verbose, Display info and debug information on the screen | 1    |
| | multibook           | --multibook, If true, assumes each file is a book | 0    |
| | ebooks              | --ebooks, If true, bypasses audible search | 0    |
| | no_opf              | --no-opf, If true, skips OPF file creation | 0   |
| | no_cache            | --no-cache, If true, processes the files even if they've been processed before | 0    |
| | fixid3              | --fixid3, If true, overrides and fixes the id3 title data | 0    |
| | add_narrators       | --add-narrators, If true, includes the narrators in the Audible search | 1   |
| target_path  |        | |     |
| | multi_author        | How to handle the Author folder for multi-author books: first_author, authors, "", "Static folder name" | first_author   |
| | in_series           | Format of the generated tree for books in a series | {author}/{series}/{series} #{part} - {title}   |
| | no_series           | Format of the generated tree for books that are NOT in a series | {author}/{title}    |
| | disc_folder         | Format of the folder name for multi-disc books | {title} {disc}    |
| tokens      |         | |    |
| | skip_series         | Used when fixid3 is true and an alt Title is generated from the id3-series data | 0   |
| | kw_ignore           | Characters ignored when generating keywords for search | | [".", ":", "_", "[", "]", "{", "}", ",", ";", "(", ")"]    |
| | kw_ignore_words     | Characters ignored when optimizing keywords for search| ["the","and","m4b","mp3","series","audiobook","audiobooks", "book", "part", "track", "novel", "disc"]    |
| | title_patterns      | ignores these patterns when alt Title is generated from bad id3 data | ["-end", "\bpart\b", "\btrack\b", "\bof\b",  "\bbook\b", "m4b", "\\(", "\\)", "_", "\\[", "\\]", "\\.", "\\s?-\\s?"]    |
