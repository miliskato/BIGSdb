#!/bin/bash -x

# this script should be executed as postgres user
# arguments to be passed:
# $1 first name
# $2 last name
# $3 password
# $4 species

# This script inserts a user into the global user database,
# its password in bigsdb_auth,
# and the user into the users tables of the species db

firstname=$(echo ${1:0:2})
username=$firstname$2
password=$3
species=$4

perl /home/bigsdb/BIGSdb/scripts/maintenance/add_user.pl -a -d global_bigsdb_users -n $username -p $password
psql -d global_bigsdb_users -c "INSERT INTO users (user_name,surname,first_name,email,affiliation,date_entered,datestamp,status) VALUES ('${username}','${2}','${1}', '${1}.${2}@sciensano.be','Sciensano','now','now', 'validated');"
psql -d bigsdb_${species}_seqdef -c "INSERT INTO users (id, user_name, surname, first_name, email, affiliation, status, date_entered, datestamp, curator, user_db) VALUES ((SELECT(SELECT MAX(id) FROM users)+1),'${username}','${2}','${1}', '${1}.${2}@sciensano.be','Sciensano','user','now','now', 0, 1);"
psql -d bigsdb_${species}_isolates -c "INSERT INTO users (id, user_name, surname, first_name, email, affiliation, status, date_entered, datestamp, curator, user_db) VALUES ((SELECT(SELECT MAX(id) FROM users)+1),'${username}','${2}','${1}', '${1}.${2}@sciensano.be','Sciensano','user','now','now', 0, 1);"
exit