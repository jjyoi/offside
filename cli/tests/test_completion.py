import unittest
from unittest.mock import patch

import httpx

from offside.__main__ import wait_for_verdict


class VerdictExitTests(unittest.TestCase):
    def test_terminal_verdict_returns_correct_exit_code_without_waiting(self):
        for status, expected in (("approved", 0), ("blocked", 1)):
            with self.subTest(status=status):
                response = httpx.Response(200, json={"status": status, "hp_after": 60, "findings": []},
                                          request=httpx.Request("GET", "http://localhost/review"))
                with patch("offside.__main__.httpx.Client") as client, patch("offside.__main__.time.sleep") as sleep:
                    client.return_value.__enter__.return_value.get.return_value = response
                    self.assertEqual(wait_for_verdict("demo", "http://localhost/review"), expected)
                    sleep.assert_not_called()
