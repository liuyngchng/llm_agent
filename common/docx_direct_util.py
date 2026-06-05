#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct DOCX text replacement via lxml + zipfile — preserves ALL document content.

python-docx's Document() → save() roundtrip silently drops ~20% of complex OOXML
features (custom parts, VML drawings, unsupported formatting). This module edits
word/document.xml directly inside the ZIP archive, so only the modified runs change.
"""

import datetime
import zipfile
import io
import os
import copy
from lxml import etree

# ── OOXML constants ──────────────────────────────────────────────────
NS_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

def _w(tag: str) -> str:
    return f'{{{NS_W}}}{tag}'

def _r(tag: str) -> str:
    return f'{{{NS_R}}}{tag}'

W_R = _w('r')
W_T = _w('t')
W_P = _w('p')
W_INS = _w('ins')
W_DEL = _w('del')
W_RPR = _w('rPr')
W_DEL_TEXT = _w('delText')
W_BODY = _w('body')
W_TBL = _w('tbl')
W_TR = _w('tr')
W_TC = _w('tc')

# ── helpers ──────────────────────────────────────────────────────────

def _next_rev_id(body_elem) -> int:
    ids = set()
    for elem in body_elem.iter():
        for attr in (f'{{{NS_W}}}id',):
            v = elem.get(attr)
            if v is not None:
                try:
                    ids.add(int(v))
                except ValueError:
                    pass
    return max(ids) + 1 if ids else 1


def _make_rev_elem(tag: str, author: str, rev_id: int, date_str: str):
    elem = etree.Element(tag)
    elem.set(_w('id'), str(rev_id))
    elem.set(_w('author'), author)
    elem.set(_w('date'), date_str)
    return elem


def _make_run(text: str, preserve_space: bool = True) -> etree.Element:
    r = etree.Element(W_R)
    t = etree.SubElement(r, W_T)
    t.text = text
    if preserve_space:
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    return r


def _clone_run_styling(original_run: etree.Element, new_text: str) -> etree.Element:
    """Clone a run's formatting properties but with new text content."""
    r = copy.deepcopy(original_run)
    t = r.find(W_T)
    if t is not None:
        t.text = new_text
    return r


def _collect_paragraph_runs(para_elem) -> list:
    """Collect (run_elem, text_elem, text, start_pos, end_pos) from a paragraph.

    Skips runs that are already inside tracked changes (w:ins, w:del).
    """
    runs = []
    pos = 0
    for child in para_elem:
        if child.tag == W_R:
            t = child.find(W_T)
            text = t.text if t is not None and t.text else ''
            runs.append((child, t, text, pos, pos + len(text)))
            pos += len(text)
    return runs


# ── main replacement logic ───────────────────────────────────────────

