#!/usr/bin/env python3
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

"""
export_quizzes.py — Step 4: Export quizzes to assessments/ + non_cc_assessments/.

Reads:  .quiz/meta.json + .quiz/source.md   (produced by frontmatter_to_meta.py)
        question-banks/*.bank.md             (for bank-referenced quizzes)
        question-banks/*.quiz.txt            (legacy format)

Writes: assessments/{id}/assessment_qti.xml
        assessments/{id}/assessment_meta.xml
        non_cc_assessments/{id}.xml.qti

Updates EXPORT_MANIFEST_PATH with two resources per quiz (QTI + meta).

Why two resources?
  Canvas CC format requires:
  - QTI resource (questions, with <dependency> pointing to meta)
  - assessment_meta resource (Canvas quiz settings; also lists the non-CC QTI)
  - non_cc_assessments/{id}.xml.qti: Canvas CE importer's convert_quizzes()
    looks ONLY in non_cc_assessments/ and returns early (creating NO quiz
    objects at all) if that folder is absent.

Standalone:
    python -m zaphod.export_quizzes
"""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import markdown
import yaml

from zaphod.export_types import (
    ExportManifest,
    ExportResource,
    generate_content_id,
    prettify_xml,
    add_text_element,
)

COURSE_ROOT = Path.cwd()
METADATA_DIR = COURSE_ROOT / "_course_metadata"
EXPORTS_DIR = METADATA_DIR / "exports"
DEFAULT_MANIFEST_PATH = EXPORTS_DIR / ".export_manifest.json"
QUESTION_BANKS_DIR = COURSE_ROOT / "question-banks"

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def get_content_dir() -> Path:
    content_dir = COURSE_ROOT / "content"
    pages_dir = COURSE_ROOT / "pages"
    return content_dir if content_dir.exists() else pages_dir


def get_manifest_path() -> Path:
    env_path = os.environ.get("EXPORT_MANIFEST_PATH")
    return Path(env_path) if env_path else DEFAULT_MANIFEST_PATH


# ============================================================================
# Question parsing (mirrors sync_banks.py NYIT format patterns)
# ============================================================================

QUESTION_HEADER_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
MC_OPTION_RE = re.compile(r"^\s*([a-z])\)\s+(.*\S)\s*$")
MC_OPTION_CORRECT_RE = re.compile(r"^\s*\*([a-z])\)\s+(.*\S)\s*$")
MULTI_ANSWER_RE = re.compile(r"^\s*\[(\*|\s)\]\s*(.*\S)\s*$")
SHORT_ANSWER_RE = re.compile(r"^\s*\*\s+(.+\S)\s*$")


def split_question_blocks(body: str) -> List[List[str]]:
    """Split quiz body into question blocks (split on blank lines)."""
    lines = body.splitlines()
    blocks: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)

    if current:
        blocks.append(current)

    return blocks


def detect_question_type(block: List[str]) -> str:
    """Detect NYIT question type from block content."""
    body = "\n".join(block)

    if "####" in body:
        return "essay"
    if "^^^^" in body:
        return "file_upload"

    for line in block:
        if re.match(r"^\s*\[[\*\s]\]", line):
            return "multiple_answers"

    has_true = any(re.search(r"a\)\s*True", line, re.IGNORECASE) for line in block)
    has_false = any(re.search(r"b\)\s*False", line, re.IGNORECASE) for line in block)
    if has_true and has_false:
        return "true_false"

    if any(re.match(r"^\s*\*\s+", line) for line in block):
        return "short_answer"

    return "multiple_choice"


