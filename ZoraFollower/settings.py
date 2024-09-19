"""

    module               - 1 автофолловер
                         - 2 соберет статистику по аккам
                         - 3 отписаться от акков
    percent_for_unfollow - процент от какого количества отписываться, при 100 отпишется от всех
    follow_from_exel     - True / False, при True будет рандомно брать адреса для подписок из файла
                           amounts_follows >= Addresses For Follow
    donors_wallets       - это кошельки пользователей, на подписчиков которых мы подписываемся
                           количество подписчиков у донора > 500
    amounts_follows      - минимальное и максимальное количество подписок для одного аккаунта
    delay_follows        - минимальная и максимальная задержка между подписками/отписками
    delay_wallets        - минимальная и максимальная задержка между кошельками
    retries              - кол-во попыток при возникновении ошибок

"""

module = 3

percent_for_unfollow = 100

follow_from_exel = False

donors_wallets = [
    '0x2c236be4a7b9420156df76eee07cd1ad35850038',
    '0xdbc1f0b92e37b01ae58944435d553aa2382eb9d3',
]

amounts_follows = [10, 20]
delay_follows = [1, 1]
delay_wallets = [100, 300]
retries = 3
