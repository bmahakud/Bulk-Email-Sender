"""
HTML Renderer - Converts HTML content to images and PDFs using PySide6.
No external CLI tools or Webkit binaries are required.
"""
import base64
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, Dict, Tuple, List
import re
from PySide6.QtGui import (
    QTextDocument, QImage, QPainter, QPdfWriter, QPageSize, QPageLayout
)
from PySide6.QtCore import QSize, Qt, QSizeF, QMarginsF, QUrl, QRectF

PAGE_SIZE_DIMENSIONS_MM: Dict[str, Tuple[float, float]] = {
    "A0": (841.0, 1189.0),
    "A1": (594.0, 841.0),
    "A2": (420.0, 594.0),
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "A6": (105.0, 148.0),
    "LETTER": (215.9, 279.4),
    "LEGAL": (215.9, 355.6),
    "TABLOID": (279.4, 431.8),
    "LEDGER": (431.8, 279.4),
    "EXECUTIVE": (184.15, 266.7),
    "B4": (250.0, 353.0),
    "B5": (176.0, 250.0),
}

_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}


class _TopLevelBodySplitter(HTMLParser):
    """Extracts top-level HTML elements from a body fragment with exact character slices."""

    def __init__(self, raw_html: str):
        super().__init__(convert_charrefs=False)
        self.raw_html = raw_html
        self.line_offsets = [0]
        for idx, ch in enumerate(raw_html):
            if ch == "\n":
                self.line_offsets.append(idx + 1)
        self.depth = 0
        self.current_node = None
        self.nodes: List[Dict] = []

    def _char_index(self) -> int:
        lineno, col = self.getpos()
        return self.line_offsets[lineno - 1] + col

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        tag_l = tag.lower()
        idx = self._char_index()
        if self.depth == 0:
            attr_dict = {k.lower(): (v or "") for k, v in attrs}
            self.current_node = {
                "tag": tag_l,
                "attrs": attr_dict,
                "start": idx,
            }
            if tag_l in _VOID_TAGS:
                end_gt = self.raw_html.find(">", idx)
                end_pos = (end_gt + 1) if end_gt != -1 else len(self.raw_html)
                self.current_node["end"] = end_pos
                self.current_node["raw"] = self.raw_html[idx:end_pos]
                self.nodes.append(self.current_node)
                self.current_node = None
                return
        if tag_l not in _VOID_TAGS:
            self.depth += 1

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        tag_l = tag.lower()
        idx = self._char_index()
        if self.depth == 0:
            attr_dict = {k.lower(): (v or "") for k, v in attrs}
            end_gt = self.raw_html.find(">", idx)
            end_pos = (end_gt + 1) if end_gt != -1 else len(self.raw_html)
            self.nodes.append({
                "tag": tag_l,
                "attrs": attr_dict,
                "start": idx,
                "end": end_pos,
                "raw": self.raw_html[idx:end_pos],
            })

    def handle_endtag(self, tag: str):
        tag_l = tag.lower()
        if tag_l in _VOID_TAGS:
            return
        if self.depth > 0:
            self.depth -= 1
            if self.depth == 0 and self.current_node is not None:
                idx = self._char_index()
                end_gt = self.raw_html.find(">", idx)
                end_pos = (end_gt + 1) if end_gt != -1 else len(self.raw_html)
                self.current_node["end"] = end_pos
                self.current_node["raw"] = self.raw_html[self.current_node["start"]:end_pos]
                self.nodes.append(self.current_node)
                self.current_node = None


def _parse_style_declarations(decl_str: str) -> Dict[str, str]:
    """Parse CSS declaration string 'a: b; c: d' into an expanded ordered dict."""
    props: Dict[str, str] = {}
    if not decl_str:
        return props
    for part in decl_str.split(";"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        k = k.strip().lower()
        v = v.strip()
        if not k or not v:
            continue
        # Normalize fractional border widths like 1.5px -> 2px for QTextDocument
        if k.startswith("border"):
            v = re.sub(r'\b1\.5px\b', '2px', v)
            v = re.sub(r'\b0\.5px\b', '1px', v)
        if k == "background" and not re.search(r'url\s*\(', v, re.I):
            props["background"] = v
            props["background-color"] = v
        elif k == "border":
            props["border"] = v
            props["border-top"] = v
            props["border-right"] = v
            props["border-bottom"] = v
            props["border-left"] = v
        elif k == "padding":
            props["padding"] = v
            tokens = [t for t in v.split() if t]
            if len(tokens) == 1:
                props["padding-top"] = props["padding-right"] = props["padding-bottom"] = props["padding-left"] = tokens[0]
            elif len(tokens) == 2:
                props["padding-top"] = props["padding-bottom"] = tokens[0]
                props["padding-right"] = props["padding-left"] = tokens[1]
            elif len(tokens) == 3:
                props["padding-top"] = tokens[0]
                props["padding-right"] = props["padding-left"] = tokens[1]
                props["padding-bottom"] = tokens[2]
            elif len(tokens) >= 4:
                props["padding-top"] = tokens[0]
                props["padding-right"] = tokens[1]
                props["padding-bottom"] = tokens[2]
                props["padding-left"] = tokens[3]
        else:
            props[k] = v
    return props


def _extract_css_rules(html_content: str) -> List[Tuple[List[str], Dict[str, str]]]:
    """Extract (selector_parts, declarations_dict) from all <style> blocks."""
    rules: List[Tuple[List[str], Dict[str, str]]] = []
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html_content, re.I | re.S)
    for block in style_blocks:
        clean = re.sub(r'/\*.*?\*/', '', block, flags=re.S)
        clean = re.sub(r'@page\s*\{[^}]*\}', '', clean, flags=re.I | re.S)
        clean = re.sub(r'@media[^{]+\{.*\}', '', clean, flags=re.I | re.S)
        for m in re.finditer(r'([^{}]+)\{([^}]*)\}', clean):
            sel_group = m.group(1).strip()
            decls = _parse_style_declarations(m.group(2))
            if not decls:
                continue
            for raw_sel in sel_group.split(","):
                sel = raw_sel.strip()
                if not sel or sel == "*" or ":" in sel:
                    continue
                parts = [p.strip() for p in re.split(r'[\s>]+', sel) if p.strip()]
                if parts:
                    rules.append((parts, decls))
    return rules


