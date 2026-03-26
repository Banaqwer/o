"""
Zodiac signs, elements, qualities, and duad calculations.

Each sign spans 30 degrees. Signs are numbered 0-11 starting at Aries.
Duads: each sign is divided into 12 equal parts of 2.5 degrees each.
  The first duad of a sign has the same sign as the sign itself.
  Subsequent duads follow the natural zodiac order.
Decanates: each sign divided into 3 parts of 10 degrees.

Book references: Lessons 1, 2, 3, 15, 16, 21, 22, 23, 24, 25
"""

# Signs in natural zodiac order (index = sign number 0-11)
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Elements (triplicities): Fire, Earth, Air, Water
ELEMENTS = {
    "Fire":  ["Aries", "Leo", "Sagittarius"],
    "Earth": ["Taurus", "Virgo", "Capricorn"],
    "Air":   ["Gemini", "Libra", "Aquarius"],
    "Water": ["Cancer", "Scorpio", "Pisces"],
}

# Qualities (quadratures): Cardinal, Fixed, Mutable
QUALITIES = {
    "Cardinal": ["Aries", "Cancer", "Libra", "Capricorn"],
    "Fixed":    ["Taurus", "Leo", "Scorpio", "Aquarius"],
    "Mutable":  ["Gemini", "Virgo", "Sagittarius", "Pisces"],
}

# Reverse lookups: sign -> element/quality
SIGN_ELEMENT = {sign: elem for elem, signs in ELEMENTS.items() for sign in signs}
SIGN_QUALITY = {sign: qual for qual, signs in QUALITIES.items() for sign in signs}

# Grouped by element and quality for scan usage
ELEMENT_SIGNS = ELEMENTS   # alias
QUALITY_SIGNS = QUALITIES  # alias


def get_sign_from_degrees(longitude_deg: float) -> str:
    """Return zodiac sign name from ecliptic longitude (0-360 degrees)."""
    index = int(longitude_deg % 360 / 30)
    return SIGNS[index]


def get_sign(longitude_deg: float) -> str:
    return get_sign_from_degrees(longitude_deg)


def get_element(sign_or_longitude) -> str:
    """Return element for a sign name or ecliptic longitude."""
    if isinstance(sign_or_longitude, (int, float)):
        sign = get_sign(sign_or_longitude)
    else:
        sign = sign_or_longitude
    return SIGN_ELEMENT[sign]


def get_quality(sign_or_longitude) -> str:
    """Return quality for a sign name or ecliptic longitude."""
    if isinstance(sign_or_longitude, (int, float)):
        sign = get_sign(sign_or_longitude)
    else:
        sign = sign_or_longitude
    return SIGN_QUALITY[sign]


def get_duad(longitude_deg: float) -> str:
    """
    Return the duad sign for a given ecliptic longitude.

    Each sign (30 deg) contains 12 duads of 2.5 degrees each.
    The first duad of a sign has the same rulership as the sign.
    Subsequent duads follow the natural zodiac starting from that sign.

    Example from Lesson 2: Sun/Moon at 6°22' Virgo (sign index=5).
    Virgo starts at 150°. Position within sign = 6.37°.
    Duad index = int(6.37 / 2.5) = 2  (0-indexed).
    First duad of Virgo = Virgo (index 5).
    Duad sign = SIGNS[(5 + 2) % 12] = SIGNS[7] = Scorpio. ✓
    """
    longitude_deg = longitude_deg % 360
    sign_index = int(longitude_deg / 30)
    pos_in_sign = longitude_deg - sign_index * 30   # 0..30
    duad_index = int(pos_in_sign / 2.5)             # 0..11
    duad_sign_index = (sign_index + duad_index) % 12
    return SIGNS[duad_sign_index]


def next_sign_in_element(sign: str, element: str) -> str:
    """Return the next sign of the same element after the given sign."""
    elem_signs = ELEMENTS[element]
    idx = elem_signs.index(sign)
    return elem_signs[(idx + 1) % len(elem_signs)]


def next_sign_in_quality(sign: str, quality: str) -> str:
    """Return the next sign of the same quality after the given sign."""
    qual_signs = QUALITIES[quality]
    idx = qual_signs.index(sign)
    return qual_signs[(idx + 1) % len(qual_signs)]
