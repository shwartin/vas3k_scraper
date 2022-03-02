import os
import re
import json
import requests
from loguru import logger
from dotenv import load_dotenv
from bs4 import BeautifulSoup


class TgScraper:
    """Scraping users from vas3k.club engine, find telegram links in bio and info and separate ids by type.

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
        # delete last comma
        self._file.seek(self._file.tell() - 2, os.SEEK_SET)
        self._file.truncate()

        self._file.write("\n]")
        self._file.close()

    def __open_file(self, filename):
        """Open a file for recording users.

        Args:
            filename (str): file name

        Returns:
            file object: opened file
        """
        if os.path.exists(filename):
            os.remove(filename)
            logger.debug(f"{filename} file removed")
        f = open(filename, "a", encoding="utf-8")
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
        at_1 = re.compile(r"@([^\s.]+)")
        at_2 = re.compile(r"@([^\s]+)")
        link = re.compile(r"t.me\/([^\s]+)")
        return at_1.findall(text) + at_2.findall(text) + link.findall(text)

    def __tg_from_bio(self, user):
        bio = user.find("div", class_="profile-user-bio")
        if bio:
            return self.__find_tg(bio.get_text())
        else:
            return []

    def __tg_from_intro(self, user):
        """Find user intro and find telegram links

        Args:
            user (srt): username in club

        Returns:
            list[str]: list of telegram user or channel names
        """
        nickname = self.__get_nickname(user)
        s = self._session.get(self.SITE_URL + f"/user/{nickname}")
        soup = BeautifulSoup(s.text, "html.parser")
        intro = soup.find("div", class_="profile-intro-text")
        if intro:
            text = intro.get_text()
            return self.__find_tg(text)
        else:
            return []

    def __separate_tg(self, tgs):
        """Separate telegram ids by type

        Args:
            tgs (list[str]): telegram ids

        Returns:
            dict: telegram separate ids
        """
        links = {"all": tgs, "channels": [], "chats": [], "personal": []}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"
        }
        for tg in tgs:
            r = requests.get(f"https://t.me/s/{tg}", headers=headers)
            soup = BeautifulSoup(r.text, "html.parser")
            tg_page = soup.find("div", class_="tgme_page_extra")
            if soup.find("div", class_="tgme_channel_info_counters"):
                links["channels"].append(tg)
            elif tg_page:
                if tg_page.find(text=re.compile("@")):
                    links["personal"].append(tg)
                else:
                    links["chats"].append(tg)

        return links

    def __get_fullname(self, user):
        return user.find("span", class_="profile-user-fullname").get_text()

    def __get_nickname(self, user):
        return (
            user.find("span", class_="profile-user-nickname")
            .get_text()
            .replace("@", "")
        )

    def __get_tg(self, user):
        tg_from_bio = self.__tg_from_bio(user)
        tg_from_intro = self.__tg_from_intro(user)
        tg = tg_from_bio + tg_from_intro
        unique_tg = list(set(tg))
        return self.__separate_tg(unique_tg)

    def __get_users_from_page(self, html):
        """Get all users from html page and get user data:

        fullname
        nickname
        tg (telegram links)

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
                user["tg"] = self.__get_tg(u)

                self.users.append(user)
                self.__to_file(user)
            except Exception as e:
                logger.error(e)

    def get_users(self):
        """Main method, that login, going to paginated page, find telegram links and telegram channel.

        Returns:
            list[dict]: users with keys: fullname, nickname, tg (telegram links)
        """
        if self.__login():
            people = self._session.get(self.SITE_URL + "/people/")
            max_page = self.__find_max_page(people.text)
            for num_page in range(1, max_page + 1):
                logger.debug(f"page {num_page} from {max_page}")
                page = self._session.get(self.SITE_URL + f"/people/?page={num_page}")
                self.__get_users_from_page(page.text)

        return self.users


if __name__ == "__main__":
    logger.add("logs.log")
    tg = TgScraper()
    users = tg.get_users()
