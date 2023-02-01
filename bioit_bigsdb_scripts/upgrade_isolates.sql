INSERT INTO scheme_fields(scheme_id, field, type, description, field_order, dropdown, primary_key, curator, datestamp, isolate_display, main_display, query_field) VALUES(2, 'cgST', 'integer', 'Sequence Type (cgMLST)', 1, 'f', 't', 1, (SELECT CURRENT_DATE), 't', 't', 't');
ALTER TABLE submissions ADD validation_type text;
ALTER TABLE isolates ADD validation_type text;
ALTER TABLE isolates ADD validation_curator text;
ALTER TABLE isolates ADD validation_date date;