# Written by Keith Jolley
# Copyright (c) 2015-2022, University of Oxford
# E-mail: keith.jolley@zoo.ox.ac.uk
#
# This file is part of Bacterial Isolate Genome Sequence Database (BIGSdb).
#
# BIGSdb is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BIGSdb is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BIGSdb. If not, see <http://www.gnu.org/licenses/>.
package BIGSdb::RejectedPage;
use strict;
use warnings;
use 5.010;
use parent qw(BIGSdb::TreeViewPage BIGSdb::CurateProfileAddPage);
use Log::Log4perl qw(get_logger);
my $logger = get_logger('BIGSdb.RejectedIsolates');
use BIGSdb::Utils;
use BIGSdb::Constants qw(:submissions :interface :design);
use List::MoreUtils qw(none);
use POSIX;
use JSON;

sub get_javascript {
    my ($self) = @_;
    my $q           = $self->{'cgi'};
    return q(
        $(document).ready(function () {
            // Toggle show/hide archived isolates
            $("#show_closed").click(function() {
                if ($("span#show_closed_text").css('display') == 'none') {
                    $("span#show_closed_text").css('display', 'inline');
                    $("span#hide_closed_text").css('display', 'none');
                } else {
                    $("span#show_closed_text").css('display', 'none');
                    $("span#hide_closed_text").css('display', 'inline');
                }
                $( "#closed" ).toggle( 'blind', {} , 500 );
                return false;
            });
        });
    );
}

sub initiate {
    my ( $self )        = @_;
    my $q               = $self->{'cgi'};
    my $rejected_isolate_id = $q->param('rejected_isolate_id');
    $self->{$_} = 1 foreach qw (jQuery jQuery.jstree noCache tooltips dropzone);
    $self->set_level1_breadcrumbs;
    return;
}

sub print_content {
	my ($self)          = @_;
	my $q               = $self->{'cgi'};
	$self->choose_set;
	my $rejected_isolate_id = $q->param('rejected_isolate_id');
	if ($rejected_isolate_id) {
		if ( $q->param('close') ) {
            $self->_close_rejected_isolate($rejected_isolate_id);
		}
	}
	say q(<h1>Manage rejected isolates</h1>);
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	if ( !$user_info ) {
		$self->print_bad_status( { message => q(You are not a recognized user. Rejected isolates are disabled.) } );
		say q(<div style="position:relative;margin-top:-8em">);
		$self->print_related_database_panel;
		say q(</div>);
		return;
	}
	my $rejected_isolates_to_show = $self->_any_rejected_isolates_to_show;
	my $closed_buffer =
	  $self->_print_archived_rejected_isolates( {get_only => 1});
	if ($rejected_isolates_to_show) {
		say q(<div class="box resultstable"><div class="scrollable">);
		$self->_print_pending_rejected_isolates;
		$self->print_rejected_isolates_for_curation;
		$self->print_navigation_bar( { closed_rejected_isolates => $closed_buffer ? 1 : 0 } );
		say q(</div></div>);
	}
	if ($closed_buffer) {
		say q(<div class="box resultstable" id="closed" style="display:none"><div class="scrollable">);
		say q(<h2>Archived rejected isolates</h2>);
		say q(<p>The following rejected isolates are archived:);
		say $closed_buffer;
		say q(</div></div>);
	}
	if (!$rejected_isolates_to_show) {
	    say q(<div class="box resultstable"><div class="scrollable">);
	    say q(<p>No isolates failed the core quality requirements and were rejected.);
	    say q(</div></div>);
	}
	return;
}

sub _any_rejected_isolates_to_show {
	my ($self) = @_;
	return 1 if $self->_get_rejected_table_by_status('pending');
	return 1 if $self->print_rejected_isolates_for_curation();
	return 1 if $self->_get_rejected_table_by_status('archived');
	return;
}

sub _get_rejected_isolates_by_status {
    my ( $self, $status ) = @_;
    my $rejected_isolates = $self->{'datastore'}->run_query( "SELECT * FROM rejected_isolates WHERE status=? ORDER BY id ASC", [$status], { fetch => 'all_arrayref', slice => {}} );
    return $rejected_isolates;
}

