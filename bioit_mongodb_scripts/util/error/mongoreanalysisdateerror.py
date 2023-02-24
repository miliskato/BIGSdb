class MongoReanalysisDateError(Exception):
    """
    The date of the reanalysis that is being inserted is not more recent than the previous analysis.
    """
