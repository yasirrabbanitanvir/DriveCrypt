import os
import sys
import json
import hashlib
import subprocess
import ctypes
import ctypes.wintypes as wt
import winreg

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".drive_locker_config.json")

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
comdlg32 = ctypes.windll.comdlg32

MB_OK           = 0x0
MB_YESNO        = 0x4
MB_ICONERROR    = 0x10
MB_ICONINFO     = 0x40
MB_ICONQUESTION = 0x20
IDYES = 6

APP_TITLE = "Drive Locker"

def msg(text, title=APP_TITLE, flags=MB_OK | MB_ICONINFO):
    return user32.MessageBoxW(0, str(text), str(title), flags)

def ask(text, title=APP_TITLE):
    return user32.MessageBoxW(0, str(text), str(title), MB_YESNO | MB_ICONQUESTION) == IDYES

def err(text, title=APP_TITLE):
    user32.MessageBoxW(0, str(text), str(title), MB_OK | MB_ICONERROR)


WS_VISIBLE      = 0x10000000
WS_CAPTION      = 0x00C00000
WS_SYSMENU      = 0x00080000
WS_TABSTOP      = 0x00010000
WS_CHILD        = 0x40000000
WS_BORDER       = 0x00800000
ES_PASSWORD     = 0x0020
ES_AUTOHSCROLL  = 0x0080
BS_PUSHBUTTON   = 0x00000000
SW_SHOW         = 5
HWND_DESKTOP    = 0
WM_COMMAND      = 0x0111
WM_DESTROY      = 0x0002
WM_CLOSE        = 0x0010
IDOK_BTN        = 1
IDCANCEL_BTN    = 2

_result_store = {}

WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_long, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

def _make_dialog(prompt, title, secret):
    result = [None]

    def wnd_proc(hwnd, msg_id, wparam, lparam):
        if msg_id == WM_COMMAND:
            ctrl_id = wparam & 0xFFFF
            if ctrl_id == IDOK_BTN:
                edit = user32.GetDlgItem(hwnd, 100)
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(edit, buf, 512)
                result[0] = buf.value
                user32.DestroyWindow(hwnd)
            elif ctrl_id == IDCANCEL_BTN:
                result[0] = None
                user32.DestroyWindow(hwnd)
        elif msg_id in (WM_DESTROY, WM_CLOSE):
            user32.PostQuitMessage(0)
        return user32.DefWindowProcW(hwnd, msg_id, wparam, lparam)

    wnd_proc_cb = WNDPROCTYPE(wnd_proc)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style",         wt.UINT),
            ("lpfnWndProc",   WNDPROCTYPE),
            ("cbClsExtra",    ctypes.c_int),
            ("cbWndExtra",    ctypes.c_int),
            ("hInstance",     wt.HINSTANCE),
            ("hIcon",         wt.HICON),
            ("hCursor",       wt.HANDLE),
            ("hbrBackground", wt.HBRUSH),
            ("lpszMenuName",  wt.LPCWSTR),
            ("lpszClassName", wt.LPCWSTR),
        ]

    class_name = "DLKInputDlg"
    hinstance  = kernel32.GetModuleHandleW(None)

    wc = WNDCLASSW()
    wc.lpfnWndProc   = wnd_proc_cb
    wc.hInstance     = hinstance
    wc.hbrBackground = ctypes.cast(6, wt.HBRUSH)
    wc.lpszClassName = class_name
    wc.hCursor       = user32.LoadCursorW(None, ctypes.cast(32512, wt.LPCWSTR))

    user32.RegisterClassW(ctypes.byref(wc))

    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    dw, dh = 380, 170
    dx = (sw - dw) // 2
    dy = (sh - dh) // 2

    hwnd = user32.CreateWindowExW(
        0, class_name, title,
        WS_VISIBLE | WS_CAPTION | WS_SYSMENU,
        dx, dy, dw, dh,
        HWND_DESKTOP, None, hinstance, None
    )

    user32.CreateWindowExW(
        0, "STATIC", prompt,
        WS_VISIBLE | WS_CHILD,
        10, 10, 350, 60,
        hwnd, None, hinstance, None
    )

    edit_style = WS_VISIBLE | WS_CHILD | WS_BORDER | WS_TABSTOP | ES_AUTOHSCROLL
    if secret:
        edit_style |= ES_PASSWORD

    edit = user32.CreateWindowExW(
        0, "EDIT", "",
        edit_style,
        10, 75, 350, 24,
        hwnd, ctypes.cast(100, wt.HMENU), hinstance, None
    )

    user32.CreateWindowExW(
        0, "BUTTON", "OK",
        WS_VISIBLE | WS_CHILD | WS_TABSTOP | BS_PUSHBUTTON,
        90, 110, 80, 26,
        hwnd, ctypes.cast(IDOK_BTN, wt.HMENU), hinstance, None
    )

    user32.CreateWindowExW(
        0, "BUTTON", "Cancel",
        WS_VISIBLE | WS_CHILD | WS_TABSTOP | BS_PUSHBUTTON,
        200, 110, 80, 26,
        hwnd, ctypes.cast(IDCANCEL_BTN, wt.HMENU), hinstance, None
    )

    user32.SetFocus(edit)
    user32.ShowWindow(hwnd, SW_SHOW)
    user32.UpdateWindow(hwnd)

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd",    wt.HWND),
            ("message", wt.UINT),
            ("wParam",  wt.WPARAM),
            ("lParam",  wt.LPARAM),
            ("time",    wt.DWORD),
            ("pt",      wt.POINT),
        ]

    msg_s = MSG()
    while user32.GetMessageW(ctypes.byref(msg_s), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg_s))
        user32.DispatchMessageW(ctypes.byref(msg_s))

    try:
        user32.UnregisterClassW(class_name, hinstance)
    except Exception:
        pass

    return result[0]


