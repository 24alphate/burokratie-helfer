"""
Stateless deterministic question flow engine.
No DB access — pure functions operating on plain data.
"""
from __future__ import annotations

import json
from typing import Optional


class FormEngine:
    def evaluate_condition(self, condition: Optional[dict], answers: dict[str, str]) -> bool:
        """
        Returns True if the question should be shown given current answers.
        Returns True when condition is None (always show).
        """
        if condition is None:
            return True

        ctype = condition.get("type")

        if ctype == "field_equals":
            return answers.get(condition["field_key"]) == condition["value"]

        if ctype == "field_not_equals":
            current = answers.get(condition["field_key"])
            return current is not None and current != condition["value"]

        if ctype == "field_in":
            return answers.get(condition["field_key"]) in condition.get("values", [])

        if ctype == "field_not_in":
            val = answers.get(condition["field_key"])
            return val is not None and val not in condition.get("values", [])

        if ctype == "and":
            return all(self.evaluate_condition(c, answers) for c in condition.get("conditions", []))

        if ctype == "or":
            return any(self.evaluate_condition(c, answers) for c in condition.get("conditions", []))

        # Unknown condition type — safe default: show the question
        return True

    def get_applicable_questions(self, questions: list, answers: dict[str, str]) -> list:
        """
        Returns ordered list of questions that should be shown given current answers.
        Each question dict must have: order_index, condition (JSON string or None).
        """
        sorted_qs = sorted(questions, key=lambda q: q.order_index)
        applicable = []
        for q in sorted_qs:
            condition = json.loads(q.condition) if q.condition else None
            if self.evaluate_condition(condition, answers):
                applicable.append(q)
        return applicable

    def get_next_question(self, questions: list, answers: dict[str, str]) -> Optional[object]:
        """
        Returns the next Question to ask, or None if all applicable questions are answered.
        answers: dict of field_key → raw_answer for currently active (is_active=True) answers.
        """
        applicable = self.get_applicable_questions(questions, answers)
        for q in applicable:
            if q.field_key not in answers:
                return q
        return None

    def get_invalidated_field_keys(
        self,
        questions: list,
        old_answers: dict[str, str],
        new_answers: dict[str, str],
    ) -> list[str]:
        """
        When a user changes an answer, some previously answered conditional questions
        may no longer apply. Returns field_keys that were applicable before but not after.
        Used by case_service to soft-delete stale answers.
        """
        old_applicable = {q.field_key for q in self.get_applicable_questions(questions, old_answers)}
        new_applicable = {q.field_key for q in self.get_applicable_questions(questions, new_answers)}
        return list(old_applicable - new_applicable)

    def completion_fraction(self, questions: list, answers: dict[str, str]) -> tuple[int, int]:
        """Returns (answered_count, total_applicable_count) for progress display."""
        applicable = self.get_applicable_questions(questions, answers)
        answered = sum(1 for q in applicable if q.field_key in answers)
        return answered, len(applicable)


form_engine = FormEngine()
