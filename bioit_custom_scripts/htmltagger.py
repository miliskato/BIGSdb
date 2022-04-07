import argparse
from pathlib import Path
from tempfile import mkstemp
from shutil import move, copymode
from os import fdopen, remove

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--htmlfilepath', required=True, type=Path)
args = argument_parser.parse_args()
htmlfilepath = Path(args.htmlfilepath)

schemedict = {'listeria_ndaro':              {'schemename_html': 'NCBI AMR genes'},
              'listeria_resfinder':          {'schemename_html': 'ResFinder'},
              'listeria_virulencefinder':    {'schemename_html': 'VirulenceFinder - <i>Listeria</i>'},
              'listeria_vfdbcore':           {'schemename_html': 'Virulence Factor DB - Core'},
              'listeria_plasmidfinder':      {'schemename_html': 'PlasmidFinder - Gram positive'},
              'mycobacterium_pointfinder':   {'schemename_html': 'PointFinder'}
              }


def tagger(htmlname):
    if htmlname == 'PointFinder':
        htmlreport = ''.join(['<div class="report_section"><h2>', htmlname, ' <small'])
    else:
        htmlreport = ''.join(['<div class="report_section"><h3>', htmlname, '</h3>'])
    htmltag = ''.join(['<a name="', htmlname, '"></a>'])
    #Create temp file
    fh, abs_path = mkstemp()
    with fdopen(fh,'w') as new_file:
        with open(htmlfilepath) as old_file:
            for line in old_file:
                new_file.write(line.replace(''.join([htmltag, htmlreport]), htmlreport).replace(htmlreport, ''.join([htmltag, htmlreport])))
    #Copy the file permissions from the old file to the new file
    copymode(htmlfilepath, abs_path)
    #Remove original file
    remove(htmlfilepath)
    #Move new file
    move(abs_path, htmlfilepath)

for scheme in schemedict:
    tagger(schemedict[scheme]['schemename_html'])