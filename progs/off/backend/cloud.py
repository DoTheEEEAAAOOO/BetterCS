import base64
import json
import re
import secrets
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import Blueprint, jsonify, request


cloud_api = Blueprint("cloud_api", __name__)
sessions = {}
GITHUB_API = "https://api.github.com"
TREE_FILE_PATH = ".bettercs/tree.json"
SESSION_COOKIE = "bettercs_session"


def github_request(token, path, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    github_request = Request(
        f"{GITHUB_API}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "BetterCS",
        },
    )

    try:
        with urlopen(github_request, timeout=20) as response:
            body = response.read()
            return response.status, json.loads(body) if body else {}
    except HTTPError as error:
        body = error.read()
        try:
            details = json.loads(body) if body else {}
        except json.JSONDecodeError:
            details = {}
        return error.code, details
    except (URLError, TimeoutError):
        return None, {}


def current_session():
    session_id = request.cookies.get(SESSION_COOKIE)
    return sessions.get(session_id) if session_id else None


def require_session():
    session = current_session()
    if session is None:
        return None, (jsonify({"ok": False, "message": "Sign in to BetterCS first."}), 401)
    return session, None


def build_tree(entries, repository, branch):
    root = {"type": "directory", "children": {}}

    for entry in entries:
        path_parts = entry.get("path", "").split("/")
        if not path_parts or not path_parts[0]:
            continue

        current = root
        for directory in path_parts[:-1]:
            children = current["children"]
            current = children.setdefault(
                directory,
                {"type": "directory", "children": {}},
            )

        name = path_parts[-1]
        if entry.get("type") == "tree":
            current["children"].setdefault(
                name,
                {"type": "directory", "children": {}},
            )
        else:
            current["children"][name] = {
                "type": entry.get("type", "file"),
                "path": entry.get("path"),
                "sha": entry.get("sha"),
                "size": entry.get("size"),
            }

    return {
        "schemaVersion": 1,
        "repository": repository,
        "branch": branch,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "root": root,
    }


@cloud_api.post("/api/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    token = str(payload.get("token", "")).strip()
    if not username or not token:
        return jsonify({"ok": False, "message": "Enter your GitHub username and token."}), 400

    status, user = github_request(token, "/user")
    if status is None:
        return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
    if status == 401:
        return jsonify({"ok": False, "message": "GitHub rejected that token."}), 401
    if status != 200:
        return jsonify({"ok": False, "message": "GitHub could not verify this login right now."}), 502
    if user.get("login", "").casefold() != username.casefold():
        return jsonify({"ok": False, "message": "That token belongs to a different GitHub username."}), 403

    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "token": token,
        "username": user["login"],
        "repo": None,
        "tree": None,
    }
    response = jsonify({"ok": True, "message": f"Signed in as {user['login']}.", "username": user["login"]})
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        secure=request.is_secure,
        samesite="Lax",
        max_age=86400,
        path="/api",
    )
    return response


@cloud_api.post("/api/repo")
def link_repository():
    session, error = require_session()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode", "existing")).strip().lower()

    if mode == "create":
        name = str(payload.get("repo", "bettercs-cloud")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            return jsonify({"ok": False, "message": "Use letters, numbers, dots, underscores, or hyphens for the repository name."}), 400

        status, details = github_request(
            session["token"],
            "/user/repos",
            method="POST",
            payload={
                "name": name,
                "private": True,
                "auto_init": True,
                "description": "BetterCS cloud storage",
            },
        )
        if status is None:
            return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
        if status == 422:
            return jsonify({"ok": False, "message": "That repository name is unavailable. Choose another name."}), 409
        if status != 201:
            return jsonify({"ok": False, "message": "GitHub could not create a private repository. Check that your token can create repositories."}), 403

        owner = details.get("owner", {}).get("login", session["username"])
        name = details.get("name", name)
    elif mode == "existing":
        repository = str(payload.get("repo", "")).strip()
        repository = re.sub(r"^https?://github\.com/", "", repository, flags=re.IGNORECASE)
        repository = repository.removesuffix(".git").strip("/")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            return jsonify({"ok": False, "message": "Use the format owner/repository or a GitHub repo URL."}), 400

        owner, name = repository.split("/", 1)
        repo_path = f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
        status, details = github_request(session["token"], repo_path)
        if status is None:
            return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
        if status != 200:
            return jsonify({"ok": False, "message": "Repository not found or not accessible with this token."}), 403
    else:
        return jsonify({"ok": False, "message": "Choose an existing repository or create a private one."}), 400

    owner = details.get("owner", {}).get("login", owner)
    name = details.get("name", name)
    repo_path = f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    if details.get("permissions", {}).get("push") is False:
        return jsonify({"ok": False, "message": "This GitHub token cannot write to that repository."}), 403

    branch = details.get("default_branch")
    if not branch:
        return jsonify({"ok": False, "message": "The repository has no default branch yet."}), 400

    tree_path = f"{repo_path}/git/trees/{quote(branch, safe='')}?recursive=1"
    tree_status, tree_data = github_request(session["token"], tree_path)
    if tree_status is None:
        return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
    if tree_status != 200:
        return jsonify({"ok": False, "message": "Could not read the repository file tree."}), 502
    if tree_data.get("truncated"):
        return jsonify({"ok": False, "message": "This repository is too large to load as one file tree."}), 413

    normalized_repo = f"{owner}/{name}"
    file_tree = build_tree(tree_data.get("tree", []), normalized_repo, branch)
    tree_json = json.dumps(file_tree, separators=(",", ":"), ensure_ascii=False)
    contents_path = f"{repo_path}/contents/{quote(TREE_FILE_PATH, safe='/')}"
    contents_status, contents = github_request(
        session["token"],
        f"{contents_path}?ref={quote(branch, safe='')}",
    )

    if contents_status not in (200, 404):
        return jsonify({"ok": False, "message": "Could not prepare the BetterCS tree file in this repository."}), 502

    file_payload = {
        "message": "Update BetterCS repository file tree",
        "content": base64.b64encode(tree_json.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if contents_status == 200 and contents.get("sha"):
        file_payload["sha"] = contents["sha"]

    write_status, _ = github_request(
        session["token"],
        contents_path,
        method="PUT",
        payload=file_payload,
    )
    if write_status is None:
        return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
    if write_status not in (200, 201):
        return jsonify({"ok": False, "message": "GitHub could not save the BetterCS file tree. Check token write access."}), 502

    session["repo"] = normalized_repo
    session["tree"] = file_tree
    return jsonify({
        "ok": True,
        "message": f"Linked {normalized_repo} as your BetterCS cloud storage.",
        "repo": normalized_repo,
        "tree": file_tree,
    })


@cloud_api.get("/api/session")
def get_session():
    session, error = require_session()
    if error:
        return error
    return jsonify({
        "ok": True,
        "username": session["username"],
        "repo": session["repo"],
        "treeLoaded": session["tree"] is not None,
    })


@cloud_api.get("/api/tree")
def get_tree():
    session, error = require_session()
    if error:
        return error
    if session["repo"] is None or session["tree"] is None:
        return jsonify({"ok": False, "message": "Link a GitHub repository first."}), 409
    return jsonify({"ok": True, "repo": session["repo"], "tree": session["tree"]})