def input_password(prompt, title=APP_TITLE):
    return _make_dialog(prompt, title, secret=True)

def input_text(prompt, title=APP_TITLE):
    return _make_dialog(prompt, title, secret=False)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"password_hash": None, "locked_drives": []}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def elevate():
    script = os.path.abspath(sys.argv[0])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}"', None, 1)
    sys.exit(0)

def get_drives():
    drives = []
    try:
        bitmask = kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                drives.append(chr(65 + i))
    except Exception:
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            if os.path.exists(f"{letter}:\\"):
                drives.append(letter)
    return drives

EXPLORER_KEY = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"

def _bit(letter):
    return 1 << (ord(letter.upper()) - ord('A'))

def _set_reg(letter, lock):
    bit = _bit(letter)
    for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
        try:
            key = winreg.CreateKeyEx(hive, EXPLORER_KEY, 0,
                                     winreg.KEY_READ | winreg.KEY_WRITE)
            for val in ["NoDrives", "NoViewOnDrive"]:
                try:
                    cur, _ = winreg.QueryValueEx(key, val)
                except FileNotFoundError:
                    cur = 0
                new = (cur | bit) if lock else (cur & ~bit)
                winreg.SetValueEx(key, val, 0, winreg.REG_DWORD, new)
            winreg.CloseKey(key)
        except Exception:
            pass

def restart_explorer():
    subprocess.Popen(
        'taskkill /f /im explorer.exe & start explorer.exe',
        shell=True, creationflags=0x08000000
    )

def setup_password():
    msg("First time setup!\nPlease set a password.", "Welcome — Drive Locker")
    while True:
        p1 = input_password("Enter new password:")
        if p1 is None:
            sys.exit(0)
        if len(p1) < 4:
            err("Password must be at least 4 characters.")
            continue
        p2 = input_password("Confirm new password:")
        if p2 is None:
            sys.exit(0)
        if p1 != p2:
            err("Passwords do not match! Please try again.")
            continue
        return hash_password(p1)

def verify_password(config):
    p = input_password("Enter password:")
    if p is None:
        return False
    return hash_password(p) == config["password_hash"]

