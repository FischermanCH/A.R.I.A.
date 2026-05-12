from __future__ import annotations

from pathlib import Path

from aria.core.i18n import I18NStore
from aria.core.text_utils import is_english

_IMAP_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _imap_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _IMAP_I18N.t(language or "de", f"result_imap.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _imap_split_markers() -> tuple[str, ...]:
    localized = _imap_text("de", "mailbox_split_markers", "")
    markers = [item for item in localized.split("|") if item]
    return tuple([":", *markers, ' for “', ' for "', " for "])


def extract_imap_mailbox_name(first_line: str) -> str:
    text = str(first_line or "").strip()
    for prefix in ("Latest emails from ", "Neueste Mails aus ", "Treffer in ", "Matches in ", "Mailbox leer: ", "Mailbox is empty: "):
        if text.startswith(prefix):
            remainder = text[len(prefix):].strip()
            for stop in _imap_split_markers():
                if stop in remainder:
                    remainder = remainder.split(stop, 1)[0].strip()
                    break
            return remainder
    return ""


def extract_imap_subjects(lines: list[str]) -> list[str]:
    subjects: list[str] = []
    for line in lines[1:]:
        clean = str(line or "").strip()
        if not clean:
            continue
        if clean.lower().startswith("from:"):
            continue
        if clean[:1].isdigit() and ". " in clean:
            subject = clean.split(". ", 1)[1].strip()
            if " [" in subject:
                subject = subject.split(" [", 1)[0].strip()
            if subject:
                subjects.append(subject)
    return subjects


def extract_imap_first_sender(lines: list[str]) -> str:
    for line in lines:
        clean = str(line or "").strip()
        if clean.lower().startswith("from:"):
            return clean.split(":", 1)[1].strip()
    return ""


def summarize_imap_result_for_chat(
    text: str,
    *,
    connection_ref: str,
    capability: str,
    search_query: str = "",
    language: str | None = None,
) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return ""
    lines = [str(line or "").rstrip() for line in clean_text.splitlines() if str(line or "").strip()]
    if not lines:
        return ""

    first = lines[0].strip()
    mailbox = extract_imap_mailbox_name(first)
    mailbox_label = mailbox or "INBOX"
    ref_label = f"`{connection_ref}`"

    if first.lower().startswith("mailbox leer:") or first.lower().startswith("mailbox is empty:"):
        return _imap_text(language, "mailbox_empty", "Mailbox check for {ref}: {mailbox} is empty.", ref=ref_label, mailbox=mailbox_label)

    if first.lower().startswith("latest emails from") or first.lower().startswith("neueste mails aus"):
        subjects = extract_imap_subjects(lines)
        sender = extract_imap_first_sender(lines)
        count = len(subjects)
        if not count:
            return ""
        parts = [
            _imap_text(
                language,
                "latest_emails",
                "Mailbox check for {ref}: {count} latest email{plural} from {mailbox}.",
                ref=ref_label,
                count=count,
                plural="" if count == 1 else "s",
                mailbox=mailbox_label,
            )
        ]
        preview = ", ".join(subjects[:3])
        if preview:
            parts.append(
                _imap_text(language, "latest_subjects", "Latest subjects: {preview}.", preview=preview)
            )
        if sender:
            parts.append(
                _imap_text(language, "latest_sender", "Most recent sender: {sender}.", sender=sender)
            )
        return " ".join(parts).strip()

    if first.lower().startswith("treffer in") or first.lower().startswith("matches in"):
        subjects = extract_imap_subjects(lines)
        count = len(subjects)
        if not count:
            return ""
        clean_query = str(search_query or "").strip()
        if is_english(language):
            parts = [f"Mailbox search for {ref_label}: {count} match{'es' if count != 1 else ''} in {mailbox_label}."]
            if clean_query:
                parts.append(f'Query: "{clean_query}".')
            parts.append(f"Top subjects: {', '.join(subjects[:3])}.")
        else:
            parts = [_imap_text(language, "search_matches", "Mailbox search for {ref}: {count} matches in {mailbox}.", ref=ref_label, count=count, mailbox=mailbox_label)]
            if clean_query:
                parts.append(_imap_text(language, "query", 'Query: "{query}".', query=clean_query))
            parts.append(_imap_text(language, "top_subjects", "Top subjects: {subjects}.", subjects=", ".join(subjects[:3])))
        return " ".join(parts).strip()
    return ""
