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

MESSAGES = {
    'debug': {
        'send_message': 'Бот отправил слудющее сообщение:\n\t{message}.',
        'code_200': 'Получен ответ "OK" от API (код 200).',
        'response_is_dict': 'Данные в ответе API поступили в виде словаря.',
        'key_in_dict': (
            'В словаре данных из ответа API присутствует ключ "homeworks".'
        ),
        'homeworks_is_list': 'Набор домашних работ поступил в виде списка.',
        'fields_is_ok': (
            'Основные поля в ответе API соответствуют документации.'
        ),
        'tokens_is_ok': 'Токены проверены. Успех!',
        'send_request': 'Запрос отправлен.',
        'get_response': 'Ответ от API успешно получен.',
    },
    'info': {
        'not_new_stasuses': 'Новые статусы домашних работ отсутсвуют.',
        'new_status': (
            'Изменился статус проверки работы "{homework}". {status}'
        ),
        'exit_from_programm': 'Программа принудительно остановлена.'
    },
    'error': {
        'code_not_200': (
            '\tСбой в работе программы: '
            'код ответа API {status_code}!\n'
            '\tДанные ответа:\n'
            '\t- ключ: {key};\n'
            '\t- данные по ключу: {data_by_key};\n'
            '\t- ответ: {response};\n'
        ),
        'send_message_error': (
            '\tОшибка при отправке ботом сообщения:\n{error}'
        ),
        'request_exception': (
            '\tСбой в работе программы: ошибка при работе с запросом!\n'
            '\tОтвет:\n{error}\n'
        ),
        'not_code_in_key_dict': (
            'В словаре в ответе API отсутствует ключ "code"!\n'
            '\tДанные отправленного запроса:\n'
            '\tОтвет:\n\t{response}\n'
        ),
        'unknown_dict': (
            'Cловарь в ответе API имеет неучтенный формат!\n'
            '\tОтвет:\n{response}\n'
        ),
        'response_is_not_dict': (
            'Ожидаемый тип данных в ответе API - словарь!'
            'Полученный тип данных в ответе API: {type_data}!\n'
        ),
        'data_is_not_dict': (
            'Ожидаемый тип данных в ответе API - словарь!'
            'Полученный тип данных в ответе API: {type_data}!'
        ),
        'key_not_in_dict': (
            'В словаре данных из ответа API отсутвует ключ "homeworks"!'
            'Полученный словарь данных:\n{data}'
        ),
        'data_is_not_list': (
            'Ожидаемый тип данных набора домашних работ - список!'
            'Полученный тип данных набора домашних работ: {type_data}!'
        ),
        'key_not_in_homework': (
            'Ошибка данных: '
            'в объекте "homework" отсутствует ключ "{key}}"!'
            'Поступивший объект:\n{homework}'
        ),
        'unknown_status': (
            'Неучтенный статус домашней работы!\n'
            '\tОжидаются: {keys}\n\tПолучен - {status}'
        ),
        'error_in_main': (
            'Сбой в работе программы!\n{error}'
        ),
    },
    'critical': {
        'token': 'Отсутствует обязательная переменная окружения: {name_token}'
    },
    'data_request': (
        '\tДанные отправленного запроса:\n'
        '\t- тип запроса: "GET";\n'
        '\t- URL (эндпоинт): {endpoint};\n'
        '\t- токен авторизации: проверен при запуске;\n'
        '\t- параметры: "from_date" = {timestamp};'
    ),
}


logging.basicConfig(
    level=logging.DEBUG,
    filename=__file__ + '.log',
    filemode='w',
    format=(
        '%(asctime)s [%(levelname)s]\n'
        '\tSource: file "%(pathname)s", line %(lineno)d, in %(funcName)s\n'
        '\t%(message)s'
    ),
)
logging.Handler = logging.StreamHandler(stream=sys.stdout)
logger = logging.getLogger(__name__)


def check_tokens():
    """Функция проверки наличия необходимых токенов."""
    indicator = 1
    for token in TOKENS:
        if (globals()[token] is None) or (globals()[token] == ''):
            logger.critical(
                MESSAGES['critical']['token'].format(name_token=token)
            )
            indicator *= 0
    if indicator == 0:
        message = MESSAGES['info']['exit_from_programm']
        logger.info(message)
        raise Exception(message)


