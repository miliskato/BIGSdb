#!/bin/bash

# will make a shell script with positional arguments
# $1 tsvpath
# $2 user mail
# $3 output file
# $5 fastq-hash (can be in tsv) # not done yet

if grep -q $2 /db/galaxy_bigsdb_access/approved_users.txt; then :
else
  printf '%s\n' "${2} is not an approved user" >&2
  exit
fi

cd /scratch/galaxy/temp
rm -f list_of_isolates.txt
# get species from tsv, two step process to be sure to have right line
speciesline=$(cat $1 | awk '{print $1}' | grep -n pipeline_name | awk -F ':' '{print $1}')
species=$(cat $1 |  sed -n ${speciesline}p | awk '{print $2}' | tr '[:upper:]' '[:lower:]')

if [ $species == "mycobacterium" ] || [ $species == "listeria" ]; then :
else
  printf '%s\n' "${species} is not an approved species" >&2
  exit
fi

# get sample_name from tsv, two step process to be sure to have right line
nameline=$(cat $1 | awk '{print $1}' | grep -n sample | awk -F ':' '{print $1}')
sample_name=$(cat $1 |  sed -n ${nameline}p | awk '{print $2}')

touch list_of_isolates.txt

for f in `curl -s http://bioit-bigs-test.sciensano.be:5000/db/bigsdb_${species}_isolates/isolates | grep -oP '(?<="http://bioit-bigs-test.sciensano.be:5000/db/bigsdb_'${species}'_isolates/isolates/)[^"]*'`; do curl -s http://bioit-bigs-test.sciensano.be:5000/db/bigsdb_${species}_isolates/isolates/$f | grep -oP '(?<="isolate":")[^"]*' >> list_of_isolates.txt; done

if grep -q $sample_name list_of_isolates.txt; then
  printf '%s\n' "${sample_name} already exists in ${species} BIGSdb" >&2
  exit
fi

# get html file and folder from tsv file name, by taking basename and doing -1
tsvfilenumber=$(basename "$1" .dat | awk -F '_' '{print $2}')
htmlfilenumber=$(( $tsvfilenumber - 1 ))
htmlfilename=$(echo $1 | sed "s/$tsvfilenumber/$htmlfilenumber/g")
htmlfilefolder=$(echo $htmlfilename | sed 's/\.dat/_files/g')

mkdir $sample_name

cp $1 ./$sample_name/report.tsv
cp $htmlfilename ./$sample_name/report.html
cp -r $htmlfilefolder/* ./$sample_name/
touch ./$sample_name/info.txt
echo "{'sample_name': '${sample_name}', 'species': '${species}', 'user': '$2'}" > ./$sample_name/info.txt
tar -cf $sample_name.tar ./$sample_name/
md5sum $sample_name.tar > ${sample_name}_md5.txt

scp -i /home/galaxy/.ssh/id_rsa_bigsdb -r ./$sample_name.tar galaxy@bioit-bigs-test:/home/galaxy
scp -i /home/galaxy/.ssh/id_rsa_bigsdb -r ./${sample_name}_md5.txt galaxy@bioit-bigs-test:/home/galaxy

echo "{user_mail: $2, sample_name: $sample_name, species: $species}" > $3
# todo need a check for pipeline name in tsv

rm -r $sample_name ${sample_name}_md5.txt $sample_name.tar
