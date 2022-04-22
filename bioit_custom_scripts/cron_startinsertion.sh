#!/bin/bash

for dir in /home/galaxy/*/
do
  species=$(cat $dir/info.txt | grep -oP "(?<='species': ')[^']*")
  sample_name=$(cat $dir/info.txt | grep -oP "(?<='sample_name': ')[^']*")
  /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/reportmover.py --reportdirectory $dir --species $species
  /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/html_tagger.py --htmlfilepath /reports/$species/$sample_name/report.html
  /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/isolate_${species}_typing_results.py --tsvfilepath /reports/$species/$sample_name/report.tsv
  /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/isolate_${species}_typing_results.py --fastafilepath /reports/$species/$sample_name/assembly/${sample_name}_contigs.fasta --isolatename $sample_name --species $species
done

# should probably add an if statement for the assembly inserter because paths may vary