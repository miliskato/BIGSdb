import argparse
from pathlib import Path
import psycopg2
import sys
import re
import shutil
import os

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--fastafilepath', required=True, type=str)
argument_parser.add_argument('--species', required=True, type=str, choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
argument_parser.add_argument('--isolatename', required=True, type=str)
args = argument_parser.parse_args()
fastafile = args.fastafilepath
species = args.species
isolate_name = args.isolatename

con = psycopg2.connect(database=f"bigsdb_{species}_isolates", user="apache", password="remote",
                       host="127.0.0.1", port="")
cur = con.cursor()
con.autocommit = True
cur.execute(f"SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'")
present = cur.fetchall()
if present[0][0] != []:
    pass
else:
    sys.exit("please insert isolate/isolate results first")

cur.execute(f"SELECT count(*) FROM sequence_bin WHERE isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}')")
presentcontigs = cur.fetchall()
if presentcontigs[0][0] == 0:
    # Make dict of fasta file while accounting for possible multiline sequences
    handle = open(Path(fastafile), 'r').readlines()
    fastadict = {}
    x = 0
    if len(handle) > 2 and not handle[2].startswith(
            ">"):  # one file had this fasta format where the sequence was on different lines
        pathcopytempfile = Path('/tmp') / ''.join([isolate_name.lower(), '.fasta'])
        shutil.copyfile((Path(fastafile)), pathcopytempfile)
        with open(pathcopytempfile, 'r') as file:
            handle2 = file.read()
        with open(pathcopytempfile, 'w') as file:
            file.write(re.sub('(?<=[A-Z])\n(?=[A-Z])', '', handle2))
        handle = open(pathcopytempfile, 'r').readlines()
        os.remove(pathcopytempfile)

    while x < len(handle):
        if handle[x].startswith(">"):
            fastadict[handle[x].rstrip().replace(f">{isolate_name}", "").strip("-_")] = handle[x + 1].rstrip()
        x += 2
    ###

    # insert into database
    for sequencename, sequence in fastadict.items():
        cur.execute(f"INSERT INTO sequence_bin(id, "
                    f"isolate_id, "
                    f"remote_contig, sequence, original_designation, sender, "
                    f"curator, date_entered, datestamp) "
                    f"VALUES((SELECT CASE WHEN (SELECT(SELECT MAX(id) FROM sequence_bin)+1) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM sequence_bin)+1) END), "
                    f"(SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                    f"'f', '{sequence}', '{sequencename.strip('>')}', 1, "
                    f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

    # # remove the file
    # os.remove(Path(fastafile))

else:
    sys.exit(f"isolate {isolate_name} already contains assembly records!")
