#Written by Keith Jolley
#Copyright (c) 2015-2025, University of Oxford
#E-mail: keith.jolley@biology.ox.ac.uk
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
package BIGSdb::ValidationPage;
use strict;
use warnings;
use 5.010;
use parent qw(BIGSdb::TreeViewPage BIGSdb::CurateProfileAddPage);
use Log::Log4perl qw(get_logger);
my $logger = get_logger('BIGSdb.Submissions');
use Data::Dumper;
use BIGSdb::Utils;
use BIGSdb::Constants qw(SEQ_METHODS :submissions :interface :design);
use List::MoreUtils qw(none);
use POSIX;
use JSON;
use constant LIMIT       => 500;
use constant INF         => 9**99;
use constant MIN_EMBARGO => 3;
use BIGSdb::UI::IsolateSubmissionsTable;

sub get_help_url {
	my ($self) = @_;
	my $q = $self->{'cgi'};
	if ( $q->param('curate') ) {
		return "$self->{'config'}->{'doclink'}/curate_submissions.html";
	} else {
		return "$self->{'config'}->{'doclink'}/submissions.html";
	}
}

sub get_submission_days {
	my ($self) = @_;
	my $days = $self->{'system'}->{'submissions_deleted_days'} // $self->{'config'}->{'submissions_deleted_days'}
	  // SUBMISSIONS_DELETED_DAYS;
	$days = SUBMISSIONS_DELETED_DAYS if !BIGSdb::Utils::is_int($days);
	return $days;
}

