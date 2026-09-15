"""Client names for the browser and the terminal.

The three workshop matters carry a real client name in their payload. The public
CUAD contracts do not: their `matter_name` repeats the document title, and the
only company name in the record is the slug the filing was published under. This
recovers a readable name from that slug, so every chunk can say whose file it
came from and a person can compare it with the client on the question. Naming
the owner of each document is the diagnosis the workshop asks for.
"""

from .questions import MATTERS

SEGMENTS = 3


def client_name(payload):
    """Return the client a chunk belongs to, as a person would read it."""
    matter = payload["matter_id"]
    if matter in MATTERS:
        return MATTERS[matter]["name"]
    return _from_slug(matter)


def _from_slug(matter):
    """The company sits at the front of a CUAD filing slug, before the dates."""
    parts = matter.split("-")
    words = [parts[0]]
    for part in parts[1:SEGMENTS]:
        if any(character.isdigit() for character in part):
            break
        words.append(part)
    return " ".join(words).title()


def demo():
    """Self-check: real slugs from the collection, including the awkward ones."""
    cases = {
        "buffalowildwingsinc-06-05-1998-ex-10-3-franchise": "Buffalowildwingsinc",
        "berkeleylights-inc-06-26-2020-ex-10-12-collabora": "Berkeleylights Inc",
        "array-biopharma-inc-license-development-and-comm": "Array Biopharma Inc",
        "virtualscopics-inc-11-12-2010-ex-10-1-strategic-": "Virtualscopics Inc",
        # A digit in the company itself must not empty the name.
        "n2kinc-10-16-1997-ex-10-16-sponsorship-agreement": "N2Kinc",
    }
    for slug, expected in cases.items():
        got = _from_slug(slug)
        assert got == expected, f"{slug} gave {got!r}, expected {expected!r}"
    assert client_name({"matter_id": "harbor"}) == MATTERS["harbor"]["name"]
    return "display.py self-check passed"


if __name__ == "__main__":
    print(demo())
