#!/bin/bash

cd /home/galaxy/mongo

for file in /home/galaxy/mongo/*_md5.txt
do
  file_name=$(basename $file _md5.txt)
  if [ $(md5sum /home/galaxy/mongo/$file_name.tar | awk '{print $1}') == $(cat $file | awk '{print $1}') ]; then
    tar -xf /home/galaxy/mongo/$file_name.tar # else wait until md5sum same
    rm /home/galaxy/mongo/$file_name.tar
    rm $file
  fi
done



for dir in /home/galaxy/mongo/*/
do
  species=$(cat $dir/info.txt | grep -oPw "(?<='species': ')[^']*")
  sample_name=$(cat $dir/info.txt | grep -oPw "(?<='sample_name': ')[^']*")
  uploader=$(cat $dir/info.txt | grep -oPw "(?<='user': ')[^']*")
  {
    sudo mv $dir /reports/$species/mongo/
    /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/htmltagger.py --htmlfilepath /reports/$species/mongo/$sample_name/report.html --species $species
    /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/main_results_inserter.py --jsonfilepath /reports/$species/$sample_name/report.json --isolatename $sample_name --uploadermailadress $uploader --species $species --results_type new_isolate
    /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/insert_assemblies.py --fastafilepath /reports/$species/$sample_name/assembly/${sample_name}_contigs.fasta --isolatename $sample_name --species $species
##    /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/cgmlst_similar_isolates.py --isolatename $sample_name --species $species
  } 2>&1 | tee /home/galaxy/mongo/$sample_name.bigsdb_insertion.log
  mv /home/galaxy/mongo/$sample_name.bigsdb_insertion.log /reports/$species/mongo/$sample_name/
done
# should probably add an if statement for the assembly inserter because paths may vary






# */1 *   * * *   root    bash /home/BIGSdb/bioit_custom_scripts/cron_startinsertion.sh
