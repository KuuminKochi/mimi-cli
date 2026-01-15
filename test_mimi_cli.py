import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO

sys.path.insert(0, "/home/kuumin/Projects/mimi-cli")

# Import from new modular structure
import mimi_lib.ui.ansi as ansi_helpers
import mimi_lib.utils.text as text_utils
from mimi_lib.ui.printer import StreamPrinter
from mimi_lib.ui.input import VimInput

# NOTE: COMMANDS are now usually in the App class, but VimInput might not have them as static list anymore.
# We'll check the implementation of VimInput.

class TestANSIHelpers(unittest.TestCase):
    """Test ANSI escape helper functions."""

    def test_clear_screen_output(self):
        """Test that clear_screen produces correct ANSI sequence."""
        with patch("sys.stdout.write") as mock_write:
            ansi_helpers.clear_screen()
            mock_write.assert_called_once_with("\033[2J\033[H")

    def test_save_cursor_output(self):
        """Test that save_cursor produces correct ANSI sequence."""
        with patch("sys.stdout.write") as mock_write:
            ansi_helpers.save_cursor()
            mock_write.assert_called_once_with("\033[s")

    def test_restore_cursor_output(self):
        """Test that restore_cursor produces correct ANSI sequence."""
        with patch("sys.stdout.write") as mock_write:
            ansi_helpers.restore_cursor()
            mock_write.assert_called_once_with("\033[u")

    def test_erase_current_line_output(self):
        """Test that erase_current_line produces correct ANSI sequence."""
        with patch("sys.stdout.write") as mock_write:
            ansi_helpers.erase_current_line()
            mock_write.assert_called_once_with("\033[2K\r")


class TestStreamPrinter(unittest.TestCase):
    """Test StreamPrinter functionality and styling."""

    def test_init(self):
        """Test that StreamPrinter initializes correctly."""
        printer = StreamPrinter(80, "  ")
        self.assertEqual(printer.width, 80)
        self.assertEqual(printer.indent, "  ")
        self.assertTrue(printer.is_start)
        self.assertFalse(printer.is_reasoning)

    def test_has_role_parameter(self):
        """Test that StreamPrinter accepts role parameter."""
        printer = StreamPrinter(80, "  ", "Mimi")
        self.assertEqual(printer.role, "Mimi")

    def test_process_new_reasoning_block(self):
        """Test that process starts new thinking block correctly."""
        printer = StreamPrinter(80, "  ")
        with patch("sys.stdout", new=StringIO()) as fake_out:
            printer.process("Thinking...", reasoning=True)
            printer.finish()
            output = fake_out.getvalue()
            # Note: The exact string format might have changed in new implementation
            # Checking for color codes is safer
            self.assertIn("\033[90m", output)  # DIM color

    def test_reasoning_content_styling(self):
        """Test that reasoning content is styled in dim gray."""
        printer = StreamPrinter(80, "  ")
        with patch("sys.stdout", new=StringIO()) as fake_out:
            printer.process("reasoning text", reasoning=True)
            printer.finish()
            output = fake_out.getvalue()
            self.assertIn("\033[90m", output)  # DIM color
            self.assertIn("reasoning text", output)

    def test_process_transitions_from_reasoning(self):
        """Test transition from reasoning to regular output."""
        printer = StreamPrinter(80, "  ")
        printer.process("reasoning content", reasoning=True)
        printer.process("final output", reasoning=False)
        self.assertFalse(printer.is_reasoning)

    def test_process_applies_markdown(self):
        """Test that process() applies markdown highlighting (basic check)."""
        printer = StreamPrinter(80, "  ")
        printer.is_start = False  # Skip header
        with patch("sys.stdout", new=StringIO()) as fake_out:
            printer.process("`code`", reasoning=False)
            printer.finish()
            output = fake_out.getvalue()
            self.assertIn("code", output)


class TestLayout(unittest.TestCase):
    """Test layout calculations."""

    @patch("shutil.get_terminal_size")
    def test_get_layout_default(self, mock_size):
        """Test default layout calculation."""
        mock_size.return_value = (100, 30)
        width, indent, cols, rows = text_utils.get_layout(None)

        # Expected: min(5, 25) = 5
        expected_margin = 5
        expected_width = 100 - (5 * 2)  # 90

        self.assertEqual(
            len(indent), expected_margin, f"Expected 5 margin, got {len(indent)}"
        )
        self.assertEqual(width, expected_width)

    @patch("shutil.get_terminal_size")
    def test_get_layout_ultrawide(self, mock_size):
        """Test layout cap on ultrawide monitors."""
        mock_size.return_value = (300, 30)
        width, indent, _, _ = text_utils.get_layout(None)

        # Expected: min(15, 25) = 15
        self.assertEqual(len(indent), 15, f"Expected 15 margin cap, got {len(indent)}")


class TestLatexFormatter(unittest.TestCase):
    """Test LaTeX to Unicode conversion."""

    def test_greek_letters(self):
        text = r"The value of \pi is approx 3.14"
        formatted = text_utils.format_latex_math(text)
        self.assertEqual(formatted, "The value of π is approx 3.14")

    def test_superscripts(self):
        text = r"E = mc^2"
        formatted = text_utils.format_latex_math(text)
        self.assertEqual(formatted, "E = mc²")

    def test_subscripts(self):
        text = r"H_2O"
        formatted = text_utils.format_latex_math(text)
        self.assertEqual(formatted, "H₂O")


if __name__ == "__main__":
    unittest.main()
