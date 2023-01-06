from subs_grabber import grab_subtitles
import argparse

parser = argparse.ArgumentParser(description='Grab subtitles from opensubtitles.com')
parser.add_argument('dir', type=str, help='Root directory of video files to get subtitles for')
parser.add_argument('--lang', type=str, help='Subtitle languages', default='en')
args = parser.parse_args()

try:
    grab_subtitles(args.dir, args.lang)
finally:
    input()
