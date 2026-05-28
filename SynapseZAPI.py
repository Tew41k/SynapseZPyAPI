#--------------------------------------------------------------------#
#            SYNAPSE Z API Python Edition BY: TEW41k                 #
#--------------------------------------------------------------------#

import os
import random
import string
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional
import ctypes
from ctypes import wintypes
import requests
import psutil

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ        = 0x80000000
GENERIC_WRITE       = 0x40000000
OPEN_EXISTING       = 3
FILE_SHARE_READ     = 0x00000001
FILE_SHARE_WRITE    = 0x00000002
PIPE_TYPE_MESSAGE   = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
INFINITE            = 0xFFFFFFFF


def _create_file(pipe_name: str, access: int) -> ctypes.c_void_p:
    handle = kernel32.CreateFileW(
        pipe_name,
        access,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    return handle


def _wait_named_pipe(name: str, timeout_ms: int) -> bool:
    return bool(kernel32.WaitNamedPipeW(name, timeout_ms))


def _set_pipe_message_mode(handle) -> None:
    mode = ctypes.c_uint32(PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE)
    kernel32.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None)


def _write_pipe(handle, data: bytes) -> bool:
    written = ctypes.c_uint32(0)
    return bool(
        kernel32.WriteFile(handle, data, len(data), ctypes.byref(written), None)
    )


def _read_pipe(handle, size: int) -> Optional[bytes]:
    buf = ctypes.create_string_buffer(size) if size > 0 else ctypes.create_string_buffer(1)
    read = ctypes.c_uint32(0)
    ok = kernel32.ReadFile(handle, buf, size, ctypes.byref(read), None)
    if not ok and size > 0:
        return None
    return bytes(buf[: read.value])


def _peek_pipe(handle) -> int:
    """Returns total bytes available in the pipe."""
    total = ctypes.c_uint32(0)
    kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(total), None)
    return total.value


def _close_handle(handle) -> None:
    kernel32.CloseHandle(handle)


