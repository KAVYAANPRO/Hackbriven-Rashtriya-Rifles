from __future__ import annotations

import base64
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services import image_generator


def _fake_jpeg_bytes(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(120, 180, 240)).save(buf, format="JPEG")
    return buf.getvalue()


def _fake_square_jpeg_bytes(size: int = 1920) -> bytes:
    return _fake_jpeg_bytes(size, size)


def _base_settings(mock_settings, **overrides):
    """Settings used by the original NVIDIA -> Pollinations -> placeholder tests: the newer
    providers (Cloudflare, OpenRouter) are switched off and nothing cools down."""
    mock_settings.has_cloudflare = False
    mock_settings.cloudflare_image_model_list = []
    mock_settings.openrouter_api_key = ""
    mock_settings.openrouter_key_pool = []
    mock_settings.openrouter_image_model_list = []
    mock_settings.provider_cooldown_seconds = 0
    mock_settings.image_use_pollinations = True
    mock_settings.nvidia_image_timeout_seconds = 25.0
    mock_settings.cloudflare_flux_steps = 8
    mock_settings.image_provider_list = ["cloudflare", "openrouter", "nvidia", "pollinations"]
    mock_settings.cloudflare_account_pool = []
    for key, value in overrides.items():
        setattr(mock_settings, key, value)
    if overrides.get("has_cloudflare") and "cloudflare_account_pool" not in overrides:
        mock_settings.cloudflare_account_pool = [(overrides.get("cloudflare_account_id", "a"), overrides.get("cloudflare_api_token", "t"))]
    return mock_settings


@pytest.fixture(autouse=True)
def _reset_pollinations_pacing():
    image_generator._pollinations_last_call_at = 0.0
    yield
    image_generator._pollinations_last_call_at = 0.0


@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_generate_image_uses_nvidia_when_available(mock_client_cls, mock_settings, tmp_path: Path):
    mock_settings.nvidia_api_key = "fake-key"
    mock_settings.nvidia_image_model = "black-forest-labs/flux.1-dev"
    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    mock_settings.provider_timeout_seconds = 5.0
    _base_settings(mock_settings)

    # NVIDIA's hosted models only accept enumerated dimensions (live-confirmed
    # with FLUX.1-dev), so _call_nvidia requests a fixed non-target size and
    # center-crops - the fake response must be a real decodable image, not
    # opaque bytes, and the saved output must end up at the target size.
    fake_image_bytes = _fake_jpeg_bytes(768, 1344)
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"image": base64.b64encode(fake_image_bytes).decode()}

    client = MagicMock()
    client.post.return_value = response
    mock_client_cls.return_value.__enter__.return_value = client

    out_path = tmp_path / "scene_00.png"
    result = image_generator.generate_image("ev charging at home", out_path)

    assert result == out_path
    with Image.open(out_path) as saved:
        assert saved.size == (1080, 1920)

    requested_payload = client.post.call_args.kwargs["json"]
    assert requested_payload["width"] == image_generator._NVIDIA_REQUEST_WIDTH
    assert requested_payload["height"] == image_generator._NVIDIA_REQUEST_HEIGHT


@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_generate_image_falls_back_to_pollinations(mock_client_cls, mock_settings, tmp_path: Path):
    mock_settings.nvidia_api_key = "fake-key"
    mock_settings.nvidia_image_model = "model"
    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    mock_settings.provider_timeout_seconds = 5.0
    _base_settings(mock_settings)

    client = MagicMock()
    client.post.side_effect = RuntimeError("nvidia quota exceeded")

    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.content = _fake_square_jpeg_bytes(1920)
    client.get.return_value = fake_response

    mock_client_cls.return_value.__enter__.return_value = client

    out_path = tmp_path / "scene_00.png"
    result = image_generator.generate_image("ev charging at home", out_path)

    assert result == out_path
    with Image.open(out_path) as saved:
        assert saved.size == (1080, 1920)

    # Pollinations' free tier now 402s on any non-square size or nologo=true
    # (live-confirmed, undocumented) - request must stay square, no nologo.
    requested_url = client.get.call_args[0][0]
    assert "width=1920&height=1920" in requested_url
    assert "nologo" not in requested_url


def test_center_crop_produces_exact_target_size():
    square = Image.new("RGB", (1920, 1920))
    cropped = image_generator._center_crop(square, 1080, 1920)
    assert cropped.size == (1080, 1920)


