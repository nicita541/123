from __future__ import annotations

import unittest

from complex_agent.memory.short_term_memory import ShortTermMemory


class MemoryTests(unittest.TestCase):
    def test_append_and_summarize(self) -> None:
        memory = ShortTermMemory()
        memory.append("observations", "one")
        self.assertEqual(memory.summarize()["observations"], ["one"])


if __name__ == "__main__":
    unittest.main()

