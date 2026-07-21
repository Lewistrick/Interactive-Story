#!/usr/bin/env python3
"""Seed demo stories via the Interactive Story API."""

import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8001/api/v1"
USERNAME = "cursor_ai_storyteller"
PASSWORD = "AI_demo_stories_2026!"


def request(method: str, path: str, data: dict | None = None, token: str | None = None) -> dict:
    """Make an HTTP request and return parsed JSON."""
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise RuntimeError(f"{method} {path} -> {e.code}: {detail}") from e


def register_and_login() -> str:
    """Register the AI demo user (or login if already exists) and return JWT."""
    try:
        request("POST", "/auth/register", {"username": USERNAME, "password": PASSWORD})
        print(f"Registered user: {USERNAME}")
    except RuntimeError as e:
        if "400" in str(e) and "already" in str(e).lower():
            print(f"User {USERNAME} already exists, logging in...")
        else:
            raise
    token_resp = request("POST", "/auth/login", {"username": USERNAME, "password": PASSWORD})
    return token_resp["access_token"]


def create_root(token: str, teaser: str, content: str) -> str:
    """Create a root story and return its id."""
    part = request("POST", "/stories/", {"teaser": teaser, "content": content}, token)
    print(f"  Root: {teaser} ({part['id']})")
    return part["id"]


def continue_story(token: str, parent_id: str, teaser: str, content: str) -> str:
    """Add a continuation and return its id."""
    part = request(
        "POST",
        f"/stories/{parent_id}/continue",
        {"teaser": teaser, "content": content},
        token,
    )
    print(f"    -> {teaser} (depth {part['depth_level']})")
    return part["id"]


def seed_stories(token: str) -> None:
    """Create three root stories with branching structure."""
    print("\n=== Story 1: The Last Lighthouse Keeper (deep branch) ===")
    s1 = create_root(
        token,
        "The Last Lighthouse Keeper",
        "Elias had tended the lighthouse alone for eleven years. "
        "Tonight the horizon wore a color he had never seen — copper, like a coin held to flame.",
    )
    s1_a = continue_story(
        token,
        s1,
        "The storm arrives",
        "By midnight the sea had become a wall. Elias climbed the spiral stairs, "
        "each step groaning as if the tower itself were afraid.",
    )
    s1_a1 = continue_story(
        token,
        s1_a,
        "Shelter in the cellar",
        "The glass cracked. He descended to the cellar with a crate of candles "
        "and the logbook he still pretended someone would read.",
    )
    continue_story(
        token,
        s1_a1,
        "A knock at the door",
        "Three knocks — patient, spaced, impossible. No boat could have landed. "
        "Elias lifted the bar and found only salt air and a footprint that glowed faintly.",
    )
    continue_story(
        token,
        s1,
        "The lamp goes out",
        "Or he could stay at the lantern room and relight the beam, knowing "
        "the storm would take the tower before dawn either way.",
    )

    print("\n=== Story 2: Fork in the Road (three wide branches) ===")
    s2 = create_root(
        token,
        "Fork in the Road",
        "Mira reached the crossroads at dusk. Three paths diverged: forest, river, hill. "
        "The signpost had been removed, but someone had scratched words into the wood.",
    )
    continue_story(
        token,
        s2,
        "Take the forest path",
        "The trees closed like curtains. Mira counted her steps to stay calm "
        "and tried not to think about the stories of travelers who never counted back.",
    )
    continue_story(
        token,
        s2,
        "Follow the river",
        "Water spoke louder than wind here. Mira waded upstream until the stones "
        "cut her boots and the moon appeared whole between two cliffs.",
    )
    continue_story(
        token,
        s2,
        "Climb the hill",
        "The hill was steeper than it looked. Halfway up she found a bench "
        "and an envelope addressed to whoever arrived next.",
    )
    continue_story(
        token,
        s2,
        "Wait until morning",
        "Mira sat on the signpost stump and decided not to choose in the dark. "
        "At first light, all three paths looked smaller — and equally possible.",
    )

    print("\n=== Story 3: Message in a Bottle ===")
    s3 = create_root(
        token,
        "Message in a Bottle",
        "The bottle washed up on Tuesday with a cork still dry inside. "
        "The note read: 'If you are reading this, I am already on my way to you.'",
    )
    s3_a = continue_story(
        token,
        s3,
        "Open the bottle",
        "Inside the glass was not paper but a folded map of a harbor that "
        "did not appear on any chart Mira owned.",
    )
    continue_story(
        token,
        s3_a,
        "Sail to the harbor",
        "She borrowed a skiff at dawn. The harbor on the map existed only at low tide, "
        "when the ribs of a sunken pier broke the surface like fingers.",
    )
    continue_story(
        token,
        s3,
        "Leave the bottle sealed",
        "Some messages are invitations; others are traps. Mira buried the bottle "
        "above the tide line and marked the spot with a circle of white stones.",
    )


def main() -> int:
    """Entry point."""
    print("Checking API health...")
    try:
        with urllib.request.urlopen("http://localhost:8001/health", timeout=10) as resp:
            print(resp.read().decode())
    except Exception as e:
        print(f"API not reachable at localhost:8001 — start with: docker compose up -d\n{e}")
        return 1

    token = register_and_login()
    seed_stories(token)
    print(f"\nDone! Log in as '{USERNAME}' to explore the stories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