def test_center_crop_is_centered_horizontally():
    # Left half red, right half blue; a centered crop of a square this wide
    # relative to the target should keep both halves partially visible.
    square = Image.new("RGB", (1920, 1920))
    for x in range(1920):
        for y in (0,):
            square.putpixel((x, y), (255, 0, 0) if x < 960 else (0, 0, 255))
    cropped = image_generator._center_crop(square, 1080, 1920)
    left_pixel = cropped.getpixel((0, 0))
    right_pixel = cropped.getpixel((1079, 0))
    assert left_pixel == (255, 0, 0)
    assert right_pixel == (0, 0, 255)


def _http_402_error() -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://image.pollinations.ai/prompt/x")
    response = httpx.Response(402, request=request)
    return httpx.HTTPStatusError("402 Payment Required", request=request, response=response)


@patch("backend.services.image_generator.time.sleep")
@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_call_pollinations_retries_on_402_then_succeeds(mock_client_cls, mock_settings, mock_sleep, tmp_path: Path):
    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    mock_settings.provider_timeout_seconds = 5.0
    _base_settings(mock_settings)

    ok_response = MagicMock()
    ok_response.raise_for_status.return_value = None
    ok_response.content = _fake_square_jpeg_bytes(1920)

    client = MagicMock()

    def get_side_effect(*_args, **_kwargs):
        if client.get.call_count <= 2:
            raise _http_402_error()
        return ok_response

    client.get.side_effect = get_side_effect
    mock_client_cls.return_value.__enter__.return_value = client

    out_path = tmp_path / "scene_00.png"
    result = image_generator._call_pollinations("a red apple", out_path)

    assert result == out_path
    assert client.get.call_count == 3
    assert mock_sleep.call_count == 2


@patch("backend.services.image_generator.time.sleep")
@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_call_pollinations_gives_up_after_max_attempts(mock_client_cls, mock_settings, mock_sleep, tmp_path: Path):
    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    mock_settings.provider_timeout_seconds = 5.0
    _base_settings(mock_settings)

    client = MagicMock()
    client.get.side_effect = lambda *a, **k: (_ for _ in ()).throw(_http_402_error())
    mock_client_cls.return_value.__enter__.return_value = client

    with pytest.raises(httpx.HTTPStatusError):
        image_generator._call_pollinations("a red apple", tmp_path / "out.png")

    assert client.get.call_count == image_generator._POLLINATIONS_MAX_ATTEMPTS


@patch("backend.services.image_generator.time.sleep")
def test_pace_pollinations_skips_wait_on_first_call(mock_sleep):
    image_generator._pace_pollinations()
    mock_sleep.assert_not_called()


@patch("backend.services.image_generator.time.monotonic")
@patch("backend.services.image_generator.time.sleep")
def test_pace_pollinations_waits_out_the_remaining_interval(mock_sleep, mock_monotonic):
    # First call at t=1000 (well past the reset last_call_at=0, so no wait);
    # second call 2s later at t=1002 should sleep for the remaining 8s of
    # the 10s minimum interval.
    mock_monotonic.side_effect = [1000.0, 1000.0, 1002.0, 1002.0]
    image_generator._pace_pollinations()
    image_generator._pace_pollinations()
    mock_sleep.assert_called_once_with(pytest.approx(8.0))


@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_generate_image_falls_back_to_local_placeholder(mock_client_cls, mock_settings, tmp_path: Path):
    mock_settings.nvidia_api_key = "fake-key"
    mock_settings.nvidia_image_model = "model"
    mock_settings.target_width = 1080
    mock_settings.target_height = 1920
    mock_settings.provider_timeout_seconds = 5.0
    _base_settings(mock_settings)

    client = MagicMock()
    client.post.side_effect = RuntimeError("nvidia down")
    client.get.side_effect = RuntimeError("pollinations down")
    mock_client_cls.return_value.__enter__.return_value = client

    out_path = tmp_path / "out.png"
    result = image_generator.generate_image("a robot and a human shaking hands", out_path)

    assert result == out_path
    with Image.open(out_path) as saved:
        assert saved.size == (1080, 1920)


def test_prompt_to_gradient_is_deterministic():
    first = image_generator._prompt_to_gradient("a red apple")
    second = image_generator._prompt_to_gradient("a red apple")
    assert first == second


def test_prompt_to_gradient_differs_for_different_prompts():
    a = image_generator._prompt_to_gradient("a red apple")
    b = image_generator._prompt_to_gradient("a blue car")
    assert a != b