def send_message(bot, message):
    """Функция отправки сообщения в чат Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(
            MESSAGES['debug']['send_message'].format(message=message)
        )
    except Exception as error:
        logger.exception(
            MESSAGES['error']['send_message_error'].format(error=error)
        )


def get_api_answer(timestamp):
    """Функция получения ответа API Практикум.Домашка."""
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except Exception as error:
        message = (
            MESSAGES['error']['request_exception'].format(
                status_code=response.status_code,
                error=error
            )
            + MESSAGES['data_request'].format(
                endpoint=ENDPOINT,
                timestamp=timestamp,
            )
        )
        logger.exception(message)
        return message

    if response.status_code != HTTPStatus.OK:
        response_data = response.json()
        if not isinstance(response_data, dict):
            raise TypeError(
                MESSAGES['error']['response_is_not_dict'].format(
                    status_code=response.status_code,
                    type_data=type(response_data)
                )
                + MESSAGES['data_request'].format(
                    endpoint=ENDPOINT,
                    timestamp=timestamp,
                )
            )
        logger.debug(MESSAGES['debug']['response_is_dict'])
        if 'code' not in response_data and 'error' not in response_data:
            raise ValueError(
                MESSAGES['error']['unknown_dict'].format(
                    status_code=response.status_code,
                    response=response_data
                )
                + MESSAGES['data_request'].format(
                    endpoint=ENDPOINT,
                    timestamp=timestamp,
                )
            )
        if 'error' in response_data:
            raise Exception(
                MESSAGES['error']['code_not_200'].format(
                    status_code=response.status_code,
                    key='error',
                    data_by_key=response_data['error'],
                    response=response_data,
                ) + MESSAGES['data_request'].format(
                    endpoint=ENDPOINT,
                    timestamp=timestamp,
                )
            )
        elif 'code' in response_data:
            raise Exception(
                MESSAGES['error']['code_not_200'].format(
                    status_code=response.status_code,
                    key='code',
                    data_by_key=response_data['code'],
                    response=response_data,
                ) + MESSAGES['data_request'].format(
                    endpoint=ENDPOINT,
                    timestamp=timestamp,
                )
            )
    logger.debug(MESSAGES['debug']['code_200'])
    return response.json()


def check_response(response):
    """Функция проверки ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            MESSAGES['error']['data_is_not_dict'].format(
                type_data=type(response)
            )
        )
    logger.debug(MESSAGES['debug']['response_is_dict'])
    if 'homeworks' not in response:
        raise KeyError(
            MESSAGES['error']['key_not_in_dict'].format(data=response)
        )
    logger.debug(MESSAGES['debug']['key_in_dict'])
    homeworks = response["homeworks"]
    if not isinstance(homeworks, list):
        raise TypeError(
            MESSAGES['error']['data_is_not_list'].format(
                type_data=type(response)
            )
        )
    logger.debug(MESSAGES['debug']['homeworks_is_list'])
    logger.debug(MESSAGES['debug']['fields_is_ok'])
    return homeworks


def parse_status(homework):
    """Функция извлечения статуса домашней работы."""
    for key in KEYS_IN_HOMEWORK:
        if 'homework_name' not in homework:
            raise KeyError(
                MESSAGES['error']['key_not_in_homework'].format(
                    key=key,
                    homework=type(homework)
                )
            )
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        keys = ''
        for key in HOMEWORK_VERDICTS.keys():
            keys += (key + ', ')
        raise ValueError(
            MESSAGES['error']['unknown_status'].format(
                keys=keys[:-2],
                status=homework_status
            )
        )
    message = MESSAGES['info']['new_status'].format(
        homework=homework['homework_name'],
        status=HOMEWORK_VERDICTS[homework_status]
    )
    logger.info(message)
    return message


def main():
    """Основная логика работы бота."""
    check_tokens()
    logger.debug(MESSAGES['debug']['tokens_is_ok'])
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            logger.debug(MESSAGES['debug']['send_request'])
            response = get_api_answer(timestamp)
            logger.debug(MESSAGES['debug']['get_response'])
            timestamp = response['current_date']
            homeworks = check_response(response)
            if len(homeworks) == 0:
                logger.info(MESSAGES['info']['not_new_stasuses'])
            else:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
        except (KeyError, TypeError, ValueError) as error:
            message = error.args[0]
            logger.exception(message)
            send_message(bot, message)
        except Exception as error:
            message = MESSAGES['error']['error_in_main'].format(
                error=error.args[0]
            )
            logger.exception(message)
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
