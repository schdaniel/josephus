"""Frontend-aware code analysis — route extraction and screen-to-code matching."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import logfire


@dataclass
class RouteEntry:
    """A single route mapping from code."""

    path: str  # URL path pattern, e.g., "/dashboard", "/users/:id"
    component: str  # Component name or file path
    source_file: str  # File where this route was defined


@dataclass
class RouteMap:
    """Collection of extracted routes."""

    routes: list[RouteEntry] = field(default_factory=list)
    framework: str | None = None


# Frontend file patterns, ordered by importance for UI documentation
FRONTEND_PRIORITY_PATTERNS = [
    # Routes / pages (highest priority)
    r"^(src/)?(app|pages|views|routes)/",
    r"(routes|routing)\.(ts|tsx|js|jsx)$",
    # Layouts and templates
    r"(layout|template)\.(ts|tsx|js|jsx|vue|svelte)$",
    # Components
    r"^(src/)?(components|ui)/",
    # Stores / state
    r"^(src/)?(store|stores|state)/",
    # Config files
    r"(next\.config|nuxt\.config|vite\.config|vue\.config)",
    r"package\.json$",
]


def prioritize_frontend_files(files: list[str]) -> list[str]:
    """Sort files with frontend-relevant files first.

    Routes, pages, and component files are prioritized over
    backend, utility, and test files.
    """

    def priority_score(path: str) -> int:
        for i, pattern in enumerate(FRONTEND_PRIORITY_PATTERNS):
            if re.search(pattern, path):
                return i
        return len(FRONTEND_PRIORITY_PATTERNS)  # Non-matching files go last

    return sorted(files, key=priority_score)


def detect_framework(files: list[str], file_contents: dict[str, str] | None = None) -> str | None:
    """Detect frontend framework from project files.

    Checks package.json dependencies for known frameworks.
    """
    if file_contents is None:
        file_contents = {}

    # Check package.json
    pkg_content = file_contents.get("package.json")
    if pkg_content:
        try:
            pkg = json.loads(pkg_content)
            all_deps = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {}),
            }

            if "next" in all_deps:
                return "nextjs"
            if "react-router-dom" in all_deps or "react-router" in all_deps:
                return "react-router"
            if "vue-router" in all_deps:
                return "vue-router"
            if "vue" in all_deps:
                return "vue"
            if "react" in all_deps:
                return "react"
            if "svelte" in all_deps or "@sveltejs/kit" in all_deps:
                return "svelte"
            if "angular" in all_deps or "@angular/core" in all_deps:
                return "angular"
        except json.JSONDecodeError:
            pass

    # Heuristic: check for framework-specific file patterns
    file_set = set(files)
    if any(f.startswith("app/") or f.startswith("src/app/") for f in file_set) and any(
        "next.config" in f for f in file_set
    ):
        return "nextjs"
    if any("nuxt.config" in f for f in file_set):
        return "nuxt"

    return None


def extract_route_map(
    files: list[str],
    file_contents: dict[str, str],
    framework: str | None = None,
) -> RouteMap:
    """Extract URL routes from source code.

    Supports Next.js (app router, pages), React Router, and Vue Router.
    """
    if framework is None:
        framework = detect_framework(files, file_contents)

    logfire.info("Extracting route map", framework=framework)

    if framework == "nextjs":
        return _extract_nextjs_routes(files)
    elif framework == "react-router":
        return _extract_react_router_routes(files, file_contents)
    elif framework == "vue-router":
        return _extract_vue_router_routes(files, file_contents)
    else:
        # Fallback: infer from file structure
        return _extract_file_based_routes(files)


def _extract_nextjs_routes(files: list[str]) -> RouteMap:
    """Extract routes from Next.js app router or pages directory."""
    routes: list[RouteEntry] = []

    for filepath in files:
        # App router: app/dashboard/page.tsx → /dashboard
        match = re.match(r"^(?:src/)?app/(.+)/page\.(tsx?|jsx?)$", filepath)
        if match:
            route_path = "/" + match.group(1)
            # Convert [param] to :param
            route_path = re.sub(r"\[(\w+)\]", r":\1", route_path)
            routes.append(
                RouteEntry(
                    path=route_path,
                    component=filepath.split("/")[-2],
                    source_file=filepath,
                )
            )
            continue

        # App router: app/page.tsx → /
        if re.match(r"^(?:src/)?app/page\.(tsx?|jsx?)$", filepath):
            routes.append(RouteEntry(path="/", component="root", source_file=filepath))
            continue

        # Pages router: pages/dashboard.tsx → /dashboard
        match = re.match(r"^(?:src/)?pages/(.+)\.(tsx?|jsx?)$", filepath)
        if match:
            page_path = match.group(1)
            if page_path == "index":
                route_path = "/"
            elif page_path.endswith("/index"):
                route_path = "/" + page_path.rsplit("/index", 1)[0]
            else:
                route_path = "/" + page_path
            # Skip special Next.js files
            if page_path.startswith("_") or page_path.startswith("api/"):
                continue
            route_path = re.sub(r"\[(\w+)\]", r":\1", route_path)
            routes.append(
                RouteEntry(
                    path=route_path,
                    component=page_path.split("/")[-1],
                    source_file=filepath,
                )
            )

    return RouteMap(routes=routes, framework="nextjs")


def _extract_react_router_routes(files: list[str], file_contents: dict[str, str]) -> RouteMap:
    """Extract routes from React Router configuration."""
    routes: list[RouteEntry] = []

    # Look for route definitions in likely files
    route_files = [f for f in files if re.search(r"(routes?|router|App)\.(tsx?|jsx?)$", f)]

    for filepath in route_files:
        content = file_contents.get(filepath, "")
        if not content:
            continue

        # Match <Route path="/dashboard" element={<Dashboard />} />
        for match in re.finditer(
            r"""<Route\s+[^>]*path=["']([^"']+)["'][^>]*(?:element=\{<(\w+)|component=\{(\w+))""",
            content,
        ):
            path = match.group(1)
            component = match.group(2) or match.group(3) or "Unknown"
            routes.append(RouteEntry(path=path, component=component, source_file=filepath))

        # Match { path: "/dashboard", element: <Dashboard /> }
        for match in re.finditer(
            r"""path:\s*["']([^"']+)["'][^}]*(?:element|component):\s*<?(\w+)""",
            content,
        ):
            path = match.group(1)
            component = match.group(2)
            routes.append(RouteEntry(path=path, component=component, source_file=filepath))

    return RouteMap(routes=routes, framework="react-router")


def _extract_vue_router_routes(files: list[str], file_contents: dict[str, str]) -> RouteMap:
    """Extract routes from Vue Router configuration."""
    routes: list[RouteEntry] = []

    router_files = [f for f in files if re.search(r"(router|routes)\.(ts|js)$", f)]

    for filepath in router_files:
        content = file_contents.get(filepath, "")
        if not content:
            continue

        # Match { path: '/dashboard', component: Dashboard }
        for match in re.finditer(
            r"""path:\s*["']([^"']+)["'][^}]*(?:component:\s*(\w+)|name:\s*["'](\w+)["'])""",
            content,
        ):
            path = match.group(1)
            component = match.group(2) or match.group(3) or "Unknown"
            routes.append(RouteEntry(path=path, component=component, source_file=filepath))

    return RouteMap(routes=routes, framework="vue-router")


def _extract_file_based_routes(files: list[str]) -> RouteMap:
    """Fallback: infer routes from file structure (pages/views directories)."""
    routes: list[RouteEntry] = []

    for filepath in files:
        match = re.match(r"^(?:src/)?(pages|views)/(.+)\.(tsx?|jsx?|vue|svelte)$", filepath)
        if match:
            page_path = match.group(2)
            if page_path == "index":
                route_path = "/"
            elif page_path.endswith("/index"):
                route_path = "/" + page_path.rsplit("/index", 1)[0]
            else:
                route_path = "/" + page_path
            routes.append(
                RouteEntry(
                    path=route_path,
                    component=page_path.split("/")[-1],
                    source_file=filepath,
                )
            )

    return RouteMap(routes=routes, framework=None)


def match_screens_to_code(
    screen_urls: list[str],
    files: list[str],
    route_map: RouteMap,
) -> dict[str, list[str]]:
    """Match crawled screen URLs to source code files.

    Returns a dict mapping screen URLs to lists of relevant source file paths.
    """
    result: dict[str, list[str]] = {}

    for url in screen_urls:
        parsed = urlparse(url)
        url_path = parsed.path.rstrip("/") or "/"
        matched_files: list[str] = []

        # Try exact route match first
        for route in route_map.routes:
            if _paths_match(url_path, route.path):
                matched_files.append(route.source_file)

        # If no exact match, try fuzzy match on path segments
        if not matched_files:
            path_parts = [p for p in url_path.strip("/").split("/") if p]
            for filepath in files:
                file_lower = filepath.lower()
                # Check if any path segment appears in the filename
                if (
                    path_parts
                    and any(part.lower() in file_lower for part in path_parts)
                    and re.search(r"\.(tsx?|jsx?|vue|svelte)$", filepath)
                ):
                    matched_files.append(filepath)

        result[url] = matched_files[:10]  # Limit to top 10 matches

    return result


def _paths_match(url_path: str, route_path: str) -> bool:
    """Check if a URL path matches a route pattern.

    /users/123 matches /users/:id
    /dashboard matches /dashboard
    """
    url_parts = url_path.strip("/").split("/")
    route_parts = route_path.strip("/").split("/")

    if len(url_parts) != len(route_parts):
        return False

    for url_part, route_part in zip(url_parts, route_parts, strict=True):
        if route_part.startswith(":"):
            continue  # Wildcard match
        if url_part != route_part:
            return False

    return True
