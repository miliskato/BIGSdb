#!/bin/bash
# Checks whether new uploads are available from galaxy to bigsdb using the following cron command
# The cronjob is deployed using ansible in the bigsdb role (tasks/main.yml)
# */1 *   * * *   root    bash /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/cron_startinsertion_mongo_implementation.sh

AZURE_REPORTSAPI_IP=to_be_replaced_by_ansible
DTAP=to_be_replaced_by_ansible

cd /scratch/bigsupload/mongo

for file in /scratch/bigsupload/mongo/*_md5.txt
do
  file_name=$(basename $file _md5.txt)
  if [ $(md5sum /scratch/bigsupload/mongo/$file_name.tar | awk '{print $1}') == $(cat $file | awk '{print $1}') ]; then
    tar -xf /scratch/bigsupload/mongo/$file_name.tar # else wait until md5sum same
    rm /scratch/bigsupload/mongo/$file_name.tar
    rm $file
  fi
done

VENV_PYTHON_BIGSDB=/home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9

for dir in /scratch/bigsupload/mongo/*/
do
  set -o errexit
  species=$(cat $dir/info.txt | grep -oPw "(?<='species': ')[^']*")
  sample_name=$(cat $dir/info.txt | grep -oPw "(?<='sample_name': ')[^']*")
  uploader=$(cat $dir/info.txt | grep -oPw "(?<='user': ')[^']*")
  insert_date=$(date +%m-%d-%Y_%H:%M:%S)
  {
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/htmltagger.py --htmlfilepath $dir/${species}/${sample_name}_${insert_date}/report.html --species $species
    # !!! resequencings will break because they will not be able to access the fastafilepath to check the md5sum,
    # !!! i don't currently see a way around it without having to temporarily add remote md5sum commands to the mainmongo script.
    # todo original_input_format?
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_mongodb_scripts/mainmongo.py --reportdirectorypath /results/${DTAP}/${species}/${sample_name}_${insert_date} --species ${species} --uploader_mail_address ${uploader} --jsonfilepath $dir/${species}/${sample_name}_${insert_date}/report.json --technical_id ${sample_name} --fastafilepath /results/${DTAP}/${species}/${sample_name}_${insert_date}/assembly/${sample_name}_contigs.fasta --vcffilepath  /results/${DTAP}/${species}/${sample_name}_${insert_date}/variant_calling/variants-${sample_name}-all.vcf --results_type new_isolate
    scp -r -o StrictHostKeyChecking=no -i /home/bigsdb/.ssh/.id_rsa_reportsapi bigsdb@$AZURE_REPORTSAPI_IP:/results/${DTAP}/${species}/${sample_name}_${insert_date} $dir
  } 2>&1 | tee /scratch/bigsupload/mongo/$sample_name.mongodb_bigsdb_insertion.log
   scp -o StrictHostKeyChecking=no -i /home/bigsdb/.ssh/.id_rsa_reportsapi bigsdb@$AZURE_REPORTSAPI_IP:/results/${DTAP}/${species}/${sample_name}_${insert_date} /scratch/bigsupload/mongo/$sample_name.mongodb_bigsdb_insertion.log
   rm /scratch/bigsupload/mongo/$sample_name.mongodb_bigsdb_insertion.log
done
