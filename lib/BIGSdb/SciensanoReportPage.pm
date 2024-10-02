#Written by Keith Jolley
#Copyright (c) 2010-2024, University of Oxford
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
package BIGSdb::SciensanoReportPage;
use strict;
use warnings;
use 5.010;
use parent qw(BIGSdb::Page);
use BIGSdb::Constants qw(:interface :limits COUNTRIES DEFAULT_CODON_TABLE NULL_TERMS);
use BIGSdb::JSContent;
use Log::Log4perl qw(get_logger);
use Try::Tiny;
use List::MoreUtils qw(none uniq);
use HTTP::Request ();
use JSON;
use Template;
use Bio::Tools::CodonTable;
use Data::Dumper;
my $logger = get_logger('BIGSdb.Page');
use constant ISOLATE_SUMMARY     => 1;
use constant LOCUS_SUMMARY       => 2;
use constant MAX_DISPLAY         => 1000;
use constant HIDE_PMIDS          => 4;
use constant HIDE_PROJECT_LENGTH => 50;

sub set_pref_requirements {
	my ($self) = @_;
	$self->{'pref_requirements'} =
	  { general => 1, main_display => 0, isolate_display => 1, analysis => 0, query_field => 0 };
	return;
}

sub get_help_url {
	my ($self) = @_;
	return "$self->{'config'}->{'doclink'}/data_records.html#isolate-records";
}

sub initiate {
	my ($self) = @_;
	my $q = $self->{'cgi'};
	my $get_zip  = $q->param('get_zip');

	if ($get_zip == 'yes') {
		$self->{'type'} = 'tar';
	} else {
		$self->{'type'} = 'no_header';
	}

	$self->{'noCache'} = 1;

	return;
}

sub print_page_content {

	my ($self) = @_;
	my $q = $self->{'cgi'};
	my $isolate_id   = $q->param('id');
	my $get_zip  = $q->param('get_zip');
	my $content_type = 'text/html';

	if ($get_zip eq 'yes') {
		$content_type = 'application/zip';
	}

	my $identifier;
	if (defined($isolate_id)){
		$self->{'isolate_data'} = $self->{'datastore'}->run_query( "SELECT * FROM $self->{'system'}->{'view'} WHERE id=?", $isolate_id, { fetch => 'row_hashref' } );
		 $identifier = $self->{'isolate_data'}->{'isolate'};
	}

	$q->charset('UTF-8');
	if ( !$q->cookie( -name => 'guid' ) && $self->{'prefstore'} ) {
		my $guid = $self->{'prefstore'}->get_new_guid;
		push @{ $self->{'cookies'} },
		  $q->cookie(
			-name     => 'guid',
			-value    => $guid,
			-expires  => '+10y',
			-httponly => 1,
			-secure   => $self->{'config'}->{'secure_cookies'} ? 1 : 0
		  );
		$self->{'setOptions'} = 1;
	}
	my %header_options;
	$header_options{'-cookie'}  = $self->{'cookies'} if $self->{'cookies'};
	$header_options{'-expires'} = '+1h'              if !$self->{'noCache'};

	$header_options{'-type'} = $content_type;

	if ($content_type eq 'application/zip') {
		$header_options{'-attachment'} = 'report-'.$isolate_id.'-'.$identifier.'.zip';
	}
	my %utf8_types = map { $_ => 1 } qw(no_header text json);
	binmode STDOUT, ':encoding(utf8)' if $utf8_types{ $self->{'type'} };
	print $q->header( \%header_options );

	$self->print_content;
}

