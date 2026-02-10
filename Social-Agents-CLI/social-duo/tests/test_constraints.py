from social_duo.core.config import default_config
from social_duo.core.constraints import validate_text


def test_constraints_basic():
    config = default_config()
    issues, metrics = validate_text(
        "Hello world #one #two #three",
        config=config,
        platform="x",
        cta_required=False,
        cta_text=None,
    )
    assert metrics["hashtag_count"] == 3
    assert any("Too many hashtags" in i for i in issues)


def test_constraints_cta():
    config = default_config()
    issues, metrics = validate_text(
        "Short post",
        config=config,
        platform="linkedin",
        cta_required=True,
        cta_text="Sign up",
    )
    assert metrics["cta_present"] is False
    assert any("CTA required" in i for i in issues)
