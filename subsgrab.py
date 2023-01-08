from subs_grabber import grab_subtitles
import argparse
import sys


# -------------------------------------------------------------

examples_str = """
Examples:
    Grab Spanish subtitles for all media under D:\Media\TvShows:
    > subsgrab.py D:\Media\TvShows es
    Grab subtitles in languages (by priority): English, Spanish, French:
    > subsgrab.py D:\Media\TvShows en,es,fr
"""

parser = argparse.ArgumentParser(
    epilog=examples_str,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description='Grab subtitles from opensubtitles.com')

parser.add_argument('directory', type=str, help='Root directory of media files')
parser.add_argument('language', type=str, help='Subtitle language as 2-letter code. Or multiple languages '
                                               'separated by commas, ordered by priority.')


# -------------------------------------------------------------

if len(sys.argv) == 1 or sys.argv[1] in ('-h', '--help'):
    # no arguments or only help argument - show help and exit
    parser.print_help()
    input("\nPress Enter to exit.")
    sys.exit()


try:
    args = parser.parse_args()
except:
    # parsing failed - help shown by default, + exit
    input("\nPress Enter to exit.")
    sys.exit()


try:
    grab_subtitles(args.directory, args.language)
except Exception as err:
    # execution failed
    print(err)
finally:
    input("\nPress Enter to exit.")
    sys.exit()


