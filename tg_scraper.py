import os
import re
import json
import requests
from loguru import logger
from dotenv import load_dotenv
from bs4 import BeautifulSoup


class TgScraper:
    load_dotenv()
    SITE_URL = os.environ.get("SITE_URL")
    TOKEN = os.environ.get("TOKEN")

    def __init__(self) -> None:
        self._session = requests.Session()
        self.users = []

    def __login(self):
        payload = {"email_or_login": self.TOKEN}
        self._session.post(self.SITE_URL + "/auth/email/", data=payload)

        main = self._session.get(self.SITE_URL)
        if main.status_code == 200:
            soup = BeautifulSoup(main.text, "html.parser")
            if soup.body.findAll(text=re.compile("Главная")):
                logger.info("logged in successfully")
                return True
            else:
                logger.info("failed to log in")
                return False

    def __find_max_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        max_page = 0
        for a in soup.find_all("a", class_="paginator-page"):
            try:
                number = int(a.get_text(strip=True))
                if number > max_page:
                    max_page = number
            except:
                pass

        return max_page

    def __find_tg(self, text):
        at = re.compile(r"@([^\s:]+)")
        link = re.compile(r"t.me\/([^\s:]+)")
        return at.findall(text) + link.findall(text)

    def __tg_from_intro(self, user):
        s = self._session.get(self.SITE_URL + f"/user/{user}")
        soup = BeautifulSoup(s.text, "html.parser")
        intro = soup.find("div", class_="profile-intro-text")
        if intro:
            text = intro.get_text()
            return self.__find_tg(text)
        else:
            return []

    def __check_tg(self, tgs):
        channels = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"
        }
        for tg in tgs:
            r = requests.get(f"https://t.me/s/{tg}", headers=headers)
            soup = BeautifulSoup(r.text, "html.parser")
            button = soup.body.find(text="Send Message")
            if not button:
                channels.append(tg)

        return channels

    def __get_users_from_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        for u in soup.find_all("article", class_="profile-card"):
            try:
                user = dict()

                user["fullname"] = u.find(
                    "span", class_="profile-user-fullname"
                ).get_text()
                user["nickname"] = (
                    u.find("span", class_="profile-user-nickname")
                    .get_text()
                    .replace("@", "")
                )
                logger.debug(f"user {user['nickname']}")
                user["bio"] = ""
                user["tg"] = ""
                bio = u.find("div", class_="profile-user-bio")
                if bio:
                    user["bio"] = bio.get_text()
                    tg = self.__find_tg(user["bio"])
                    if tg:
                        user["tg"] = tg

                tg_from_intro = self.__tg_from_intro(user["nickname"])
                if tg_from_intro:
                    user["tg"] += tg_from_intro
                    if len(user["tg"]) >= 2:
                        user["tg"] = list(set(user["tg"]))

                user["channels"] = ""
                if user["tg"]:
                    channels = self.__check_tg(user["tg"])
                    if channels:
                        user["channels"] = channels

                self.users.append(user)
            except Exception as e:
                logger.error(e)

    def get_users(self):
        if self.__login():
            people = self._session.get(self.SITE_URL + "/people/")
            max_page = self.__find_max_page(people.text)
            for num_page in range(1, max_page + 1):
                logger.debug(f"page {num_page} from {max_page}")
                page = self._session.get(self.SITE_URL + f"/people/?page={num_page}")
                self.__get_users_from_page(page.text)

        return self.users


if __name__ == "__main__":
    tg = TgScraper()
    users = tg.get_users()
    if users:
        with open("users.json", "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False)