def test_generate_placeholder_produces_target_size(tmp_path: Path):
    out_path = tmp_path / "placeholder.png"
    result = image_generator._generate_placeholder("a robot and a human shaking hands", out_path)
    assert result == out_path
    with Image.open(out_path) as saved:
        assert saved.size == (1080, 1920)


# ---------------------------------------------------------------------------
# Cloudflare Workers AI / OpenRouter / cool-down / framing
# ---------------------------------------------------------------------------


@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_cloudflare_is_used_first_and_its_square_output_is_framed(mock_client_cls, mock_settings, tmp_path: Path):
    _base_settings(
        mock_settings,
        has_cloudflare=True,
        cloudflare_account_id="acct",
        cloudflare_api_token="tok",
        cloudflare_image_model_list=["@cf/black-forest-labs/flux-1-schnell"],
        nvidia_api_key="nv",
        target_width=1080,
        target_height=1920,
        provider_timeout_seconds=5.0,
    )
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.headers = {"content-type": "application/json"}
    response.json.return_value = {"result": {"image": base64.b64encode(_fake_jpeg_bytes(1024, 1024)).decode()}, "success": True}
    client = MagicMock()
    client.post.return_value = response
    mock_client_cls.return_value.__enter__.return_value = client

    out = tmp_path / "scene.png"
    image_generator.generate_image("two race cars", out)

    url = client.post.call_args.args[0]
    assert url == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run/@cf/black-forest-labs/flux-1-schnell"
    assert client.post.call_args.kwargs["json"] == {"prompt": "two race cars", "steps": 8}
    assert client.post.call_args.kwargs["headers"]["Authorization"] == "Bearer tok"
    assert client.post.call_count == 1  # NVIDIA never tried
    with Image.open(out) as saved:
        assert saved.size == (1080, 1920)


@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_cloudflare_binary_image_response_is_accepted(mock_client_cls, mock_settings, tmp_path: Path):
    _base_settings(
        mock_settings, has_cloudflare=True, cloudflare_account_id="a", cloudflare_api_token="t",
        cloudflare_image_model_list=["@cf/stabilityai/stable-diffusion-xl-base-1.0"],
        target_width=1080, target_height=1920, provider_timeout_seconds=5.0,
    )
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.headers = {"content-type": "image/png"}
    buf = io.BytesIO()
    Image.new("RGB", (768, 1344), (1, 2, 3)).save(buf, format="PNG")
    response.content = buf.getvalue()
    client = MagicMock()
    client.post.return_value = response
    mock_client_cls.return_value.__enter__.return_value = client

    out = tmp_path / "scene.png"
    image_generator._call_cloudflare("x", out)
    assert client.post.call_args.kwargs["json"]["width"] == image_generator._NVIDIA_REQUEST_WIDTH
    with Image.open(out) as saved:
        assert saved.size == (1080, 1920)


@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_unfunded_openrouter_falls_through_without_trying_every_model(mock_client_cls, mock_settings, tmp_path: Path):
    _base_settings(
        mock_settings, openrouter_api_key="k", openrouter_image_model_list=["m1", "m2"],
        nvidia_api_key="", image_use_pollinations=False,
        target_width=1080, target_height=1920, provider_timeout_seconds=5.0,
    )
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/images")
    refused = httpx.Response(402, request=request, json={"error": {"message": "Insufficient credits"}})
    client = MagicMock()
    client.post.return_value = refused
    mock_client_cls.return_value.__enter__.return_value = client

    out = tmp_path / "scene.png"
    image_generator.generate_image("x", out)  # falls back to the placeholder

    assert client.post.call_count == 1  # 402 on m1 means m2 would be refused too
    with Image.open(out) as saved:
        assert saved.size == (1080, 1920)


@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_failed_provider_is_skipped_on_the_next_scene(mock_client_cls, mock_settings, tmp_path: Path):
    _base_settings(
        mock_settings, nvidia_api_key="nv", nvidia_image_model="m", provider_cooldown_seconds=600,
        image_use_pollinations=False, target_width=1080, target_height=1920, provider_timeout_seconds=5.0,
    )
    client = MagicMock()
    client.post.side_effect = httpx.ReadTimeout("hung")
    mock_client_cls.return_value.__enter__.return_value = client

    image_generator.generate_image("scene one", tmp_path / "a.png")
    image_generator.generate_image("scene two", tmp_path / "b.png")
    assert client.post.call_count == 1  # second scene didn't wait on the hung provider again


