import xml.etree.ElementTree as ET
import os
from pathlib import Path
import glob
from open_subtitles import OpenSubtitles
from filename_matcher import FilenameMatcher
from typing import List, Tuple

# ------------------------------------------------------


class NfoTypeError(Exception):
    pass


# ------------------------------------------------------


class SubtitlesGrabber:

    def __init__(self, lang="en"):
        self.open_subtitles = OpenSubtitles(login=True)
        self.languages = set(lang.split(","))
        self._supports_multi_cd = False
        self._filematcher = FilenameMatcher()

    @staticmethod
    def build_subtitle_filename(base_fname: str, lang: str) -> str:
        return f"{base_fname}.{lang}.srt"

    @property
    def has_downloads(self):
        return self.open_subtitles.remaining_downloads is None or self.open_subtitles.remaining_downloads > 0

    def find_subtitles_for_nfo(self, nfo_file: str, search_params: dict) -> (dict, None):
        """ Get for subtitles for nfo file. Returns the matching subtitle item, or None if nothing is found  """
        assert "languages" in search_params, "Subtitle languages must be specified"
        search_params["imdb_id"] = _read_nfo(nfo_file, "imdbid")
        result = self.search(search_params)
        if len(result) == 0:
            return None
        subtitle_fnames = [item['attributes']['files'][0]['file_name'] for item in result]
        result_ix = self._filematcher.get_best_match_ix(nfo_file, subtitle_fnames)
        if result_ix is None:
            return None
        return result[result_ix]

    def search(self, search_params: dict) -> List[dict]:
        result = self.open_subtitles.search(search_params)
        if not self._supports_multi_cd:
            result = [r for r in result if len(r['attributes']['files']) == 1 and
                      r['attributes']['files'][0]['file_name'] is not None]
        return result

    def find_existing_subtitles_for_file(self, fname: str) -> List[str]:
        """ returns list of subtitle languages that exist (locally) for an nfo/media file """
        base_fname = os.path.splitext(fname)[0]
        existing_langs = []
        for stfile in glob.glob(self.build_subtitle_filename(glob.escape(base_fname), lang="*")):
            lang = stfile.replace(str(base_fname) + ".", "")[:2]
            existing_langs.append(lang)
        return existing_langs

    def grab_subtitles_for_file(self, fname: str) -> Tuple[str, str]:
        """ Find and download subtitles for video or nfo file
        Returns one of the following (status, info) tuples:

        - Subtitles already exist locally:  ("exist", "")
        - No matching subtitles found:      ("notfound", "")
        - Successful downloaded:            ("downloaded", <remote name of downloaded subtitle>)
        - Failed download:                  ("failed", <failure msg>)
        - Reached download limit:           ("dllimit", "")

        """

        base_fname = os.path.splitext(fname)[0]

        missing_langs = self.languages.difference(self.find_existing_subtitles_for_file(fname))
        if len(missing_langs) == 0:
            return "exist", ""

        nfo_file = base_fname + ".nfo"
        assert os.path.isfile(nfo_file), "No nfo file: " + str(nfo_file)

        subtitle_item = self.find_subtitles_for_nfo(nfo_file, {"languages": missing_langs})

        if subtitle_item is None:
            return "notfound", ""

        if not self.has_downloads:
            return "dllimit", ""

        if not self._supports_multi_cd:
            assert len(subtitle_item['attributes']['files']) == 1

        dst_stfile = self.build_subtitle_filename(base_fname, lang=subtitle_item['attributes']['language'])
        subtitle_file_item = subtitle_item['attributes']['files'][0]
        self.open_subtitles.download_item(subtitle_file_item, dst_stfile)

        if os.path.isfile(dst_stfile):
            return "downloaded", subtitle_file_item['file_name']

        return "failed", "Download failed"


# ------------------------------------------------------


def grab_subtitles(root_dir: str, lang: str):
    """ Get subtitles for nfo files under root directory """

    print(f"\nGrabbing {lang} subtitles for media at " + root_dir)

    nfo_files = glob.glob(os.path.join(root_dir, "**", "*.nfo"))
    if len(nfo_files) == 0:
        nfo_files = glob.glob(os.path.join(root_dir, "*.nfo"))
    if len(nfo_files) == 0:
        print("No nfo files found under " + root_dir)
        return

    grabber = SubtitlesGrabber(lang=lang)

    stop_msg = ""
    results = {"failed": [], "downloaded": [], "notfound": [], "exist": []}
    for nfo_file in nfo_files:

        if len(glob.glob(glob.escape(os.path.splitext(nfo_file)[0]) + ".*")) == 1:
            # nfo file not associated with media file
            continue

        try:
            status, info = grabber.grab_subtitles_for_file(nfo_file)
            if status == "dllimit":
                print("\nOpenSubtitles download limit reached. Try again later.")
                stop_msg = " (reached limit)"
                break
        except NfoTypeError:
            continue
        except Exception as err:
            status, info = "failed", "Error encountered"

        results[status].append(nfo_file)

        if status == "exist":
            msg = "Subtitles already exist"
        elif status == "notfound":
            msg = "Could not find subtitles"
        elif status == "downloaded":
            msg = "Downloaded subtitles"
        elif status == "failed":
            msg = "Failed getting subtitles"

        print(f"{msg:25} - {os.path.splitext(nfo_file)[0]}" + (" - " + info if len(info) else ""))

    counts = {k: len(v) for k, v in results.items()}
    tot = counts["failed"] + counts["downloaded"] + counts["notfound"] + counts["exist"]
    print(f"\nDone{stop_msg}. Out of {tot} media files:")
    print(f"{counts['exist'] + counts['downloaded']} have subtitles "
          f"({counts['exist']} already had subtitles, {counts['downloaded']} were downloaded now.)")
    print(f"{counts['failed'] + counts['notfound']} Dont have subtitles "
          f"({counts['notfound']} not found in opensubtitles db, {counts['failed']} failed to download.)")


# ------------------------------------------------------


def _read_nfo(nfo_file: Path, key: str) -> str:
    """ read key from nfo file """
    tree = ET.parse(nfo_file)
    root = tree.getroot()
    item = root.find(key)
    if item is None:
        raise NfoTypeError(nfo_file)
    return item.text

