#Written by Keith Jolley
#Copyright (c) 2015-2022, University of Oxford
#E-mail: keith.jolley@zoo.ox.ac.uk
#
#This file is part of Bacterial Isolate Genome Sequence Database (BIGSdb).
#
#BIGSdb is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#BIGSdb is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with BIGSdb.  If not, see <http://www.gnu.org/licenses/>.
package BIGSdb::AlertPage;
use strict;
use warnings;
use 5.010;
use parent qw(BIGSdb::TreeViewPage BIGSdb::CurateProfileAddPage);
use Log::Log4perl qw(get_logger);
my $logger = get_logger('BIGSdb.Alerts');
use BIGSdb::Utils;
use BIGSdb::Constants qw(SEQ_METHODS :submissions :interface :design);
use List::MoreUtils qw(none);
use POSIX;
use JSON;
use constant LIMIT => 500;
use constant INF   => 9**99;

sub get_help_url {
	my ($self) = @_;
	my $q = $self->{'cgi'};
	if ( $q->param('curate') ) {
		return "$self->{'config'}->{'doclink'}/curate_submissions.html";
	} else {
		return "$self->{'config'}->{'doclink'}/submissions.html";
	}
}

sub get_javascript {
	my ($self) = @_;
	my $q = $self->{'cgi'};
	my $max         = $self->{'config'}->{'max_upload_size'} / ( 1024 * 1024 );
	my $max_files   = LIMIT;
	my $tree_js     = $self->get_tree_javascript( { checkboxes => 1, check_schemes => 1, submit_name => 'filter' } );
	my $submit_type = q();
	my $alert_id = $q->param('alert_id') // q();
	my $links         = $self->get_related_databases;
	my $db_trigger    = q();
	if ( @$links > 1 ) {
		$db_trigger = << "END";
+\$("#related_db_trigger,#close_related_db").click(function(){
		\$("#related_db_panel").toggle("slide",{direction:"right"},"fast");
		return false;
	});
END
	}
	my $buffer = << "END";
\$(function () {
	\$("fieldset#scheme_fieldset").css("display","block");
	\$("#filter").click(function() {
		var fields = ["technology", "assembly", "software", "read_length", "coverage", "locus", "fasta"];
		for (i=0; i<fields.length; i++){
			\$("#" + fields[i]).prop("required",false);
		}

	});
	\$("#technology").change(function() {
		check_technology();
	});
	check_technology();
	\$( "#show_closed" ).click(function() {
		if (\$("span#show_closed_text").css('display') == 'none'){
			\$("span#show_closed_text").css('display', 'inline');
			\$("span#hide_closed_text").css('display', 'none');
		} else {
			\$("span#show_closed_text").css('display', 'none');
			\$("span#hide_closed_text").css('display', 'inline');
		}
		\$( "#closed" ).toggle( 'blind', {} , 500 );
		return false;
	});
	\$("form#file_upload_form").dropzone({
		paramName: function() { return 'file_upload'; },
		parallelUploads: 6,
		maxFiles: $max_files,
		uploadMultiple: true,
		maxFilesize: $max,
		init: function () {
        	this.on('queuecomplete', function () {
         		if (this.getUploadingFiles().length === 0 && this.getQueuedFiles().length === 0) {
	         		var url = "$self->{'system'}->{'script_name'}?db=$self->{'instance'}&page=alert";
	         		if ('$submit_type'.length){
	         			url += "&$submit_type=1";
	         		} else if ('$alert_id'.length){
	         			url += "&alert_id=$alert_id";
	         		}
	             	location.href = url;
         		}
        	});
    	}
	});
	\$("form#file_upload_form").addClass("dropzone");
	$db_trigger
	resize_rmlst_cell();
});

function resize_rmlst_cell(){
	var width=0;
	\$(".rmlst_result").each(function( index ) {
		if (\$(this).width() > width){
			width = \$(this).width();
		}
	});
	\$(".rmlst_cell").css("min-width", width + 20 + "px");
}

function status_markall(status){
	\$("select[name^='status_']").val(status);
}

function check_technology() {
	var fields = [ "read_length", "coverage"];
	for (i=0; i<fields.length; i++){
		if (\$("#technology").val() == 'Illumina'){
			\$("#" + fields[i]).prop("required",true);
			\$("#" + fields[i] + "_label").text((fields[i]+":!").replace("_", " "));
		} else {
			\$("#" + fields[i]).prop("required",false);
			\$("#" + fields[i] + "_label").text((fields[i]+":").replace("_", " "));
		}
	}
}
$tree_js
END
	return $buffer;
}

