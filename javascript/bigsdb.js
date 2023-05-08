/**
 * Written by Keith Jolley 
 * Copyright (c) 2010-2021, University of Oxford 
 * E-mail: keith.jolley@zoo.ox.ac.uk
 * 
 * This file is part of Bacterial Isolate Genome Sequence Database (BIGSdb).
 * 
 * BIGSdb is free software: you can redistribute it and/or modify it under the
 * terms of the GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later
 * version.
 * 
 * BIGSdb is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
 * A PARTICULAR PURPOSE. See the GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License along with
 * BIGSdb. If not, see <http://www.gnu.org/licenses/>.
 */

$(function () {
	$('div.content a:not(.lightbox)').tooltip({ 
	    track: false, 
	    show: {delay: 250}, 
	    showURL: false, 
	    showBody: " - ", 
	    fade: 250 
	});
	$('.showhide').show();
	$("#hidefromnonJS").removeClass("hiddenbydefault");
	$(".hideonload").slideUp("normal");
	$('.hideshow').hide();
	$('#toggle1,#toggle2').click(function(){
      $('.showhide').toggle();
      $('.hideshow').toggle();
    });	
	$('.flash_message').effect('highlight',{},2000).hide('fade',{},1000);
	
	$('a#toggle_tooltips,span#toggle').show();
	$('a#toggle_tooltips').click(function(event){		
		event.preventDefault();
		if ($('a#toggle_tooltips').hasClass('tooltips_enabled')){
			$('a#toggle_tooltips').removeClass('tooltips_enabled');
			$('a#toggle_tooltips').addClass('tooltips_disabled');
			$('a#toggle_tooltips').prop('title','Enable tooltips');
		} else {
			$('a#toggle_tooltips').removeClass('tooltips_disabled');
			$('a#toggle_tooltips').addClass('tooltips_enabled');
			$('a#toggle_tooltips').prop('title','Disable tooltips');
		}
		$('.tooltip').toggle();
	  	$(this).attr('href', function(){  		
	  		$.ajax({
	  			url: this.href,
	  			cache: false,
	  		});
	   	});
	});

	show_expand_trigger();
	$('a#expand_trigger').click(function(event){
		if ($('span#expand').is(":visible")){
			$('div.main_content').css({"max-width":"calc(100vw - 40px)"});
			$('span#expand').hide();
			$('span#contract').show();
		} else {
			$('div.main_content').css({"max-width":max_width + 'px'});
			$('span#expand').show();
			$('span#contract').hide();
		}
	});
	
	
	//Tooltips
	reloadTooltips();
	$('a#toggle_tooltips').prop('title',$('a#toggle_tooltips')
			.hasClass('tooltips_enabled') ? 'Disable tooltips' : 'Enable tooltips');
	
	//Add tooltip to truncated definition list titles
	$('dt').each(function(){
		if( this.offsetWidth + 1 < this.scrollWidth){
			$(this).prop('title', $(this).text());
			$(this).tooltip();
			$(this).css('cursor', 'pointer');
		}
	});
	$(window).resize(function() {
		show_expand_trigger();
	});
	
});

$.urlParam = function(name){
    var results = new RegExp('[\?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (results==null){
       return null;
    }
    else{
       return results[1] || 0;
    }
}

function show_expand_trigger() {
	if ($(window).width() > max_width + 100){
		$("a#expand_trigger").show();
	} else {
		$('a#expand_trigger').hide();
	}
}

function reloadTooltips() {
	var title = $("a[title],span[title]" ).not('.lightbox');
	$.each(title, function(index, value) {
		var value = $(this).attr('title');
		value = value.replace(/^([^<h3>].+?) - /,"<h3>$1</h3>");
		$(this).tooltip({content: value});
	});
	title = $("label[title]" ).not('.lightbox');
	$.each(title, function(index, value) {
		var value = $(this).attr('title');
		$(this).tooltip({content: value});
	});
}
		
function getCookie(name) {
  var dc = document.cookie;
  var prefix = name + "=";
  var begin = dc.indexOf("; " + prefix);
  if (begin == -1) {
    begin = dc.indexOf(prefix);
    if (begin != 0) return null;
  } else
    begin += 2;
  var end = document.cookie.indexOf(";", begin);
  if (end == -1)
    end = dc.length;
  return unescape(dc.substring(begin + prefix.length, end));
}