def parse_quiz_questions(body: str,
                         default_points: float) -> List[Dict[str, Any]]:
    """Parse quiz questions from body text into structured dicts."""
    questions: List[Dict[str, Any]] = []
    blocks = split_question_blocks(body)

    for block in blocks:
        if not block:
            continue

        m = QUESTION_HEADER_RE.match(block[0])
        if not m:
            continue

        number = int(m.group(1))
        stem = m.group(2).strip()
        rest = block[1:]
        qtype = detect_question_type(block)
        answers: List[Dict[str, Any]] = []

        if qtype == "multiple_choice":
            for line in rest:
                m_corr = MC_OPTION_CORRECT_RE.match(line)
                m_opt = MC_OPTION_RE.match(line)
                if m_corr:
                    answers.append({"text": m_corr.group(2), "correct": True})
                elif m_opt:
                    answers.append({"text": m_opt.group(2), "correct": False})
                elif not answers:
                    stem += " " + line.strip()

        elif qtype == "multiple_answers":
            for line in rest:
                m_ma = MULTI_ANSWER_RE.match(line)
                if m_ma:
                    answers.append({
                        "text": m_ma.group(2),
                        "correct": m_ma.group(1) == "*",
                    })

        elif qtype == "true_false":
            answers = [
                {"text": "True",
                 "correct": any("*a)" in line.lower() for line in block)},
                {"text": "False",
                 "correct": any("*b)" in line.lower() for line in block)},
            ]

        elif qtype == "short_answer":
            for line in rest:
                m_sa = SHORT_ANSWER_RE.match(line)
                if m_sa:
                    answers.append({"text": m_sa.group(1), "correct": True})

        questions.append({
            "number": number,
            "stem": stem,
            "type": qtype,
            "answers": answers,
            "points": default_points,
        })

    return questions


def split_quiz_frontmatter(raw: str) -> Tuple[Dict[str, Any], str]:
    """Split YAML frontmatter from quiz body text."""
    lines = raw.splitlines()
    if not lines or not lines[0].strip().startswith("---"):
        return {}, raw

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip().startswith("---"):
            end_idx = i
            break

    if end_idx is None:
        return {}, raw

    fm_text = "\n".join(lines[1:end_idx])
    body_text = "\n".join(lines[end_idx + 1:])
    meta = yaml.safe_load(fm_text) or {}
    return meta if isinstance(meta, dict) else {}, body_text


def extract_quiz_description(body: str) -> str:
    """Extract description text (lines before the first numbered question)."""
    lines = body.splitlines()
    desc_lines = []
    for line in lines:
        if re.match(r"^\s*\d+\.\s+", line):
            break
        desc_lines.append(line)
    return "\n".join(desc_lines).strip()


def load_questions_from_banks(question_groups: list) -> List[Dict[str, Any]]:
    """Load questions from .bank.md files referenced in question_groups."""
    questions: List[Dict[str, Any]] = []
    default_points = 1.0

    for group in question_groups:
        bank_filename = group.get("bank")
        points = float(group.get("points_per_question", default_points))
        if not bank_filename:
            continue

        bank_path = QUESTION_BANKS_DIR / f"{bank_filename}.md"
        if not bank_path.exists():
            bank_path = QUESTION_BANKS_DIR / bank_filename
        if not bank_path.exists():
            print(f"[export:quizzes:warn] Bank not found: {bank_filename}")
            continue

        try:
            raw = bank_path.read_text(encoding="utf-8")
            _, body = split_quiz_frontmatter(raw)
            questions.extend(parse_quiz_questions(body, points))
        except Exception as e:
            print(f"[export:quizzes:warn] Failed to load bank {bank_filename}: {e}")

    return questions


# ============================================================================
# QTI XML generation
# ============================================================================

def add_qti_metadata(parent: ET.Element, label: str, entry: str) -> None:
    """Add a <qtimetadatafield> child to *parent*."""
    field = ET.SubElement(parent, "qtimetadatafield")
    add_text_element(field, "fieldlabel", label)
    add_text_element(field, "fieldentry", entry)


