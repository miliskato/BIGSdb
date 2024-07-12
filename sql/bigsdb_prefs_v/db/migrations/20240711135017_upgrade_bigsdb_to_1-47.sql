-- migrate:up
CREATE OR REPLACE FUNCTION next_dashboard(_guid text,_dbase_config text) RETURNS text AS $next_dashboard$
DECLARE
		dashboard_count integer;
BEGIN
	SELECT COUNT(*) INTO dashboard_count FROM dashboards WHERE (guid,dbase_config)=(_guid,_dbase_config);
	RETURN 'dashboard#' || (dashboard_count+1);
END
$next_dashboard$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION name_dashboard() RETURNS TRIGGER AS $next_dashboard$
DECLARE
	dashboard_count integer;
	new_name text;
	name_exists boolean;
BEGIN
    IF NEW.name IS NULL THEN
    	dashboard_count := 1;
    	name_exists := 1;
    	WHILE name_exists LOOP
    		new_name := 'dashboard#' || LPAD((dashboard_count)::text,2,'0');
    		IF NOT EXISTS (SELECT * FROM dashboards WHERE (guid,dbase_config,name)=(NEW.guid,NEW.dbase_config,new_name)) THEN
    			name_exists = false;
    		END IF;
    		dashboard_count := dashboard_count + 1;
    	END LOOP;
    	NEW.name := new_name;
    END IF;
    RETURN NEW;
END;
$next_dashboard$ language plpgsql;

-- migrate:down
CREATE OR REPLACE FUNCTION next_dashboard(_guid text,_dbase_config text) RETURNS text AS $next_dashboard$
DECLARE
		dashboard_count integer;
BEGIN
	SELECT COUNT(*) INTO dashboard_count FROM dashboards WHERE (guid,dbase_config)=(_guid,_dbase_config);
	RETURN 'dashboard#' || (dashboard_count+1);
END
$next_dashboard$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION name_dashboard() RETURNS TRIGGER AS $next_dashboard$
DECLARE
	dashboard_count integer;
BEGIN
    IF NEW.name IS NULL THEN
    	SELECT COUNT(*) INTO dashboard_count FROM dashboards WHERE (guid,dbase_config)=(NEW.guid,NEW.dbase_config);
    	NEW.name := 'dashboard#' || LPAD((dashboard_count+1)::text,2,'0');
    END IF;
    RETURN NEW;
END;
$next_dashboard$ language plpgsql;
