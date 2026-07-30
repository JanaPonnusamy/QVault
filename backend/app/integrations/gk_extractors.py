"""Extraction logic per classified page type (see `gk_site_analyzer.py`).

Deterministic first, always: a known quiz plugin (`wp_basic_quiz` — GKToday's
current plugin, confirmed live) is parsed with fixed selectors plus a
simulated quiz-submission call to reveal the correct answer (the plugin hides
it from the initial page load). Only when no known plugin/pattern yields a
usable structure does this fall back to the existing provider-abstracted LLM
layer (`services/llm_service.py`) to structure the page's text into questions —
never to invent content that is not present on the page.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from app.integrations.gk_http import post_form
from app.services.llm_service import LLMService

_WP_BASIC_QUIZ_CONFIG_RE = re.compile(r"var\s+wp_basic_quiz\s*=\s*(\{.*?\});", re.DOTALL)
_QID_RE = re.compile(r"\[(\d+)\]")
_SQUES_OPTION_RE = re.compile(r"\[([A-D])\]\s*([^\[]+)")
_SQUES_ANSWER_LETTER_RE = re.compile(r"([A-D])\s*[\[:]")

_MCQ_SYSTEM_PROMPT = (
    "You extract multiple-choice quiz questions from raw web page text. "
    'Return ONLY a JSON object: {"questions": [{"question": str, '
    '"options": [str, ...], "correct_answer": str, "explanation": str}]}. '
    'If no real quiz questions are present, return {"questions": []}. '
    "Never invent questions that are not present in the text."
)

_FILL_BLANK_SYSTEM_PROMPT = (
    "You extract fill-in-the-blank questions from raw web page text. "
    'Return ONLY a JSON object: {"items": [{"question": str (blank shown as '
    '____), "answer": str, "explanation": str}]}. If none are present, return '
    '{"items": []}. Never invent content not present in the text.'
)


def _clean_text(html: str, limit: int = 6000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)[:limit]


def extract_mcq(url: str, html: str, plugin: str | None) -> tuple[list[dict], int]:
    """Returns (questions, ai_used) where ai_used is 1 if the AI fallback produced
    any of the returned questions, else 0."""
    if plugin == "sques_quiz":
        rows = _extract_sques_quiz(html)
        if rows:
            return rows, 0
    if plugin == "wp_basic_quiz":
        rows = _extract_wp_basic_quiz(url, html)
        if rows:
            return rows, 0
    return _extract_mcq_via_ai(html)


def _extract_sques_quiz(html: str) -> list[dict]:
    """GKToday's older (and, it turns out, still concurrently used — on both
    topic quizzes and "Daily Current Affairs Quiz" pages) quiz format: unlike
    `wp_basic_quiz`, the correct answer + explanation are already in the
    static HTML (just CSS-hidden behind "Show Answer") — no AJAX simulation
    needed. The outer wrapper div's class differs by page type
    (`sques_quiz` vs `ques_print`), so this walks from each `.wp_quiz_question`
    element itself — via sibling/document-order traversal — rather than
    requiring a specific wrapper, which is what both variants actually share."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for ques_el in soup.select(".wp_quiz_question"):
        options_el = ques_el.find_next_sibling(class_="wp_quiz_question_options")
        if not options_el:
            continue

        # Some pages embed an admin-only "Edit" link inside the options
        # block itself; left in place it bleeds into the last option's text
        # (no closing "[" to stop the regex at). Options are never links.
        for a in options_el.find_all("a"):
            a.decompose()

        question_text = ques_el.get_text(" ", strip=True)
        question_text = re.sub(r"^\d+\.\s*", "", question_text).strip()

        options_text = options_el.get_text("\n", strip=True)
        options = _SQUES_OPTION_RE.findall(options_text)
        if not options:
            continue

        # Answer/hint live further down (inside a CSS-hidden sibling block),
        # not a direct sibling of options_el — find_next walks forward in
        # document order, so this lands on this question's own answer/hint
        # (not a later question's) since blocks never overlap.
        answer_el = options_el.find_next(class_="ques_answer")
        answer_text = answer_el.get_text(" ", strip=True) if answer_el else ""
        answer_text = re.sub(r"(?i)correct\s*answer\s*:?", "", answer_text).strip()
        letter_match = _SQUES_ANSWER_LETTER_RE.search(answer_text)
        correct_letter = letter_match.group(1) if letter_match else None

        hint_el = options_el.find_next(class_="answer_hint")
        solution_text = hint_el.get_text(" ", strip=True) if hint_el else ""
        solution_text = re.sub(r"(?i)^notes\s*:?", "", solution_text).strip()

        option_rows = []
        correct_text = ""
        for label, text in options:
            text = text.strip()
            is_correct = correct_letter == label
            if is_correct:
                correct_text = text
            option_rows.append({"label": label, "text": text, "is_correct": is_correct})

        if question_text and option_rows:
            results.append({
                "question_text": question_text,
                "options": option_rows,
                "correct_answer_text": correct_text,
                "solution_text": solution_text,
                "confidence": 0.9 if correct_letter else 0.5,
            })
    return results


