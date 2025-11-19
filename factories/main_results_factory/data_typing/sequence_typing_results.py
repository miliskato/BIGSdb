from dataclasses import dataclass


@dataclass
class SequenceTypingData:
    """
    This class initializes the lists of values for common ST fields.
    """
    cgst: str
    st: str
    rst: str


@dataclass
class ListeriaSequenceTypingData:
    """
    This class initializes the lists of values for ST fields specific to Listeria
    """
    cc: str
    lineage: str


@dataclass
class NeisseriaSequenceTypingData:
    """
    This class initializes the lists of values for ST fields specific to Neisseria
    """
    pora_vr1: str
    pora_vr2: str
    porb: str
