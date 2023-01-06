import xml.etree.ElementTree as ET
import os
from pathlib import Path
import glob
from open_subtitles import OpenSubtitles


# ------------------------------------------------------


class NfoTypeError(Exception):
    pass

# ------------------------------------------------------


class SubtitlesGrabber:

    def __init__(self, lang="en"):
        self.open_subtitles = OpenSubtitles(login=True)
        self.languages = set(lang.split(","))
        self._supports_multi_cd = False

    @staticmethod
    def build_subtitle_filename(base_fname: str, lang: str) -> str:
        return f"{base_fname}.{lang}.srt"

    def find_subtitles_for_nfo(self, nfo_file: str, search_params: dict):
        """ Search for subtitles for nfo file """
        assert "languages" in search_params, "Subtitle languages must be specified"
        search_params["imdb_id"] = _read_nfo(nfo_file, "imdbid")
        return self.search(search_params)

    def search(self, search_params, sort_by="download_count"):
        result = self.open_subtitles.search(search_params)
        if not self._supports_multi_cd:
            result = [r for r in result if len(r['attributes']['files']) == 1]
        return [r for _, r in sorted(zip([r['attributes'][sort_by] for r in result], result),
                                     key=lambda x: x[0], reverse=True)]

    def find_existing_subtitles_for_file(self, fname: str):
        base_fname = os.path.splitext(fname)[0]
        existing_langs = []
        for stfile in glob.glob(self.build_subtitle_filename(glob.escape(base_fname), lang="*")):
            lang = stfile.replace(str(base_fname) + ".", "")[:2]
            existing_langs.append(lang)
        return existing_langs

    def grab_subtitles_for_file(self, fname: str, verbose: bool = True) -> str:
        """ Find and download subtitles for video or nfo file
        Returns status (str):
                "exist"         - subtitles already exist
                "notfound"      - could not find subtitles for file
                "downloaded"    - downloaded subtitles successfully
                "failed"        - downloading subtitles failed
        """

        base_fname = os.path.splitext(fname)[0]

        def _finalize(status):
            if status == "exist":
                msg = "Subtitles already exist"
            elif status == "notfound":
                msg = "Subtitles not found"
            elif status == "failed":
                msg = "Failed downloading subtitles"
            elif status == "downloaded":
                msg = "Downloaded subtitles"
            else:
                raise ValueError("Unknown status")
            if verbose:
                print(f"{msg:25} - {base_fname}")
            return status

        missing_langs = self.languages.difference(self.find_existing_subtitles_for_file(fname))
        if len(missing_langs) == 0:
            return _finalize("exist")

        nfo_file = base_fname + ".nfo"
        assert os.path.isfile(nfo_file), "No nfo file: " + str(nfo_file)

        subtitle_items = self.find_subtitles_for_nfo(nfo_file, {"languages": missing_langs})

        if len(subtitle_items) == 0:
            return _finalize("notfound")

        subtitle_attribs = subtitle_items[0]['attributes']
        if not self._supports_multi_cd:
            assert len(subtitle_attribs['files']) == 1
        dst_stfile = self.build_subtitle_filename(base_fname, lang=subtitle_attribs['language'])

        self.open_subtitles.download_item(subtitle_attribs['files'][0], dst_stfile)
        return _finalize("downloaded" if os.path.isfile(dst_stfile) else "failed")


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

    results = {"failed": [], "downloaded": [], "notfound": [], "exist": []}
    for nfo_file in nfo_files:
        try:
            status = grabber.grab_subtitles_for_file(nfo_file)
            results[status].append(nfo_file)
        except NfoTypeError:
            pass

    counts = {k: len(v) for k, v in results.items()}
    tot = counts["failed"] + counts["downloaded"] + counts["notfound"] + counts["exist"]
    print(f"\nDone. Out of {tot} media files:")
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

