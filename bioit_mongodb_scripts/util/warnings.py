class MongoWarnings(UserWarning):
    """
    Basic class for warnings
    """


class MongoResequencingNoIsolateWarning(MongoWarnings):
    """
    Warning displayed if a resequencing is submitted and no sample is in the isolate collection.
    """
class MongoTooManyResequencingsWarning(MongoWarnings):
    """
    Warning displayed if a resequencing is submitted and no sample is in the isolate collection.
    """