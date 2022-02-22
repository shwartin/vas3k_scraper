import os
import requests
from loguru import logger
from dotenv import load_dotenv

load_dotenv()
SITE_URL = os.environ.get("SITE_URL")
TOKEN = os.environ.get("TOKEN")

payload = {"email_or_login": TOKEN}

with requests.session() as s:
    s.post(SITE_URL + "/auth/email/", data=payload)
    r = s.get(SITE_URL + "/people/")
    logger.debug(r.text)
