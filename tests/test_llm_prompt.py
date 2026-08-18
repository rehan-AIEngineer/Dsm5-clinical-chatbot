import unittest

from app.llm import build_cot_prompt


class LlmPromptSafetyTests(unittest.TestCase):
    def test_prompt_forbids_diagnosis_and_treatment_recommendations(self):
        prompt = build_cot_prompt("I feel very anxious lately", [{"disorder_name": "Anxiety Disorders", "section_name": "Overview", "text": "Anxiety can be distressing."}])

        self.assertIn("never provide a definitive diagnosis", prompt.lower())
        self.assertIn("do not offer treatment plans", prompt.lower())
        self.assertIn("medication advice", prompt.lower())


if __name__ == "__main__":
    unittest.main()
