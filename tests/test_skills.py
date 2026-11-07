"""Skills loader tests (built-in files + user overrides)."""
import os
import tempfile
import unittest
from unittest import mock

from molmcp.common import skills


class TestSkills(unittest.TestCase):
    def test_builtin_index_and_lookup(self):
        for app in ("pymol", "chimerax"):
            lst = skills.list_skills(app)
            self.assertTrue(lst, "no skills found for %s" % app)
            for s in lst:
                self.assertTrue(s["name"] and s["body"], s["path"])
                self.assertIn(s["app"], (app, "both", "shared"))
            self.assertIn("working-with-the-agent-tools", [s["name"] for s in lst])
            self.assertIn("skill(name)", skills.index_text(app))
            self.assertIsNotNone(skills.get_skill(app, "working-with-the-agent-tools"))
            self.assertIsNotNone(skills.get_skill(app, "WORKING"))  # fuzzy, case-insensitive

    def test_user_override_and_save(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"MOLMCP_SKILLS_DIR": d}):
            path = skills.save_user_skill("pymol", "My Recipe!", "do this\nthen that")
            self.assertTrue(path.endswith(os.path.join("pymol", "my-recipe.md")))
            s = skills.get_skill("pymol", "my-recipe")
            self.assertEqual(s["source"], "user")
            self.assertIn("do this", s["body"])
            # override a built-in by name
            skills.save_user_skill("pymol", "working-with-the-agent-tools", "---\nname: working-with-the-agent-tools\ntitle: X\napp: pymol\ndescription: mine\ntags: t\n---\nOVERRIDE")
            s = skills.get_skill("pymol", "working-with-the-agent-tools")
            self.assertEqual(s["body"], "OVERRIDE")
            self.assertEqual(s["source"], "user")


if __name__ == "__main__":
    unittest.main()
