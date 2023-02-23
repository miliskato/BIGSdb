class MongoValueError(ValueError):
    """
    Basic class for mongo errors when not getting the right value.
    """


class MongoMissingValueIsolateCollectionError(MongoValueError):
    """
    Missing isolate in the isolate collection.
    """


class MongoReanalysisDateError(MongoValueError):
    """
    The date of the reanalysis that is being inserted is not more recent than the previous analysis.
    """

class MongoResequencingAlreadyExistsError(MongoValueError):
    """
    The resequencing being inserted already exists
    """