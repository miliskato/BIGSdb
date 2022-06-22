#!/bin/bash

export MODULEPATH=/etc/lmod/modules
source /etc/profile.d/lmod.sh

cd /temp/scratch
export PYTHONPATH=/home/BIGSdb/automated-reanalysis
source /home/BIGSdb/3.9PythonVenv/bin/activate
for species in listeria neisseria stec mycobacterium salmonella
do
  python /home/BIGSdb/automated-reanalysis/camel/scripts/reanalysis/reanalysis.py --host-url http://$HOSTNAME.sciensano.be --species $species --config /home/BIGSdb/automated-reanalysis/camel/scripts/reanalysis/config.yml --threads 4
done
