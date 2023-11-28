// parses a html and searches for the html element with the id "largetable_resultsheader" and returns its value (splitted by spaces and the 0th element).
// If no value is found, then it returns 0. Typically the value would be a sentence like "2 records returned. Click the hyperlinks for detailed information."
const parseHTML_returnINT = html => {
    return ((element = new DOMParser().parseFromString(html, "text/html").getElementById("largetable_resultsheader")) => {
        return element ? element.textContent.split(" ")[0] : "0";
    })();
}

// Parses the input url and passes the html on to the parseHTML_returnINT constant.
// Then combines the int and the url into a href element and replaces an element in the html with a given id (id_field) by the href element.
// the function works for any url that uses the search function in bigsdb: bigsdb.pl?set_id=0&page=query
// an example url would be: "/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&order=id&db=bigsdb_mycobacterium_isolates&designation_value1=1&designation_field1=s_2_cgST&designation_value2=5&designation_field2=s_2_cgST"
function replaceQueriedValue(url, id_field) {
    return fetch(url)
        .then(response => response.text())
        .then(html => {
            const recordsFound = parseHTML_returnINT(html);
            document.getElementById(id_field).innerHTML = `<a href=${url} target="_blank">${recordsFound} isolates</a>`;
        });
}