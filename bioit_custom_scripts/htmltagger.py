import argparse
from pathlib import Path
from tempfile import mkstemp
from shutil import move, copymode
from os import fdopen, remove

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--htmlfilepath', required=True, type=Path)
argument_parser.add_argument('--species', required=True, type=str, choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
args = argument_parser.parse_args()
htmlfilepath = Path(args.htmlfilepath)
species = args.species

schemedict = {'listeria':        {'listeria_ndaro':              {'schemename_html': 'NCBI AMR genes'},
                                  'listeria_resfinder':          {'schemename_html': 'ResFinder'},
                                  'listeria_virulencefinder':    {'schemename_html': 'VirulenceFinder - <i>Listeria</i>'},
                                  'listeria_vfdbcore':           {'schemename_html': 'Virulence Factor DB - Core'},
                                  'listeria_plasmidfinder':      {'schemename_html': 'PlasmidFinder - Gram positive'}},
              'mycobacterium':   {'mycobacterium_pointfinder':   {'schemename_html': 'PointFinder'}},
              'neisseria':       {'neisseria_ndaro':             {'schemename_html': 'NCBI AMR genes'},
                                  'neisseria_resfinder':         {'schemename_html': 'ResFinder'}},
              'stec':            {'stec_pointfinder':            {'schemename_html': 'PointFinder'},
                                  'stec_ndaro':                  {'schemename_html': 'NCBI AMR genes'},
                                  'stec_resfinder':              {'schemename_html': 'ResFinder'},
                                  'stec_virulencefinder_ecoli':  {'schemename_html': 'VirulenceFinder - <i>E. coli</i>'},
                                  'stec_virulencefinder_shiga':  {'schemename_html': 'VirulenceFinder - Shiga-toxin genes'},
                                  'stec_plasmidfinder':          {'schemename_html': 'PlasmidFinder - Enterobacteriaceae'}},
              'salmonella':      {'salmonella_spifinder':          {'schemename_html': 'SPIFinder'},
                                  'salmonella_pointfinder':        {'schemename_html': 'PointFinder'},
                                  'salmonella_ndaro':              {'schemename_html': 'NCBI AMR genes'},
                                  'salmonella_resfinder':          {'schemename_html': 'ResFinder'},
                                  'salmonella_vfdbcore':           {'schemename_html': 'Virulence Factor DB - Core'},
                                  'salmonella_plasmidfinder':      {'schemename_html': 'PlasmidFinder - Enterobacteriaceae'}},
              }


def tagger(htmlname):
    if htmlname == 'PointFinder' or htmlname == 'SPIFinder':
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

for scheme in schemedict[species]:
    tagger(schemedict[species][scheme]['schemename_html'])