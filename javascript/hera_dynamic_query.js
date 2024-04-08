function generateUrlCgst(species, cgmlst_bigsdb_scheme_id, cgsts) {
    // generates the url to look up all isolates belonging to specific cgsts
    // usage: <script type="text/javascript">generateUrlCgst("mycobacterium", "2", ["1","2","3"])</script>

    // arg species: str: commonly used bioit species name; either genus or specific like stec
    // arg cgmlst_bigsdb_scheme_id: int as str: usually 2 (1 is mlst), but seeing as stec has two mlst's it's 3 there
    // arg cgsts: List of ints as List of strs: all the to be queried cgsts

    // an example return would be; "/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&order=id&db=bigsdb_mycobacterium_isolates&designation_value1=1&designation_field1=s_2_cgST&designation_value2=5&designation_field2=s_2_cgST"
    let url = `/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&db=bigsdb_${species}_isolates`;

    cgsts.forEach((cgst, index) => {
        url += `&designation_value${index + 1}=${cgst}&designation_field${index + 1}=s_${cgmlst_bigsdb_scheme_id}_cgST`;
    });
    url += `&designation_andor=OR`;

    return url;
}

function generateUrlCgstDate(species, cgmlst_bigsdb_scheme_id, cgsts, date_lower, date_upper) {
    // generates the url to look up all isolates belonging to specific cgsts and inserted within a certain date range (YYYY-MM-DD)
    // usage: <script type="text/javascript">generateUrlCgst("mycobacterium", "2", ["1","2","3"], "2020-02-03", "2026-06-19")</script>

    // arg species: str: commonly used bioit species name; either genus or specific like stec
    // arg cgmlst_bigsdb_scheme_id: int as str: usually 2 (1 is mlst), but seeing as stec has two mlst's it's 3 there
    // arg cgsts: List of ints as List of strs: all the to be queried cgsts
    // arg date_lower; str: the lowerbound isolation date
    // arg date_upper; str: the upperbound isolation date

    // an example return would be; "/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&order=id&db=bigsdb_mycobacterium_isolates&designation_value1=1&designation_field1=s_2_cgST&designation_value2=5&designation_field2=s_2_cgST&prov_field1=isolation_date&prov_value1=2020-06-05&prov_operator1=>=&prov_field2=isolation_date&prov_value2=2024-08-02&prov_operator2=<="
    let url = `/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&db=bigsdb_${species}_isolates&prov_field1=isolation_date&prov_value1=${date_lower}&prov_operator1=>=&prov_field2=isolation_date&prov_value2=${date_upper}&prov_operator2=<=`;

    cgsts.forEach((cgst, index) => {
        url += `&designation_value${index + 1}=${cgst}&designation_field${index + 1}=s_${cgmlst_bigsdb_scheme_id}_cgST`;
    });
    url += `&designation_andor=OR`;

    return url;
}

function generateUrlClgr(species, clgr_bigsdb_scheme_id, clgr) {
    // generates the url to look up all isolates belonging to a specific cluster/classification group
    // usage: <script type="text/javascript">generateUrlCgst("mycobacterium", "2", "5")</script>

    // arg species: str: commonly used bioit species name; either genus or specific like stec
    // arg clgr_bigsdb_scheme_id: int as str: either 1 or 2 for the warnings and alerts, but possibly another number if htere are more hierarchical clustering thresholds
    // arg clgr: int as str: cluster/classification group

    // an example return would be; "/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&order=id&db=bigsdb_mycobacterium_isolates&designation_value1=1&designation_field1=cg_2_group"
    return `/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&db=bigsdb_${species}_isolates&designation_value1=${clgr}&designation_field1=cg_${clgr_bigsdb_scheme_id}_group`;
}

function generateUrlClgrDate(species, clgr_bigsdb_scheme_id, clgr, date_lower, date_upper) {
    // generates the url to look up all isolates belonging to a specific cluster/classification group and inserted within a certain date range (YYYY-MM-DD)
    // usage: <script type="text/javascript">generateUrlCgst("mycobacterium", "2", "5")</script>

    // arg species: str: commonly used bioit species name; either genus or specific like stec
    // arg clgr_bigsdb_scheme_id: int as str: either 1 or 2 for the warnings and alerts, but possibly another number if htere are more hierarchical clustering thresholds
    // arg clgr: int as str: cluster/classification group
        // arg date_lower; str: the lowerbound isolation date
    // arg date_upper; str: the upperbound isolation date

    // an example return would be; "/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&order=id&db=bigsdb_mycobacterium_isolates&designation_value1=1&designation_field1=cg_2_group&prov_field1=isolation_date&prov_value1=2020-06-05&prov_operator1=>=&prov_field2=isolation_date&prov_value2=2024-08-02&prov_operator2=<="
    return `/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&db=bigsdb_${species}_isolates&designation_value1=${clgr}&designation_field1=cg_${clgr_bigsdb_scheme_id}_group&prov_field1=isolation_date&prov_value1=${date_lower}&prov_operator1=>=&prov_field2=isolation_date&prov_value2=${date_upper}&prov_operator2=<=`;
}

const parseHTML_returnINT = html => {
    // parses a html and searches for the html element with the id "largetable_resultsheader" and returns its value (splitted by spaces and the 0th element). This element contains the nr of isolates returned for the given url.
    // If no value is found, then it returns 0. Typically the value would be a sentence like "2 records returned. Click the hyperlinks for detailed information."

    // arg html: actual html, the fetched url

    // the return is an int casted as a str, so "0" or "1"
    return ((element = new DOMParser().parseFromString(html, "text/html").getElementById("largetable_resultsheader")) => {
        return element ? element.textContent.split(" ")[0] : "0";
    })();
}

function replaceQueriedValue(url, id_field) {
    // Parses the input url and passes the html on to the parseHTML_returnINT constant.
    // Then combines the int and the url into a href element and replaces an element in the html with a given id (id_field) by the href element.
    // the function works for any url that uses the search function in bigsdb: bigsdb.pl?set_id=0&page=query

    // arg url: an url like the output of generateUrlCgst
    // id_field: the id of the html element that needs to be replaced

    // there is no return; the function modifies the html in place, in practice it is used right after specifying a html element with the given id_field
    return fetch(url)
        .then(response => response.text())
        .then(html => {
            const recordsFound = parseHTML_returnINT(html);
            document.getElementById(id_field).innerHTML = `<a href="${url}" target="_blank">${recordsFound} isolates</a>`;
        });
}

function addUrlToField(url, id_field) {
    // Adds a Url to a html element; this allows for very long urls that are dynamically generated and then don't need to be stored in the sql table
    // the function works for any url that uses the search function in bigsdb: bigsdb.pl?set_id=0&page=query

    // arg url: an url like the output of generateUrlCgst
    // id_field: the id of the html element that needs to be replaced

    // there is no return; the function modifies the html in place, in practice it is used right after specifying a html element with the given id_field
    return document.getElementById(id_field).innerHTML = `<a href=${url} target="_blank">${id_field}</a>`;
}