sub get_javascript {
    $logger->error('use get_javascript');
	my ($self)      = @_;
	my $q           = $self->{'cgi'};
	my $max         = $self->{'config'}->{'max_upload_size'} / ( 1024 * 1024 );
	my $max_files   = LIMIT;
	my $tree_js     = $self->get_tree_javascript( { checkboxes => 1, check_schemes => 1, submit_name => 'filter' } );
	my $submit_type = q();
	foreach my $type (qw(isolates genomes assemblies alleles profiles)) {
		if ( $q->param($type) ) {
			$submit_type = $type;
			last;
		}
	}
	my $submission_id = $q->param('submission_id') // q();
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
	         		var url = "$self->{'system'}->{'script_name'}?db=$self->{'instance'}&page=submit";
	         		if ('$submit_type'.length){
	         			url += "&$submit_type=1";
	         		} else if ('$submission_id'.length){
	         			url += "&submission_id=$submission_id";
	         		}
	             	location.href = url;
         		}
        	});
    	}
	});
	//Note that bigsdb.min,js contains a click event for the expand trigger. This also relies on the
	//visibility of span#expand. The below should always run first because bigsdb.min.js is loaded
	//with 'defer'.
	\$('a#expand_trigger').click(function(event) {
		event.preventDefault();
		let expand = \$('span#expand').is(":visible");
		let max_width_term = expand ? "calc(100vw - 100px)" : "min(" + (max_width - 100) + "px, 100vw - 100px)";
		\$("div#isolate_table,div#profile_table").css("max-width",max_width_term);
	});
	\$("form#file_upload_form").addClass("dropzone");
	$db_trigger
	resize_rmlst_cell();
	\$('#locus').multiselect({
	  	classes: 'filter',
	 	menuHeight: 250,
	 	menuWidth: 400,
	 	noneSelectedText: '',
	 	selectedList: 1,
	  }).multiselectfilter();
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
    $logger->error(Dumper($q));
	$self->{$_} = 1 foreach qw (jQuery jQuery.jstree noCache tooltips dropzone allowExpand jQuery.multiselect);

    $logger->error('😵😵');

    if ( $q->param('bulk_status')) {
        ## TODO 🍟🍟 Duplicate stuffs
        $logger->error('hey ho ouille aieaieaie 🙋‍♂️');
        $logger->error(Dumper($q));
        # Processing batch update
        my @selected_submissions = $q->param('selected_submissions[]');
        my %outcome = ( accepted => 'good', rejected => 'bad' );

        foreach my $submission_id (@selected_submissions) {
            next if none { $_ eq $q->param('bulk_status') } keys %outcome;
            $self->{'submissionHandler'}->update_submission_outcome( $submission_id, $outcome{ $q->param('bulk_status') } );
        }
    }

	if ( $q->param('curate') ) {
		$self->set_level2_breadcrumbs('Curate submission');
	} elsif ($q->param('isolate')) {
		$self->set_level2_breadcrumbs('New submission');
	} else {
		$self->{'processing'} = 1 if defined $q->param('submission_id');
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
	if ( ( $self->{'system'}->{'submissions'} // '' ) ne 'yes' || !$self->{'config'}->{'submission_dir'} ) {
		say q(<h1>Manage submissions</h1>);
		$self->print_bad_status( { message => q(The submission system is not enabled.) } );
		say q(<div style="position:relative;margin-top:-8em">);
		$self->print_related_database_panel;
		say q(</div>);
		return;
	}
	my $q = $self->{'cgi'};

	# Handle bulk status update
	if ($q->param('bulk_status')) {
        ## TODO 🍟🍟 Duplicate stuffs
        $logger->error('I got a bulk_status !✅✅✅');
		$self->_update_bulk_submission_status();
	}

	$self->choose_set;

	say q(<h1>Manage submissions</h1>);
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	if ( !$user_info ) {
		$self->print_bad_status( { message => q(You are not a recognized user. Submissions are disabled.) } );
		say q(<div style="position:relative;margin-top:-8em">);
		$self->print_related_database_panel;
		say q(</div>);
		return;
	}
	foreach my $type (qw (alleles profiles isolates genomes assemblies)) {
		if ( $q->param($type) ) {
			last if $self->_user_over_quota;
			my $method = "_handle_$type";
			$self->$method;
			return;
		}
	}
	my $submissions_to_show = $self->_any_pending_submissions_to_show;
	$self->_delete_old_submissions;
	my $closed_buffer =
	  $self->print_submissions_for_curation( { status => 'closed', show_outcome => 1, get_only => 1 } );
	if ( !$self->_print_started_submissions ) {    #Returns true if submissions in process
		say q(<div class="box" id="resultspanel"><div class="scrollable">);
#		$self->_print_new_submission_links;
		if ( !$submissions_to_show ) {
			$self->print_navigation_bar( { closed_submissions => $closed_buffer ? 1 : 0 } );
		}
        #ca passe ici
		say q(</div>);
		$self->print_related_database_panel;
		say q(</div>);
	}
	if ($submissions_to_show) {
		say q(<div class="box resultstable">);
		$self->_print_pending_submissions;
		$self->print_submissions_for_curation;
		$self->print_navigation_bar( { closed_submissions => $closed_buffer ? 1 : 0 } );
		say q(</div>);
	}
	if ($closed_buffer) {
		say q(<div class="box resultstable" id="closed" style="display:none"><div class="scrollable">);
		say q(<h2>Closed submissions for which you had curator rights</h2>);
		my $days = $self->get_submission_days;
		say q(<p>The following submissions are now closed);
		#  . qq(for $days days.);
		say $closed_buffer;
		say q(</div></div>);
	}
	return;
}

sub _any_pending_submissions_to_show {
	my ($self) = @_;
	return 1 if $self->_get_own_submissions('pending');
	return 1 if $self->print_submissions_for_curation( { get_only => 1 } );
	return 1 if $self->_get_own_submissions('closed');
	return;
}

sub _user_over_quota {
	my ($self) = @_;
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	my $total_limit =
	  BIGSdb::Utils::is_int( $self->{'system'}->{'total_pending_submissions'} )
	  ? $self->{'system'}->{'total_pending_submissions'}
	  : TOTAL_PENDING_LIMIT;
	my $total_pending =
	  $self->{'datastore'}->run_query(
		'SELECT COUNT(*) FROM submissions WHERE (submitter,status)=(?,?) AND (dataset IS NULL OR dataset = ?)',
		[ $user_info->{'id'}, 'pending', $self->{'instance'} ] );
	if ( $total_pending >= $total_limit ) {
		$self->print_bad_status(
			{
				message => q(Your account has too many pending submissions. )
				  . q(You will not be able to submit any more until these have been curated.)
			}
		);
		return 1;
	}
	my $daily_limit =
	  BIGSdb::Utils::is_int( $self->{'system'}->{'daily_pending_submissions'} )
	  ? $self->{'system'}->{'daily_pending_submissions'}
	  : DAILY_PENDING_LIMIT;
	my $daily_pending = $self->{'datastore'}->run_query(
		'SELECT COUNT(*) FROM submissions WHERE (submitter,status,date_submitted)=(?,?,?) '
		  . 'AND (dataset IS NULL OR dataset = ?)',
		[ $user_info->{'id'}, 'pending', 'now', $self->{'instance'} ]
	);
	if ( $daily_pending >= $daily_limit ) {
		$self->print_bad_status(
			{
					message => q(Your account has too many pending submissions )
				  . q(submitted today. You will not be able to submit any more until either tomorrow or )
				  . q(when these have been curated.)
			}
		);
		return 1;
	}
	return;
}

sub _handle_alleles {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ($self) = @_;
	my $q = $self->{'cgi'};
	if ( $self->{'system'}->{'dbtype'} ne 'sequences' ) {
		$self->print_bad_status(
			{
				message => q(You cannot submit new allele sequences for definition in an isolate database.)
			}
		);
		return;
	}
	if ( $q->param('submit') ) {
		$self->_update_allele_prefs;
	}
	$self->_submit_alleles;
	return;
}

sub _handle_profiles {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ($self) = @_;
	my $q = $self->{'cgi'};
	if ( $self->{'system'}->{'dbtype'} ne 'sequences' ) {
		$self->print_bad_status(
			{
				message => q(You cannot submit new profiles for definition in an isolate database.)
			}
		);
		return;
	}
	$self->_submit_profiles;
	return;
}

sub _handle_isolates {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ($self) = @_;
	my $q = $self->{'cgi'};
	if ( $self->{'system'}->{'dbtype'} ne 'isolates' ) {
		$self->print_bad_status(
			{
				message => q(You cannot submit new isolates to a sequence definition database.)
			}
		);
		return;
	}
	$self->_submit_isolates;
	return;
}

sub _handle_genomes {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ($self) = @_;
	my $q = $self->{'cgi'};
	if ( $self->{'system'}->{'dbtype'} ne 'isolates' ) {
		$self->print_bad_status(
			{
				message => q(You cannot submit new genomes to a sequence definition database.)
			}
		);
		return;
	}
	$self->_submit_isolates( { genomes => 1 } );
	return;
}

sub _delete_old_submissions {
	my ($self) = @_;
	my $days = $self->get_submission_days;
	my $submissions =
	  $self->{'datastore'}->run_query(
		qq(SELECT id FROM submissions WHERE status IN ('closed','started') AND datestamp<now()-interval '$days days'),
		undef, { fetch => 'col_arrayref' } );
	foreach my $submission_id (@$submissions) {
		$self->{'submissionHandler'}->delete_submission($submission_id);
	}
	return;
}

sub _get_submissions_by_status {
	my ( $self, $status, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	my ( $qry, $get_all, @args );
	if ( $options->{'get_all'} ) {
		$qry     = 'SELECT * FROM submissions WHERE status=? AND (dataset IS NULL OR dataset = ?) ORDER BY id';
		$get_all = 1;
		push @args, ( $status, $self->{'instance'} );
	} else {
		$qry =
		  'SELECT * FROM submissions WHERE (submitter,status)=(?,?) AND (dataset IS NULL OR dataset = ?) ORDER BY id';
		$get_all = 0;
		push @args, ( $user_info->{'id'}, $status, $self->{'instance'} );
	}
	my $submissions =
	  $self->{'datastore'}->run_query( $qry, \@args,
		{ fetch => 'all_arrayref', slice => {}, cache => "SubmitPage::get_submissions_by_status$get_all" } );
	return $submissions;
}

sub _get_submissions {
	my ( $self, $submission_ids ) = @_;
	return [] if !$submission_ids || ref $submission_ids ne 'ARRAY' || !@$submission_ids;

	my $placeholders = join( ',', ('?') x @$submission_ids );
	my $qry = "SELECT * FROM submissions WHERE id IN ($placeholders) AND (dataset IS NULL OR dataset = ?) ORDER BY id";
	my @args = ( @$submission_ids, $self->{'instance'} );

	my $submissions =
	  $self->{'datastore'}->run_query( $qry, \@args,
		{ fetch => 'all_arrayref', slice => {}, cache => "SubmitPage::get_submissions_by_ids" } );
	return $submissions;
}

sub _print_started_submissions {
	my ($self) = @_;
	my $incomplete = $self->_get_submissions_by_status('started');
	if (@$incomplete) {
		say q(<div class="box" id="resultspanel"><div class="scrollable">);
		say q(<h2>Submission in process</h2>);
		say q(<p>Please note that you must either proceed with or abort the in process submission before you can )
		  . q(start another.</p>);
		foreach my $submission (@$incomplete) { #There should only be one but this isn't enforced at the database level.
			say qq(<dl class="data"><dt>Submission</dt><dd>$submission->{'id'}</dd>);
			say qq(<dt>Datestamp</dt><dd>$submission->{'datestamp'}</dd>);
			say qq(<dt>Type</dt><dd>$submission->{'type'}</dd>);
			if ( $submission->{'type'} eq 'alleles' ) {
				my $allele_submission = $self->{'submissionHandler'}->get_allele_submission( $submission->{'id'} );
				if ($allele_submission) {
					say qq(<dt>Locus</dt><dd>$allele_submission->{'locus'}</dd>);
					my $seq_count = @{ $allele_submission->{'seqs'} };
					say qq(<dt>Sequences</dt><dd>$seq_count</dd>);
				}
			} elsif ( $submission->{'type'} eq 'profiles' ) {
				my $profile_submission = $self->{'submissionHandler'}->get_profile_submission( $submission->{'id'} );
				if ($profile_submission) {
					my $scheme_id   = $profile_submission->{'scheme_id'};
					my $set_id      = $self->get_set_id;
					my $scheme_info = $self->{'datastore'}->get_scheme_info( $scheme_id, { set_id => $set_id } );
					say qq(<dt>Scheme</dt><dd>$scheme_info->{'name'}</dd>);
					my $profile_count = @{ $profile_submission->{'profiles'} };
					say qq(<dt>Profiles</dt><dd>$profile_count</dd>);
				}
			}
			say qq(<dt>Action</dt><dd><a href="$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;)
			  . qq(page=submit&amp;$submission->{'type'}=1">Abort/Continue</a>);
			say q(</dl>);
		}
		say q(</div></div>);
		return 1;
	}
	return;
}

sub _get_own_submissions {
	my ( $self, $status, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	my $submissions = $self->_get_submissions_by_status( $status, { get_all => 0 } );
	my $buffer;
	my $embargo = $self->{'datastore'}->get_embargo_attributes;
	if (@$submissions) {
		my $td     = 1;
		my $set_id = $self->get_set_id;
		my $table_buffer;
		foreach my $submission (@$submissions) {
			my $details        = q();
			my %details_method = (
				alleles    => '_get_allele_submission_details',
				profiles   => '_get_profile_submission_details',
				isolates   => '_get_isolate_submission_details',
				genomes    => '_get_isolate_submission_details',
				assemblies => '_get_assembly_submission_details'
			);
			if ( $details_method{ $submission->{'type'} } ) {
				my $method = $details_method{ $submission->{'type'} };
				$details = $self->$method($submission);
                $logger->error($details);
			}
			my $url = qq($self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;page=submit&amp;)
			  . qq(submission_id=$submission->{'id'}&amp;view=1);
			$table_buffer .=
				qq(<tr class="td$td"><td><a href="$url">$submission->{'id'}</a></td>)
			  . qq(<td>$submission->{'date_submitted'}</td><td>$submission->{'datestamp'}</td>)
			  . qq(<td>$submission->{'type'}</td><td>$details</td>);
			if ( $self->{'system'}->{'dbtype'} eq 'isolates' && $embargo->{'embargo_enabled'} ) {
				my $embargo_months = $submission->{'embargo'} // '-';
				$table_buffer .= qq(<td>$embargo_months</td>);
			}
			if ( $options->{'show_outcome'} ) {
				my %style = FACE_STYLE;
				$table_buffer .= qq(<td><span $style{$submission->{'outcome'}}></span></td>);
			}
=begin
			if ( $options->{'allow_remove'} ) {
				$table_buffer .=
					qq(<td><a href="$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;)
				  . qq(page=submit&amp;submission_id=$submission->{'id'}&amp;remove=1">)
				  . q(<span class="fas fa-lg fa-times"></span></a></td>);
			}
=cut
			$table_buffer .= q(</tr>);
			$td = $td == 1 ? 2 : 1;
		}
		if ($table_buffer) {
			$buffer .= q(<div class="scrollable"><table class="resultstable"><tr><th>Submission id</th>)
			  . q(<th>Submitted</th><th>Updated</th><th>Type</th><th>Details</th>);
			$buffer .= q(<th>Embargo requested (months)</th>)
			  if $self->{'system'}->{'dbtype'} eq 'isolates' && $embargo->{'embargo_enabled'};
			$buffer .= q(<th>Outcome</th>) if $options->{'show_outcome'};
			#$buffer .= q(<th>Remove</th>)  if $options->{'allow_remove'};
			$buffer .= q(</tr>);
			$buffer .= $table_buffer;
			$buffer .= q(</table></div>);
		}
	}
	return $buffer;
}

sub _get_allele_submission_details {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission ) = @_;
	my $set_id            = $self->get_set_id;
	my $allele_submission = $self->{'submissionHandler'}->get_allele_submission( $submission->{'id'} );
	my $allele_count      = @{ $allele_submission->{'seqs'} };
	my $plural            = $allele_count == 1 ? '' : 's';
	return if $set_id && !$self->{'datastore'}->is_locus_in_set( $allele_submission->{'locus'}, $set_id );
	my $clean_locus = $self->clean_locus( $allele_submission->{'locus'} );
	return "$allele_count $clean_locus sequence$plural";
}

sub _get_profile_submission_details {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission ) = @_;
	my $set_id             = $self->get_set_id;
	my $profile_submission = $self->{'submissionHandler'}->get_profile_submission( $submission->{'id'} );
	my $profile_count      = @{ $profile_submission->{'profiles'} };
	my $plural             = $profile_count == 1 ? '' : 's';
	return
	  if $set_id
	  && !$self->{'datastore'}->is_scheme_in_set( $profile_submission->{'scheme_id'}, $set_id );
	my $scheme_info =
	  $self->{'datastore'}->get_scheme_info( $profile_submission->{'scheme_id'}, { get_pk => 1, set_id => $set_id } );
	return "$profile_count $scheme_info->{'name'} profile$plural";
}

sub _get_isolate_submission_details {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission ) = @_;
    $logger->error('hey ho ouille aieaieaie 🙋‍♂️');
    $logger->error(Dumper $submission);
	my $isolate_submission = $self->{'submissionHandler'}->get_isolate_submission( $submission->{'id'} );
    my $isolate_count      = @{ $isolate_submission->{'isolates'} };
	my $plural             = $isolate_count == 1 ? '' : 's';
	return "$isolate_count isolate$plural";
}

sub _get_assembly_submission_details {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission ) = @_;
	my $isolate_submission = $self->{'submissionHandler'}->get_assembly_submission( $submission->{'id'} );
	my $assembly_count     = @$isolate_submission;
	my $plural             = $assembly_count == 1 ? 'y' : 'ies';
	return "$assembly_count assembl$plural";
}

sub _print_pending_submissions {
    $logger->error('use _print_pending_submissions');
	my ($self) = @_;
	my $buffer = $self->_get_own_submissions('pending');
	if ($buffer) {
		say q(<h2>Pending submissions</h2>);
		say q(<p>You have submitted the following submissions that are pending curation:</p>);
		say q(<div class="scrollable">);
		say $buffer;
		say q(</div>);
	}
	return;
}

sub print_submissions_for_curation {
	my ( $self, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	return if ( $self->{'system'}->{'submissions'} // '' ) ne 'yes';
	return if !$self->{'config'}->{'submission_dir'};
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	return if !$user_info || ( $user_info->{'status'} ne 'admin' && $user_info->{'status'} ne 'curator' );
	my $buffer;
    $logger->error('use print_submissions_for_curation');
    $buffer .= $self->_get_isolate_submissions_for_curation($options);
	return $buffer if $options->{'get_only'};
	say $buffer    if $buffer;
	return;
}

sub _get_isolate_submissions_for_curation {
    $logger->error('use _get_isolate_submissions_for_curation');
	my ( $self, $options ) = @_;
	my $status = $options->{'status'} // 'pending';
	# return q() if !$self->can_modify_table('isolates'); # disable this so that all curators, regardless of their rights can validate new isolates, mk 23/10/18
	my $submissions = $self->_get_submissions_by_status( $status, { get_all => 1 } );
    $logger->error("$submissions");
	my $embargo = $self->{'datastore'}->get_embargo_attributes;

	# Get isolate curate message if it exists
	my $isolate_curate_message = "$self->{'dbase_config_dir'}/$self->{'instance'}/isolate_curate.html";
	my $curate_message_content = q();
	if (-e $isolate_curate_message) {
		$curate_message_content = $self->print_file( $isolate_curate_message, { get_only => 1 } );
	}

	# Create table renderer instance
	my $table_renderer = BIGSdb::UI::IsolateSubmissionsTable->new();

	# Use the renderer to generate the complete form with table
	my $return_buffer = $table_renderer->render_complete_form(
        submissions             => $submissions,
        status                  => $status,
        system                  => $self->{'system'},
        instance                => $self->{'instance'},
        datastore               => $self->{'datastore'},
        submissionHandler       => $self->{'submissionHandler'},
        embargo                 => $embargo,
        can_modify_sequence_bin => $self->can_modify_table('sequence_bin'),
        isolate_curate_message  => $curate_message_content,
        show_outcome            => 0
	);
    $logger->error(Dumper($options));

	return $return_buffer;
}

sub _get_isolate_for_curation_review {
    my ( $self ) = @_;
    my $q     = $self->{'cgi'};
    $logger->error('use _get_️isolate_for_curation_review');

    my @selected_submissions = $q->param('selected_submissions[]');
    my $submissions = $self->_get_submissions( @selected_submissions );
	my $embargo = $self->{'datastore'}->get_embargo_attributes;

	# Get isolate curate message if it exists
	my $isolate_curate_message = "$self->{'dbase_config_dir'}/$self->{'instance'}/isolate_curate.html";
	my $curate_message_content = q();
	if (-e $isolate_curate_message) {
		$curate_message_content = $self->print_file( $isolate_curate_message, { get_only => 1 } );
	}

	# Create table renderer instance
	my $table_renderer = BIGSdb::UI::IsolateSubmissionsTable->new();

	# Use the renderer to generate the complete form with table
	my $return_buffer = $table_renderer->render_complete_form(
        submissions             => $submissions,
        status                  => 'pending', # TODO 🌈🌈🌈🌈
        system                  => $self->{'system'},
        instance                => $self->{'instance'},
        datastore               => $self->{'datastore'},
        submissionHandler       => $self->{'submissionHandler'},
        embargo                 => $embargo,
        can_modify_sequence_bin => $self->can_modify_table('sequence_bin'),
        isolate_curate_message  => $curate_message_content,
        show_outcome           => 1
	);

	return $return_buffer;
}

sub _print_closed_submissions {
	my ($self) = @_;
	my $buffer = $self->_get_own_submissions( 'closed', { show_outcome => 1, allow_remove => 1 } );
	if ($buffer) {
		say q(<h2>Recently closed submissions</h2>);
		my $days = $self->get_submission_days;
		say q(<p>You have submitted the following submissions which are now closed);
=begin
		  . q(you have recorded the results.  Alternatively they will be removed automatically after )
		  . qq($days days.</p>);
=cut
		say $buffer;
	}
	return;
}

sub _print_allele_warnings {
	my ( $self, $warnings ) = @_;
	return if ref $warnings ne 'ARRAY' || !@$warnings;
	my @info = @$warnings;
	local $" = q(<br />);
	my $plural = @info == 1 ? '' : 's';
	say qq(<div class="box statuswarn"><h2>Warning$plural:</h2><p>@info</p><p>Warnings do not prevent submission )
	  . q(but may result in the submission being rejected depending on curation criteria.</p></div>);
	return;
}

sub _abort_submission {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission_id ) = @_;
	return if !$self->{'cgi'}->param('confirm');
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	my $submission =
	  $self->{'datastore'}
	  ->run_query( 'SELECT id FROM submissions WHERE (id,submitter)=(?,?)', [ $submission_id, $user_info->{'id'} ] );
	$self->{'submissionHandler'}->delete_submission($submission_id) if $submission_id;
	return;
}

sub _delete_selected_submission_files {
	my ( $self, $submission_id ) = @_;
	my $q     = $self->{'cgi'};
	my $files = $self->_get_submission_files($submission_id);
	my $i     = 0;
	my $dir   = $self->{'submissionHandler'}->get_submission_dir($submission_id) . '/supporting_files';
	foreach my $file (@$files) {
		if ( $q->param("file$i") ) {
			if ( $file->{'filename'} =~ /^([^\/]+)$/x ) {
				my $filename = $1;
				unlink "$dir/$filename" || $logger->error("Cannot delete $dir/$filename.");
			}
			$q->delete("file$i");
		}
		$i++;
	}
	return;
}

sub _finalize_submission {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission_id ) = @_;
	my $q          = $self->{'cgi'};
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	return if !$submission || $submission->{'status'} ne 'started';
	$self->_check_invalid_embargo;
	$logger->info("$self->{'instance'}: New $submission->{'type'} submission");
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	my $embargo   = $self->{'datastore'}->get_embargo_attributes;
	eval {
		if ( $submission->{'type'} eq 'alleles' ) {
			$self->{'db'}->do(
				'UPDATE allele_submissions SET (technology,read_length,coverage,assembly,software)=(?,?,?,?,?) '
				  . 'WHERE submission_id=? AND submission_id IN (SELECT id FROM submissions WHERE submitter=?)',
				undef,
				scalar $q->param('technology'),
				scalar $q->param('read_length'),
				scalar $q->param('coverage'),
				scalar $q->param('assembly'),
				scalar $q->param('software'),
				$submission_id,
				$user_info->{'id'}
			);
		}
		my $embargo_months;
		if ( $q->param('embargo') && BIGSdb::Utils::is_int( scalar $q->param('embargo_months') ) ) {
			$embargo_months = $q->param('embargo_months');
		}
		$self->{'db'}->do(
			'UPDATE submissions SET (status,date_submitted,datestamp,email)=(?,?,?,?) WHERE (id,submitter)=(?,?)',
			undef, 'pending', 'now', 'now', $q->param('email') // undef,
			$submission_id, $user_info->{'id'}
		);
		if ( $self->{'system'}->{'dbtype'} eq 'isolates' && $q->param('embargo') ) {
			$self->{'db'}->do( 'UPDATE submissions SET embargo=? WHERE (id,submitter)=(?,?)',
				undef, $embargo_months, $submission_id, $user_info->{'id'} );
		}
		$self->{'submissionHandler'}->write_db_file($submission_id);
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
	$self->{'submissionHandler'}->notify_curators($submission_id);
	return;
}

sub _submit_alleles {
	my ($self)        = @_;
	my $q             = $self->{'cgi'};
	my $submission_id = $self->_get_started_submission_id;
	$q->param( submission_id => $submission_id );
	my $ret;
	if ($submission_id) {
		my $allele_submission = $self->{'submissionHandler'}->get_allele_submission($submission_id);
		my $fasta_string;
		foreach my $seq ( @{ $allele_submission->{'seqs'} } ) {
			$fasta_string .= ">$seq->{'seq_id'}\n";
			$fasta_string .= "$seq->{'sequence'}\n";
		}
		if ( !$q->param('no_check') ) {
			$ret =
			  $self->{'submissionHandler'}->check_new_alleles_fasta( $allele_submission->{'locus'}, \$fasta_string );
			$self->_print_allele_warnings( $ret->{'info'} );
		}
		$self->_presubmit_alleles( $submission_id, undef );
		return;
	} elsif ( $q->param('submit') ) {
		$ret = $self->_check_new_alleles;
		if ( $ret->{'err'} ) {
			my @err = @{ $ret->{'err'} };
			local $" = '<br />';
			my $plural = @err == 1 ? '' : 's';
			$self->print_bad_status( { message => qq(Error$plural:), detail => qq(@err) } );
		} else {
			if ( $ret->{'info'} ) {
				$self->_print_allele_warnings( $ret->{'info'} );
			}
			$self->_presubmit_alleles( undef, $ret->{'seqs'} );
			return;
		}
	}
	say q(<div class="box" id="queryform">);
	say q(<h2>Submit new alleles</h2>);
	say q(<p>You need to make a separate submission for each locus for which you have new alleles - this is because )
	  . q(different loci may have different curators.  You can submit any number of new sequences for a single locus )
	  . q(as one submission. Sequences should be trimmed to the correct start/end sites for the selected locus.</p>);
	my $set_id = $self->get_set_id;
	my ( $loci, $labels );
	say $q->start_form;
	my $schemes = $self->{'datastore'}->run_query(
		'SELECT id FROM schemes WHERE id IN (SELECT sm.scheme_id FROM scheme_members sm '
		  . 'JOIN loci l ON sm.locus=l.id WHERE (no_submissions = FALSE OR no_submissions IS NULL)) '
		  . 'ORDER BY display_order,description',
		undef,
		{ fetch => 'col_arrayref' }
	);

	if ( @$schemes > 1 ) {
		say q(<fieldset id="scheme_fieldset" style="float:left;display:none"><legend>Filter loci by scheme</legend>);
		say q(<div id="tree" class="scheme_tree" style="float:left;max-height:initial">);
		say $self->get_tree( undef, { no_link_out => 1, select_schemes => 1, filter_no_submissions => 1 } );
		say q(</div>);
		say $q->submit( -name => 'filter', -id => 'filter', -label => 'Filter', -class => 'small_submit' );
		say q(</fieldset>);
		my @selected_schemes;
		foreach my $scheme_id ( @$schemes, 0 ) {
			push @selected_schemes, $scheme_id if $q->param("s_$scheme_id");
		}
		my $scheme_loci = @selected_schemes ? $self->_get_scheme_loci( \@selected_schemes ) : undef;
		( $loci, $labels ) =
		  $self->{'datastore'}->get_locus_list( { only_include => $scheme_loci, set_id => $set_id, submissions => 1 } );
	} else {
		( $loci, $labels ) = $self->{'datastore'}->get_locus_list( { set_id => $set_id, submissions => 1 } );
	}
	say q(<fieldset style="float:left;"><legend>Select locus</legend>);
	say $q->popup_menu(
		-name     => 'locus',
		-id       => 'locus',
		-values   => $loci,
		-labels   => $labels,
		-size     => 7,
		-required => 'required'
	);
	say q(</fieldset>);
	$self->_print_sequence_details_fieldset($submission_id);
	say q(<fieldset style="float:left"><legend>FASTA or single sequence</legend>);
	if ( $q->param('sequence_file') ) {
		my $filename = $q->param('sequence_file');
		$filename =~ s/[\.\/]//gx;    #Prevent directory traversal
		my $full_path = "$self->{'config'}->{'secure_tmp_dir'}/$filename";
		if ( -e $full_path ) {
			my $seq_ref = BIGSdb::Utils::slurp($full_path);
			$q->param( fasta => $$seq_ref );
		}
	}
	say $q->textarea(
		-name     => 'fasta',
		-rows     => 8,
		-id       => 'fasta',
		-required => 'required',
		-style    => 'max-width:800px;width:calc(100vw - 100px)'
	);
	say q(</fieldset>);
	say $q->hidden($_) foreach qw(db page alleles);
	$self->print_action_fieldset( { no_reset => 1 } );
	say $q->end_form;
	return;
}

sub _submit_profiles {
	my ($self)        = @_;
	my $q             = $self->{'cgi'};
	my $submission_id = $self->_get_started_submission_id;
	$q->param( submission_id => $submission_id );
	my $ret;
	if ($submission_id) {
		$self->_presubmit_profiles( $submission_id, undef );
		return;
	} elsif ( ( $q->param('submit') && $q->param('data') ) ) {
		my $scheme_id = $q->param('scheme_id');
		my $set_id    = $self->get_set_id;
		my $data      = $q->param('data');
        $ret = $self->{'submissionHandler'}->check_new_profiles( $scheme_id, $set_id, \$data );
		if ( $ret->{'err'} ) {
			my $err = $ret->{'err'};
			local $" = '<br />';
			my $plural = @$err == 1 ? '' : 's';
			$self->print_bad_status( { message => qq(Error$plural:), detail => qq(@$err) } );
		} elsif ( !@{ $ret->{'profiles'} } ) {
			$self->print_bad_status( { message => q(Error:), detail => 'No profiles in upload.' } );
		} else {
			$self->_presubmit_profiles( undef, $ret->{'profiles'} );
			return;
		}
	}
	my $scheme_id = $q->param('scheme_id');
	if ( !BIGSdb::Utils::is_int($scheme_id) ) {
		$self->print_bad_status( { message => q(Scheme id must be an integer.) } );
		return;
	}
	my $set_id      = $self->get_set_id;
	my $scheme_info = $self->{'datastore'}->get_scheme_info( $scheme_id, { get_pk => 1, set_id => $set_id } );
	if ( !$scheme_info || !$scheme_info->{'primary_key'} ) {
		$self->print_bad_status( { message => q(Invalid scheme passed.) } );
		return;
	}
	say q(<div class="box" id="queryform">);
	say qq(<h2>Submit new $scheme_info->{'name'} profiles</h2>);
	say q(<p>Paste in your profiles for assignment using the template available below.</p>);
	say q(<h2>Templates</h2>);
	my ( $text, $excel ) = ( TEXT_FILE, EXCEL_FILE );
	say qq(<p><a href="$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;page=tableHeader&amp;)
	  . qq(table=profiles&amp;scheme_id=$scheme_id&amp;no_fields=1&amp;id_field=1" title="Download tab-delimited )
	  . qq(header for your spreadsheet">$text</a>)
	  . qq[<a href="$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;page=excelTemplate&amp;]
	  . qq[table=profiles&amp;scheme_id=$scheme_id&amp;no_fields=1&amp;id_field=1" title="Download submission template ]
	  . qq[(xlsx format)">$excel</a></p>];
	say $q->start_form;
	say q(<fieldset style="float:left"><legend>Please paste in tab-delimited text <b>)
	  . q((include a field header as the first line)</b></legend>);
	say $q->textarea(
		-name     => 'data',
		-rows     => 15,
		-required => 'required',
		-style    => 'max-width:800px;width:calc(100vw - 100px)'
	);
	say q(</fieldset>);
	say $q->hidden($_) foreach qw(db page profiles scheme_id);
	$self->print_action_fieldset( { no_reset => 1 } );
	say $q->end_form;
	say q(</div>);
	return;
}

sub _submit_isolates {
	my ( $self, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	my $q             = $self->{'cgi'};
	my $submission_id = $self->_get_started_submission_id;
	$q->param( submission_id => $submission_id );
	if ($submission_id) {
		$self->_presubmit_isolates( { submission_id => $submission_id, options => $options } );
		return;
	} elsif ( ( $q->param('submit') && $q->param('data') ) ) {
		my $set_id = $self->get_set_id;
		my $data   = $q->param('data');
		$options->{'limit'} = LIMIT if $options->{'genomes'};
		my $ret = $self->{'submissionHandler'}->check_new_isolates( $set_id, \$data, $options );
		if ( $ret->{'err'} ) {
			my $err = $ret->{'err'};
			local $" = '<br />';
			my $plural = @$err == 1 ? '' : 's';
			s/'null'/<em>null<\/em>/gx foreach @$err;
			$self->print_bad_status( { message => qq(Error$plural:), detail => qq(@$err) } );
		} else {
			$self->_presubmit_isolates(
				{ isolates => $ret->{'isolates'}, positions => $ret->{'positions'}, options => $options } );
			return;
		}
	}
	my $set_id     = $self->get_set_id;
	my $set_clause = $set_id ? qq(&amp;set_id=$set_id) : q();
	say q(<div class="box" id="queryform"><div class="scrollable">);
	say q(<h2>Submit new isolates);
	say q( with genome assemblies) if $options->{'genomes'};
	say q(</h2>);
	say q(<p>Paste in your isolates for addition to the database using the template available below.</p>);
	say q(<ul><li>Optionally enter aliases (alternative names) for your isolates as a semi-colon)
	  . q( (;)-separated list.</li>);
	say q(<li>Optionally enter references for your isolates as a semi-colon (;)-separated list of PubMed ids.</li>);
	say q(<li>You can also upload additional allele fields along with the other isolate data - simply create a )
	  . q(new column with the locus name. );
	say q(By default, loci are not included with genome submissions since these can be extracted )
	  . q(directly from the genome.)
	  if $options->{'genomes'};
	say q(</li>);

	if ( $options->{'genomes'} ) {
		my $limit = LIMIT;
		say q(<li>Enter the name of the assembly contig FASTA file in the assembly_filename field and upload )
		  . q(this file as supporting data. FASTA files can be either uncompressed (.fas, .fasta) or )
		  . qq(gzip/zip compressed (.fas.gz, .fas.zip). <strong>Upload is limited to $limit files.</strong></li>);
		my @methods = SEQ_METHODS;
		local $" = q(, );
		say q(<li>Enter the name of the sequence method used in the sequence_method field )
		  . qq((allowed values: @methods)</li>);
	}
	say q(</ul>);
	my $contig_file_clause = $options->{'genomes'} ? '&amp;addCols=assembly_filename,sequence_method&noLoci=1' : q();
	my ( $text, $excel ) = ( TEXT_FILE, EXCEL_FILE );
	say q(<h2>Templates</h2>);
	say qq(<p><a href="$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;page=tableHeader&amp;)
	  . qq(table=isolates&amp;order=scheme$set_clause$contig_file_clause" title="Download tab-delimited )
	  . qq(header for your spreadsheet">$text</a>)
	  . qq[<a href="$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;page=excelTemplate&amp;]
	  . qq[table=isolates&amp;order=scheme$set_clause$contig_file_clause" title="Download submission template ]
	  . qq[(xlsx format)">$excel</a></p>];
	my $plugins = $self->{'pluginManager'}->get_installed_plugins;
	if ( $plugins->{'DatabaseFields'} ) {
		say qq(<p>Check the <a href="$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;page=plugin&amp;)
		  . q(name=DatabaseFields" target="_blank">description of database fields</a> for help with filling in )
		  . q(the template.</p>);
	}
	say $q->start_form;
	say q(<fieldset style="float:left"><legend>Please paste in tab-delimited text <b>)
	  . q((include a field header as the first line)</b></legend>);
	say $q->textarea(
		-name     => 'data',
		-rows     => 15,
		-required => 'required',
		-style    => 'max-width:1400px;width:calc(100vw - 100px)'
	);
	say q(</fieldset>);
	say $q->hidden($_) foreach qw(db page isolates genomes);
	$self->print_action_fieldset( { no_reset => 1 } );
	say $q->end_form;
	say q(</div></div>);
	return;
}

sub _check_invalid_embargo {
	my ($self)         = @_;
	my $q              = $self->{'cgi'};
	my $embargo        = $self->{'datastore'}->get_embargo_attributes;
	my $embargo_months = $q->param('embargo_months');
	if ( $q->param('embargo') && BIGSdb::Utils::is_int($embargo_months) ) {
		if ( !$embargo->{'embargo_enabled'} || $embargo_months > $embargo->{'max_initial_embargo'} ) {
			$logger->error(
				"Invalid embargo requested: $embargo_months months. Setting to default ($embargo->{'default_embargo'})."
			);
			$q->param( embargo_months => $embargo->{'default_embargo'} );
			return 1;
		}
	}
	return;
}

sub _get_assembly_wrong_sender {
	my ( $self, $submission_id ) = @_;
	my $invalid_ids  = [];
	my $wrong_sender = [];
	my $cleaned_list = $self->{'datastore'}->run_query(
		'SELECT isolate_id AS id,isolate,filename FROM assembly_submissions WHERE '
		  . 'submission_id=? ORDER BY isolate_id',
		$submission_id,
		{ fetch => 'all_arrayref', slice => {} }
	);
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	foreach my $record (@$cleaned_list) {
		my $sender = $self->{'datastore'}
		  ->run_query( "SELECT sender FROM $self->{'system'}->{'view'} WHERE id=?", $record->{'id'} );
		if ( !$sender ) {
			push @$invalid_ids, $record->{'id'};
		} elsif ( $sender != $submission->{'submitter'} ) {
			push @$wrong_sender, $record->{'id'};
		}
	}
	return { wrong_sender => $wrong_sender, invalid_ids => $invalid_ids };
}


sub _print_file_fieldset {
	my ( $self, $submission_id ) = @_;
	my $file_table = $self->_print_submission_file_table( $submission_id, { get_only => 1 } );
	if ($file_table) {
		say q(<fieldset style="float:left"><legend>Supporting files</legend>);
		say $file_table;
		say q(</fieldset>);
	}
	return;
}

sub _print_summary {
	my ( $self, $submission_id ) = @_;
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	say q(<fieldset style="float:left"><legend>Summary</legend>);
	say qq(<dl class="data"><dt>type</dt><dd>$submission->{'type'}</dd>);
	my $user_string =
	  $self->{'datastore'}->get_user_string( $submission->{'submitter'}, { email => 1, affiliation => 1 } );
	say qq(<dt>submitter</dt><dd>$user_string</dd>);
	say qq(<dt>datestamp</dt><dd>$submission->{'datestamp'}</dd>);
	say qq(<dt>status</dt><dd>$submission->{'status'}</dd>);
	my %outcome = (
		good  => 'accepted - data uploaded',
		bad   => 'rejected - data not uploaded',
		mixed => 'mixed - submission partially accepted'
	);
	say qq(<dt>outcome</dt><dd>$outcome{$submission->{'outcome'}}</dd>) if $submission->{'outcome'};

	if ( defined $submission->{'curator'} ) {
		my $curator_string =
		  $self->{'datastore'}->get_user_string( $submission->{'curator'}, { email => 1, affiliation => 1 } );
		say qq(<dt>curator</dt><dd>$curator_string</dd>);
	}
	if ( $submission->{'type'} eq 'alleles' ) {
		my $allele_submission = $self->{'submissionHandler'}->get_allele_submission($submission_id);
		my $locus             = $self->clean_locus( $allele_submission->{'locus'} ) // $allele_submission->{'locus'};
		say qq(<dt>locus</dt><dd>$locus</dd>);
		my $allele_count   = @{ $allele_submission->{'seqs'} };
		my $fasta_icon     = $self->get_file_icon('FAS');
		my $submission_dir = $self->{'submissionHandler'}->get_submission_dir($submission_id);
		if ( !-e "$submission_dir/sequences.fas" ) {
			$self->{'submissionHandler'}->write_submission_allele_FASTA($submission_id);
			$logger->error("No submission FASTA file for allele submission $submission_id.");
		}
		say q(<dt>sequences</dt>)
		  . qq(<dd><a href="/submissions/$submission_id/sequences.fas">$allele_count$fasta_icon</a></dd>);
		say qq(<dt>technology</dt><dd>$allele_submission->{'technology'}</dd>);
		say qq(<dt>read length</dt><dd>$allele_submission->{'read_length'}</dd>)
		  if $allele_submission->{'read_length'};
		say qq(<dt>coverage</dt><dd>$allele_submission->{'coverage'}</dd>) if $allele_submission->{'coverage'};
		say qq(<dt>assembly</dt><dd>$allele_submission->{'assembly'}</dd>) if $allele_submission->{'assembly'};
		say qq(<dt>assembly software</dt><dd>$allele_submission->{'software'}</dd>)
		  if $allele_submission->{'software'};
	}
	say q(</dl></fieldset>);
	return;
}

#Check submission exists and curator has appropriate permissions.
sub _is_submission_valid {
	my ( $self, $submission_id, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	if ( !$submission_id ) {
		$self->print_bad_status( { message => q(No submission id passed.) } ) if !$options->{'no_message'};
		return;
	}
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	if ( !$submission ) {
		$self->print_bad_status( { message => qq(Submission '$submission_id' does not exist.) } )
		  if !$options->{'no_message'};
		return;
	}
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	if ( $options->{'curate'} ) {
		if ( !$user_info || ( $user_info->{'status'} ne 'admin' && $user_info->{'status'} ne 'curator' ) ) {
			$self->print_bad_status(
				{
					message => q(Your account does not have the required permissions to curate this submission.)
				}
			) if !$options->{'no_message'};
			return;
		}
		if ( $submission->{'type'} eq 'alleles' ) {
			my $allele_submission = $self->{'submissionHandler'}->get_allele_submission( $submission->{'id'} );
			my $curator_allowed =
			  $self->{'datastore'}
			  ->is_allowed_to_modify_locus_sequences( $allele_submission->{'locus'}, $user_info->{'id'} );
			if ( !( $self->is_admin || $curator_allowed ) ) {
				$self->print_bad_status(
					{
						message => q(Your account does not have the required )
						  . qq(permissions to curate new $allele_submission->{'locus'} sequences.)
					}
				) if !$options->{'no_message'};
				return;
			}
		}
	}
	if ( $options->{'user_owns'} ) {
		return if $submission->{'submitter'} != $user_info->{'id'};
	}
	return 1;
}

sub set_level2_breadcrumbs {
	my ( $self, $page ) = @_;
	$self->{'breadcrumbs'} = [
		{
			label => $self->{'system'}->{'webroot_label'} // 'Organism',
			href  => $self->{'system'}->{'webroot'}
		},
		{
			label => $self->{'system'}->{'formatted_description'} // $self->{'system'}->{'description'},
			href  => "$self->{'system'}->{'script_name'}?db=$self->{'instance'}"
		},
		{
			label => 'Submissions',
			href  => "$self->{'system'}->{'script_name'}?db=$self->{'instance'}&amp;page=submit"
		},
		{
			label => $page
		}
	];
	return;
}

sub _curate_submission {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission_id ) = @_;
	my $q = $self->{'cgi'};
	say q(<h1>Curate submission</h1>);
	return if !$self->_is_submission_valid( $submission_id, { curate => 1 } );
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	my $curate     = 1;
	if ( $submission->{'status'} eq 'closed' ) {
		$self->print_bad_status( { message => q(This submission is closed and cannot now be modified.) } );
		$curate = 0;
	}
	my $disk_full = $self->_check_storage_report_dir;
	say q(<div class="box" id="resultspanel">);
	say qq(<h2 style="overflow-x:auto;overflow-y:hidden">Submission: $submission_id</h2>);
	my %isolate_type = map { $_ => 1 } qw(isolates genomes assemblies);
	if ( $isolate_type{ $submission->{'type'} } && $q->param('curate') && $q->param('update') ) {
		$self->_update_isolate_submission_isolate_status($submission_id);
		$submission = $self->{'submissionHandler'}->get_submission($submission_id);
	}
	$self->_print_summary($submission_id);
	say q(<div style="clear:both"></div>);
	say q(<div class="flex_container" style="justify-content:left">);
	$self->_print_sequence_table_fieldset( $submission_id, { curate => $curate } );
	$self->_print_profile_table_fieldset( $submission_id, { curate => $curate } );
	$self->_print_isolate_table_fieldset( $submission_id, { curate => $curate } );
	$self->_print_assembly_table_fieldset( $submission_id, { curate => $curate } );
	$self->_print_advisories( $submission_id, { curate => $curate } );
	$self->_print_file_fieldset($submission_id);
	$self->_print_message_fieldset($submission_id);
	$self->_print_archive_fieldset($submission_id);

	if ($curate && !$disk_full) {
		$self->_print_close_submission_fieldset($submission_id);
	} elsif ($curate && $disk_full) {
	    $self->_print_disk_full_warning;
	}
	#else {
		#$self->_print_reopen_submission_fieldset($submission_id);
	#}
	say q(<div style="clear:both"></div>);
	say q(</div></div>);
	return;
}

sub _view_submission {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission_id ) = @_;
	my $q = $self->{'cgi'};
	say q(<h1>Submission summary</h1>);
	return if !$self->_is_submission_valid($submission_id);
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	say q(<div class="box" id="resultspanel">);
	say qq(<h2 style="overflow-x:auto">Submission: $submission_id</h2>);
	$self->_print_summary($submission_id);
	say q(<div style="clear:both"></div>);
	say q(<div class="flex_container" style="justify-content:left">);
	$self->_print_sequence_table_fieldset($submission_id);
	$self->_print_profile_table_fieldset($submission_id);
	$self->_print_file_upload_fieldset( $submission_id, { no_add => $submission->{'status'} eq 'closed' ? 1 : 0 } )
	  if $submission->{'type'} ne 'isolates';
	$self->_print_assembly_table_fieldset( $submission_id, { download_link => 1 } );
	$self->_print_advisories( $submission_id, { view => 1 } );
	$self->_print_isolate_table_fieldset($submission_id);
	$self->_print_message_fieldset( $submission_id, { no_add => $submission->{'status'} eq 'closed' ? 1 : 0 } );
	$self->_print_archive_fieldset($submission_id);
	#$self->_print_cancel_fieldset($submission_id);

	if ( $submission->{'status'} eq 'started' ) {
		say $q->start_form;
		$self->print_action_fieldset( { no_reset => 1, submit_label => 'Finalize submission!' } );
		say $q->hidden( finalize => 1 );
		say $q->hidden($_) foreach qw(db page locus submit finalize submission_id);
		say $q->end_form;
	}
	say q(</div></div>);
	return;
}

sub _close_submission {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission_id ) = @_;
	return if !$self->_is_submission_valid( $submission_id, { curate => 1, no_message => 1 } );
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	return if !$submission || $submission->{'status'} eq 'closed';    #Prevent refresh from re-sending E-mail
	my $curator_id = $self->get_curator_id;
        eval {
		$self->{'db'}->do( 'UPDATE submissions SET (status,datestamp,curator)=(?,?,?) WHERE id=?',
			undef, 'closed', 'now', $curator_id, $submission_id );
	};
	if ($@) {
		$logger->error($@);
		$self->{'db'}->rollback;
	} else {
		$self->{'db'}->commit;
	}
        my $dbname = $self->{'datastore'}->run_query('select current_database()');
        open(BASH, "|-", "bash");
        print BASH "/home/bigsdb/BIGSdb/3.12PythonVenv/bin/python3.12 /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/sample_validation_to_mongo.py --db $dbname --sub_id $submission_id \n";
        close(BASH);
        $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	my $curator_info = $self->{'datastore'}->get_user_info($curator_id);
	$self->{'submissionHandler'}->remove_submission_from_digest($submission_id);
	if ( $submission->{'email'} ) {
		my $desc = $self->{'system'}->{'description'} || 'BIGSdb';
		$self->{'submissionHandler'}->email(
			$submission_id,
			{
				recipient => $submission->{'submitter'},
				sender    => $curator_id,
				subject   => "$desc submission closed - $submission_id",
				message   => $self->{'submissionHandler'}
				  ->get_text_summary( $submission_id, { messages => 1, correspondence_first => 1 } ),
				cc_sender => $curator_info->{'submission_email_cc'}
			}
		);
	}
	return;
}

=begin
sub _remove_submission {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission_id ) = @_;
	return if !$self->_is_submission_valid( $submission_id, { no_message => 1, user_owns => 1 } );
	$self->{'submissionHandler'}->delete_submission($submission_id);
	return;
}
=cut

sub _cancel_submission {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission_id ) = @_;
	return if !$self->_is_submission_valid( $submission_id, { no_message => 1, user_owns => 1 } );
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	return if $submission->{'status'} ne 'pending';
	my $curators = $self->{'submissionHandler'}->get_curators($submission_id);
	my $desc     = $self->{'system'}->{'description'} || 'BIGSdb';
	my $subject  = "CANCELLED $submission->{'type'} submission ($desc) - $submission_id";
	my $message  = "This submission has been CANCELLED by the submitter.\n\n";
	$message .= $self->{'submissionHandler'}->get_text_summary( $submission_id, { messages => 1 } );
	$logger->info("$self->{'instance'}: Submission cancelled.");
	$self->{'submissionHandler'}->remove_submission_from_digest($submission_id);

	foreach my $curator_id (@$curators) {
		my $user_info = $self->{'datastore'}->get_user_info($curator_id);
		next if $user_info->{'submission_digests'};
		next if !$self->{'submissionHandler'}->can_email_curator($curator_id);
		$self->{'submissionHandler'}->email(
			$submission_id,
			{
				recipient => $curator_id,
				sender    => $submission->{'submitter'},
				subject   => $subject,
				message   => $message,
			}
		);
		$self->{'submissionHandler'}->write_flood_protection_file($curator_id);
	}
	$self->{'submissionHandler'}->delete_submission($submission_id);
	return;
}

sub _reopen_submission {
	my ( $self, $submission_id ) = @_;
	return if !$self->_is_submission_valid( $submission_id, { no_message => 1, curate => 1 } );
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	return if $submission->{'status'} ne 'closed';
	my $curator_id = $self->get_curator_id;
	my $message    = 'Submission re-opened.';
	eval {
		$self->{'db'}->do( 'UPDATE submissions SET (status,outcome,datestamp,curator)=(?,?,?,?) WHERE id=?',
			undef, 'pending', undef, 'now', $curator_id, $submission_id );
		$self->{'submissionHandler'}->update_submission_datestamp($submission_id);
		$self->{'db'}->do( 'INSERT INTO messages (submission_id,timestamp,user_id,message) VALUES (?,?,?,?)',
			undef, $submission_id, 'now', $curator_id, $message );
	};
	if ($@) {
		$logger->error($@);
		$self->{'db'}->rollback;
	} else {
		$self->{'db'}->commit;
		$self->{'submissionHandler'}->append_message( $submission_id, $curator_id, $message );
	}
	return;
}

sub _get_fasta_string {
	my ( $self, $seqs ) = @_;
	my $buffer;
	foreach my $seq (@$seqs) {
		$buffer .= ">$seq->{'seq_id'}\n";
		$buffer .= "$seq->{'sequence'}\n";
	}
	return $buffer;
}

sub _tar_submission {    ## no critic (ProhibitUnusedPrivateSubroutines) #Called by dispatch table
	my ( $self, $submission_id ) = @_;
	return if !defined $submission_id || $submission_id !~ /BIGSdb_\d+/x;
	my $submission = $self->{'submissionHandler'}->get_submission($submission_id);
	return if !$submission;
	my $submission_dir = $self->{'submissionHandler'}->get_submission_dir($submission_id);
	$submission_dir =
	  $submission_dir =~ /^($self->{'config'}->{'submission_dir'}\/BIGSdb[^\/]+)$/x ? $1 : undef;    #Untaint
	binmode STDOUT;
	local $" = ' ';
	my $command = "cd $submission_dir && tar -cf - *";

	#The output of system calls will not be sent to the browser when running under mod_perl.
	#This is also the case when running under Plack::App::CGIBin.
	#We can run commands using backticks to circumvent this issue.
	#https://github.com/kjolley/BIGSdb/issues/748
	#https://github.com/kjolley/BIGSdb/issues/751
	my $tar = `$command`;
	if ( length $tar ) {
		print $tar;
	} else {
		$logger->error('Cannot create tar output.');
	}
	return;
}

sub _update_allele_prefs {
	my ($self) = @_;
	my $guid = $self->get_guid;
	return if !$guid;
	my $q = $self->{'cgi'};
	foreach my $param (qw(technology read_length coverage assembly software)) {
		my $field = "submit_allele_$param";
		my $value = $q->param($param);
		next if !$value;
		$self->{'prefstore'}->set_general( $guid, $self->{'system'}->{'db'}, $field, $value );
	}
	return;
}

sub _get_scheme_loci {
	my ( $self, $scheme_ids ) = @_;
	my @loci;
	my %locus_selected;
	my $set_id = $self->get_set_id;
	foreach (@$scheme_ids) {
		my $scheme_loci =
			$_
		  ? $self->{'datastore'}->get_scheme_loci($_)
		  : $self->{'datastore'}->get_loci_in_no_scheme( { set_id => $set_id } );
		foreach my $locus (@$scheme_loci) {
			if ( !$locus_selected{$locus} ) {
				push @loci, $locus;
				$locus_selected{$locus} = 1;
			}
		}
	}
	return \@loci;
}

sub set_pref_requirements {
	my ($self) = @_;
	$self->{'pref_requirements'} =
	  { general => 1, main_display => 0, isolate_display => 0, analysis => 0, query_field => 0 };
	return;
}

sub get_title {
	my ($self) = @_;
	return 'Submissions';
}

sub print_panel_buttons {
	my ($self) = @_;
	$self->print_related_dbases_button;
	return;
}

sub _check_storage_report_dir {
    my ($self) = @_;
    my $usage_percentage = $self->_get_storage_report_dir;
    my $disk_full = 0;
    if ($usage_percentage >= 99) {
        say q(<p class="warning" style="padding: 10px 0 10px 10px;">More than 99% of the disk is used. Isolates can not be accepted/rejected anymore until some JSON reports are removed from the /output_reports directory.);
        $disk_full = 1;
    } elsif ($usage_percentage > 90) {
        say q(<p class="warning" style="padding: 10px 0 10px 10px;">More than 90% of the disk is used. Remove JSON reports from the /output_reports directory before accepting/rejecting other isolates.);
    } elsif ($usage_percentage > 80) {
        say q(<p class="warning" style="padding: 10px 0 10px 10px;">More than 80% of the disk is used. Remove JSON reports from the /output_reports directory before accepting/rejecting other isolates.);
    }
    return $disk_full;
}

sub _get_storage_report_dir {
    my ($self) = @_;
    my $mount_point = '/output_reports';
    my $df_output = `df --output=pcent $mount_point 2>/dev/null`;
    chomp($df_output);
    my @lines = grep { $_ !~ /^Use%/ } split(/\n/, $df_output);
    my $usage_percentage = $lines[0];
    $usage_percentage =~ s/%$//;
    return $usage_percentage;
}

sub _validate_submission {
    my ($self, $submission_id) = @_;
    my $q = $self->{'cgi'};
    # Update the submission outcome to "good" and status to "closed"
    eval {
        $self->{'db'}->do("UPDATE submissions SET (outcome, status, datestamp) = ('good', 'closed', 'now') WHERE id = ?",
            undef, $submission_id);
    };
    if ($@) {
        $logger->error("Validation failed: $@");
        $self->{'db'}->rollback;
        $q->param('error', 'Validation failed.');
    }
    else {
        $self->{'db'}->commit;
        $q->param('message', 'Submission validated and closed.');
    }
    return;
}

sub _update_bulk_submission_status {
    my ($self) = @_;
    my $q = $self->{'cgi'};

    my $status = $q->param('bulk_status');
    return if !$status;

    my @submission_ids = $q->param('submission_ids[]');
    return if !@submission_ids;

    my $curator_id = $self->get_curator_id;
    my $outcome;

    if ($status eq 'Accepted') {
        $outcome = 'good';
    } elsif ($status eq 'rejected') {
        $outcome = 'bad';
    }

    eval {
        foreach my $submission_id (@submission_ids) {
            if (defined $outcome) {
                # accepted or rejected: set outcome and update datestamp/curator
                $self->{'db'}->do(
                    'UPDATE submissions SET datestamp = ?, curator = ?, outcome = ? WHERE id = ?',
                    undef, 'now', $curator_id, $outcome, $submission_id
                );
            } elsif ($status eq 'pending') {
                # pending: clear outcome, update datestamp/curator
                $self->{'db'}->do(
                    'UPDATE submissions SET datestamp = ?, curator = ?, outcome = NULL WHERE id = ?',
                    undef, 'now', $curator_id, $submission_id
                );
            }
        }
    };
    if ($@) {
        $self->{'db'}->rollback;
    } else {
        $self->{'db'}->commit;
    }
    return;
}

sub _print_disk_full_warning {
    my ($self) = @_;
    say q(<fieldset style="float:left;max-width:300px"><legend>Action</legend>);
    say q(<p class="warning" style="padding: 10px 0 10px 10px;">Submissions cannot be closed until some disk space is freed up.);
    say q(</fieldset>);
}
1;