sub initiate {
	my ($self)        = @_;
	my $q             = $self->{'cgi'};
	my $alert_id = $q->param('alert_id');
	if ( $q->param('tar') && $q->param('alert_id') ) {
		$self->{'type'}       = 'tar';
		$self->{'attachment'} = "$alert_id\.tar";
		$self->{'noCache'}    = 1;
		return;
	}
	$self->{$_} = 1 foreach qw (jQuery jQuery.jstree noCache tooltips dropzone);
	if ( $q->param('curate') ) {
		$self->set_level2_breadcrumbs('Curate alert');
	} else {
		$self->{'processing'} = 1 if defined $q->param('alert_id');
		foreach my $method (qw(abort finalize close remove cancel)) {
			if ( $q->param($method) ) {
				$self->{'processing'} = 0;
				last;
			}
		}
		$self->set_level1_breadcrumbs;
	}
	return;
}

sub print_content {
	my ($self) = @_;
#	if ( ( $self->{'system'}->{'submissions'} // '' ) ne 'yes' || !$self->{'config'}->{'submission_dir'} ) {
#		say q(<h1>Manage alerts</h1>);
#		$self->print_bad_status( { message => q(The alert system is not enabled.) } );
#		say q(<div style="position:relative;margin-top:-8em">);
#		$self->print_related_database_panel;
#		say q(</div>);
#		return;
#	}
	my $q = $self->{'cgi'};
	$self->choose_set;
	my $alert_id = $q->param('alert_id');
	if ($alert_id) {
		if ( $q->param('reopen') ) {
			$self->_reopen_alert($alert_id);
		}
		my %return_after = map { $_ => 1 } qw (view curate);
		my $action_performed;
		# i think this is the dispatch table ~MK 2024/01/11
		foreach my $action (qw (abort finalize close remove view curate cancel)) {
			if ( $q->param($action) ) {
				my $method = "_${action}_alert";
				$self->$method($alert_id);
				$action_performed = 1;
				return if $return_after{$action};
				last;
			}
		}
	}
	say q(<h1>Manage alerts</h1>);
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	if ( !$user_info ) {
		$self->print_bad_status( { message => q(You are not a recognized user. Alerts are disabled.) } );
		say q(<div style="position:relative;margin-top:-8em">);
		$self->print_related_database_panel;
		say q(</div>);
		return;
	}
	my $alerts_to_show = $self->_any_pending_alerts_to_show;
	my $closed_buffer =
	  $self->print_alerts_for_curation( { status => 'archived', show_outcome => 1, get_only => 1 } );
	if ($alerts_to_show) {
		say q(<div class="box resultstable"><div class="scrollable">);
		$self->_print_pending_alerts;
		$self->print_alerts_for_curation;
		$self->_print_archived_alerts;
		$self->print_navigation_bar( { closed_submissions => $closed_buffer ? 1 : 0 } );
		say q(</div></div>);
	}
	if ($closed_buffer) {
		say q(<div class="box resultstable" id="closed" style="display:none"><div class="scrollable">);
		say q(<h2>Archived alerts for which you had curator rights</h2>);
		say q(<p>The following alerts are now closed);
		say $closed_buffer;
		say q(</div></div>);
	}
	return;
}

sub _any_pending_alerts_to_show {
	my ($self) = @_;
	return 1 if $self->_get_own_alerts('pending');
	return 1 if $self->print_alerts_for_curation( { get_only => 1 } );
	return 1 if $self->_get_own_alerts('archived');
	return;
}

