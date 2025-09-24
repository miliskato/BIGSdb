#Written for BIGSdb table rendering
package BIGSdb::UI::IsolateSubmissionsTable;
use strict;
use warnings;
use 5.010;
use BIGSdb::Constants qw(:design);
use Log::Log4perl qw(get_logger);
my $logger = get_logger('BIGSdb.Submissions');

sub new {
    my ($class, $args) = @_;
    return bless $args // {}, $class;
}

sub render_table {
    my ($self, %args) = @_;
    my $submissions = $args{submissions} // [];
    my $status = $args{status} // 'pending';
    my $system = $args{system};
    my $instance = $args{instance};
    my $datastore = $args{datastore};
    my $submissionHandler = $args{submissionHandler};
    my $embargo = $args{embargo} // {};
    my $show_outcome = $args{show_outcome} // 0;

    return q() if !@$submissions;

    my $buffer = q();
    my $td = 1;

    # Generate table rows
    foreach my $submission (@$submissions) {
        next if $submission->{'type'} ne 'isolates' && $submission->{'type'} ne 'genomes';
        next if $submission->{'type'} eq 'genomes' && !$args{can_modify_sequence_bin};

        my $submitter_string = $datastore->get_user_string($submission->{'submitter'}, {email => 1});
        my $isolate_count = $submissionHandler->get_isolate_submission_count($submission->{'id'});

        $buffer .= qq(<tr class="td$td"><td>);
        $buffer .= qq(<input type="checkbox" name="selected_submissions[]" value="$submission->{'id'}" />);
        $buffer .= qq(<a href="$system->{'script_name'}?db=$instance&amp;page=submit&amp;submission_id=$submission->{'id'}&amp;curate=1">$submission->{'id'}</a>);
        $buffer .= qq(</td>);
        $buffer .= qq(<td>$submission->{'date_submitted'}</td>);
        $buffer .= qq(<td>$submission->{'datestamp'}</td>);
        $buffer .= qq(<td>$submitter_string</td>);
        $buffer .= qq(<td>$isolate_count</td>);
        $buffer .= qq(<td class="quality">$submission->{'quality'}</td>);

        if ($system->{'dbtype'} eq 'isolates' && $embargo->{'embargo_enabled'}) {
            my $embargo_months = $submission->{'embargo'} // '-';
            $buffer .= qq(<td>$embargo_months</td>);
        }

        if ($show_outcome) {
            $buffer .= qq(<td>$submission->{'outcome'}</td>);
        }

        $buffer .= qq(</tr>\n);
        $td = $td == 1 ? 2 : 1;
    }

    return $buffer;
}

sub render_complete_form {
    my ($self, %args) = @_;
    my $q           = $self->{'cgi'};
    my $submissions = $args{submissions} // [];
    my $status = $args{status} // 'pending';
    my $system = $args{system};
    my $instance = $args{instance};
    my $embargo = $args{embargo} // {};
    my $show_outcome = $args{show_outcome} // 0;
    $logger->error('I am in render_complete_form');

    # Filter submissions for isolates/genomes
    my @filtered_submissions = grep {
        ($_->{'type'} eq 'isolates') ||
        ($_->{'type'} eq 'genomes' && $args{can_modify_sequence_bin})
    } @$submissions;

    return q() if !@filtered_submissions;

    my $return_buffer = q();

    # Add headers based on status
    if ($status eq 'closed') {
        $return_buffer .= q(<h3>Isolate submissions</h3>);
    } else {
        $return_buffer .= qq(<h2>New isolate submissions waiting for curation</h2>\n);
        $return_buffer .= qq(<p>Your account is authorized to handle the following submissions:</p>\n);
        if ($args{isolate_curate_message}) {
            $return_buffer .= $args{isolate_curate_message};
        }
    }

    $return_buffer .= q(<div class="scrollable">);
    $return_buffer .= q(<form method="post" action="/cgi-bin/bigsdb/bigsdb.pl?page=validation" id="isolateSubmissionsForm" enctype="multipart/form-data">);

    $return_buffer .= q(<input type="hidden" name="db" value="bigsdb_neisseria_isolates">);
    $return_buffer .= q(<input type="hidden" name="page" value="validation">);

    # Add control buttons
    $return_buffer .= q(<button type="button" id="isolateSubmissionsForm_checkAll" onclick="toggleCheckboxes('isolateSubmissionsForm')" data-checked="false">Check All</button> );
    $return_buffer .= q(<button type="button" id="isolateSubmissionsForm_checkGood" onclick="toggleCheckboxesByQuality('isolateSubmissionsForm', 'good')" data-checked="false">Check Good Quality</button> );
    $return_buffer .= q(<button type="button" id="isolateSubmissionsForm_checkWarning" onclick="toggleCheckboxesByQuality('isolateSubmissionsForm', 'warning')" data-checked="false">Check Warning Quality</button> );

    # Start table
    $return_buffer .= q(<table class="resultstable"><tr><th>Submission id</th>);
    $return_buffer .= q(<th>Submitted</th><th>Updated</th><th>Submitter</th><th>Isolates</th><th>Quality</th>);
    $return_buffer .= q(<th>Embargo requested (months)</th>) if $system->{'dbtype'} eq 'isolates' && $embargo->{'embargo_enabled'};
    $return_buffer .= q(<th>Outcome</th>) if $show_outcome;
    $return_buffer .= qq(</tr>\n);

    # Add table rows
    $return_buffer .= $self->render_table(%args, submissions => \@filtered_submissions, show_outcome => $show_outcome);

    # Close table and add controls
    $return_buffer .= q(</table>);
    $return_buffer .= q(<div style="margin-top: 10px;">);
    $return_buffer .= qq(<select id="statusDropdown" name="bulk_status" style="margin-right: 10px;">);
    $return_buffer .= q(<option value="">Select Status...</option>);
    $return_buffer .= q(<option value="pending">Pending</option>);
    $return_buffer .= q(<option value="accepted">Accepted</option>);
    $return_buffer .= q(<option value="rejected">Rejected</option>);
    $return_buffer .= q(</select>);
    $return_buffer .= q(<input type="submit" value="Update" onclick="return validateAndSubmit()">);
    $return_buffer .= q(</div>);
    $return_buffer .= q(</form>);
    $return_buffer .= qq(</div>\n);

    return $return_buffer;
}

1;
