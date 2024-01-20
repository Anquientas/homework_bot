from dotenv import load_dotenv
from http import HTTPStatus
import logging
import os
import requests
import sys
import time

import telegram


load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

KEYS_IN_HOMEWORK = ('homework_name', 'status')
KEYS_IN_RESPONSE_WITH_CODE_NOT_OK = ('error', 'code')

CODE_NOT_OK = (
    '\tСбой в работе программы: код ответа API {status_code}!\n'
    '\tДанные отправленного запроса:\n'
    '\t- тип запроса: "GET";\n'
    '\t- URL (эндпоинт): {url};\n'
    '\t- заголовок: {headers}\n'
    '\t- параметры: {params}\n'
)
CODE_OK = 'Получен ответ "OK" от API (код 200).'
ERROR_IN_MAIN = (
    'Сбой в работе программы!\n{error}'
)
ERROR_IN_RESPONSE = (
    '\tСбой в работе программы: в ответе вернулась ошибка!\n'
    '\tДанные отправленного запроса:\n'
    '\t- тип запроса: "GET";\n'
    '\t- URL (эндпоинт): {url};\n'
    '\t- заголовок: {headers}\n'
    '\t- параметры: {params}\n'
    '\tДанные ответа:\n'
    '\t- ключ: {key};\n'
    '\t- данные по ключу: {data_by_key};\n'
)
ERROR_REPEAT = 'При новом запросе обнаружилась та же ошибка.'
FIELDS_IS_OK = (
    'Основные поля в ответе API соответствуют документации.'
)
HOMEWORKS_IS_NOT_LIST = (
    '\tОжидаемый тип данных набора домашних работ - список!\n'
    '\tПолученный тип данных набора домашних работ: {type_data}!'
)
HOMEWORKS_IS_LIST = 'Набор домашних работ поступил в виде списка.'
KEY_IN_DICT = (
    'В словаре данных из ответа API присутствует ключ "homeworks".'
)
KEY_NOT_IN_DICT = (
    '\tВ словаре данных из ответа API отсутвует ключ "homeworks"!'
)
ALL_KEYS_IN_HOMEWORK = 'Все ключи присутствуют в homework.'
KEY_NOT_IN_HOMEWORK = (
    '\tОшибка данных: в объекте "homework" отсутствует ключ "{key}"!'
)
MESSAGE_SEND = 'Бот отправил следующее сообщение:\n\t{message}'
MESSAGE_SEND_ERROR = (
    '\tОшибка при отправке ботом сообщения!\n'
    '\tТекст ссобщения: {message}\n\tОшибка: {error}.'
)
NEW_STATUS = (
    'Изменился статус проверки работы "{homework}". {status}'
)
NOT_NEW_STATUSES = 'Новые статусы домашних работ отсутсвуют.'
NOT_TOKEN = (
    'Отсутствует(ют) обязательная(ые) переменная(ые) окружения: {tokens}!\n'
    'Программа принудительно остановлена.'
)
RESPONSE_IS_DICT = 'Данные в ответе API поступили в виде словаря.'
RESPONSE_IS_NOT_DICT = (
    '\tОжидаемый тип данных в ответе API - словарь!\n'
    '\tПолученный тип данных в ответе API: {type_data}!'
)
RESPONSE_GET = 'Ответ от API успешно получен.'
REQUEST_EXCEPTION = (
    '\tСбой в работе программы: ошибка при работе с запросом!\n'
    '\tДанные отправленного запроса:\n'
    '\t- тип запроса: "GET";\n'
    '\t- URL (эндпоинт): {url};\n'
    '\t- заголовок: {headers}\n'
    '\t- параметры: {params}\n'
    '\tОшибка:\n\t{error}'
)
REQUEST_SEND = 'Запрос отправлен.'
STATUS_IS_KNOWN = 'Получен учтенный статус homework.'
TOKENS_IS_OK = 'Токены проверены. Успех!'
UNKNOWN_STATUS = (
    'Неучтенный статус домашней работы: {status}!'
)


logger = logging.getLogger(__name__)


def check_tokens():
    """Функция проверки наличия необходимых токенов."""
    tokens = []
    for token in TOKENS:
        if not globals()[token]:
            tokens.append(token)
    if tokens:
        message = NOT_TOKEN.format(tokens=tokens)
        logger.critical(message)
        raise ValueError(message)


def send_message(bot, message):
    """Функция отправки сообщения в чат Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(MESSAGE_SEND.format(message=message))
        return True
    except Exception as error:
        logger.exception(
            MESSAGE_SEND_ERROR.format(
                message=message,
                error=error
            )
        )


def get_api_answer(timestamp):
    """Функция получения ответа API Практикум.Домашка."""
    request_data = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        response = requests.get(**request_data)
        response_data = response.json()
    except requests.exceptions.RequestException as error:
        raise OSError(
            REQUEST_EXCEPTION.format(
                error=error,
                **request_data
            )
        )

    if response.status_code != HTTPStatus.OK:
        raise ValueError(
            CODE_NOT_OK.format(
                status_code=response.status_code,
                **request_data
            )
        )
    for key in KEYS_IN_RESPONSE_WITH_CODE_NOT_OK:
        if key in response_data:
            raise ValueError(
                ERROR_IN_RESPONSE.format(
                    key=key,
                    data_by_key=response_data[key],
                    **request_data
                )
            )
    logger.debug(CODE_OK)
    return response_data


def check_response(response):
    """Функция проверки ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            RESPONSE_IS_NOT_DICT.format(type_data=type(response))
        )
    logger.debug(RESPONSE_IS_DICT)
    if 'homeworks' not in response:
        raise KeyError(KEY_NOT_IN_DICT)
    logger.debug(KEY_IN_DICT)
    homeworks = response["homeworks"]
    if not isinstance(homeworks, list):
        raise TypeError(
            HOMEWORKS_IS_NOT_LIST.format(type_data=type(homeworks))
        )
    logger.debug(HOMEWORKS_IS_LIST)
    logger.debug(FIELDS_IS_OK)
    return homeworks


def parse_status(homework):
    """Функция извлечения статуса домашней работы."""
    for key in KEYS_IN_HOMEWORK:
        if key not in homework:
            raise KeyError(
                KEY_NOT_IN_HOMEWORK.format(key=key)
            )
    logger.debug(ALL_KEYS_IN_HOMEWORK)
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            UNKNOWN_STATUS.format(status=homework_status)
        )
    logger.debug(STATUS_IS_KNOWN)
    message = NEW_STATUS.format(
        homework=homework['homework_name'],
        status=HOMEWORK_VERDICTS[homework_status]
    )
    logger.info(message)
    return message


def main():
    """Основная логика работы бота."""
    check_tokens()
    logger.debug(TOKENS_IS_OK)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    message_error_last = ''
    while True:
        try:
            logger.debug(REQUEST_SEND)
            response = get_api_answer(timestamp)
            logger.debug(RESPONSE_GET)
            homeworks = check_response(response)
            if not homeworks:
                logger.info(NOT_NEW_STATUSES)
            else:
                homework = homeworks[0]
                message = parse_status(homework)
                if send_message(bot, message):
                    timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = ERROR_IN_MAIN.format(error=error)
            if message != message_error_last:
                logger.exception(message)
                if send_message(bot, message):
                    message_error_last = message
            else:
                logger.debug(ERROR_REPEAT)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s [%(levelname)s]\n'
            '\tSource: file "%(pathname)s", line %(lineno)d, in %(funcName)s\n'
            '\t%(message)s'
        ),
        handlers=[
            logging.FileHandler(__file__ + '.log', mode='w'),
            stream_handler
        ]
    )

    main()
