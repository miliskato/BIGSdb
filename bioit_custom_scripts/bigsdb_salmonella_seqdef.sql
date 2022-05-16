INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp)
VALUES(1, 'MLST', 'MLST scheme downloaded and updated weekly from the Pasteur-institute Bigsdb-interface.', 't', 1, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp)
VALUES(2, 'cgMLST', 'cgMLST scheme downloaded and updated weekly from the Pasteur-institute Bigsdb-interface.', 't', 2, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO scheme_fields(scheme_id, field, type, description, field_order, dropdown, primary_key, curator, datestamp)
 VALUES(1, 'ST', 'integer', 'Sequence Type', 1, 'f', 't', 1, (SELECT CURRENT_DATE));