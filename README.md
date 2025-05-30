# booktree
Reorganize your audiobooks using ID3 or Audible metadata into a tree structure recommended and supported by media servers like Audibookshelf. The originals are untouched and will be hardlinked to their destination

It does the following:
- take a source folder, ideally your downloads folder where your audiobook files are
- recursively find all the M4B/MP3 files in it, and for each file:
  - pull and parse metadata information from id3 tags
  - using the id3 tags and the file information, attempt to pull metadata from the Metadata sources
  - create a tree structure on the target folder, ideally your media folder (like your abs audiobook library folder)
  - hardlink the audiobook file to the target folder

<mark>booktree</mark> builds the following heirarchy on the target folder (this is configurable):
* <media_path>/Author/Title (If there is no series information)
* <media_path>/Author/Series/Series #Part - Title

The above format is the default. User can modify/tweak this in the config file.  See [Config File Documentation](CONFIG.md)

## Usage:
### Help
~~~
to run in the docker container, run: > docker exec [-it] <<container_name>> /venv/bin/python booktree.py /config/<<config>>.json 

usage: booktree [-h] [--dry-run] config_file

Reorganize your audiobooks using ID3 or Audbile metadata. The originals are untouched and will be hardlinked to their
destination

positional arguments:
  config_file           Your Config File

options:
  -h, --help            show this help message and exit
  --dry-run             If provided, will override dryRun in config
~~~

## Install
* Python >= 3.10
* ffmpeg
* httpx
* thefuzz 
* pathvalidate
* Requests
* langcodes

1. run pip install -r requirements.txt to install dependencies
2. copy default_config.cfg into config.json and modify with your paths settings (files, source_path, media_path)
3. if using MAM as a source, create a MAM session ID and set the value in config.json file (/Config/session)

### Recommended Workflow

1. Start small (pick a folder that has a handful of books, don't run it on 2K files the first try :) )
2. Run <mark>booktree</mark> in <mark>--dry-run</mark> mode
3. Check the resulting log file to check the matches.  What you should check for:
    * Rows where isMatched = TRUE
      * Anywhere mamCount = 1 is an exact match... celebrate!
      * Check for rows where mamCount or audibleMatchCount is high (>3), if it is, just check if it picked the right match
    * Rows where isMatched = FALSE - there are many reasons why there won't be a match
      *  The book is NOT SOLD on Audible at all (or in your region)
      *  The book/torrent has been deleted since you snatched it
      *  The ID3 metadata is empty or bad, e.g., Author/Narrator that's not comma delimited, bad title and series information
4.  If everything looks good, rerun booktree without the --dry-run parameter
5.  Recategorize/Set Location (in you client, e.g., Qbit), to where you have your "processed" files to optimize performance. It's ok if you don't, the script will add them to the list of files to be processed, but will skip processing them if they have already been processed before (cache check).

  Optionally, you can choose to work on the log file, and feed that as input to booktree in a succeeding run:

1. Fix the <mark>paths</mark> column to edit/change the generated target path.  When isMatched=TRUE, booktree will just use the paths value as-is
2. If isMatched = FALSE, you can fix the id3-metadata to re-do the search.  The areas to focus on are:
    *  id3-asin
    *  id3-title
    *  id3-author
    *  id3-seriesparts
3. Rerun booktree using the "log" mode and passing the updated logfile as input, booktree.py log /config/log_config.json. I recommend having a separate log_config.json file for this 

## Disclaimers

* It should work seamlessly on any single file or multi-file book under a single book folder
* The script may not immediately work on older, multibook collections >> set multibook = true
* The script may not immediately work on Multi-CD books
* Hard linking will only work if the source and target paths are on the same volume.  If you are using Unraid, same datasets

## FAQ
  **Q:  Where is my config file?**
  <p>A: You can copy the default_config.cfg into <somefile>.json.  Modify or add the values of paths: [{file, source_path, media_path}]</p>

  **Q:  My files are from other sources, can I still use this tool?**
  <p>A: Use audible as metadata source, Config/metadata = audible</p>

  **Q:  What if the mam or audible search returns multiple matches?**
  <p>A: Fuzzymatch is used to get the best match</p>

  **Q:  My metadata is not producing any match, what can I do?**
  <p>A: Lower the matchrate, Change the fuzzy_match algorith, Set --fixid3 flag.</p>
  