sub _get_rejected_table_by_status {
    my ( $self, $status ) = @_;
    my $rejected_isolates = $self->_get_rejected_isolates_by_status($status);

    my $buffer;
    if (@$rejected_isolates) {
        my $td = 1;
        my $table_buffer;
        foreach my $rejected_isolate (@$rejected_isolates) {
            # Split rejection reasons into an array (assuming they are comma-separated)
            my @rejection_reasons = split /,/, $rejected_isolate->{'rejection_reasons'};
            my $rejection_buffer = join '<br>', @rejection_reasons;

            # Create a row for the isolate
            $table_buffer .= qq(<tr class="td$td"><td>$rejected_isolate->{'id'}</td>)
                             . qq(<td>$rejected_isolate->{'isolate'}</td>)
                             . qq(<td>$rejected_isolate->{'insertion_date'}</td>);
            $table_buffer .= qq(<td>$rejected_isolate->{'archival_date'}</td>) if $status eq 'archived';
            $table_buffer .= qq(<td>$rejection_buffer</td>)
                             . qq(<td>$rejected_isolate->{'insertion_type'}</td>);
            $table_buffer .= qq(<td>$rejected_isolate->{'report_link'}</td>) if $status eq 'pending';
            $table_buffer .= q(</tr>);

            $td = $td == 1 ? 2 : 1; # Alternate row styling
        }

        if ($table_buffer) {
            $buffer .= q(<table class="resultstable"><tr><th>Id</th><th>Isolate</th><th>Insertion date</th>);
            $buffer .= q(<th>Archival date</th>) if $status eq 'archived';
            $buffer .= q(<th>Rejection reasons</th><th>Insertion type</th>);
            $buffer .= q(<th>Report</th>) if $status eq 'pending';
            $buffer .= q(</tr>);
            $buffer .= $table_buffer;
            $buffer .= q(</table>);
        }
    }

    return $buffer;
}
sub _print_pending_rejected_isolates {
    my ( $self ) = @_;
	my $buffer = $self->_get_rejected_table_by_status('pending');
	if ($buffer) {
		say q(<h2>Pending rejected isolates</h2>);
		say q(<p>The following isolates that were submitted did not meet the core quality control requirements and are pending for archival:</p>);
		say $buffer;
	} else {
		say q(<p>There are no core qc rejected isolates that are pending for archival</p>);
	}
	return;
}

sub _print_archived_rejected_isolates {
    my ($self, $options) = @_;
	$options = {} if ref $options ne 'HASH';
	my $buffer = $self->_get_rejected_table_by_status('archived');
	if ($buffer) {
		return $buffer if $options->{'get_only'};
	    say $buffer if $buffer;
	}
	return;
}

