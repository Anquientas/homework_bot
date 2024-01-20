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

# Далее - блок заготовок сообщений
# Принцип наименования: MES_{level}_{long_name},
# где: MES - сокращение от "MESSAGE";
#      {level} - уровень критичности сообщения;
#      {long_name} - наименование заготовки сообщения.

MES_DEBUG_CODE_NOT_OK = 'Ответ, полученный от API не "OK" (код {code})'
MES_DEBUG_CODE_OK = 'Получен ответ "OK" от API (код 200).'
MES_DEBUG_ERROR_REPEAT = 'При новом запросе обнаружилась та же ошибка.'
MES_DEBUG_FIELDS_IS_OK = (
    'Основные поля в ответе API соответствуют документации.'
)
MES_DEBUG_HOMEWORKS_IS_LIST = 'Набор домашних работ поступил в виде списка.'
MES_DEBUG_KEY_IN_DICT = (
    'В словаре данных из ответа API присутствует ключ "homeworks".'
)
MES_DEBUG_KEYS_IN_HOMEWORK = 'Все ключи присутствуют в homework.'
MES_DEBUG_MESSAGE_SEND = 'Бот отправил следующее сообщение:\n\t{message}.'
MES_DEBUG_RESPONSE_IS_DICT = 'Данные в ответе API поступили в виде словаря.'
MES_DEBUG_RESPONSE_GET = 'Ответ от API успешно получен.'
MES_DEBUG_REQUEST_SEND = 'Запрос отправлен.'
MES_DEBUG_STATUS_IS_KNOWN = 'Получен учтенный статус homework.'
MES_DEBUG_TOKENS_IS_OK = 'Токены проверены. Успех!'

MES_INFO_NEW_STATUS = (
    'Изменился статус проверки работы "{homework}". {status}'
)
MES_INFO_NOT_NEW_STATUSES = 'Новые статусы домашних работ отсутсвуют.'
MES_INFO_PROGRAMM_STOP = 'Программа принудительно остановлена.'

MES_ERROR_CODE_NOT_OK = (
    '\tСбой в работе программы: код ответа API {status_code}!\n'
    '\tДанные отправленного запроса:\n'
    '\t- тип запроса: "GET";\n'
    '\t- URL (эндпоинт): {endpoint};\n'
    '\t- заголовок: {headers}\n'
    '\tДанные ответа:\n'
    '\t- ключ: {key};\n'
    '\t- данные по ключу: {data_by_key};\n'
)
MES_ERROR_ERROR_IN_MAIN = (
    'Сбой в работе программы!\n{error}'
)
MES_ERROR_HOMEWORKS_IS_NOT_LIST = (
    '\tОжидаемый тип данных набора домашних работ - список!\n'
    '\tПолученный тип данных набора домашних работ: {type_data}!'
)
MES_ERROR_KEY_NOT_IN_DICT = (
    '\tВ словаре данных из ответа API отсутвует ключ "homeworks"!'
)
MES_ERROR_KEY_NOT_IN_HOMEWORK = (
    '\tОшибка данных: в объекте "homework" отсутствует ключ "{key}"'
)
MES_ERROR_MESSAGE_SEND_ERROR = (
    '\tОшибка при отправке ботом сообщения!\n'
    '\tТекст ссобщения: {message}\n\tОшибка: {error}.'
)
MES_ERROR_RESPONSE_IS_NOT_DICT = (
    '\tОжидаемый тип данных в ответе API - словарь!\n'
    '\tПолученный тип данных в ответе API: {type_data}!'
)
MES_ERROR_REQUEST_EXCEPTION = (
    '\tСбой в работе программы: ошибка при работе с запросом!\n'
    '\tДанные отправленного запроса:\n'
    '\t- тип запроса: "GET";\n'
    '\t- URL (эндпоинт): {endpoint};\n'
    '\t- заголовок: {headers}\n'
    '\tОшибка:\n\t{error}'
)
MES_ERROR_UNKNOWN_STATUS = (
    'Неучтенный статус домашней работы: {status}!\n'
)

MES_CRITICAL_NOT_TOKEN = (
    'Отсутствует обязательная переменная окружения: {name_token}'
)


logger = logging.getLogger(__name__)


