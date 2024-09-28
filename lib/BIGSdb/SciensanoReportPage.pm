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
use parent qw(BIGSdb::TreeViewPage);
use BIGSdb::Constants qw(:interface :limits COUNTRIES DEFAULT_CODON_TABLE NULL_TERMS);
use BIGSdb::JSContent;
use Log::Log4perl qw(get_logger);
use Try::Tiny;
use List::MoreUtils qw(none uniq);
use JSON;
use Template;
use Bio::Tools::CodonTable;
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
	if ( $self->{'cgi'}->param('no_header') ) {
		$self->{'type'}    = 'no_header';
		$self->{'noCache'} = 1;
		return;
	}
	$self->{$_} = 1 foreach qw(jQuery jQuery.jstree jQuery.columnizer);
	my $field_attributes = $self->{'xmlHandler'}->get_all_field_attributes;
	foreach my $field ( keys %$field_attributes ) {
		if ( $field_attributes->{$field}->{'type'} eq 'geography_point'
			|| ( $field_attributes->{$field}->{'geography_point_lookup'} // q() ) eq 'yes' )
		{
			$self->{'ol'} = 1;
			last;
		}
	}
	$self->set_level1_breadcrumbs;
	return;
}

sub print_content {
	my ($self)      = @_;
	my $q           = $self->{'cgi'};
	my $isolate_id  = $q->param('id');
	my $set_id      = $self->get_set_id;
	my $scheme_data = $self->{'datastore'}->get_scheme_list( { set_id => $set_id } );
	if ( !defined $isolate_id || $isolate_id eq '' ) {
		say q(<h1>Isolate information</h1>);
		say q(<div class="box statusbad"><p>No isolate id provided.</p></div>);
		return;
	} elsif ( !BIGSdb::Utils::is_int($isolate_id) ) {
		say q(<h1>Isolate information</h1>);
		$self->print_bad_status( { message => q(Isolate id must be an integer.) } );
		return;
	}
	if ( $self->{'system'}->{'dbtype'} ne 'isolates' ) {
		say q(<h1>Isolate information</h1>);
		$self->print_bad_status( { message => q(This function can only be called for isolate databases.) } );
		return;
	}
	my $data =
	  $self->{'datastore'}
	  ->run_query( "SELECT * FROM $self->{'system'}->{'view'} WHERE id=?", $isolate_id, { fetch => 'row_hashref' } );
	if ( !$data ) {
		say qq(<h1>Isolate information: id-$isolate_id</h1>);
		$self->print_bad_status( { message => q(The database contains no record of this isolate.) } );
		return;
	} elsif ( !$self->is_allowed_to_view_isolate($isolate_id) ) {
		say q(<h1>Isolate information</h1>);
		$self->print_bad_status(
			{
				message => q(Your user account does not have permission to view this record.),
			}
		);
		return;
	}
	my $identifier;
	if ( ( $data->{ $self->{'system'}->{'labelfield'} } // q() ) ne q() ) {
		my $field = $self->{'system'}->{'labelfield'};
		$field =~ tr/_/ /;
		$identifier = qq($field $data->{lc($self->{'system'}->{'labelfield'})} (id:$data->{'id'}));
	} else {
		$identifier = qq(id $data->{'id'});
	}

	say qq(<h1>Report for $identifier</h1>);
	# ICI
	say q(<div class="box" id="resultspanel">);
	say q(wololo);
	$self->display_pseudo_id();

	# Call azure to get token

	# Call azure to fetch report

	say q(</div>);
	return;
}

sub display_pseudo_id {
    my ($self)     = @_;
    my $q          = $self->{'cgi'};
    my $isolate_id = $q->param('id');
    my $data =
      $self->{'datastore'}
      ->run_query( "SELECT * FROM isolates LEFT JOIN mapping_table ON isolates.isolate = mapping_table.isolate WHERE id=?", $isolate_id, { fetch => 'row_hashref' } );
    my $identifier = $data->{'pseudo_id'};  # defaults to / if empty
    say qq(<p>Pseudo id: $identifier</p>);
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
