from __future__ import annotations

import unittest

from streamlit.testing.v1 import AppTest


class StreamlitInterfaceTests(unittest.TestCase):
    def test_initial_screen_renders_without_exception(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertEqual(
            [(metric.label, metric.value) for metric in app.metric],
            [
                ("Messages reçus", "12"),
                ("Visites uniques", "11"),
                ("Messages fusionnés", "1"),
            ],
        )

    def test_generation_displays_results_and_downloads(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        generate = next(button for button in app.button if button.label == "Générer le briefing")
        generate.click().run(timeout=30)

        self.assertEqual([str(item.value) for item in app.exception], [])
        self.assertTrue(
            {"Briefing", "Preuves", "Traçabilité"}.issubset(
                {tab.label for tab in app.tabs}
            )
        )
        self.assertTrue(
            {"Télécharger en Markdown", "Télécharger en PDF"}.issubset(
                {button.label for button in app.get("download_button")}
            )
        )
        self.assertTrue(app.session_state["result"]["pdf"].startswith(b"%PDF"))

    def test_anthropic_model_selector_renders(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        provider = next(item for item in app.selectbox if item.label == "Moteur sémantique")
        provider.select("Anthropic").run()

        self.assertEqual([str(item.value) for item in app.exception], [])
        model = next(item for item in app.selectbox if item.label == "Modèle Claude")
        self.assertEqual(model.value, "claude-haiku-5-5")
        self.assertIn("Clé API", {item.label for item in app.text_input})


if __name__ == "__main__":
    unittest.main()