class SynapseZAPI:
    _latest_error: str = ""
    @classmethod
    def get_latest_error_message(cls) -> str:
        """Returns the latest error message from any action."""
        return cls._latest_error

    @classmethod
    def execute(cls, script: str, pid: int = 0) -> int:
        """
        Return values:
            0  – Execution successful
            1  – Bin folder not found
            2  – Scheduler folder not found
            3  – No access to write file
        """
        main_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Synapse Z")
        bin_path = os.path.join(main_path, "bin")

        if not os.path.isdir(bin_path):
            cls._latest_error = "Bin Folder not found"
            return 1

        scheduler_path = os.path.join(bin_path, "scheduler")

        if not os.path.isdir(scheduler_path):
            cls._latest_error = "Scheduler Folder not found"
            return 2

        random_name = cls._random_string(10) + ".lua"
        file_path = (
            os.path.join(scheduler_path, random_name)
            if pid == 0
            else os.path.join(scheduler_path, f"PID{pid}_{random_name}")
        )

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(script + "@@FileFullyWritten@@")
        except Exception as exc:
            cls._latest_error = str(exc)
            return 3

        return 0

    @classmethod
    def get_expire_date(cls) -> Optional[datetime]:
        """
        Return values:
            datetime  – Expiry date (UTC)
            None      – Could not find Account Key / API Error
        """
        acc_key = cls.get_account_key()
        if not acc_key:
            cls._latest_error = "Could not find Account Key"
            return None

        try:
            resp = requests.get(
                "https://z-api.synapse.do/info",
                headers={"User-Agent": "SYNZ-SERVICE", "key": acc_key},
                timeout=10,
            )
        except Exception as exc:
            cls._latest_error = str(exc)
            return None

        if resp.status_code != 418:
            cls._latest_error = f"API Error: {resp.status_code}"
            return None

        expire_ts = int(resp.text.strip())
        return datetime.fromtimestamp(expire_ts, tz=timezone.utc)

    @classmethod
    def redeem(cls, license_key: str) -> int:
        """
        Return values:
             0  – Successful
            -1  – Could not find Account Key
            -2  – API Error
            -3  – Invalid License
        """
        acc_key = cls.get_account_key()
        if not acc_key:
            cls._latest_error = "Could not find Account Key"
            return -1

        try:
            resp = requests.post(
                "https://z-api.synapse.do/redeem",
                headers={"User-Agent": "SYNZ-SERVICE", "key": acc_key, "license": license_key},
                timeout=10,
            )
        except Exception as exc:
            cls._latest_error = str(exc)
            return -2

        if resp.status_code != 418:
            if resp.status_code == 403:
                cls._latest_error = "Invalid License"
                return -3
            cls._latest_error = f"API Error: {resp.status_code}"
            return -2

        if resp.text.startswith("Added"):
            return 0

        cls._latest_error = "Invalid License"
        return -3

    @classmethod
    def reset_hwid(cls) -> int:
        """
        Return values:
             0  – Successful
            -1  – Could not find Account Key
            -2  – API Error
            -3  – Cooldown
            -4  – Blacklisted
        """
        acc_key = cls.get_account_key()
        if not acc_key:
            cls._latest_error = "Could not find Account Key"
            return -1

        try:
            resp = requests.post(
                "https://z-api.synapse.do/resethwid",
                headers={"User-Agent": "SYNZ-SERVICE", "key": acc_key},
                timeout=10,
            )
        except Exception as exc:
            cls._latest_error = str(exc)
            return -2

        if resp.status_code == 418:
            return 0
        if resp.status_code == 429:
            cls._latest_error = "Cooldown"
            return -3
        if resp.status_code == 403:
            cls._latest_error = "Blacklisted"
            return -4

        cls._latest_error = f"API Error: {resp.status_code}"
        return -2

    @staticmethod
    def get_roblox_processes() -> List[psutil.Process]:
        """Return all running RobloxPlayerBeta processes."""
        return [p for p in psutil.process_iter(["name"]) if p.info["name"] == "RobloxPlayerBeta"]

    @classmethod
    def get_synz_roblox_instances(cls) -> List[psutil.Process]:
        """Return only the Roblox processes that are injected with SynZ."""
        return [p for p in cls.get_roblox_processes() if cls.is_synz(p.pid)]

    @staticmethod
    def is_synz(pid: int) -> bool:
        """Return True if the given PID belongs to a SynZ-injected Roblox instance."""
        try:
            proc = psutil.Process(pid)
            exe_path = proc.exe()

            with open(exe_path, "rb") as f:
                header = f.read(0x1000)

            return b".grh" in header
        except Exception as exc:
            print(f"Error checking process: {exc}")
            return False

    @classmethod
    def are_all_instances_synz(cls) -> bool:
        """Return True if every running Roblox instance is a SynZ instance."""
        processes = cls.get_roblox_processes()
        if not processes:
            return False
        return len(cls.get_synz_roblox_instances()) == len(processes)

    @staticmethod
    def get_account_key() -> str:
        """Read and return the local SynZ account key, or '' if absent."""
        path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "auth_v2.syn")
        if not os.path.isfile(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()


    @staticmethod
    def _random_string(length: int) -> str:
        chars = string.ascii_uppercase + string.digits
        return "".join(random.choice(chars) for _ in range(length))


class SynapseZAPI2:
    _timer: Optional[threading.Timer] = None
    _sessions: Dict[int, "SynapseZAPI2.SynapseSession"] = {}
    _sessions_lock = threading.Lock()

    _session_added_callbacks:   List[Callable] = []
    _session_removed_callbacks: List[Callable] = []
    _session_output_callbacks:  List[Callable] = []


    @classmethod
    def on_session_added(cls, cb: Callable) -> None:
        cls._session_added_callbacks.append(cb)

    @classmethod
    def on_session_removed(cls, cb: Callable) -> None:
        cls._session_removed_callbacks.append(cb)

    @classmethod
    def on_session_output(cls, cb: Callable) -> None:
        cls._session_output_callbacks.append(cb)

    @classmethod
    def _fire_session_added(cls, session: "SynapseZAPI2.SynapseSession") -> None:
        for cb in cls._session_added_callbacks:
            cb(session)

    @classmethod
    def _fire_session_removed(cls, session: "SynapseZAPI2.SynapseSession") -> None:
        for cb in cls._session_removed_callbacks:
            cb(session)

    @classmethod
    def _fire_session_output(cls, session: "SynapseZAPI2.SynapseSession", type_: int, output: str) -> None:
        for cb in cls._session_output_callbacks:
            cb(session, type_, output)



    @classmethod
    def start_instances_timer(cls) -> None:
        """Start the 2-second polling timer that detects new SynZ Roblox instances."""
        if cls._timer is not None:
            return
        cls._schedule_tick()

    @classmethod
    def stop_instances_timer(cls) -> None:
        """Stop the instances polling timer."""
        if cls._timer is not None:
            cls._timer.cancel()
            cls._timer = None

    @classmethod
    def _schedule_tick(cls) -> None:
        cls._timer = threading.Timer(2.0, cls._instances_timer_tick)
        cls._timer.daemon = True
        cls._timer.start()

    @classmethod
    def _instances_timer_tick(cls) -> None:
        try:
            processes = SynapseZAPI.get_roblox_processes()
            for proc in processes:
                pid = proc.pid
                with cls._sessions_lock:
                    if pid in cls._sessions:
                        continue

                if not SynapseZAPI.is_synz(pid):
                    continue

                session = cls.SynapseSession()
                with cls._sessions_lock:
                    cls._sessions[pid] = session

                if session.init(pid):
                    cls._fire_session_added(session)
                else:
                    with cls._sessions_lock:
                        cls._sessions.pop(pid, None)
        finally:
            if cls._timer is not None:
                cls._schedule_tick()

    @classmethod
    def execute(cls, source: str, pid: int = 0) -> None:
        with cls._sessions_lock:
            snapshot = dict(cls._sessions)

        if pid == 0:
            for session in snapshot.values():
                session.execute(source)
        else:
            session = snapshot.get(pid)
            if session:
                session.execute(source)

    @classmethod
    def get_instances(cls) -> Dict[int, "SynapseZAPI2.SynapseSession"]:
        with cls._sessions_lock:
            return dict(cls._sessions)

    @classmethod
    def _remove_session(cls, pid: int) -> None:
        with cls._sessions_lock:
            session = cls._sessions.pop(pid, None)
        if session:
            cls._fire_session_removed(session)


    class SynapseSession:
        def __init__(self) -> None:
            self.pid: int = 0
            self.pipe_name: str = ""

            self._pending_commands: List[str] = []
            self._on_message_callbacks: List[Callable[[str, str, int], None]] = []
            self._lock = threading.Lock()

            # Register built-in console output handler
            self.add_on_message_callback(self._console_output)


        def queue_command(self, command: str) -> None:
            with self._lock:
                self._pending_commands.append(command)

        def execute(self, source: str) -> None:
            self.queue_command(f"execute {source}")

        def reload_settings_in_internal_ui(self) -> None:
            self.queue_command("reload_settings")

        def add_on_message_callback(self, callback: Callable[[str, str, int], None]) -> None:
            with self._lock:
                self._on_message_callbacks.append(callback)

        def init(self, pid: int) -> bool:
            self.pid = pid
            initial_pipe = f"\\\\.\\pipe\\synz-{pid}"

            if not _wait_named_pipe(initial_pipe, 10):
                return False

            handle = _create_file(initial_pipe, GENERIC_READ | GENERIC_WRITE)
            if handle == INVALID_HANDLE_VALUE:
                return False

            _set_pipe_message_mode(handle)

            _write_pipe(handle, b"new")
            _read_pipe(handle, 0)

            size = _peek_pipe(handle)
            if size > 0:
                data = _read_pipe(handle, size)
                self.pipe_name = data.decode("utf-8")

                t = threading.Thread(target=self._session_loop, daemon=True)
                t.start()

                _close_handle(handle)
                return True

            _close_handle(handle)
            return False


        def _console_output(self, command: str, data: str, i: int) -> None:
            if command != "read":
                return

            parts = data.split(" ", 1)
            if len(parts) < 2:
                return
            sub_command, sub_data = parts

            if sub_command == "output":
                parts2 = sub_data.split(" ", 1)
                if len(parts2) < 2:
                    return
                type_ = int(parts2[0])
                output = parts2[1]
                SynapseZAPI2._fire_session_output(self, type_, output)
            elif sub_command == "error":
                SynapseZAPI2._fire_session_output(self, 3, sub_data)

        def _session_loop(self) -> None:
            try:
                while True:
                    if not _wait_named_pipe(self.pipe_name, INFINITE):
                        continue

                    handle = _create_file(self.pipe_name, GENERIC_READ | GENERIC_WRITE)
                    if handle == INVALID_HANDLE_VALUE:
                        continue

                    _set_pipe_message_mode(handle)

                    try:
                        while True:
                            with self._lock:
                                command_queue = list(self._pending_commands)
                                self._pending_commands.clear()

                            command_queue.append("read")

                            count_bytes = str(len(command_queue)).encode("utf-8")
                            if not _write_pipe(handle, count_bytes):
                                break

                            for idx, cmd in enumerate(command_queue):
                                cmd_bytes = cmd.encode("utf-8")
                                _write_pipe(handle, cmd_bytes)
                                _read_pipe(handle, 0)  # ack

                                size = _peek_pipe(handle)
                                if size > 0:
                                    raw = _read_pipe(handle, size)
                                    temp_str = raw.decode("utf-8")
                                    try:
                                        num_responses = int(temp_str)
                                    except ValueError:
                                        num_responses = 0

                                    for j in range(num_responses):
                                        _read_pipe(handle, 0)  # ack
                                        data_size = _peek_pipe(handle)
                                        if data_size == 0:
                                            break

                                        data_buf = _read_pipe(handle, data_size)
                                        data_str = data_buf.decode("utf-8")

                                        with self._lock:
                                            callbacks = list(self._on_message_callbacks)

                                        for cb in callbacks:
                                            cb(cmd, data_str, j)

 #------BY TEW41K-------

                            time.sleep(0.005)
 #BY TEW41K
                    except Exception:
                        pass
                    finally:
                        _close_handle(handle)

            finally:
                SynapseZAPI2._remove_session(self.pid)

#--------------------------------------------------------------------#
#            SYNAPSE Z API Python Edition BY: TEW41k                 #
#--------------------------------------------------------------------#