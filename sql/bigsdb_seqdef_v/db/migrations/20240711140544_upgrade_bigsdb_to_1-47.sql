-- migrate:up
CREATE TABLE curator_configs (
user_id integer NOT NULL,
dbase_config text NOT NULL,
curator integer NOT NULL,
datestamp date NOT NULL,
PRIMARY KEY (user_id,dbase_config),
CONSTRAINT cc_user_id FOREIGN KEY (user_id) REFERENCES users
ON DELETE CASCADE
ON UPDATE CASCADE,
CONSTRAINT cc_curator FOREIGN KEY (curator) REFERENCES users
ON DELETE NO ACTION
ON UPDATE CASCADE
);

GRANT SELECT,UPDATE,INSERT,DELETE ON curator_configs TO apache;

DROP INDEX i_s2;
CREATE INDEX i_s2 ON sequences(exemplar,locus);
CREATE INDEX i_s4 ON sequences(sender);

ALTER TABLE schemes ALTER COLUMN allow_missing_loci boolean NOT NULL DEFAULT FALSE;
ALTER TABLE schemes ADD COLUMN allow_presence boolean NOT NULL DEFAULT FALSE;
ALTER TABLE schemes ALTER COLUMN no_submissions boolean NOT NULL DEFAULT FALSE;
ALTER TABLE schemes ALTER COLUMN disable boolean NOT NULL DEFAULT FALSE;

ALTER TABLE scheme_fields ADD COLUMN option_list text;

DROP INDEX i_sr1;
DROP INDEX i_a1;
DROP INDEX i_p1;
DROP INDEX i_pm3;
CREATE INDEX i_pm4 ON profile_members(locus,allele_id,scheme_id);
DROP INDEX i_pf3;
DROP INDEX i_pr1;
ALTER TABLE submissions ADD COLUMN dataset text;

CREATE OR REPLACE FUNCTION update_locus_stats() RETURNS TRIGGER AS $update_locus_stats$
	DECLARE
		current_min_length integer;
		current_max_length integer;
		current_datestamp date;
		allele_length integer;
	BEGIN
		IF (TG_OP = 'DELETE' AND OLD.allele_id NOT IN ('0','N','P')) THEN
			PERFORM locus FROM sequences WHERE locus=OLD.locus;
			IF NOT FOUND THEN  --There are no more alleles for this locus.
				UPDATE locus_stats SET datestamp=null,allele_count=0,min_length=null,max_length=null WHERE locus=OLD.locus;
			ELSE
				SELECT MIN(LENGTH(sequence)),MAX(LENGTH(sequence)),MAX(datestamp) INTO
				current_min_length,current_max_length,current_datestamp FROM sequences WHERE
				locus=OLD.locus AND allele_id NOT IN ('0','N','P');
				UPDATE locus_stats SET datestamp=current_datestamp,allele_count=allele_count-1,
				min_length=current_min_length,max_length=current_max_length WHERE locus=OLD.locus;
			END IF;
		ELSIF (TG_OP = 'INSERT' AND NEW.allele_id NOT IN ('0','N','P')) THEN
			UPDATE locus_stats SET datestamp='now',allele_count=allele_count+1 WHERE locus=NEW.locus;
			SELECT min_length,max_length INTO current_min_length,current_max_length FROM locus_stats WHERE locus=NEW.locus;
			allele_length := LENGTH(NEW.sequence);
			IF (current_min_length IS NULL OR allele_length < current_min_length) THEN
				UPDATE locus_stats SET min_length = allele_length WHERE locus=NEW.locus;
			END IF;
			IF (current_max_length IS NULL OR allele_length > current_max_length) THEN
				UPDATE locus_stats SET max_length = allele_length WHERE locus=NEW.locus;
			END IF;
		END IF;
		RETURN NULL;
	END;
$update_locus_stats$ LANGUAGE plpgsql;

CREATE TABLE peptide_mutations (
id int NOT NULL UNIQUE,
locus text NOT NULL,
wild_type_allele_id text,
reported_position int NOT NULL,
locus_position int NOT NULL,
wild_type_aa text NOT NULL,
variant_aa text NOT NULL,
flanking_length int NOT NULL,
curator integer NOT NULL,
datestamp date NOT NULL,
PRIMARY KEY (id),
CONSTRAINT pm_wild_type_allele_id FOREIGN KEY (locus,wild_type_allele_id) REFERENCES sequences(locus,allele_id)
ON DELETE NO ACTION
ON UPDATE CASCADE,
CONSTRAINT pm_curator FOREIGN KEY (curator) REFERENCES users
ON DELETE NO ACTION
ON UPDATE CASCADE
);

GRANT SELECT,UPDATE,INSERT,DELETE ON peptide_mutations TO apache;

CREATE TABLE sequences_peptide_mutations (
locus text NOT NULL,
allele_id text NOT NULL,
mutation_id int NOT NULL,
amino_acid char(1) NOT NULL,
is_wild_type boolean NOT NULL,
is_mutation boolean NOT NULL,
curator integer NOT NULL,
datestamp date NOT NULL,
PRIMARY KEY(locus, allele_id, mutation_id),
CONSTRAINT spm_sequences FOREIGN KEY (locus,allele_id) REFERENCES sequences
ON DELETE CASCADE
ON UPDATE CASCADE,
CONSTRAINT spm_mutation_id FOREIGN KEY (mutation_id) REFERENCES peptide_mutations
ON DELETE CASCADE
ON UPDATE CASCADE,
CONSTRAINT spm_curator FOREIGN KEY (curator) REFERENCES users
ON DELETE NO ACTION
ON UPDATE CASCADE
);

