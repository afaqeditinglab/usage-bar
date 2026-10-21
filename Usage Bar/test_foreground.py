"""Offline foreground-hook regressions; no account access or real desktop inputs."""
import unittest
from unittest.mock import Mock, patch
import usage_bar as bar


class ForegroundTests(unittest.TestCase):
    def setUp(self):
        self.native = patch.object(bar, "u").start()
        self.addCleanup(patch.stopall)
        self.native.SetWinEventHook.side_effect = [101, 102]
        self.native.GetForegroundWindow.return_value = 10
        self.native.IsIconic.return_value = False
        self.windows = {10: {"native": 11}, 20: {"native": 21}}
        self.guard = bar.ForegroundVisibility(self.windows)
        self.addCleanup(self.guard.close)

    def event(self, event=3, hwnd=10):
        self.guard.changed(None, event, hwnd, 0, 0, 0, 0)

    def test_focus_change_hides_without_timer(self):
        self.native.GetForegroundWindow.return_value = 30
        self.event()
        self.native.ShowWindow.assert_any_call(11, 0)
        self.native.ShowWindow.assert_any_call(21, 0)
        self.assertFalse(self.guard.allows(10))

    def test_invisible_null_and_overlay_foreground_fail_closed(self):
        for hwnd in (None, 0, 30, 99):
            self.native.GetForegroundWindow.return_value = hwnd
            self.assertFalse(self.guard.allows(10))

    def test_stale_event_uses_current_focus_and_multiple_owners(self):
        self.native.GetForegroundWindow.return_value = 20
        self.event(hwnd=10)
        self.native.ShowWindow.assert_called_once_with(11, 0)

    def test_alt_tab_switcher_blocks_reshow_until_end(self):
        self.event(0x14)
        self.assertFalse(self.guard.allows(10))
        self.event(3)
        self.assertFalse(self.guard.allows(10))
        self.event(0x15)
        self.assertTrue(self.guard.allows(10))
        self.native.IsIconic.return_value = True
        self.assertFalse(self.guard.allows(10))

    def test_hook_lifetime_and_partial_failure(self):
        self.native.GetMessageW.return_value = 0
        self.guard.start()
        self.guard.thread.join()
        self.assertEqual(self.native.UnhookWinEvent.call_count, 2)
        self.guard.close()
        self.assertEqual(self.native.UnhookWinEvent.call_count, 2)
        self.native.SetWinEventHook.side_effect = [201, None]
        with self.assertRaises(OSError):
            bar.ForegroundVisibility({}).start()
        self.native.UnhookWinEvent.assert_called_with(201)

    def test_shortcut_hides_before_switch_without_consuming_input(self):
        key = bar.wintypes.DWORD(9)
        address = bar.ctypes.addressof(key)
        self.native.GetAsyncKeyState.return_value = 0x8000
        self.guard.key_changed(0, 0x100, address)
        self.assertFalse(self.guard.allows(10))
        self.native.ShowWindow.assert_any_call(11, 0)
        self.native.CallNextHookEx.assert_called_once_with(None, 0, 0x100, address)
        self.guard.key_changed(0, 0x101, address)
        self.assertTrue(self.guard.allows(10))
        self.native.GetAsyncKeyState.return_value = 0
        self.guard.key_changed(0, 0x100, address)
        self.assertTrue(self.guard.allows(10))


if __name__ == "__main__":
    unittest.main()
