# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0]

### Added
- SciensanoReportPage.pm to download the report directly from BIGSdb as previous solution was not working under BIGSdb 1.48

### Change
- Reports are not stored on the local VM, they need to be called from AZURE api
- Computation of the cgmlst matrix is done on AZURE
- html tagger is running on AZURE
- BIGSdb was upload from V1.36 -> V1.47
- Local MongoDB hosts the mapping table for pseudonymization and the other collections are stored in MongoDB Atlas

### Bugfix
- API call for Download/visualisation of the html reports 
- Sequence bin plugin in BIGSdb

### Removed
- Uploading of the pipeline's reports directly from galaxy
- Possibility to accept resequencing (disabled for now)

## [1.0.0] - 2024-04-27 
- Local version of the NRC platform as deployed on nrcnei-prod

## [0.0.0]
- Local earliest developments of the NRC platform not deployed on any prod instance