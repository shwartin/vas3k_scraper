import os
import re
import json
import pydantic
import requests
from loguru import logger
from bs4 import BeautifulSoup
from dotenv import load_dotenv


class Telegram(pydantic.BaseModel):
    # all: list[str] = []  # debug
    chats: list[str] = []
    channels: list[str] = []
    personal: list[str] = []


class User(pydantic.BaseModel):
    fullname: str
    nickname: str
    telegram: Telegram = []


class UserList(pydantic.BaseModel):
    # https://stackoverflow.com/a/58636711/12843933
    __root__: list[User] = []


# todo
# finished writer
# test


class Scraper:
    """Scraping users from vas3k.club engine, find telegram links in bio and info and separate ids by type."""

    def __init__(self, site_url: pydantic.AnyHttpUrl, token: str) -> None:
        self.site_url = site_url
        self.token = token
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"
        }
        self.right_login_text = "Главная"
        self.web_tg_url = "https://t.me/s"
        self.session = requests.Session()
        self.users = self._paginator()

    def __del__(self):
        self.session.close()

    def _login(self) -> bool:
        payload = {"email_or_login": self.token}
        self.session.post(f"{self.site_url}/auth/email/", data=payload)

        main = self.session.get(self.site_url)
        if main.status_code == 200:
            soup = BeautifulSoup(main.text, "html.parser")
            if soup.body.findAll(text=re.compile(self.right_login_text)):
                logger.info("logged in successfully")
                return True
            else:
                logger.info("failed to log in")
                return False

    @staticmethod
    def _find_max_page(html: str) -> int:
        """Find max pagination page number."""
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

    def _tg_from_bio(self, user: BeautifulSoup) -> list[str]:
        bio = user.find("div", class_="profile-user-bio")
        if bio:
            text = bio.encode_contents().decode()
            return self._finder(text)
        else:
            return []

    def _tg_from_intro(self, user: str) -> list[str]:
        """Find user intro and find telegram links"""
        nickname = self._get_nickname(user)
        s = self.session.get(f"{self.site_url}/user/{nickname}")
        soup = BeautifulSoup(s.text, "html.parser")
        intro = soup.find("div", class_="profile-intro-text")
        if intro:
            # text = intro.get_text()
            text = intro.encode_contents().decode()
            return self._finder(text)
        else:
            return []

    def _separator(self, tgs) -> Telegram:
        """Separate telegram ids by type"""
        channels = []
        chats = []
        personal = []
        for tg in tgs:
            with requests.get(f"{self.web_tg_url}/{tg}", headers=self.headers) as r:
                if not r.status_code == 200:
                    continue
                if all(pattern in r.url for pattern in ["/s/", tg]):
                    channels.append(tg)
                elif tg in r.url:
                    soup = BeautifulSoup(r.text, "html.parser")
                    if desc := soup.find("div", class_="tgme_page_extra"):
                        if "@" in desc.get_text(strip=True):
                            personal.append(tg)
                        else:
                            chats.append(tg)
        if channels or chats or personal:
            return Telegram(all=tgs, channels=channels, chats=chats, personal=personal)

    @staticmethod
    def _finder(text: str) -> list[str]:
        """Find telegram links starts with @ and t.me/"""
        at = re.compile(r"@([\w\-\.]+[\w])")
        link = re.compile(r"t.me\/([\w\-\.]+[\w])")
        return at.findall(text) + link.findall(text)

    @staticmethod
    def _get_fullname(user: BeautifulSoup) -> str:
        return user.find("span", class_="profile-user-fullname").get_text()

    @staticmethod
    def _get_nickname(user: BeautifulSoup) -> str:
        return (
            user.find("span", class_="profile-user-nickname")
            .get_text()
            .replace("@", "")
        )

    def _get_tg(self, user) -> Telegram:
        tg_from_bio = self._tg_from_bio(user)
        tg_from_intro = self._tg_from_intro(user)
        tg = tg_from_bio + tg_from_intro
        unique_tg = list(set(tg))
        if telegram := self._separator(unique_tg):
            return telegram

    def _get_users(self, html: str) -> UserList:
        """Get all users from html page and get user data:"""
        page_users = UserList()
        soup = BeautifulSoup(html, "html.parser")
        for u in soup.find_all("article", class_="profile-card"):
            if telegram := self._get_tg(u):
                page_users.__root__.append(
                    User(
                        fullname=self._get_fullname(u),
                        nickname=self._get_nickname(u),
                        telegram=telegram,
                    )
                )
        if page_users.__root__:
            return page_users

    def _paginator(self) -> UserList:
        """Main method, that login, going to paginated page, find telegram links."""
        users = UserList()
        if self._login():
            people = self.session.get(f"{self.site_url}/people/")
            # max_page = self._find_max_page(people.text)
            max_page = 1
            for num_page in range(1, max_page + 1):
                logger.debug(f"page {num_page} from {max_page}")
                page = self.session.get(f"{self.site_url}/people/?page={num_page}")
                users.__root__ += self._get_users(page.text).__root__

        return users


if __name__ == "__main__":
    load_dotenv()
    login_token = os.environ.get("TOKEN")
    logger.add("logs.log")
    s = Scraper("https://4aff.club", login_token)
    logger.debug(s.users)
    with open("4aff.json", mode="w", encoding="utf-8") as f:
        f.write(s.users.json(ensure_ascii=False))
    # logger.debug(s.users.json())
