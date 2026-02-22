"""DOM extractor — structured data extraction from a Playwright page."""

from __future__ import annotations

import logfire
from playwright.async_api import Page

from josephus.crawler.models import (
    DOMData,
    FormField,
    Heading,
    InteractiveElement,
    NavLink,
)


class DOMExtractor:
    """Extracts structured data from a page's DOM for LLM consumption."""

    # Tab selectors — role-based, ARIA, and common framework selectors
    TAB_SELECTORS = [
        '[role="tab"]',
        "[aria-selected]",
        ".MuiTab-root",
        ".ant-tabs-tab",
        ".nav-tabs .nav-link",
        ".tab-item",
        '[data-toggle="tab"]',
        '[data-bs-toggle="tab"]',
    ]

    # Modal trigger selectors
    MODAL_SELECTORS = [
        '[data-toggle="modal"]',
        '[data-bs-toggle="modal"]',
        "[aria-haspopup='dialog']",
        ".MuiDialog-root",
        ".ant-modal",
        ".modal-trigger",
    ]

    async def extract(self, page: Page) -> DOMData:
        """Extract structured DOM data from a page."""
        logfire.info("Extracting DOM data", url=page.url)

        headings = await self._extract_headings(page)
        nav_links = await self._extract_nav_links(page)
        interactive = await self._extract_interactive_elements(page)
        form_fields = await self._extract_form_fields(page)
        visible_text = await self._extract_visible_text(page)
        aria_landmarks = await self._extract_aria_landmarks(page)
        tabs = await self._detect_tabs(page)
        modals = await self._detect_modals(page)

        return DOMData(
            headings=headings,
            nav_links=nav_links,
            interactive_elements=interactive,
            form_fields=form_fields,
            visible_text=visible_text,
            aria_landmarks=aria_landmarks,
            detected_tabs=tabs,
            detected_modals=modals,
        )

    async def _extract_headings(self, page: Page) -> list[Heading]:
        """Extract heading hierarchy (h1-h6)."""
        headings = []
        for level in range(1, 7):
            elements = await page.query_selector_all(f"h{level}")
            for el in elements:
                text = await el.inner_text()
                text = text.strip()
                if text:
                    headings.append(Heading(level=level, text=text))
        return headings

    async def _extract_nav_links(self, page: Page) -> list[NavLink]:
        """Extract navigation links."""
        links: list[NavLink] = []
        # Look in nav elements and common nav containers
        nav_selectors = ["nav a", '[role="navigation"] a', ".sidebar a", ".navbar a"]

        seen_hrefs: set[str] = set()
        for selector in nav_selectors:
            elements = await page.query_selector_all(selector)
            for el in elements:
                try:
                    text = (await el.inner_text()).strip()
                    href = await el.get_attribute("href") or ""
                    if not text or not href or href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)
                    is_active = False
                    class_attr = await el.get_attribute("class") or ""
                    aria_current = await el.get_attribute("aria-current") or ""
                    if "active" in class_attr or aria_current == "page":
                        is_active = True
                    links.append(NavLink(text=text, href=href, is_active=is_active))
                except Exception:
                    continue
        return links

    async def _extract_interactive_elements(self, page: Page) -> list[InteractiveElement]:
        """Extract buttons, links, and other interactive elements."""
        elements: list[InteractiveElement] = []

        # Buttons
        buttons = await page.query_selector_all(
            "button:visible, [role='button']:visible, input[type='submit']:visible"
        )
        for btn in buttons:
            try:
                label = (await btn.inner_text()).strip()
                if not label:
                    label = await btn.get_attribute("aria-label") or ""
                    if not label:
                        label = await btn.get_attribute("title") or ""
                if label:
                    role = await btn.get_attribute("role")
                    elements.append(
                        InteractiveElement(
                            element_type="button",
                            label=label,
                            selector=await self._build_selector(btn, page),
                            action="click",
                            aria_role=role,
                        )
                    )
            except Exception:
                continue

        # Select dropdowns
        selects = await page.query_selector_all("select:visible")
        for sel in selects:
            try:
                label = ""
                sel_id = await sel.get_attribute("id")
                if sel_id:
                    label_el = await page.query_selector(f'label[for="{sel_id}"]')
                    if label_el:
                        label = (await label_el.inner_text()).strip()
                if not label:
                    label = await sel.get_attribute("aria-label") or "Dropdown"
                elements.append(
                    InteractiveElement(
                        element_type="select",
                        label=label,
                        selector=await self._build_selector(sel, page),
                        action="select",
                    )
                )
            except Exception:
                continue

        return elements

    async def _extract_form_fields(self, page: Page) -> list[FormField]:
        """Extract form fields with their labels."""
        fields: list[FormField] = []

        inputs = await page.query_selector_all(
            "input:visible:not([type='hidden']):not([type='submit']):not([type='button']), "
            "textarea:visible, "
            "select:visible"
        )

        for inp in inputs:
            try:
                field_type = await inp.get_attribute("type") or "text"
                tag = await inp.evaluate("el => el.tagName.toLowerCase()")
                if tag == "textarea":
                    field_type = "textarea"
                elif tag == "select":
                    field_type = "select"

                name = await inp.get_attribute("name")
                placeholder = await inp.get_attribute("placeholder")
                required = await inp.get_attribute("required") is not None

                # Try to find label
                label = None
                inp_id = await inp.get_attribute("id")
                if inp_id:
                    label_el = await page.query_selector(f'label[for="{inp_id}"]')
                    if label_el:
                        label = (await label_el.inner_text()).strip()
                if not label:
                    label = await inp.get_attribute("aria-label")

                fields.append(
                    FormField(
                        field_type=field_type,
                        label=label,
                        name=name,
                        placeholder=placeholder,
                        required=required,
                        selector=await self._build_selector(inp, page),
                    )
                )
            except Exception:
                continue

        return fields

    async def _extract_visible_text(self, page: Page) -> str:
        """Extract visible text content, excluding scripts and styles."""
        text = await page.evaluate("""
            () => {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode: (node) => {
                            const parent = node.parentElement;
                            if (!parent) return NodeFilter.FILTER_REJECT;
                            const tag = parent.tagName.toLowerCase();
                            if (['script', 'style', 'noscript', 'svg'].includes(tag)) {
                                return NodeFilter.FILTER_REJECT;
                            }
                            const style = window.getComputedStyle(parent);
                            if (style.display === 'none' || style.visibility === 'hidden') {
                                return NodeFilter.FILTER_REJECT;
                            }
                            const text = node.textContent.trim();
                            if (!text) return NodeFilter.FILTER_REJECT;
                            return NodeFilter.FILTER_ACCEPT;
                        }
                    }
                );
                const texts = [];
                let node;
                while ((node = walker.nextNode())) {
                    const text = node.textContent.trim();
                    if (text) texts.push(text);
                }
                return texts.join(' ');
            }
        """)
        # Truncate to reasonable size for LLM context
        max_length = 10000
        if len(text) > max_length:
            text = text[:max_length] + "..."
        return text

    async def _extract_aria_landmarks(self, page: Page) -> list[str]:
        """Extract ARIA landmark roles."""
        landmarks = await page.evaluate("""
            () => {
                const roles = ['banner', 'navigation', 'main', 'complementary',
                              'contentinfo', 'search', 'form', 'region'];
                const found = [];
                for (const role of roles) {
                    const els = document.querySelectorAll(`[role="${role}"]`);
                    if (els.length > 0) found.push(role);
                }
                // Also check semantic HTML elements
                const semanticMap = {
                    'header': 'banner', 'nav': 'navigation', 'main': 'main',
                    'aside': 'complementary', 'footer': 'contentinfo'
                };
                for (const [tag, role] of Object.entries(semanticMap)) {
                    if (document.querySelector(tag) && !found.includes(role)) {
                        found.push(role);
                    }
                }
                return found;
            }
        """)
        return landmarks

    async def _detect_tabs(self, page: Page) -> list[str]:
        """Detect tab labels on the page."""
        tabs: list[str] = []
        for selector in self.TAB_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = (await el.inner_text()).strip()
                    if text and text not in tabs:
                        tabs.append(text)
            except Exception:
                continue
        return tabs

    async def _detect_modals(self, page: Page) -> list[str]:
        """Detect modal triggers on the page."""
        modals: list[str] = []
        for selector in self.MODAL_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = (await el.inner_text()).strip()
                    if not text:
                        text = await el.get_attribute("aria-label") or ""
                    if text and text not in modals:
                        modals.append(text)
            except Exception:
                continue
        return modals

    async def _build_selector(self, element: object, page: Page) -> str:
        """Build a CSS selector for an element (best effort)."""
        try:
            selector = await page.evaluate(
                """(el) => {
                    if (el.id) return '#' + el.id;
                    const tag = el.tagName.toLowerCase();
                    const classes = Array.from(el.classList).slice(0, 2).join('.');
                    if (classes) return tag + '.' + classes;
                    return tag;
                }""",
                element,
            )
            return selector
        except Exception:
            return ""
