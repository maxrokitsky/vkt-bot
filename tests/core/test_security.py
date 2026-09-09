"""``vkt_bot.core.security``."""

from __future__ import annotations

import datetime
import string
from typing import TYPE_CHECKING

import jwt
import pytest

from vkt_bot.core.security import (
    ALGORITHM,
    create_access_token,
    get_password_hash,
    get_random_string,
    verify_password,
)

if TYPE_CHECKING:
    from vkt_bot.config import VktSettings


class TestPasswordHashing:
    """``get_password_hash`` / ``verify_password``."""

    def test_hash_is_not_the_password(self) -> None:
        assert get_password_hash("hunter2") != "hunter2"

    def test_hash_is_bcrypt(self) -> None:
        assert get_password_hash("hunter2").startswith("$2b$")

    def test_verify_correct_password(self) -> None:
        assert verify_password("hunter2", get_password_hash("hunter2")) is True

    def test_verify_wrong_password(self) -> None:
        assert verify_password("wrong", get_password_hash("hunter2")) is False

    def test_hashes_are_salted(self) -> None:
        assert get_password_hash("hunter2") != get_password_hash("hunter2")

    def test_both_hashes_verify(self) -> None:
        password = "hunter2"
        for _ in range(2):
            assert verify_password(password, get_password_hash(password))

    def test_unicode_password(self) -> None:
        password = "пароль-с-юникодом"
        assert verify_password(password, get_password_hash(password))

    def test_empty_password(self) -> None:
        assert verify_password("", get_password_hash(""))

    def test_case_matters(self) -> None:
        assert verify_password("Hunter2", get_password_hash("hunter2")) is False


class TestRandomString:
    """``get_random_string``."""

    def test_default_length(self) -> None:
        assert len(get_random_string()) == 32

    def test_custom_length(self) -> None:
        assert len(get_random_string(8)) == 8

    def test_zero_length(self) -> None:
        assert get_random_string(0) == ""

    def test_only_letters_and_digits(self) -> None:
        allowed = set(string.ascii_letters + string.digits)
        assert set(get_random_string(200)) <= allowed

    def test_values_differ(self) -> None:
        assert get_random_string() != get_random_string()


class TestAccessToken:
    """``create_access_token``."""

    def test_subject_is_encoded(self, settings: VktSettings) -> None:
        token = create_access_token("user@example.com", datetime.timedelta(minutes=5))
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        assert payload["sub"] == "user@example.com"

    def test_non_string_subject_is_stringified(self, settings: VktSettings) -> None:
        token = create_access_token(42, datetime.timedelta(minutes=5))
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        assert payload["sub"] == "42"

    def test_expiry_respects_delta(self, settings: VktSettings) -> None:
        token = create_access_token("u", datetime.timedelta(minutes=5))
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        expires_in = datetime.datetime.fromtimestamp(
            payload["exp"], tz=datetime.UTC
        ) - datetime.datetime.now(datetime.UTC)

        assert (
            datetime.timedelta(minutes=4) < expires_in <= datetime.timedelta(minutes=5)
        )

    def test_expired_token_is_rejected(self, settings: VktSettings) -> None:
        token = create_access_token("u", datetime.timedelta(minutes=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])

    def test_wrong_key_is_rejected(self) -> None:
        token = create_access_token("u", datetime.timedelta(minutes=5))
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, "wrong-key", algorithms=[ALGORITHM])

    def test_algorithm_is_hs256(self) -> None:
        assert ALGORITHM == "HS256"
        token = create_access_token("u", datetime.timedelta(minutes=5))
        assert jwt.get_unverified_header(token)["alg"] == "HS256"
