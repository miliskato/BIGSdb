//application for the api of HERA

function getCookieValue(cookieName) {
    // Split the document.cookie string into individual cookies
    var cookies = document.cookie.split(';');

    // Iterate through the cookies to find the one with the specified name
    for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        // Check if the cookie starts with the provided name
        if (cookie.startsWith(cookieName + '=')) {
            // Return the cookie value (substring after the '=' sign)
            return cookie.substring(cookieName.length + 1);
        }
    }
    // Return null if the cookie is not found
    return null;
}

function get_jwt_preview(id, pseudo_id, species, validation_type, res_time, get_zip, dtap, newWindow){
    // gets the html report from Azure through the API, if it fails, returns a failure message
    query_url = "/reportsapi" + "/get_html_report?isolate_id=" + pseudo_id + '&date=' + res_time + "&species=" + species + "&get_zip=" + get_zip + "&dtap=" + dtap + "&validation_type=" + validation_type
    console.log(query_url)
    $.ajax( query_url , {
        method: 'GET',
        headers: {"x-access-token": localStorage.getItem('token')},
        success:function(response){
            // console.log(response);
            //     var baseUrl = window.location.href.split('?')[0];
            //     var blobContent = '<base href="' + baseUrl  + '">' + '<script src="' + baseUrl  + '/../../javascript/bigsdb.min.js">'+ response;
            //     var blob = new Blob([blobContent], { type: 'text/html' });
            //     newWindow.location.href = URL.createObjectURL(blob);
            newWindow.document.body.innerHTML = '';  // in order to clear previous message
            newWindow.document.write('<script src="/javascript/jquery.min.js"></script>' +
                '<script src="/javascript/hera_reportsapi.js"></script>' +
                '<meta name="pseudo_id" content="' + pseudo_id + '" />' +
                '<style> /* Custom link class to enhance default anchor behavior */ .custom-link { color: blue; text-decoration: underline; cursor: pointer; } .custom-link.visited { color: purple; } .custom-link:active { color: red; } </style>' +
                response.replaceAll(pseudo_id, id).replace(/<title>.*?<\/title>/i, "<title>" +id + "</title>"));
           },
        error:function(){
        var blob = new Blob(['Failure to retrieve the report. Please resubmit the request to start again or submit a ticket to bioit@sciensano if it still fails'], { type: 'text/html' });
        newWindow.location.href = URL.createObjectURL(blob);
    }
    });
}

function replacePseudoIdByID(content, pseudo_id, id) {
    // Function to modify file content (similar to `sed`)
    const regex = new RegExp(pseudo_id, 'g');
    return content.replace(regex, id);
}

async function depseudonymizeZip(content, pseudo_id, id) {
    // function to replace the pseudo_id by id everywhere and return a new zip
    // Create a new JSZip instance for the modified files
    const newZip = new JSZip();
    // Iterate over all files
    for (const originalFilename in content.files) {
        if (Object.prototype.hasOwnProperty.call(content.files, originalFilename)) {
            const file = content.files[originalFilename];
            let fileContent = await file.async('string');
            // Modify the file content
            fileContent = replacePseudoIdByID(fileContent, pseudo_id, id);
            // Modify the filename/directory name if needed
            const newFilename = replacePseudoIdByID(originalFilename, pseudo_id, id);
            // Add the modified file / directory to the new zip archive
            newZip.file(newFilename, fileContent);
        }
    }
    return newZip;
}

function get_jwt_zip(id, pseudo_id, species, validation_type, res_time, get_zip, dtap, newWindow){
    // gets the html report from Azure through the API as a zip file, if it fails, returns a failure message
    query_url = "/reportsapi" + "/get_html_report?isolate_id=" + pseudo_id + '&date=' + res_time + "&species=" + species + "&get_zip=" + get_zip + "&dtap=" + dtap + "&validation_type=" + validation_type
    $.ajax( query_url , {
        method: 'GET',
        headers: {"x-access-token": localStorage.getItem('token')},
        cache:false,
        xhrFields:{
            responseType: 'blob'
        },
        success: async function(response) {
            // Create a Blob from the response
            const blob = new Blob([response], { type: 'application/zip' });

            // Convert Blob to ArrayBuffer and load content
            const arrayBuffer = await blob.arrayBuffer();
            const content = await JSZip.loadAsync(arrayBuffer);

            // Run the recursive zip depseudonymizer
            const newZip = await depseudonymizeZip(content, pseudo_id, id);

            // Generate the new zip file & download it
            const newZipContent = await newZip.generateAsync({ type: 'blob' });
            var blobUrl = newWindow.URL.createObjectURL(newZipContent);
            const anchor = newWindow.document.createElement('a');
            anchor.style.display = 'none';
            anchor.href = blobUrl;
            anchor.download = 'report_' + id + '_' + res_time + '_' + species + '.zip';
            anchor.click();
            newWindow.close(); //done to come back to original page
        },
        error:function(){
            var blob = new Blob(['Failure to retrieve the report. Please resubmit the request to start again or submit a ticket to bioit@sciensano if it still fails'], { type: 'text/html' });
            newWindow.location.href = URL.createObjectURL(blob);
        }
    });
}