def _replace_in_paragraph(para_elem, old_text: str, new_text: str,
                          author: str, rev_id_counter, date_str: str) -> int:
    """Replace all occurrences of old_text with new_text in one paragraph.

    Handles text spanning multiple runs. Returns count of replacements.
    """
    runs_data = _collect_paragraph_runs(para_elem)
    if not runs_data:
        return 0

    full_text = ''.join(rd[2] for rd in runs_data)

    # Build index: for each char position, which run and offset within that run
    char_to_run = []
    for rd_idx, (run, t, text, start, end) in enumerate(runs_data):
        char_to_run.extend([(rd_idx, i) for i in range(len(text))])

    if old_text not in full_text:
        return 0

    count = 0
    search_start = 0
    safe_limit = 500

    while search_start < len(full_text):
        idx = full_text.find(old_text, search_start)
        if idx == -1:
            break

        end_idx = idx + len(old_text)
        count += 1

        # Determine affected character range
        affected_indices = list(range(idx, end_idx))
        if not affected_indices or affected_indices[-1] >= len(char_to_run):
            search_start = idx + max(len(new_text), 1)
            continue

        # Group affected characters by source run
        run_groups = {}
        for ci in affected_indices:
            if ci < len(char_to_run):
                rd_idx, _ = char_to_run[ci]
                run_groups.setdefault(rd_idx, []).append(ci)

        rev_id = next(rev_id_counter)
        del_elem = _make_rev_elem(W_DEL, author, rev_id, date_str)
        ins_elem = _make_rev_elem(W_INS, author, rev_id + 1, date_str)
        next(rev_id_counter)  # consume the ins ID too

        # Build the replacement elements for each affected run
        processed_runs = set()
        replacement_nodes = []  # list of (position_index_in_para, element) to insert at end

        # Find the first affected run's position in the paragraph
        first_affected_rd = min(run_groups.keys())
        ref_child = runs_data[first_affected_rd][0]

        for rd_idx in sorted(run_groups.keys()):
            run, t, text, run_start, run_end = runs_data[rd_idx]
            affected_chars = run_groups[rd_idx]
            local_start = min(affected_chars) - run_start
            local_end = max(affected_chars) - run_start + 1

            before_text = text[:local_start]
            deleted_text = text[local_start:local_end]
            after_text = text[local_end:]

            # Build the new node sequence
            new_nodes = []
            if before_text:
                new_nodes.append(_clone_run_styling(run, before_text))

            if deleted_text:
                del_run = _clone_run_styling(run, deleted_text)
                del_run.find(W_T).tag = W_DEL_TEXT
                del_elem.append(del_run)

            if after_text:
                new_nodes.append(_clone_run_styling(run, after_text))

            # Replace the old run with new nodes + deletions/insertions
            parent = para_elem
            idx_in_parent = list(parent).index(run)
            parent.remove(run)

            # Insert back: before_text run(s), then del_elem, then after_text run(s)
            insert_pos = idx_in_parent
            for node in new_nodes:
                parent.insert(insert_pos, node)
                insert_pos += 1

            if deleted_text:
                parent.insert(insert_pos, del_elem)
                insert_pos += 1

            processed_runs.add(rd_idx)

        # Insert the new text (w:ins) after the last deletion
        ins_run = _make_run(new_text)
        ins_elem.append(ins_run)
        # Find the del_elem's position and insert ins_elem right after it
        try:
            del_pos = list(para_elem).index(del_elem)
            para_elem.insert(del_pos + 1, ins_elem)
        except ValueError:
            # del_elem might have been moved, find last tracked change
            track_elems = [c for c in para_elem if c.tag in (W_DEL, W_INS)]
            if track_elems:
                last_tc_pos = list(para_elem).index(track_elems[-1])
                para_elem.insert(last_tc_pos + 1, ins_elem)
            else:
                para_elem.append(ins_elem)

        # Rebuild for next iteration
        runs_data = _collect_paragraph_runs(para_elem)
        full_text = ''.join(rd[2] for rd in runs_data)
        char_to_run = []
        for rd_idx, (run, t, text, start, end) in enumerate(runs_data):
            char_to_run.extend([(rd_idx, i) for i in range(len(text))])

        search_start = idx + max(len(new_text), 1)
        safe_limit -= 1
        if safe_limit <= 0:
            break

    return count


def _replace_in_element(body_elem, old_text: str, new_text: str,
                        author: str, rev_id_counter, date_str: str) -> int:
    """Replace text in all paragraphs within a body element (document body,
    header, footer, etc.), including table cells."""
    total = 0

    # Direct paragraphs
    for p in body_elem.iterfind(f'.//{W_P}'):
        total += _replace_in_paragraph(p, old_text, new_text, author,
                                       rev_id_counter, date_str)

    return total


# ── public API ───────────────────────────────────────────────────────

def direct_tracked_replace(src_path: str, dst_path: str,
                           corrections: dict[str, str],
                           author: str = 'Proofreader') -> int:
    """Replace text in a .docx file with tracked changes, preserving ALL content.

    Opens the .docx as a ZIP archive and directly edits word/document.xml
    using lxml. Only modified runs change — all other parts (styles, headers,
    images, custom XML, VML, etc.) are preserved byte-for-byte.

    Args:
        src_path: Path to source .docx file.
        dst_path: Path for output .docx file.
        corrections: Dict mapping old_text → new_text.
        author: Name shown in tracked changes.

    Returns:
        Total number of replacements made.
    """
    date_str = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")

    # Read source ZIP
    with zipfile.ZipFile(src_path, 'r') as zin:
        zip_data = {name: zin.read(name) for name in zin.namelist()}

    # Parse document.xml
    doc_xml_name = 'word/document.xml'
    if doc_xml_name not in zip_data:
        raise ValueError(f"Not a valid .docx: {doc_xml_name} not found")

    doc_xml = etree.fromstring(zip_data[doc_xml_name])
    body = doc_xml.find(W_BODY)
    if body is None:
        raise ValueError("document.xml has no w:body element")

    rev_id_counter = iter(range(_next_rev_id(body), 999999))

    total = 0
    for old_text, new_text in corrections.items():
        if not old_text or old_text == new_text:
            continue
        count = _replace_in_element(body, old_text, new_text, author,
                                    rev_id_counter, date_str)
        total += count

    if total > 0:
        # Serialize modified document.xml back to bytes
        modified_xml = etree.tostring(doc_xml, xml_declaration=True,
                                      encoding='UTF-8', standalone=True)
        zip_data[doc_xml_name] = modified_xml

    # Write output ZIP
    os.makedirs(os.path.dirname(dst_path) or '.', exist_ok=True)
    with zipfile.ZipFile(dst_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in zip_data.items():
            zout.writestr(name, data)

    return total
