class BadCollectionError(Exception):
    """
    The collection of the isolate is currently not supported by the inserter
    """

    def __init__(self):
        super().__init__("The inserter only handles 'isolates' and 'badqc' collections.")


class IsolateNotFoundException(Exception):
    """
    The pseudo id doesn't have an equivalent isolate_id in MongoDB
    """

    def __init__(self, pseudo_id: str) -> None:
        """
        :param pseudo_id: the pseudo id of the isolate
        :return: None
        """
        super().__init__(f'The specified isolate with pseudo_id={pseudo_id} does not exist')
