# Telegram links scraper from vas3k.club engine 

Scraping [vas3k.club engine](https://github.com/vas3k/vas3k.club) users and fing all telegram links.
 
 ## Description

I know several clubs on [vas3k.club engine](https://github.com/vas3k/vas3k.club):
- https://vas3k.club/
- https://rationalanswer.club/
- https://4aff.club
- https://sorokin.club

Scraper detect telegram links:
1. start from `@`
2. including `t.me/`

## Prepare

1. Join the club
2. Go to `https://your.club/user/{login}/edit/account/` and get login token
3. Install virtual environment with [poetry](https://github.com/python-poetry/poetry) `poetry install`

## Usage

```
poetry run python vas3k_scraper.py --url "http://vas3k.club" file.json
```

And then enter your token.

Where:
- `http://vas3k.club` url of your club
- `file.json` file for stored data

## Result

`file.json` fake example:
```
[
    {
        "fullname": "Вастрик Бот",
        "nickname": "vas3k_club",
        "telegram": {
            "chats": [],
            "channels": [
                {
                    "id": "vas3k_club",
                    "title": "Вастрик.Клуб",
                    "description": "Канал Вастрик.Клуба (vas3k.club)",
                    "subscribers": 6868
                }
            ],
            "personal": [
                "vas3k_club"
            ]
        }
    },
    {
        "fullname": "RationalAnswer Bot",
        "nickname": "RationalAnswer_club",
        "telegram": {
            "chats": [
                "RationalAnswer_club_chat"
            ],
            "channels": [
                {
                    "id": "RationalAnswer_club",
                    "title": "Клуб RationalAnswer",
                    "description": "Здесь регулярно появляются ссылки на новые интересные посты и еженедельные рассылки Клуба RationalAnswer: https://RationalAnswer.club/Чат Клуба: https://t.me/RationalAnswer_club_chat",
                    "subscribers": 664
                }
            ],
            "personal": []
        }
    },
]
```

## Disclaimer

This repository/project is intended for Educational Purposes ONLY. Use this code for own risk.