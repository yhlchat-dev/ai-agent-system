# -*- coding: utf-8 -*-
"""
Weather API Adapter: OpenWeatherMap + WeatherAPI.com
"""
from core.tools.adapters import BaseAPIAdapter

class WeatherAdapter(BaseAPIAdapter):
    """OpenWeatherMap Weather Adapter"""
    def call(self, city, **kwargs):
        api_key = self._decrypt(self.config.get('api_key'))
        if not api_key:
            return {"success": False, "result": None, "error": "API Key not configured"}
        
        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {'q': city, 'appid': api_key, 'units': 'metric', 'lang': 'en'}
        
        try:
            if not REQUESTS_AVAILABLE:
                return {"success": False, "result": None, "error": "requests library not installed"}
                
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            if resp.status_code == 200:
                weather = data['weather'][0]['description']
                temp = data['main']['temp']
                result = f"{city} weather: {weather}, temperature: {temp}C"
                return {"success": True, "result": result, "error": None}
            else:
                return {"success": False, "result": None, "error": data.get('message', 'Unknown error')}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}

class WeatherAPIAdapter(BaseAPIAdapter):
    """WeatherAPI.com Weather Adapter (more accurate for domestic weather)"""
    def call(self, city, **kwargs):
        api_key = self._decrypt(self.config.get('api_key'))
        if not api_key:
            return {"success": False, "result": None, "error": "API Key not configured"}
        
        url = "http://api.weatherapi.com/v1/current.json"
        params = {'key': api_key, 'q': city, 'lang': 'en'}
        
        try:
            if not REQUESTS_AVAILABLE:
                return {"success": False, "result": None, "error": "requests library not installed"}
                
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            if resp.status_code == 200:
                condition = data['current']['condition']['text']
                temp = data['current']['temp_c']
                result = f"{city} weather: {condition}, temperature: {temp}C"
                return {"success": True, "result": result, "error": None}
            else:
                error_msg = data.get('error', {}).get('message', 'Unknown error')
                return {"success": False, "result": None, "error": error_msg}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