def add_choice_response(presentation: ET.Element, item: ET.Element,
                        question: Dict[str, Any]) -> None:
    """Add choice-based response elements to a QTI item."""
    rcardinality = "Single" if question["type"] != "multiple_answers" else "Multiple"

    response_lid = ET.SubElement(presentation, "response_lid")
    response_lid.set("ident", "response1")
    response_lid.set("rcardinality", rcardinality)

    render_choice = ET.SubElement(response_lid, "render_choice")
    for i, answer in enumerate(question.get("answers", [])):
        lbl = ET.SubElement(render_choice, "response_label")
        lbl.set("ident", f"answer{i}")
        mat = ET.SubElement(lbl, "material")
        mt = ET.SubElement(mat, "mattext")
        mt.set("texttype", "text/plain")
        mt.text = answer["text"]

    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes_elem = ET.SubElement(resprocessing, "outcomes")
    decvar = ET.SubElement(outcomes_elem, "decvar")
    decvar.set("maxvalue", "100")
    decvar.set("minvalue", "0")
    decvar.set("varname", "SCORE")
    decvar.set("vartype", "Decimal")

    correct_ids = [
        f"answer{i}"
        for i, a in enumerate(question.get("answers", []))
        if a.get("correct")
    ]
    for correct_id in correct_ids:
        rc = ET.SubElement(resprocessing, "respcondition")
        rc.set("continue", "No")
        cv = ET.SubElement(rc, "conditionvar")
        ve = ET.SubElement(cv, "varequal")
        ve.set("respident", "response1")
        ve.text = correct_id
        sv = ET.SubElement(rc, "setvar")
        sv.set("action", "Set")
        sv.set("varname", "SCORE")
        sv.text = "100"


def add_short_answer_response(presentation: ET.Element, item: ET.Element,
                               question: Dict[str, Any]) -> None:
    """Add short-answer response elements to a QTI item."""
    rs = ET.SubElement(presentation, "response_str")
    rs.set("ident", "response1")
    rs.set("rcardinality", "Single")
    fib = ET.SubElement(rs, "render_fib")
    rl = ET.SubElement(fib, "response_label")
    rl.set("ident", "answer1")

    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes_elem = ET.SubElement(resprocessing, "outcomes")
    decvar = ET.SubElement(outcomes_elem, "decvar")
    decvar.set("maxvalue", "100")
    decvar.set("minvalue", "0")
    decvar.set("varname", "SCORE")
    decvar.set("vartype", "Decimal")

    for answer in question.get("answers", []):
        if answer.get("correct"):
            rc = ET.SubElement(resprocessing, "respcondition")
            cv = ET.SubElement(rc, "conditionvar")
            ve = ET.SubElement(cv, "varequal")
            ve.set("respident", "response1")
            ve.text = answer["text"]
            sv = ET.SubElement(rc, "setvar")
            sv.set("action", "Set")
            sv.set("varname", "SCORE")
            sv.text = "100"


def add_essay_response(presentation: ET.Element, item: ET.Element,
                       question: Dict[str, Any]) -> None:
    """Add essay response elements to a QTI item."""
    rs = ET.SubElement(presentation, "response_str")
    rs.set("ident", "response1")
    rs.set("rcardinality", "Single")
    fib = ET.SubElement(rs, "render_fib")
    fib.set("fibtype", "String")
    fib.set("rows", "15")
    fib.set("columns", "60")


def add_qti_item(section: ET.Element, question: Dict[str, Any],
                 quiz_id: str) -> None:
    """Add a question <item> to a QTI section element."""
    item_id = f"{quiz_id}_q{question['number']}"

    item = ET.SubElement(section, "item")
    item.set("ident", item_id)
    item.set("title", f"Question {question['number']}")

    itemmetadata = ET.SubElement(item, "itemmetadata")
    qtimetadata = ET.SubElement(itemmetadata, "qtimetadata")

    qti_type_map = {
        "multiple_choice": "multiple_choice_question",
        "multiple_answers": "multiple_answers_question",
        "true_false": "true_false_question",
        "short_answer": "short_answer_question",
        "essay": "essay_question",
        "file_upload": "file_upload_question",
    }
    add_qti_metadata(qtimetadata, "cc_profile",
                     qti_type_map.get(question["type"], "multiple_choice_question"))
    add_qti_metadata(qtimetadata, "cc_weighting", str(question["points"]))

    presentation = ET.SubElement(item, "presentation")
    mat = ET.SubElement(presentation, "material")
    mt = ET.SubElement(mat, "mattext")
    mt.set("texttype", "text/html")
    mt.text = f"<p>{html.escape(question['stem'])}</p>"

    if question["type"] in ["multiple_choice", "multiple_answers", "true_false"]:
        add_choice_response(presentation, item, question)
    elif question["type"] == "short_answer":
        add_short_answer_response(presentation, item, question)
    elif question["type"] == "essay":
        add_essay_response(presentation, item, question)