def drive_status_text(drives, locked):
    lines = ["Drive List:\n"]
    for d in drives:
        status = "[LOCKED]" if d in locked else "[Unlocked]"
        sys_tag = " [System]" if d == "C" else ""
        lines.append(f"  {d}:\\   {status}{sys_tag}")
    lines.append("\n")
    return "\n".join(lines)

def lock_menu(config):
    drives   = get_drives()
    locked   = config["locked_drives"]
    unlocked = [d for d in drives if d not in locked and d != "C"]

    if not unlocked:
        msg("No drives available to lock.")
        return

    options = "\n".join(f"  {i+1}. {d}:\\" for i, d in enumerate(unlocked))
    choice_str = input_text(
        f"Which drive do you want to lock?\n\n{options}\n\nEnter the number (e.g. 1):",
        "Lock Drive"
    )
    if choice_str is None:
        return
    try:
        idx = int(choice_str.strip()) - 1
        if idx < 0 or idx >= len(unlocked):
            raise ValueError
    except ValueError:
        err("Invalid number entered.")
        return

    letter = unlocked[idx]
    if not ask(f"Lock drive {letter}:?\nExplorer will restart."):
        return

    _set_reg(letter, True)
    restart_explorer()

    if letter not in config["locked_drives"]:
        config["locked_drives"].append(letter)
    save_config(config)
    msg(f"{letter}: Drive is now locked.\nIt will no longer appear in Windows Explorer.")

def unlock_menu(config):
    locked = config["locked_drives"]
    if not locked:
        msg("No drives are currently locked.")
        return

    options = "\n".join(f"  {i+1}. {d}:\\" for i, d in enumerate(locked))
    choice_str = input_text(
        f"Which drive do you want to unlock?\n\n{options}\n\nEnter the number:",
        "Unlock Drive"
    )
    if choice_str is None:
        return
    try:
        idx = int(choice_str.strip()) - 1
        if idx < 0 or idx >= len(locked):
            raise ValueError
    except ValueError:
        err("Invalid number entered.")
        return

    letter = locked[idx]

    p = input_password(f"Enter password to unlock {letter}:")
    if p is None:
        return
    if hash_password(p) != config["password_hash"]:
        err("Wrong password! Unlock failed.")
        return

    _set_reg(letter, False)
    restart_explorer()

    config["locked_drives"].remove(letter)
    save_config(config)
    msg(f"{letter}: Drive is now unlocked.")

def change_password(config):
    p_old = input_password("Enter your current password:")
    if p_old is None:
        return
    if hash_password(p_old) != config["password_hash"]:
        err("Wrong password!")
        return
    while True:
        p1 = input_password("Enter new password:")
        if p1 is None:
            return
        if len(p1) < 4:
            err("Password must be at least 4 characters.")
            continue
        p2 = input_password("Confirm new password:")
        if p2 is None:
            return
        if p1 != p2:
            err("Passwords do not match!")
            continue
        config["password_hash"] = hash_password(p1)
        save_config(config)
        msg("Password changed successfully.")
        return

def main_menu(config):
    while True:
        drives = get_drives()
        locked = config["locked_drives"]
        status = drive_status_text(drives, locked)

        admin_status = "Administrator Mode" if is_admin() else "Not running as Admin!"

        menu_text = (
            f"{status}"
            f"[{admin_status}]\n\n"
            "Menu:\n"
            "  1.  Lock a Drive\n"
            "  2.  Unlock a Drive\n"
            "  3.  Change Password\n"
            "  4.  Exit\n\n"
            "Enter a number:"
        )

        choice = input_text(menu_text, "Drive Locker  —  alpha version by Yasir")
        if choice is None or choice.strip() == "4":
            break
        elif choice.strip() == "1":
            lock_menu(config)
        elif choice.strip() == "2":
            unlock_menu(config)
        elif choice.strip() == "3":
            change_password(config)
        else:
            err("Invalid choice. Please enter 1, 2, 3 or 4.")


if __name__ == "__main__":
    if not is_admin():
        elevate()

    config = load_config()

    if config["password_hash"] is None:
        config["password_hash"] = setup_password()
        save_config(config)

    main_menu(config)
    msg("Exiting Drive Locker. Stay safe!", "Goodbye!")
