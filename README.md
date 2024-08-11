# booktree
Reorganize your audiobooks using ID3, MAM or Audible metadata into a tree structure recommended and supported by media servers like Audibookshelf. The originals are untouched and will be hardlinked to their destination

It does the following:
- take a source folder, ideally your downloads folder where your audiobook files are
- recursively find all the M4B/MP3 files in it, and for each file:
  - pull and parse metadata information from id3 tags
  - using the id3 tags and the file information, attempt to pull metadata from the Metadata sources
  - create a tree structure on the target folder, ideally your media folder (like your abs audiobook library folder)
  - hardlink the audiobook file to the target folder

<mark>booktree</mark> builds the following heirarchy on the target folder:
* <media_path>/Author/Title (If there is no series information)
* <media_path>/Author/Series/Series #Part - Title

## Usage:

### Recommended Workflow

1. Start small (pick a folder that has a handful of books, don't run it on 2K files the first try :) )
2. Run <mark>booktree</mark> in <mark>--dry-run</mark> mode
3. Check the resulting log file to check the matches.  What you should check for:
    * Rows where isMatched = TRUE
      * Anywhere mamCount = 1 is an exact match... celebrate!
      * Check for rows where mamCount or audibleMatchCount is high (>3), if it is, just check if it picked the right match
    * Rows where isMatched = FALSE - there are many reasons why there won't be a match
      *  The book is NOT SOLD on Audible at all (or in your region)
      *  The book/torrent has been deleted from MAM since you snatched it
      *  The ID3 metadata is empty or bad, e.g., Author/Narrator that's not comma delimited, bad title and series information
4.  If everything looks good, rerun booktree without the --dry-run parameter
5.  Recategorize/Set Location (in you client, e.g., Qbit), to where you have your "processed" files so the script won't have to go thru them again next time

  Optionally, you can choose to work on the log file (removing all the rows that matched and already processed), and feed that as input to booktree in a succeeding run:

1. Fix the ID3 metadata in the log file (easier to do that in the log file as you can't touch the file). The areas to focus on are:
    *  id3-asin
    *  id3-title
    *  id3-author
    *  id3-series
2. Fixing those four fields will increase your match rate
3. Rerun booktree using the "log" mode and passing the updated logfile as input, booktree.py log --inputFile <updatedlogfile.csv> [the rest of the args]

  If there really is no match (metadata=id3), and you still want to organize the book from the updated id3 information, update the metadasource column to "as-is" and it will take the data from the log and not query MAM or Audible

### Help and Examples
~~~
usage: python booktree.py [-h] {mam|audible|mam-audible|log} [--file FILE] --source_path SOURCE_PATH --media_path MEDIA_PATH [--log_path LOG_PATH] [--dry-run] [--verbose] [--session]
~~~

| Flag | Description | Default Value |
| ----------- | ----------- | ----------- |
|  -h, --help |           Show this help message and exit||
|  {audible,mam,mam-audible,log} | Source of the metada: (mam, audible,log)|mam-audible|
|  --file FILE            |The input file or for directory scan, the file(s) path/pattern you want to process.  Accepts * and ?|\*.m4b,*.mp3|
|  --source_path SOURCE_PATH|Where your unorganized files are|Required|
|  --media_path MEDIA_PATH|Where your organized files will be, i.e. your Audiobookshelf library|Required|
|  --log_path LOG_PATH   |Where your log files will be|<booktree>/logs|
|  --dry-run             |If provided, will only create logfile and not actually build the tree||
|  --verbose            |If provided, will display more debug information||
|  --session | If using mam or mam-audible, include the MAM session ID||


### Examples and Use Cases

#### Use Case #1: Minimum usage required - Process all m4b files under current folder to /data/media/abs.
~~~
python booktree.py --media_path /data/media/abs [--dry-run]
~~~

#### Use Case #2a: One Book in a folder - Process all m4b files from /downloads/01 The Lies of Locke Lamora to /data/media/abs.
~~~
python booktree.py --source_path "/downloads/01 The Lies of Locke Lamora" --media_path /data/media/abs [--dry-run]
~~~

#### Use Case #2b: One Book in a folder - Process all m4b files from a folder 01 The Lies of Locke Lamora somewhere under /downloads to /data/media/abs.
~~~
python booktree.py --file "**/01 The Lies of Locke Lamora/*.m4b" --source_path "/downloads" --media_path /data/media/abs [--dry-run]
~~~

#### Use Case #3a: One Book in a file (that is under a book folder) - Process a single file, named "**/KATE.DANIELS.04.Magic Bleeds.m4b" somewhere under /downloads to "/data/media/abs"
~~~
python booktree.py --file "**/KATE.DANIELS.04.Magic Bleeds.m4b" --source_path /downloads --media_path /data/media/abs [--dry-run]
~~~

#### Use Case #3b: One Book in a file (that is NOT under a book folder) - Process a single file, named "**/KATE.DANIELS.04.Magic Bleeds.m4b" /downloads/Matchup to "/data/media/abs" For this use case, it is IMPORTANT that the --source_path be the parent folder of the file
~~~
python booktree.py --file "MatchUp.m4b" --source_path /downloads/MatchUp --media_path /data/media/abs [--dry-run]
~~~

#### Use Case #4: All audiobooks under a folder - Recursively process all m4b files from /downloads to /data/media/abs.
~~~
python booktree.py --source_path /downloads --media_path /data/media/abs [--dry-run]
~~~

#### Use Case #5: Reprocess the logfile named inputFile.csv and rename/hardlink files from /downloads to /data/media/abs
~~~
python booktree.py log --file inputFile.csv --source_path /downloads --media_path /data/media/abs [--dry-run]
~~~

#### Use Case #6: Process files from /downloads to /data/media/abs, use audible only, not MAM
~~~
python booktree.py audible --source_path /downloads --media_path /data/media/abs [--dry-run]
~~~

## FAQ
  **Q:  My files are not from MAM, can I still use this tool?**
  <p>A: Use audible as metadata source, i.e., booktree.py audible</p>

  **Q:  What if the mam or audible search returns multiple matches?**
  <p>A: Fuzzymatch is used to get the best match</p>

## Dependencies
* Python >= 3.10
* ffmpeg
* audible
* thefuzz 

run pip install -r requirements.txt to install dependencies

## Disclaimers

* While I have tested this on over 30K files and over 4K audiobooks, I have NOT tested this on Windows, some of the / should probably be \
* It should work seamlessly on recent MAM books : single file or multi-file book under a single book folder
* The script may not immediately work on older, Multibook collections immediately -- I suggest editing the log and update the book and id-3 title columns and rerun in log mode
* The script may not immediately work on Multi-CD books -- I suggest editing the log and update the book and id-3 title columns and rerun in log mode
* Hard linking will only work if the source and target paths are on the same volume



