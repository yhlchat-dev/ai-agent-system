# -*- coding: utf-8 -*-
"""
Email Sending Adapter
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.tools.adapters import BaseAPIAdapter

class EmailAdapter(BaseAPIAdapter):
    """Email Sending Adapter"""
    def call(self, to_addr, subject, body, **kwargs):
        smtp_server = self.config.get('smtp_server')
        smtp_port = self.config.get('smtp_port', 587)
        username = self._decrypt(self.config.get('username'))
        password = self._decrypt(self.config.get('password'))
        
        if not all([smtp_server, username, password]):
            return {"success": False, "result": None, "error": "Email configuration incomplete"}
        
        msg = MIMEMultipart()
        msg['From'] = username
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
            server.quit()
            return {"success": True, "result": "Email sent successfully", "error": None}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
