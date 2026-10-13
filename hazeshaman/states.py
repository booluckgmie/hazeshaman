"""Canonical state list and name normalisation for DOE/APIMS-style data."""
import re

STATES = [
    "Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang",
    "Perak", "Perlis", "Pulau Pinang", "Sabah", "Sarawak", "Selangor",
    "Terengganu", "WP Kuala Lumpur", "WP Putrajaya", "WP Labuan",
]

_ALIASES = {
    "penang": "Pulau Pinang", "pulaupinang": "Pulau Pinang", "pinang": "Pulau Pinang",
    "n.sembilan": "Negeri Sembilan", "nsembilan": "Negeri Sembilan", "negerisembilan": "Negeri Sembilan",
    "kl": "WP Kuala Lumpur", "kualalumpur": "WP Kuala Lumpur", "wpkl": "WP Kuala Lumpur",
    "wpkualalumpur": "WP Kuala Lumpur", "wilayahpersekutuankualalumpur": "WP Kuala Lumpur",
    "putrajaya": "WP Putrajaya", "wpputrajaya": "WP Putrajaya",
    "wilayahpersekutuanputrajaya": "WP Putrajaya",
    "labuan": "WP Labuan", "wplabuan": "WP Labuan", "wilayahpersekutuanlabuan": "WP Labuan",
    "malacca": "Melaka", "trengganu": "Terengganu",
}
_CANON = {re.sub(r"[^a-z]", "", s.lower()): s for s in STATES}


def normalise_state(name: str) -> str | None:
    key = re.sub(r"[^a-z.]", "", str(name).lower())
    if key in _ALIASES:
        return _ALIASES[key]
    key = key.replace(".", "")
    return _ALIASES.get(key) or _CANON.get(key)
