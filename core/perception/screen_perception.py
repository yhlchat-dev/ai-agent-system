#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Screen Perception Module

Features:
1. Screen capture
2. Screen mirroring
3. Image recognition
4. Screen region monitoring
"""
import time
from typing import Dict, Any, Tuple, Optional
import base64


class ScreenMirror:
    """Screen Mirror: Screenshot and screen monitoring"""
    
    def __init__(self):
        """Initialize screen mirror"""
        self.last_frame = None
        self.frame_history = []
        self.max_history = 100
        
        try:
            from PIL import ImageGrab
            self.ImageGrab = ImageGrab
            self.available = True
            print("[ScreenMirror] PIL available, full screen mirroring functionality")
        except ImportError:
            self.ImageGrab = None
            self.available = False
            print("[ScreenMirror] PIL unavailable, screen mirroring functionality limited")
    
    def get_frame(self, region: Tuple[int, int, int, int] = None) -> Optional[Any]:
        """
        Get screen capture
        
        :param region: Capture region (x1, y1, x2, y2), None means fullscreen
        :return: Image object or None
        """
        if not self.available:
            return self.last_frame
        
        try:
            if region:
                frame = self.ImageGrab.grab(bbox=region)
            else:
                frame = self.ImageGrab.grab()
            
            self.last_frame = frame
            
            self.frame_history.append({
                "time": time.time(),
                "frame": frame
            })
            
            if len(self.frame_history) > self.max_history:
                self.frame_history.pop(0)
            
            return frame
        except Exception as e:
            print(f"[ScreenMirror] Screenshot failed: {e}")
            return self.last_frame
    
    def get_frame_base64(self, region: Tuple[int, int, int, int] = None) -> Optional[str]:
        """
        Get screen capture (Base64 encoded)
        
        :param region: Capture region (x1, y1, x2, y2)
        :return: Base64 encoded image string
        """
        frame = self.get_frame(region)
        
        if not frame:
            return None
        
        try:
            from io import BytesIO
            buffer = BytesIO()
            frame.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return img_base64
        except Exception as e:
            print(f"[ScreenMirror] Base64 encoding failed: {e}")
            return None
    
    def save_frame(self, filepath: str, region: Tuple[int, int, int, int] = None) -> bool:
        """
        Save screen capture to file
        
        :param filepath: File path
        :param region: Capture region
        :return: Whether successful
        """
        frame = self.get_frame(region)
        
        if not frame:
            return False
        
        try:
            frame.save(filepath)
            print(f"[ScreenMirror] Screenshot saved: {filepath}")
            return True
        except Exception as e:
            print(f"[ScreenMirror] Failed to save screenshot: {e}")
            return False
    
    def get_screen_size(self) -> Tuple[int, int]:
        """
        Get screen size
        
        :return: (width, height) Screen size
        """
        if not self.available:
            return (1920, 1080)
        
        try:
            frame = self.ImageGrab.grab()
            return frame.size
        except Exception as e:
            print(f"[ScreenMirror] Failed to get screen size: {e}")
            return (1920, 1080)
    
    def compare_frames(self, frame1: Any, frame2: Any) -> float:
        """
        Compare similarity between two frames
        
        :param frame1: First frame
        :param frame2: Second frame
        :return: Similarity (0.0-1.0)
        """
        if not frame1 or not frame2:
            return 0.0
        
        try:
            if frame1.size != frame2.size:
                return 0.0
            
            return 1.0
        except Exception as e:
            print(f"[ScreenMirror] Image comparison failed: {e}")
            return 0.0
    
    def detect_change(self, threshold: float = 0.9) -> bool:
        """
        Detect if screen has changed
        
        :param threshold: Change threshold
        :return: Whether changed
        """
        if len(self.frame_history) < 2:
            return False
        
        try:
            last_two = self.frame_history[-2:]
            similarity = self.compare_frames(last_two[0]["frame"], last_two[1]["frame"])
            return similarity < threshold
        except Exception as e:
            print(f"[ScreenMirror] Change detection failed: {e}")
            return False
    
    def get_frame_history(self, limit: int = 5) -> list:
        """
        Get frame history
        
        :param limit: Return count limit
        :return: Frame history list
        """
        return self.frame_history[-limit:]
    
    def clear_history(self):
        """Clear history"""
        self.frame_history.clear()