//application for the api of HERA
function get_jwt_preview(id, species, res_time, get_zip){
    query_string = "http://127.0.0.1:5001/search?isolate_id=" + id + '&res_version=' + res_time +"&species=" + species + "&get_zip=" + get_zip
    $.ajax( query_string , {
        method: 'GET',
        headers: {"x-access-token": localStorage.getItem('token')},
        success:function(response){
            // console.log(response);
                document.open('/report');
                document.write(response);
           },
        error:function(){
        document.open('error')
        document.write('Failure to retrieve the report. Please refresh the page to start again or call BIOIT if it still fails')
    }
    });
}

function get_jwt_zip(id, species, res_time, get_zip){
    query_string = "http://127.0.0.1:5001/search?isolate_id=" + id + '&res_version=' + res_time +"&species=" + species + "&get_zip=" + get_zip
    $.ajax( query_string , {
        method: 'GET',
        headers: {"x-access-token": localStorage.getItem('token')},
        cache:false,
        xhrFields:{
            responseType: 'blob'
        },
        success:function(response) {
            filename = 'report_' + id +'_' + res_time + '_' + species +'.zip'
            var blobUrl = window.URL.createObjectURL(response);
            const anchor = document.createElement('a');
            anchor.style.display = 'none';
            anchor.href = blobUrl;
            anchor.download = filename;
            anchor.click();
            location.reload() //done to come back to original page
        },
        error:function(){
            document.open('error')
            document.write('Failure to retrieve the report. Please refresh the page to start again or call BIOIT if it still fails')
        }
    });
}

function get_jwt_report (get_zip){
    var title = document.title
    var id = title.replace(/^.*\(|\).*$/g, '');
    var species = title.replace(/^.*- /g, '').replace(' isolates','').toLowerCase();
    var res_version = 'null'
    console.log(id)
    console.log(species)

    const dt = document.querySelectorAll("dt");
    const dd = document.querySelectorAll("dd");
    //start the loading screen as we have now all the elements needed to start querying the api
    document.write('Retrieving your report, please wait...')
    dt.forEach((el, index) => {
        if (el.textContent.includes("latest analysis date") === true) {
             console.log(el.textContent);
             console.log(dd[index].textContent);
             res_version = dd[index].textContent;
        }
    })

    $.ajax({
        url: 'http://127.0.0.1:5001/login',
        type: 'post',
        data: {
            "email": "test@test.com",
            "password": "1234"
        },
        headers: {
            "Access-Control-Allow-Origin": "http://127.0.0.1:5000/login",
        },
        success: function (data) {
            console.log(data)
            localStorage.setItem('token', data.token);
        },
        complete: function(){
            if(get_zip === 'yes'){
                get_jwt_zip(id, species, res_version, get_zip)
            }else{
                 get_jwt_preview(id, species, res_version, get_zip)
            }
        },
        dataType: 'json'
    });

}

function get_subpart(rel_file_path){
    query_string = "http://127.0.0.1:5001/get_file?file_path=" + rel_file_path
    var file_extension = rel_file_path.split('.').pop();
    $.ajax( query_string , {
        method: 'GET',
        headers: {"x-access-token": localStorage.getItem('token')},
        contentType: "octet/stream",
        xhrFields:{
            responseType: ''
        },
        success:function(response){
            console.log(response);
            document.open('/test')
            if(file_extension === 'html'){

                document.write(response)
            }else{
                document.write("<textarea disabled rows=100 cols=100>", response, "</textarea>")
            }

            },
        error:function(){
            document.write('Failure to retrieve the document. Please refresh the page to start again or call BIOIT if it still fails')
        }
    });
}

function get_jwt_subpart(rel_file_path){
       $.ajax({
        url: 'http://127.0.0.1:5001/login',
        type: 'post',
        data: {
            "email": "test@test.com",
            "password": "1234"
        },
        headers: {
            "Access-Control-Allow-Origin": "http://127.0.0.1:5000/login",
        },
        success: function (data) {
            console.log(data)
            localStorage.setItem('token', data.token);
        },
        complete: function(){
               get_subpart(rel_file_path)

        },
        dataType: 'json'
    });
}

