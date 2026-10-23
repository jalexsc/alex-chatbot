import pytest

from app.identifiers import is_valid_isbn, is_valid_isbn10, is_valid_isbn13, is_valid_issn


@pytest.mark.parametrize("value", ["0306406152", "0-306-40615-2", "0-8044-2957-X"])
def test_valid_isbn10(value):
    assert is_valid_isbn10(value)


@pytest.mark.parametrize("value", ["9780306406157", "978-0-306-40615-7", "978 0 306 40615 7"])
def test_valid_isbn13(value):
    assert is_valid_isbn13(value)


@pytest.mark.parametrize("value", ["0306406153", "9780306406158", "abc", "", "123"])
def test_invalid_isbn(value):
    assert not is_valid_isbn(value)


@pytest.mark.parametrize("value", ["0378-5955", "03785955", "0317-8471"])
def test_valid_issn(value):
    assert is_valid_issn(value)


@pytest.mark.parametrize("value", ["0378-5956", "1234567", "ABCD-1234"])
def test_invalid_issn(value):
    assert not is_valid_issn(value)
