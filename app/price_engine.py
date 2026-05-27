"""
price_engine.py
---------------
Pure, stateless calculation functions for the Buea Market Watch pricing core.

No database access occurs here — all functions are plain Python and are fully
unit-testable in isolation.
"""


def calculate_fair_threshold(bulk_price: int, units_per_bulk: int) -> int:
    """
    Compute the maximum fair retail price per unit (the "Fair Trade Threshold").

    Formula
    -------
        threshold = round((bulk_price / units_per_bulk) * 1.10)

    Parameters
    ----------
    bulk_price : int
        INS wholesale price for the full bulk package, in FCFA.
    units_per_bulk : int
        Number of base retail units that fit in one bulk package
        (e.g. 300 cups in a 50 kg bag of Garri).

    Returns
    -------
    int
        Maximum fair retail price per unit, rounded to the nearest FCFA.

    Raises
    ------
    ValueError
        If ``units_per_bulk`` is 0 (division-by-zero guard).

    Examples
    --------
    >>> calculate_fair_threshold(30_000, 300)
    110
    >>> calculate_fair_threshold(20_000, 40)
    550
    """
    if units_per_bulk == 0:
        raise ValueError("Units per bulk cannot be zero")

    raw = (bulk_price / units_per_bulk) * 1.10
    return round(raw)


def evaluate_submission(submitted_price: int, threshold: int) -> bool:
    """
    Determine whether a submitted unit price constitutes a pricing anomaly.

    Parameters
    ----------
    submitted_price : int
        Price the student observed at the point of sale, in FCFA per unit.
    threshold : int
        Fair Trade Threshold returned by :func:`calculate_fair_threshold`.

    Returns
    -------
    bool
        ``True``  → anomaly (price exceeds threshold) → RED alert
        ``False`` → fair price                        → GREEN badge

    Examples
    --------
    >>> evaluate_submission(111, 110)
    True
    >>> evaluate_submission(110, 110)
    False
    >>> evaluate_submission(105, 110)
    False
    """
    return submitted_price > threshold


def get_ui_color_code(is_anomaly: bool) -> str:
    """
    Map an anomaly boolean to the UI color token string.

    Parameters
    ----------
    is_anomaly : bool
        Output of :func:`evaluate_submission`.

    Returns
    -------
    str
        ``"RED"`` for price-gouging alert, ``"GREEN"`` for fair vendor.
    """
    return "RED" if is_anomaly else "GREEN"
