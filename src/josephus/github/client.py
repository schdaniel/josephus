"""GitHub API client for repository operations."""

import base64
from dataclasses import dataclass
from typing import Any

import httpx
import logfire

from josephus.github.auth import GitHubAuth


@dataclass
class RepoFile:
    """A file from a GitHub repository."""

    path: str
    name: str
    content: str
    sha: str
    size: int
    encoding: str = "utf-8"


@dataclass
class RepoTree:
    """Directory tree structure from a repository."""

    sha: str
    tree: list[dict[str, Any]]
    truncated: bool


@dataclass
class Repository:
    """GitHub repository metadata."""

    id: int
    name: str
    full_name: str
    description: str | None
    default_branch: str
    language: str | None
    private: bool
    html_url: str


class GitHubClient:
    """Client for GitHub API operations.

    Handles repository content fetching, branch creation, commits, and PRs.
    Uses installation tokens for authentication.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, auth: GitHubAuth | None = None) -> None:
        self.auth = auth or GitHubAuth()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        installation_id: int,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an authenticated request to GitHub API."""
        token = await self.auth.get_installation_token(installation_id)
        client = await self._get_client()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token.token}"

        response = await client.request(method, path, headers=headers, **kwargs)

        # Log API calls
        logfire.debug(
            "GitHub API request",
            method=method,
            path=path,
            status=response.status_code,
        )

        return response

    # ─────────────────────────────────────────────────────────────────
    # Repository Operations
    # ─────────────────────────────────────────────────────────────────

    async def get_repository(
        self,
        installation_id: int,
        owner: str,
        repo: str,
    ) -> Repository:
        """Get repository metadata."""
        response = await self._request(
            "GET",
            f"/repos/{owner}/{repo}",
            installation_id,
        )
        response.raise_for_status()
        data = response.json()

        return Repository(
            id=data["id"],
            name=data["name"],
            full_name=data["full_name"],
            description=data.get("description"),
            default_branch=data["default_branch"],
            language=data.get("language"),
            private=data["private"],
            html_url=data["html_url"],
        )

    async def get_tree(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        tree_sha: str = "HEAD",
        recursive: bool = True,
    ) -> RepoTree:
        """Get repository tree (file listing).

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            tree_sha: Tree SHA or branch name (default: HEAD)
            recursive: Whether to get full tree recursively

        Returns:
            RepoTree with file/directory listing
        """
        params = {"recursive": "1"} if recursive else {}
        response = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/git/trees/{tree_sha}",
            installation_id,
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        return RepoTree(
            sha=data["sha"],
            tree=data["tree"],
            truncated=data.get("truncated", False),
        )

    async def get_file_content(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,
    ) -> RepoFile:
        """Get contents of a single file.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            path: File path in repository
            ref: Git ref (branch, tag, commit SHA)

        Returns:
            RepoFile with decoded content
        """
        params = {"ref": ref} if ref else {}
        response = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            installation_id,
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        # Decode base64 content
        content = ""
        if data.get("content"):
            content = base64.b64decode(data["content"]).decode("utf-8")

        return RepoFile(
            path=data["path"],
            name=data["name"],
            content=content,
            sha=data["sha"],
            size=data["size"],
        )

    async def get_directory_contents(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        path: str = "",
        ref: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get contents of a directory.

        Returns list of file/directory entries (not recursive).
        """
        params = {"ref": ref} if ref else {}
        response = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            installation_id,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    # ─────────────────────────────────────────────────────────────────
    # Branch Operations
    # ─────────────────────────────────────────────────────────────────

    async def get_ref(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        ref: str,
    ) -> dict[str, Any]:
        """Get a git reference (branch/tag)."""
        response = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/git/ref/{ref}",
            installation_id,
        )
        response.raise_for_status()
        return response.json()

    async def create_branch(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        branch_name: str,
        from_sha: str,
    ) -> dict[str, Any]:
        """Create a new branch.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            branch_name: Name for the new branch
            from_sha: SHA to branch from

        Returns:
            Created ref object
        """
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            installation_id,
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": from_sha,
            },
        )
        response.raise_for_status()
        return response.json()

    # ─────────────────────────────────────────────────────────────────
    # Commit Operations
    # ─────────────────────────────────────────────────────────────────

    async def create_or_update_file(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a file in the repository.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            path: File path
            content: File content (will be base64 encoded)
            message: Commit message
            branch: Target branch
            sha: File SHA (required for updates, None for new files)

        Returns:
            Commit and content objects
        """
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        payload: dict[str, Any] = {
            "message": message,
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        response = await self._request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{path}",
            installation_id,
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def create_tree(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        base_tree: str,
        tree: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create a git tree (for multi-file commits).

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            base_tree: SHA of the base tree
            tree: List of tree entries (path, mode, type, content/sha)

        Returns:
            Created tree object
        """
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/trees",
            installation_id,
            json={
                "base_tree": base_tree,
                "tree": tree,
            },
        )
        response.raise_for_status()
        return response.json()

    async def create_commit(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        message: str,
        tree_sha: str,
        parent_shas: list[str],
    ) -> dict[str, Any]:
        """Create a git commit.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            message: Commit message
            tree_sha: SHA of the tree for this commit
            parent_shas: List of parent commit SHAs

        Returns:
            Created commit object
        """
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/commits",
            installation_id,
            json={
                "message": message,
                "tree": tree_sha,
                "parents": parent_shas,
            },
        )
        response.raise_for_status()
        return response.json()

    async def update_ref(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        ref: str,
        sha: str,
        force: bool = False,
    ) -> dict[str, Any]:
        """Update a git reference to point to a new SHA."""
        response = await self._request(
            "PATCH",
            f"/repos/{owner}/{repo}/git/refs/{ref}",
            installation_id,
            json={
                "sha": sha,
                "force": force,
            },
        )
        response.raise_for_status()
        return response.json()

    # ─────────────────────────────────────────────────────────────────
    # Pull Request Operations
    # ─────────────────────────────────────────────────────────────────

    async def create_pull_request(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = False,
    ) -> dict[str, Any]:
        """Create a pull request.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            title: PR title
            body: PR description
            head: Head branch (source)
            base: Base branch (target)
            draft: Whether to create as draft PR

        Returns:
            Created pull request object
        """
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            installation_id,
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "draft": draft,
            },
        )
        response.raise_for_status()
        return response.json()

    # ─────────────────────────────────────────────────────────────────
    # High-Level Operations
    # ─────────────────────────────────────────────────────────────────

    async def create_blob(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        content: str,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """Create a git blob.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            content: Blob content (text or base64-encoded binary)
            encoding: Content encoding ("utf-8" or "base64")

        Returns:
            Created blob object with SHA
        """
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/blobs",
            installation_id,
            json={
                "content": content,
                "encoding": encoding,
            },
        )
        response.raise_for_status()
        return response.json()

    async def commit_files(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        branch: str,
        files: dict[str, str],
        message: str,
        base_branch: str | None = None,
        binary_files: dict[str, bytes] | None = None,
    ) -> dict[str, Any]:
        """Commit multiple files in a single commit.

        Creates a new branch if it doesn't exist, then commits all files.
        Supports both text files and binary files (e.g., screenshots).

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            branch: Target branch name
            files: Dict of path -> text content
            message: Commit message
            base_branch: Branch to base from (if creating new branch)
            binary_files: Dict of path -> binary content (e.g., screenshots)

        Returns:
            Created commit object
        """
        binary_files = binary_files or {}

        # Warn if total binary size exceeds 10MB
        total_binary_size = sum(len(data) for data in binary_files.values())
        if total_binary_size > 10 * 1024 * 1024:
            logfire.warn(
                "Binary files exceed 10MB total — consider using Git LFS",
                total_size_mb=total_binary_size / (1024 * 1024),
                binary_file_count=len(binary_files),
            )

        # Get base branch ref
        repo_info = await self.get_repository(installation_id, owner, repo)
        base = base_branch or repo_info.default_branch

        try:
            ref = await self.get_ref(installation_id, owner, repo, f"heads/{branch}")
            base_sha = ref["object"]["sha"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Branch doesn't exist, create from base
                base_ref = await self.get_ref(installation_id, owner, repo, f"heads/{base}")
                base_sha = base_ref["object"]["sha"]
                await self.create_branch(installation_id, owner, repo, branch, base_sha)
            else:
                raise

        # Get current tree
        current_tree = await self.get_tree(installation_id, owner, repo, base_sha, recursive=False)

        # Build tree entries for text files
        tree_entries = []
        for path, content in files.items():
            tree_entries.append(
                {
                    "path": path,
                    "mode": "100644",  # Regular file
                    "type": "blob",
                    "content": content,
                }
            )

        # Create blobs for binary files and add to tree
        for path, data in binary_files.items():
            encoded = base64.b64encode(data).decode("ascii")
            blob = await self.create_blob(installation_id, owner, repo, encoded, encoding="base64")
            tree_entries.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob["sha"],
                }
            )

        # Create new tree
        new_tree = await self.create_tree(
            installation_id, owner, repo, current_tree.sha, tree_entries
        )

        # Create commit
        commit = await self.create_commit(
            installation_id,
            owner,
            repo,
            message,
            new_tree["sha"],
            [base_sha],
        )

        # Update branch ref
        await self.update_ref(
            installation_id,
            owner,
            repo,
            f"heads/{branch}",
            commit["sha"],
        )

        all_paths = list(files.keys()) + list(binary_files.keys())
        logfire.info(
            "Committed files",
            repo=f"{owner}/{repo}",
            branch=branch,
            files=all_paths,
            text_files=len(files),
            binary_files=len(binary_files),
            commit_sha=commit["sha"],
        )

        return commit
