"""Test di 'fili --skill' (la guida per un'AI). Nulla tocca il sistema.

Esecuzione:  python -I tests/test_skill.py        (dalla radice del repository)
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from test_fili import FakeRun, call  # noqa: E402  (disattiva anche l'esecutore vero)

from fili import __version__, cli, skill  # noqa: E402


def subcommands(parser):
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            return action.choices
    return {}


def all_options(parser):
    found = set()
    for p in [parser] + list(subcommands(parser).values()):
        for action in p._actions:
            found.update(action.option_strings)
    return found


class TestSkillFlag(unittest.TestCase):
    def test_prints_the_guide_and_exits_zero_without_a_command(self):
        run = FakeRun()
        code, out, err, run = call(["--skill"], run=run)
        self.assertEqual(code, 0, err)
        self.assertEqual(run.calls, [])                      # nessun comando di sistema, nemmeno di sola lettura
        self.assertIn("fili - guide for an AI agent (version %s)" % __version__, out)
        self.assertIn("Never add `--yes` or `--force` on your own", out)
        self.assertIn("## Workflow for a change", out)

    def test_alias_and_position(self):
        _, ref, _, _ = call(["--skill"])
        for argv in (["--skil"], ["list", "--skill"], ["--skill", "--dry-run"]):
            code, out, err, run = call(argv)
            self.assertEqual((code, out), (0, ref), argv)
            self.assertEqual(run.calls, [])

    def test_json_wraps_the_text(self):
        code, out, err, _ = call(["--json", "--skill"])
        self.assertEqual(code, 0, err)
        doc = json.loads(out)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["command"], "skill")
        self.assertIn("## Exit codes", doc["data"]["markdown"])

    def test_listed_in_the_main_help(self):
        text = cli._build_parser().format_help()      # --help lo stampa argparse sullo stdout vero, non su un flusso nostro
        self.assertIn("--skill", text)
        self.assertIn("AI agent", text)


class TestSkillContent(unittest.TestCase):
    def setUp(self):
        self.text = skill.build(__version__, cli.EXIT_CODES)
        self.parser = cli._build_parser()

    def test_every_command_of_the_parser_is_in_the_guide_and_vice_versa(self):
        in_guide = {name for name, _, _ in skill.COMMANDS}
        self.assertEqual(in_guide, set(subcommands(self.parser)))
        for name in in_guide:
            self.assertIn("`%s`" % name, self.text)

    def test_every_exit_code_is_listed_with_its_meaning(self):
        for code, meaning in cli.EXIT_CODES.items():
            self.assertIn("- %d: %s" % (code, meaning), self.text)

    def test_every_option_the_guide_mentions_exists(self):
        real = all_options(self.parser) | {"--skill", "--skil"}
        mentioned = set(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", self.text))
        # --out è il nome che la guida usa per l'opzione di 'extract'; --force/--yes ecc. devono esserci davvero
        unknown = sorted(m for m in mentioned if m not in real)
        self.assertEqual(unknown, [], "opzioni citate nella guida ma inesistenti: %s" % unknown)

    def test_safety_rules_are_present(self):
        for phrase in ("--dry-run", "approved", "Administrator", "self-signed certificate", "protected classes",
                       "usb-reset", "cert-remove", "--all-matching", "--instance", "--iface"):
            self.assertIn(phrase, self.text)

    def test_commands_that_change_the_system_are_marked(self):
        marked = {n: e for n, e, _ in skill.COMMANDS}
        for name in ("install", "reinstall", "restore", "uninstall", "usb-reset"):
            self.assertIn("CHANGES the system", marked[name])
        for name in ("list", "status", "diagnose", "extract"):
            self.assertEqual(marked[name], "read-only")

    def test_formatting_leaves_no_template_braces(self):
        self.assertNotRegex(self.text, r"\{(version|commands|exit_codes)\}")
        self.assertIn('{"command": str', self.text)


if __name__ == "__main__":
    unittest.main()
