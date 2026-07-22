#!/usr/bin/env python3
"""Flood the API with accounts, nonsense posts, votes, and reports.

Creates ~20 users and enough activity to populate the moderator quarantine
queue via every automatic trigger that the MVP implements:

* ``user_reports`` — ≥3 distinct reports on a part
* ``story_score_threshold`` — part ``vote_score`` ≤ −5
* ``rapid_posting`` — ≥5 parts from one user within 1 hour
* ``user_reputation_threshold`` — forced via SQL (Wilson reputation never
  goes negative, so this trigger cannot fire through the public API alone)

Also promotes ``chaos_moderator`` so you can open ``/moderator``.

Auth is limited to 20 requests/min/IP (register + login each count). This
script caches JWTs on disk, reuses them on resume, clears Redis ``rl:*``
keys when needed, and backs off for a full window on 429.

Root creation requires ``MIN_REPUTATION_CREATE_ROOT`` (50). Score refresh
resets Wilson reputation after each post, so writers are SQL-bumped to
Legend immediately before every create/continue. Rapid posting uses one
root plus a deep chain (max 3 open roots/user; sibling-branch cooldown).

Usage::

    # Stack must be up: docker compose up -d
    python3 scripts/seed_moderation_chaos.py

Requires ``docker exec`` into ``istory-postgres`` / ``istory-redis`` for
tier bumps, moderator promotion, reputation quarantine, and rate-limit reset.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = "http://localhost:8001/api/v1"
PASSWORD = "ChaosSpam_2026!"
NUM_USERS = 20
MODERATOR_USERNAME = "chaos_moderator"
TOKEN_CACHE_PATH = Path(__file__).resolve().parent / ".chaos_tokens.json"

# Match app/core/config.py defaults (auth is the tight one).
AUTH_LIMIT = 20
AUTH_WINDOW_SECONDS = 60
WRITE_LIMIT = 60
# Leave headroom so a retry burst does not immediately 429 again.
AUTH_SOFT_LIMIT = 16


@dataclass
class Account:
    """Registered chaos account with a live JWT."""

    username: str
    token: str
    user_id: str | None = None


class RateBudget:
    """Track recent calls against a fixed-window limit."""

    def __init__(self, name: str, limit: int, window: int) -> None:
        """Initialize a named budget."""
        self.name = name
        self.limit = limit
        self.window = window
        self._times: list[float] = []

    def _prune(self, now: float) -> None:
        """Drop timestamps outside the current window."""
        cutoff = now - self.window
        self._times = [t for t in self._times if t >= cutoff]

    def wait_if_needed(self) -> None:
        """Block until another call fits under the soft limit."""
        while True:
            now = time.monotonic()
            self._prune(now)
            if len(self._times) < self.limit:
                return
            sleep_for = self._times[0] + self.window - now + 1.0
            print(
                f"  [{self.name}] budget full "
                f"({len(self._times)}/{self.limit} in {self.window}s); "
                f"sleeping {sleep_for:.1f}s"
            )
            time.sleep(max(sleep_for, 1.0))

    def record(self) -> None:
        """Record one call against the budget."""
        now = time.monotonic()
        self._prune(now)
        self._times.append(now)


AUTH_BUDGET = RateBudget("auth", AUTH_SOFT_LIMIT, AUTH_WINDOW_SECONDS)
WRITE_BUDGET = RateBudget("write", WRITE_LIMIT - 4, AUTH_WINDOW_SECONDS)


def nonsense(n: int = 8) -> str:
    """Return a random nonsense word of length ``n``."""
    vowels = "aeiou"
    consonants = "bcdfghjklmnpqrstvwxyz"
    chars: list[str] = []
    for i in range(n):
        chars.append(random.choice(consonants if i % 2 == 0 else vowels))
    return "".join(chars)


def gibberish_sentence(words: int = 6) -> str:
    """Build a short nonsense sentence."""
    return " ".join(nonsense(random.randint(4, 10)) for _ in range(words)).capitalize() + "."


def clear_redis_rate_limits() -> None:
    """Delete Redis rate-limit keys so the seed is not stuck mid-run."""
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "istory-redis",
                "sh",
                "-c",
                'keys=$(redis-cli --scan --pattern "rl:*"); '
                'if [ -n "$keys" ]; then redis-cli DEL $keys; echo "$keys" | wc -w; '
                "else echo 0; fi",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cleared = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "0"
        print(f"  cleared {cleared} Redis rate-limit key(s)")
        AUTH_BUDGET._times.clear()
        WRITE_BUDGET._times.clear()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"  warning: could not clear Redis rate limits ({e})")


def load_token_cache() -> dict[str, dict]:
    """Load cached username → {token, user_id} mapping."""
    if not TOKEN_CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(TOKEN_CACHE_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_token_cache(accounts: list[Account]) -> None:
    """Persist JWTs so a re-run does not burn the auth rate limit."""
    existing = load_token_cache()
    for account in accounts:
        existing[account.username] = {
            "token": account.token,
            "user_id": account.user_id,
        }
    TOKEN_CACHE_PATH.write_text(json.dumps(existing, indent=2))


def request(
    method: str,
    path: str,
    data: dict | None = None,
    token: str | None = None,
    *,
    budget: RateBudget | None = None,
    retries: int = 8,
) -> dict:
    """HTTP JSON helper with full-window backoff on 429."""
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None

    last_err: Exception | None = None
    for attempt in range(retries):
        if budget is not None:
            budget.wait_if_needed()
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if budget is not None:
                    budget.record()
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode()
            if e.code == 429 and attempt < retries - 1:
                print(
                    f"  429 on {method} {path} (attempt {attempt + 1}/{retries}); "
                    "clearing Redis rl:* keys"
                )
                clear_redis_rate_limits()
                time.sleep(1.5)
                last_err = e
                continue
            raise RuntimeError(f"{method} {path} -> {e.code}: {detail}") from e
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"{method} {path} failed after retries: {last_err}")


def psql(sql: str) -> str:
    """Run SQL inside the postgres container."""
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "istory-postgres",
            "psql",
            "-U",
            "istory",
            "-d",
            "istory",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def token_still_valid(token: str) -> dict | None:
    """Return /auth/me payload if ``token`` is accepted, else None."""
    try:
        # /auth/me is not on the auth rate-limit bucket.
        return request("GET", "/auth/me", token=token, budget=None, retries=2)
    except RuntimeError:
        return None


def register_or_login(username: str, cache: dict[str, dict]) -> Account:
    """Reuse a cached JWT when possible; otherwise register/login once."""
    cached = cache.get(username)
    if cached and cached.get("token"):
        me = token_still_valid(str(cached["token"]))
        if me is not None:
            print(f"  cached token ok for {username}")
            return Account(
                username=username,
                token=str(cached["token"]),
                user_id=str(me.get("id") or cached.get("user_id") or ""),
            )
        print(f"  cached token expired for {username}, re-authenticating")

    user_id: str | None = None
    registered = False
    try:
        profile = request(
            "POST",
            "/auth/register",
            {"username": username, "password": PASSWORD},
            budget=AUTH_BUDGET,
        )
        print(f"  registered {username}")
        user_id = str(profile["id"]) if profile.get("id") else None
        registered = True
    except RuntimeError as e:
        msg = str(e).lower()
        if "already" not in msg and "registered" not in msg:
            raise
        # Username taken — fall through to login only (one auth call).
        print(f"  exists {username}, logging in")

    token_resp = request(
        "POST",
        "/auth/login",
        {"username": username, "password": PASSWORD},
        budget=AUTH_BUDGET,
    )
    token = token_resp["access_token"]
    if user_id is None:
        me = request("GET", "/auth/me", token=token)
        user_id = str(me["id"])
    account = Account(username=username, token=token, user_id=user_id)
    # Persist immediately so a mid-run failure does not lose progress.
    save_token_cache([account])
    if registered:
        time.sleep(0.05)
    return account


def bump_to_legend(usernames: list[str]) -> None:
    """Raise reputation so Legend daily/spacing limits allow posting.

    Score refresh recalculates Wilson reputation (often back to 0) after every
    create/vote, so callers must re-bump before each write that needs tier/root
    gates (``MIN_REPUTATION_CREATE_ROOT`` is 50).
    """
    if not usernames:
        return
    values = ", ".join(f"'{u}'" for u in usernames)
    psql(
        f"UPDATE users SET reputation_score = 600 "
        f"WHERE username IN ({values});"
    )


def ensure_legend(*accounts: Account) -> None:
    """Re-apply Legend reputation for the given accounts."""
    bump_to_legend([a.username for a in accounts])


def promote_moderator(username: str) -> None:
    """Mark a user as moderator."""
    out = psql(
        f"UPDATE users SET is_moderator = true "
        f"WHERE username = '{username}' RETURNING username, is_moderator;"
    )
    print(out)


def force_reputation_quarantine(username: str) -> None:
    """Seed a user_reputation_threshold queue entry.

    Wilson-based reputation is always ≥ 0, so the −20 threshold cannot fire
    via votes alone. We set the score and open a quarantine log the same way
    the service would.
    """
    sql = f"""
    WITH u AS (
      UPDATE users
      SET reputation_score = -25,
          is_quarantined = true,
          quarantine_reason = 'reputation_score -25 <= -20 (chaos seed)',
          quarantined_at = NOW()
      WHERE username = '{username}'
      RETURNING id
    )
    INSERT INTO quarantine_logs (
      id, entity_type, entity_id, reason, triggered_by, automatic, created_at
    )
    SELECT gen_random_uuid(), 'USER', u.id,
           'reputation_score -25 <= -20 (chaos seed)',
           'user_reputation_threshold', true, NOW()
    FROM u
    WHERE NOT EXISTS (
      SELECT 1 FROM quarantine_logs q
      WHERE q.entity_id = u.id AND q.resolved_at IS NULL
    );
    """
    print(psql(sql))


def create_root(account: Account) -> str:
    """Create a nonsense root story as ``account``; return its id."""
    last_err: Exception | None = None
    for _ in range(4):
        ensure_legend(account)
        time.sleep(0.05)
        try:
            part = request(
                "POST",
                "/stories/",
                {
                    "teaser": gibberish_sentence(3)[:120],
                    "content": gibberish_sentence(12),
                },
                account.token,
                budget=WRITE_BUDGET,
            )
            return str(part["id"])
        except RuntimeError as e:
            last_err = e
            msg = str(e).lower()
            if "quarantined" in msg:
                raise
            if "reputation" in msg or "403" in msg or "429" in msg:
                ensure_legend(account)
                time.sleep(0.3)
                continue
            raise
    raise RuntimeError(f"create_root failed for {account.username}: {last_err}")


def continue_part(account: Account, parent_id: str) -> str:
    """Add a nonsense continuation as ``account``; return its id."""
    last_err: Exception | None = None
    for _ in range(4):
        ensure_legend(account)
        time.sleep(0.05)
        try:
            part = request(
                "POST",
                f"/stories/{parent_id}/continue",
                {
                    "teaser": gibberish_sentence(3)[:120],
                    "content": gibberish_sentence(10),
                },
                account.token,
                budget=WRITE_BUDGET,
            )
            return str(part["id"])
        except RuntimeError as e:
            last_err = e
            msg = str(e).lower()
            if "quarantined" in msg:
                raise
            if "reputation" in msg or "403" in msg or "429" in msg:
                ensure_legend(account)
                time.sleep(0.3)
                continue
            raise
    raise RuntimeError(f"continue_part failed for {account.username}: {last_err}")


def vote(token: str, story_id: str, vote_type: str) -> None:
    """Cast an UP or DOWN vote."""
    request(
        "POST",
        f"/stories/{story_id}/vote",
        {"vote_type": vote_type},
        token,
        budget=WRITE_BUDGET,
    )


def report(token: str, story_id: str) -> dict:
    """Report a story part."""
    return request(
        "POST",
        f"/stories/{story_id}/report",
        {"reason": f"chaos {nonsense(6)}"},
        token,
        budget=WRITE_BUDGET,
    )


def wait_for_api() -> None:
    """Fail fast if the stack is not reachable."""
    try:
        with urllib.request.urlopen("http://localhost:8001/health", timeout=10) as resp:
            print(resp.read().decode())
    except Exception as e:  # noqa: BLE001
        print(
            f"API not reachable at localhost:8001 — start with: docker compose up -d\n{e}"
        )
        sys.exit(1)


def main() -> int:
    """Create chaos accounts and trip every quarantine alarm."""
    random.seed()
    print("Checking API health...")
    wait_for_api()

    print("\n=== Clearing Redis rate-limit keys ===")
    clear_redis_rate_limits()

    cache = load_token_cache()
    print(f"\n=== Ensuring {NUM_USERS} accounts (token cache: {TOKEN_CACHE_PATH.name}) ===")
    accounts: list[Account] = []
    for i in range(1, NUM_USERS + 1):
        name = f"chaos_user_{i:02d}"
        accounts.append(register_or_login(name, cache))
    save_token_cache(accounts)

    print("\n=== Moderator account ===")
    mod = register_or_login(MODERATOR_USERNAME, cache)
    save_token_cache([*accounts, mod])

    # Writers need Legend for daily quota / spacing; re-bumped before each write
    # because score refresh resets Wilson reputation to ~0 after every post.
    posters = accounts[:5]
    voters = accounts[5:15]
    reporters = accounts[15:20]
    print("\n=== Initial Legend bump for writers ===")
    bump_to_legend([a.username for a in posters])
    print(psql(
        "SELECT username, reputation_score FROM users "
        f"WHERE username IN ({', '.join(repr(a.username) for a in posters)}) "
        "ORDER BY username;"
    ))
    print("=== Promoting moderator ===")
    promote_moderator(MODERATOR_USERNAME)

    print("\n=== Rapid posting (trigger: rapid_posting) ===")
    # Max 3 concurrent open roots/user; sibling cooldown blocks multi-branch
    # under one parent. Use one root + a deep chain (Legend spacing = 0).
    # Quarantine fires at ≥5 parts in 1h — including leftovers from prior runs.
    # Treat "account is quarantined" as success for this trigger and continue.
    rapid_user = posters[0]
    rapid_root: str | None = None
    try:
        rapid_root = create_root(rapid_user)
        print(f"  {rapid_user.username} root: {rapid_root}")
        leaf = rapid_root
        for i in range(4):
            leaf = continue_part(rapid_user, leaf)
            print(f"  {rapid_user.username} continue #{i + 1}: {leaf}")
            time.sleep(0.05)
        print("  warning: rapid user not quarantined after 5 parts")
    except RuntimeError as e:
        if "quarantined" in str(e).lower():
            print(f"  rapid_posting quarantine triggered OK: {e}")
        else:
            raise
    if rapid_root is None:
        # Prior run may already have roots; pick any listed root by this author via SQL.
        out = psql(
            "SELECT id::text FROM story_parts "
            f"WHERE author_id = (SELECT id FROM users WHERE username = '{rapid_user.username}') "
            "AND parent_part_id IS NULL "
            "ORDER BY created_at DESC LIMIT 1;"
        )
        for line in out.splitlines():
            line = line.strip()
            if len(line) == 36 and line.count("-") == 4:
                rapid_root = line
                break
        print(f"  using prior root: {rapid_root}")

    print("\n=== Roots + branches from other Legend posters ===")
    # Stay within MAX_CONCURRENT_OPEN_TREES=3 per user. One branch per
    # (author, parent) because of SIBLING_BRANCH_COOLDOWN_SECONDS=3600.
    story_ids: list[str] = [rapid_root] if rapid_root else []
    branch_ids: list[str] = []
    active_posters = posters[1:]  # skip quarantined rapid_user

    for poster in active_posters:
        for root_n in range(3):
            try:
                root_id = create_root(poster)
            except RuntimeError as e:
                print(f"  root skipped for {poster.username}: {e}")
                break
            story_ids.append(root_id)
            print(f"  root #{root_n + 1} by {poster.username}: {root_id}")
            time.sleep(0.05)

    # Cross-author continues: each poster adds one child under someone else's part.
    parents = list(story_ids)
    for poster in active_posters:
        for parent in random.sample(parents, k=min(4, len(parents))):
            try:
                child = continue_part(poster, parent)
                branch_ids.append(child)
                story_ids.append(child)
                print(f"  branch by {poster.username} under {parent[:8]}… -> {child}")
            except RuntimeError as e:
                print(f"  branch skipped: {e}")
            time.sleep(0.05)

    print("\n=== Voting war (trigger: story_score_threshold) ===")
    bait_author = active_posters[0]
    bait_id = None
    for parent in random.sample(story_ids, k=min(8, len(story_ids))):
        try:
            bait_id = continue_part(bait_author, parent)
            break
        except RuntimeError as e:
            print(f"  bait continue skipped under {parent[:8]}…: {e}")
    if bait_id is None:
        # Fall back to an existing part if every parent is on cooldown.
        bait_id = story_ids[-1]
        print(f"  using existing part as bait: {bait_id}")
    else:
        story_ids.append(bait_id)
        print(f"  bait story: {bait_id}")
    # Need vote_score ≤ -5; use enough distinct DOWN voters.
    for voter in voters:
        try:
            vote(voter.token, bait_id, "DOWN")
            print(f"  DOWN from {voter.username}")
        except RuntimeError as e:
            print(f"  vote skipped: {e}")
        time.sleep(0.05)

    print("\n=== Random voting noise ===")
    targets = random.sample(story_ids, min(15, len(story_ids)))
    for target in targets:
        for voter in random.sample(voters, k=min(5, len(voters))):
            vtype = random.choice(["UP", "DOWN"])
            try:
                vote(voter.token, target, vtype)
            except RuntimeError:
                pass
            time.sleep(0.02)
    print(f"  cast votes on {len(targets)} parts")

    print("\nWaiting for score-refresh quarantine...")
    time.sleep(3)

    print("\n=== Mass reports (trigger: user_reports) ===")
    report_author = active_posters[1] if len(active_posters) > 1 else active_posters[0]
    report_target = None
    for parent in random.sample(story_ids, k=min(8, len(story_ids))):
        try:
            report_target = continue_part(report_author, parent)
            break
        except RuntimeError as e:
            print(f"  report-target continue skipped: {e}")
    if report_target is None:
        report_target = next(
            (s for s in reversed(story_ids) if s != bait_id),
            story_ids[0],
        )
        print(f"  using existing part as report target: {report_target}")
    else:
        print(f"  report target: {report_target}")
    for reporter in reporters:
        try:
            resp = report(reporter.token, report_target)
            print(
                f"  report by {reporter.username}: "
                f"count={resp.get('report_count')} quarantined={resp.get('quarantined')}"
            )
        except RuntimeError as e:
            print(f"  report skipped: {e}")
        time.sleep(0.05)

    for extra in branch_ids[:2]:
        for reporter in reporters[:3]:
            try:
                report(reporter.token, extra)
            except RuntimeError:
                pass
            time.sleep(0.02)

    print("\n=== Force reputation quarantine (SQL) ===")
    force_reputation_quarantine(accounts[10].username)

    print("\n=== Queue snapshot (moderator API) ===")
    try:
        queue = request(
            "GET",
            "/moderator/quarantine-queue?limit=50",
            token=mod.token,
        )
        items = queue if isinstance(queue, list) else queue.get("items", queue)
        if isinstance(items, list):
            print(f"  open quarantine items: {len(items)}")
            triggers: dict[str, int] = {}
            for item in items:
                key = str(item.get("triggered_by", "?"))
                triggers[key] = triggers.get(key, 0) + 1
            for key, count in sorted(triggers.items()):
                print(f"    {key}: {count}")
        else:
            print(f"  unexpected queue payload: {queue}")
    except RuntimeError as e:
        print(f"  could not read queue (is moderator flag live?): {e}")
        print("  tip: log out/in as chaos_moderator in the UI if the link is missing")

    print(
        f"""
Done.
  Login as moderator: username={MODERATOR_USERNAME}  password={PASSWORD}
  Open: http://localhost:8001/moderator
  Spam accounts: chaos_user_01 .. chaos_user_{NUM_USERS:02d}  password={PASSWORD}
"""
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