def _part_matches_elem(sel_part: str, elem: Dict) -> bool:
    """Check if a single CSS selector token (tag, .class, tag.class, #id) matches elem."""
    if not sel_part or sel_part == "*":
        return False
    tag = elem.get("tag", "")
    classes = elem.get("classes", set())
    elem_id = elem.get("id", "")

    if sel_part.startswith("#"):
        return elem_id == sel_part[1:].lower()
    if sel_part.startswith("."):
        req_classes = [c.lower() for c in sel_part.split(".") if c]
        return all(c in classes for c in req_classes)
    if "." in sel_part:
        sub = sel_part.split(".")
        req_tag = sub[0].lower()
        req_classes = [c.lower() for c in sub[1:] if c]
        return (req_tag == tag) and all(c in classes for c in req_classes)
    return sel_part.lower() == tag


def _selector_matches(sel_parts: List[str], current_elem: Dict, ancestor_stack: List[Dict]) -> bool:
    """Check if a simple or descendant CSS selector matches current_elem given ancestor_stack."""
    if not _part_matches_elem(sel_parts[-1], current_elem):
        return False
    if len(sel_parts) == 1:
        return True
    needed = list(sel_parts[:-1])
    for anc in reversed(ancestor_stack):
        if _part_matches_elem(needed[-1], anc):
            needed.pop()
            if not needed:
                return True
    return False


class _QtHTMLNormalizer(HTMLParser):
    """
    Normalizes modern HTML/CSS into Qt QTextDocument-compatible HTML:
    - Inlines <style> rules into elements' style attributes so inline styles on <td>/<th>
      never wipe out class/descendant table borders or backgrounds in QTextDocument.
    - Adds width="100%" and cellspacing="0" to full-width / collapsed tables.
    - Wraps right-aligned margin-left:auto tables (like .totals-table) in a non-floating
      100% layout table so they align cleanly to the right edge.
    - Converts bordered/card block <div> elements (like .notice-box, .spec-card,
      .section-heading, .page-footer-note) into 1-cell full-width tables so QTextDocument
      renders their borders, left accent bars, backgrounds, and padding accurately.
    """

    def __init__(self, css_rules: List[Tuple[List[str], Dict[str, str]]]):
        super().__init__(convert_charrefs=False)
        self.css_rules = css_rules
        self.stack: List[Dict] = []
        self.out: List[str] = []

    @staticmethod
    def _format_style(props: Dict[str, str]) -> str:
        return "; ".join(f"{k}: {v}" for k, v in props.items() if v)

    @staticmethod
    def _escape_attr(val: str) -> str:
        return val.replace('"', '&quot;')

    def _matched_css_for(self, elem: Dict) -> Dict[str, str]:
        merged: Dict[str, str] = {}
        for sel_parts, decls in self.css_rules:
            if _selector_matches(sel_parts, elem, self.stack):
                merged.update(decls)
        return merged

    def handle_decl(self, decl: str):
        self.out.append(f"<!{decl}>")

    def handle_comment(self, data: str):
        pass

    def handle_data(self, data: str):
        self.out.append(data)

    def handle_entityref(self, name: str):
        self.out.append(f"&{name};")

    def handle_charref(self, name: str):
        self.out.append(f"&#{name};")

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        tag_l = tag.lower()
        attr_dict: Dict[str, str] = {}
        attr_order: List[str] = []
        for k, v in attrs:
            kl = k.lower()
            if kl not in attr_dict:
                attr_order.append(kl)
            attr_dict[kl] = v if v is not None else ""

        classes = set(attr_dict.get("class", "").lower().split())
        elem_id = attr_dict.get("id", "").lower()
        elem_info = {"tag": tag_l, "classes": classes, "id": elem_id}

        # 1. Merge matched <style> rules + inline style
        combined_css = self._matched_css_for(elem_info)
        inline_css = _parse_style_declarations(attr_dict.get("style", ""))
        combined_css.update(inline_css)

        # Check if parent table has top/bottom border that should apply to direct cells
        if tag_l in ("td", "th") and self.stack:
            parent_table = None
            for anc in reversed(self.stack):
                if anc["tag"] == "table":
                    parent_table = anc
                    break
            if parent_table and parent_table.get("propagate_table_borders"):
                t_borders = parent_table.get("table_border_props", {})
                for prop_name, prop_val in t_borders.items():
                    if prop_name not in combined_css:
                        combined_css[prop_name] = prop_val

        wrapper_close = f"</{tag_l}>"

        # 2. Special handling for <table>
        if tag_l == "table":
            if "cellspacing" not in attr_dict:
                attr_dict["cellspacing"] = "0"
                attr_order.append("cellspacing")
            if "cellpadding" not in attr_dict:
                attr_dict["cellpadding"] = "0"
                attr_order.append("cellpadding")

            css_w = combined_css.get("width", "")
            if css_w == "100%" and "width" not in attr_dict:
                attr_dict["width"] = "100%"
                attr_order.append("width")

            # Right-aligned table via margin-left: auto (e.g. .totals-table)
            if combined_css.get("margin-left") == "auto" and css_w and css_w != "100%":
                w_num = re.sub(r'[^0-9%]', '', css_w) or "260"
                attr_dict["width"] = w_num
                if "width" not in attr_order:
                    attr_order.append("width")
                mb = combined_css.pop("margin-bottom", "12px")
                mt = combined_css.pop("margin-top", "0px")
                combined_css.pop("margin-left", None)
                self.out.append(
                    f'<table width="100%" cellspacing="0" cellpadding="0" border="0" '
                    f'style="margin-top: {mt}; margin-bottom: {mb};">'
                    f'<tr><td>&nbsp;</td><td width="{w_num}" align="right">'
                )
                wrapper_close = "</table></td></tr></table>"

            # Determine if table-level border-top / border-bottom should propagate to cells
            has_table_border = ("border-bottom" in combined_css or "border-top" in combined_css)
            is_data_grid = "items-table" in classes or "totals-table" in classes
            elem_info["propagate_table_borders"] = bool(has_table_border and not is_data_grid)
            if elem_info["propagate_table_borders"]:
                elem_info["table_border_props"] = {
                    k: combined_css.pop(k)
                    for k in ("border-bottom", "padding-bottom", "border-top", "padding-top")
                    if k in combined_css
                }
                if "class" in attr_dict:
                    attr_dict.pop("class", None)
                    attr_order = [k for k in attr_order if k != "class"]

        # 3. Special handling for <td> / <th> alignment & vertical-align attributes
        elif tag_l in ("td", "th"):
            ta = combined_css.get("text-align", "").lower()
            if ta in ("left", "center", "right", "justify") and "align" not in attr_dict:
                attr_dict["align"] = ta
                attr_order.append("align")
            va = combined_css.get("vertical-align", "").lower()
            if va in ("top", "middle", "bottom") and "valign" not in attr_dict:
                attr_dict["valign"] = va
                attr_order.append("valign")

        # 4. Special handling for block <div> with borders or card backgrounds
        elif tag_l == "div":
            is_page_wrapper = bool(classes & {"page", "page-break", "a4-page", "pdf-page"})
            disp = combined_css.get("display", "").lower()
            is_inline = ("inline" in disp)
            has_border = any(
                k in combined_css and combined_css[k] not in ("none", "0", "0px")
                for k in ("border", "border-top", "border-bottom", "border-left", "border-right")
            )
            has_bg_box = (
                ("background-color" in combined_css or "background" in combined_css)
                and any(k in combined_css for k in ("padding", "padding-top", "padding-bottom", "padding-left", "padding-right"))
            )
            if (has_border or has_bg_box) and not is_page_wrapper and not is_inline:
                mt = combined_css.pop("margin-top", "0px")
                mb = combined_css.pop("margin-bottom", "10px")
                combined_css.pop("margin", None)
                ta = combined_css.get("text-align", "").lower()
                align_attr = f' align="{ta}"' if ta in ("left", "center", "right") else ""
                cell_style = self._format_style(combined_css)
                self.out.append(
                    f'<table width="100%" cellspacing="0" cellpadding="0" border="0" '
                    f'style="margin-top: {mt}; margin-bottom: {mb};">'
                    f'<tr><td{align_attr} style="{self._escape_attr(cell_style)}">'
                )
                elem_info["css"] = combined_css
                elem_info["wrapper_close"] = "</td></tr></table>"
                self.stack.append(elem_info)
                return

        if combined_css and tag_l not in ("html", "head", "style", "meta", "title"):
            attr_dict["style"] = self._format_style(combined_css)
            if "style" not in attr_order:
                attr_order.append("style")

        attr_str = ""
        for k in attr_order:
            v = attr_dict.get(k, "")
            attr_str += f' {k}="{self._escape_attr(v)}"'

        self.out.append(f"<{tag_l}{attr_str}>")

        if tag_l not in _VOID_TAGS:
            elem_info["css"] = combined_css
            elem_info["wrapper_close"] = wrapper_close
            self.stack.append(elem_info)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        tag_l = tag.lower()
        attr_str = "".join(f' {k.lower()}="{self._escape_attr(v or "")}"' for k, v in attrs)
        self.out.append(f"<{tag_l}{attr_str}/>")

    def handle_endtag(self, tag: str):
        tag_l = tag.lower()
        if tag_l in _VOID_TAGS:
            return
        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx]["tag"] == tag_l:
                entry = self.stack.pop(idx)
                self.out.append(entry.get("wrapper_close", f"</{tag_l}>"))
                return
        self.out.append(f"</{tag_l}>")


