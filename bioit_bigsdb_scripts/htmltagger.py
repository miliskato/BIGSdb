import argparse
import sys
from os import fdopen, remove
from pathlib import Path
from shutil import move, copymode
from tempfile import mkstemp

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--htmlfilepath', required=True, type=Path)
argument_parser.add_argument('--species', required=True, type=str, choices=list(get_bigsdb_config_data()['species']))
args = argument_parser.parse_args()
htmlfilepath = Path(args.htmlfilepath)
species = args.species

schemedict = {'listeria':        {'listeria_ndaro':              {'schemename_html': 'NCBI AMR genes (NDARO)'},
                                  'listeria_resfinder':          {'schemename_html': 'ResFinder'},
                                  'listeria_virulencefinder':    {'schemename_html': 'VirulenceFinder - <i>Listeria</i>'},
                                  'listeria_vfdbcore':           {'schemename_html': 'Virulence Factor DB - Core'},
                                  'listeria_plasmidfinder':      {'schemename_html': 'PlasmidFinder - Gram positive'}},
              'mycobacterium':   {'mycobacterium_pointfinder':   {'schemename_html': 'PointFinder'}},
              'neisseria':       {'neisseria_ndaro':             {'schemename_html': 'NCBI AMR genes (NDARO)'},
                                  'neisseria_resfinder':         {'schemename_html': 'ResFinder'}},
              'stec':            {'stec_pointfinder':            {'schemename_html': 'PointFinder'},
                                  'stec_ndaro':                  {'schemename_html': 'NCBI AMR genes (NDARO)'},
                                  'stec_resfinder':              {'schemename_html': 'ResFinder'},
                                  'stec_virulencefinder_ecoli':  {'schemename_html': 'VirulenceFinder - <i>E. coli</i>'},
                                  'stec_virulencefinder_shiga':  {'schemename_html': 'VirulenceFinder - Shiga-toxin genes'},
                                  'stec_plasmidfinder':          {'schemename_html': 'PlasmidFinder - Enterobacteriaceae'}},
              'salmonella':      {'salmonella_spifinder':          {'schemename_html': 'SPIFinder'},
                                  'salmonella_pointfinder':        {'schemename_html': 'PointFinder'},
                                  'salmonella_ndaro':              {'schemename_html': 'NCBI AMR genes (NDARO)'},
                                  'salmonella_resfinder':          {'schemename_html': 'ResFinder'},
                                  'salmonella_vfdbcore':           {'schemename_html': 'Virulence Factor DB - Core'},
                                  'salmonella_plasmidfinder':      {'schemename_html': 'PlasmidFinder - Enterobacteriaceae'},
                                  'salmonella_abritamr':           {'schemename_html': 'AbritAMR'}},
              }


def tagger(htmlname: str) -> None:
    """
    This function tags a html file at specific locations (scheme start). These tags can then be used to direct the user to that exact location in Bigsdb
    :param htmlname: name of the scheme to be tagged in the html file
    :return: None
    """
    if htmlname == 'PointFinder':
        htmlreport = ''.join(['<div class="report_section"><h2>', htmlname, ' <small'])
    else:
        htmlreport = ''.join(['<div class="report_section"><h3>', htmlname, '</h3>'])
    htmltag = ''.join(['<a name="', htmlname, '"></a>'])
    # Create temp file
    fh, abs_path = mkstemp()
    with fdopen(fh, 'w') as new_file:
        with open(htmlfilepath) as old_file:
            for line in old_file:
                new_file.write(line.replace(''.join([htmltag, htmlreport]), htmlreport).replace(htmlreport, ''.join([htmltag, htmlreport])))
    # Copy the file permissions from the old file to the new file
    copymode(htmlfilepath, abs_path)
    # Remove original file
    remove(htmlfilepath)
    # Move new file
    move(abs_path, htmlfilepath)


for scheme in schemedict[species]:
    tagger(schemedict[species][scheme]['schemename_html'])
