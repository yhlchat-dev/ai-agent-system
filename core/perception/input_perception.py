#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Input Perception Module

Features:
1. Keyboard state perception
2. Mouse position perception
3. Mouse click perception
4. Keyboard input simulation
"""
import time
from typing import Dict, Any, Tuple, Optional


class InputPerception:
    """Input Perception: Keyboard and mouse status monitoring"""
    
    def __init__(self):
        """Initialize input perception"""
        self.last_mouse_pos = (0, 0)
        self.last_key_state = {}
        self.click_history = []
        self.key_history = []
        
        try:
            import pyautogui
            self.pyautogui = pyautogui
            self.available = True
            print("[InputPerception] pyautogui available, full input perception functionality")
        except ImportError:
            self.pyautogui = None
            self.available = False
            print("[InputPerception] pyautogui unavailable, input perception functionality limited")
    
    def get_mouse_pos(self) -> Tuple[int, int]:
        """
        Get mouse position
        
        :return: (x, y) Mouse coordinates
        """
        if not self.available:
            return self.last_mouse_pos
        
        try:
            pos = self.pyautogui.position()
            self.last_mouse_pos = pos
            return pos
        except Exception as e:
            print(f"[InputPerception] Failed to get mouse position: {e}")
            return self.last_mouse_pos
    
    def get_key_state(self) -> Dict[str, bool]:
        """
        Get keyboard state (simplified version)
        
        :return: Keyboard state dictionary
        """
        return self.last_key_state
    
    def simulate_click(self, x: int, y: int, button: str = 'left') -> bool:
        """
        Simulate mouse click
        
        :param x: X coordinate
        :param y: Y coordinate
        :param button: Mouse button ('left', 'right', 'middle')
        :return: Whether successful
        """
        if not self.available:
            print("[InputPerception] pyautogui unavailable, cannot simulate click")
            return False
        
        try:
            self.pyautogui.click(x, y, button=button)
            self.click_history.append({
                "time": time.time(),
                "pos": (x, y),
                "button": button
            })
            return True
        except Exception as e:
            print(f"[InputPerception] Simulated click failed: {e}")
            return False
    
    def simulate_key_press(self, key: str) -> bool:
        """
        Simulate keyboard key press
        
        :param key: Key name
        :return: Whether successful
        """
        if not self.available:
            print("[InputPerception] pyautogui unavailable, cannot simulate key press")
            return False
        
        try:
            self.pyautogui.press(key)
            self.key_history.append({
                "time": time.time(),
                "key": key
            })
            return True
        except Exception as e:
            print(f"[InputPerception] Simulated key press failed: {e}")
            return False
    
    def simulate_type(self, text: str, interval: float = 0.1) -> bool:
        """
        Simulate keyboard text input
        
        :param text: Text to input
        :param interval: Input interval (seconds)
        :return: Whether successful
        """
        if not self.available:
            print("[InputPerception] pyautogui unavailable, cannot simulate input")
            return False
        
        try:
            self.pyautogui.typewrite(text, interval=interval)
            return True
        except Exception as e:
            print(f"[InputPerception] Simulated input failed: {e}")
            return False
    
    def move_mouse(self, x: int, y: int, duration: float = 0.5) -> bool:
        """
        Move mouse to specified position
        
        :param x: X coordinate
        :param y: Y coordinate
        :param duration: Movement time (seconds)
        :return: Whether successful
        """
        if not self.available:
            print("[InputPerception] pyautogui unavailable, cannot move mouse")
            return False
        
        try:
            self.pyautogui.moveTo(x, y, duration=duration)
            self.last_mouse_pos = (x, y)
            return True
        except Exception as e:
            print(f"[InputPerception] Mouse movement failed: {e}")
            return False
    
    def get_click_history(self, limit: int = 10) -> list:
        """
        Get click history
        
        :param limit: Return count limit
        :return: Click history list
        """
        return self.click_history[-limit:]
    
    def get_key_history(self, limit: int = 10) -> list:
        """
        Get key press history
        
        :param limit: Return count limit
        :return: Key press history list
        """
        return self.key_history[-limit:]
    
    def clear_history(self):
        """Clear history"""
        self.click_history.clear()
        self.key_history.clear()
