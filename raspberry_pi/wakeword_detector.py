#!/usr/bin/env python3
"""Porcupine wake-word detector wrapper.

Provides a PorcupineWakeDetector class that runs detection in a background
thread and calls a user-supplied callback on detection. It supports pause/
resume so caller can temporarily free the input device for recording.

Usage:
    def on_detect():
        print('wake')

    det = PorcupineWakeDetector(on_detect, device_index=0)
    det.start()
    ...
    det.pause()
    det.resume()
    det.stop()
"""
from typing import Callable, Optional
import threading
import time
import struct
import logging

try:
    import pvporcupine
except Exception:
    pvporcupine = None

logger = logging.getLogger("wakeword.detector")


class PorcupineWakeDetector:
    """Detect wake-word with pvporcupine in a background thread.

    Args:
        on_detect: callable invoked with no args when keyword is detected.
        keyword_path: optional path to .ppn keyword file.
        keyword_name: optional built-in keyword name.
        device_index: audio input device index to open with pyaudio.
        access_key: optional pvporcupine access key for cloud-enabled builds.
    """

    def __init__(
        self,
        on_detect: Callable[[], None],
        keyword_path: Optional[str] = None,
        keyword_name: Optional[str] = None,
        device_index: Optional[int] = None,
        access_key: Optional[str] = None,
    ):
        self.on_detect = on_detect
        self.keyword_path = "/home/pi/museum_client/raspberry_pi/hey-bro_en_raspberry-pi_v3_0_0.ppn"
        self.keyword_name = "hey bro"
        self.device_index = device_index
        self.access_key = "afWRrpT7g4LBTzLY5pGiVMCHXuYPMC9XpBuZsLkAaM/QZPWSrpRdAg=="

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._stream_closed_event = threading.Event()  # ✅ NEW: Track when stream is actually closed
        self._thread: Optional[threading.Thread] = None
        self._porcupine = None

    def start(self):
        if pvporcupine is None:
            raise RuntimeError("pvporcupine is not installed")

        try:
            if self.keyword_path:
                self._porcupine = pvporcupine.create(access_key=self.access_key ,keyword_paths=[self.keyword_path])
            else:
                # fallback to named keyword if provided
                if self.keyword_name:
                    kws = [self.keyword_name]
                else:
                    kws = ["hey_siri"]
                if self.access_key:
                    self._porcupine = pvporcupine.create(access_key=self.access_key, keywords=kws)
                else:
                    self._porcupine = pvporcupine.create(keywords=kws)
        except Exception as e:
            logger.error(f"Failed to create Porcupine instance: {e}")
            raise

        self._stop_event.clear()
        self._pause_event.clear()
        self._stream_closed_event.set()  # ✅ Initially no stream
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 1.0):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        # release porcupine
        try:
            if self._porcupine:
                self._porcupine.delete()
        except Exception:
            pass

    def pause(self):
        """Pause detection and release microphone"""
        logger.info("🔇 Pausing wake word detector...")
        self._pause_event.set()
        # Wait for stream to actually close (with timeout)
        if self._stream_closed_event.wait(timeout=2.0):
            logger.info("✅ Wake word detector paused - microphone released")
        else:
            logger.warning("⚠️ Timeout waiting for stream to close")

    def resume(self):
        """Resume detection"""
        logger.info("🔊 Resuming wake word detector...")
        self._stream_closed_event.clear()  # Will reopen stream
        self._pause_event.clear()

    def _run_loop(self):
        import pyaudio

        pa = pyaudio.PyAudio()
        frame_length = self._porcupine.frame_length
        sample_rate = self._porcupine.sample_rate

        stream = None
        try:
            while not self._stop_event.is_set():
                if self._pause_event.is_set():
                    if stream is not None:
                        try:
                            stream.stop_stream()
                            stream.close()
                            logger.info("🔇 Wake word stream CLOSED")  # ✅ Better logging
                        except Exception as e:
                            logger.error(f"Error closing stream: {e}")
                        stream = None
                        self._stream_closed_event.set()  # ✅ Signal that stream is closed

                    while self._pause_event.is_set() and not self._stop_event.is_set():
                        time.sleep(0.05)
                    continue

                if stream is None:
                    try:
                        self._stream_closed_event.clear()  # ✅ About to open stream
                        stream = pa.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=sample_rate,
                            input=True,
                            frames_per_buffer=frame_length,
                            input_device_index=self.device_index,
                        )
                        logger.info("🔊 Wake word stream OPENED")  # ✅ Better logging
                    except Exception as e:
                        logger.error(f"Porcupine failed to open audio stream: {e}")
                        self._stream_closed_event.set()
                        time.sleep(0.2)
                        continue

                try:
                    data = stream.read(frame_length, exception_on_overflow=False)
                except Exception as e:
                    logger.error(f"Porcupine read error: {e}")
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                    stream = None
                    self._stream_closed_event.set()
                    time.sleep(0.1)
                    continue

                try:
                    pcm = struct.unpack_from("h" * frame_length, data)
                except Exception:
                    continue

                try:
                    result = self._porcupine.process(pcm)
                except Exception:
                    result = -1

                if result >= 0:
                    try:
                        self.on_detect()
                    except Exception:
                        logger.exception("on_detect callback raised")
                    # small sleep to avoid double-detection
                    time.sleep(0.3)

        except Exception as e:
            logger.error(f"Porcupine audio loop error: {e}")
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                    logger.info("🔇 Wake word stream closed (cleanup)")
                except Exception:
                    pass
                self._stream_closed_event.set()
            try:
                pa.terminate()
            except Exception:
                pass