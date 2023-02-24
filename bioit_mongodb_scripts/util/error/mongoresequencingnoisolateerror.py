class MongoResequencingNoIsolateError(Exception):
    """
    Warning displayed if a resequencing is submitted and no sample is in the isolate collection.
    """