sub print_content {
	my ($self)      = @_;
	my $q           = $self->{'cgi'};
	my $isolate_id  = $q->param('id');
	my $pseudo_id   = $q->param('pseudo_id');

	my $has_isolate_id = (defined $isolate_id);# && ($isolate_id ne '');
	my $has_pseudo_id = (defined $pseudo_id);# && $pseudo_id ne '');

	if ( $self->{'system'}->{'dbtype'} ne 'isolates' ) {
		say q(<h1>Isolate information</h1>);
		$self->print_bad_status({ message => q(This function can only be called for isolate databases.) });
		return;
	}

	my $data;

	if ( !$has_isolate_id && !$has_pseudo_id ) {
		say q(<h1>Isolate information</h1>);
	 	say q(<div class="box statusbad"><p>No isolate id provided.</p></div>);
	 	return;
	 } elsif ( $has_isolate_id eq "1" && !BIGSdb::Utils::is_int($isolate_id)) {
	 	say q(<h1>Isolate information</h1>);
	 	$self->print_bad_status( { message => q(Isolate id must be an integer.) } );
	 	return;
	} elsif ( $has_isolate_id eq "1" ) {
	 	$data = $self->{'isolate_data'};
	 	if (!$self->{'isolate_data'}) {
	 		say qq(<h1>Isolate information: id-$isolate_id</h1>);
	 		$self->print_bad_status( { message => q(The database contains no record of this isolate.) } );
	 		return;
	 	}
	 	elsif (!$self->is_allowed_to_view_isolate($isolate_id)) {
	 		say q(<h1>Isolate information</h1>);
	 		$self->print_bad_status( { message => q(Your user account does not have permission to view this record.) } );
	 		return;
	 	}
	 }

	my $bigsdb_users_auth = $self->{'cgi'}->cookie( -name => 'global_bigsdb_users_auth' );

	my $identifier;
	if (!$has_pseudo_id) {
		$pseudo_id = $self->get_pseudo_id();
		if (( $data->{ $self->{'system'}->{'labelfield'} } // q()) ne q()) {
			my $field = $self->{'system'}->{'labelfield'};
			$field =~ tr/_/ /;
			$identifier = qq($field $data->{lc($self->{'system'}->{'labelfield'})} (id:$data->{'id'}));
		}
		else {
			$identifier = qq(id $data->{'id'});
		}
	}

	# Call azure to get token
	my $login_url = 'http://172.23.3.72:9090/login';

	my $ua = LWP::UserAgent->new();
	my $login_response = $ua->post(
		$login_url,
		Content_Type => 'form-data',
		Content =>
		{
			'email' => 'bioit@sciensano.be',
			'password' => $bigsdb_users_auth
		}
	);

	if (!$login_response->is_success) {
		my $mess = $login_response->message;
		say qq(Unable to authenticate to report api: $mess);
		return
	}

	my $login_response_data = decode_json($login_response->content);
	my $report_api_token = $login_response_data->{token};

	my $description = $self->{'system'}->{'description'};
	my $species = lc($description =~ s/ isolates//r);

	my $dtap=get_dtap();

	my $res_time = 'null';
		if ($q->param('submit_date')) {
			$res_time = $q->param('submit_date')
		}
	my $validation_type = 'null';
		if ($q->param('validation_type')) {
			$validation_type = $q->param('validation_type');
		}

	my $get_zip  = $q->param('get_zip');
	if ($get_zip != 'yes') {
		$get_zip = 'no';
	}

	# Call azure to fetch report
	my $report_url = "http://172.23.3.72:9090/get_html_report?isolate_id=".$pseudo_id.'&date='.$res_time."&species=".$species."&get_zip=".$get_zip."&dtap=".$dtap."&validation_type=".$validation_type;
	my $report_response = $ua->get(
		$report_url,
		'x-access-token' => $report_api_token
	);

	my $content = $report_response->content;
	if ($report_response->is_success) {
		$content =~ s/<td>$pseudo_id<\/td>/<td>$pseudo_id - $identifier<\/td>/;
		say $content;
	} else {
		my $mess = $report_response->message;
		my $code = $report_response->code;
		say qq(<p>Unable to generate report: $mess ($code)</p>);
		say qq(<p>$content</p>);
		return
	}
	return;
}

sub get_dtap {
	my $hostname = $ENV{HTTP_HOST};
	my @dtap_match=$hostname =~ m/dev|test|acc|prod/g;
	my $dtap_found = $dtap_match[0];
	return $dtap_found;
}

sub get_pseudo_id {
    my ($self)     = @_;
    my $q          = $self->{'cgi'};
    my $isolate_id = $q->param('id');
    my $data =
      $self->{'datastore'}->run_query( "SELECT * FROM isolates LEFT JOIN mapping_table ON isolates.isolate = mapping_table.isolate WHERE id=?", $isolate_id, { fetch => 'row_hashref' } );
    my $identifier = $data->{'pseudo_id'};  # defaults to / if empty
	return $identifier;
}

sub get_title {
	my ( $self, $options ) = @_;
	return 'Isolate information' if $options->{'breadcrumb'};
	my $q          = $self->{'cgi'};
	my $isolate_id = $q->param('id');
	return q()                   if $q->param('no_header');
	return q(Invalid isolate id) if !BIGSdb::Utils::is_int($isolate_id);
	my $name  = $self->get_name($isolate_id);
	my $title = qq(Isolate information: id-$isolate_id);
	local $" = q( );
	$title .= qq( ($name)) if $name;
	$title .= qq( - $self->{'system'}->{'description'});
	return $title;
}

sub get_name {
	my ( $self, $isolate_id ) = @_;
	return if $self->{'system'}->{'dbtype'} ne 'isolates';
	return $self->{'datastore'}
	  ->run_query( "SELECT $self->{'system'}->{'labelfield'} FROM $self->{'system'}->{'view'} WHERE id=?",
		$isolate_id );
}

1;
