#!/usr/bin/env python3
"""Publish the uploaded Pages artifact and wait for it to finish.

actions/deploy-pages cancels the deployment when its own 10 minute timer
fires. On this repository the Pages update is still running at that point,
and cancelling it leaves uniqgames.net on the previous version. This waits
the update out and never cancels it.

Expects the github-pages artifact from actions/upload-pages-artifact, plus
the usual Actions environment (GITHUB_TOKEN, the OIDC request URL, run id).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
WAIT_SECONDS = 35 * 60
POLL_SECONDS = 15

DONE = "succeed"
FATAL = {
    "deployment_failed",
    "deployment_content_failed",
    "deployment_cancelled",
    "deployment_lost",
}


def request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "uniqgames-pages-publish",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise SystemExit(f"{method} {url} failed: HTTP {error.code} {detail}") from error
    return json.loads(raw) if raw else {}


def oidc_token() -> str:
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    token = os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]
    req = urllib.request.Request(url, headers={"Authorization": f"bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.loads(response.read().decode())
    value = payload.get("value")
    if not value:
        raise SystemExit("GitHub did not return an OIDC token.")
    return value


def artifact_id(repo: str, run_id: str, token: str) -> int:
    url = f"{API}/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    payload = request("GET", url, token)
    matches = [
        item
        for item in payload.get("artifacts", [])
        if item.get("name") == "github-pages" and not item.get("expired")
    ]
    if len(matches) != 1:
        names = [item.get("name") for item in payload.get("artifacts", [])]
        raise SystemExit(f"Expected one github-pages artifact, found {names}.")
    print(f"Artifact {matches[0]['id']} ({matches[0].get('size_in_bytes')} bytes)", flush=True)
    return int(matches[0]["id"])


def main() -> None:
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    run_id = os.environ["GITHUB_RUN_ID"]
    sha = os.environ["GITHUB_SHA"]

    created = request(
        "POST",
        f"{API}/repos/{repo}/pages/deployments",
        token,
        {
            "artifact_id": artifact_id(repo, run_id, token),
            "pages_build_version": sha,
            "oidc_token": oidc_token(),
        },
    )
    deployment_id = created.get("id") or sha
    print(f"Created deployment {deployment_id}", flush=True)

    deadline = time.monotonic() + WAIT_SECONDS
    status_url = f"{API}/repos/{repo}/pages/deployments/{deployment_id}"
    while True:
        status = request("GET", status_url, token).get("status") or ""
        print(f"Current status: {status or '(blank)'}", flush=True)
        if status == DONE:
            return
        if status in FATAL:
            raise SystemExit(f"Pages deployment finished with status {status}.")
        if time.monotonic() >= deadline:
            print(
                "Still publishing after 35 minutes. Leaving it running so Pages can finish.",
                flush=True,
            )
            raise SystemExit(1)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