def generate_qti_assessment(identifier: str, title: str, meta: Dict[str, Any],
                             description: str,
                             questions: List[Dict[str, Any]]) -> str:
    """Generate QTI 1.2 XML for a quiz (CC format for standard importers)."""
    root = ET.Element("questestinterop")
    root.set("xmlns", "http://www.imsglobal.org/xsd/ims_qtiasiv1p2")

    assessment = ET.SubElement(root, "assessment")
    assessment.set("ident", identifier)
    assessment.set("title", title)

    qtimetadata = ET.SubElement(assessment, "qtimetadata")
    add_qti_metadata(qtimetadata, "cc_profile", "cc.exam.v0p1")
    add_qti_metadata(qtimetadata, "qmd_assessmenttype", "Examination")

    if meta.get("time_limit"):
        add_qti_metadata(qtimetadata, "qmd_timelimit", str(meta["time_limit"]))

    # Zaphod-specific metadata for round-trip fidelity
    for key, label in [
        ("quiz_type", "zaphod_quiz_type"),
        ("points_possible", "zaphod_points_possible"),
        ("allowed_attempts", "zaphod_allowed_attempts"),
    ]:
        if meta.get(key):
            add_qti_metadata(qtimetadata, label, str(meta[key]))

    if meta.get("inline_questions") is not None:
        add_qti_metadata(qtimetadata, "zaphod_inline_questions",
                         str(meta["inline_questions"]))
    if meta.get("shuffle_answers") is not None:
        add_qti_metadata(qtimetadata, "zaphod_shuffle_answers",
                         str(meta["shuffle_answers"]))
    if meta.get("published") is not None:
        add_qti_metadata(qtimetadata, "zaphod_published", str(meta["published"]))

    if description:
        objectives = ET.SubElement(assessment, "objectives")
        mat = ET.SubElement(objectives, "material")
        mt = ET.SubElement(mat, "mattext")
        mt.set("texttype", "text/html")
        mt.text = markdown.markdown(description, extensions=["extra", "codehilite"])

    section = ET.SubElement(assessment, "section")
    section.set("ident", f"{identifier}_section")
    for q in questions:
        add_qti_item(section, q, identifier)

    return prettify_xml(root)


def generate_non_cc_qti(identifier: str, title: str, meta: Dict[str, Any],
                        questions: List[Dict[str, Any]]) -> str:
    """
    Generate non-CC QTI 1.2 for non_cc_assessments/{id}.xml.qti.

    Canvas CE importer's convert_quizzes() looks ONLY in non_cc_assessments/
    and returns early (creating NO quiz objects at all) if that folder is absent.
    The non-CC format uses a different schema URL and a nested section structure.
    """
    root = ET.Element("questestinterop")
    root.set("xmlns", "http://www.imsglobal.org/xsd/ims_qtiasiv1p2")
    root.set("xmlns:xsi", XSI_NS)
    root.set("xsi:schemaLocation",
             "http://www.imsglobal.org/xsd/ims_qtiasiv1p2 "
             "http://www.imsglobal.org/xsd/ims_qtiasiv1p2p1.xsd")

    assessment = ET.SubElement(root, "assessment")
    assessment.set("ident", identifier)
    assessment.set("title", title)

    qtimetadata = ET.SubElement(assessment, "qtimetadata")
    if meta.get("time_limit"):
        add_qti_metadata(qtimetadata, "qmd_timelimit", str(meta["time_limit"]))
    if meta.get("allowed_attempts"):
        add_qti_metadata(qtimetadata, "cc_maxattempts", str(meta["allowed_attempts"]))

    root_section = ET.SubElement(assessment, "section")
    root_section.set("ident", "root_section")

    # Canvas non-CC format convention: questions go in a nested section
    questions_section = ET.SubElement(root_section, "section")
    questions_section.set("ident", f"{identifier}_questions")
    questions_section.set("title", title)

    for q in questions:
        add_qti_item(questions_section, q, identifier)

    return prettify_xml(root)


