"""Behavior checks for the Statistics conversational analysis agent."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import ai_analysis


BASE = {
    "metadata": {"platform": "survey", "category": "통계", "row_count": 100},
    "tables": [
        {
            "id": "score_summary",
            "title": "점수 요약",
            "section": "기술통계",
            "columns": ["집단", "평균", "작성자"],
            "rows": [["A", 12, "secret-person"], ["B", 10, "secret-person-2"]],
            "row_count": 2,
        },
        {
            "id": "writer_analysis",
            "title": "작성자 분석",
            "columns": ["사람", "횟수"],
            "rows": [["secret-person", 99]],
            "row_count": 1,
        },
    ],
}


def response(text):
    return SimpleNamespace(
        result=SimpleNamespace(text=text, display_model="local-model"),
        target=SimpleNamespace(label="local"),
        cost_usd=0.01,
        notes=[],
    )


class AnalysisAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_reads_safe_table_calculates_and_remembers_conversation(self):
        fake = AsyncMock(
            side_effect=[
                response('{"tool":"read_table","table_id":"score_summary"}'),
                response('{"tool":"calculate","expression":"(12-10)/10*100"}'),
                response("점수 요약 표에서 A 평균 12, B 평균 10으로 차이는 20%입니다."),
            ]
        )
        with patch.object(ai_analysis.user_llm, "achat_for_user", fake):
            result = await ai_analysis.analyze(
                BASE,
                "user-1",
                "chat",
                question="A와 B의 차이를 계산해줘",
                history=[
                    {"role": "user", "content": "두 집단을 보자"},
                    {"role": "assistant", "content": "집단을 확인하겠습니다."},
                ],
            )

        self.assertEqual(result["cost_usd"], 0.03)
        self.assertEqual(result["tables_used"], ["점수 요약"])
        sent = json.dumps(fake.call_args_list, ensure_ascii=False, default=str)
        self.assertIn("두 집단을 보자", sent)
        self.assertIn("20", sent)
        self.assertNotIn("secret-person", sent)
        self.assertNotIn("작성자 분석", sent)

    async def test_rejects_invalid_history_and_private_table(self):
        with self.assertRaises(ValueError):
            await ai_analysis.analyze(
                BASE, "user-1", "chat", question="질문", history={"role": "user"}
            )
        self.assertEqual(
            ai_analysis._agent_tool(
                BASE, {"tool": "read_table", "table_id": "writer_analysis"}
            ),
            {"error": "조회할 수 없는 표입니다."},
        )

    def test_calculator_rejects_code(self):
        self.assertEqual(ai_analysis._calculate("(12-10)/10*100"), "20")
        self.assertEqual(
            ai_analysis._agent_action(
                '[도구 호출] read_table({"table_id":"score_summary"})'
            ),
            {"tool": "read_table", "table_id": "score_summary"},
        )
        with self.assertRaises(ValueError):
            ai_analysis._calculate("__import__('os').system('true')")


if __name__ == "__main__":
    unittest.main()
