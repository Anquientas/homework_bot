from dotenv import load_dotenv
from http import HTTPStatus
import logging
import os
import requests
import sys
import time

import telegram

from exceptions import AnotherCodeResponse


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

MESSAGE_ERROR_CHECK_TOKENS = (
    'Отсутствует обязательная переменная окружения: {token}\n'
    'Программа принудительно остановлена.'
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
))
logger.addHandler(handler)


def check_tokens():
    """Функция проверки наличия необходимых токенов."""
    tokens_inserts = (
        (PRACTICUM_TOKEN, 'PRACTICUM_TOKEN'),
        (TELEGRAM_TOKEN, 'TELEGRAM_TOKEN'),
        (TELEGRAM_CHAT_ID, 'TELEGRAM_CHAT_ID'),
    )

    for token, insert in tokens_inserts:
        if token is None:
            logger.critical(
                MESSAGE_ERROR_CHECK_TOKENS.format(token=insert)
            )
            return False
    return True


def send_message(bot, message):
    """Функция отправки сообщения в чат Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except BaseException as error:
        logger.error(
            f'Ошибка при отправке ботом сообщения:\n{error}',
            exc_info=True
        )
    else:
        logger.debug(f'Бот отправил сообщение "{message}"')


def get_api_answer(timestamp):
    """Функция получения ответа API Практикум.Домашка."""
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )

        if response.status_code != HTTPStatus.OK:
            message = (
                'Сбой в работе программы: '
                f'код ответа API {response.status_code}!'
            )
            logger.error(message)
            raise AnotherCodeResponse(response.status_code)

        logger.debug('Получен ответ "OK" от API (код 200).')
        return response.json()
    except requests.ConnectionError as error:
        message = (
            'Сбой в работе функции get_api_answer: '
            f'ошибка подключения к удаленному серверу!\n{error}'
        )
        logger.error(message, exc_info=True)
        return message
    except requests.HTTPError as error:
        message = (f'Сбой в работе программы: ошибка HTTP!\n{error}')
        logger.error(message, exc_info=True)
        return message
    except requests.URLRequired as error:
        message = (
            'Сбой в работе функции get_api_answer: '
            f'для отправки запроса необходим действительный URL!\n{error}'
        )
        logger.error(message, exc_info=True)
        return message
    except requests.Timeout as error:
        message = (
            'Сбой в работе функции get_api_answer: '
            f'время запроса истекло!\n{error}'
        )
        logger.error(message, exc_info=True)
        return message
    except requests.RequestException as error:
        message = (
            'Сбой в работе функции get_api_answer: '
            f'неоднозначная ошибка при работе с запросом!\n{error}'
        )
        logger.error(message, exc_info=True)
        return message


def check_response(response):
    """Функция проверки ответа API на соответствие документации."""
    if type(response) is not dict:
        logger.error('В ответе API данные поступили не в виде словаря!')
        raise TypeError()
    logger.debug('Данные в ответе API поступили в виде словаря.')

    if "homeworks" not in response:
        logger.error(
            'В словаре данных из ответа API отсутвует ключ "homeworks"!'
        )
        raise KeyError()
    logger.debug(
        'В словаре данных из ответа API присутствует ключ "homeworks".'
    )

    if "current_date" not in response:
        logger.error(
            'В словаре данных из ответа API отсутвует ключ "current_date"!'
        )
        raise KeyError()
    logger.debug(
        'В словаре данных из ответа API присутствует ключ "current_date".'
    )

    if type(response["homeworks"]) is not list:
        logger.error('Домашние работы поступают не списком!')
        raise TypeError()
    logger.debug('Домашние работы поступили списком.')
    logger.debug('Основные поля в ответе API соответствуют документации.')

    try:
        if len(response["homeworks"]) == 0:
            logger.info('Новые статусы домашних работ отсутсвуют.')
        return response["homeworks"]
    except Exception as error:
        message = (
            'Сбой в работе функции check_response: '
            f'непредвиденная ошибка!\n{error}'
        )
        logger.error(message, exc_info=True)
    return message


def parse_status(homework):
    """Функция извлечения статуса домашней работы."""
    if "homework_name" not in homework:
        logger.error(
            'Ошибка данных: '
            'в объекте "homework" отсутствует ключ "homework_name"!'
        )
        raise KeyError()
    if "status" not in homework:
        logger.error(
            'Ошибка данных: '
            'в объекте "homework" отсутствует ключ "status"!'
        )
        raise KeyError()
    if homework["status"] not in HOMEWORK_VERDICTS:
        logger.error(
            f'Получен необычный статус домашней работы: {homework["status"]}'
        )
        raise KeyError()

    try:
        message = (
            'Изменился статус проверки работы '
            f'"{homework["homework_name"]}". '
            f'{HOMEWORK_VERDICTS[homework["status"]]}'
        )
        logger.info(message)
        return message
    except Exception as error:
        message = (
            'Сбой в работе функции parse_status: '
            f'непредвиденная ошибка!\n{error}'
        )
        logger.error(message, exc_info=True)
    return message


def main():
    """Основная логика работы бота."""
    if check_tokens():
        logger.debug('Токены проверены. Успех!')
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    else:
        logger.error(
            'Ошибка запуска бота: не получены все необходимые токены!'
        )
        raise SystemExit()

    timestamp = int(time.time())

    while True:
        try:
            logger.debug('Запрос отправлен.')
            response = get_api_answer(timestamp)
            logger.debug('Ответ от API успешно получен.')
            send_message(bot, 'Ответ от API успешно получен.')
            homeworks = check_response(response)
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
        except Exception as error:
            message = (
                f'Сбой в работе программы: непредвиденная ошибка!\n{error}'
            )
            logger.error(message, exc_info=True)
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