def generate_assessment_meta_xml(identifier: str, title: str,
                                  meta: Dict[str, Any], description: str,
                                  question_count: int) -> str:
    """
    Generate assessment_meta.xml — Canvas-specific quiz settings companion.

    Canvas requires this alongside the QTI file to create a proper quiz object.
    Without it Canvas cannot import the quiz at all.
    """
    root = ET.Element("quiz")
    root.set("identifier", identifier)
    root.set("xmlns", "http://canvas.instructure.com/xsd/cccv1p0")
    root.set("xmlns:xsi", XSI_NS)
    root.set("xsi:schemaLocation",
             "http://canvas.instructure.com/xsd/cccv1p0 "
             "https://canvas.instructure.com/xsd/cccv1p0.xsd")

    ET.SubElement(root, "title").text = title
    desc_html = markdown.markdown(description, extensions=["extra"]) if description else ""
    ET.SubElement(root, "description").text = desc_html
    ET.SubElement(root, "shuffle_answers").text = str(
        meta.get("shuffle_answers", True)).lower()
    ET.SubElement(root, "scoring_policy").text = meta.get("scoring_policy", "keep_highest")
    ET.SubElement(root, "hide_results")
    ET.SubElement(root, "quiz_type").text = meta.get("quiz_type", "assignment")
    ET.SubElement(root, "points_possible").text = str(
        float(meta.get("points_possible", question_count))
    )
    ET.SubElement(root, "require_lockdown_browser").text = "false"
    ET.SubElement(root, "require_lockdown_browser_for_results").text = "false"
    ET.SubElement(root, "require_lockdown_browser_monitor").text = "false"
    ET.SubElement(root, "lockdown_browser_monitor_data")
    ET.SubElement(root, "show_correct_answers").text = str(
        meta.get("show_correct_answers", True)
    ).lower()
    ET.SubElement(root, "anonymous_submissions").text = "false"
    ET.SubElement(root, "could_be_locked").text = "false"

    time_limit = meta.get("time_limit", "")
    ET.SubElement(root, "time_limit").text = str(time_limit) if time_limit else ""
    ET.SubElement(root, "disable_timer_autosubmission").text = "false"
    ET.SubElement(root, "allowed_attempts").text = str(meta.get("allowed_attempts", 1))
    ET.SubElement(root, "one_question_at_a_time").text = "false"
    ET.SubElement(root, "cant_go_back").text = "false"
    ET.SubElement(root, "available").text = "false"
    ET.SubElement(root, "one_time_results").text = "false"
    ET.SubElement(root, "show_correct_answers_last_attempt").text = "false"
    ET.SubElement(root, "only_visible_to_overrides").text = "false"
    ET.SubElement(root, "module_locked").text = "false"
    ET.SubElement(root, "assignment_overrides")

    return prettify_xml(root)


# ============================================================================
# Quiz loading
# ============================================================================

def _load_quiz_dict(identifier: str, title: str, meta: Dict[str, Any],
                    body: str) -> Dict[str, Any]:
    """Build a quiz data dict from parsed components."""
    description = extract_quiz_description(body)
    questions = parse_quiz_questions(body, float(meta.get("points_per_question", 1.0)))

    if not questions and meta.get("question_groups"):
        questions = load_questions_from_banks(meta["question_groups"])

    return {
        "identifier": identifier,
        "title": title,
        "meta": meta,
        "description": description,
        "questions": questions,
    }


def load_quiz_from_folder(quiz_folder: Path) -> Optional[Dict[str, Any]]:
    """Load a quiz from a .quiz/ folder using meta.json + source.md."""
    meta_path = quiz_folder / "meta.json"
    if not meta_path.is_file():
        print(f"[export:quizzes:warn] No meta.json in {quiz_folder.name}, skipping")
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[export:quizzes:warn] Failed to load {meta_path}: {e}")
        return None

    title = meta.get("name") or meta.get("title")
    if not title:
        title = quiz_folder.stem.replace(".quiz", "").replace("-", " ").strip()

    body = ""
    source_path = quiz_folder / "source.md"
    if source_path.is_file():
        body = source_path.read_text(encoding="utf-8")

    identifier = generate_content_id(quiz_folder, COURSE_ROOT)
    return _load_quiz_dict(identifier, title, meta, body)


# ============================================================================
# Writing quiz output files
# ============================================================================

