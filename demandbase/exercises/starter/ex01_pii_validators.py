"""Exercise 01: validators that cut PII false positives.   (concept: 02-guardrails/LEARN.md)

A regex like 13-19 digits catches every card number, and also order IDs,
timestamps and phone numbers. Redacting those breaks legitimate prompts.
Checksums fix it.

1. luhn_ok(text): True if the digits in `text` (spaces/dashes allowed) pass the
   Luhn check: from the rightmost digit, double every second digit, subtract 9 if
   the result > 9, sum everything; valid if sum % 10 == 0. Fewer than 12 digits -> False.

2. iban_ok(text): True for a valid IBAN (spaces allowed, case-insensitive):
   - 15-34 alphanumerics, starts with 2 letters + 2 digits
   - move the first 4 chars to the end, replace letters with numbers (A=10 ... Z=35),
     and the resulting integer mod 97 must equal 1

3. find_ibans(text): list of valid IBANs found in free text (as they appear),
   using a regex for candidates plus iban_ok.

Run:  make check EX=01
"""


def luhn_ok(text: str) -> bool:
    raise NotImplementedError


def iban_ok(text: str) -> bool:
    raise NotImplementedError


def find_ibans(text: str) -> list[str]:
    raise NotImplementedError