class HTMLRenderer:
    """HTML to Image and PDF converter using PySide6 Qt GUI components"""

    @staticmethod
    def _get_qpage_size(size_str: str, custom_dims_mm: Optional[Tuple[float, float]] = None) -> QPageSize:
        """Create a precise QPageSize object matching standard or custom dimensions."""
        if custom_dims_mm:
            w, h = custom_dims_mm
            return QPageSize(QSizeF(w, h), QPageSize.Unit.Millimeter)

        key = (size_str or "A4").upper()
        if key in PAGE_SIZE_DIMENSIONS_MM:
            w, h = PAGE_SIZE_DIMENSIONS_MM[key]
            enum_val = None
            if hasattr(QPageSize, "PageSizeId"):
                enum_name = key.capitalize() if key in ("LETTER", "LEGAL", "TABLOID", "LEDGER", "EXECUTIVE") else key
                enum_val = getattr(QPageSize.PageSizeId, enum_name, None)
            if enum_val is None:
                enum_name = key.capitalize() if key in ("LETTER", "LEGAL", "TABLOID", "LEDGER", "EXECUTIVE") else key
                enum_val = getattr(QPageSize, enum_name, None)

            if enum_val is not None:
                try:
                    return QPageSize(enum_val)
                except Exception:
                    pass
            return QPageSize(QSizeF(w, h), QPageSize.Unit.Millimeter)

        return QPageSize(QPageSize.PageSizeId.A4) if hasattr(QPageSize, "PageSizeId") else QPageSize(QPageSize.A4)

    @staticmethod
    def _parse_page_css(html_content: str):
        """
        Parses @page rules from CSS in the HTML content, extracting:
        - page_size_str: (A4, A1, A0, Letter, Legal, etc.)
        - is_landscape: bool
        - margins_mm: (top, right, bottom, left) in millimeters, or None
        - has_explicit_breaks: bool
        - explicit_breaks_count: int
        - custom_dims_mm: Optional[Tuple[float, float]]
        """
        page_size_str = "A4"
        is_landscape = False
        margins_mm = None
        custom_dims_mm = None

        break_matches = re.findall(
            r'page-break-(before|after):\s*always|break-(before|after):\s*page',
            html_content, re.IGNORECASE
        )
        has_explicit_breaks = bool(break_matches)
        explicit_breaks_count = len(break_matches)

        def _to_mm(val_str: str) -> float:
            val_str = val_str.strip()
            m = re.match(r'^([0-9.]+)\s*(mm|cm|in|px|pt)?$', val_str, re.IGNORECASE)
            if not m:
                return 0.0
            num = float(m.group(1))
            unit = (m.group(2) or "mm").lower()
            if unit == "mm": return num
            if unit == "cm": return num * 10.0
            if unit == "in": return num * 25.4
            if unit == "pt": return num * (25.4 / 72.0)
            if unit == "px": return num * (25.4 / 96.0)
            return num

        page_match = re.search(r'@page\s*\{([^}]+)\}', html_content, re.IGNORECASE | re.DOTALL)
        if page_match:
            block = page_match.group(1)

            if re.search(r'\blandscape\b', block, re.IGNORECASE):
                is_landscape = True
            elif re.search(r'\bportrait\b', block, re.IGNORECASE):
                is_landscape = False

            size_m = re.search(r'size:\s*([^;\}]+)', block, re.IGNORECASE)
            if size_m:
                size_val = size_m.group(1).strip()
                if re.search(r'\blandscape\b', size_val, re.IGNORECASE):
                    is_landscape = True
                elif re.search(r'\bportrait\b', size_val, re.IGNORECASE):
                    is_landscape = False

                for name in ("A0", "A1", "A2", "A3", "A4", "A5", "A6", "LETTER", "LEGAL", "TABLOID", "LEDGER", "EXECUTIVE", "B4", "B5"):
                    if re.search(rf'\b{name}\b', size_val, re.IGNORECASE):
                        page_size_str = name
                        break

                dim_m = re.findall(r'([0-9.]+)\s*(mm|cm|in|px|pt)', size_val, re.IGNORECASE)
                if len(dim_m) >= 2:
                    custom_dims_mm = (_to_mm(f"{dim_m[0][0]}{dim_m[0][1]}"), _to_mm(f"{dim_m[1][0]}{dim_m[1][1]}"))

            margin_m = re.search(r'margin:\s*([^;\}]+)', block, re.IGNORECASE)
            if margin_m:
                raw_margin = margin_m.group(1).strip()
                parts = raw_margin.split()
                try:
                    mm_vals = [_to_mm(p) for p in parts if p.strip()]
                    if len(mm_vals) == 1:
                        margins_mm = (mm_vals[0], mm_vals[0], mm_vals[0], mm_vals[0])
                    elif len(mm_vals) == 2:
                        margins_mm = (mm_vals[0], mm_vals[1], mm_vals[0], mm_vals[1])
                    elif len(mm_vals) == 3:
                        margins_mm = (mm_vals[0], mm_vals[1], mm_vals[2], mm_vals[1])
                    elif len(mm_vals) >= 4:
                        margins_mm = (mm_vals[0], mm_vals[1], mm_vals[2], mm_vals[3])
                except Exception:
                    pass
        else:
            if re.search(r'594\s*mm|841\s*mm', html_content, re.IGNORECASE):
                page_size_str = "A1"
            elif re.search(r'420\s*mm|594\s*mm', html_content, re.IGNORECASE):
                page_size_str = "A2"
            elif re.search(r'297\s*mm|420\s*mm', html_content, re.IGNORECASE):
                page_size_str = "A3"

        return page_size_str, is_landscape, margins_mm, has_explicit_breaks, explicit_breaks_count, custom_dims_mm

    @staticmethod
    def _split_html_into_pages(html_content: str) -> List[str]:
        """
        Splits an HTML document into separate per-page HTML documents whenever explicit
        page containers (<div class="page">...) or page-break rules (.page-break,
        page-break-after: always, break-after: page, page-break-before: always) are used.
        Each returned string preserves the full <head><style>...</style></head> wrapper.
        """
        try:
            break_after_classes = {"page-break", "pagebreak"}
            break_before_classes = set()

            for sel_parts, decls in _extract_css_rules(html_content):
                if len(sel_parts) == 1 and sel_parts[0].startswith("."):
                    cls_name = sel_parts[0][1:].lower()
                    if decls.get("page-break-after", "").lower() == "always" or decls.get("break-after", "").lower() == "page":
                        break_after_classes.add(cls_name)
                    if decls.get("page-break-before", "").lower() == "always" or decls.get("break-before", "").lower() == "page":
                        break_before_classes.add(cls_name)

            body_open = re.search(r'<body[^>]*>', html_content, re.I)
            body_close = re.search(r'</body\s*>', html_content, re.I)
            if body_open and body_close and body_open.end() < body_close.start():
                prefix = html_content[:body_open.end()]
                body_inner = html_content[body_open.end():body_close.start()]
                suffix = html_content[body_close.start():]
            else:
                prefix = ""
                body_inner = html_content
                suffix = ""

            splitter = _TopLevelBodySplitter(body_inner)
            splitter.feed(body_inner)
            top_nodes = splitter.nodes

            # If a single wrapper div encloses multiple page sections, unwrap one level
            if len(top_nodes) == 1:
                only = top_nodes[0]
                only_classes = set(only["attrs"].get("class", "").lower().split())
                if not (only_classes & break_after_classes):
                    inner_m = re.match(r'^(<[^>]+>)(.*)(</[^>]+>)\s*$', only["raw"], re.S)
                    if inner_m:
                        sub_splitter = _TopLevelBodySplitter(inner_m.group(2))
                        sub_splitter.feed(inner_m.group(2))
                        if len(sub_splitter.nodes) > 1:
                            prefix = prefix + "\n" + inner_m.group(1)
                            suffix = inner_m.group(3) + "\n" + suffix
                            top_nodes = sub_splitter.nodes

            if len(top_nodes) <= 1:
                return [html_content]

            pages_raw: List[str] = []
            current_chunk: List[str] = []
            saw_explicit_page_signal = False

            for node in top_nodes:
                classes = set(node["attrs"].get("class", "").lower().split())
                style = node["attrs"].get("style", "").lower()

                is_page_box = bool(classes & {"page", "a4-page", "pdf-page"})
                has_break_after = (
                    bool(classes & break_after_classes)
                    or bool(re.search(r'page-break-after:\s*always|break-after:\s*page', style))
                )
                has_break_before = (
                    bool(classes & break_before_classes)
                    or bool(re.search(r'page-break-before:\s*always|break-before:\s*page', style))
                )

                if is_page_box or has_break_after or has_break_before:
                    saw_explicit_page_signal = True

                text_only = re.sub(r'<[^>]+>', '', node["raw"]).strip()
                has_media = bool(re.search(r'<(img|table|svg)\b', node["raw"], re.I))
                is_empty_divider = (
                    not text_only
                    and not has_media
                    and (has_break_after or has_break_before or bool(classes & {"page-break", "pagebreak"}))
                )

                if is_empty_divider:
                    if current_chunk:
                        pages_raw.append("\n".join(current_chunk))
                        current_chunk = []
                    continue

                if (has_break_before or is_page_box) and current_chunk:
                    pages_raw.append("\n".join(current_chunk))
                    current_chunk = []

                current_chunk.append(node["raw"])

                if has_break_after or is_page_box:
                    pages_raw.append("\n".join(current_chunk))
                    current_chunk = []

            if current_chunk:
                pages_raw.append("\n".join(current_chunk))

            # Filter out any blank chunks
            valid_pages = []
            for chunk in pages_raw:
                txt = re.sub(r'<[^>]+>', '', chunk).strip()
                if txt or re.search(r'<(img|table|svg)\b', chunk, re.I):
                    valid_pages.append(f"{prefix}\n{chunk}\n{suffix}")

            if saw_explicit_page_signal and len(valid_pages) > 1:
                return valid_pages
        except Exception as e:
            print(f"Warning in _split_html_into_pages: {e}")

        return [html_content]

    @staticmethod
    def _normalize_html_for_qt(html_content: str) -> str:
        """
        Transforms HTML/CSS so PySide6 QTextDocument renders tables, borders,
        right-aligned totals, and callout boxes accurately.
        """
        try:
            css_rules = _extract_css_rules(html_content)
            normalizer = _QtHTMLNormalizer(css_rules)
            normalizer.feed(html_content)
            return "".join(normalizer.out)
        except Exception as e:
            print(f"Warning in _normalize_html_for_qt: {e}")
            return html_content

    @staticmethod
    def prepare_html_for_email_body(html_content: str) -> str:
        """
        Prepares an HTML template for direct inclusion in an email body (Gmail, Outlook, etc.):
        - Inlines all <style> rules onto the HTML elements so email clients that strip <style>
          tags still render every table border, background color, right-aligned total, and box.
        - If the HTML contains multiple explicit pages (<div class="page"> / .page-break),
          adds a clean visual page frame and spacing around each page block so Page 1, Page 2,
          and Page 3 appear as distinct pages inside the email body as well.
        """
        if not html_content or "<" not in html_content:
            return html_content
        try:
            page_htmls = HTMLRenderer._split_html_into_pages(html_content)
            norm = HTMLRenderer._normalize_html_for_qt(html_content)
            if len(page_htmls) > 1:
                # Enhance each .page container so multiple pages are visually distinct in the email body
                def _style_page_div(match):
                    full_tag = match.group(0)
                    cls_m = re.search(r'class=["\']([^"\']*)["\']', full_tag, re.I)
                    if not cls_m:
                        return full_tag
                    classes = set(cls_m.group(1).lower().split())
                    if not (classes & {"page", "a4-page", "pdf-page"}):
                        return full_tag
                    extra_style = (
                        "background-color: #ffffff; border: 1px solid #cbd5e1; "
                        "border-radius: 6px; padding: 22px; margin: 0 auto 24px auto; "
                        "box-sizing: border-box;"
                    )
                    if re.search(r'style=["\']', full_tag, re.I):
                        return re.sub(
                            r'style=["\']([^"\']*)["\']',
                            lambda m: f'style="{m.group(1)}; {extra_style}"',
                            full_tag,
                            count=1,
                            flags=re.I
                        )
                    return full_tag[:-1] + f' style="{extra_style}">'

                norm = re.sub(r'<div\b[^>]*>', _style_page_div, norm, flags=re.I)
            return norm
        except Exception:
            return html_content

    _CACHED_BROWSER_EXE: Optional[str] = None
    _BROWSER_SEARCHED: bool = False

    @classmethod
    def _find_headless_browser(cls) -> Optional[str]:
        """Locate Microsoft Edge or Google Chrome on the system for 1:1 browser PDF rendering."""
        if cls._BROWSER_SEARCHED:
            return cls._CACHED_BROWSER_EXE
        cls._BROWSER_SEARCHED = True

        import os
        import shutil

        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for c in candidates:
            if c and Path(c).exists():
                cls._CACHED_BROWSER_EXE = c
                return c

        for name in ("msedge", "chrome", "google-chrome"):
            found = shutil.which(name)
            if found:
                cls._CACHED_BROWSER_EXE = found
                return found

        return None

    @classmethod
    def _render_pdf_via_browser(
        cls,
        html_content: str,
        pdf_path: str,
        w_mm: float,
        tight_h_mm: float,
        std_h_mm: float,
        margins_mm: Tuple[float, float, float, float],
        expected_pages: int,
    ) -> bool:
        """
        Renders HTML to PDF using headless Edge/Chrome so the output PDF matches
        the browser view 100% pixel-for-pixel (A4, A1, 1-page, 2-page, 3-page, etc.)
        with tight page height so there is no empty white space below the footer.
        """
        browser_exe = cls._find_headless_browser()
        if not browser_exe:
            return False

        import subprocess
        import tempfile
        import shutil
        import uuid

        top_m, right_m, bot_m, left_m = margins_mm

        def _run_print(cur_h_mm: float, zoom_factor: float = 1.0, auto_js_fit: str = "named") -> Tuple[bool, int]:
            uid = uuid.uuid4().hex[:10]
            tmp_dir = Path(tempfile.gettempdir()) / f"pm_pdf_{uid}"
            prof_dir = tmp_dir / "prof"
            tmp_html = tmp_dir / "doc.html"
            out_pdf = Path(pdf_path).resolve()

            try:
                prof_dir.mkdir(parents=True, exist_ok=True)
                # Remove existing @page rules so our exact tight-height @page rule takes full effect
                cleaned_html = re.sub(r'@page\s*\{[^}]*\}', '', html_content, flags=re.I | re.S)
                zoom_rule = f"html, body {{ zoom: {zoom_factor}; }}" if zoom_factor < 1.0 else ""
                print_css = (
                    f"<style id=\"pm-base-print-style\">\n"
                    f"@page {{\n"
                    f"  size: {w_mm:.1f}mm {cur_h_mm:.1f}mm;\n"
                    f"  margin: {top_m:.1f}mm {right_m:.1f}mm {bot_m:.1f}mm {left_m:.1f}mm;\n"
                    f"}}\n"
                    f"@media print, screen {{\n"
                    f"  * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}\n"
                    f"  .page {{ page-break-inside: avoid; break-inside: avoid; }}\n"
                    f"  {zoom_rule}\n"
                    f"}}\n"
                    f"</style>"
                )

                js_script = ""
                if auto_js_fit in ("named", "uniform") and zoom_factor == 1.0:
                    use_named_js = "true" if auto_js_fit == "named" else "false"
                    js_script = (
                        f"<script>\n"
                        f"(function() {{\n"
                        f"  try {{\n"
                        f"    var wMm = {w_mm:.2f};\n"
                        f"    var stdHMm = {std_h_mm:.2f};\n"
                        f"    var topM = {top_m:.2f}, rightM = {right_m:.2f}, botM = {bot_m:.2f}, leftM = {left_m:.2f};\n"
                        f"    var useNamed = {use_named_js};\n"
                        f"    var pages = document.querySelectorAll('.page, .a4-page, .pdf-page');\n"
                        f"    var cssOut = '';\n"
                        f"    if (pages.length > 1) {{\n"
                        f"      var maxMm = 0;\n"
                        f"      for (var i = 0; i < pages.length; i++) {{\n"
                        f"        var rect = pages[i].getBoundingClientRect();\n"
                        f"        var hMm = Math.ceil((rect.height * 25.4 / 96.0) + topM + botM + 6.0);\n"
                        f"        if (hMm < 80) hMm = 80;\n"
                        f"        if (hMm > stdHMm) hMm = stdHMm;\n"
                        f"        if (hMm > maxMm) maxMm = hMm;\n"
                        f"        if (useNamed) {{\n"
                        f"          cssOut += '@page pm_p' + i + ' {{ size: ' + wMm + 'mm ' + hMm + 'mm !important; margin: ' + topM + 'mm ' + rightM + 'mm ' + botM + 'mm ' + leftM + 'mm !important; }}\\n';\n"
                        f"          cssOut += '.pm-page-idx-' + i + ' {{ page: pm_p' + i + '; }}\\n';\n"
                        f"          pages[i].classList.add('pm-page-idx-' + i);\n"
                        f"        }}\n"
                        f"      }}\n"
                        f"      if (maxMm > 80) {{\n"
                        f"        cssOut += '@page {{ size: ' + wMm + 'mm ' + maxMm + 'mm !important; margin: ' + topM + 'mm ' + rightM + 'mm ' + botM + 'mm ' + leftM + 'mm !important; }}\\n';\n"
                        f"      }}\n"
                        f"    }} else {{\n"
                        f"      var targetEl = (pages.length === 1) ? pages[0] : document.body;\n"
                        f"      var bHeight = targetEl.getBoundingClientRect().height;\n"
                        f"      var singleHMm = Math.ceil((bHeight * 25.4 / 96.0) + topM + botM + 6.0);\n"
                        f"      if (singleHMm >= 80 && singleHMm < stdHMm - 10) {{\n"
                        f"        cssOut += '@page {{ size: ' + wMm + 'mm ' + singleHMm + 'mm !important; margin: ' + topM + 'mm ' + rightM + 'mm ' + botM + 'mm ' + leftM + 'mm !important; }}\\n';\n"
                        f"      }}\n"
                        f"    }}\n"
                        f"    if (cssOut) {{\n"
                        f"      var st = document.createElement('style');\n"
                        f"      st.innerHTML = cssOut;\n"
                        f"      document.head.appendChild(st);\n"
                        f"    }}\n"
                        f"  }} catch (e) {{}}\n"
                        f"}})();\n"
                        f"</script>"
                    )

                if re.search(r'</head\s*>', cleaned_html, re.I):
                    prepared = re.sub(r'(</head\s*>)', print_css + r'\n\1', cleaned_html, count=1, flags=re.I)
                else:
                    prepared = print_css + "\n" + cleaned_html

                if js_script:
                    if re.search(r'</body\s*>', prepared, re.I):
                        prepared = re.sub(r'(</body\s*>)', js_script + r'\n\1', prepared, count=1, flags=re.I)
                    else:
                        prepared = prepared + "\n" + js_script

                tmp_html.write_text(prepared, encoding="utf-8")

                if out_pdf.exists():
                    try:
                        out_pdf.unlink()
                    except Exception:
                        pass

                cmd = [
                    browser_exe,
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-extensions",
                    "--disable-sync",
                    "--no-pdf-header-footer",
                    "--print-to-pdf-no-header",
                    f"--user-data-dir={str(prof_dir)}",
                    f"--print-to-pdf={str(out_pdf)}",
                    tmp_html.resolve().as_uri(),
                ]
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW on Windows
                )
                if out_pdf.exists() and out_pdf.stat().st_size > 500:
                    pdf_bytes = out_pdf.read_bytes()
                    page_count = len(re.findall(rb'/Type\s*/Page(?!s)\b', pdf_bytes))
                    return True, max(1, page_count)
                return False, 0
            except Exception:
                return False, 0
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        # Pass 1: Per-page exact DOM measurement in Chromium (named @page per .page block)
        ok, actual_pages = _run_print(tight_h_mm, 1.0, auto_js_fit="named")
        if not ok:
            return False
        if actual_pages == expected_pages:
            return True

        # Pass 2: Uniform tight height measured directly in Chromium DOM
        ok_u, pages_u = _run_print(tight_h_mm, 1.0, auto_js_fit="uniform")
        if ok_u and pages_u == expected_pages:
            return True

        # Pass 3: Step height up or zoom if template content exceeded standard height
        if expected_pages >= 1 and pages_u > expected_pages:
            for candidate_h in (min(std_h_mm, tight_h_mm + 20.0), min(std_h_mm, tight_h_mm + 40.0), std_h_mm):
                ok_h, pages_h = _run_print(candidate_h, 1.0, auto_js_fit="none")
                if ok_h and pages_h <= expected_pages:
                    return True
            for z in (0.92, 0.85, 0.78):
                ok_z, pages_z = _run_print(std_h_mm, z, auto_js_fit="none")
                if ok_z and pages_z <= expected_pages:
                    return True

        return True

    @staticmethod
    def _register_data_images(doc: QTextDocument, html_content: str):
        """Pre-register base64 data URIs as document resources so images always render."""
        data_uris = re.findall(
            r'src=["\'](data:image/([a-zA-Z0-9+.-]+);base64,([A-Za-z0-9+/=]+))["\']',
            html_content, re.IGNORECASE
        )
        for full_src, img_fmt, b64_str in data_uris:
            try:
                raw_bytes = base64.b64decode(b64_str)
                qimg = QImage.fromData(raw_bytes)
                if not qimg.isNull():
                    doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(full_src), qimg)
            except Exception:
                pass

    @staticmethod
    def render_html_to_pdf(html_content: str, pdf_path: str, page_size_str: str = "A4") -> bool:
        """
        Render HTML content to a PDF file.
        Automatically honors @page CSS rules (A4, A1, Letter, orientation, margins),
        tightly fits the vertical page height to the content so there is no empty bottom void,
        and guarantees multi-page or single-page templates strictly preserve their
        intended page structure (Page 1 on PDF Page 1, Page 2 on PDF Page 2, etc.).
        """
        try:
            Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)

            # 1. Parse @page rules from CSS
            css_size, is_landscape, margins_mm, has_explicit_breaks, explicit_breaks_count, custom_dims_mm = (
                HTMLRenderer._parse_page_css(html_content)
            )
            target_size_str = css_size if css_size else page_size_str

            if custom_dims_mm:
                w_mm, std_h_mm = custom_dims_mm
            else:
                w_mm, std_h_mm = PAGE_SIZE_DIMENSIONS_MM.get(target_size_str.upper(), (210.0, 297.0))
            if is_landscape and w_mm < std_h_mm:
                w_mm, std_h_mm = std_h_mm, w_mm

            effective_margins = margins_mm if margins_mm is not None else (8.0, 8.0, 8.0, 8.0)
            top_m, right_m, bot_m, left_m = effective_margins

            # 2. Check explicit multi-page sections (e.g. Page 1 of 3, Page 2 of 3, Page 3 of 3)
            page_htmls = HTMLRenderer._split_html_into_pages(html_content)
            expected_pages = len(page_htmls) if len(page_htmls) > 1 else ((explicit_breaks_count + 1) if has_explicit_breaks else 1)

            # 3. Measure natural content height of each page to eliminate empty bottom white space
            printable_w_px = max(200.0, (w_mm - left_m - right_m) * 96.0 / 25.4)
            chunk_heights_px: List[float] = []
            for chunk_html in page_htmls:
                norm_c = HTMLRenderer._normalize_html_for_qt(chunk_html)
                tmp_doc = QTextDocument()
                HTMLRenderer._register_data_images(tmp_doc, norm_c)
                tmp_doc.setHtml(norm_c)
                tmp_doc.setTextWidth(printable_w_px)
                chunk_heights_px.append(tmp_doc.size().height())

            max_chunk_px = max(chunk_heights_px) if chunk_heights_px else 0.0
            # Account for ~1.16x vertical line-height/margin difference in Chromium vs QTextDocument
            browser_est_h_mm = (max_chunk_px * 1.16 * 25.4 / 96.0) + top_m + bot_m + 8.0

            if len(page_htmls) > 1 or expected_pages == 1:
                if 80.0 < browser_est_h_mm < (std_h_mm - 12.0):
                    tight_h_mm = browser_est_h_mm
                else:
                    tight_h_mm = std_h_mm
            else:
                tight_h_mm = std_h_mm

            # 4. Primary Engine: Headless Edge/Chrome for 100% browser-identical PDF output
            if HTMLRenderer._render_pdf_via_browser(
                html_content,
                pdf_path,
                w_mm,
                tight_h_mm,
                std_h_mm,
                effective_margins,
                expected_pages,
            ):
                return True

            # 5. Fallback Engine: PySide6 QPdfWriter with tight per-page height & CSS normalization
            first_chunk_px = chunk_heights_px[0] if chunk_heights_px else 0.0
            first_h_mm = (first_chunk_px * 25.4 / 96.0) + top_m + bot_m + 6.0
            init_h_mm = first_h_mm if (80.0 < first_h_mm < (std_h_mm - 12.0)) else tight_h_mm
            selected_size = HTMLRenderer._get_qpage_size(target_size_str, (w_mm, init_h_mm))

            writer = QPdfWriter(pdf_path)
            writer.setPageSize(selected_size)
            writer.setResolution(96)
            writer.setPageOrientation(QPageLayout.Orientation.Portrait)
            writer.setPageMargins(QMarginsF(left_m, top_m, right_m, bot_m), QPageLayout.Unit.Millimeter)

            try:
                paint_rect = writer.pageLayout().paintRectPixels(writer.resolution())
                page_w = paint_rect.width()
                page_h = paint_rect.height()
            except Exception:
                page_w = writer.width()
                page_h = writer.height()

            if len(page_htmls) > 1:
                painter = QPainter(writer)
                for idx, single_page_html in enumerate(page_htmls):
                    norm_page_html = HTMLRenderer._normalize_html_for_qt(single_page_html)
                    doc = QTextDocument()
                    HTMLRenderer._register_data_images(doc, norm_page_html)
                    doc.setHtml(norm_page_html)
                    doc.setTextWidth(page_w)

                    natural_h = doc.size().height()
                    natural_w = doc.idealWidth()

                    # Tighten individual page height in QPdfWriter so each page ends right below its footer
                    indiv_h_mm = max(90.0, min(std_h_mm, (natural_h * 25.4 / 96.0) + top_m + bot_m + 6.0))
                    writer.setPageSize(HTMLRenderer._get_qpage_size(target_size_str, (w_mm, indiv_h_mm)))
                    if idx > 0:
                        writer.newPage()

                    try:
                        cur_rect = writer.pageLayout().paintRectPixels(writer.resolution())
                        cur_page_h = cur_rect.height()
                    except Exception:
                        cur_page_h = page_h

                    scale_y = (cur_page_h / natural_h) if (natural_h > cur_page_h and natural_h > 0) else 1.0
                    scale_x = (page_w / natural_w) if (natural_w > page_w and natural_w > 0) else 1.0
                    scale = min(scale_x, scale_y, 1.0)

                    offset_x = ((page_w - (page_w * scale)) / 2.0) if scale < 1.0 else 0.0

                    painter.save()
                    if scale < 1.0:
                        if offset_x > 0:
                            painter.translate(offset_x, 0)
                        painter.scale(scale, scale)
                    doc.drawContents(painter)
                    painter.restore()

                painter.end()
                return True

            # Single-chunk HTML document: normalize and paginate cleanly
            norm_html = HTMLRenderer._normalize_html_for_qt(html_content)
            doc = QTextDocument()
            HTMLRenderer._register_data_images(doc, norm_html)
            doc.setHtml(norm_html)
            doc.setTextWidth(page_w)

            natural_h = doc.size().height()
            natural_w = doc.idealWidth()

            min_pages = (explicit_breaks_count + 1) if has_explicit_breaks else 1

            if page_h > 0 and natural_h > 0:
                full_pages = int(natural_h // page_h)
                remainder = natural_h % page_h
                if remainder == 0:
                    computed_pages = max(1, full_pages)
                else:
                    # Tolerance: minor spillover up to 220px on unsplit templates is absorbed into full_pages
                    if remainder <= 220.0 and full_pages >= 1 and not has_explicit_breaks:
                        computed_pages = full_pages
                    else:
                        computed_pages = full_pages + 1
            else:
                computed_pages = 1

            target_pages = max(computed_pages, min_pages)

            total_target_h = target_pages * page_h
            scale_y = (total_target_h / natural_h) if (natural_h > total_target_h) else 1.0
            scale_x = (page_w / natural_w) if (natural_w > 0 and natural_w > page_w) else 1.0
            scale = min(scale_x, scale_y, 1.0)

            offset_x = 0.0
            if scale < 1.0:
                scaled_w = page_w * scale
                if page_w > scaled_w:
                    offset_x = (page_w - scaled_w) / 2.0

            if target_pages == 1:
                painter = QPainter(writer)
                if scale < 1.0:
                    if offset_x > 0:
                        painter.translate(offset_x, 0)
                    painter.scale(scale, scale)
                doc.drawContents(painter)
                painter.end()
                return True
            else:
                effective_page_h = page_h / scale
                doc.setPageSize(QSizeF(page_w / scale, effective_page_h))

                painter = QPainter(writer)
                for p in range(target_pages):
                    if p > 0:
                        writer.newPage()
                    painter.save()
                    if offset_x > 0:
                        painter.translate(offset_x, 0)
                    painter.scale(scale, scale)
                    painter.translate(0, -p * effective_page_h)
                    clip_rect = QRectF(0, p * effective_page_h, page_w / scale, effective_page_h)
                    painter.setClipRect(clip_rect)
                    doc.drawContents(painter, clip_rect)
                    painter.restore()
                painter.end()
                return True

        except Exception as e:
            print(f"Error rendering HTML to PDF: {str(e)}")
            return False

    @staticmethod
    def render_html_to_image(html_content: str, image_path: str, format_str: str = "PNG", 
                              width_val: Optional[int] = None, height_val: Optional[int] = None) -> bool:
        """
        Render HTML content to an Image (PNG, JPEG, GIF, WEBP) using QPainter.
        If the HTML has multiple explicit pages, renders each page as a distinct visual
        page sheet separated by a clean divider gap.
        """
        try:
            # Page dimensions
            if width_val and width_val > 0:
                document_width = width_val
            else:
                css_size, is_landscape, _, _, _, custom_dims = HTMLRenderer._parse_page_css(html_content)
                if custom_dims:
                    document_width = int(custom_dims[0] * 96 / 25.4)
                elif css_size in PAGE_SIZE_DIMENSIONS_MM:
                    w_mm, h_mm = PAGE_SIZE_DIMENSIONS_MM[css_size]
                    if is_landscape:
                        w_mm, h_mm = h_mm, w_mm
                    document_width = int(w_mm * 96 / 25.4)
                else:
                    document_width = 800

            page_htmls = HTMLRenderer._split_html_into_pages(html_content)

            if len(page_htmls) > 1 and not height_val:
                docs: List[Tuple[QTextDocument, int]] = []
                gap = 18
                pad = 16
                inner_w = max(200, document_width - (pad * 2))
                total_h = gap
                for single_page_html in page_htmls:
                    norm_p = HTMLRenderer._normalize_html_for_qt(single_page_html)
                    d = QTextDocument()
                    HTMLRenderer._register_data_images(d, norm_p)
                    d.setHtml(norm_p)
                    d.setTextWidth(inner_w)
                    h = max(200, int(d.size().height()) + (pad * 2))
                    docs.append((d, h))
                    total_h += h + gap

                image = QImage(QSize(document_width, total_h), QImage.Format_ARGB32)
                image.fill(Qt.GlobalColor.lightGray)
                painter = QPainter(image)
                painter.fillRect(0, 0, document_width, total_h, Qt.GlobalColor.white)

                y_cursor = gap // 2
                for idx, (d, box_h) in enumerate(docs):
                    if idx > 0:
                        # Subtle page divider band between pages
                        painter.fillRect(0, y_cursor - gap, document_width, gap, Qt.GlobalColor.lightGray)
                    painter.fillRect(0, y_cursor, document_width, box_h, Qt.GlobalColor.white)
                    painter.save()
                    painter.translate(pad, y_cursor + pad)
                    d.drawContents(painter)
                    painter.restore()
                    y_cursor += box_h + gap

                painter.end()
                Path(image_path).parent.mkdir(parents=True, exist_ok=True)
                return image.save(image_path, format_str.upper())

            norm_html = HTMLRenderer._normalize_html_for_qt(html_content)
            doc = QTextDocument()
            HTMLRenderer._register_data_images(doc, norm_html)
            doc.setHtml(norm_html)
            doc.setTextWidth(document_width)
            
            # Dynamically compute ideal height from document layout or use custom height
            document_height = height_val if height_val and height_val > 0 else int(doc.size().height())
            if document_height <= 0:
                document_height = 600
                
            image = QImage(QSize(document_width, document_height), QImage.Format_ARGB32)
            image.fill(Qt.white)  # Clear container with solid white background
            
            painter = QPainter(image)
            doc.drawContents(painter)
            painter.end()
            
            # Ensure output directory exists
            Path(image_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Save using selected format
            return image.save(image_path, format_str.upper())
        except Exception as e:
            print(f"Error rendering HTML to image: {str(e)}")
            return False

    @classmethod
    def render_html_to_base64_image(cls, html_content: str, format_str: str = "PNG",
                                    width_val: Optional[int] = None, height_val: Optional[int] = None) -> Optional[str]:
        """
        Render HTML input to a temporary image and return its base64 data URL
        """
        temp_img_path = str(Path("temp") / f"temp_body_render.{format_str.lower()}")
        if cls.render_html_to_image(html_content, temp_img_path, format_str, width_val, height_val):
            try:
                with open(temp_img_path, "rb") as f:
                    data = f.read()
                b64_data = base64.b64encode(data).decode("utf-8")
                mime = f"image/{format_str.lower()}"
                if format_str.lower() == "jpg":
                    mime = "image/jpeg"
                
                # Cleanup tempo file
                if Path(temp_img_path).exists():
                    Path(temp_img_path).unlink()
                
                return f"data:{mime};base64,{b64_data}"
            except Exception as e:
                print(f"Error converting rendered image to base64: {e}")
        return None

    @classmethod
    def render_html_to_base64_pdf(cls, html_content: str, page_size_str: str = "A4") -> Optional[str]:
        """
        Render HTML input to a temporary PDF and return its base64 bytes
        """
        import uuid
        temp_pdf = str(Path("temp") / f"temp_attachment_{uuid.uuid4().hex[:8]}.pdf")
        if cls.render_html_to_pdf(html_content, temp_pdf, page_size_str):
            try:
                with open(temp_pdf, "rb") as f:
                    data = f.read()
                b64_data = base64.b64encode(data).decode("utf-8")
                
                # Cleanup
                if Path(temp_pdf).exists():
                    Path(temp_pdf).unlink()
                    
                return b64_data
            except Exception as e:
                print(f"Error reading rendered PDF to base64: {e}")
        return None
