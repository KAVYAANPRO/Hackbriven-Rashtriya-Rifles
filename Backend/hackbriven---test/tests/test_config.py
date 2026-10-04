from __future__ import annotations

from backend.config import Settings, _parse_key_pool


def test_parse_key_pool_splits_comma_separated_values():
    assert _parse_key_pool("key1,key2,key3", "") == ["key1", "key2", "key3"]


def test_parse_key_pool_strips_whitespace_and_drops_blanks():
    assert _parse_key_pool(" key1 , , key2,", "") == ["key1", "key2"]


def test_parse_key_pool_falls_back_to_singular_when_plural_unset():
    assert _parse_key_pool("", "legacy-key") == ["legacy-key"]


def test_parse_key_pool_prefers_plural_over_singular_when_both_set():
    assert _parse_key_pool("pool-key", "legacy-key") == ["pool-key"]


def test_parse_key_pool_empty_when_neither_set():
    assert _parse_key_pool("", "") == []


def test_eightscale_key_pool_property_uses_plural_field():
    settings = Settings(eightscale_api_keys="a,b,c", eightscale_api_key="")
    assert settings.eightscale_key_pool == ["a", "b", "c"]


def test_magic_hour_key_pool_property_falls_back_to_legacy_field():
    settings = Settings(magic_hour_api_keys="", magic_hour_api_key="solo-key")
    assert settings.magic_hour_key_pool == ["solo-key"]
