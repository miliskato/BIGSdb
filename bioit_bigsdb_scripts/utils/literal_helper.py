from typing import Literal, get_args, get_origin


def validate_literal(value, literal_type):
    if get_origin(literal_type) is Literal:
        return value in get_args(literal_type)
    raise TypeError(f"{literal_type} is not a Literal type")
