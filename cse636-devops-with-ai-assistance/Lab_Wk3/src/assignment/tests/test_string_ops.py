from app.string_ops import slugify, truncate


def test_slugify():
    assert slugify(" Hello World ") == "hello-world"


def test_truncate_short():
    assert truncate("hi", 10) == "hi"


def test_truncate_long():
    assert truncate("hello world", 5) == "hello..."
