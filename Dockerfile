FROM python:latest
WORKDIR /tg_scraper
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "tg_scraper.py"]