@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_unconfigured_providers_are_not_attempted(mock_client_cls, mock_settings, tmp_path: Path):
    from backend.services.model_router import attempt_sink

    _base_settings(mock_settings, nvidia_api_key="", image_use_pollinations=False, target_width=1080, target_height=1920)
    events: list[dict] = []
    token = attempt_sink.set(events.append)
    try:
        image_generator.generate_image("x", tmp_path / "a.png")
    finally:
        attempt_sink.reset(token)
    assert [e["provider"] for e in events] == ["local_placeholder"]
    mock_client_cls.assert_not_called()


def test_square_images_keep_the_whole_picture_instead_of_a_thin_slice():
    from backend.services import framing

    square = Image.new("RGB", (1000, 1000), (0, 0, 0))
    for x in range(0, 100):  # a red stripe at the far left edge of the subject
        for y in range(1000):
            square.putpixel((x, y), (255, 0, 0))
    framed = framing.fit_to_frame(square, 1080, 1920)
    assert framed.size == (1080, 1920)
    # The far-left stripe survives (center-cropping would have thrown it away)...
    assert framed.getpixel((40, 960))[0] > 200
    # ...and the top of the frame is the darkened blurred backdrop, not stretched content.
    assert max(framed.getpixel((540, 20))) < 200


def test_near_vertical_images_are_simply_cover_cropped():
    from backend.services import framing

    tall = Image.new("RGB", (768, 1344), (10, 200, 10))
    framed = framing.fit_to_frame(tall, 1080, 1920)
    assert framed.size == (1080, 1920)
    assert framed.getpixel((540, 20)) == (10, 200, 10)


# ---------------------------------------------------------------------------
# Cloudflare as the only image provider
# ---------------------------------------------------------------------------


def _cf_ok_response():
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.headers = {"content-type": "application/json"}
    response.json.return_value = {"result": {"image": base64.b64encode(_fake_jpeg_bytes(1024, 1024)).decode()}}
    return response


@patch("backend.services.image_generator.time.sleep")
@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_cloudflare_only_never_touches_other_ai_providers(mock_client_cls, mock_settings, _sleep, tmp_path: Path):
    from backend.services.model_router import attempt_sink

    _base_settings(
        mock_settings, has_cloudflare=True, cloudflare_account_id="a", cloudflare_api_token="t",
        cloudflare_image_model_list=["@cf/black-forest-labs/flux-1-schnell"], image_provider_list=["cloudflare"],
        openrouter_api_key="k", openrouter_image_model_list=["m"], nvidia_api_key="nv",  # configured, but not allowed
        target_width=1080, target_height=1920, provider_timeout_seconds=5.0,
    )
    request = httpx.Request("POST", "https://api.cloudflare.com/x")
    client = MagicMock()
    client.post.side_effect = [httpx.Response(503, request=request)] * 3  # Cloudflare down for this scene
    mock_client_cls.return_value.__enter__.return_value = client

    events: list[dict] = []
    token = attempt_sink.set(events.append)
    try:
        image_generator.generate_image("x", tmp_path / "a.png")
    finally:
        attempt_sink.reset(token)
    assert [e["provider"] for e in events] == ["cloudflare", "local_placeholder"]
    assert all("cloudflare.com" in call.args[0] for call in client.post.call_args_list)
    assert client.post.call_count == 3  # retried before giving up


@patch("backend.services.image_generator.time.sleep")
@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_cloudflare_retries_a_rate_limit_then_succeeds(mock_client_cls, mock_settings, mock_sleep, tmp_path: Path):
    _base_settings(
        mock_settings, has_cloudflare=True, cloudflare_account_id="a", cloudflare_api_token="t",
        cloudflare_image_model_list=["@cf/black-forest-labs/flux-1-schnell"], image_provider_list=["cloudflare"],
        target_width=1080, target_height=1920, provider_timeout_seconds=5.0,
    )
    request = httpx.Request("POST", "https://api.cloudflare.com/x")
    client = MagicMock()
    client.post.side_effect = [httpx.Response(429, request=request), _cf_ok_response()]
    mock_client_cls.return_value.__enter__.return_value = client

    out = tmp_path / "a.png"
    image_generator.generate_image("x", out)
    assert client.post.call_count == 2
    mock_sleep.assert_called_once()
    with Image.open(out) as saved:
        assert saved.size == (1080, 1920)