def set_logger():
    """Функция настройки логгера."""
    log_format = (
        '%(asctime)s [%(levelname)s]\n'
        '\tSource: file "%(pathname)s", line %(lineno)d, in %(funcName)s\n'
        '\t%(message)s'
    )
    logging.basicConfig(
        level=logging.DEBUG,
        filename=__file__ + '.log',
        filemode='w',
        format=log_format,
    )
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(handler)


def check_tokens():
    """Функция проверки наличия необходимых токенов."""
    indicator = True
    for token in TOKENS:
        if not globals()[token]:
            logger.critical(
                MES_CRITICAL_NOT_TOKEN.format(name_token=token)
            )
            indicator = False
    if not indicator:
        message = MES_INFO_PROGRAMM_STOP
        logger.info(message)
        raise AttributeError(message)


def send_message(bot, message):
    """Функция отправки сообщения в чат Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(MES_DEBUG_MESSAGE_SEND.format(message=message))
    except Exception as error:
        logger.exception(
            MES_ERROR_MESSAGE_SEND_ERROR.format(
                message=message,
                error=error
            )
        )


def get_api_answer(timestamp):
    """Функция получения ответа API Практикум.Домашка."""
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        response_data = response.json()
    except requests.exceptions.RequestException as error:
        raise Exception(
            MES_ERROR_REQUEST_EXCEPTION.format(
                endpoint=ENDPOINT,
                headers=HEADERS,
                error=error
            )
        )

    if response.status_code != HTTPStatus.OK:
        logger.debug(
            MES_DEBUG_CODE_NOT_OK.format(code=response.status_code)
        )
        for key in KEYS_IN_RESPONSE_WITH_CODE_NOT_OK:
            raise Exception(
                MES_ERROR_CODE_NOT_OK.format(
                    status_code=response.status_code,
                    endpoint=ENDPOINT,
                    headers=HEADERS,
                    key=key,
                    data_by_key=response_data[key]
                )
            )
    logger.debug(MES_DEBUG_CODE_OK)
    return response_data


def check_response(response):
    """Функция проверки ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            MES_ERROR_RESPONSE_IS_NOT_DICT.format(type_data=type(response))
        )
    logger.debug(MES_DEBUG_RESPONSE_IS_DICT)
    if 'homeworks' not in response:
        raise KeyError(MES_ERROR_KEY_NOT_IN_DICT)
    logger.debug(MES_DEBUG_KEY_IN_DICT)
    homeworks = response["homeworks"]
    if not isinstance(homeworks, list):
        raise TypeError(
            MES_ERROR_HOMEWORKS_IS_NOT_LIST.format(type_data=type(homeworks))
        )
    logger.debug(MES_DEBUG_HOMEWORKS_IS_LIST)
    logger.debug(MES_DEBUG_FIELDS_IS_OK)
    return homeworks


def parse_status(homework):
    """Функция извлечения статуса домашней работы."""
    for key in KEYS_IN_HOMEWORK:
        if key not in homework:
            raise KeyError(
                MES_ERROR_KEY_NOT_IN_HOMEWORK.format(key=key)
            )
    logger.debug(MES_DEBUG_KEYS_IN_HOMEWORK)
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            MES_ERROR_UNKNOWN_STATUS.format(status=homework_status)
        )
    logger.debug(MES_DEBUG_STATUS_IS_KNOWN)
    message = MES_INFO_NEW_STATUS.format(
        homework=homework['homework_name'],
        status=HOMEWORK_VERDICTS[homework_status]
    )
    logger.info(message)
    return message


def main():
    """Основная логика работы бота."""
    check_tokens()
    logger.debug(MES_DEBUG_TOKENS_IS_OK)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    message_error_last = ''
    while True:
        try:
            logger.debug(MES_DEBUG_REQUEST_SEND)
            response = get_api_answer(timestamp)
            logger.debug(MES_DEBUG_RESPONSE_GET)
            timestamp = response.get('current_date', timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.info(MES_INFO_NOT_NEW_STATUSES)
            else:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
        except Exception as error:
            message = MES_ERROR_ERROR_IN_MAIN.format(error=error.args[0])
            if message != message_error_last:
                logger.exception(message)
                send_message(bot, message)
                message_error_last = message
            else:
                logger.debug(MES_DEBUG_ERROR_REPEAT)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    set_logger()
    main()