function get_jwt_report (get_zip, validation_type_opt, id_opt, pseudo_id_opt, species_opt, date_opt){
    //  Logs in to the api and gets the html report either in zip format or in a new web page
    if (arguments.length === 1) {
        var title = document.title
        var validation_type = 'null'
        var id = title.replace(/^.*\(|\).*$/g, '');
        var pseudo_id = document.querySelector('body meta[name="pseudo_id"]').content; // query pseudo id from page which is put there by the IsolateInfoPage.pm
        var species = title.replace(/^.*- /g, '').replace(' isolates', '').toLowerCase();
        var date = 'null';
    } else {
        var validation_type = validation_type_opt
        var id = id_opt
        var pseudo_id = pseudo_id_opt
        var species = species_opt
        var date = date_opt
    }
    var dtap = window.location.hostname.match(/-(\w+)\./)?.[1] || null;
    console.log(id);
    console.log(pseudo_id)
    console.log(species);
    console.log(dtap);

    const dt = document.querySelectorAll("dt");
    const dd = document.querySelectorAll("dd");
    //start the loading screen as we have now all the elements needed to start querying the api
    var newWindow = window.open('',  '_blank');
    newWindow.document.cookie = "global_bigsdb_users_auth=" + getCookieValue('global_bigsdb_users_auth') + ";"
    var gifUrl = '/images/static/loading_icon.gif';
    // Construct the HTML content with the loading message and GIF
    var htmlContent = `
      <div style="text-align: center; padding: 20px;">
        <p style="font-size: 20px;">Retrieving your report, please wait...</p>
        <img src="${gifUrl}" alt="Loading..."/>
        <p style="font-size: 15px;">(This may take a while)</p>
      </div>
    `;
    newWindow.document.write(htmlContent);
    // var blob = new Blob([loadingMessage], { type: 'text/html' });
    // newWindow.location.href = URL.createObjectURL(blob);
    dt.forEach((el, index) => {
        if (el.textContent.includes("latest analysis date") === true) {
             console.log(dd[index].textContent);
             date = dd[index].textContent;
        }
    })

     $.ajax({
        url: "/reportsapi" + '/login',
        type: 'post',
        data: {
            "email": "bioit@sciensano.be",
            "password": getCookieValue('global_bigsdb_users_auth')
        },
        headers: {
            "Access-Control-Allow-Origin": "http://127.0.0.1:5000/login",
        },
        success: function (data) {
            // console.log(data)
            localStorage.setItem('token', data.token);
        },
        complete: function(){
            if(get_zip === 'yes'){
                get_jwt_zip(id, pseudo_id, species, validation_type, date, get_zip, dtap, newWindow)
            }else{
                 get_jwt_preview(id, pseudo_id, species, validation_type, date, get_zip, dtap, newWindow)
            }
        },
        dataType: 'json'
    });

}

function get_subpart(rel_file_path){
    // after a html report has been generated in a new browser page, this function is used to access subfiles such as alignments or the vcf
    var pseudo_id = document.querySelector('body meta[name="pseudo_id"]').content;
    query_url = "/reportsapi" + "/get_file?file_path=" + rel_file_path.replaceAll(document.title, pseudo_id)
    var file_extension = rel_file_path.split('.').pop();
    $.ajax( query_url , {
        method: 'GET',
        headers: {"x-access-token": localStorage.getItem('token')},
        contentType: "octet/stream",
        xhrFields:{
            responseType: ''
        },
        success:function(response){
            var wnd = window.open("about:blank");
            if(file_extension === 'html'){
                wnd.document.write(response.replaceAll(pseudo_id, document.title));
                wnd.document.close();
            }else{
                wnd.document.write("<textarea disabled rows=100 cols=100>", response.replaceAll(pseudo_id, document.title), "</textarea>");
            }

            },
        error:function(){
            document.write('Failure to retrieve the document. Please resubmit the request to start again or submit a ticket to bioit@sciensano if it still fails')
        }
    });
}

function get_jwt_subpart(rel_file_path){
    // wrapper with login ability around the get_subpart function
    $.ajax({
        url: "/reportsapi" + "/login",
        type: 'post',
        data: {
            "email": "bioit@sciensano.be",
            "password": getCookieValue('global_bigsdb_users_auth')
        },
        headers: {
            "Access-Control-Allow-Origin": "http://127.0.0.1:5000/login",
        },
        success: function (data) {
            // console.log(data)
            localStorage.setItem('token', data.token);
        },
        complete: function(){
               get_subpart(rel_file_path)

        },
        dataType: 'json'
    });
}