sub _get_alerts_by_status {
	my ( $self, $status, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	my ( $qry, $get_all, @args );
	if ( $options->{'get_all'} ) {
		$qry     = 'SELECT * FROM alerts WHERE status=? ORDER BY CAST(id AS INTEGER)';
		$get_all = 1;
		push @args, $status;
	} else {
		$qry     = 'SELECT * FROM alerts WHERE (submitter,status)=(?,?) ORDER BY CAST(id AS INTEGER)';
		$get_all = 0;
		push @args, ( $user_info->{'id'}, $status );
	}
	my $alerts =
	  $self->{'datastore'}->run_query( $qry, \@args,
		{ fetch => 'all_arrayref', slice => {}, cache => "AlertPage::get_alerts_by_status$get_all" } );
	return $alerts;
}

sub _get_own_alerts {
	my ( $self, $status, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	my $alerts = $self->_get_alerts_by_status( $status, { get_all => 0 } );
	my $buffer;
	if (@$alerts) {
		my $td     = 1;
		my $set_id = $self->get_set_id;
		my $table_buffer;
		foreach my $alert (@$alerts) {
			my $details = '';
			my $url = qq($self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;page=alert&amp;)
			  . qq(alert_id=$alert->{'id'}&amp;view=1);
			$table_buffer .=
			    qq(<tr class="td$td"><td><a href="$url">$alert->{'id'}</a></td>)
			  . qq(<td>$alert->{'date_submitted'}</td><td>$alert->{'datestamp'}</td>)
			  . qq(<td>$alert->{'type'}</td>);
			$table_buffer .= qq(<td>$details</td>);
			if ( $options->{'show_outcome'} ) {
				my %style = FACE_STYLE;
				$table_buffer .= qq(<td><span $style{$alert->{'outcome'}}></span></td>);
			}
=begin
			if ( $options->{'allow_remove'} ) {
				$table_buffer .=
				    qq(<td><a href="$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;)
				  . qq(page=alert&amp;alert_id=$alert->{'id'}&amp;remove=1">)
				  . q(<span class="fas fa-lg fa-times"></span></a></td>);
			}
=cut
			$table_buffer .= q(</tr>);
			$td = $td == 1 ? 2 : 1;
		}
		if ($table_buffer) {
			$buffer .= q(<table class="resultstable"><tr><th>Alert id</th><th>Submitted</th><th>Updated</th>)
			  . q(<th>Type</th><th>Details</th>);
			$buffer .= q(<th>Outcome</th>) if $options->{'show_outcome'};
			#$buffer .= q(<th>Remove</th>)  if $options->{'allow_remove'};
			$buffer .= q(</tr>);
			$buffer .= $table_buffer;
			$buffer .= q(</table>);
		}
	}
	return $buffer;
}

sub _print_pending_alerts {
	my ($self) = @_;
	my $buffer = $self->_get_own_alerts('pending');
	if ($buffer) {
		say q(<h2>Pending alerts</h2>);
		say q(<p>You have submitted the following alerts that are pending curation:</p>);
		say $buffer;
	}
	return;
}

sub print_alerts_for_curation {
	my ( $self, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
#	return if ( $self->{'system'}->{'submissions'} // '' ) ne 'yes';
#	return if !$self->{'config'}->{'submission_dir'};
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	return if !$user_info || ( $user_info->{'status'} ne 'admin' && $user_info->{'status'} ne 'curator' );
	my $buffer;
	$buffer .= $self->_get_alerts_for_curation($options);
	return $buffer if $options->{'get_only'};
	say $buffer if $buffer;
	return;
}

sub _get_alerts_for_curation {
	my ( $self, $options ) = @_;
	my $status = $options->{'status'} // 'pending';
	# return q() if !$self->can_modify_table('isolates'); # disable this so that all curators, regardless of their rights can validate new isolates, mk 23/10/18
	my $alerts = $self->_get_alerts_by_status( $status, { get_all => 1 } );
	my $buffer;
	my $td = 1;
	foreach my $item (@$alerts) {
		next if $item->{'type'} ne 'warning' && $item->{'type'} ne 'alert';
		$buffer .=
		    qq(<tr class="td$td"><td><a href="$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;)
		  . qq(page=alert&amp;alert_id=$item->{'id'}&amp;curate=1">$item->{'id'}</a></td>)
		  . qq(<td>$item->{'date_submitted'}</td>)
		  . qq(<td>$item->{'type'}</td>)
		  . qq(<td>$item->{'method'}</td>);
		if ( $status eq 'archived' ) {
			my %style = FACE_STYLE;
			$buffer .= qq(<td><span $style{$item->{'outcome'}}></span></td>);
		}
		$buffer .= qq(</tr>\n);
		$td = $td == 1 ? 2 : 1;
	}
	my $return_buffer = q();
	if ($buffer) {
		if ( $status eq 'archived' ) {
			$return_buffer .= q(<h3>Alerts</h3>);
		} else {
			$return_buffer .= qq(<h2>New alerts waiting for curation</h2>\n);
			$return_buffer .= qq(<p>Your account is authorized to handle the following alerts:<p>\n);
		}
		$return_buffer .= q(<table class="resultstable"><tr><th>Alert id</th><th>Triggered</th>)
		  . q(<th>Type</th><th>Method</th>);
		$return_buffer .= q(<th>Outcome</th>) if $status eq 'archived';
		$return_buffer .= qq(</tr>\n);
		$return_buffer .= $buffer;
		$return_buffer .= qq(</table>\n);
	}
	return $return_buffer;
}

sub _print_archived_alerts {
	my ($self) = @_;
	my $buffer = $self->_get_own_alerts( 'archived', { show_outcome => 1, allow_remove => 1 } );
	if ($buffer) {
		say q(<h2>Recently archived alerts</h2>);
		say q(<p>You have submitted the following alerts which are now archived);
		say $buffer;
	}
	return;
}

sub _abort_alert {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table, see also the line containing "_${action}_alert"
	my ( $self, $alert_id ) = @_;
	return if !$self->{'cgi'}->param('confirm');
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	my $alert =
	  $self->{'datastore'}
	  ->run_query( 'SELECT id FROM alerts WHERE (id,submitter)=(?,?)', [ $alert_id, $user_info->{'id'} ] );
	$self->{'submissionHandler'}->delete_alert($alert_id) if $alert_id;
	return;
}

sub _finalize_alert {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table, see also the line containing "_${action}_alert"
	my ( $self, $alert_id ) = @_;
	my $q          = $self->{'cgi'};
	my $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	return if !$alert || $alert->{'status'} ne 'started';
	$logger->info("$self->{'instance'}: New $alert->{'type'} alert");
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	eval {
		$self->{'db'}->do(
			'UPDATE alerts SET (status,datestamp,email)=(?,?,?) WHERE (id,submitter)=(?,?)',
			undef, 'pending', 'now', $q->param('email') // undef,
			$alert_id, $user_info->{'id'}
		);
	};
	if ($@) {
		$logger->error($@);
		$self->{'db'}->rollback;
	} else {
		$self->{'db'}->commit;
	}
	my $guid = $self->get_guid;
	return if !$guid;
	$self->{'prefstore'}
	  ->set_general( $guid, $self->{'system'}->{'db'}, 'submit_email', $q->param('email') ? 'on' : 'off' );
	$self->{'submissionHandler'}->notify_curators($alert_id);
	return;
}

sub _print_alert_table_fieldset {
	my ( $self, $alert_id, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	my $q          = $self->{'cgi'};
	my $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	return if !$alert;
	my $alert_details = $self->{'submissionHandler'}->get_alert_details($alert_id);
	return if !$alert_details;
	my $order    = $alert_details->{'order'};
	say q(<fieldset><legend>Warning/Alert</legend>);
	my $csv_icon = $self->get_file_icon('CSV');
	say $q->start_form;
	$self->_print_alert_table( $alert_id, $options );
	#$self->_print_update_button( { record_status => 1 } ) if $options->{'curate'};
	say $q->hidden($_) foreach qw(db page alert_id curate);
	say $q->end_form;
=begin
	if ( $options->{'curate'} && !$alert->{'outcome'} && !$self->{'contigs_missing'} ) {
		say $q->start_form( -action => $self->{'system'}->{'curate_script'} );
		say $q->submit( -name => 'Batch curate', -class => 'submit', -style => 'margin-top:0.5em' );
		my $page = $q->param('page');
		$q->param( page   => 'batchAdd' );
		$q->param( table  => 'alerts' );
		$q->param( submit => 1 );
		say $q->hidden($_) foreach qw(db page alert_id table submit);
		say $q->end_form;

		#Restore value
		$q->param( page => $page );
	}
=cut
	say q(</fieldset>);
	say q(<div id="dialog"></div>);
	$self->{'all_assigned_or_archived'} = $alert->{'outcome'} ? 1 : 0;
	return;
}

sub _get_outcome {
	my ( $self,         $args )         = @_;
	my ( $all_assigned, $all_archived ) = @{$args}{qw(all_assigned all_archived)};
	if ($all_assigned) {
		return 'good';
	} elsif ($all_archived) {
		return 'bad';
	}
	return 'mixed';
}

sub _print_alert_table {
	my ( $self, $alert_id, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	my $q                  = $self->{'cgi'};
	my $alert = $self->{'submissionHandler'}->get_alert_details($alert_id);
	my $alert_details           = $alert->{'alert_details'};
	my $fields =
	  $self->{'submissionHandler'}
	  ->get_populated_fields( $alert->{'alert_details'}, $alert->{'order'} );
	my $max_width = $self->{'config'}->{'page_max_width'} // PAGE_MAX_WIDTH;
	my $main_max_width = $max_width - 100;
	say qq(<div style="max-width:min(${main_max_width}px, 100vw - 100px)"><div class="scrollable">)
	  . q(<table class="resultstable" style="margin-bottom:0"><tr>);
	say qq(<th>$_</th>) foreach @$fields;
	say q(</tr>);
	my $td = 1;
	local $" = q(</td><td>);
	my $index = 0;

	foreach my $alert_detail (@$alert_details) {
		$index++;
		my @values;
		foreach my $field (@$fields) {
			push @values, $alert_detail->{$field} // q();
		}
		say qq(<tr class="td$td"><td>@values</td>);
		say q(</tr>);
		$td = $td == 1 ? 2 : 1;
	}
	say q(</table></div></div>);
	return;
}

#sub _print_update_button {
#	my ( $self, $options ) = @_;
#	$options = {} if ref $options ne 'HASH';
#	my $q = $self->{'cgi'};
#	say q(<div style="float:right">);
#	if ( $options->{'mark_all'} ) {
#		say q(<span style="margin-right:1em">)
#		  . q(Mark all: <input type="button" onclick='status_markall("pending")' )
#		  . q(value="Pending" class="small_reset" /><input type="button" )
#		  . q(onclick='status_markall("archived")' value="archived" class="small_reset" />)
#		  . q(</span>);
#	}
#	if ( $options->{'record_status'} ) {
#		say q(<label for="record_status">Record status:</label>);
#		say $q->popup_menu(
#			-name  => 'record_status',
#			id     => 'record_status',
#			# values => [qw(pending accepted archived)]
#			values => [qw(pending archived)]
#		);
#	}
#	say $q->submit( -name => 'update', -label => 'Update', -class => 'small_submit' );
#	say q(</div>);
#	return;
#}

sub _print_close_alert_fieldset {
	my ( $self, $alert_id ) = @_;
	my $q = $self->{'cgi'};
	say $q->start_form;
	$q->param( close => 1 );
	say $q->hidden($_) foreach qw( db page alert_id close );
	$self->print_action_fieldset( { no_reset => 1, submit_label => 'Archive alert' } );
        say $q->end_form;
	return;
}

=begin
sub _print_reopen_alert_fieldset {
	my ( $self, $alert_id ) = @_;
	my $q = $self->{'cgi'};
	say $q->start_form;
	$q->param( reopen => 1 );
	say $q->hidden($_) foreach qw( db page alert_id reopen curate);
	$self->print_action_fieldset( { no_reset => 1, submit_label => 'Re-open alert' } );
	say $q->end_form;
	return;
}
=cut

sub _print_summary {
	my ( $self, $alert_id ) = @_;
	my $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	say q(<fieldset style="float:left"><legend>Summary</legend>);
	say qq(<dl class="data"><dt>type</dt><dd>$alert->{'type'}</dd>);
	my $user_string =
	  $self->{'datastore'}->get_user_string( $alert->{'submitter'}, { email => 1, affiliation => 1 } );
	say qq(<dt>submitter</dt><dd>$user_string</dd>);
	say qq(<dt>datestamp</dt><dd>$alert->{'datestamp'}</dd>);
	say qq(<dt>status</dt><dd>$alert->{'status'}</dd>);
	my %outcome = (
		good  => 'accepted - data uploaded',
		bad   => 'archived - data not uploaded',
		mixed => 'mixed - alert partially accepted'
	);
	say qq(<dt>outcome</dt><dd>$outcome{$alert->{'outcome'}}</dd>) if $alert->{'outcome'};

	if ( defined $alert->{'curator'} ) {
		my $curator_string =
		  $self->{'datastore'}->get_user_string( $alert->{'curator'}, { email => 1, affiliation => 1 } );
		say qq(<dt>curator</dt><dd>$curator_string</dd>);
	}
	say q(</dl></fieldset>);
	return;
}

#Check alert exists and curator has appropriate permissions.
sub _is_alert_valid {
	my ( $self, $alert_id, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	if ( !$alert_id ) {
		$self->print_bad_status( { message => q(No alert id passed.) } ) if !$options->{'no_message'};
		return;
	}
	my $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	if ( !$alert ) {
		$self->print_bad_status( { message => qq(Alert '$alert_id' does not exist.) } )
		  if !$options->{'no_message'};
		return;
	}
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	if ( $options->{'curate'} ) {
		if ( !$user_info || ( $user_info->{'status'} ne 'admin' && $user_info->{'status'} ne 'curator' ) ) {
			$self->print_bad_status(
				{
					message => q(Your account does not have the required permissions to curate this alert.)
				}
			) if !$options->{'no_message'};
			return;
		}
	}
	if ( $options->{'user_owns'} ) {
		return if $alert->{'submitter'} != $user_info->{'id'};
	}
	return 1;
}

sub set_level2_breadcrumbs {
	my ( $self, $page ) = @_;
	$self->{'breadcrumbs'} = [
		{
			label => $self->{'system'}->{'webroot_label'} // 'Organism',
			href => $self->{'system'}->{'webroot'}
		},
		{
			label => $self->{'system'}->{'formatted_description'} // $self->{'system'}->{'description'},
			href => "$self->{'system'}->{'script_name'}?db=$self->{'instance'}"
		},
		{
			label => 'Alerts',
			href  => "$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;page=alert"
		},
		{
			label => $page
		}
	];
	return;
}

sub _curate_alert {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table, see also the line containing "_${action}_alert"
	my ( $self, $alert_id ) = @_;
	my $q = $self->{'cgi'};
	say q(<h1>Curate alert</h1>);
	return if !$self->_is_alert_valid( $alert_id, { curate => 1 } );
	my $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	my $curate     = 1;
	if ( $alert->{'status'} eq 'archived' ) {
		$self->print_bad_status( { message => q(This alert is archived and cannot now be modified.) } );
		$curate = 0;
	}
	say q(<div class="box" id="resultstable">);
	say qq(<h2 style="overflow-x:auto;overflow-y:hidden">Alert: $alert_id</h2>);
	$self->_print_summary($alert_id);
	say q(<div style="clear:both"></div>);
	say q(<div class="flex_container" style="justify-content:left">);
	$self->_print_alert_table_fieldset( $alert_id, { curate => $curate } );

	if ($curate) {
		$self->_print_close_alert_fieldset($alert_id);
	} else {
		$self->_print_reopen_alert_fieldset($alert_id);
	}
	say q(<div style="clear:both"></div>);
	my $page = $self->{'curate'} ? 'index' : 'submit';
	say q(</div></div>);
	return;
}

sub _view_alert {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table, see also the line containing "_${action}_alert"
	my ( $self, $alert_id ) = @_;
	my $q = $self->{'cgi'};
	say q(<h1>Alert summary</h1>);
	return if !$self->_is_alert_valid($alert_id);
	my $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	say q(<div class="box" id="resultstable">);
	say qq(<h2 style="overflow-x:auto">Alert: $alert_id</h2>);
	$self->_print_summary($alert_id);
	say q(<div style="clear:both"></div>);
	say q(<div class="flex_container" style="justify-content:left">);
	$self->_print_alert_table_fieldset($alert_id);
	say q(</div></div>);
	return;
}

sub _close_alert {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table, see also the line containing "_${action}_alert"
	my ( $self, $alert_id ) = @_;
	return if !$self->_is_alert_valid( $alert_id, { curate => 1, no_message => 1 } );
	my $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	return if !$alert || $alert->{'status'} eq 'archived';    #Prevent refresh from re-sending E-mail
	my $curator_id = $self->get_curator_id;
        eval {
		$self->{'db'}->do( 'UPDATE alerts SET (status,datestamp,curator)=(?,?,?) WHERE id=?',
			undef, 'archived', 'now', $curator_id, $alert_id );
	};
	if ($@) {
		$logger->error($@);
		$self->{'db'}->rollback;
	} else {
		$self->{'db'}->commit;
	}
        my $dbname = $self->{'datastore'}->run_query('select current_database()');
#        open(BASH, "|-", "bash");
#        print BASH "/home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9 /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/sample_validation_to_mongo.py --db $dbname --sub_id $alert_id \n";
#        close(BASH);
        $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	my $curator_info = $self->{'datastore'}->get_user_info($curator_id);
	if ( $alert->{'email'} ) {
		my $desc = $self->{'system'}->{'description'} || 'BIGSdb';
		$self->{'submissionHandler'}->email(
			$alert_id,
			{
				recipient => $alert->{'submitter'},
				sender    => $curator_id,
				subject   => "$desc alert closed - $alert_id",
				message   => $self->{'submissionHandler'}
				  ->get_text_summary( $alert_id, { messages => 1, correspondence_first => 1 } ),
				cc_sender => $curator_info->{'submission_email_cc'}
			}
		);
	}
	return;
}

=begin
sub _remove_alert {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table, see also the line containing "_${action}_alert"
	my ( $self, $alert_id ) = @_;
	return if !$self->_is_alert_valid( $alert_id, { no_message => 1, user_owns => 1 } );
	$self->{'submissionHandler'}->delete_alert($alert_id);
	return;
}
=cut

sub _cancel_alert {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table, see also the line containing "_${action}_alert"
	my ( $self, $alert_id ) = @_;
	return if !$self->_is_alert_valid( $alert_id, { no_message => 1, user_owns => 1 } );
	my $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	return if $alert->{'status'} ne 'pending';
	my $curators = $self->{'submissionHandler'}->_get_curators($alert_id);
	my $desc     = $self->{'system'}->{'description'} || 'BIGSdb';
	my $subject  = "CANCELLED $alert->{'type'} alert ($desc) - $alert_id";
	my $message  = "This alert has been CANCELLED by the submitter.\n\n";
	$message .= $self->{'submissionHandler'}->get_text_summary( $alert_id, { messages => 1 } );
	$logger->info("$self->{'instance'}: Alert cancelled.");
	$self->{'submissionHandler'}->remove_submission_from_digest($alert_id);

	foreach my $curator_id (@$curators) {
		my $user_info = $self->{'datastore'}->get_user_info($curator_id);
		next if $user_info->{'submission_digests'};
		next if !$self->{'submissionHandler'}->can_email_curator($curator_id);
		$self->{'submissionHandler'}->email(
			$alert_id,
			{
				recipient => $curator_id,
				sender    => $alert->{'submitter'},
				subject   => $subject,
				message   => $message,
			}
		);
		$self->{'submissionHandler'}->write_flood_protection_file($curator_id);
	}
	$self->{'submissionHandler'}->delete_alert($alert_id);
	return;
}

sub _reopen_alert {
	my ( $self, $alert_id ) = @_;
	return if !$self->_is_alert_valid( $alert_id, { no_message => 1, curate => 1 } );
	my $alert = $self->{'submissionHandler'}->get_alert($alert_id);
	return if $alert->{'status'} ne 'archived';
	my $curator_id = $self->get_curator_id;
	my $message    = 'Alert re-opened.';
	eval {
		$self->{'db'}->do( 'UPDATE alerts SET (status,datestamp,curator)=(?,?,?) WHERE id=?',
			undef, 'pending', 'now', $curator_id, $alert_id );
		$self->{'submissionHandler'}->update_alert_datestamp($alert_id);
		$self->{'db'}->do( 'INSERT INTO messages (alert_id,timestamp,user_id,message) VALUES (?,?,?,?)',
			undef, $alert_id, 'now', $curator_id, $message );
	};
	if ($@) {
		$logger->error($@);
		$self->{'db'}->rollback;
	} else {
		$self->{'db'}->commit;
		$self->{'submissionHandler'}->append_message( $alert_id, $curator_id, $message );
	}
	return;
}

sub set_pref_requirements {
	my ($self) = @_;
	$self->{'pref_requirements'} =
	  { general => 1, main_display => 0, isolate_display => 0, analysis => 0, query_field => 0 };
	return;
}

sub get_title {
	my ($self) = @_;
	return 'Alerts';
}

sub print_panel_buttons {
	my ($self) = @_;
	$self->print_related_dbases_button;
	return;
}
1;
