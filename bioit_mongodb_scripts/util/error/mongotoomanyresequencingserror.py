class MongoTooManyResequencingsError(Exception):
    """
    Warning displayed if a resequencing is submitted and an unvalidated resequencing is already present.
    """