GRANT SELECT,UPDATE,INSERT,DELETE ON sequences_peptide_mutations TO apache;

CREATE TABLE dna_mutations (
id int NOT NULL UNIQUE,
locus text NOT NULL,
wild_type_allele_id text,
reported_position int NOT NULL,
locus_position int NOT NULL,
wild_type_nuc text NOT NULL,
variant_nuc text NOT NULL,
flanking_length int NOT NULL,
curator integer NOT NULL,
datestamp date NOT NULL,
PRIMARY KEY (id),
CONSTRAINT dm_curator FOREIGN KEY (curator) REFERENCES users
ON DELETE NO ACTION
ON UPDATE CASCADE
);

GRANT SELECT,UPDATE,INSERT,DELETE ON dna_mutations TO apache;

CREATE TABLE sequences_dna_mutations (
locus text NOT NULL,
allele_id text NOT NULL,
mutation_id int NOT NULL,
nucleotide char(1) NOT NULL,
is_wild_type boolean NOT NULL,
is_mutation boolean NOT NULL,
curator integer NOT NULL,
datestamp date NOT NULL,
PRIMARY KEY(locus, allele_id, mutation_id),
CONSTRAINT sdm_sequences FOREIGN KEY (locus,allele_id) REFERENCES sequences
ON DELETE CASCADE
ON UPDATE CASCADE,
CONSTRAINT sdm_mutation_id FOREIGN KEY (mutation_id) REFERENCES dna_mutations
ON DELETE CASCADE
ON UPDATE CASCADE,
CONSTRAINT sdm_curator FOREIGN KEY (curator) REFERENCES users
ON DELETE NO ACTION
ON UPDATE CASCADE
);

GRANT SELECT,UPDATE,INSERT,DELETE ON sequences_dna_mutations TO apache;

CREATE TABLE db_attributes (
field text NOT NULL,
value text NOT NULL,
PRIMARY KEY(field)
);

GRANT SELECT,UPDATE,INSERT,DELETE ON db_attributes TO apache;

INSERT INTO db_attributes (field,value) VALUES ('version','45');
INSERT INTO db_attributes (field,value) VALUES ('type','seqdef');

-- migrate:down
DROP TABLE curator_configs;

DROP INDEX i_s2;
CREATE INDEX i_s2 ON sequences(exemplar) WHERE exemplar;
DROP INDEX i_s4;

ALTER TABLE schemes ALTER COLUMN allow_missing_loci boolean;
ALTER TABLE schemes DROP COLUMN allow_presence;
ALTER TABLE schemes ALTER COLUMN no_submissions boolean;
ALTER TABLE schemes ALTER COLUMN disable boolean;

ALTER TABLE scheme_fields DROP COLUMN option_list;

CREATE INDEX i_sr1 ON sequence_refs (pubmed_id);
CREATE INDEX i_a1 ON accession (databank,databank_id);
CREATE INDEX i_p1 ON profiles ((lpad(profile_id,20,'0')));
CREATE INDEX i_pm3 ON profile_members (allele_id);
DROP INDEX i_pm4;
CREATE INDEX i_pf3 ON profile_fields (value);
CREATE INDEX i_pr1 ON profile_refs (pubmed_id);
ALTER TABLE submissions DROP COLUMN dataset;

CREATE OR REPLACE FUNCTION update_locus_stats() RETURNS TRIGGER AS $update_locus_stats$
	DECLARE
		current_min_length integer;
		current_max_length integer;
		current_datestamp date;
		allele_length integer;
	BEGIN
		IF (TG_OP = 'DELETE' AND OLD.allele_id NOT IN ('0','N')) THEN
			PERFORM locus FROM sequences WHERE locus=OLD.locus;
			IF NOT FOUND THEN  --There are no more alleles for this locus.
				UPDATE locus_stats SET datestamp=null,allele_count=0,min_length=null,max_length=null WHERE locus=OLD.locus;
			ELSE
				SELECT MIN(LENGTH(sequence)),MAX(LENGTH(sequence)),MAX(datestamp) INTO
				current_min_length,current_max_length,current_datestamp FROM sequences WHERE
				locus=OLD.locus AND allele_id NOT IN ('0','N');
				UPDATE locus_stats SET datestamp=current_datestamp,allele_count=allele_count-1,
				min_length=current_min_length,max_length=current_max_length WHERE locus=OLD.locus;
			END IF;
		ELSIF (TG_OP = 'INSERT' AND NEW.allele_id NOT IN ('0','N')) THEN
			UPDATE locus_stats SET datestamp='now',allele_count=allele_count+1 WHERE locus=NEW.locus;
			SELECT min_length,max_length INTO current_min_length,current_max_length FROM locus_stats WHERE locus=NEW.locus;
			allele_length := LENGTH(NEW.sequence);
			IF (current_min_length IS NULL OR allele_length < current_min_length) THEN
				UPDATE locus_stats SET min_length = allele_length WHERE locus=NEW.locus;
			END IF;
			IF (current_max_length IS NULL OR allele_length > current_max_length) THEN
				UPDATE locus_stats SET max_length = allele_length WHERE locus=NEW.locus;
			END IF;
		END IF;
		RETURN NULL;
	END;
$update_locus_stats$ LANGUAGE plpgsql;

DROP TABLE peptide_mutations;
DROP TABLE dna_mutations;
DROP TABLE sequences_dna_mutations;
DROP TABLE db_attributes;