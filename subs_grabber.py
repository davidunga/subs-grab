import json
import xml.etree.ElementTree as ET
import os
from pathlib import Path
import glob
from open_subtitles import OpenSubtitles
from filename_matcher import FilenameMatcher
from typing import List, Tuple

# ------------------------------------------------------

LANGAUGE_CODES_FILE = os.path.dirname(__file__) + "/resources/language_codes.json"
DEFAULT_LANGUAGE = "en"


class NfoTypeError(Exception):
    pass


# ------------------------------------------------------


class SubtitlesGrabber:

    def __init__(self, languages: List[str] = None, get_all_langs: bool = False):
        """
        Args:
            languages: list of languages (2-letter codes)
            get_all_langs: get all languages in list, instead of by priority
        """
        self.open_subtitles = OpenSubtitles(login=True)
        self.languages = [DEFAULT_LANGUAGE] if languages is None else languages
        self._get_all_langs = get_all_langs
        self._supports_multi_cd = False
        self._filematcher = FilenameMatcher()

        language_code2name = {item["alpha2"]: item["English"] for item in json.load(open(LANGAUGE_CODES_FILE, "r"))}
        self._language_names = []
        for language in self.languages:
            if language not in language_code2name:
                raise ValueError("Unknown language code: " + language)
            self._language_names.append(language_code2name[language])

    @staticmethod
    def build_subtitle_filename(base_fname: str, lang: str) -> str:
        return f"{base_fname}.{lang}.srt"

    @property
    def has_downloads(self):
        return self.open_subtitles.remaining_downloads is None or self.open_subtitles.remaining_downloads > 0

    @property
    def language_names(self):
        return self._language_names

    def find_subtitles_for_nfo(self, nfo_file: str, search_params: dict) -> List[dict]:
        """ Get for subtitle items for nfo file
            Returns at most one item per language (the best match for each language, if any)
        """
        assert "languages" in search_params, "Subtitle languages must be specified"
        search_params["imdb_id"] = _read_nfo(nfo_file, "imdbid")
        search_results = self.search(search_params)
        if len(search_results) == 0:
            return []
        result = []
        for lang in search_params['languages']:
            subtitle_fnames = [item['attributes']['files'][0]['file_name']
                               for item in search_results if item['attributes']['language'] == lang]
            if len(subtitle_fnames) == 0:
                continue
            result_ix = self._filematcher.get_best_match_ix(nfo_file, subtitle_fnames)
            if result_ix is not None:
                result.append(search_results[result_ix])
        return result

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
        - Successful downloaded:            ("downloaded", <downloaded languages string>)
        - Failed download:                  ("failed", "")
        - Reached download limit:           ("dllimit", "")
        """

        if not self.has_downloads:
            return "dllimit", ""

        base_fname = os.path.splitext(fname)[0]
        missing_langs = [lang for lang in self.languages if lang not in self.find_existing_subtitles_for_file(fname)]

        if len(missing_langs) == 0:
            # no missing subtitles
            return "exist", ""

        if self.languages[0] not in missing_langs and not self._get_all_langs:
            # some missing subtitles, but top priority subtitles exist
            return "exist", ""

        nfo_file = base_fname + ".nfo"
        assert os.path.isfile(nfo_file), "No nfo file: " + str(nfo_file)

        subtitle_items = self.find_subtitles_for_nfo(nfo_file, {"languages": missing_langs})

        if len(subtitle_items) == 0:
            return "notfound", ""

        downloaded_languages = []
        subtitle_languages = [subtitle_item['attributes']['language'] for subtitle_item in subtitle_items]
        for language in self.languages:
            if language not in subtitle_languages:
                continue
            dst_stfile = self.build_subtitle_filename(base_fname, lang=language)
            subtitle_files_item = subtitle_items[subtitle_languages.index(language)]['attributes']['files']
            if len(subtitle_files_item) > 1 and not self._supports_multi_cd:
                raise ValueError("Unexpected format: multi-cd")
            self.open_subtitles.download_item(subtitle_files_item[0], dst_stfile)
            if os.path.isfile(dst_stfile):
                downloaded_languages.append(language)
                if not self._get_all_langs:
                    break

        if len(downloaded_languages) > 0:
            return "downloaded", ", ".join(downloaded_languages)

        return "failed", ""


# ------------------------------------------------------

def grab_subtitles(root_dir: str, langs: str):
    """ Get subtitles for nfo files under root directory """

    languages = [c.strip() for c in langs.split(",")]
    print(f"\nGrabbing subtitles for media at " + root_dir)

    nfo_files = glob.glob(os.path.join(root_dir, "**", "*.nfo"))
    if len(nfo_files) == 0:
        nfo_files = glob.glob(os.path.join(root_dir, "*.nfo"))
    if len(nfo_files) == 0:
        print("No nfo files found under " + root_dir)
        return

    grabber = SubtitlesGrabber(languages=languages)
    print("Languages: " + ", ".join(grabber.language_names))

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
            status, info = "failed", "Error"

        results[status].append(nfo_file)

        if status == "exist":
            msg = "Subtitles already exist"
        elif status == "notfound":
            msg = "Could not find subtitles"
        elif status == "downloaded":
            msg = "Downloaded subtitles"
        elif status == "failed":
            msg = "Failed download"
        if len(info):
            msg += " (" + info + ")"

        print(f"{msg:30} - {os.path.splitext(nfo_file)[0]}")

    counts = {k: len(v) for k, v in results.items()}
    tot = counts["failed"] + counts["downloaded"] + counts["notfound"] + counts["exist"]
    if tot > 0:
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

