import json


def total_value(items):
    return sum(item["price"] * item["qty"] for item in items)


def to_json(items):
    return json.dumps(items)
