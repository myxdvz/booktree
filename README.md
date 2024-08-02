# booktree
Reorganize your audiobooks using ID3 and/or Audbile metadata. The originals are untouched and will be hardlinked to their destination

It does the following:
- take a source folder, ideally your downloads folder where your audiobook files are
- recursively find all the M4B files in it, and for each file:
  - pull and parse metadata information from id3 tags
  - using the id3 tags and the file information, attempt to pull metadata from Audible
  - create a tree structure on the target folder, ideally your media folder (like your abs audiobook library folder)
  - hardlink the M4B file to the target folder

**booktree** builds the following heirarchy on the target folder:
* <media_path>/Author/Title (If there is no series information)
* <media_path>/Author/Series/SeriesPart - Title

## Usage:
~~~
usage: python booktree.py [-h] {audible|log} -user USER -pwd PWD --source_path SOURCE_PATH --media_path MEDIA_PATH [--log_path LOG_PATH] [-match MATCH] [--dry-run]
~~~

| Flag | Description | Default Value |
| ----------- | ----------- | ----------- |
|  -h, --help |           Show this help message and exit||
|  {audible,log} | Source of the metada: (audible,log)|audible|
|  -user USER            |Your audible username|Required for audible|
|  -pwd PWD              |Your audible password|Required for audible|
|  --source_path SOURCE_PATH|Where your unorganized files are|Required|
|  --media_path MEDIA_PATH|Where your organized files will be, i.e. your Audiobookshelf library|Required|
|  --log_path LOG_PATH   |Where your log files will be|Current directory|
|  -match MATCH          |The min acceptable ratio for the fuzzymatching algorithm| 35|
|  --dry-run             |If provided, will only create logfile and not actually build the tree||


Note that using the log as the metadata source is still under development.  The intention is to allow a user to run the script using audible as metadata source in dry-run mode first to generate the log file and then in succeeding runs, use the log file as the input. This will allow the user to make edits and corrections in the log file to provide or correct any missing metadata before actually organizing the files.

## FAQ
**Q:  What if there are no id3 tags at all?**
<p>A: Parent folder information is used to perform keyword search</p>

**Q:  What if there's no author/artist tag?**
<p>A: If audible metadata can be pulled, it will use audible author information.  Otherwise, author is set to "Unknown"</p>

**Q:  What if the audible search returns multiple matches?**
<p>A: Fuzzymatch is used to get the best match that is on or above the minimum acceptable match rate provided, default is 35</p>

**Q:  My match rates are bad, how can I improve it?**
<p>A: Play around with the match rate parameter, specially if the source files have very little metadata available</p>

## Dependencies
* ffmpeg
* audible
* thefuzz 

run pip install -r requirements.txt to install dependencies

Note that hardlinks only work if the source and target directories are in the SAME volume


