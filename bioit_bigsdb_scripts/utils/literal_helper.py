from typing import Literal, get_args, get_origin


def validate_literal(value, literal_type) -> None:
    """
    small function to validate that the value used is part of a Literal
    :param value: value to validate
    :param literal_type: the Literal type
    :return: None
    """
    if not get_origin(literal_type) is Literal:
        raise TypeError(f"{literal_type} is not a Literal type")
    if value in get_args(literal_type):
        return
    raise NameError(f"{value} is not a valid for literal type: {literal_type}")