@patch("backend.services.image_generator.time.sleep")
@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_daily_quota_stops_calling_cloudflare_until_reset(mock_client_cls, mock_settings, mock_sleep, tmp_path: Path):
    from backend.services.model_router import attempt_sink

    _base_settings(
        mock_settings, has_cloudflare=True, cloudflare_account_id="a", cloudflare_api_token="t",
        cloudflare_image_model_list=["@cf/black-forest-labs/flux-1-schnell"], image_provider_list=["cloudflare"],
        target_width=1080, target_height=1920, provider_timeout_seconds=5.0,
    )
    request = httpx.Request("POST", "https://api.cloudflare.com/x")
    quota = httpx.Response(429, request=request, json={"success": False, "errors": [
        {"code": 4006, "message": "AiError: you have used up your daily free allocation of 10,000 neurons"}]})
    client = MagicMock()
    client.post.return_value = quota
    mock_client_cls.return_value.__enter__.return_value = client

    events: list[dict] = []
    token = attempt_sink.set(events.append)
    try:
        image_generator.generate_image("scene one", tmp_path / "a.png")
        image_generator.generate_image("scene two", tmp_path / "b.png")
    finally:
        attempt_sink.reset(token)

    assert client.post.call_count == 1  # no retries, and the second scene never calls Cloudflare
    mock_sleep.assert_not_called()
    assert image_generator.cloudflare_quota_exhausted_until() is not None
    assert "daily free image limit" in events[0]["error"] and "UTC" in events[0]["error"]
    assert [e["provider"] for e in events] == ["cloudflare", "local_placeholder", "cloudflare", "local_placeholder"]


@patch("backend.services.image_generator.time.sleep")
@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_second_cloudflare_account_takes_over_when_the_first_is_used_up(mock_client_cls, mock_settings, _sleep, tmp_path: Path):
    _base_settings(
        mock_settings, has_cloudflare=True, cloudflare_account_pool=[("acct1", "tok1"), ("acct2", "tok2")],
        cloudflare_image_model_list=["@cf/black-forest-labs/flux-1-schnell"], image_provider_list=["cloudflare"],
        target_width=1080, target_height=1920, provider_timeout_seconds=5.0,
    )
    request = httpx.Request("POST", "https://api.cloudflare.com/x")
    quota = httpx.Response(429, request=request, json={"errors": [{"code": 4006, "message": "daily free allocation"}]})
    client = MagicMock()
    client.post.side_effect = [quota, _cf_ok_response(), _cf_ok_response()]
    mock_client_cls.return_value.__enter__.return_value = client

    image_generator.generate_image("scene one", tmp_path / "a.png")
    image_generator.generate_image("scene two", tmp_path / "b.png")

    urls = [call.args[0] for call in client.post.call_args_list]
    assert "/accounts/acct1/" in urls[0] and "/accounts/acct2/" in urls[1]
    assert "/accounts/acct2/" in urls[2]  # account 1 is skipped for the rest of the day
    assert client.post.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer tok2"
    assert image_generator.cloudflare_quota_exhausted_until() is None  # account 2 still has allowance


@patch("backend.services.image_generator.time.sleep")
@patch("backend.services.image_generator.settings")
@patch("backend.services.image_generator.httpx.Client")
def test_pollinations_backs_up_cloudflare_when_every_account_is_spent(mock_client_cls, mock_settings, _sleep, tmp_path: Path):
    from backend.services.model_router import attempt_sink

    _base_settings(
        mock_settings, has_cloudflare=True, cloudflare_account_pool=[("acct1", "tok1")],
        cloudflare_image_model_list=["@cf/black-forest-labs/flux-1-schnell"], image_provider_list=["cloudflare", "pollinations"],
        target_width=1080, target_height=1920, provider_timeout_seconds=5.0,
    )
    request = httpx.Request("POST", "https://api.cloudflare.com/x")
    client = MagicMock()
    client.post.return_value = httpx.Response(429, request=request, json={"errors": [{"code": 4006, "message": "daily free allocation"}]})
    poll = MagicMock()
    poll.raise_for_status.return_value = None
    poll.content = _fake_square_jpeg_bytes(768)
    client.get.return_value = poll
    mock_client_cls.return_value.__enter__.return_value = client

    events: list[dict] = []
    token = attempt_sink.set(events.append)
    try:
        image_generator.generate_image("x", tmp_path / "a.png")
    finally:
        attempt_sink.reset(token)
    assert [(e["provider"], e["ok"]) for e in events] == [("cloudflare", False), ("pollinations", True)]
