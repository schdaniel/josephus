"""Tests for frontend-aware code analysis."""

import json

from josephus.analyzer.frontend import (
    detect_framework,
    extract_route_map,
    match_screens_to_code,
    prioritize_frontend_files,
)


class TestPrioritizeFrontendFiles:
    def test_routes_before_utils(self):
        files = ["src/utils/helper.ts", "src/pages/dashboard.tsx", "src/lib/api.ts"]
        result = prioritize_frontend_files(files)
        assert result[0] == "src/pages/dashboard.tsx"

    def test_components_before_backend(self):
        files = ["server/main.py", "src/components/Button.tsx", "README.md"]
        result = prioritize_frontend_files(files)
        assert result[0] == "src/components/Button.tsx"

    def test_package_json_included(self):
        files = ["src/index.ts", "package.json", "README.md"]
        result = prioritize_frontend_files(files)
        assert "package.json" in result


class TestDetectFramework:
    def test_nextjs(self):
        pkg = json.dumps({"dependencies": {"next": "14.0.0", "react": "18.0.0"}})
        result = detect_framework(["package.json"], {"package.json": pkg})
        assert result == "nextjs"

    def test_react_router(self):
        pkg = json.dumps({"dependencies": {"react": "18.0.0", "react-router-dom": "6.0.0"}})
        result = detect_framework(["package.json"], {"package.json": pkg})
        assert result == "react-router"

    def test_vue_router(self):
        pkg = json.dumps({"dependencies": {"vue": "3.0.0", "vue-router": "4.0.0"}})
        result = detect_framework(["package.json"], {"package.json": pkg})
        assert result == "vue-router"

    def test_no_package_json(self):
        result = detect_framework(["src/main.py"], {})
        assert result is None

    def test_nextjs_from_file_structure(self):
        files = ["next.config.js", "app/page.tsx", "app/dashboard/page.tsx"]
        result = detect_framework(files, {})
        assert result == "nextjs"


class TestExtractNextjsRoutes:
    def test_app_router(self):
        files = [
            "app/page.tsx",
            "app/dashboard/page.tsx",
            "app/settings/page.tsx",
            "app/users/[id]/page.tsx",
        ]
        pkg = json.dumps({"dependencies": {"next": "14.0.0"}})
        result = extract_route_map(files, {"package.json": pkg}, framework="nextjs")

        paths = [r.path for r in result.routes]
        assert "/" in paths
        assert "/dashboard" in paths
        assert "/settings" in paths
        assert "/users/:id" in paths
        assert result.framework == "nextjs"

    def test_pages_router(self):
        files = [
            "pages/index.tsx",
            "pages/about.tsx",
            "pages/users/[id].tsx",
            "pages/_app.tsx",  # Should be skipped
            "pages/api/hello.ts",  # Should be skipped
        ]
        pkg = json.dumps({"dependencies": {"next": "14.0.0"}})
        result = extract_route_map(files, {"package.json": pkg}, framework="nextjs")

        paths = [r.path for r in result.routes]
        assert "/" in paths
        assert "/about" in paths
        assert "/users/:id" in paths
        assert len(result.routes) == 3  # _app and api/ excluded

    def test_src_app_router(self):
        files = ["src/app/page.tsx", "src/app/dashboard/page.tsx"]
        result = extract_route_map(files, {}, framework="nextjs")
        paths = [r.path for r in result.routes]
        assert "/" in paths
        assert "/dashboard" in paths


class TestExtractReactRouterRoutes:
    def test_jsx_routes(self):
        content = """
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/users/:id" element={<UserProfile />} />
        """
        files = ["src/App.tsx"]
        result = extract_route_map(files, {"src/App.tsx": content}, framework="react-router")

        paths = [r.path for r in result.routes]
        assert "/dashboard" in paths
        assert "/settings" in paths
        assert "/users/:id" in paths
        assert result.framework == "react-router"

    def test_object_routes(self):
        content = """
        const routes = [
            { path: "/dashboard", element: <Dashboard /> },
            { path: "/settings", element: <Settings /> },
        ];
        """
        files = ["src/routes.tsx"]
        result = extract_route_map(files, {"src/routes.tsx": content}, framework="react-router")

        paths = [r.path for r in result.routes]
        assert "/dashboard" in paths
        assert "/settings" in paths


class TestExtractVueRouterRoutes:
    def test_vue_routes(self):
        content = """
        const routes = [
            { path: '/dashboard', component: Dashboard },
            { path: '/settings', name: 'settings' },
            { path: '/users/:id', component: UserProfile },
        ];
        """
        files = ["src/router.ts"]
        result = extract_route_map(files, {"src/router.ts": content}, framework="vue-router")

        paths = [r.path for r in result.routes]
        assert "/dashboard" in paths
        assert "/settings" in paths
        assert "/users/:id" in paths


class TestMatchScreensToCode:
    def test_exact_route_match(self):
        from josephus.analyzer.frontend import RouteEntry, RouteMap

        route_map = RouteMap(
            routes=[
                RouteEntry(
                    path="/dashboard", component="Dashboard", source_file="src/pages/dashboard.tsx"
                ),
                RouteEntry(
                    path="/settings", component="Settings", source_file="src/pages/settings.tsx"
                ),
            ]
        )

        result = match_screens_to_code(
            screen_urls=["https://app.example.com/dashboard"],
            files=["src/pages/dashboard.tsx", "src/pages/settings.tsx"],
            route_map=route_map,
        )

        assert "https://app.example.com/dashboard" in result
        assert "src/pages/dashboard.tsx" in result["https://app.example.com/dashboard"]

    def test_parameterized_route_match(self):
        from josephus.analyzer.frontend import RouteEntry, RouteMap

        route_map = RouteMap(
            routes=[
                RouteEntry(
                    path="/users/:id",
                    component="UserProfile",
                    source_file="src/pages/users/[id].tsx",
                ),
            ]
        )

        result = match_screens_to_code(
            screen_urls=["https://app.example.com/users/123"],
            files=["src/pages/users/[id].tsx"],
            route_map=route_map,
        )

        assert "src/pages/users/[id].tsx" in result["https://app.example.com/users/123"]

    def test_fuzzy_match_fallback(self):
        from josephus.analyzer.frontend import RouteMap

        route_map = RouteMap(routes=[])  # Empty — no routes

        result = match_screens_to_code(
            screen_urls=["https://app.example.com/dashboard"],
            files=["src/components/Dashboard.tsx", "src/utils/api.ts"],
            route_map=route_map,
        )

        # Should match on "dashboard" in filename
        assert "src/components/Dashboard.tsx" in result["https://app.example.com/dashboard"]
