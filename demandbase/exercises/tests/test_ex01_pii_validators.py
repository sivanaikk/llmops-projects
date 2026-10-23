import pytest


@pytest.fixture
def m(impl):
    return impl("ex01_pii_validators")


@pytest.mark.parametrize("card", ["4111 1111 1111 1111", "5500-0000-0000-0004", "378282246310005"])
def test_valid_cards(m, card):
    assert m.luhn_ok(card)


@pytest.mark.parametrize("not_card", ["4111 1111 1111 1112", "1234 5678 9012 3456", "20261023120000", "12345", "abcd"])
def test_rejects_non_cards(m, not_card):
    assert not m.luhn_ok(not_card)


def test_iban(m):
    assert m.iban_ok("GB82 WEST 1234 5698 7654 32")
    assert m.iban_ok("de89370400440532013000")
    assert not m.iban_ok("GB82 WEST 1234 5698 7654 33")  # checksum off by one
    assert not m.iban_ok("GB82")


def test_find_ibans_in_text(m):
    text = "Pay GB82 WEST 1234 5698 7654 32 today, not GB82 WEST 1234 5698 7654 33. Ref ORDER-2026."
    assert m.find_ibans(text) == ["GB82 WEST 1234 5698 7654 32"]
