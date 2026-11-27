"""Format and parse decimal values at the desktop input boundary."""

from math import isfinite

from PySide6.QtCore import QLocale

_SHORTEST = QLocale.FloatingPointPrecisionOption.FloatingPointShortest.value


def _decimal_locale(locale: QLocale) -> QLocale:
    numbers = QLocale(locale)
    numbers.setNumberOptions(
        numbers.numberOptions()
        | QLocale.NumberOption.OmitGroupSeparator
        | QLocale.NumberOption.RejectGroupSeparator
    )
    return numbers


def format_decimal(value: float, locale: QLocale, precision: int = _SHORTEST) -> str:
    return _decimal_locale(locale).toString(float(value), "g", precision)


def parse_decimal(text: str, locale: QLocale) -> float:
    number, valid = _decimal_locale(locale).toDouble(text.strip())
    if not valid or not isfinite(number):
        example = format_decimal(1.5, locale)
        raise ValueError(f"Enter a finite number such as {example} without grouping separators.")
    return number