def _extract_wp_basic_quiz(url: str, html: str) -> list[dict]:
    config_match = _WP_BASIC_QUIZ_CONFIG_RE.search(html)
    if not config_match:
        return []
    try:
        config = json.loads(config_match.group(1))
    except json.JSONDecodeError:
        return []
    admin_ajax = config.get("admin_ajax")
    submit_action = config.get("quiz_submit_action")
    if not admin_ajax or not submit_action:
        return []

    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(class_="load_quiz_container")
    if not container:
        return []

    questions = []
    for block in soup.select(".question_list"):
        radio = block.find("input", attrs={"type": "radio"})
        if not radio or not radio.get("name"):
            continue
        match = _QID_RE.search(radio["name"])
        if not match:
            continue
        qid = match.group(1)
        ques_txt = block.select_one(".ques_txt")
        options = []
        for opt in block.select(".funkyradio-success"):
            label = opt.find("label")
            inp = opt.find("input")
            if label and inp:
                options.append({"value": inp.get("value", ""), "text": label.get_text(strip=True)})
        if ques_txt and options:
            questions.append({"id": qid, "question_text": ques_txt.get_text(strip=True), "options": options})

    if not questions:
        return []

    answers_form = "&".join(f"selected_answer[{q['id']}]=1" for q in questions)
    payload = {
        "action": submit_action,
        "subaction": "submitquiz",
        "qncount": container.get("data-qncount", "0"),
        "quiz_token": container.get("data-token", ""),
        "answers": answers_form,
        "testtype": container.get("data-testtype", "daily"),
        "quizids": container.get("data-quiz", ""),
        "quizname": container.get("data-quizname", ""),
        "quizslug": container.get("data-quizslug", ""),
        "quesids": container.get("data-quesids", ""),
        "showans": container.get("data-showans", "1"),
        "quizmarks": container.get("data-quizmarks", "1,0"),
    }
    response = post_form(admin_ajax, payload, referer=url)
    if not response or not response.get("status"):
        # One retry: a cold first hit against the AJAX endpoint occasionally
        # drops (WAF/plugin warm-up), and it's cheap relative to a page fetch.
        response = post_form(admin_ajax, payload, referer=url)

    if not response or not response.get("status"):
        return [
            {
                "question_text": q["question_text"],
                "options": [
                    {"label": chr(64 + i), "text": o["text"], "is_correct": False}
                    for i, o in enumerate(q["options"], 1)
                ],
                "correct_answer_text": "",
                "solution_text": "",
                "confidence": 0.5,
            }
            for q in questions
        ]

    by_id = {str(item.get("id")): item for item in response.get("questions", [])}
    results = []
    for q in questions:
        detail = by_id.get(q["id"]) or {}
        answer_index = str(detail.get("answer")) if detail.get("answer") is not None else None
        options_out = []
        correct_text = ""
        for i, o in enumerate(q["options"], 1):
            is_correct = answer_index is not None and str(i) == answer_index
            if is_correct:
                correct_text = o["text"]
            options_out.append({"label": chr(64 + i), "text": o["text"], "is_correct": is_correct})
        results.append({
            "question_text": q["question_text"],
            "options": options_out,
            "correct_answer_text": correct_text,
            "solution_text": detail.get("explanation") or detail.get("ans_explanation") or "",
            "confidence": 0.9 if answer_index else 0.5,
        })
    return results


def _extract_mcq_via_ai(html: str) -> tuple[list[dict], int]:
    text = _clean_text(html)
    if len(text) < 80:
        return [], 0
    try:
        parsed, _ = LLMService().generate_json(_MCQ_SYSTEM_PROMPT, text)
    except Exception:
        return [], 0

    results = []
    for item in parsed.get("questions") or []:
        options_raw = item.get("options") or []
        correct = str(item.get("correct_answer") or "").strip()
        if not item.get("question") or len(options_raw) < 2:
            continue
        options = [
            {"label": chr(65 + i), "text": str(o), "is_correct": str(o).strip() == correct}
            for i, o in enumerate(options_raw)
        ]
        results.append({
            "question_text": item["question"],
            "options": options,
            "correct_answer_text": correct,
            "solution_text": item.get("explanation", ""),
            "confidence": 0.5,
            "ai_assisted": True,
        })
    return results, (1 if results else 0)


def extract_essay(url: str, html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    article = soup.find("article") or soup.find("main")
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    body_source = article if article else soup
    paragraphs = [p.get_text(" ", strip=True) for p in body_source.find_all("p")]
    body = "\n\n".join(p for p in paragraphs if len(p.split()) > 5)
    if not body:
        return None
    return {"title": title, "body": body[:8000]}


def extract_fill_blank(url: str, html: str) -> tuple[list[dict], int]:
    text = _clean_text(html, limit=8000)
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    deterministic = []
    for i, line in enumerate(lines):
        if not re.search(r"_{3,}|\.{5,}", line):
            continue
        answer = ""
        if i + 1 < len(lines) and re.match(r"(?i)answer\s*[:\-]", lines[i + 1]):
            answer = re.sub(r"(?i)answer\s*[:\-]\s*", "", lines[i + 1]).strip()
        deterministic.append({
            "question_text": line,
            "options": [],
            "correct_answer_text": answer,
            "solution_text": "",
            "confidence": 0.9 if answer else 0.4,
        })

    missing = [d for d in deterministic if not d["correct_answer_text"]]
    if not missing:
        return deterministic, 0

    try:
        parsed, _ = LLMService().generate_json(_FILL_BLANK_SYSTEM_PROMPT, text)
        ai_items = parsed.get("items") or []
    except Exception:
        ai_items = []

    ai_by_question = {item.get("question", "").strip(): item for item in ai_items if item.get("question")}
    for d in missing:
        match = ai_by_question.get(d["question_text"].strip())
        if match and match.get("answer"):
            d["correct_answer_text"] = match["answer"]
            d["solution_text"] = match.get("explanation", "")
            d["confidence"] = 0.5
            d["ai_assisted"] = True

    ai_used = 1 if any(d.get("ai_assisted") for d in deterministic) else 0
    return deterministic, ai_used
