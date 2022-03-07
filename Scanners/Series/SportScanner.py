#
# Most code here is copyright (c) 2010 Plex Development Team. All rights reserved.
#

import re
import os
import os.path
import logging
import Media
import VideoFiles
import Stack
import Utils

regex_all_in_file_name = [
    r'(?P<show>.*?)[^0-9a-zA-Z]+(?P<year>[0-9]{4})[^0-9a-zA-Z]+'
    r'(?P<month>[0-9]{2})[^0-9a-zA-Z]+(?P<day>[0-9]{2})[^0-9a-zA-Z]+(?P<title>.*)$',
    r'^(?P<show>.*?)-(?P<season>[0-9]{4}).*-([0-9a-zA-z]+-)'
    r'(?P<year>[0-9]{4})(?P<month>[0-9]{2})(?P<day>[0-9]{2})'
    r'[-_](?P<title>.*?)(_ALT)?$'
]

regex_date_title_file_name = [
    '.*'
]

regex_title_file_name = [
    '.*'
]


def set_logging():
    cache_path = os.path.join(
        os.environ['LOCALAPPDATA'], 'Plex Media Server', 'Logs', 'Sports Scanner Logs')
    if not os.path.exists(cache_path):
        os.makedirs(cache_path)
    filename = '_root_.scanner.log'
    log_file = os.path.join(cache_path, filename)

    # Bypass DOS path MAX_PATH limitation
    # (260 Bytes=> 32760 Bytes, 255 Bytes per folder unless UDF 127B ytes max)
    if os.sep == "\\":
        dos_path = os.path.abspath(log_file) if isinstance(log_file, unicode) else os.path.abspath(log_file.decode('utf-8'))
        log_file = u"\\\\?\\UNC\\" + dos_path[2:] if dos_path.startswith(u"\\\\") else u"\\\\?\\" + dos_path

    global logger
    logger = logging.getLogger('main')
    #if not mode:  mode = 'a' if os.path.exists(log_file) and os.stat(log_file).st_mtime + 3600 > time.time()
    # else 'w' # Override mode for repeat manual scans or immediate rescans
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)-15s %(levelname)s - %(message)s'))
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)


def get_additional_metadata_for_sub_episode(clean_files, file_name, logger):
    logger.warning("SS: Working on file_name | {0} |".format(file_name))
    # jump in here for some additional metadata logic
    additional_metadata_file = os.path.splitext(clean_files[file_name])[0] + '.SportScanner'
    additional_metadata_sub_episode = ''
    if os.path.isfile(additional_metadata_file):
        additional_metadata_size = os.path.getsize(additional_metadata_file)
        additional_metadata_fd = os.open(additional_metadata_file, os.O_RDONLY)
        additional_metadata_lines = os.read(additional_metadata_fd,
                                            additional_metadata_size).splitlines()
        os.close(additional_metadata_fd)
        if len(additional_metadata_lines) > 0:
            additional_metadata_sub_episode = additional_metadata_lines[0]
    try:
        additional_metadata_sub_episode = int(additional_metadata_sub_episode)
    except ValueError:
        additional_metadata_sub_episode = -1
    return additional_metadata_sub_episode


