from __future__ import annotations

import os
import time

import gradio as gr
import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

_STAGE_ORDER = [
    "queued",
    "running_intelligence",
    "running_generation",
    "running_composition",
    "running_validation",
    "done",
]

_STAGE_LABELS = {
    "queued": "Queued",
    "running_intelligence": "Script",
    "running_generation": "Visuals & Voice",
    "running_composition": "Composition",
    "running_validation": "Quality Check",
    "done": "Done",
    "failed": "Failed",
}


def _render_status(status: str) -> str:
    if status == "failed":
        return "\n".join(f"- {label}" for label in _STAGE_LABELS.values() if label != "Failed") + "\n\n**Failed**"

    reached = _STAGE_ORDER.index(status) if status in _STAGE_ORDER else -1
    lines = []
    for i, stage in enumerate(_STAGE_ORDER):
        label = _STAGE_LABELS[stage]
        if i < reached:
            lines.append(f"- [x] {label}")
        elif i == reached:
            lines.append(f"- [ ] **{label} (running)**" if stage != "done" else f"- [x] {label}")
        else:
            lines.append(f"- [ ] {label}")
    return "\n".join(lines)


def _auth_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def generate(topic: str, language: str, motion_tier: str, api_key: str):
    topic = (topic or "").strip()
    if not topic:
        yield "Enter a topic first.", None, gr.update(interactive=True), None, gr.update(interactive=False), gr.update(interactive=False), ""
        return

    yield "Submitting job...", None, gr.update(interactive=False), None, gr.update(interactive=False), gr.update(interactive=False), ""

    with httpx.Client(timeout=30.0) as client:
        try:
            response = client.post(
                f"{API_BASE_URL}/jobs",
                json={"topic": topic, "language": language, "motion_tier": motion_tier},
                headers=_auth_headers(api_key),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("detail", "")  # type: ignore[union-attr]
            except Exception:
                pass
            yield f"Could not reach the backend at {API_BASE_URL}: {exc} {detail}", None, gr.update(interactive=True), None, gr.update(interactive=False), gr.update(interactive=False), ""
            return

        job = response.json()
        job_id = job["id"]

        while True:
            time.sleep(1.5)
            try:
                response = client.get(f"{API_BASE_URL}/jobs/{job_id}")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                yield f"Lost connection to backend: {exc}", None, gr.update(interactive=True), job_id, gr.update(interactive=False), gr.update(interactive=False), ""
                return

            job = response.json()
            status = job["status"]

            if status == "failed":
                reason = job.get("error_reason", "unknown error")
                stage = job.get("error_stage", "unknown stage")
                yield f"{_render_status(status)}\n\n**Reason ({stage}):** {reason}", None, gr.update(interactive=True), job_id, gr.update(interactive=False), gr.update(interactive=False), ""
                return

            if status == "done":
                quality_text = ""
                try:
                    qr = client.get(f"{API_BASE_URL}/jobs/{job_id}/quality-report")
                    if qr.status_code == 200:
                        report = qr.json()
                        quality_text = (
                            f"**Quality check:** {'PASSED' if report.get('passed') else 'FAILED'}  \n"
                            f"{report.get('width')}x{report.get('height')} · "
                            f"{report.get('duration_seconds', 0):.1f}s · "
                            f"audio: {report.get('has_audio_track')}"
                        )
                except httpx.HTTPError:
                    pass
                yield _render_status(status), job.get("result_path"), gr.update(interactive=True), job_id, gr.update(interactive=True), gr.update(interactive=False), quality_text
                return

            yield _render_status(status), None, gr.update(interactive=False), job_id, gr.update(interactive=False), gr.update(interactive=False), ""


def approve(job_id: str, approver: str, api_key: str):
    if not job_id:
        return "No job to approve yet.", gr.update(interactive=False), gr.update(interactive=False)
    with httpx.Client(timeout=15.0) as client:
        try:
            response = client.post(
                f"{API_BASE_URL}/jobs/{job_id}/approve",
                json={"approver": (approver or "demo-operator").strip() or "demo-operator"},
                headers=_auth_headers(api_key),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f"Approve failed: {exc}", gr.update(interactive=True), gr.update(interactive=False)

    body = response.json()
    return f"Approved by {body.get('approved_by')} at {body.get('approved_at')}.", gr.update(interactive=False), gr.update(interactive=True)


def publish(job_id: str, api_key: str):
    if not job_id:
        return "No job to publish yet."
    with httpx.Client(timeout=15.0) as client:
        try:
            response = client.post(f"{API_BASE_URL}/jobs/{job_id}/publish", headers=_auth_headers(api_key))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f"Publish failed: {exc}"

    body = response.json()
    if body.get("status") == "manual_handoff":
        return body.get("manual_handoff_note", "Manual handoff created.")
    return f"Unexpected publish status: {body.get('status')} ({body.get('publish_error', '')})"


def cancel(job_id: str, api_key: str):
    if not job_id:
        return "No job to cancel yet."
    with httpx.Client(timeout=15.0) as client:
        try:
            response = client.post(f"{API_BASE_URL}/jobs/{job_id}/cancel", headers=_auth_headers(api_key))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f"Cancel failed: {exc}"

    body = response.json()
    return f"Job {job_id} cancelled (was: {body.get('status')})."


def refresh_credits():
    with httpx.Client(timeout=10.0) as client:
        try:
            response = client.get(f"{API_BASE_URL}/credits")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f"Could not fetch credits: {exc}"
    body = response.json()
    costs = ", ".join(f"{tier}={cost}" for tier, cost in body.get("cost_by_tier", {}).items())
    return f"**Balance:** {body.get('balance')} credits  \n**Cost per job:** {costs}"


def do_login(entered_key: str):
    with httpx.Client(timeout=10.0) as client:
        try:
            response = client.post(f"{API_BASE_URL}/auth/login", json={"api_key": entered_key or ""})
        except httpx.HTTPError as exc:
            return f"Could not reach backend: {exc}", gr.update(visible=True), gr.update(visible=False), ""

    if response.status_code == 200:
        return "", gr.update(visible=False), gr.update(visible=True), (entered_key or "")

    try:
        detail = response.json().get("detail", "Invalid API key")
    except Exception:
        detail = "Invalid API key"
    return detail, gr.update(visible=True), gr.update(visible=False), ""


def check_auth_on_load():
    """Auto-skip the login screen when BACKEND_API_KEY isn't configured on
    the backend - auth is opt-in (see DEPLOYMENT.md §10), so a deployment
    that never set a key shouldn't force a login prompt no one can pass."""
    with httpx.Client(timeout=10.0) as client:
        try:
            response = client.get(f"{API_BASE_URL}/providers/status")
            response.raise_for_status()
            auth_enabled = bool(response.json().get("auth", {}).get("enabled", False))
        except httpx.HTTPError:
            auth_enabled = True  # can't confirm it's off - fail closed, show login

    if auth_enabled:
        return gr.update(visible=True), gr.update(visible=False)
    return gr.update(visible=False), gr.update(visible=True)


def refresh_providers():
    with httpx.Client(timeout=10.0) as client:
        try:
            response = client.get(f"{API_BASE_URL}/providers/status")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f"Could not fetch provider status: {exc}"
    body = response.json()
    lines = []
    for stage, info in body.items():
        if not isinstance(info, dict) or "chain" not in info:
            continue
        marks = " -> ".join(
            f"{name}{'✅' if info['configured'].get(name) else '⬜'}" for name in info["chain"]
        )
        lines.append(f"**{stage}:** {marks}")
    lines.append(f"\n**Auth enabled:** {body.get('auth', {}).get('enabled')}")
    lines.append(f"**Persistence (Mongo):** {body.get('persistence', {}).get('mongodb_configured')}")
    return "\n\n".join(lines)


with gr.Blocks(title="Qoneqt Content Engine") as demo:
    gr.Markdown(
        "# IdeaFeed AI — Qoneqt Content Engine\n"
        "One topic in. A reviewed, approved, ready-to-publish video out."
    )

    job_id_state = gr.State(value=None)
    api_key_state = gr.State(value="")

    with gr.Group(visible=True) as login_group:
        gr.Markdown("### Login\nThis deployment requires a backend API key.")
        login_input = gr.Textbox(label="API key", type="password")
        login_button = gr.Button("Login", variant="primary")
        login_status = gr.Markdown()

    with gr.Group(visible=False) as main_group:
        with gr.Row():
            topic_input = gr.Textbox(
                label="Topic, prompt, idea or trend",
                placeholder="Why electric vehicles are becoming popular",
                scale=3,
            )
            language_input = gr.Dropdown(choices=["en", "hi", "hinglish"], value="en", label="Language", scale=1)
            motion_tier_input = gr.Dropdown(
                choices=["basic", "balanced", "max"], value="balanced", label="Motion effort", scale=1
            )
            generate_button = gr.Button("Generate", variant="primary", scale=1)

        with gr.Row():
            stage_status = gr.Markdown(label="Pipeline stages")
            video_output = gr.Video(label="Result")

        quality_report_display = gr.Markdown(label="Quality report")

        with gr.Row():
            approver_input = gr.Textbox(label="Approver name/email", value="demo-operator", scale=2)
            approve_button = gr.Button("Approve", interactive=False, scale=1)
            publish_button = gr.Button("Publish (Qoneqt manual handoff)", interactive=False, scale=1)
            cancel_button = gr.Button("Cancel job", variant="stop", scale=1)

        handoff_output = gr.Textbox(label="Approval / publish / cancel result", lines=6)

        generate_button.click(
            fn=generate,
            inputs=[topic_input, language_input, motion_tier_input, api_key_state],
            outputs=[
                stage_status,
                video_output,
                generate_button,
                job_id_state,
                approve_button,
                publish_button,
                quality_report_display,
            ],
        )

        approve_button.click(
            fn=approve,
            inputs=[job_id_state, approver_input, api_key_state],
            outputs=[handoff_output, approve_button, publish_button],
        )

        publish_button.click(
            fn=publish,
            inputs=[job_id_state, api_key_state],
            outputs=[handoff_output],
        )

        cancel_button.click(
            fn=cancel,
            inputs=[job_id_state, api_key_state],
            outputs=[handoff_output],
        )

        with gr.Accordion("Credits", open=False):
            credits_display = gr.Markdown()
            credits_refresh = gr.Button("Refresh balance")
            credits_refresh.click(fn=refresh_credits, outputs=[credits_display])

        with gr.Accordion("AI orchestra — provider fallback status", open=False):
            providers_display = gr.Markdown()
            providers_refresh = gr.Button("Refresh provider status")
            providers_refresh.click(fn=refresh_providers, outputs=[providers_display])

    login_button.click(
        fn=do_login,
        inputs=[login_input],
        outputs=[login_status, login_group, main_group, api_key_state],
    )

    demo.load(fn=check_auth_on_load, outputs=[login_group, main_group])

if __name__ == "__main__":
    demo.queue().launch()
