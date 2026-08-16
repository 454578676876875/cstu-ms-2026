from app import reorder_quantity, days_of_supply, apply_discount


def test_reorder_quantity_below_point():
    assert reorder_quantity(current_stock=5, reorder_point=10, target_stock=50) == 45


def test_reorder_quantity_at_or_above_point():
    assert reorder_quantity(current_stock=10, reorder_point=10, target_stock=50) == 0
    assert reorder_quantity(current_stock=20, reorder_point=10, target_stock=50) == 0


def test_days_of_supply():
    assert days_of_supply(current_stock=100, daily_usage=25) == 4


def test_days_of_supply_zero_usage():
    assert days_of_supply(current_stock=100, daily_usage=0) == float("inf")


def test_apply_discount():
    assert apply_discount(100, 20) == 80
