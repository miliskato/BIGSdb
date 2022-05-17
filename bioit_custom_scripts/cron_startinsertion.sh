#!/bin/bash

cd /home/galaxy

for file in /home/galaxy/*_md5.txt
do
  file_name=$(basename $file _md5.txt)
  if [ $(md5sum /home/galaxy/$file_name.tar | awk '{print $1}') == $(cat $file | awk '{print $1}') ]; then
    tar -xf /home/galaxy/$file_name.tar # else wait until md5sum same
    rm /home/galaxy/$file_name.tar
    rm $file
  fi
done



for dir in /home/galaxy/*/
do
  species=$(cat $dir/info.txt | grep -oP "(?<='species': ')[^']*")
  sample_name=$(cat $dir/info.txt | grep -oP "(?<='sample_name': ')[^']*")
  {
    /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/reportmover.py --reportdirectory $dir --species $species
    /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/htmltagger.py --htmlfilepath /reports/$species/$sample_name/report.html --species $species
    /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/isolate_${species}_typing_results.py --tsvfilepath /reports/$species/$sample_name/report.tsv --isolatename $sample_name
    /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/insert_assemblies.py --fastafilepath /reports/$species/$sample_name/assembly/${sample_name}_contigs.fasta --isolatename $sample_name --species $species
    /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/cgmlst_similar_isolates.py --isolatename $sample_name --species $species
  } 2>&1 | tee /home/galaxy/$sample_name.bigsdb_insertion.log
  mv /home/galaxy/$sample_name.bigsdb_insertion.log /reports/$species/$sample_name/
done
# should probably add an if statement for the assembly inserter because paths may vary






# */1 *   * * *   root    bash /home/BIGSdb/bioit_custom_scripts/cron_startinsertion.sh