"""A tiny inventory-reorder helper -- the target repo for the Week 2 pipeline's
Lint -> Test -> AI Code Review stages.
"""


def reorder_quantity(current_stock, reorder_point, target_stock):
    """How many units to order to bring stock back up to target_stock.

    Returns 0 if current_stock is already at or above the reorder point.
    """
    if current_stock >= reorder_point:
        return 0
    return target_stock - current_stock


def days_of_supply(current_stock, daily_usage):
    if daily_usage == 0:
        return float("inf")
    return current_stock / daily_usage


def apply_discount(price, percent_off):
    # NOTE: no bounds check on percent_off -- a value > 100 silently produces a
    # negative price. Left in on purpose so the AI review stage has something
    # substantive to catch beyond style nits.
    return price * (1 - percent_off / 100)
