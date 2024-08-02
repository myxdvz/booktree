# booktree
Reorganize your audiobooks using ID3 or Audbile metadata. The originals are untouched and will be hardlinked to their destination

It does the following:
- take a source folder, ideally your torrents download folder where your audiobook files are
- recursively find all the M4B files in it, and for each file
  - pull and parse metadata information from id3 tags
  - using the id3 tags and the file information, attempts to pull metadata from Audible
  - create a tree structure on the target folder, ideally your media folder (like your abs audiobook library folder)
  - and hardlinks all files from the parent folder of the M4B file to the target folder

## Usage:
usage: booktree [-h] --source_path SOURCE_PATH --media_path MEDIA_PATH [--log_path LOG_PATH] [--dry-run] [-user USER] [-pwd PWD]
                [-match MATCH] [-log LOG]
                {audible,log}

positional arguments:
  {audible,log}         Source of the metada: (audible, log)

| Flag | Description | Default Value |
| ----------- | ----------- | ----------- |
|  -h, --help |           show this help message and exit||
|  --source_path SOURCE_PATH|Where your unorganized files are|Required|
|  --media_path MEDIA_PATH|Where your organized files will be, i.e. your Audiobookshelf library|Required|
|  --log_path LOG_PATH   |Where your log files will be|Current directory|
|  --dry-run             |If provided, will only create log and not actually build the tree||
|  -user USER            |Your audible username|Required for audible|
|  -pwd PWD              |Your audible password|Required for audible|
|  -match MATCH          |The min acceptable ratio for the fuzzymatching algorithm.| 35|
|  -log LOG              |The file path/name to be used as metadata input|Future Use|


## How it works
**It builds the following heirarchy on the target folder**
* <mediaDirector>/Author/Title (If there is no series information)
* <mediaDirector>/Author/Series/SeriesPart - Title

## FAQ
**Q:  What if there are no tags?**
<p>A: Parent Folder information is used as keyword search</p>

**Q:  What if there's no author/artist tag?**
<p>A: Author is set to "Unknown"</p>

**Q:  What if the audible search returns multiple matches?**
<p>A: Fuzzymatch is used to get the best match.  You set the minimum acceptable match rate, default is 35</p>

**Q:  My match rates are bad, how can I improve it?**
<p>A: Play around with the match ratio setting.  Specially if the source files have very little metadata available</p>

## Dependencies
* ffmpeg
* audible
* thefuzz 

run pip install -r requirements.txt to install dependecies

Note that hardlinks only work if the source and target directories are in the SAME volume


