from dataclasses import dataclass

@dataclass
class SerotypingData:
    """
    This class stores the serogroup
    """
    serogroup: str

@dataclass
class NeisseriaSerotypingData:
    """
    This class initializes the lists of values for additional serogroup fields for Neisseria
    """
    capsule_serogroup: str

