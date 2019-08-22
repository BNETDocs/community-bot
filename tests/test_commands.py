
from bnetbot.instance import *
from bnetbot.commands import *
import unittest


class TestCommandParsing(unittest.TestCase):
    def test_trigger(self):
        bot = BotInstance("test")
        self.assertIsNone(bot.parse_command(".test", source=SOURCE_LOCAL))
        self.assertIsNotNone(bot.parse_command("/test", source=SOURCE_LOCAL))
        self.assertIsNotNone(bot.parse_command("!test", source=SOURCE_PUBLIC))
        self.assertIsNone(bot.parse_command(".test", source=SOURCE_PUBLIC))

    def test_parsing(self):
        bot = BotInstance("test")
        cmd = bot.parse_command("/test 1 2 3")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.command, "test")
        self.assertEqual(len(cmd.args), 3)


if __name__ == "__main__":
    unittest.main()
