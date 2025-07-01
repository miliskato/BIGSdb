from typing import Literal, get_args, get_origin


def validate_literal(value, literal_type):
    if not get_origin(literal_type) is Literal:
        raise TypeError(f"{literal_type} is not a Literal type")
    if value in get_args(literal_type):
        return
    raise NameError(f"{value} is not a valid for literal type: {literal_type}")
