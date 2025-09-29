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
	$self->{$_} = 1 foreach qw (jQuery jQuery.jstree noCache tooltips dropzone allowExpand jQuery.multiselect);


    #curate defined if the user has clicked on a submission id to curate it
	if ( $q->param('curate') ) {
        $logger->error('I am here with curate param='.$q->param('curate'));
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

	my $submissions_to_show = $self->_any_pending_submissions_to_show;
	$self->_delete_old_submissions;
	my $closed_buffer =
        $self->print_submissions_for_curation( { status => 'closed', show_outcome => 1, get_only => 1 } );

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
    $logger->error('hey ho ouille aieaieaie bklablablabalbla 🙋‍♂️');
	my $isolate_submission = $self->{'submissionHandler'}->get_isolate_submission( $submission->{'id'} );
    my $isolate_count      = @{ $isolate_submission->{'isolates'} };
	my $plural             = $isolate_count == 1 ? '' : 's';
	return "$isolate_count isolate$plural";
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
    my $q = $self->{'cgi'};
	$options = {} if ref $options ne 'HASH';
	return if ( $self->{'system'}->{'submissions'} // '' ) ne 'yes';
	return if !$self->{'config'}->{'submission_dir'};
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	return if !$user_info || ( $user_info->{'status'} ne 'admin' && $user_info->{'status'} ne 'curator' );
	my $buffer = '';
    $logger->error('use print_submissions_for_curation');

    if ( defined($q->param('bulk_status')) ) {
        $buffer .= $self->_get_isolate_for_curation_review($options);
    } elsif ( defined($q->param('validate_submission')) ) {
        my @submission_ids = $q->param('selected_submissions[]');
        my $bulk_status = $q->param('outcome');
        my %outcome = (accepted => 'good', rejected => 'bad', pending => '' );
        my $bulk_outcome = $outcome{ $bulk_status };
        $logger->error("bulk outcome is $bulk_outcome");

        $self->_validate_submission($bulk_outcome, @submission_ids);

        my $submission_count = scalar @submission_ids;
        $buffer .= qq('✅ $submission_count submission(s) have been successfully "$bulk_status".');
    } else {
        $buffer .= $self->_get_isolate_submissions_for_curation($options);
    }

    return $buffer if $options->{'get_only'};
    say $buffer if $buffer;
    return;
}

sub _validate_submission {
    my ($self, $outcome, @submission_ids) = @_;
    my $curator_id = $self->get_curator_id;

    eval {
        for my $submission_id (@submission_ids) {
            # Update submission status
            $self->{'db'}->do(
                'UPDATE submissions SET (status,datestamp,curator,outcome)=(?,?,?,?) WHERE id=?',
                undef, 'closed', 'now', $curator_id, $outcome, $submission_id
            );

            #open(BASH, "|-", "bash");
            #print BASH "/home/bigsdb/BIGSdb/3.12PythonVenv/bin/python3.12 /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/sample_validation_to_mongo.py --db $dbname --sub_id $submission_id \n";
            #close(BASH);
        }
    };
    if ($@) {
        $logger->error("Validation failed: $@");
        $self->{'db'}->rollback;
    } else {
        $self->{'db'}->commit;
    }
    return;
}

sub _get_isolate_submissions_for_curation {
	my ( $self, $options ) = @_;
    my $status = $options->{'status'} // 'pending';
	# return q() if !$self->can_modify_table('isolates'); # disable this so that all curators, regardless of their rights can validate new isolates, mk 23/10/18
	my $submissions = $self->_get_submissions_by_status( $status, { get_all => 1 } );
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
        embargo                 => $embargo,
        isolate_curate_message  => $curate_message_content,
        show_outcome            => 0,
        datastore               => $self->{'datastore'},
        submissionHandler       => $self->{'submissionHandler'}
	);

	return $return_buffer;
}

sub _get_isolate_for_curation_review {
    my ( $self ) = @_;
    my $q     = $self->{'cgi'};

    my @selected_submissions = $q->param('selected_submissions[]');
    my $submissions = $self->_get_submissions(\@selected_submissions );
	my $embargo = $self->{'datastore'}->get_embargo_attributes;

	# Get isolate curate message if it exists
	my $isolate_curate_message = "$self->{'dbase_config_dir'}/$self->{'instance'}/isolate_curate.html";
	my $curate_message_content = q();
    $logger->error('isolate_curate_message='.$isolate_curate_message);
	if (-e $isolate_curate_message) {
		$curate_message_content = $self->print_file( $isolate_curate_message, { get_only => 1 } );
	}

	# Create table renderer instance
	my $table_renderer = BIGSdb::UI::IsolateSubmissionsTable->new();
	# Use the renderer to generate the complete form with table
	my $return_buffer = $table_renderer->render_review_form(
        submissions             => $submissions,
        system                  => $self->{'system'},
        outcome                 => $q->param('bulk_status'),
        embargo                 => $embargo,
        isolate_curate_message  => $curate_message_content,
        datastore               => $self->{'datastore'},
        submissionHandler       => $self->{'submissionHandler'}
	);

	return $return_buffer;
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


1;