def Scan(path, files, mediaList, subdirs):
    """Look for episodes."""
    set_logging()
    logger.warning("SS: Starting scan")
    # logger.warning("SS: path | {} |".format(path))
    # logger.warning("SS: files | {} |".format(files))
    # logger.warning("SS: subdirs | {} |".format(subdirs))

    # Scan for video files.
    VideoFiles.Scan(path, files, mediaList, subdirs)

    logger.warning("SS: Video files | {} |".format(files))
    logger.warning("SS: Video subdirs | {} |".format(subdirs))


    def NumberEpisode(year,month,day,filehash,sub):
        if not re.match(r"^[0-9]{4}$",year):
	    raise ValueError("Incorrectly formatted year. Must be 4 char str: {0}".format(year))

        if int(year) > 2021:
            if sub < 0:
                ep = int('%s%02d%02d%03d' % (year[-2:],month, day, filehash % (10 ** 3)))
            else:
                ep = int('%s%02d%02d%03d' % (year[-2:],month, day, sub))
        else:
            if sub < 0:
                ep = int('%s%02d%02d%04d' % (year[-2:],month, day, filehash % (10 ** 4)))
            else:
                ep = int('%s%02d%02d%04d' % (year[-2:],month, day, sub))
        return ep

    # Here we have only video files in files, path is only the TLD, media is empty, subdirs is populated
    # No files here? Then what are we doing!
    clean_files = dict()
    if len(files) == 0:
        return
    library_name_as_sport = None
    show_name_as_year = None
    season_name_as_event = None
    for file_path in files:
        logger.warning("Lex: File Path | {}".format(file_path))
        if not library_name_as_sport:
            event_file_path = os.path.dirname(file_path)
            season_name_as_event = os.path.basename(event_file_path)
            logger.warning("Lex: Season Name as Event | {}".format(season_name_as_event))
            year_file_path = os.path.dirname(event_file_path)
            show_name_as_year = os.path.basename(year_file_path)
            logger.warning("Lex: Show Name as Year | {}".format(show_name_as_year))
            library_file_path = os.path.dirname(year_file_path)
            library_name_as_sport = os.path.basename(library_file_path)
            logger.warning("Lex: Library Name as Sport | {}".format(library_name_as_sport))
        file_name = os.path.basename(file_path)
        logger.warning("Lex: File Name | {}".format(file_name))
        (file_name, ext) = os.path.splitext(file_name)
        # Minor cleaning on the file_name to avoid false matches on H.264, 720p, etc.
        whack_rx = [
            r'([hHx][\.]?264)[^0-9].*',
            r'[^[0-9](720[pP]).*',
            r'[^[0-9](1080[pP]).*',
            r'[^[0-9](480[pP]).*',
            r'[^[0-9](540[pP]).*'
        ]
        for rx in whack_rx:
            file_name = re.sub(rx, "", file_name)
        clean_files[file_name] = file_path
        logger.warning("Lex: Clean Files | {}".format(clean_files))

    paths = Utils.SplitPath(path)

    if len(paths) == 1 and len(paths[0]) == 0 or len(path) == 0 :
        # This is just a load of files dumped in the root directory
        # - we can't deal with this properly
        logger.warning("SS: In TLD, no files here can be scanned")
        return

    if len(paths) == 1 and len(paths[0]) > 0:
        logger.warning("We are in | len(paths) == 1 and len(paths[0]) > 0")
        # These files have been dumped into a League directory but have no seasons.
        for file_name in clean_files:
            additional_metadata_sub_episode = get_additional_metadata_for_sub_episode(
                clean_files=clean_files, file_name=file_name, logger=logger)

            for rx in regex_all_in_file_name:
                match = re.search(rx, file_name, re.IGNORECASE)
                if match:
                    logger.warning("SS: matched regex | {0} |".format(rx))
                    year = match.group('year')
                    month = int(match.group('month'))
                    day = int(match.group('day'))
                    show = re.sub(r'[^0-9a-zA-Z]+', ' ', match.group('show'))
                    title = re.sub(r'[^0-9a-zA-Z]+', ' ', match.group('title'))
                    if 'season' in match.groups():
                        season = match.group('season')
                    else:
                        season = year

                    filename = "{0}{1}SportScanner.txt".format(os.path.dirname(clean_files[file]),os.path.sep)
                    logger.warning("SS: FileName: {0}".format(filename))

                    # Check to see if a .SportScanner file_name exists, then read in the contents
                    if os.path.isfile(filename):
                        size = os.path.getsize(filename)
                        fd = os.open(filename, os.O_RDONLY)
                        file_contents = os.read(fd, size)
                        # logger.warning("SS: FileContents: {0}".format(file_contents))
                        season_match = re.search('(?P<season>XX..)',file_contents, re.IGNORECASE)
                        if season_match:
                            season_format = season_match.group('season').lower()
                            logger.warning("SS: Using {0} season format for {1}".format(season_format, show))

                            if season_format == "xxyy":
                                # If this is a split season then get the dates
                                split_dates_match = re.search(r'(?P<month>\d{1,2}),(?P<day>\d{1,2})', file_contents, re.IGNORECASE)
                                if split_dates_match:
                                    split_month = int(split_dates_match.group('month'))
                                    split_day = int(split_dates_match.group('day'))
                                    logger.warning("SS: Split date is {0}-{1}".format(split_month, split_day))
                                    logger.warning("SS: Event date is {0}-{1}".format(month, day))
                                    if month < split_month or (month == split_month and day < split_day):
                                        logger.warning("SS: Event happened before split date")
                                        short_year = year[-2:]
                                        year_before = str(int(short_year) - 1)
                                        season = int("{0}{1}".format(year_before, short_year))
                                    else:
                                        logger.warning("SS: Event happened after split date")
                                        short_year = year[-2:]
                                        year_after = str(int(short_year) + 1)
                                        season = int("{0}{1}".format(short_year, year_after))
                                else:
                                    logger.warning("SS: Could not match dates")
                    else:
                        logger.warning("SS: Could not find {0}, defaulting to XXXX season format")

                    # Using a hash so that each file_name gets the same episode number on every scan
                    # The year must be included for seasons that run over a year boundary
                    # Issue #37: Episode numbers made after the year 2022 overrun the 32-bit unsigned
                    #    integer. Use a function to create a 9-character hash for years 2022 and up
                    ep = NumberEpisode(year,month,day,abs(hash(file)),additional_metadata_subepisode)
                    tv_show = Media.Episode(show, season, ep, title, int(year))
                    tv_show.released_at = '%s-%02d-%02d' % (year, month, day)
                    tv_show.parts.append(clean_files[file_name])
                    mediaList.append(tv_show)
                    break
                else:
                    logger.warning("SS: No match found for {0}".format(file_name))
    elif len(paths) >= 2:
        logger.warning("We are in | len(paths) >= 2")
        # Here we assume that it is in this format: League/Season/Event
        logger.warning("Lex: path | {}".format(path))
        show = show_name_as_year
        logger.warning("Lex: Show | {}".format(show))
        season = season_name_as_event
        logger.warning("Lex: Season | {}".format(season))
        # Look for the season in obvious ways or fail
        # match = re.match(r'Season (\d{4})', paths[1])
        # if match:
        #     season = match.group(1)
        # else:
        #     match = re.match(r'(\d{4})', paths[1])
        #     if match:
        #         season = match.group(1)

        # Look for ALL the information we need in the filename
        # - but trust what we have already found
        for file_name in clean_files:
            logger.warning("Lex: Gather File Information | {}".format(file_name))
            additional_metadata_sub_episode = get_additional_metadata_for_sub_episode(
                clean_files=clean_files, file_name=file_name, logger=logger)

            logger.warning("Lex: Regex Patterns | {}".format(regex_all_in_file_name))
            for rx in regex_all_in_file_name:
                logger.warning("Lex: Regex Pattern | {}".format(rx))
                match = re.search(rx, file_name, re.IGNORECASE)
                if match:
                    logger.warning("SS: matched regex | {0} |".format(rx))
                    year = match.group('year')
                    month = int(match.group('month'))
                    day = int(match.group('day'))
                    logger.warning("Lex: Extracted Date | {}-{}-{}".format(year, month, day))
                    logger.warning("Lex: Title | {}".format(match.group('title')))
                    title = re.sub(r'[^0-9a-zA-Z]+', ' ', match.group('title'))
                    title = re.sub(season_name_as_event + r'\s+', '', title)
                    logger.warning("Lex: Title | {}".format(title))

                    # Using a hash so that each file_name gets the same episode number on every scan
                    # The year must be included for seasons that run over a year boundary
                    # Issue #37: Episode numbers made after the year 2022 overrun the 32-bit unsigned
                    #    integer. Use a function to create a 9-character hash for years 2022 and up
                    ep = NumberEpisode(year,month,day,abs(hash(file)),additional_metadata_subepisode)
                    tv_show = Media.Episode(show, season, ep, title, int(year))
                    # Use month as Season for testing
                    tv_show = Media.Episode(show, month, ep, title, int(year))
                    tv_show.released_at = '%s-%02d-%02d' % (year, month, day)
                    tv_show.parts.append(clean_files[file_name])
                    mediaList.append(tv_show)
                    break
            # The following two loops should be used to match against other file_name names.
            for rx in regex_date_title_file_name:
                break
            for rx in regex_title_file_name:
                break

    # Stack the results.
    Stack.Scan(path, files, mediaList, subdirs)


import sys

if __name__ == '__main__':
    path = sys.argv[1]
    files = [os.path.join(path, file) for file in os.listdir(path)]
    media = []
    Scan(path[1:], files, media, [])
    logging.info("SS: media |", media, "|")
