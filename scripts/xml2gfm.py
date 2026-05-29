#!/usr/bin/env python3
import re
import sys
import textwrap
import urllib.request
import xml.etree.ElementTree as ET


XI = "{http://www.w3.org/2001/XInclude}"


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def md_escape(text):
    return text.replace("\\", "\\\\")


def inline(elem):
    parts = [elem.text or ""]
    for child in elem:
        name = local_name(child.tag)
        body = inline(child)
        if name == "tt":
            parts.append(f"`{body}`")
        elif name == "bcp14":
            parts.append(f"**{body}**")
        elif name == "xref":
            target = child.attrib.get("target", body)
            parts.append(f"[{target}]")
        elif name == "eref":
            target = child.attrib.get("target", body)
            label = body or target
            parts.append(f"[{label}]({target})")
        else:
            parts.append(body)
        parts.append(child.tail or "")
    return clean("".join(parts))


def wrap_paragraph(text):
    return "\n".join(
        textwrap.wrap(
            text,
            width=88,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )


def wrap_with_indent(text, first_prefix="", later_prefix=""):
    return "\n".join(
        textwrap.wrap(
            text,
            width=88,
            initial_indent=first_prefix,
            subsequent_indent=later_prefix,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )


def code_info(elem):
    value = elem.attrib.get("type", "text")
    if value in ("abnf", "pseudocode"):
        return value
    return "text"


def render_blocks(parent, level, counters):
    blocks = []
    for elem in parent:
        name = local_name(elem.tag)
        if name == "name":
            continue
        if name == "section":
            blocks.extend(render_section(elem, level, counters))
        elif name == "t":
            text = inline(elem)
            if text:
                blocks.append(wrap_paragraph(text))
        elif name == "ul":
            lines = []
            for li in elem.findall("li"):
                lines.append(f"- {inline(li)}")
            blocks.append("\n".join(lines))
        elif name == "ol":
            lines = []
            for li in elem.findall("li"):
                lines.append(f"1. {inline(li)}")
            blocks.append("\n".join(lines))
        elif name == "dl":
            lines = []
            children = list(elem)
            for idx in range(0, len(children), 2):
                if idx + 1 >= len(children):
                    break
                term = inline(children[idx])
                desc = inline(children[idx + 1])
                lines.append(f"- **{term}**: {desc}")
            blocks.append("\n".join(lines))
        elif name in ("sourcecode", "artwork"):
            text = (elem.text or "").strip("\n")
            blocks.append(f"```{code_info(elem)}\n{text}\n```")
    return blocks


def render_section(section, level, counters):
    if section.attrib.get("numbered", "true") != "false":
        if len(counters) < level:
            counters.extend([0] * (level - len(counters)))
        counters[level - 1] += 1
        del counters[level:]
        number = ".".join(str(value) for value in counters) + ". "
    else:
        number = ""

    title_elem = section.find("name")
    title = inline(title_elem) if title_elem is not None else "Section"
    heading = "#" * min(level + 1, 6)
    blocks = [f"{heading} {number}{title}"]
    blocks.extend(render_blocks(section, level + 1, counters))
    return blocks


def author_name(author):
    fullname = author.attrib.get("fullname")
    if fullname:
        return fullname
    initials = author.attrib.get("initials", "")
    surname = author.attrib.get("surname", "")
    return clean(f"{initials} {surname}")


def join_names(names):
    if len(names) <= 1:
        return names[0] if names else ""
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def series_value(reference, name):
    for series in reference.findall("seriesInfo"):
        if series.attrib.get("name") == name:
            return series.attrib.get("value", "")
    return ""


def render_reference(reference):
    anchor = reference.attrib.get("anchor", "")
    target = reference.attrib.get("target", "")
    front = reference.find("front")
    title = inline(front.find("title")) if front is not None and front.find("title") is not None else ""
    authors = []
    if front is not None:
        authors = [author_name(author) for author in front.findall("author")]
    date = front.find("date") if front is not None else None
    date_text = ""
    if date is not None:
        month = date.attrib.get("month", "")
        year = date.attrib.get("year", "")
        date_text = clean(f"{month} {year}")

    rfc = series_value(reference, "RFC")
    doi = series_value(reference, "DOI")
    label = anchor or (f"RFC{rfc}" if rfc else "Reference")

    pieces = []
    names = join_names([name for name in authors if name])
    if names:
        pieces.append(f"{names},")
    if title:
        pieces.append(f"\"{title}\",")
    if rfc:
        pieces.append(f"RFC {rfc},")
    if doi:
        pieces.append(f"DOI {doi},")
    if date_text:
        pieces.append(f"{date_text},")
    if target:
        pieces.append(f"<{target}>.")

    text = " ".join(pieces).rstrip(",")
    return wrap_with_indent(f"**[{label}]** {text}", "- ", "  ")


def reference_from_include(elem):
    href = elem.attrib.get("href", "")
    if not href:
        return None
    try:
        with urllib.request.urlopen(href, timeout=20) as response:
            reference = ET.fromstring(response.read())
        return render_reference(reference)
    except Exception:
        match = re.search(r"reference\.RFC\.(\d+)\.xml$", href)
        if not match:
            return None
        number = match.group(1)
        return f"- **[RFC{number}]** <https://www.rfc-editor.org/info/rfc{number}>."


def render_references(root):
    refs = []
    for reference in root.findall(".//reference"):
        ref = render_reference(reference)
        if ref:
            refs.append(ref)
    for include in root.findall(f".//{XI}include"):
        ref = reference_from_include(include)
        if ref:
            refs.append(ref)
    if not refs:
        return []
    return ["## Normative References", "\n".join(refs)]


def main():
    if len(sys.argv) not in (3, 4):
        print(f"usage: {sys.argv[0]} input.xml output.md [preamble.md]", file=sys.stderr)
        return 2

    xml_path, md_path = sys.argv[1:3]
    preamble_path = sys.argv[3] if len(sys.argv) == 4 else None
    root = ET.parse(xml_path).getroot()
    front = root.find("front")
    title = inline(front.find("title")) if front is not None else root.attrib.get("docName")
    doc_name = root.attrib.get("docName", "")

    blocks = [f"# {title}"]
    if doc_name:
        blocks.append(f"*Internet-Draft: `{doc_name}`*")

    abstract = front.find("abstract") if front is not None else None
    if abstract is not None:
        blocks.append("## Abstract")
        blocks.extend(render_blocks(abstract, 2, []))

    middle = root.find("middle")
    if middle is not None:
        blocks.extend(render_blocks(middle, 1, []))

    blocks.extend(render_references(root))

    output = "\n\n".join(block for block in blocks if block).rstrip() + "\n"
    if preamble_path:
        with open(preamble_path, encoding="utf-8") as handle:
            preamble = handle.read().rstrip()
        output = f"{preamble}\n\n{output}"
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
