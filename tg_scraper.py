from calendar import c
import re
import click
import requests
from loguru import logger
from requests import session
from bs4 import BeautifulSoup
from pydantic import AnyHttpUrl, BaseModel


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"
}
MAIN_TEXT = "Главная"
WEB_TG_URL = "https://t.me/s"


class Channel(BaseModel):
    id: str
    title: str
    description: str
    subscribers: int


class Telegram(BaseModel):
    chats: list[str] = []
    channels: list[Channel] = []
    personal: list[str] = []


class User(BaseModel):
    fullname: str
    nickname: str
    telegram: Telegram = []


class UserList(BaseModel):
    # https://stackoverflow.com/a/58636711/12843933
    __root__: list[User] = []


def login(s: session, url: AnyHttpUrl, token: str) -> bool:
    """Login to club"""
    payload = {"email_or_login": token}
    s.post(f"{url}/auth/email/", data=payload)

    main = s.get(url)
    if not main.status_code == 200:
        logger.error(f"Problem with login. Status code is {main.status_code}")
        return False
    soup = BeautifulSoup(main.text, "html.parser")
    if not soup.body.findAll(text=re.compile(MAIN_TEXT)):
        logger.info("Failed to login")
        return False
    logger.info("I'm in")
    return True


def find_max_page(html: str) -> int:
    """Find max pagination page number."""
    soup = BeautifulSoup(html, "html.parser")
    max_page = 0
    for a in soup.find_all("a", class_="paginator-page")[:-1]:
        try:
            number = int(a.get_text(strip=True))
            if number > max_page:
                max_page = number
        except Exception as e:
            logger.error(f"Finding max page error: {e}.")

    return max_page


def tg_from_bio(user: BeautifulSoup) -> list[str]:
    """Find telegram link in bio"""
    bio = user.find("div", class_="profile-user-bio")
    if bio:
        text = bio.encode_contents().decode()
        return finder(text)
    else:
        return []


def tg_from_intro(s: session, url: AnyHttpUrl, user: BeautifulSoup) -> list[str]:
    """Find user intro and find telegram links"""
    nickname = get_nickname(user)
    s = s.get(f"{url}/user/{nickname}")
    soup = BeautifulSoup(s.text, "html.parser")
    intro = soup.find("div", class_="profile-intro-text")
    if not intro:
        return []
    text = intro.encode_contents().decode()
    return finder(text)


def convert_str_to_number(x: str) -> int:
    total_stars = 0
    num_map = {"K": 1000, "M": 1000000, "B": 1000000000}
    if x.isdigit():
        total_stars = int(x)
    else:
        if len(x) > 1:
            total_stars = float(x[:-1]) * num_map.get(x[-1].upper(), 1)
    return int(total_stars)


def get_channel_info(soup: BeautifulSoup) -> Channel:
    title = soup.find(class_="tgme_channel_info_header_title").get_text()
    description = soup.find("div", class_="tgme_channel_info_description").get_text()
    subscribers = (
        soup.find("div", class_="tgme_channel_info_counter")
        .find("span", class_="counter_value")
        .get_text(strip=True)
    )
    subscribers = convert_str_to_number(subscribers)
    return title, description, subscribers


def separator(tgs: list) -> Telegram:
    """Separate telegram ids by type"""
    channels = []
    chats = []
    personal = []
    for tg in tgs:
        with requests.get(f"{WEB_TG_URL}/{tg}", headers=HEADERS) as r:
            if not r.status_code == 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            if all(pattern in r.url for pattern in ["/s/", tg]):
                title, description, subscribers = get_channel_info(soup)
                channels.append(
                    Channel(
                        id=tg,
                        title=title,
                        description=description,
                        subscribers=subscribers,
                    )
                )
            elif tg in r.url:
                if desc := soup.find("div", class_="tgme_page_extra"):
                    if "@" in desc.get_text(strip=True):
                        personal.append(tg)
                    else:
                        chats.append(tg)

    if any([channels, chats, personal]):
        return Telegram(channels=channels, chats=chats, personal=personal)


def finder(text: str) -> list[str]:
    """Find telegram links starts with @ and t.me/"""
    at = re.compile(r"@([\w\-\.]+[\w])")
    link = re.compile(r"t.me\/([\w\-\.]+[\w])")
    return at.findall(text) + link.findall(text)


def get_fullname(user: BeautifulSoup) -> str:
    return user.find("span", class_="profile-user-fullname").get_text()


def get_nickname(user: BeautifulSoup) -> str:
    return user.find("span", class_="profile-user-nickname").get_text().replace("@", "")


def get_tg(s: session, url: AnyHttpUrl, user: BeautifulSoup) -> Telegram:
    tg_bio = tg_from_bio(user)
    tg_intro = tg_from_intro(s, url, user)
    tg = tg_bio + tg_intro
    unique_tg = list(set(tg))
    if telegram := separator(unique_tg):
        return telegram


def get_users(s: session, url: AnyHttpUrl, html: str) -> UserList:
    """Get all users from html page"""
    page_users = UserList()
    soup = BeautifulSoup(html, "html.parser")
    for u in soup.find_all("article", class_="profile-card"):
        try:
            if telegram := get_tg(s, url, u):
                page_users.__root__.append(
                    User(
                        fullname=get_fullname(u),
                        nickname=get_nickname(u),
                        telegram=telegram,
                    )
                )
        except requests.exceptions.ProxyError as e:
            logger.error(f"Error: {e}. User: {u}.")
    return page_users


@click.command()
@click.option("--url", help="Site", required=True)
@click.option("--token", help="Login token", required=True)
@click.argument("file", type=click.File("w"), required=True)
def paginator(url: AnyHttpUrl, token: str, file: str) -> None:
    """Scraping club users and fing all telegram links."""
    users = UserList()
    with requests.session() as s:
        s.headers = HEADERS
        if login(s, url, token):
            people = s.get(f"{url}/people/")
            max_page = find_max_page(people.text)
            with click.progressbar(
                range(1, max_page + 1), label="Scraping users"
            ) as bar:
                for num_page in bar:
                    page = s.get(f"{url}/people/?page={num_page}")
                    page_users = get_users(s, url, page.text)
                    users.__root__ += page_users.__root__

    file.write(users.json(ensure_ascii=False))


if __name__ == "__main__":
    logger.add("logs.log")
    paginator()
