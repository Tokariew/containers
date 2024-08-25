import datetime
from pathlib import Path

import lxml
import requests
from bs4 import BeautifulSoup
from ruamel.yaml import YAML
from tqdm import tqdm
from loguru import logger
from sys import stdout

logger.remove(0)
logger.add(stdout,
           level='WARNING',
           colorize=True,
           backtrace=False,
           diagnose=False,
           format="<level>{level}:</level> {message}\x1b[K")
logger.add("/srv/logfile", rotation="10 MB", backtrace=True)


def getasin(url):
    asin = url[url.find('/dp/') + 4:]
    return asin[:10]


def canonicalurl(asin):
    return f'https://www.amazon.com/dp/{asin}/'


def get_book_info(url):
    headers = {
        "User-Agent":
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0",
        "Accept-Language": "en-GB",
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "lxml")

    name = soup.select_one(selector="#productTitle").getText()
    name = name.strip()
    try:
        price = soup.select_one(selector="#kindle-price").getText()
    except AttributeError:
        price = soup.select_one(
            "span[class='a-size-base a-color-secondary ebook-price-value']")
        if price:
            price = price.getText()
        else:
            price = soup.find("span", {"class": "kindleExtraMessage"})
            price = price.find('span', {'class': 'a-color-price'}).getText()
    price = float(price.strip().split()[0][1:])
    image = soup.find("img",
                      id="landingImage")["data-a-dynamic-image"].split('"')[1]
    author = soup.select_one("span[class='author notFaded']").getText()
    author = author.split('\n')[1].strip()
    return name, author, price, image


def get_price(url):
    *_, price, _ = get_book_info(url)
    return price


def send_notif(book, min_price=False):
    headers = {
        'Priority': '3',
        'Attach': book.image,
        "Actions": f"view, Check promo, {book.url}, clear=true;"
    }
    lowest = ''
    if min_price:
        headers['Tags'] = 'warning'
        headers['Priority'] = 'high'
        lowest = "Lowest price!! "
    requests.post(
        'http://ntfy/book',
        data=
        f'{lowest}{book.title} by {book.author} is currently on sale by {book.diff_price:0.2f}$.',
        headers=headers)


def send_error(txt):
    requests.post('http://ntfy/book',
                  data=txt,
                  headers={
                      'Tag': 'no_entry',
                      'Priority': '4'
                  })


def dump_data(to_dump, filepath):
    to_dump = [item.__dict__ for item in to_dump]
    to_dump = sorted(to_dump, key=lambda i: (i['asin'], i['title']))
    yaml.indent(mapping=4, sequence=6, offset=3)
    with open(filepath, 'w') as file:
        yaml.dump(to_dump, file)


def read_data(filepath):
    with open(filepath) as yamlfile:
        tmp = yaml.load(yamlfile)
        return {Book(**item) for item in tmp}


def import_new_books(filepath):
    failed = []
    new_books = []
    with open(filepath) as file:
        for line in file:
            try:
                new_books.append(Book(line))
            except AttributeError:
                logger.opt(exception=True).debug("What happend:")
                failed.append(line)

    if failed:
        with open(filepath, 'w') as file:
            file.write(''.join(failed))
        send_error(f'Failed adding {len(failed)} books.')
        for url in failed:
            logger.error(f"Can't add book {url}")
    else:
        filepath.unlink()
    return set(new_books)


class Book:

    def __init__(self, url='', **kwargs):
        if 'asin' in kwargs.keys():
            for key in kwargs.keys():
                setattr(self, key, kwargs[key])
            self.url = url
        else:
            self.asin = getasin(url)
            self.url = canonicalurl(self.asin)
            self.title, self.author, self.price, self.image = get_book_info(
                self.url)
            self.min_price = self.price
            self.max_price = self.price
            self.diff_price = 0
            self.last_change = datetime.datetime.now()

    def update_price(self):
        price = get_price(self.url)

        if price != self.price:
            self.diff_price = self.price - price
            if price < self.min_price:
                send_notif(self, min_price=True)
                self.min_price = price
            elif price < self.price:
                send_notif(self)
            elif price > self.max_price:
                self.max_price = price
            self.price = price
            self.last_change = datetime.datetime.now()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Book):
            return NotImplemented
        return self.asin == other.asin

    def __hash__(self) -> int:
        return hash(self.asin)

    def __repr__(self):
        return f'{self.title} by {self.author} on {self.url}'


if __name__ == '__main__':
    yaml = YAML(typ='safe')
    yaml.default_flow_style = False

    new_book_set = set()
    current_book_set = set()

    new_book_file = Path('/srv/new_books.txt')
    if new_book_file.exists():
        new_book_set = import_new_books(new_book_file)

    current_book_file = Path('/srv/exported_books.yaml')
    if current_book_file.exists():
        current_book_set = read_data(current_book_file)
        failed = []
        with tqdm(total=len(current_book_set), desc="Updating prices") as pbar:
            for book in current_book_set:
                try:
                    book.update_price()
                except AttributeError:
                    logger.opt(exception=True).debug("What happend:")
                    failed.append(book.url)
                pbar.update()
        if failed:
            send_error(f'Failed updating prices for {len(failed)} books.')
            for book in failed:
                logger.error(f"Can't add book {book}")

    current_book_set = current_book_set.union(new_book_set)

    dump_data(current_book_set, current_book_file)
