#!/bin/bash

username=$1
species=$2

#use: make_curator.sh username species

psql  -d bigsdb_${species}_isolates -c "update users set curator = 1 where user_name = '${username}'";
psql  -d bigsdb_${species}_isolates -c "update users set status = 'curator' where user_name = '${username}'";
psql  -d bigsdb_${species}_seqdef -c "update users set curator = 1 where user_name = '${username}'";
psql  -d bigsdb_${species}_seqdef -c "update users set status = 'curator' where user_name = '${username}'";
psql  -d global_bigsdb_users -c "INSERT INTO permissions (user_name,permission,curator,datestamp) VALUES ('${username}','modify_isolates','${username}','now'), ('${username}','modify_projects','${username}','now'), ('${username}','modify_field_attributes','${username}','now'), ('${username}','modify_value_attributes','${username}','now'), ('${username}','designate_alleles','${username}','now'), ('${username}','modify_sparse_fields','${username}','now')";