def _write_quiz(quiz_data: Dict[str, Any], assessments_dir: Path,
                non_cc_dir: Path, manifest: ExportManifest) -> None:
    """Write QTI files for one quiz and append resources to the manifest."""
    identifier = quiz_data["identifier"]
    title = quiz_data["title"]
    meta = quiz_data["meta"]
    description = quiz_data["description"]
    questions = quiz_data["questions"]

    quiz_dir = assessments_dir / identifier
    quiz_dir.mkdir(parents=True, exist_ok=True)

    # CC QTI (for standard importers)
    (quiz_dir / "assessment_qti.xml").write_text(
        generate_qti_assessment(identifier, title, meta, description, questions),
        encoding="utf-8",
    )

    # Canvas assessment_meta.xml (quiz settings)
    (quiz_dir / "assessment_meta.xml").write_text(
        generate_assessment_meta_xml(identifier, title, meta, description,
                                     len(questions)),
        encoding="utf-8",
    )

    # non_cc_assessments/{id}.xml.qti (Canvas CE importer requirement)
    (non_cc_dir / f"{identifier}.xml.qti").write_text(
        generate_non_cc_qti(identifier, title, meta, questions),
        encoding="utf-8",
    )

    meta_id = f"{identifier}_meta"

    # QTI resource — questions; links to meta via dependency
    manifest.append_resource(ExportResource(
        identifier=identifier,
        type="imsqti_xmlv1p2/imscc_xmlv1p1/assessment",
        href=None,
        files=[f"assessments/{identifier}/assessment_qti.xml"],
        dependency=meta_id,
    ))

    # Meta resource — also lists the non-CC QTI so Canvas CE can find it
    manifest.append_resource(ExportResource(
        identifier=meta_id,
        type="associatedcontent/imscc_xmlv1p1/learning-application-resource",
        href=f"assessments/{identifier}/assessment_meta.xml",
        files=[
            f"assessments/{identifier}/assessment_meta.xml",
            f"non_cc_assessments/{identifier}.xml.qti",
        ],
    ))


# ============================================================================
# Main step logic
# ============================================================================

def export_quizzes(manifest: ExportManifest) -> None:
    """Export all quizzes to assessments/ + non_cc_assessments/ in staging."""
    staging_dir = manifest.staging_dir
    assessments_dir = staging_dir / "assessments"
    non_cc_dir = staging_dir / "non_cc_assessments"
    assessments_dir.mkdir(parents=True, exist_ok=True)
    non_cc_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    content_dir = get_content_dir()

    if content_dir.exists():
        for quiz_folder in sorted(content_dir.rglob("*.quiz")):
            if not quiz_folder.is_dir():
                continue

            quiz_data = load_quiz_from_folder(quiz_folder)
            if not quiz_data:
                continue

            _write_quiz(quiz_data, assessments_dir, non_cc_dir, manifest)
            count += 1
            print(f"[export:quizzes] {quiz_data['title']} "
                  f"({len(quiz_data['questions'])} questions)")

    # Legacy: .quiz.txt files in question-banks/
    if QUESTION_BANKS_DIR.exists():
        for quiz_file in sorted(QUESTION_BANKS_DIR.glob("*.quiz.txt")):
            try:
                raw = quiz_file.read_text(encoding="utf-8")
                meta, body = split_quiz_frontmatter(raw)
                title = meta.get("name") or meta.get("title") or quiz_file.stem
                identifier = generate_content_id(quiz_file, COURSE_ROOT)
                quiz_data = _load_quiz_dict(identifier, title, meta, body)
                _write_quiz(quiz_data, assessments_dir, non_cc_dir, manifest)
                count += 1
                print(f"[export:quizzes] {title} "
                      f"({len(quiz_data['questions'])} questions) [legacy]")
            except Exception as e:
                print(f"[export:quizzes:warn] Failed to process {quiz_file}: {e}")

    print(f"[export:quizzes] Done — {count} quizzes exported")


def main() -> None:
    manifest_path = get_manifest_path()
    if not manifest_path.is_file():
        print(f"[export:quizzes] ERROR: manifest not found at {manifest_path}")
        print("[export:quizzes] Run 'zaphod export' first to initialise the export.")
        raise SystemExit(1)

    manifest = ExportManifest.load(manifest_path)
    export_quizzes(manifest)
    manifest.save(manifest_path)


if __name__ == "__main__":
    main()