sub print_rejected_isolates_for_curation {
	my ( $self, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	return if !$user_info || ( $user_info->{'status'} ne 'admin' && $user_info->{'status'} ne 'curator' );
	my $buffer;
	$buffer .= $self->_get_rejected_isolates_for_curation($options);
	return $buffer if $options->{'get_only'};
	say $buffer if $buffer;
	return;
}

sub _get_rejected_isolates_for_curation {
	my ( $self, $options ) = @_;
	my $status = $options->{'status'} // 'pending';
	my $rejected_isolates = $self->_get_rejected_isolates_by_status( $status );
	my $table_buffer;
	my $td = 1;
	foreach my $rejected_isolate (@$rejected_isolates) {
	    # Split rejection reasons into an array (assuming they are comma-separated)
        my @rejection_reasons = split /,/, $rejected_isolate->{'rejection_reasons'};
        my $rejection_buffer = join '<br>', @rejection_reasons;

        my $archive_button = q();

        if ($status eq 'pending') {
            $archive_button = $self->_print_close_rejected_isolate_fieldset($rejected_isolate->{'id'});
        }

        # Create a row for the isolate
        $table_buffer .= qq(<tr class="td$td"><td>$rejected_isolate->{'id'}</td>)
                         . qq(<td>$rejected_isolate->{'isolate'}</td>)
                         . qq(<td>$rejected_isolate->{'insertion_date'}</td>);
        $table_buffer .= qq(<td>$rejected_isolate->{'archival_date'}</td>) if $status eq 'archived';
        $table_buffer .= qq(<td>$rejection_buffer</td>)
                         . qq(<td>$rejected_isolate->{'insertion_type'}</td>);
        $table_buffer .= qq(<td>$rejected_isolate->{'report_link'}</td>) if $status eq 'pending';
        $table_buffer .= qq(<td>$archive_button</td>) if $status eq 'pending';  # Archive button for pending only
        $table_buffer .= q(</tr>);

        $td = $td == 1 ? 2 : 1; # Alternate row styling
        }
	my $return_buffer = q();
	if ($table_buffer) {
        if ( $status eq 'archived' ) {
            $return_buffer .= q(<h3>Rejected isolates</h3>);
        } else {
            $return_buffer .= qq(<h2>New rejected isolates waiting for archival</h2>\n);
            $return_buffer .= qq(<p>Your account is authorized to handle the following rejected isolates:<p>\n);
        }
        $return_buffer .= q(<table class="resultstable"><tr><th>Id</th><th>Isolate</th><th>Insertion date</th>);
        $return_buffer .= q(<th>Archival date</th>) if $status eq 'archived';
        $return_buffer .= q(<th>Rejection reasons</th><th>Insertion type</th>);
        $return_buffer .= q(<th>Report</th>) if $status eq 'pending';
        $return_buffer .= q(<th>Archive</th>) if $status eq 'pending';  # Only show "Archive" column for pending isolates
        $return_buffer .= q(</tr>);
        $return_buffer .= $table_buffer;
        $return_buffer .= q(</table>);
    }
	return $return_buffer;
}

sub print_navigation_bar {
    my ( $self, $options ) = @_;
    my $buffer = q();
    if ( $options->{'closed_rejected_isolates'} ) {
		$buffer .=
			q(<a id="show_closed" style="cursor:pointer;margin-right:1em" class="small_submit">)
		  . q(<span id="show_closed_text" style="display:inline">)
		  . q(<span class="fas fa fa-eye"></span> Show archived rejected isolates</span>)
		  . q(<span id="hide_closed_text" style="display:none">)
		  . q(<span class="fas fa fa-eye-slash"></span> Hide archived rejected isolates</span></a>);
	}
	say $buffer;
	return;
}

sub _print_close_rejected_isolate_fieldset {
	my ( $self, $rejected_isolate_id ) = @_;
	my $q = $self->{'cgi'};
    my $buffer = $q->start_form;
	$q->param( close => 1 );
	$q->param( rejected_isolate_id => $rejected_isolate_id );
    $buffer .= $q->hidden($_) foreach qw( db page rejected_isolate_id close );
	$buffer .= $self->print_action_fieldset( { legend => '', no_reset => 1, submit_label => 'archive', class => 'small_submit', get_only => 1 } );
    $buffer .= $q->end_form;
	return $buffer;
}

sub _close_rejected_isolate {
	my ( $self, $rejected_isolate_id ) = @_;
	return if !$self->_is_rejected_isolate_valid( $rejected_isolate_id, { close => 1, no_message => 1 } );
	my $rejected_isolate = $self->{'submissionHandler'}->get_rejected_isolate($rejected_isolate_id);
	return if !$rejected_isolate || $rejected_isolate->{'status'} eq 'archived';    #Prevent refresh from re-sending E-mail
	my $curator_id = $self->get_curator_id;
    eval {
		$self->{'db'}->do(
		'UPDATE rejected_isolates SET (status,archival_date,curator)=(?,?,?) WHERE id=?',
		undef, 'archived', 'now', $curator_id, $rejected_isolate_id
		);
	};
	if ($@) {
	    print STDERR "error during update of database";
		$logger->error($@);
		$self->{'db'}->rollback;
	} else {
		$self->{'db'}->commit;
	}
	my $dbname = $self->{'datastore'}->run_query('select current_database()');
    $rejected_isolate = $self->{'submissionHandler'}->get_rejected_isolate($rejected_isolate_id);
	return;
}

sub _is_rejected_isolate_valid {
	my ( $self, $rejected_isolate_id, $options ) = @_;
	$options = {} if ref $options ne 'HASH';
	if ( !$rejected_isolate_id ) {
		$self->print_bad_status( { message => q(No rejected isolate id passed.) } ) if !$options->{'no_message'};
		return;
	}
	my $rejected_isolate = $self->{'submissionHandler'}->get_rejected_isolate($rejected_isolate_id);
	if ( !$rejected_isolate ) {
		$self->print_bad_status( { message => qq(Rejected isolate '$rejected_isolate_id' does not exist.) } )
		  if !$options->{'no_message'};
		return;
	}
	my $user_info = $self->{'datastore'}->get_user_info_from_username( $self->{'username'} );
	if ( $options->{'close'} ) {
		if ( !$user_info || ( $user_info->{'status'} ne 'admin' && $user_info->{'status'} ne 'curator' ) ) {
			$self->print_bad_status(
				{
					message => q(Your account does not have the required permissions to close this rejected isolate.)
				}
			) if !$options->{'no_message'};
			return;
		}
	}
	return 1;
}

sub get_title {
	my ($self) = @_;
	return 'Rejected Isolates';
}
1;