from app.inventory_ops import total_value, to_json


def test_total_value():
    items = [{"price": 2.0, "qty": 3}, {"price": 5.0, "qty": 1}]
    assert total_value(items) == 11.0


def test_to_json():
    assert to_json([{"a": 1}]) == '[{"a": 1}]'
