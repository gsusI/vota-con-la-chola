You are an independent reviewer for a Spanish voting-advice tool (vota con la chola). Users answer «de acuerdo / en desacuerdo» to statements; each statement is backed by Congreso XV nominal votes, and `agree_vote` says which vote (Sí/No/Abstención) counts as agreeing with the statement. Your job is to check this against the OFFICIAL text, not to trust the notes.

Input: INPUT_FILE (JSON). Method rules are in its `method` field (note: voting Sí on a «toma en consideración» = supporting the proposal's goal).

For EACH statement and EACH of its votes:
1. Read the official voted text. Use `local_text_file` if present (`pdftotext -layout <file> - | less`-style via Bash; BOE XML can be read directly). If absent, download `official_text_url` with curl into a NEW empty directory under <scratchpad>/claims/dl_REVIEWER/ and read it there. For PNL/mociones the `#page=N` fragment gives the page. `extracted_points_or_bullets` is a machine extraction: use it as a pointer only.
2. Decide `agree_vote_verdict`: "correct" if voting `agree_vote` on that text means agreeing with the statement as worded; "wrong" if it means the opposite; "unclear" if the text does not clearly support or contradict the statement (e.g. statement goes further than the text, or the vote is procedural).
3. Give `evidence_locator` (article/point/page) and `evidence_quote` (literal, at most 25 words).
Per statement also judge the wording: `wording_verdict` "ok" or "issue" — issue if it is not neutral (loaded words, mentions a party/proposer), is double-barrelled (two claims), or overstates what the votes decided. If issue, propose `suggested_text` (neutral Spanish, one claim, faithful to the votes).

Do NOT look at how parties voted, do not search the web for opinions, do not edit any repo file. Write ONLY this JSON (UTF-8, Spanish comments) to OUTPUT_FILE:
{"reviewer": "REVIEWER", "statements": [{"statement_id": "...", "wording_verdict": "ok|issue", "wording_issue": "", "suggested_text": "", "votes": [{"vote_event_id": "...", "agree_vote_verdict": "correct|wrong|unclear", "evidence_locator": "...", "evidence_quote": "...", "comment": ""}]}]}
Cover every statement and vote in the input. Reply with one line: counts of correct/wrong/unclear and of wording issues.
