from dotenv import load_dotenv
from http import HTTPStatus
import logging
import os
import requests
import sys
from time import time, sleep

from telegram import Bot


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

MESSAGE_ERROR_CHECK_TOKENS = '''
Отсутствует обязательная переменная окружения: '{token}}'
Программа принудительно остановлена.
'''


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
))
logger.addHandler(handler)


def check_tokens() -> None:
    """Функция проверки получения всех необходимых токенов."""
    if PRACTICUM_TOKEN == '':
        logger.critical(
            MESSAGE_ERROR_CHECK_TOKENS.format(token=PRACTICUM_TOKEN)
        )
        raise SystemExit(
            MESSAGE_ERROR_CHECK_TOKENS.format(token=PRACTICUM_TOKEN)
        )
    if TELEGRAM_TOKEN == '':
        logger.critical(
            MESSAGE_ERROR_CHECK_TOKENS.format(token=TELEGRAM_TOKEN)
        )
        raise SystemExit(
            MESSAGE_ERROR_CHECK_TOKENS.format(token=TELEGRAM_TOKEN)
        )
    if TELEGRAM_CHAT_ID == '':
        logger.critical(
            MESSAGE_ERROR_CHECK_TOKENS.format(token=TELEGRAM_CHAT_ID)
        )
        raise SystemExit(
            MESSAGE_ERROR_CHECK_TOKENS.format(token=TELEGRAM_CHAT_ID)
        )


def send_message(bot, message):
    """Функция отправки сообщения в чат Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение "{message}"')
    except Exception as error:
        logger.error(
            f'Ошибка при отправке ботом сообщения:\n{error}',
            exc_info=True
        )


def get_api_answer(timestamp):
    """Функция получения ответа API Практикум.Домашка."""
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )

        if response.status_code == HTTPStatus.OK:
            logger.info('Получен ответ "OK" от API (код 200).')
            return response.json()

        message = '''
Сбой в работе программы: код ответа API {code}!
{addition}!
'''
        statuses_messages = {
            '400': message.format(
                code=400,
                addition='Проверьте значение параметра "from_date"'
            ),
            '401': message.format(
                code=401,
                addition='Проверьте действительность и корректность токенов'
            ),
            '404': message.format(
                code=404,
                addition=f'Эндпоинт {ENDPOINT} недоступен!'
            ),
        }

        if str(response.status_code) in statuses_messages:
            logger.error(statuses_messages[str(response.status_code)])
            return statuses_messages[str(response.status_code)]

    except requests.ConnectionError as error:
        message = f'''
Сбой в работе программы: ошибка подключения к удаленному серверу!
{error}
'''
        logger.error(message, exc_info=True)
        return message
    except requests.HTTPError as error:
        message = f'''
Сбой в работе программы: ошибка подключения к удаленному серверу!
{error}
'''
        logger.error(message, exc_info=True)
        return message
    except requests.URLRequired as error:
        message = f'''
Сбой в работе программы: для отправки запроса необходим действительный URL!
{error}
'''
        logger.error(message, exc_info=True)
        return message
    except requests.Timeout as error:
        message = f'''
Сбой в работе программы: время запроса истекло!
{error}
'''
        logger.error(message, exc_info=True)
        return message
    except requests.RequestException as error:
        message = f'''
Сбой в работе программы: неоднозначная ошибка при работе с запросом!
{error}
'''
        logger.error(message, exc_info=True)
        return message


def check_response(response):
    """Функция проверки ответа API на соответствие документации."""
    try:
        if "homeworks" in response and "current_date" in response:
            message = 'Основные поля в ответе API соответствуют документации.'
            logger.debug(message)
            if len(response["homeworks"]) == 0:
                logger.info('Новые статусы домашних работ отсутсвуют.')
                return None
            else:
                return response["homeworks"]
        else:
            message = (
                'Сбой в работе программы: '
                'основные поля в ответе API не соответствуют документации.'
            )
            logger.error(message)
            return message
    except Exception as error:
        message = f'''
Сбой в работе программы: непредвиденная ошибка!
{error}
'''
        logger.error(message, exc_info=True)
    return message


def parse_status(homework):
    """Функция извлечения статуса конкретной домашней работы."""
    try:
        if "homework_name" not in homework:
            message = (
                'Ошибка данных: '
                'в объекте "homework" отсутствует ключ "homework_name"!'
            )
            logger.error(message)
            return message
        if "status" not in homework:
            message = (
                'Ошибка данных: '
                'в объекте "homework" отсутствует ключ "homework_name"!'
            )
            logger.error(message)
            return message
        message = (
            'Изменился статус проверки работы '
            f'"{homework["homework_name"]}". '
            f'{HOMEWORK_VERDICTS[homework["status"]]}'
        )
        logger.info(message)
        return message
    except KeyError():
        message = (
            'Получен необычный статус домашней работы: '
            f'{homework["status"]}'
        )
        logger.error(message)
        return message


def main():
    """Основная логика работы бота."""
    check_tokens()
    logger.debug('Токены проверены. Успех!')
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time())

    while True:
        try:
            logger.debug('Запрос отправлен.')
            answer = get_api_answer(timestamp)
            if type(answer) is str:
                send_message(bot, answer)
            else:
                logger.debug('Ответ от API успешно получен.')
                answer = check_response(answer)
                if type(answer) is str:
                    send_message(bot, answer)
                elif type(answer) is dict:
                    message = parse_status(answer)
                    send_message(bot, message)
                elif type(answer) is list:
                    for homework in answer:
                        message = parse_status(homework)
                        send_message(bot, message)
            sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'''
Сбой в работе программы: непредвиденная ошибка!
{error}
'''
            logger.critical(message, exc_info=True)
            send_message(bot, message)
            raise SystemExit('Программа принудительно остановлена.')


if __name__ == '__main__':
    main()
