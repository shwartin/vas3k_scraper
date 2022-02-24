import os
import re
import json
import requests
from loguru import logger
from dotenv import load_dotenv
from bs4 import BeautifulSoup


class TgScraper:
    """Scraping users from vas3k.club engine, find telegram links in bio and info and find telegram channels.

    SITE_URL and TOKEN determine in .env file.
    """

    load_dotenv()
    SITE_URL = os.environ.get("SITE_URL")
    TOKEN = os.environ.get("TOKEN")

    def __init__(self) -> None:
        self._session = requests.Session()
        self._filename = "users.json"
        self._file = self.__open_file(self._filename)
        self.users = []

    def __del__(self):
        self._file.seek(self._file.tell() - 2, os.SEEK_SET)
        self._file.truncate()
        self._file.write("\n]")
        self._file.close()

    def __open_file(self, filename):
        if os.path.exists(filename):
            os.remove(filename)
            logger.debug(f"{filename} file removed")
        f = open("users.json", "a", encoding="utf-8")
        f.write("[\n")
        return f

    def __to_file(self, user):
        """Write user info to file

        Args:
            user (dict): users data
        """
        json.dump(user, self._file, ensure_ascii=False)
        self._file.write(",\n")

    def __login(self):
        """Login method.

        Returns:
            bool: True if logged in successfully, False if not
        """
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
        """Find max pagination page number.

        Args:
            html (str): html page with pagination

        Returns:
            int: max page number
        """
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
        """Find telegram links starts with @ and t.me/

        Args:
            text (str): where need find telegram links

        Returns:
            list[str]: list of telegram user or channel names
        """
        at = re.compile(r"@([^\s:]+)")
        link = re.compile(r"t.me\/([^\s:]+)")
        return at.findall(text) + link.findall(text)

    def __tg_from_intro(self, user):
        """Find user intro and find telegram links

        Args:
            user (srt): username in club

        Returns:
            list[srt]: list of telegram user or channel names
        """
        s = self._session.get(self.SITE_URL + f"/user/{user}")
        soup = BeautifulSoup(s.text, "html.parser")
        intro = soup.find("div", class_="profile-intro-text")
        if intro:
            text = intro.get_text()
            return self.__find_tg(text)
        else:
            return []

    def __check_tg(self, tgs):
        """Check if telegram name is channel

        Args:
            tgs (list[str]): telegram names

        Returns:
            list[srt]: telegram channel names
        """
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

    def __get_fullname(self, user):
        return user.find("span", class_="profile-user-fullname").get_text()

    def __get_nickname(self, user):
        return (
            user.find("span", class_="profile-user-nickname")
            .get_text()
            .replace("@", "")
        )

    def __get_users_from_page(self, html):
        """Get all users from html page and get user data:

        fullname
        nickname
        bio
        tg (telegram links)
        channels (telegram channels)

        Args:
            html (str): html page
        """
        soup = BeautifulSoup(html, "html.parser")
        for u in soup.find_all("article", class_="profile-card"):
            try:
                user = dict()

                user["fullname"] = self.__get_fullname(u)
                user["nickname"] = self.__get_nickname(u)
                logger.debug(f"user {user['nickname']}")
                user["bio"] = ""
                user["tg"] = []
                bio = u.find("div", class_="profile-user-bio")
                if bio:
                    user["bio"] = bio.get_text()
                    tg = self.__find_tg(user["bio"])
                    if tg:
                        user["tg"] = tg

                tg_from_intro = self.__tg_from_intro(user["nickname"])
                if tg_from_intro:
                    user["tg"] += tg_from_intro
                    user["tg"] = list(set(user["tg"]))

                user["channels"] = ""
                if user["tg"]:
                    channels = self.__check_tg(user["tg"])
                    if channels:
                        user["channels"] = channels

                self.users.append(user)
                self.__to_file(user)
            except Exception as e:
                logger.error(e)

    def get_users(self):
        """Main method, that login, going to paginated page, find telegram links and telegram channel.

        Returns:
            list[dict]: users with keys: fullname, nickname, bio, tg (telegram links), channels (telegram channels)
        """
        if self.__login():
            people = self._session.get(self.SITE_URL + "/people/")
            max_page = self.__find_max_page(people.text)
            max_page = 1
            for num_page in range(1, max_page + 1):
                logger.debug(f"page {num_page} from {max_page}")
                page = self._session.get(self.SITE_URL + f"/people/?page={num_page}")
                self.__get_users_from_page(page.text)

        return self.users


if __name__ == "__main__":
    logger.add("logs.log")
    tg = TgScraper()
    users = tg.get_users()
